CREATE TABLE customers (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL CHECK (btrim(name) <> ''),
  owner TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT ''
);

ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT 'Lainnya';
ALTER TABLE transactions
  ADD COLUMN customer_id BIGINT REFERENCES customers(id),
  ADD COLUMN customer_snapshot JSONB,
  ADD COLUMN fulfillment_status TEXT NOT NULL DEFAULT 'delivered'
    CHECK (fulfillment_status IN ('draft', 'ready', 'delivered'));

CREATE INDEX idx_transactions_customer ON transactions (customer_id);
CREATE SEQUENCE dashboard_invoice_seq;

CREATE TABLE dashboard_settings (
  name TEXT PRIMARY KEY,
  value TIMESTAMPTZ NOT NULL
);
