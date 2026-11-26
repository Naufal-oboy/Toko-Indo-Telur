# Data Science — Toko Indo Telur

Bagian data science untuk Capstone Asah 2026 (Tim A26-CS201): dataset intent
untuk chatbot WhatsApp, data produk contoh, dan evaluasi baseline.

> Seluruh data di folder ini **dummy/sintetis**. Tidak ada chat, nama, atau nomor

## Isi folder

| File | Isi |
| --- | --- |
| `data/dataset_intent_dummy.csv` | 250 pesan WhatsApp dummy, 50 per kelas, 5 kelas intent |
| `data/products_dummy.csv` | 8 produk contoh dengan harga dan stok dummy |
| `evaluasi_intent.py` | Validasi dataset dan perbandingan dua konfigurasi baseline |

## Kelas intent

| Kelas | Arti | Contoh |
| --- | --- | --- |
| `sapaan` | Salam pembuka saja | "halo", "assalamualaikum kak" |
| `format_pesanan` | Pesan berisi order (produk + jumlah) | "mau pesan telur 5 rak" |
| `cek_harga` | Menanyakan harga produk | "harga gula 1 kg berapa" |
| `cek_stok` | Menanyakan ketersediaan | "stok telur ada kak" |
| `lainnya` | Di luar empat kelas di atas (fallback) | "lokasi toko di mana ya" |

Nama kelas dan skema CSV (`text,intent`) mengikuti yang dipakai di `ai-service`,
sehingga file ini bisa langsung dipakai lewat argumen `--dataset` pada
`ai-service/src/train_evaluate.py`.

Aturan pelabelan: pesan yang diawali salam dilabeli menurut isinya. Contoh:
"halo kak mau pesan telur 4 rak" adalah `format_pesanan`, dan
"halo kak toko buka?" adalah `lainnya`.

## Data dictionary

**`dataset_intent_dummy.csv`**

| Kolom | Tipe | Keterangan |
| --- | --- | --- |
| `text` | text | Isi pesan, huruf kecil |
| `intent` | text | Salah satu dari 5 kelas intent |

**`products_dummy.csv`** (nama kolom mengikuti field produk pada respons `GET /api/products`)

| Kolom | Tipe | Keterangan |
| --- | --- | --- |
| `sku` | text | Kode produk, unik |
| `name` | text | Nama produk |
| `description` | text | Keterangan, saat ini selalu "Data dummy" |
| `price` | numeric | Harga per satuan dalam rupiah |
| `stock` | numeric | Jumlah stok |
| `unit` | text | rak, kg, liter, dus, atau butir |
| `is_active` | boolean | Status produk |

## Cara menjalankan

```bash
python data-science/evaluasi_intent.py
```

Hanya butuh Python 3, tanpa library tambahan.

## Hasil baseline (26 November 2026)

- Validasi: 250 baris, 0 kosong, 0 duplikat, 0 label tak dikenal.
- Split: stratified 200 latih / 50 uji (10 per kelas), seed 42.

| Konfigurasi | Accuracy | Macro-F1 |
| --- | --- | --- |
| A: TF-IDF 1-gram + Naive Bayes (alpha 1.0) | 0,86 | 0,86 |
| B: TF-IDF 1-2 gram + Naive Bayes (alpha 0.1) | 0,86 | 0,86 |

Temuan dari 7 pesan uji yang salah:

- `cek_stok` punya precision terendah (0,69). Kata umum seperti "ada" dan
  "nggak" menarik pesan lain ke kelas ini, misalnya "ada lowongan kerja nggak kak".
- Order tanpa kata "pesan" atau "order" tertukar dengan `cek_harga`,
  misalnya "minta telur 8 rak ya kak".
- Pesan sangat pendek atau ejaan tidak baku salah diklasifikasi, misalnya "p"
  dan "assalamu'alaikum".
- Ucapan seperti "baik kak ditunggu" tertukar dengan `sapaan`.

## Batasan

- Semua pesan sintetis dan ditulis dari satu sumber, sehingga variasi gaya
  bahasanya lebih sempit daripada pesan pelanggan asli.
- Harga dan stok produk bukan data toko.
- Baseline ini untuk menguji dataset, bukan model final chatbot.
