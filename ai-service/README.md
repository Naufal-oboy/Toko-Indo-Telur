# Toko Indo Telur — AI Service (`ai-service/`)

Layanan AI berbasis **FastAPI** untuk proyek capstone **Asah 2026 (Tim A26-CS201 — Toko Indo Telur)** yang menangani klasifikasi maksud pesan pelanggan WhatsApp (*intent classification*), pencocokan katalog produk aktif secara *read-only*, serta penyusunan saran balasan generatif berbasis **Google Gemini API** dengan *factuality guard* dan *fallback* aturan sederhana.

> **Batasan MVP:** Layanan ini dibangun untuk **demonstrasi dan validasi kebutuhan MVP** (bukan klaim siap produksi ataupun klaim capaian penjualan nyata UMKM). Seluruh akses ke data produk bersifat ***read-only*** (`BR-08`) sehingga chatbot tidak pernah mengubah stok maupun transaksi.

---

## 1. Masalah Bisnis & Tujuan Klasifikasi Maksud Pesan

**Toko Indo Telur** (grosir sembako di Bontang) menerima pesanan dari warung dan pelanggan melalui WhatsApp sementara pencatatan dilakukan manual oleh satu orang. Saat pesan masuk meningkat, balasan awal untuk pertanyaan berulang (sapaan, cara pesan, cek stok, dan cek harga) sering tertunda.

Tujuan layanan AI ini adalah menyediakan respons awal yang cepat, sopan, dan terarah dengan mengklasifikasikan setiap pesan pelanggan ke dalam **5 kelas intent**:

| Kelas Intent | Deskripsi | Contoh Pesan |
| --- | --- | --- |
| `sapaan` | Sapaan pembuka percakapan | `"halo"`, `"selamat pagi bu"`, `"assalamualaikum"` |
| `format_pesanan` | Niat memesan atau menanyakan cara/format order | `"mau pesan"`, `"cara order gimana?"`, `"bisa pesan telur 2 rak?"` |
| `cek_stok` | Pertanyaan ketersediaan barang | `"stok telur ada?"`, `"stok telor ready ga?"` |
| `cek_harga` | Pertanyaan harga barang | `"harga gula berapa?"`, `"harga gulaa brp?"` |
| `lainnya` | Pesan di luar cakupan bot (komplain, pembayaran khusus, jadwal antar, atau teks acak) | `"komplain barang kemarin pecah"`, `"asdfghjkl 12345"` |

---

## 2. Sumber Dataset, Batasan Penggunaan & Cara Retrain (`DS-04`)

### Sumber & Hak Penggunaan Data (`BR-09` & `NFR-05`)
- **`data/intent_dataset_dummy.csv`**: Dataset **dummy sintetis** berisi **202 baris mentah** (menjadi **200 baris unik** setelah normalisasi & deduplikasi, seimbang **40 sampel per kelas** untuk 5 kelas intent), mencakup variasi bahasa percakapan grosir sembako Indonesia dan salah ketik (*typo*) seperti `telor`, `gulaa`, `brp`, `migor`, dan `ready`.
- **`data/sample_products.json`**: Katalog contoh **11 produk sembako** berformat identik dengan respons Express `GET /api/products` (`id`, `sku`, `name`, `description`, `price`, `stock`, `unit`, `is_active`), termasuk produk stok menipis (`<= 5`), stok habis (`0.000`), dan 1 produk nonaktif (`is_active: false`) untuk pengujian filter.
- **Privasi & batasan:** Dataset **tidak memuat PII**, tidak menggunakan nomor telepon, nama pelanggan nyata, ataupun isi chat asli UMKM. Hasil evaluasi pada data dummy **tidak diklaim** mewakili performa produksi maupun metrik bisnis aktual UMKM.

### Skema CSV Dataset
File dataset pelatihan wajib berformat CSV UTF-8 dengan dua kolom:
```csv
text,intent
stok telor ada?,cek_stok
harga gulaa brp?,cek_harga
```

