import { Router } from "express";
import { pool } from "../config/database.js";

const router = Router();
const statuses = ["draft", "ready", "delivered"];
const paymentMethods = ["cash", "transfer"];
const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const dateFormat = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Makassar" });
const timeFormat = new Intl.DateTimeFormat("id-ID", { timeZone: "Asia/Makassar", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

function fail(message, status = 400) {
  throw Object.assign(new Error(message), { status });
}

function restorePaymentState(receipt) {
  const paymentStatus = receipt.paymentStatus ?? "unpaid";
  const suppliedPaymentMethod = receipt.paymentMethod;
  const paidAt = receipt.paidAt ?? null;

  if (!['unpaid', 'paid', 'partial'].includes(paymentStatus)) {
    fail("Status pembayaran pada backup tidak valid.");
  }
  if (suppliedPaymentMethod !== undefined && suppliedPaymentMethod !== null &&
      !paymentMethods.includes(suppliedPaymentMethod)) {
    fail("Metode pembayaran pada backup tidak valid.");
  }
  if (receipt.paidAt !== undefined && paidAt !== null &&
      (typeof paidAt !== "string" || !Number.isFinite(Date.parse(paidAt)))) {
    fail("Waktu pembayaran pada backup tidak valid.");
  }

  if (paymentStatus === "unpaid") {
    if (paidAt !== null) fail("Nota unpaid pada backup tidak boleh memiliki waktu pembayaran.");
    // Backup sebelum migration 003 can contain the old database default cash.
    if (suppliedPaymentMethod === undefined || suppliedPaymentMethod === null || suppliedPaymentMethod === "cash") {
      return { paymentStatus, paymentMethod: null, paidAt: null };
    }
    fail("Nota unpaid pada backup tidak boleh memiliki metode pembayaran.");
  }
  if (!paymentMethods.includes(suppliedPaymentMethod)) {
    fail("Nota paid atau partial pada backup wajib memiliki metode pembayaran yang valid.");
  }
  return { paymentStatus, paymentMethod: suppliedPaymentMethod, paidAt };
}

function text(value, label, limit, required = false) {
  if (typeof value !== "string" || value.trim().length > limit || (required && !value.trim())) {
    fail(label + " tidak valid.");
  }
  return value.trim();
}

function decimal(value, scale, maximum, minimum = 0) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum || value > maximum ||
      Number(value.toFixed(scale)) !== value) fail("Nilai harga, stok, atau jumlah tidak valid.");
  return value;
}

function id(value) {
  if (typeof value !== "string" || !/^[1-9]\d{0,17}$/.test(value)) fail("ID tidak valid.");
  return value;
}

function customer(row) {
  return { id: row.id, name: row.name, owner: row.owner, phone: row.phone, area: row.address, initial: Array.from(row.name)[0]?.toLocaleUpperCase("id-ID") };
}

function icon(category) {
  const icons = { Telur: "egg", Beras: "grain", Tepung: "grain", Minyak: "oil" };
  return Object.hasOwn(icons, category) ? icons[category] : "box";
}

function product(row) {
  return { key: row.id, name: row.name, sku: row.sku, description: row.description, category: row.category, unit: row.unit, price: Number(row.price), stock: Number(row.stock), icon: icon(row.category), archived: !row.is_active };
}

function customerInput(body) {
  return [text(body.name, "Nama toko", 200, true), text(body.owner ?? "", "Pemilik", 200),
    text(body.phone ?? "", "Nomor HP", 40), text(body.area ?? "", "Alamat", 500)];
}

function productInput(body) {
  return [text(body.name, "Nama produk", 200, true), text(body.category, "Kategori", 60, true),
    text(body.unit, "Satuan", 32, true), decimal(body.price, 2, 999999999999.99),
    decimal(body.stock, 3, 99999999999.999)];
}

