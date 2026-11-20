
import "dotenv/config";
import express from "express";
import cors from "cors";
import { pool } from "./config/database.js";

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:5173",
}));

app.use(express.json());

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

app.listen(PORT, () => {
  console.log(`Server berjalan di http://localhost:${PORT}`);
});