### Cara Melatih Ulang Saat Dataset Final DS (`DS-04`) Tersedia
Begitu dataset final dari tim Data Science (`DS-04`) diterima, latih dan evaluasi ulang seluruh kandidat model tanpa mengubah kode melalui argumen `--dataset`:
```bash
python src/train_evaluate.py \
  --dataset path/ke/dataset_final_ds04.csv \
  --output-model artifacts/intent_model.joblib \
  --output-report artifacts/evaluation_report.json
```

---

## 3. Langkah Preprocessing Teks & Normalisasi Typo

Seluruh teks pesan pelanggan (saat pelatihan maupun inferensi) diproses secara identik oleh `normalize_text()` pada `src/preprocessing.py`:

1. **Casefolding**: Mengubah seluruh teks menjadi huruf kecil (*lowercase*).
2. **Pembersihan karakter non-alfanumerik**: Menghapus tanda baca dan simbol berisik (`?`, `!`, `.`, `,`, dll.) sambil mempertahankan huruf, angka, dan spasi.
3. **Pemangkasan huruf berulang ($\ge 3$ kali)**: Mengubah pengulangan huruf berlebihan menjadi satu karakter (contoh: `gulaaaa` $\rightarrow$ `gula`, `haloooo` $\rightarrow$ `halo`).
4. **Normalisasi kamus slang & typo (`TYPO_MAP`) + vokal ganda akhir**: Memetakan singkatan dan salah ketik umum chat grosir sembako Indonesia (contoh: `telor` $\rightarrow$ `telur`, `gulaa` $\rightarrow$ `gula`, `brp`/`brpa`/`brapa` $\rightarrow$ `berapa`, `hrg`/`hrga` $\rightarrow$ `harga`, `ready`/`redi`/`redy` $\rightarrow$ `ada`, `migor` $\rightarrow$ `minyak goreng`, `trigu` $\rightarrow$ `terigu`, `psn`/`pesen`/`order` $\rightarrow$ `pesan`, `ga`/`gak`/`gk`/`tdk` $\rightarrow$ `tidak`), serta memangkas vokal ganda di akhir kata yang tidak masuk kamus langsung.
5. **Normalisasi spasi**: Menggabungkan spasi ganda dan menghapus spasi di awal/akhir teks.

Untuk pencarian produk (`src/product_matcher.py`), kueri yang sudah dinormalisasi dibersihkan dari *stopword* tanya/sapaan, difilter ketat hanya pada produk aktif (`is_active == True`), lalu dicocokkan dengan **RapidFuzz** (*token-to-token alignment* & skor *tie-breaker* ukuran kemasan) sehingga mampu membedakan status `matched`, `missing_product_name` (mis. `"stok ada?"`), dan `not_found` (mis. `"stok emas batangan ada?"`).

---

## 4. Model yang Dilatih & Pembagian Train/Test Bebas *Data Leakage*

Skrip `src/train_evaluate.py` melatih dan membandingkan **3 kandidat pipeline `scikit-learn`** pada pembagian data dan metrik yang identik:

- **Pencegahan *data leakage*:** Teks dinormalisasi dan dideduplikasi **sebelum** dilakukan pemisahan data (`202` baris mentah $\rightarrow$ `200` baris unik). Skrip melakukan asersi eksplisit bahwa irisan `set(x_train).intersection(set(x_test))` wajib kosong.
- **Pembagian data:** Stratified split **80/20** (`train_size = 160`, `test_size = 40`, `random_state = 42`, masing-masing **8 sampel uji per kelas**). Seluruh *vectorizer* TF-IDF hanya di-`fit` pada `x_train`.

