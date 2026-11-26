# Data Science — Toko Indo Telur

Bagian Data Science untuk Capstone Project Asah 2026 (Tim A26-CS201): dataset intent dummy untuk chatbot WhatsApp, data produk contoh, evaluasi baseline, dan alur persiapan data untuk AI Service (`DS-01` s.d. `DS-04`).

> **Batasan Privasi & Data (`BR-09` & `NFR-05`):**
> Seluruh data di folder ini adalah **data sintetis/dummy**. Tidak ada nomor telepon, identitas pelanggan, maupun riwayat percakapan WhatsApp riil milik UMKM.
> **Penting:** Analisis data transaksi riil UMKM, pola musiman penjualan, dan rekomendasi bisnis berbasis transaksi **belum selesai/belum dilakukan** karena dataset transaksi asli Toko Indo Telur belum tersedia dalam repository ini.

---

## 1. Isi Folder & Struktur Data

| File | Baris Data | Deskripsi |
| --- | --- | --- |
| `data/dataset_intent_dummy.csv` | 250 pesan dummy (50 baris per kelas intent) | Dataset intent untuk pengujian dan evaluasi baseline chatbot |
| `data/products_dummy.csv` | 8 produk sembako dummy | Sampel master produk untuk pengujian struktur data kasir & bot |
| `evaluasi_intent.py` | Script Python standalone (tanpa dependensi eksternal) | Validasi kualitas dataset (`TC-12`) dan komparasi 2 baseline model (`TC-09`) |

---

## 2. Kelas Intent & Aturan Pelabelan

Dataset intent dikelompokkan ke dalam **5 kelas intent**:

| Kelas | Definisi | Contoh Pesan Dummy |
| --- | --- | --- |
| `sapaan` | Salam pembuka saja tanpa isi pesanan/pertanyaan | `"halo"`, `"assalamualaikum kak"`, `"selamat pagi"` |
| `format_pesanan` | Pesan berisi niat pesan atau rincian order (produk + jumlah) | `"mau pesan telur 5 rak"`, `"cara order gimana?"` |
| `cek_harga` | Pertanyaan harga produk sembako | `"harga gula 1 kg berapa"`, `"minyak 2 liter harganya brp"` |
| `cek_stok` | Pertanyaan ketersediaan stok barang | `"stok telur ada kak"`, `"telur ayam ready gak?"` |
| `lainnya` | Di luar 4 kelas di atas (komplain, lokasi toko, lowongan, obrolan bebas) | `"lokasi toko di mana ya"`, `"ada lowongan kerja nggak kak"` |

**Aturan Pelabelan Intent:**
Pesan yang diawali salam tetapi memuat pesan inti dilabeli menurut intinya. Contoh:
- *"halo kak mau pesan telur 4 rak"* $\rightarrow$ `format_pesanan` (bukan `sapaan`).
- *"halo kak toko buka jam berapa?"* $\rightarrow$ `lainnya` (bukan `sapaan`).

---

## 3. Data Dictionary

### A. `data/dataset_intent_dummy.csv`

| Kolom | Tipe | Contoh Nilai | Keterangan |
| --- | --- | --- | --- |
| `text` | string | `stok telur ada kak` | Teks pesan pesan pelanggan dummy (huruf kecil). |
| `intent` | string | `cek_stok` | Label kelas intent, salah satu dari 5 kelas yang sah. |

### B. `data/products_dummy.csv` (Struktur selaras dengan respons `GET /api/products`)

| Kolom | Tipe | Contoh Nilai | Keterangan |
| --- | --- | --- | --- |
| `sku` | string | `TELUR-RAK-01` | Kode SKU produk unik. |
| `name` | string | `Telur ayam 1 rak` | Nama komoditas produk sembako. |
| `description` | string | `Data dummy` | Deskripsi produk. |
| `price` | numeric | `55000` | Harga satuan dalam Rupiah. |
| `stock` | numeric | `120` | Jumlah stok kuantitas awal. |
| `unit` | string | `rak`, `kg`, `liter`, `dus`, `butir` | Satuan ukur penjualan produk. |
| `is_active` | boolean | `true` | Penanda status produk aktif. |

---

## 4. Proses Validasi Dataset & Cara Menjalankan

Script `evaluasi_intent.py` dirancang tanpa dependensi eksternal (hanya membutuhkan Python 3 standar):

```bash
python data-science/evaluasi_intent.py
```

