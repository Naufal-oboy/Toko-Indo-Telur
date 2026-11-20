import "dotenv/config";
import { randomUUID } from "node:crypto";
import { pool } from "../src/config/database.js";

const expectedTables = [
  "products",
  "transactions",
  "transaction_items",
  "stock_movements",
  "sync_records",
];

async function expectFailure(client, label, query, expectedCode) {
  await client.query("SAVEPOINT expected_failure");

  try {
    await client.query(query);
  } catch (error) {
    await client.query("ROLLBACK TO SAVEPOINT expected_failure");

    if (error.code !== expectedCode) {
      throw new Error(
        `${label} gagal dengan kode ${error.code ?? "tidak diketahui"}; diharapkan ${expectedCode}.`,
      );
    }

    console.log(`OK: ${label} ditolak (${error.code}).`);
    return;
  }

  await client.query("RELEASE SAVEPOINT expected_failure");
  throw new Error(`${label} seharusnya ditolak database.`);
}

async function verifyDatabase() {
  const client = await pool.connect();

  try {
    const database = await client.query(`
      SELECT current_database() AS database, current_user AS database_user
    `);
    console.log(`Terhubung ke database ${database.rows[0].database} sebagai ${database.rows[0].database_user}.`);

    const tables = await client.query(
      `SELECT table_name
       FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = ANY($1::text[])
       ORDER BY table_name`,
      [expectedTables],
    );
    const foundTables = new Set(tables.rows.map((row) => row.table_name));
    const missingTables = expectedTables.filter((table) => !foundTables.has(table));

    if (missingTables.length > 0) {
      throw new Error(`Tabel belum tersedia: ${missingTables.join(", ")}.`);
    }

    console.log(`OK: lima tabel aplikasi tersedia (${expectedTables.join(", ")}).`);

    const foreignKeys = await client.query(`
      SELECT tc.table_name, kcu.column_name, ccu.table_name AS references_table
      FROM information_schema.table_constraints AS tc
      JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
      JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
      WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
        AND tc.table_name = ANY($1::text[])
      ORDER BY tc.table_name, kcu.column_name
    `, [expectedTables]);

    console.log(`OK: ${foreignKeys.rowCount} foreign key terdeteksi.`);

    await client.query("BEGIN");
    try {
      await expectFailure(
        client,
        "harga produk negatif",
        "INSERT INTO products (name, price) VALUES ('Produk harga negatif', -1)",
        "23514",
      );
      await expectFailure(
        client,
        "stok produk negatif",
        "INSERT INTO products (name, price, stock) VALUES ('Produk stok negatif', 1, -1)",
        "P0001",
      );

      const product = await client.query(
        "INSERT INTO products (name, price) VALUES ('Produk uji sementara', 10000) RETURNING id",
      );
      const transaction = await client.query(
        `INSERT INTO transactions (client_transaction_id, invoice_number)
         VALUES ($1, $2)
         RETURNING id`,
        [randomUUID(), `TEST-${randomUUID()}`],
      );

      await expectFailure(
        client,
        "kuantitas item nol",
        `INSERT INTO transaction_items (
          transaction_id, product_id, product_name_snapshot, unit_snapshot, quantity, unit_price
        ) VALUES (${transaction.rows[0].id}, ${product.rows[0].id}, 'Produk uji sementara', 'pcs', 0, 10000)`,
        "23514",
      );

      const movement = await client.query(
        `INSERT INTO stock_movements (product_id, movement_type, quantity_change, notes)
         VALUES ($1, 'restock', 10, 'uji rollback')
         RETURNING stock_before, stock_after`,
        [product.rows[0].id],
      );
      if (movement.rows[0].stock_before !== "0.000" || movement.rows[0].stock_after !== "10.000") {
        throw new Error("Trigger pergerakan stok tidak menghitung stok dengan benar.");
      }
      console.log("OK: restock memperbarui stok melalui stock_movements.");

      await expectFailure(
        client,
        "penjualan yang membuat stok negatif",
        `INSERT INTO stock_movements (product_id, transaction_id, movement_type, quantity_change)
         VALUES (${product.rows[0].id}, ${transaction.rows[0].id}, 'sale', -11)`,
        "P0001",
      );

      await client.query("ROLLBACK");
      console.log("OK: seluruh data uji di-rollback.");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    }
  } finally {
    client.release();
    await pool.end();
  }
}

verifyDatabase().catch((error) => {
  console.error("Verifikasi database gagal:", error.message);
  process.exitCode = 1;
});