| ID Model | Konfigurasi Pipeline | Karakteristik |
| --- | --- | --- |
| `tfidf_logreg` | `FeatureUnion(TF-IDF word 1-2 + char_wb 3-5, sublinear_tf=True)` + `LogisticRegression(max_iter=1000, random_state=42)` | Probabilitas terkalibrasi, cepat, tahan typo via *char n-gram*. |
| `tfidf_linear_svc` | `FeatureUnion(TF-IDF word 1-2 + char_wb 3-5, sublinear_tf=True)` + `CalibratedClassifierCV(LinearSVC(random_state=42), cv=3)` | Margin pemisah kuat untuk teks chat pendek + probabilitas terkalibrasi via `predict_proba`. |
| `tfidf_multinomial_nb` | `TfidfVectorizer(word 1-2, sublinear_tf=True)` + `MultinomialNB()` | Baseline probabilistik klasik yang ringan dan sangat cepat. |

Model terbaik disimpan ke `artifacts/intent_model.joblib` (terpisah dari fungsi kustom sehingga aman di-load dengan `joblib.load`) dan laporan lengkap disimpan ke `artifacts/evaluation_report.json`.

---

## 5. Penyedia API Generatif Proprietary, Guardrails & Fallback

- **Penyedia & SDK:** **Google Gemini API** melalui SDK resmi **`google-genai`** (model default: `gemini-3.5-flash-lite`). Klien diinisialisasi secara *lazy* di sisi server (`src/generative_service.py`), dengan `GEMINI_API_KEY` hanya dibaca dari variabel lingkungan / `.env` dan tidak pernah disimpan di repositori ataupun diekspos ke klien (`NFR-04`).
- **Batasan & Pengendalian Operasional (`Risiko #6`):**
  - **Timeout terkontrol:** `GEMINI_TIMEOUT_SECONDS` (default `15` detik).
  - **Batas pemakaian (*rate cap*):** `SlidingWindowRateLimiter` lokal sebesar `GEMINI_MAX_CALLS_PER_MINUTE` (default `30` panggilan/menit).
  - **Minimisasi data (tanpa PII):** Prompt ke Gemini hanya memuat isi pesan, intent terdeteksi, dan metadata produk terverifikasi server (tanpa nomor HP/identitas pelanggan).
  - **Logging & simulasi kegagalan:** Setiap kegagalan (timeout, error API, rate limit, pelanggaran guard) dicatat di log server, dan flag request `simulate_failure=true` disediakan untuk menguji jalur *fallback* (`TC-10`).
- **Pemeriksaan Pasca-Generasi (*Factuality Guard* — `validate_generated_reply`):**
  Sebelum jawaban Gemini dikirim ke pengguna, guard memverifikasi:
  1. Panjang teks wajar (`10–1500` karakter).
  2. Tidak ada klaim mutasi stok atau pembayaran selesai (mis. *"stok sudah dikurangi"*, `BR-08`).
  3. Untuk `cek_harga` yang cocok: wajib memuat angka harga Rupiah **persis** sama dengan data server dan dilarang menambahkan angka harga Rp lain yang bertentangan.
  4. Untuk `cek_stok` / `cek_harga` yang cocok: wajib memuat status stok deterministik (`tersedia` / `menipis` / `habis`) serta kata **`perkiraan`**.
  5. Untuk produk `not_found`: dilarang mengarang nominal harga `Rp` apa pun.
  6. Jika `auto_reply_stock_enabled=false` pada `cek_stok`: dilarang membocorkan status stok.
- **Fallback Aturan Sederhana (`build_fallback_reply`):** Jika API key belum diisi, timeout, error jaringan/kuota, rate limit tercapai, `simulate_failure=true`, atau output gagal *factuality guard*, sistem otomatis mengembalikan templat jawaban bahasa Indonesia yang deterministik (`source: "fallback_rule"`, `fallback_used: true`).
- **Mitigasi Stok Offline (`Risiko #3`):**
  - Status stok dihitung deterministik di kode (`<= 0` $\rightarrow$ `habis`, `<= LOW_STOCK_THRESHOLD` [default `5`] $\rightarrow$ `menipis`, `> threshold` $\rightarrow$ `tersedia`) disertai catatan wajib bahwa stok bersifat **perkiraan**.
  - Toggle **`AUTO_REPLY_STOCK_ENABLED`** (via `.env` atau override per request) memungkinkan pemilik menonaktifkan jawaban stok otomatis untuk intent `cek_stok`, sehingga bot membalas sopan bahwa pemilik akan mengecek dan membalas secara manual.