async function atomic(work) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await work(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

async function snapshot(client) {
  const { rows: products } = await client.query("SELECT * FROM products ORDER BY id");
  const { rows: customers } = await client.query("SELECT * FROM customers ORDER BY id");
  const { rows: sales } = await client.query(`
    SELECT t.*, COALESCE(s.status, 'processed') AS sync_status,
      COALESCE((SELECT jsonb_agg(jsonb_build_object(
        'key', i.product_id::text, 'name', i.product_name_snapshot, 'unit', i.unit_snapshot,
        'quantity', i.quantity, 'price', i.unit_price, 'subtotal', i.subtotal
      ) ORDER BY i.id) FROM transaction_items i WHERE i.transaction_id = t.id), '[]') AS lines
    FROM transactions t LEFT JOIN sync_records s ON s.server_transaction_id = t.id
    ORDER BY t.transaction_date DESC, t.id DESC
  `);
  const { rows: settings } = await client.query("SELECT name, value FROM dashboard_settings");
  const legacyCustomer = { name: "Pelanggan umum", owner: "", area: "", initial: "P" };
  return {
    items: products.map(product), customers: customers.map(customer),
    receipts: sales.map((sale) => ({
      number: sale.invoice_number, clientId: sale.client_transaction_id, createdAt: sale.transaction_date,
      date: dateFormat.format(sale.transaction_date), time: timeFormat.format(sale.transaction_date).replace(":", "."),
      customer: sale.customer_snapshot ?? legacyCustomer, total: Number(sale.total_amount),
      status: sale.fulfillment_status, pending: sale.sync_status !== "processed",
      paymentMethod: sale.payment_method, paymentStatus: sale.payment_status, paidAt: sale.paid_at, notes: sale.notes,
      quantities: sale.lines.reduce((quantities, line) => {
        quantities[line.key] = Number(((quantities[line.key] ?? 0) + line.quantity).toFixed(3));
        return quantities;
      }, {}), lines: sale.lines,
    })),
    ...Object.fromEntries(settings.map(({ name, value }) => [name, value])),
  };
}

async function consistentSnapshot() {
  return atomic(async (client) => {
    await client.query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY");
    return snapshot(client);
  });
}

function reply(res, data, status = 200) {
  res.status(status).json({ success: true, data });
}

router.use((req, _res, next) => {
  if (["POST", "PUT", "PATCH"].includes(req.method) && req.path !== "/backup" &&
      (!req.body || typeof req.body !== "object" || Array.isArray(req.body))) {
    return next(Object.assign(new Error("Body JSON wajib diisi."), { status: 400 }));
  }
  next();
});

router.get("/", async (_req, res) => reply(res, await consistentSnapshot()));

router.post("/customers", async (req, res) => {
  const { rows: [row] } = await pool.query("INSERT INTO customers (name, owner, phone, address) VALUES ($1,$2,$3,$4) RETURNING *", customerInput(req.body));
  reply(res, customer(row), 201);
});

async function adjustStock(client, key, stock) {
  await client.query(`
    INSERT INTO stock_movements (product_id, movement_type, quantity_change, notes)
    SELECT id, CASE WHEN $2::numeric > stock THEN 'restock' ELSE 'adjustment' END,
      $2::numeric - stock, 'Penyesuaian stok dari dashboard'
    FROM products WHERE id=$1 AND stock <> $2::numeric
  `, [key, stock]);
}

async function saveProduct(client, input, key, expectedStock) {
  const [name, category, unit, price, stock] = input;
  if (key) {
    const existing = (await lockProducts(client, [key])).get(key);
    if (!existing?.is_active) fail("Produk tidak ditemukan.", 404);
    if (Number(existing.stock) !== expectedStock) fail("Stok berubah. Muat ulang data sebelum mengubah produk.", 409);
  }
  const result = key
    ? await client.query("UPDATE products SET name=$1, category=$2, unit=$3, price=$4 WHERE id=$5 AND is_active RETURNING id", [name, category, unit, price, key])
    : await client.query("INSERT INTO products (name, category, unit, price) VALUES ($1,$2,$3,$4) RETURNING id", [name, category, unit, price]);
  if (!result.rowCount) fail("Produk tidak ditemukan.", 404);
  key = result.rows[0].id;
  await adjustStock(client, key, stock);
  const { rows: [row] } = await client.query("SELECT * FROM products WHERE id=$1", [key]);
  return product(row);
}

router.post("/products", async (req, res) => reply(res, await atomic((client) => saveProduct(client, productInput(req.body))), 201));
router.put("/products/:id", async (req, res) => {
  const expectedStock = decimal(req.body.expectedStock, 3, 99999999999.999);
  reply(res, await atomic((client) => saveProduct(client, productInput(req.body), id(req.params.id), expectedStock)));
});
router.delete("/products/:id", async (req, res) => {
  const result = await pool.query("UPDATE products SET is_active=false WHERE id=$1 RETURNING id", [id(req.params.id)]);
  if (!result.rowCount) fail("Produk tidak ditemukan.", 404);
  reply(res, { key: result.rows[0].id });
});

async function lockProducts(client, keys) {
  const { rows } = await client.query("SELECT * FROM products WHERE id=ANY($1::bigint[]) ORDER BY id FOR UPDATE", [keys]);
  return new Map(rows.map((row) => [row.id, row]));
}

function checkStock(products, lines) {
  for (const line of lines) {
    const row = products.get(line.key);
    if (!row?.is_active) fail("Produk di dalam nota sudah tidak aktif.", 409);
    if (Number(row.stock) < line.quantity) fail("Stok " + row.name + " tidak mencukupi.", 409);
  }
}

async function recordSale(client, saleId, lines) {
  for (const line of lines) {
    await client.query("INSERT INTO stock_movements (product_id, transaction_id, movement_type, quantity_change) VALUES ($1,$2,'sale',$3)", [line.key, saleId, -line.quantity]);
  }
}

router.post("/receipts", async (req, res) => {
  const { clientId, customerId, status, items, createdAt, deviceId = "web" } = req.body;
  if (typeof clientId !== "string" || !uuid.test(clientId) || !["draft", "ready"].includes(status)) fail("Identitas atau status nota tidak valid.");
  if (!Array.isArray(items) || !items.length || items.length > 200) fail("Isi barang nota tidak valid.");
  const lines = items.map((line) => {
    if (!line || typeof line !== "object") fail("Barang tidak valid.");
    return { key: id(line.key), quantity: decimal(line.quantity, 3, 99999999999.999, 0.001), price: decimal(line.price, 2, 999999999999.99) };
  });
  if (new Set(lines.map((line) => line.key)).size !== lines.length) fail("Produk ganda dalam satu nota.");
  const buyerId = id(customerId);
  const device = text(deviceId, "Perangkat", 128, true);
  const transactionDate = createdAt === undefined ? new Date() : new Date(typeof createdAt === "string" ? createdAt : NaN);
  if (!Number.isFinite(transactionDate.getTime()) || transactionDate.getTime() > Date.now() + 300000) fail("Waktu nota tidak valid.");
  const result = await atomic(async (client) => {
    await client.query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", [clientId.toLowerCase()]);
    const existing = await client.query("SELECT invoice_number FROM transactions WHERE client_transaction_id=$1", [clientId]);
    if (existing.rowCount) return { number: existing.rows[0].invoice_number };
    const buyer = await client.query("SELECT * FROM customers WHERE id=$1 FOR KEY SHARE", [buyerId]);
    if (!buyer.rowCount) fail("Pelanggan tidak ditemukan.", 404);
    const products = await lockProducts(client, lines.map((line) => line.key));
    checkStock(products, lines);
    for (const line of lines) {
      if (Number(products.get(line.key).price) !== line.price) fail("Harga produk berubah. Periksa kembali nota.", 409);
    }
    const { rows: [sale] } = await client.query(`
      INSERT INTO transactions (client_transaction_id, invoice_number, customer_id, customer_snapshot, fulfillment_status, payment_method, payment_status, paid_at, transaction_date)
      VALUES ($1, 'NT-' || to_char(nextval('dashboard_invoice_seq'), 'FM000000000000'), $2,$3,$4,NULL,'unpaid',NULL,$5)
      RETURNING id, invoice_number
    `, [clientId, buyerId, customer(buyer.rows[0]), status, transactionDate]);
    for (const line of lines) {
      const row = products.get(line.key);
      await client.query(`
        INSERT INTO transaction_items (transaction_id, product_id, product_name_snapshot, unit_snapshot, quantity, unit_price)
        VALUES ($1,$2,$3,$4,$5,$6)
      `, [sale.id, line.key, row.name, row.unit, line.quantity, row.price]);
    }
    if (status === "ready") await recordSale(client, sale.id, lines);
    await client.query(`
      INSERT INTO sync_records (client_transaction_id, device_id, server_transaction_id, status, processed_at)
      VALUES ($1,$2,$3,'processed',NOW())
    `, [clientId, device, sale.id]);
    await client.query("INSERT INTO dashboard_settings VALUES ('lastSync', NOW()) ON CONFLICT (name) DO UPDATE SET value=excluded.value");
    return { number: sale.invoice_number };
  });
  reply(res, result, 201);
});

router.patch("/receipts/:number/status", async (req, res) => {
  const { status } = req.body;
  if (!["ready", "delivered"].includes(status)) fail("Status tidak valid.");
  await atomic(async (client) => {
    const { rows: [sale] } = await client.query("SELECT id, fulfillment_status FROM transactions WHERE invoice_number=$1 FOR UPDATE", [req.params.number]);
    if (!sale) fail("Nota tidak ditemukan.", 404);
    if (sale.fulfillment_status === status) return;
    if (sale.fulfillment_status === "delivered") fail("Nota sudah diantar.", 409);
    if (sale.fulfillment_status === "draft") {
      const { rows: lines } = await client.query("SELECT product_id AS key, SUM(quantity)::float8 AS quantity FROM transaction_items WHERE transaction_id=$1 GROUP BY product_id ORDER BY product_id", [sale.id]);
      if (!lines.length) fail("Nota tidak memiliki barang.", 409);
      const products = await lockProducts(client, lines.map((line) => line.key));
      checkStock(products, lines);
      await recordSale(client, sale.id, lines);
    }
    await client.query("UPDATE transactions SET fulfillment_status=$2 WHERE id=$1", [sale.id, status]);
  });
  reply(res, { status });
});

router.patch("/receipts/:number/payment", async (req, res) => {
  const { paymentMethod } = req.body;
  if (!paymentMethods.includes(paymentMethod)) fail("Metode pembayaran tidak valid.");
  const payment = await atomic(async (client) => {
    const { rows: [sale] } = await client.query(`
      SELECT id, invoice_number, fulfillment_status, payment_status, payment_method, paid_at
      FROM transactions
      WHERE invoice_number=$1
      FOR UPDATE
    `, [req.params.number]);
    if (!sale) fail("Nota tidak ditemukan.", 404);
    if (sale.payment_status === "paid") {
      if (sale.payment_method !== paymentMethod) fail("Pembayaran nota sudah tercatat dengan metode berbeda.", 409);
      return {
        number: sale.invoice_number,
        paymentMethod: sale.payment_method,
        paymentStatus: sale.payment_status,
        paidAt: sale.paid_at,
      };
    }
    if (sale.payment_status === "partial") fail("Pembayaran partial tidak dapat diselesaikan otomatis.", 409);
    if (sale.payment_status !== "unpaid") fail("Status pembayaran nota tidak dapat diubah.", 409);
    if (sale.fulfillment_status !== "delivered") fail("Pembayaran hanya dapat dicatat setelah nota diantar.", 409);
    const { rows: [updated] } = await client.query(`
      UPDATE transactions
      SET payment_method=$2, payment_status='paid', paid_at=NOW()
      WHERE id=$1
      RETURNING invoice_number, payment_method, payment_status, paid_at
    `, [sale.id, paymentMethod]);
    return {
      number: updated.invoice_number,
      paymentMethod: updated.payment_method,
      paymentStatus: updated.payment_status,
      paidAt: updated.paid_at,
    };
  });
  reply(res, payment);
});

router.post("/backup", async (_req, res) => {
  const data = await atomic(async (client) => {
    await client.query("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ");
    const result = await snapshot(client);
    const { rows: [row] } = await client.query("INSERT INTO dashboard_settings VALUES ('lastBackup', NOW()) ON CONFLICT (name) DO UPDATE SET value=excluded.value RETURNING value");
    return { ...result, version: 2, createdAt: row.value, lastBackup: row.value };
  });
  reply(res, data);
});

router.post("/restore", async (req, res) => {
  const { version, items, customers, receipts } = req.body;
  if (version !== 2 || ![items, customers, receipts].every(Array.isArray) ||
      items.length > 10000 || customers.length > 10000 || receipts.length > 25000) fail("File backup tidak valid.");
  const paymentStates = receipts.map(restorePaymentState);
  await atomic(async (client) => {
    await client.query("LOCK TABLE customers, products, transactions IN SHARE ROW EXCLUSIVE MODE");
    const { rows: [state] } = await client.query("SELECT EXISTS (SELECT FROM customers UNION ALL SELECT FROM products UNION ALL SELECT FROM transactions) AS occupied");
    if (state.occupied) fail("Pemulihan membutuhkan database kosong agar data dan catatan stok yang ada tetap aman.", 409);
    const productIds = new Map();
    const customerIds = new Map();
    for (const item of items) {
      const key = id(item?.key);
      if (productIds.has(key) || typeof item.archived !== "boolean") fail("Produk backup tidak valid.");
      const saved = await saveProduct(client, productInput(item));
      productIds.set(key, saved.key);
      const sku = item.sku == null ? null : text(item.sku, "SKU", 64, true);
      const description = item.description == null ? null : text(item.description, "Deskripsi", 100000);
      await client.query("UPDATE products SET sku=$2, description=$3, is_active=$4 WHERE id=$1", [saved.key, sku, description, !item.archived]);
    }
    for (const entry of customers) {
      const key = id(entry?.id);
      if (customerIds.has(key)) fail("Pelanggan backup ganda.");
      const { rows: [saved] } = await client.query("INSERT INTO customers (name, owner, phone, address) VALUES ($1,$2,$3,$4) RETURNING id", customerInput(entry));
      customerIds.set(key, saved.id);
    }
    let invoiceSequence = 0;
    for (const [index, receipt] of receipts.entries()) {
      if (!receipt || typeof receipt.clientId !== "string" || !uuid.test(receipt.clientId) ||
          !statuses.includes(receipt.status) || !Array.isArray(receipt.lines) || receipt.lines.length > 1000 ||
          typeof receipt.createdAt !== "string" || !Number.isFinite(Date.parse(receipt.createdAt))) fail("Nota backup tidak valid.");
      const number = text(receipt.number, "Nomor nota", 80, true);
      if (/^NT-\d{12}$/.test(number)) invoiceSequence = Math.max(invoiceSequence, Number(number.slice(3)));
      const [name, owner, phone, area] = customerInput(receipt.customer ?? {});
      const customerId = receipt.customer.id ? customerIds.get(id(receipt.customer.id)) : null;
      if (receipt.customer.id && !customerId) fail("Pelanggan nota tidak ditemukan dalam backup.");
      const buyer = { id: customerId, name, owner, phone, area, initial: Array.from(name)[0].toLocaleUpperCase("id-ID") };
        const { paymentStatus, paymentMethod, paidAt } = paymentStates[index];
      const notes = receipt.notes == null ? null : text(receipt.notes, "Catatan", 100000);
      const { rows: [sale] } = await client.query(`
        INSERT INTO transactions (client_transaction_id, invoice_number, customer_id, customer_snapshot, fulfillment_status, transaction_date, payment_method, payment_status, paid_at, notes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id
      `, [receipt.clientId, number, customerId, buyer, receipt.status, receipt.createdAt, paymentMethod, paymentStatus, paidAt, notes]);
      for (const line of receipt.lines) {
        const key = productIds.get(id(line?.key));
        if (!key) fail("Produk nota tidak ditemukan dalam backup.");
        await client.query(`
          INSERT INTO transaction_items (transaction_id, product_id, product_name_snapshot, unit_snapshot, quantity, unit_price)
          VALUES ($1,$2,$3,$4,$5,$6)
        `, [sale.id, key, text(line.name,"Nama produk",200,true), text(line.unit,"Satuan",32,true),
          decimal(line.quantity,3,99999999999.999,0.001), decimal(line.price,2,999999999999.99)]);
      }
      const { rows: [saved] } = await client.query("SELECT total_amount FROM transactions WHERE id=$1", [sale.id]);
      if (Number(saved.total_amount) !== receipt.total) fail("Total nota backup tidak cocok dengan rincian.");
      await client.query(`
        INSERT INTO sync_records (client_transaction_id, device_id, server_transaction_id, status, processed_at)
        VALUES ($1,'backup',$2,'processed',NOW())
      `, [receipt.clientId, sale.id]);
    }
    if (invoiceSequence) await client.query("SELECT setval('dashboard_invoice_seq', $1)", [invoiceSequence]);
    await client.query("INSERT INTO dashboard_settings VALUES ('lastBackup', NOW()), ('lastSync', NOW()) ON CONFLICT (name) DO UPDATE SET value=excluded.value");
  });
  reply(res, await consistentSnapshot());
});

router.use((error, _req, res, next) => {
  if (res.headersSent) return next(error);
  if (error.status >= 400 && error.status < 500) {
    return res.status(error.status).json({ success: false, message: error.status === 413 ? "File backup terlalu besar." : error.message });
  }
  if (error.code === "22003" || error.code === "23505") {
    return res.status(409).json({ success: false, message: "Nilai melebihi batas atau data sudah ada." });
  }
  next(error);
});

export default router;