### Pemeriksaan Kualitas Data (`TC-12` PRD)
Sebelum melatih model, script menjalankan 3 asersi integritas data:
1. **Pengecekan Nilai Kosong:** Memastikan kolom `text` dan `intent` tidak kosong.
2. **Pengecekan Duplikasi:** Memastikan tidak ada teks pesan yang sama persis (case-insensitive).
3. **Pengecekan Label Sah:** Memastikan tidak ada label intent di luar 5 kelas yang ditentukan.
4. **Distribusi Kelas:** Menampilkan jumlah baris per kelas (harus seimbang 50 sampel per kelas).

---

## 5. Hasil Evaluasi Baseline Model (`TC-09` PRD)

Evaluasi dijalankan pada tanggal 26 November 2026 dengan konfigurasi:
- Total data: **250 baris** (tanpa data kosong, tanpa duplikat, label terverifikasi).
- Pembagian data: Stratified split seed 42 (80% train = 200 baris, 20% test = 50 baris, masing-masing 10 sampel uji per kelas).

| Konfigurasi Baseline | Fitur Ekstraksi | Classifier | Test Accuracy | Test Macro-F1 |
| --- | --- | --- | :---: | :---: |
| **Konfigurasi A** | TF-IDF 1-gram | Naive Bayes ($\alpha = 1.0$) | **0.86** | **0.86** |
| **Konfigurasi B** | TF-IDF 1-2 gram | Naive Bayes ($\alpha = 0.1$) | **0.86** | **0.86** |

### Analisis Kesalahan Prediksi (Misklasifikasi)
Dari 50 sampel data uji, terdapat 7 pesan yang salah diprediksi oleh kedua konfigurasi baseline:
1. **Penarikan kata umum pada `cek_stok` (Precision terendah: 0.69):** Kata seperti *"ada"* dan *"nggak"* menarik pesan luar cakupan ke kelas `cek_stok` (mis. pesan *"ada lowongan kerja nggak kak"* dan *"nerima pegawai nggak"* dari kelas `lainnya` salah diklasifikasi sebagai `cek_stok`).
2. **Pesan order tanpa kata kunci eksplisit:** Pesan *"minta telur 8 rak ya kak"* (`format_pesanan`) salah diprediksi sebagai `cek_harga` karena tidak memuat kata *"pesan"* atau *"order"*.
3. **Pesan terlalu singkat / ejaan unik:** Pesan *"p"* dan *"assalamu'alaikum"* (`sapaan`) salah diprediksi sebagai `cek_stok`.
4. **Pesan penutup chat:** Pesan *"baik kak ditunggu"* (`lainnya`) salah diprediksi sebagai `sapaan`.

---

## 6. Hubungan dengan Folder `ai-service/` & Alur Handoff

- **Perbedaan Dataset:** Folder `ai-service/` menggunakan dataset internal dummy awal sebanyak **202 baris mentah (200 setelah deduplikasi)** dan menghasilkan metrik evaluasi accuracy 0.9250 / macro-F1 0.9229 dengan model `tfidf_linear_svc`.
- **Larangan Perbandingan Langsung:** Angka **0.86** (baseline DS 250 baris) dan **0.925** (model AI 200 baris) **tidak boleh dibandingkan langsung** karena dataset, jumlah sampel, serta algoritma pembandingnya berbeda.
- **Status Retraining:** Model aktif pada `ai-service` saat ini **belum di-retrain** menggunakan dataset 250 baris milik Data Science.
- **Alur Handoff Dataset:** File `dataset_intent_dummy.csv` ini disiapkan untuk dioper ke tim AI Service sebagai masukan argumen `--dataset` pada script retraining:
  ```bash
  cd ai-service
  python src/train_evaluate.py --dataset ../data-science/data/dataset_intent_dummy.csv
  ```

---

## 7. Batasan & Rekomendasi Pekerjaan Data Science Selanjutnya

1. **Keterbatasan Data Dummy:** Seluruh kalimat ditulis secara sintetis dari sumber internal, sehingga ragam bahasa percakapan, slang Bontang, dan variasi singkatan lokal masih terbatas.
2. **Ketiadaan Data Transaksi:** Dataset `products_dummy.csv` hanya berisi 8 produk contoh dan belum ada dataset histori penjualan nyata UMKM di folder ini.
3. **Rekomendasi Pekerjaan Selanjutnya:**
   - Mengumpulkan data transaksi dan riwayat nota yang telah diizinkan pemilik UMKM.
   - Melakukan Exploratory Data Analysis (EDA) terhadap produk terlaris, jam ramai transaksi, dan waktu siklus pemesanan hingga pengantaran.
   - Menambah variasi kata negatif dan teks di luar cakupan (*out-of-scope*) pada kelas `lainnya` untuk menaikkan precision kelas `cek_stok`.
   - Menguji performa classifier lanjutan (misalnya SVM linier dengan char n-gram) sebelum handoff final ke AI Service.