---

## 6. Library & Dependensi (`requirements.txt`)

| Paket | Versi (`requirements.txt`) | Fungsi |
| --- | --- | --- |
| `fastapi` | `>=0.115.0,<1.0.0` | Framework REST API & dokumentasi Swagger `/docs` |
| `uvicorn[standard]` | `>=0.32.0,<1.0.0` | ASGI server untuk menjalankan FastAPI |
| `pydantic` | `>=2.9.0,<3.0.0` | Validasi skema request/response yang ketat |
| `pydantic-settings` | `>=2.6.0,<3.0.0` | Manajemen konfigurasi dari environment / `.env` |
| `python-dotenv` | `>=1.0.1,<2.0.0` | Pembacaan file `.env` pada pengembangan lokal |
| `scikit-learn` | `>=1.5.0,<2.0.0` | TF-IDF, `LogisticRegression`, `LinearSVC`, `MultinomialNB`, evaluasi metrik |
| `joblib` | `>=1.4.0,<2.0.0` | Serialisasi dan pemuatan artefak model terlatih |
| `rapidfuzz` | `>=3.10.0,<4.0.0` | Pencocokan nama produk toleran typo |
| `httpx` | `>=0.27.0,<1.0.0` | Klien HTTP *read-only* (`GET /api/products`) ke backend Express |
| `google-genai` | `>=1.0.0,<2.0.0` | SDK resmi Google Gemini API |
| `pytest` | `>=8.3.0,<9.0.0` | Pengujian otomatis unit, endpoint API, dan skenario chatbot |

---

## 7. Hasil Evaluasi Perbandingan 3 Model

Seluruh angka berikut diambil langsung dari `artifacts/evaluation_report.json` (dataset `data/intent_dataset_dummy.csv`: **202** baris mentah $\rightarrow$ **200** baris unik, split stratified **80/20** dengan **160** sampel latih dan **40** sampel uji identik, `random_state = 42`):

| Model | Konfigurasi Pipeline | Accuracy (Test) | Macro-F1 (Test) | 5-Fold CV Macro-F1 (Train) | Latensi (ms/pesan) | Status |
| --- | --- | :---: | :---: | :---: | :---: | :---: |
| **`tfidf_linear_svc`** | `FeatureUnion(TF-IDF word 1-2 + char_wb 3-5) + CalibratedClassifierCV(LinearSVC, cv=3)` | **0.9250** | **0.9229** | `0.9554 ± 0.0345` | `2.4325` | **Terpilih** |
| `tfidf_logreg` | `FeatureUnion(TF-IDF word 1-2 + char_wb 3-5) + LogisticRegression(max_iter=1000)` | `0.9000` | `0.8961` | `0.9554 ± 0.0345` | `0.9832` | Pembanding |
| `tfidf_multinomial_nb` | `TfidfVectorizer(word 1-2) + MultinomialNB()` | `0.8500` | `0.8290` | `0.8746 ± 0.0173` | `0.4309` | Baseline |

### Ringkasan Metrik Per Kelas — Model Terpilih (`tfidf_linear_svc`, `test_size = 40`)

| Kelas Intent | Precision | Recall | F1-Score | Support |
| --- | :---: | :---: | :---: | :---: |
| `cek_harga` | `1.0000` | `1.0000` | `1.0000` | `8` |
| `cek_stok` | `0.8889` | `1.0000` | `0.9412` | `8` |
| `format_pesanan` | `0.8889` | `1.0000` | `0.9412` | `8` |
| `lainnya` | `0.8750` | `0.8750` | `0.8750` | `8` |
| `sapaan` | `1.0000` | `0.7500` | `0.8571` | `8` |
| **Macro Avg** | **`0.9306`** | **`0.9250`** | **`0.9229`** | **`40`** |

