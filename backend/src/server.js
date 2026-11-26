
import "dotenv/config";
import express from "express";
import cors from "cors";
import { pool } from "./config/database.js";
import productRoutes from "./routes/products.routes.js";
import dashboardRoutes from "./routes/dashboard.routes.js";

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:5173",
}));

app.use("/api/dashboard/restore", express.json({ limit: "10mb" }));
app.use("/api/dashboard", express.json(), dashboardRoutes);
app.use(express.json());
app.use("/api/products", productRoutes);

// Cek backend
app.get("/api/health", (req, res) => {
  res.json({
    success: true,
    message: "Toko Indo Telur API berjalan",
  });
});

// Cek koneksi database
app.get("/api/db-check", async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT
        current_database() AS database,
        NOW() AS server_time
    `);

    res.status(200).json({
      success: true,
      message: "PostgreSQL berhasil terhubung!",
      data: result.rows[0],
    });
  } catch (error) {
    console.error("Database connection error:", error.message);

    res.status(500).json({
      success: false,
      message: "Gagal terhubung ke database",
    });
  }
});

app.use((error, req, res, next) => {
  if (res.headersSent) {
    return next(error);
  }

  if (error.code === "23505") {
    return res.status(409).json({
      success: false,
      message: "SKU produk sudah digunakan",
    });
  }

  if (error.code === "23503" || error.code === "23001") {
    return res.status(409).json({
      success: false,
      message: "Produk tidak dapat dihapus karena masih memiliki riwayat transaksi atau stok",
    });
  }

  console.error("API error:", error.message);
  return res.status(500).json({
    success: false,
    message: "Terjadi kesalahan pada server",
  });
});

export { app };

if (/[\\/]src[\\/]server\.js$/.test(process.argv[1] ?? "")) {
  app.listen(PORT, () => {
    console.log(`Server berjalan di http://localhost:${PORT}`);
  });
}
