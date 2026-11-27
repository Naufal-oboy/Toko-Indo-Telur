import "dotenv/config";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { once } from "node:events";
import { readFile } from "node:fs/promises";
import pg from "pg";

const database = {
  host: process.env.PGHOST || "localhost",
  port: Number(process.env.PGPORT || 5432),
  database: process.env.PGDATABASE,
  user: process.env.PGUSER,
  password: process.env.PGPASSWORD,
};
const admin = new pg.Pool(database);
const schema = "dashboard_test_" + randomUUID().replaceAll("-", "");
let pool;
let server;
let schemaCreated = false;

try {
  await admin.query(`CREATE SCHEMA "${schema}"`);
  schemaCreated = true;
  process.env.PGOPTIONS = "-c search_path=" + schema;
  ({ pool } = await import("../src/config/database.js"));
  const { rows: [target] } = await pool.query("SELECT current_schema() AS name");
  assert.equal(target.name, schema, "Test operations must stay in an isolated schema.");
  for (const filename of ["001_initial_schema.sql", "002_dashboard.sql"]) {
    await pool.query(await readFile(new URL("../src/database/migrations/" + filename, import.meta.url), "utf8"));
  }
  const legacyUnpaidId = randomUUID();
  await pool.query(
    "INSERT INTO transactions (client_transaction_id, invoice_number, payment_status) VALUES ($1, $2, 'unpaid')",
    [legacyUnpaidId, "LEGACY-UNPAID"],
  );
  await pool.query(await readFile(new URL("../src/database/migrations/003_payment_workflow.sql", import.meta.url), "utf8"));
  const { rows: [legacyUnpaid] } = await pool.query("SELECT payment_method, paid_at FROM transactions WHERE client_transaction_id=$1", [legacyUnpaidId]);
  assert.equal(legacyUnpaid.payment_method, null);
  assert.equal(legacyUnpaid.paid_at, null);
  const { app } = await import("../src/server.js");
  server = app.listen(0, "127.0.0.1");
  await once(server, "listening");
  const base = "http://127.0.0.1:" + server.address().port + "/api/dashboard";

  async function request(path = "", method = "GET", body, status = 200) {
    const response = await fetch(base + path, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json();
    assert.equal(response.status, status, JSON.stringify(result));
    assert.equal(result.success, status < 400);
    return result.data;
  }

  const values = { name: "Telur uji", category: "Telur", unit: "rak", price: 56000.25, stock: 5 };
  await request("/customers", "POST", undefined, 400);
  const customer = await request("/customers", "POST", { name: "Toko uji", phone: "0812" }, 201);
  const product = await request("/products", "POST", values, 201);
  const draft = { clientId: randomUUID(), customerId: customer.id, status: "draft", items: [{ key: product.key, quantity: 2, price: values.price }] };
  const [first, retry] = await Promise.all([
    request("/receipts", "POST", draft, 201),
    request("/receipts", "POST", draft, 201),
  ]);
  assert.equal(first.number, retry.number);
  let data = await request();
  assert.equal(data.items[0].stock, 5);
  assert.equal(data.receipts.length, 2);
  assert.equal(data.receipts[0].total, 112000.5);
  assert.equal(data.receipts[0].paymentMethod, null);
  assert.equal(data.receipts[0].paymentStatus, "unpaid");
  assert.equal(data.receipts[0].paidAt, null);
  await request("/receipts/TIDAK-ADA/payment", "PATCH", { paymentMethod: "cash" }, 404);
  await request("/receipts/" + first.number + "/payment", "PATCH", { paymentMethod: "cash" }, 409);

  await request("/products/" + product.key, "PUT", { ...values, price: 60000, expectedStock: 5 });
  await Promise.all([
    request("/receipts/" + first.number + "/status", "PATCH", { status: "ready" }),
    request("/receipts/" + first.number + "/status", "PATCH", { status: "ready" }),
  ]);
  await request("/receipts/" + first.number + "/status", "PATCH", { status: "delivered" });
  await request("/receipts/" + first.number + "/payment", "PATCH", { paymentMethod: "card" }, 400);
  const payment = await request("/receipts/" + first.number + "/payment", "PATCH", { paymentMethod: "transfer" });
  assert.equal(payment.number, first.number);
  assert.equal(payment.paymentMethod, "transfer");
  assert.equal(payment.paymentStatus, "paid");
  assert.ok(payment.paidAt);
  await request("/receipts/" + first.number + "/payment", "PATCH", { paymentMethod: "transfer" }, 409);
  await request("/products/" + product.key, "PUT", { ...values, expectedStock: 5 }, 409);
  await request("/receipts", "POST", { ...draft, clientId: randomUUID(), status: "ready" }, 409);
  await request("/receipts", "POST", {
    ...draft, clientId: randomUUID(), status: "ready", items: [{ key: product.key, quantity: 4, price: 60000 }],
  }, 409);
  data = await request();
  assert.equal(data.items[0].stock, 3);
  assert.equal(data.receipts[0].lines[0].price, values.price);
  assert.equal(data.receipts[0].pending, false);
  assert.equal(data.receipts[0].status, "delivered");
  assert.equal(data.receipts[0].paymentMethod, "transfer");
  assert.equal(data.receipts[0].paymentStatus, "paid");
  assert.ok(data.receipts[0].paidAt);
  assert.ok(data.lastSync);
  assert.equal((await pool.query("SELECT COUNT(*)::int AS count FROM stock_movements WHERE movement_type='sale'")).rows[0].count, 1);

  await request("/products/" + product.key, "DELETE");
  await request("/receipts", "POST", { ...draft, clientId: randomUUID() }, 409);
  const backup = await request("/backup", "POST");
  assert.equal(backup.version, 2);
  assert.ok(backup.lastBackup);
  await request("/restore", "POST", backup, 409);

  // Reset fixtures only after proving this pool is using the schema created above.
  await pool.query(`TRUNCATE "${schema}".sync_records, "${schema}".stock_movements, "${schema}".transaction_items,
    "${schema}".transactions, "${schema}".products, "${schema}".customers RESTART IDENTITY`);
  const invalid = { ...backup, receipts: [{ ...backup.receipts[0], total: 0 }] };
  await request("/restore", "POST", invalid, 400);
  assert.equal((await request()).items.length, 0);
  const historicalBackup = structuredClone(backup);
  delete historicalBackup.receipts[0].paidAt;
  const restored = await request("/restore", "POST", historicalBackup);
  assert.equal(restored.items[0].stock, 3);
  assert.equal(restored.items[0].archived, true);
  assert.equal(restored.receipts[0].total, 112000.5);
  assert.equal(restored.receipts[0].number, first.number);
  assert.equal(restored.receipts[0].customer.id, restored.customers[0].id);
  assert.equal(restored.receipts[0].paymentStatus, "paid");
  assert.equal(restored.receipts[0].paymentMethod, "transfer");
  assert.equal(restored.receipts[0].paidAt, null);
  console.log("OK: migration pembayaran, pelanggan, produk, stok atomik, nota idempoten, pembayaran, dan backup/pemulihan.");
} finally {
  if (server) await new Promise((resolve) => server.close(resolve));
  if (pool) await pool.end();
  if (schemaCreated) await admin.query(`DROP SCHEMA "${schema}" CASCADE`);
  await admin.end();
}