*(Catatan: Metrik di atas berasal dari data dummy sintetis tanpa PII dan bukan klaim akurasi produksi nyata; evaluasi perlu dijalankan ulang saat dataset final `DS-04` tersedia.)*

---

## 8. Alasan Pemilihan Model Terbaik

Model **`tfidf_linear_svc`** dipilih sebagai model aktif berdasarkan kriteria seleksi terukur (**Macro-F1 tertinggi**, dengan *tie-breaker* Accuracy lalu latensi terendah):

1. **Macro-F1 dan Accuracy tertinggi pada test set identik:** `tfidf_linear_svc` meraih Macro-F1 **`0.9229`** dan Accuracy **`0.9250`**, mengungguli `tfidf_logreg` (`0.8961` / `0.9000`) dan `tfidf_multinomial_nb` (`0.8290` / `0.8500`), terutama pada pemisahan kelas `lainnya` (`F1 = 0.8750` vs `0.8000` pada LogReg dan `0.5455` pada MultinomialNB).
2. **Tahan terhadap typo & pesan singkat:** Penggunaan `FeatureUnion` gabungan *word n-gram* `(1, 2)` dan *character n-gram* `char_wb (3, 5)` membantu menangani variasi ejaan dan singkatan pelanggan grosir.
3. **Skor probabilitas siap pakai untuk API:** Pembungkus `CalibratedClassifierCV(LinearSVC, cv=3)` menyediakan `predict_proba` sehingga endpoint `/ai/predict-intent` dapat mengembalikan `confidence` dan distribusi `scores` seluruh kelas secara konsisten.
4. **Latensi sangat rendah:** Rata-rata **`2.4325 ms/pesan`** jauh di bawah ambang respons interaktif chat sehingga tidak menjadi hambatan performa pada layanan REST API. *Confusion matrix* tiap kandidat juga tersimpan lengkap di `artifacts/evaluation_report.json`.

---

## 9. Kontrak Endpoint REST API

Port default: **`8000`** (Swagger interaktif tersedia di `GET /docs`). Seluruh respons sukses maupun error (`400`/`422`/`500`/`503`) mengikuti envelope konsisten dengan backend Express:
```json
{ "success": true, "message": "...", "data": { ... } }
```

### 1) `GET /ai/health`
Memeriksa kesehatan layanan, status pemuatan model, dan konfigurasi non-rahasia (tanpa membocorkan API key).
```bash
curl http://localhost:8000/ai/health
```
Contoh respons (`200 OK`):
```json
{
  "success": true,
  "message": "Toko Indo Telur AI Service berjalan",
  "data": {
    "status": "ok",
    "service": "toko-indo-telur-ai-service",
    "model_loaded": true,
    "model_name": "tfidf_linear_svc",
    "gemini_configured": false,
    "gemini_model": "gemini-3.5-flash-lite",
    "auto_reply_stock_enabled": true,
    "low_stock_threshold": 5.0,
    "backend_configured": true,
    "api_key_auth_enabled": false
  }
}
```

### 2) `POST /ai/predict-intent`
Mengklasifikasikan intent pesan pelanggan dan mengembalikan teks ternormalisasi beserta probabilitas tiap kelas.
```bash
curl -X POST http://localhost:8000/ai/predict-intent \
  -H "Content-Type: application/json" \
  -d '{"message": "stok telor ada?"}'
```
Contoh respons (`200 OK`):
```json
{
  "success": true,
  "message": "Prediksi intent berhasil",
  "data": {
    "original_message": "stok telor ada?",
    "normalized_message": "stok telur ada",
    "intent": "cek_stok",
    "confidence": 0.9611,
    "scores": {
      "cek_stok": 0.9611,
      "format_pesanan": 0.0196,
      "sapaan": 0.0114,
      "cek_harga": 0.0045,
      "lainnya": 0.0034
    }
  }
}
```
Contoh respons input tidak valid (`422 Unprocessable Entity` untuk pesan kosong/non-string):
```json
{
  "success": false,
  "message": "message: Pesan tidak boleh kosong atau hanya spasi.",
  "data": null
}
```

