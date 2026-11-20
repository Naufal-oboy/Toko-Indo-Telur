import "dotenv/config";
import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { pool } from "../src/config/database.js";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const migrationsDirectory = path.join(
  currentDirectory,
  "../src/database/migrations",
);
const migrationLockId = 26012026;

async function getMigrationFiles() {
  const entries = await readdir(migrationsDirectory, { withFileTypes: true });

  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".sql"))
    .map((entry) => entry.name)
    .sort();
}

async function runMigrations() {
  const client = await pool.connect();
  let hasLock = false;

  try {
    await client.query("SELECT pg_advisory_lock($1)", [migrationLockId]);
    hasLock = true;

    await client.query(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        filename TEXT PRIMARY KEY,
        checksum TEXT NOT NULL,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    const files = await getMigrationFiles();

    for (const filename of files) {
      const sql = await readFile(path.join(migrationsDirectory, filename), "utf8");
      const checksum = createHash("sha256").update(sql).digest("hex");
      const existing = await client.query(
        "SELECT checksum FROM schema_migrations WHERE filename = $1",
        [filename],
      );

      if (existing.rowCount > 0) {
        if (existing.rows[0].checksum !== checksum) {
          throw new Error(
            `Migration ${filename} sudah tercatat tetapi isi filenya berubah. Buat migration baru, jangan ubah migration yang telah dijalankan.`,
          );
        }

        console.log(`Lewati ${filename} (sudah diterapkan).`);
        continue;
      }

      console.log(`Terapkan ${filename}...`);
      await client.query("BEGIN");

      try {
        await client.query(sql);
        await client.query(
          "INSERT INTO schema_migrations (filename, checksum) VALUES ($1, $2)",
          [filename, checksum],
        );
        await client.query("COMMIT");
        console.log(`Selesai ${filename}.`);
      } catch (error) {
        await client.query("ROLLBACK");
        throw error;
      }
    }
  } finally {
    if (hasLock) {
      await client.query("SELECT pg_advisory_unlock($1)", [migrationLockId]);
    }

    client.release();
    await pool.end();
  }
}

runMigrations().catch((error) => {
  console.error("Migration gagal:", error.message);
  process.exitCode = 1;
});
