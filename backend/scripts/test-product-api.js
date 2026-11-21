import "dotenv/config";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { pool } from "../src/config/database.js";

const { app } = await import("../src/server.js");
const server = await new Promise((resolve) => {
  const instance = app.listen(0, "127.0.0.1", () => resolve(instance));
});
const address = server.address();
const baseUrl = `http://127.0.0.1:${address.port}`;
const testSuffix = `${Date.now()}-${randomUUID().slice(0, 8)}`;
const createdProductIds = [];
let relatedTransactionId;

async function request(method, path, body) {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  return {
    status: response.status,
    body: await response.json(),
  };
}

function expectStatus(response, expectedStatus, label) {
  assert.equal(response.status, expectedStatus, `${label}: status tidak sesuai`);
  assert.equal(response.body.success, expectedStatus < 400, `${label}: format success tidak sesuai`);
  console.log(`OK: ${label} (${expectedStatus}).`);
}

async function cleanup() {
  if (relatedTransactionId) {
    await pool.query("DELETE FROM transaction_items WHERE transaction_id = $1", [relatedTransactionId]);
    await pool.query("DELETE FROM transactions WHERE id = $1", [relatedTransactionId]);
  }

  for (const productId of createdProductIds) {
    await pool.query("DELETE FROM products WHERE id = $1", [productId]);
  }
}

try {
  expectStatus(await request("GET", "/api/health"), 200, "health check");
  expectStatus(await request("GET", "/api/db-check"), 200, "database check");

  const listResponse = await request("GET", "/api/products");
  expectStatus(listResponse, 200, "mengambil daftar produk");
  assert.ok(Array.isArray(listResponse.body.data), "Daftar produk harus berupa array.");

  const productPayload = {
    sku: `TEST-SKU-${testSuffix}`,
    name: `Produk API ${testSuffix}`,
    description: "Produk sementara untuk integration test.",
    price: "12500.50",
    unit: "pcs",
  };
  const createResponse = await request("POST", "/api/products", productPayload);
  expectStatus(createResponse, 201, "menambahkan produk valid");
  const productId = createResponse.body.data.id;
  createdProductIds.push(productId);
  assert.equal(Number(createResponse.body.data.stock), 0, "Produk baru harus memiliki stok 0.");

  expectStatus(await request("GET", `/api/products/${productId}`), 200, "mengambil produk berdasarkan ID");
  expectStatus(await request("GET", "/api/products/999999999999"), 404, "produk tidak ditemukan");
  expectStatus(await request("GET", "/api/products/bukan-id"), 400, "validasi ID produk");

  expectStatus(
    await request("POST", "/api/products", { name: "Harga negatif", price: "-1" }),
    400,
    "menolak harga negatif",
  );
  expectStatus(
    await request("POST", "/api/products", { ...productPayload, name: "SKU duplikat" }),
    409,
    "menolak SKU duplikat",
  );

  const updateResponse = await request("PUT", `/api/products/${productId}`, {
    name: `Produk API diperbarui ${testSuffix}`,
    price: "13500",
    unit: "kg",
  });
  expectStatus(updateResponse, 200, "memperbarui produk");
  assert.equal(updateResponse.body.data.name, `Produk API diperbarui ${testSuffix}`);
  assert.equal(updateResponse.body.data.unit, "kg");

  expectStatus(
    await request("PUT", `/api/products/${productId}`, { stock: 20 }),
    400,
    "menolak perubahan stok langsung",
  );
  expectStatus(await request("DELETE", `/api/products/${productId}`), 200, "menghapus produk tanpa relasi");
  createdProductIds.splice(createdProductIds.indexOf(productId), 1);

  const relatedResponse = await request("POST", "/api/products", {
    sku: `RELATED-SKU-${testSuffix}`,
    name: `Produk berelasi ${testSuffix}`,
    price: "5000",
  });
  expectStatus(relatedResponse, 201, "menambahkan produk untuk uji relasi");
  const relatedProductId = relatedResponse.body.data.id;
  createdProductIds.push(relatedProductId);

  const transaction = await pool.query(
    `INSERT INTO transactions (client_transaction_id, invoice_number)
     VALUES ($1, $2)
     RETURNING id`,
    [randomUUID(), `TEST-INVOICE-${testSuffix}`],
  );
  relatedTransactionId = transaction.rows[0].id;
  await pool.query(
    `INSERT INTO transaction_items (
      transaction_id, product_id, product_name_snapshot, unit_snapshot, quantity, unit_price
    ) VALUES ($1, $2, $3, 'pcs', 1, 5000)`,
    [relatedTransactionId, relatedProductId, `Produk berelasi ${testSuffix}`],
  );

  expectStatus(
    await request("DELETE", `/api/products/${relatedProductId}`),
    409,
    "menolak penghapusan produk yang berelasi",
  );
} finally {
  try {
    await cleanup();
  } finally {
    await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
    await pool.end();
  }
}

console.log("Semua pengujian Product API berhasil.");
