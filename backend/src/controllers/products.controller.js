import { pool } from "../config/database.js";

const productColumns = `
  id,
  sku,
  name,
  description,
  price,
  stock,
  unit,
  is_active,
  created_at,
  updated_at
`;

const mutableFields = new Set([
  "sku",
  "name",
  "description",
  "price",
  "unit",
  "is_active",
]);

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function isValidId(value) {
  return /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) > 0;
}

function normalizeOptionalText(value, fieldName, maxLength, errors) {
  if (value === null) {
    return null;
  }

  if (typeof value !== "string") {
    errors.push(`${fieldName} harus berupa teks.`);
    return undefined;
  }

  const normalizedValue = value.trim();
  if (normalizedValue.length === 0) {
    return null;
  }

  if (maxLength && normalizedValue.length > maxLength) {
    errors.push(`${fieldName} maksimal ${maxLength} karakter.`);
    return undefined;
  }

  return normalizedValue;
}

function normalizeRequiredText(value, fieldName, maxLength, errors) {
  if (typeof value !== "string") {
    errors.push(`${fieldName} wajib berupa teks.`);
    return undefined;
  }

  const normalizedValue = value.trim();
  if (normalizedValue.length === 0) {
    errors.push(`${fieldName} tidak boleh kosong.`);
    return undefined;
  }

  if (maxLength && normalizedValue.length > maxLength) {
    errors.push(`${fieldName} maksimal ${maxLength} karakter.`);
    return undefined;
  }

  return normalizedValue;
}

function normalizePrice(value, errors) {
  const normalizedValue = typeof value === "number"
    ? String(value)
    : typeof value === "string"
      ? value.trim()
      : undefined;

  if (typeof normalizedValue !== "string" || !/^\d{1,12}(?:\.\d{1,2})?$/.test(normalizedValue)) {
    errors.push("Harga harus berupa angka non-negatif dengan maksimal dua angka desimal.");
    return undefined;
  }

  return normalizedValue;
}

function validateProductPayload(body, { isCreate }) {
  const errors = [];
  const data = {};

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { errors: ["Body request harus berupa objek JSON."] };
  }

  for (const fieldName of Object.keys(body)) {
    if (!mutableFields.has(fieldName) && fieldName !== "stock") {
      errors.push(`Field ${fieldName} tidak didukung.`);
    }
  }

  if (hasOwn(body, "stock")) {
    errors.push("Stok tidak dapat diubah melalui Product API. Gunakan stock_movements.");
  }

  if (isCreate && !hasOwn(body, "name")) {
    errors.push("Nama produk wajib diisi.");
  }
  if (isCreate && !hasOwn(body, "price")) {
    errors.push("Harga produk wajib diisi.");
  }

  if (hasOwn(body, "name")) {
    data.name = normalizeRequiredText(body.name, "Nama produk", null, errors);
  }
  if (hasOwn(body, "sku")) {
    data.sku = normalizeOptionalText(body.sku, "SKU", 64, errors);
  }
  if (hasOwn(body, "description")) {
    if (body.description !== null && typeof body.description !== "string") {
      errors.push("Deskripsi harus berupa teks atau null.");
    } else {
      data.description = body.description === null ? null : body.description.trim();
    }
  }
  if (hasOwn(body, "price")) {
    data.price = normalizePrice(body.price, errors);
  }
  if (hasOwn(body, "unit")) {
    data.unit = normalizeRequiredText(body.unit, "Satuan", 32, errors);
  }
  if (hasOwn(body, "is_active")) {
    if (typeof body.is_active !== "boolean") {
      errors.push("is_active harus bernilai boolean.");
    } else {
      data.is_active = body.is_active;
    }
  }

  if (!isCreate && Object.keys(data).length === 0 && errors.length === 0) {
    errors.push("Sediakan minimal satu field produk untuk diperbarui.");
  }

  return { data, errors };
}

function sendValidationError(res, errors) {
  return res.status(400).json({
    success: false,
    message: errors[0],
  });
}

export async function getProducts(req, res, next) {
  try {
    const result = await pool.query(`
      SELECT ${productColumns}
      FROM products
      ORDER BY name ASC, id ASC
    `);

    return res.status(200).json({
      success: true,
      message: "Daftar produk berhasil diambil",
      data: result.rows,
    });
  } catch (error) {
    return next(error);
  }
}

export async function getProductById(req, res, next) {
  const { id } = req.params;
  if (!isValidId(id)) {
    return res.status(400).json({
      success: false,
      message: "ID produk tidak valid",
    });
  }

  try {
    const result = await pool.query(
      `SELECT ${productColumns} FROM products WHERE id = $1`,
      [id],
    );

    if (result.rowCount === 0) {
      return res.status(404).json({
        success: false,
        message: "Produk tidak ditemukan",
      });
    }

    return res.status(200).json({
      success: true,
      message: "Detail produk berhasil diambil",
      data: result.rows[0],
    });
  } catch (error) {
    return next(error);
  }
}

export async function createProduct(req, res, next) {
  const { data, errors } = validateProductPayload(req.body, { isCreate: true });
  if (errors.length > 0) {
    return sendValidationError(res, errors);
  }

  try {
    const result = await pool.query(
      `INSERT INTO products (sku, name, description, price, unit, is_active)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING ${productColumns}`,
      [
        data.sku ?? null,
        data.name,
        data.description ?? null,
        data.price,
        data.unit ?? "pcs",
        data.is_active ?? true,
      ],
    );

    return res.status(201).json({
      success: true,
      message: "Produk berhasil ditambahkan",
      data: result.rows[0],
    });
  } catch (error) {
    return next(error);
  }
}

export async function updateProduct(req, res, next) {
  const { id } = req.params;
  if (!isValidId(id)) {
    return res.status(400).json({
      success: false,
      message: "ID produk tidak valid",
    });
  }

  const { data, errors } = validateProductPayload(req.body, { isCreate: false });
  if (errors.length > 0) {
    return sendValidationError(res, errors);
  }

  const fields = Object.keys(data);
  const assignments = fields.map((fieldName, index) => `${fieldName} = $${index + 1}`);
  const values = fields.map((fieldName) => data[fieldName]);
  values.push(id);

  try {
    const result = await pool.query(
      `UPDATE products
       SET ${assignments.join(", ")}
       WHERE id = $${values.length}
       RETURNING ${productColumns}`,
      values,
    );

    if (result.rowCount === 0) {
      return res.status(404).json({
        success: false,
        message: "Produk tidak ditemukan",
      });
    }

    return res.status(200).json({
      success: true,
      message: "Produk berhasil diperbarui",
      data: result.rows[0],
    });
  } catch (error) {
    return next(error);
  }
}

export async function deleteProduct(req, res, next) {
  const { id } = req.params;
  if (!isValidId(id)) {
    return res.status(400).json({
      success: false,
      message: "ID produk tidak valid",
    });
  }

  try {
    const result = await pool.query(
      `DELETE FROM products
       WHERE id = $1
       RETURNING ${productColumns}`,
      [id],
    );

    if (result.rowCount === 0) {
      return res.status(404).json({
        success: false,
        message: "Produk tidak ditemukan",
      });
    }

    return res.status(200).json({
      success: true,
      message: "Produk berhasil dihapus",
      data: result.rows[0],
    });
  } catch (error) {
    return next(error);
  }
}
