-- Skema inti Toko Indo Telur. Dijalankan oleh scripts/run-migrations.js,
-- sehingga seluruh file ini berjalan dalam satu transaksi PostgreSQL.

CREATE TABLE IF NOT EXISTS products (
  id BIGSERIAL PRIMARY KEY,
  sku VARCHAR(64) UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  price NUMERIC(14, 2) NOT NULL,
  stock NUMERIC(14, 3) NOT NULL DEFAULT 0,
  unit VARCHAR(32) NOT NULL DEFAULT 'pcs',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_products_sku_not_blank CHECK (sku IS NULL OR BTRIM(sku) <> ''),
  CONSTRAINT ck_products_name_not_blank CHECK (BTRIM(name) <> ''),
  CONSTRAINT ck_products_price_nonnegative CHECK (price >= 0),
  CONSTRAINT ck_products_stock_nonnegative CHECK (stock >= 0),
  CONSTRAINT ck_products_unit_not_blank CHECK (BTRIM(unit) <> '')
);

CREATE TABLE IF NOT EXISTS transactions (
  id BIGSERIAL PRIMARY KEY,
  client_transaction_id UUID NOT NULL UNIQUE,
  invoice_number VARCHAR(80) NOT NULL UNIQUE,
  transaction_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  total_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
  payment_method VARCHAR(16) NOT NULL DEFAULT 'cash',
  payment_status VARCHAR(16) NOT NULL DEFAULT 'paid',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_transactions_invoice_not_blank CHECK (BTRIM(invoice_number) <> ''),
  CONSTRAINT ck_transactions_total_nonnegative CHECK (total_amount >= 0),
  CONSTRAINT ck_transactions_payment_method CHECK (payment_method IN ('cash', 'transfer')),
  CONSTRAINT ck_transactions_payment_status CHECK (payment_status IN ('unpaid', 'paid', 'partial'))
);

CREATE TABLE IF NOT EXISTS transaction_items (
  id BIGSERIAL PRIMARY KEY,
  transaction_id BIGINT NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT,
  product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
  product_name_snapshot TEXT NOT NULL,
  unit_snapshot VARCHAR(32) NOT NULL,
  quantity NUMERIC(14, 3) NOT NULL,
  unit_price NUMERIC(14, 2) NOT NULL,
  subtotal NUMERIC(14, 2) GENERATED ALWAYS AS (ROUND(quantity * unit_price, 2)) STORED,
  CONSTRAINT ck_transaction_items_name_not_blank CHECK (BTRIM(product_name_snapshot) <> ''),
  CONSTRAINT ck_transaction_items_unit_not_blank CHECK (BTRIM(unit_snapshot) <> ''),
  CONSTRAINT ck_transaction_items_quantity_positive CHECK (quantity > 0),
  CONSTRAINT ck_transaction_items_unit_price_nonnegative CHECK (unit_price >= 0),
  CONSTRAINT ck_transaction_items_subtotal_nonnegative CHECK (subtotal >= 0)
);

CREATE TABLE IF NOT EXISTS stock_movements (
  id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
  transaction_id BIGINT REFERENCES transactions(id) ON DELETE RESTRICT,
  movement_type VARCHAR(16) NOT NULL,
  quantity_change NUMERIC(14, 3) NOT NULL,
  stock_before NUMERIC(14, 3) NOT NULL,
  stock_after NUMERIC(14, 3) NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ck_stock_movements_type CHECK (movement_type IN ('sale', 'restock', 'adjustment', 'return')),
  CONSTRAINT ck_stock_movements_nonzero_change CHECK (quantity_change <> 0),
  CONSTRAINT ck_stock_movements_sale_direction CHECK (
    (movement_type <> 'sale' OR (transaction_id IS NOT NULL AND quantity_change < 0))
    AND (movement_type NOT IN ('restock', 'return') OR quantity_change > 0)
  ),
  CONSTRAINT ck_stock_movements_stock_consistency CHECK (
    stock_before >= 0
    AND stock_after >= 0
    AND stock_after = stock_before + quantity_change
  )
);

CREATE TABLE IF NOT EXISTS sync_records (
  id BIGSERIAL PRIMARY KEY,
  client_transaction_id UUID NOT NULL UNIQUE,
  device_id VARCHAR(128) NOT NULL,
  server_transaction_id BIGINT UNIQUE REFERENCES transactions(id) ON DELETE RESTRICT,
  status VARCHAR(16) NOT NULL DEFAULT 'received',
  error_message TEXT,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ,
  CONSTRAINT ck_sync_records_device_not_blank CHECK (BTRIM(device_id) <> ''),
  CONSTRAINT ck_sync_records_status CHECK (status IN ('received', 'processed', 'failed')),
  CONSTRAINT ck_sync_records_lifecycle CHECK (
    (status = 'received' AND server_transaction_id IS NULL AND processed_at IS NULL AND error_message IS NULL)
    OR (status = 'processed' AND server_transaction_id IS NOT NULL AND processed_at IS NOT NULL AND error_message IS NULL)
    OR (status = 'failed' AND server_transaction_id IS NULL AND processed_at IS NOT NULL AND BTRIM(error_message) <> '')
  )
);