### 3) `POST /ai/suggest-reply`
Menghasilkan saran balasan berbasis Gemini dengan *factuality guard*, atau jatuh ke *fallback* aturan sederhana (`simulate_failure=true` dapat dipakai untuk menguji *fallback*).
```bash
curl -X POST http://localhost:8000/ai/suggest-reply \
  -H "Content-Type: application/json" \
  -d '{
    "message": "harga gulaa berapa?",
    "intent": "cek_harga",
    "products": [
      {
        "id": 2,
        "sku": "GUL-1KG",
        "name": "Gula Pasir 1 kg",
        "price": "17500.00",
        "stock": "40.000",
        "unit": "kg",
        "is_active": true
      }
    ],
    "use_generative": true,
    "auto_reply_stock_enabled": true,
    "simulate_failure": false
  }'
```

### 4) `POST /ai/chatbot/respond`
Alur penuh simulator / siap-webhook WhatsApp (`predict-intent` $\rightarrow$ ambil produk dari payload / *read-only* `GET /api/products` backend / katalog sampel demo $\rightarrow$ `suggest-reply`).
```bash
curl -X POST http://localhost:8000/ai/chatbot/respond \
  -H "Content-Type: application/json" \
  -d '{
    "message": "stok telor ada?",
    "sender_id": "test-user-01",
    "channel": "simulator",
    "use_generative": true,
    "auto_reply_stock_enabled": true,
    "simulate_failure": false
  }'
```

---

## 10. Cara Menjalankan Lokal

Pastikan Python **3.11+** (dikembangkan pada Python **3.13**) tersedia, lalu jalankan dari folder `ai-service/`:

```bash
cd ai-service

# 1. Buat dan aktifkan virtual environment
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# 2. Instal dependensi
pip install -r requirements.txt

# 3. Salin template konfigurasi (isi GEMINI_API_KEY secara lokal; jangan commit .env)
cp .env.example .env

# 4. (Opsional) Latih ulang model & perbarui artefak evaluasi
python src/train_evaluate.py

# 5. Jalankan REST API FastAPI (port default 8000)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Jalankan seluruh suite pengujian otomatis (TC-07 s.d. TC-10)
pytest -v
```

---

## 11. Cara Deploy Online (`Dockerfile` / Render / Railway)

Folder `ai-service/` sudah menyertakan `Dockerfile` berbasis `python:3.13-slim` yang otomatis membaca variabel `PORT` dari platform cloud (`uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}`).

### Opsi A — Docker Lokal / Container Registry
```bash
cd ai-service
docker build -t toko-indo-telur-ai-service .
docker run --rm -p 8000:8000 --env-file .env toko-indo-telur-ai-service
```

### Opsi B — Render / Railway (Web Service)
1. Hubungkan repositori GitHub dan atur **Root Directory** ke `ai-service`.
2. Pilih runtime **Docker** (otomatis memakai `ai-service/Dockerfile`) atau **Python** dengan:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
3. Atur **Environment Variables** pada dashboard (jangan pernah commit key ke Git):
   - `BACKEND_BASE_URL` (URL publik backend Express, mis. `https://<backend-domain>`)
   - `GEMINI_API_KEY` (opsional; jika kosong layanan tetap aman berjalan memakai *fallback* aturan sederhana)
   - `GEMINI_MODEL=gemini-3.5-flash-lite`
   - `GEMINI_TIMEOUT_SECONDS=15`
   - `GEMINI_MAX_CALLS_PER_MINUTE=30`
   - `AUTO_REPLY_STOCK_ENABLED=true`
   - `USE_SAMPLE_PRODUCTS_FALLBACK=true` *(set `false` jika ingin ketat hanya memakai backend live)*
   - `CORS_ORIGINS` (domain frontend & backend yang diizinkan, dipisahkan koma)
4. Atur **Health Check Path** ke `/ai/health` lalu verifikasi respons `200 OK` dengan `model_loaded: true`.