CREATE OR REPLACE FUNCTION toko_indo_telur_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION toko_indo_telur_require_zero_initial_stock()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.stock <> 0 THEN
    RAISE EXCEPTION 'Produk baru harus dimulai dengan stok 0; gunakan stock_movements untuk restock awal';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION toko_indo_telur_prevent_direct_stock_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.stock IS DISTINCT FROM OLD.stock
     AND COALESCE(current_setting('toko_indo_telur.stock_movement_write', TRUE), 'off') <> 'on' THEN
    RAISE EXCEPTION 'Stok produk hanya boleh berubah melalui stock_movements';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION toko_indo_telur_apply_stock_movement()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  current_stock NUMERIC(14, 3);
  new_stock NUMERIC(14, 3);
BEGIN
  SELECT stock INTO current_stock
  FROM products
  WHERE id = NEW.product_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Produk % tidak ditemukan', NEW.product_id;
  END IF;

  new_stock := current_stock + NEW.quantity_change;
  IF new_stock < 0 THEN
    RAISE EXCEPTION 'Stok tidak mencukupi untuk perubahan % pada produk %', NEW.quantity_change, NEW.product_id;
  END IF;

  NEW.stock_before := current_stock;
  NEW.stock_after := new_stock;

  PERFORM set_config('toko_indo_telur.stock_movement_write', 'on', TRUE);
  UPDATE products SET stock = new_stock WHERE id = NEW.product_id;
  PERFORM set_config('toko_indo_telur.stock_movement_write', 'off', TRUE);

  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION toko_indo_telur_prevent_stock_movement_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'stock_movements adalah catatan audit yang tidak dapat diubah atau dihapus';
END;
$$;

CREATE OR REPLACE FUNCTION toko_indo_telur_refresh_transaction_total()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  affected_transaction_id BIGINT;
BEGIN
  affected_transaction_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.transaction_id ELSE NEW.transaction_id END;

  UPDATE transactions
  SET total_amount = COALESCE((
    SELECT SUM(subtotal) FROM transaction_items WHERE transaction_id = affected_transaction_id
  ), 0)
  WHERE id = affected_transaction_id;

  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION toko_indo_telur_validate_sync_transaction()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  stored_client_transaction_id UUID;
BEGIN
  IF NEW.server_transaction_id IS NOT NULL THEN
    SELECT client_transaction_id INTO stored_client_transaction_id
    FROM transactions
    WHERE id = NEW.server_transaction_id;

    IF NOT FOUND OR stored_client_transaction_id <> NEW.client_transaction_id THEN
      RAISE EXCEPTION 'server_transaction_id harus merujuk transaksi dengan client_transaction_id yang sama';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_products_set_updated_at
BEFORE UPDATE ON products
FOR EACH ROW EXECUTE FUNCTION toko_indo_telur_set_updated_at();

CREATE TRIGGER trg_products_require_zero_initial_stock
BEFORE INSERT ON products
FOR EACH ROW EXECUTE FUNCTION toko_indo_telur_require_zero_initial_stock();

CREATE TRIGGER trg_products_prevent_direct_stock_update
BEFORE UPDATE OF stock ON products
FOR EACH ROW EXECUTE FUNCTION toko_indo_telur_prevent_direct_stock_update();

CREATE TRIGGER trg_stock_movements_apply_stock
BEFORE INSERT ON stock_movements
FOR EACH ROW EXECUTE FUNCTION toko_indo_telur_apply_stock_movement();

CREATE TRIGGER trg_stock_movements_immutable
BEFORE UPDATE OR DELETE ON stock_movements
FOR EACH ROW EXECUTE FUNCTION toko_indo_telur_prevent_stock_movement_change();

CREATE TRIGGER trg_transaction_items_refresh_total
AFTER INSERT OR UPDATE OR DELETE ON transaction_items
FOR EACH ROW EXECUTE FUNCTION toko_indo_telur_refresh_transaction_total();

CREATE TRIGGER trg_sync_records_validate_transaction
BEFORE INSERT OR UPDATE OF client_transaction_id, server_transaction_id ON sync_records
FOR EACH ROW EXECUTE FUNCTION toko_indo_telur_validate_sync_transaction();

CREATE INDEX IF NOT EXISTS idx_products_active_name
  ON products (name)
  WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_transactions_transaction_date
  ON transactions (transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_payment_status_date
  ON transactions (payment_status, transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_transaction_items_transaction_id
  ON transaction_items (transaction_id);

CREATE INDEX IF NOT EXISTS idx_transaction_items_product_id
  ON transaction_items (product_id);

CREATE INDEX IF NOT EXISTS idx_stock_movements_product_created_at
  ON stock_movements (product_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_stock_movements_transaction_id
  ON stock_movements (transaction_id)
  WHERE transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sync_records_status_received_at
  ON sync_records (status, received_at);

CREATE INDEX IF NOT EXISTS idx_sync_records_device_id
  ON sync_records (device_id);
