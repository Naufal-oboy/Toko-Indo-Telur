# Product Requirements Document (PRD)

## Sistem Nota Digital & Chatbot Toko Indo Telur

| Informasi | Keterangan |
| --- | --- |
| Program | Asah 2026 — Capstone Project |
| Tim | A26-CS201 |
| UMKM | Toko Indo Telur, grosir sembako di Bontang |
| Judul use case | Kemudahan Pembuatan Nota Penjualan dan Penanganan Pesanan Pelanggan untuk Toko Indo Telur |
| Jenis produk | MVP aplikasi kasir web (browser Android), layanan data/stok, dan chatbot WhatsApp nomor uji |
| Status dokumen | **Draft rencana berdasarkan Project Plan revisi**, belum merupakan bukti implementasi |
| Horizon perencanaan | Empat minggu; tanggal kalender resmi belum ditetapkan dalam dokumen sumber |
| Sasaran validasi | Pemilik UMKM mencoba alur nota, printer, pemulihan data, dan chatbot; memberi feedback |

> **Status perubahan scope:** Pengaturan stok otomatis, sinkronisasi data server, chatbot pertanyaan harga/stok, dan ekspor CSV **dipertahankan sebagai fitur rencana tim** karena tercantum dalam Project Plan. Keempatnya merupakan perluasan dari use case awal yang masih harus dikonfirmasi kepada PIC UMKM dan Tim Asah. Tidak ada fitur lama yang dihapus dari PRD ini.

> **Status implementasi per 21 November 2026:** Backend Express sudah dapat memeriksa koneksi PostgreSQL. Migration initial telah diterapkan untuk produk, transaksi, item transaksi, pergerakan stok, dan catatan sinkronisasi. Constraint untuk nominal, kuantitas, dan field snapshot nota; trigger untuk total/audit stok/pencegahan stok negatif; serta mekanisme idempotency telah diuji. CRUD, endpoint penjualan, sinkronisasi aplikasi, chatbot, cetak, dan fitur offline belum diimplementasikan.

## 1. Ringkasan produk

Toko Indo Telur melayani pesanan grosir sembako melalui WhatsApp dan gudang. Pencatatan dan pembuatan nota masih manual oleh satu orang. Ketika volume chat meningkat, ada pesan terlambat dibalas dan nota disiapkan mendekati waktu pengantaran. Produk ini merencanakan kasir web dengan nota digital, pengelolaan produk/stok, offline-first, sinkronisasi, cetak nota thermal, backup/restore, serta chatbot pada nomor WhatsApp uji untuk sapaan, format pemesanan, dan pengecekan stok/harga melalui server.

MVP ditujukan untuk **demonstrasi serta validasi kebutuhan**, bukan janji siap digunakan pada lingkungan produksi. Keputusan adopsi dilakukan terpisah oleh UMKM.

## 2. Masalah dan konteks

### 2.1 Proses saat ini (as-is)

1. Pelanggan memesan melalui WhatsApp atau datang ke gudang.
2. Pemilik membalas satu per satu, mencatat detail, dan menghitung total manual.
3. Nota ditulis menjelang pengantaran; sebagian nota dapat menyusul.
4. Pengantaran umumnya dilakukan sekitar 2–5 hari setelah pemesanan.
5. Pembayaran dilakukan tunai atau transfer setelah pengantaran atau paling lambat satu minggu setelahnya.

### 2.2 Masalah yang ditemukan

- Pembuatan nota dilakukan manual dan bergantung pada satu orang.
- Waktu pemilik tersita untuk pekerjaan berulang.
- Banyak pesan masuk menyebabkan sebagian pelanggan lambat mendapat respons.
- Nota yang terlambat mengganggu pengecekan barang pada pengantaran.

### 2.3 Pernyataan masalah

> Bagaimana membantu pemilik grosir membuat dan menyiapkan nota penjualan sebelum pengantaran, sembari menyediakan respons awal pelanggan yang lebih cepat, dengan MVP web yang tetap dapat mencatat transaksi saat offline?

## 3. Tujuan dan batas keberhasilan

### Tujuan produk

1. Mempercepat alur pembuatan nota dibanding pencatatan manual, tanpa menjanjikan besaran peningkatan tertentu.
2. Menjaga konsistensi produk, harga, stok, dan riwayat nota.
3. Memungkinkan transaksi offline di perangkat pemilik serta sinkronisasi ketika internet tersedia.
4. Menghasilkan nota yang dapat dicetak pada printer toko atau dibagikan secara digital.
5. Mengotomatiskan respons awal dan memberi informasi harga/stok dari data server melalui chatbot nomor uji.
6. Memenuhi pekerjaan Main Quest untuk Full-Stack, Data Science, dan Next Gen AI Engineer.

### Indikator penerimaan MVP (bukan capaian yang sudah terbukti)

- Pemilik dapat membuat, menyimpan, melihat kembali, mencetak/membagikan nota dari HP.
- Proses nota offline berjalan setelah aplikasi disiapkan; data tidak hilang ketika halaman ditutup.
- Backup dapat dipulihkan pada perangkat berbeda tanpa merusak data aktif ketika file invalid.
- Penjualan yang disinkronkan tidak tercatat dua kali.
- Chatbot uji membalas sapaan, format pemesanan, dan permintaan harga/stok sesuai data server, dengan pesan aman bila data tidak tersedia atau usang.
- Website dan REST API AI mempunyai URL yang bisa diakses untuk demonstrasi setelah deployment.
- Hasil analisis DS dan evaluasi dua model/konfigurasi AI terdokumentasi dengan data dan metrik yang dapat diperiksa.
- UMKM memberi feedback setelah mencoba skenario inti.

## 4. Pengguna dan hak interaksi

| Aktor | Kebutuhan | Lingkup interaksi |
| --- | --- | --- |
| Pemilik toko / operator kasir | Membuat nota, mengelola produk dan stok, mencetak, backup dan melihat riwayat | Pengguna utama web kasir |
| Pengantar barang | Mendapat nota yang siap sebelum pengantaran | Penerima nota cetak atau berkas digital |
| Pelanggan | Mendapat balasan awal serta informasi harga/ketersediaan | Pesan WhatsApp ke nomor uji pada tahap demo |
| Tim pengembang | Menguji fitur, dataset, model, API, dan sistem | Akses pengembangan dan data uji yang diizinkan |

**Catatan:** mekanisme akun, otorisasi, dan identitas pelanggan untuk sistem produksi **belum diputuskan** di dokumen sumber. Jangan menganggap autentikasi atau penyimpanan data pelanggan nyata telah disetujui.

## 5. Ruang lingkup, prioritas, dan status sumber

- **Wajib (Proyek):** komitmen fungsi yang ditulis tim dalam Project Plan.
- **Wajib (Use Case):** dibutuhkan untuk memenuhi alur use case awal.
- **Wajib (Main Quest):** hasil kerja pendidikan yang diwajibkan checklist learning path.
- **Tambahan (Proyek):** nilai tambah yang juga tercatat pada Project Plan.

Seluruh butir di bawah merupakan **target**, bukan pernyataan fitur sudah selesai.

### 5.1 Functional requirements (FR)

| ID | Fitur / requirement | Prioritas sumber | Kriteria penerimaan ringkas |
| --- | --- | --- | --- |
| FR-01 | Pembuatan nota digital | Wajib (Proyek) | Produk dan jumlah bisa dipilih, total otomatis, nota tersimpan, input tidak valid ditolak. |
| FR-02 | CRUD produk & harga | Wajib (Proyek) | Produk dapat ditambah, diubah, dihapus; harga historis nota tidak berubah. |
| FR-03 | Manajemen stok otomatis | Wajib (Proyek) | Stok berubah setelah transaksi tersimpan; kuantitas melebihi stok diberi peringatan. |
| FR-04 | Riwayat nota | Wajib (Proyek) | Nota tampil kembali dengan tanggal, item, harga saat transaksi, dan total yang sama. |
| FR-05 | Mode kasir offline/online | Wajib (Proyek) | Nota/produk/stok lokal tetap bisa dipakai offline setelah penyiapan awal, data tetap ada setelah aplikasi ditutup. |
| FR-06 | Cetak nota thermal Bluetooth 58 mm | Wajib (Proyek) | Nota 1–10 item dapat dicetak dan terbaca di printer toko; kegagalan cetak tidak menghapus nota. |
| FR-07 | Backup dan restore melalui file | Wajib (Proyek) | Data produk, stok, nota pulih pada HP lain; file invalid ditolak tanpa merusak data lama. |
| FR-08 | Sinkronisasi transaksi dan stok | Wajib (Proyek) | Transaksi offline terkirim saat online; retry tidak membuat nota ganda. |
| FR-09 | Server dan database stok online | Wajib (Proyek) | Produk/harga/stok tersimpan di server dan dapat diakses web kasir serta chatbot. |
| FR-10 | Balasan WhatsApp dasar | Wajib (Proyek) | Nomor uji membalas sapaan, petunjuk format pesan, dan pesan di luar aturan. |
| FR-11 | Chatbot WhatsApp harga & stok | Wajib (Proyek) | Jawaban berdasarkan data server; produk tidak dikenal ditangani; bot tidak mengubah stok. |
| FR-12 | Pengujian dan perbaikan | Wajib (Proyek) | Uji fitur normal/invalid/offline/sinkronisasi dicatat, bug diperbaiki lalu diuji ulang. |
| FR-13 | Demonstrasi dan feedback UMKM | Wajib (Proyek) | Pemilik mencoba nota, cetak, chatbot, dan memberikan evaluasi. |
| FR-14 | UI status aksi & panduan | Wajib (Main Quest, FS) | Indikator loading/berhasil/gagal ditampilkan; alur dapat dicoba mengikuti panduan. |
| FR-15 | Website web publik | Wajib (Main Quest, FS) | URL dapat dibuka browser HP dan alur inti dapat diakses saat demo. |
| FR-16 | Berbagi nota digital gambar/PDF | Wajib (Use Case) | Berkas yang dibagikan sama dengan nota tersimpan; dapat dikirim ke pengantar/pelanggan. |
| FR-17 | Ekspor riwayat nota CSV | Tambahan (Proyek) | CSV terunduh dan dapat dibuka dalam aplikasi spreadsheet. |

**Kelengkapan:** FR-01 s.d. FR-17 mencakup seluruh fitur kasir, stok, server, chatbot, operasional uji/demo, berbagi nota, dan CSV dari Project Plan terbaru. Persyaratan DS/AI dijabarkan terpisah pada §8 agar tidak tertukar dengan fungsi aplikasi pelanggan.

### 5.2 Yang tidak dikerjakan

- Sinkronisasi **antar-HP secara real-time** (berbeda dari mengirim transaksi offline ke server saat online).
- Chatbot yang mengubah stok atau melakukan pembayaran.
- Dukungan printer selain printer milik toko atau konfigurasi printer lanjutan.
- Laporan keuangan lengkap.
- Pembayaran digital.
- Penerapan produksi otomatis setelah demonstrasi.

## 6. Alur pengguna

### UF-01 — Pemilik membuat nota

1. Buka aplikasi kasir di HP.
2. Pilih produk dan masukkan kuantitas; aplikasi menampilkan harga, stok lokal, dan total.
3. Validasi bahwa jumlah positif, produk sah, dan stok memadai.
4. Simpan nota; sistem mencatat snapshot item/harga transaksi dan mengurangi stok lokal.
5. Lihat nota pada riwayat.
6. Cetak ke printer thermal toko atau bagikan nota digital.
7. Jika offline, transaksi berstatus menunggu sinkronisasi; ketika online, kirim ke server tanpa mencatat ganda.

**Kondisi gagal:** produk dihapus/invalid, kuantitas nol/huruf, stok tidak mencukupi, penyimpanan gagal, atau printer tak tersambung. Aplikasi harus menampilkan pesan yang jelas dan tidak kehilangan nota yang sudah disimpan.

### UF-02 — Pemulihan setelah perangkat rusak

1. Pemilik membuat file cadangan dari perangkat A.
2. Pemilik membuka aplikasi pada perangkat B.
3. Pilih file cadangan; aplikasi memvalidasi struktur dan versi data.
4. Setelah dikonfirmasi, aplikasi memulihkan produk, stok, dan nota.
5. Verifikasi jumlah entri serta beberapa sampel sebelum melanjutkan transaksi.

**Kondisi gagal:** file rusak, format salah atau impor terputus → data yang ada tetap utuh.

### UF-03 — Chatbot menerima pesan uji

1. Pesan masuk ke **nomor WhatsApp uji** melalui mekanisme integrasi yang diizinkan.
2. Pesan diteruskan ke backend dan API AI untuk mendeteksi maksud (sapaan, format pemesanan, pertanyaan stok/harga, lain-lain).
3. Untuk harga/stok, backend mengambil data **server**, bukan mengandalkan angka stok di HP yang belum sinkron.
4. Fitur generatif dapat menyusun saran jawaban dari API proprietary; aturan validasi memastikan harga/stok tetap berdasarkan database.
5. Bot mengirim respons atau pesan fallback yang aman jika input tidak dikenal, data tak mutakhir, atau layanan gagal.

**Aturan penting:** chatbot bersifat **read-only** terhadap stok dan transaksi; bila data server mungkin tertinggal, jelaskan bahwa ketersediaan merupakan perkiraan dan perlu konfirmasi pemilik.

## 7. Aturan bisnis (BR)

| ID | Aturan | Rasional / uji |
| --- | --- | --- |
| BR-01 | Jumlah item harus bilangan positif; harga tidak boleh negatif | Hindari nota tidak valid |
| BR-02 | Nilai item pada nota memakai snapshot nama/harga saat transaksi | Perubahan harga produk tidak mengubah nota historis |
| BR-03 | Stok lokal berkurang setelah penyimpanan transaksi yang berhasil | Hindari stok terpotong jika nota gagal disimpan |
| BR-04 | Penjualan melebihi stok terpantau memunculkan peringatan dan tidak disimpan sebagai transaksi normal | Hindari stok negatif tak disengaja |
| BR-05 | Setiap nota memiliki pengenal unik yang stabil untuk retry | Menjamin idempotensi sinkronisasi |
| BR-06 | Server menurunkan pergerakan stok dari transaksi diterima; jangan menimpa angka stok tanpa aturan konflik | Hindari selisih antara kasir dan chatbot |
| BR-07 | Nota offline disimpan dan diberi status sinkronisasi | Pemilik memahami data belum terkirim ke server |
| BR-08 | Bot membaca harga/stok hanya melalui backend dan tidak mengubah keduanya | Pembatasan peran chatbot |
| BR-09 | Data pelanggan nyata dan isi chat asli tidak digunakan dalam pengembangan tanpa izin eksplisit | Privasi UMKM dan pelanggan |
| BR-10 | Fallback cetak berupa aplikasi pendamping atau berkas gambar/PDF | Kompatibilitas Bluetooth Android tidak dijamin |

## 8. Persyaratan Data Science dan Gen AI (Main Quest)

### 8.1 Data Science — DS-01 s.d. DS-04

| ID | Deliverable | Kriteria penerimaan |
| --- | --- | --- |
| DS-01 | Business questions | Rumuskan pertanyaan terkait proses pesanan, produk, dan penjualan serta peran data pada solusi. |
| DS-02 | Data wrangling dan validasi | Bersihkan format, nilai hilang/invalid, dan duplikasi; catat sumber, asumsi, dan batasan data dummy. |
| DS-03 | Analisis dan rekomendasi | Hasil analisis menjawab pertanyaan bisnis, perhitungannya diperiksa, dan rekomendasinya bisa dipahami UMKM. |
| DS-04 | Dataset untuk FS/AE | Sediakan tabel produk/harga/stok contoh, transaksi/pesan uji tanpa identitas, serta data dictionary; bagi data latih dan uji bila model membutuhkan pelatihan. |

**Sumber data:** daftar produk dan contoh nota yang diizinkan pemilik; selebihnya data sintetis/dummy. Tanpa akses ke chat dan nomor telepon pelanggan asli. Temuan dari data dummy tidak boleh diklaim mewakili kinerja bisnis nyata.

### 8.2 Gen AI — AI-01 s.d. AI-04

| ID | Deliverable | Kriteria penerimaan |
| --- | --- | --- |
| AI-01 | Model klasifikasi maksud pesan | Definisi kelas jelas; preprocessing terdokumentasi; pelatihan hanya memakai train set dan evaluasi pada test set terpisah. |
| AI-02 | Saran balasan generatif | Memanggil API proprietary dari server; hasil relevan dan tidak digunakan untuk mengarang harga/stok. |
| AI-03 | Perbandingan model/konfigurasi | Bandingkan minimal dua model/konfigurasi dengan **data evaluasi dan metrik yang sama**; tulis alasan pemilihan. |
| AI-04 | REST API model online | Model dapat diakses backend melalui **FastAPI atau Flask** di endpoint daring; validasi input/error diuji. |

**Dokumentasi wajib di README proyek saat hasil tersedia:** rumusan masalah, sumber dan hak penggunaan dataset, preprocessing, model yang digunakan/dilatih, penyedia API proprietary, library/dependensi, konfigurasi percobaan, tabel hasil evaluasi dan keputusan pemilihan. Saat ini belum ada nilai metrik, tautan model, atau API provider yang telah dipastikan.

**Metrik yang diusulkan (perlu disepakati sebelum uji):** accuracy dan macro-F1 untuk intent classifier; penilaian relevansi/ketepatan fakta untuk saran jawaban. Ini merupakan **usulan teknis**, bukan hasil atau syarat metrik numerik dari dokumen sumber.

## 9. Non-functional requirements (NFR)

| ID | Persyaratan | Kriteria uji |
| --- | --- | --- |
| NFR-01 | Responsif di browser Android | Layar kasir dan nota dapat digunakan pada HP saat uji demo. |
| NFR-02 | Persistensi offline | Nota dan stok lokal tetap ada setelah browser ditutup lalu dibuka kembali. |
| NFR-03 | Ketahanan sinkronisasi | Retry/putus koneksi tidak menghilangkan atau menggandakan transaksi. |
| NFR-04 | Keamanan data & kunci | Kunci API dan webhook berada di server, tidak masuk GitHub atau bundle frontend. |
| NFR-05 | Privasi dan minimisasi data | Pengujian memakai data dummy/diizinkan; tidak menyalin nomor dan percakapan pelanggan asli. |
| NFR-06 | Ketahanan impor | File backup yang invalid gagal aman tanpa merusak data eksisting. |
| NFR-07 | Keterbacaan cetak | Nota 58 mm untuk 1 dan 10 item terbaca pada printer toko yang diuji. |
| NFR-08 | Transparansi status | Loading/sukses/gagal serta status sinkronisasi tampil jelas. |
| NFR-09 | Dokumentasi | README, panduan, skema data, hasil evaluasi model dan hasil pengujian tersedia setelah pengembangan. |
| NFR-10 | Deployment demo | Website publik dan REST API AI dapat diakses untuk uji; URL ditambahkan setelah aktif. |

**Belum disepakati:** SLA/uptime, angka batas latensi, target throughput, kebijakan retensi data produksi, dan dukungan lintas versi Android. Tidak ditetapkan angka spekulatif di PRD ini.

## 10. Rancangan teknis dan baseline implementasi

### 10.1 Komponen

- **Frontend:** React untuk kasir, produk, riwayat, stok, cetak, ekspor, backup/restore, dan status sinkronisasi.
- **Penyimpanan lokal:** mekanisme browser yang dipilih tim untuk menyimpan nota, produk, stok, dan antrean transaksi offline.
- **Backend aplikasi:** Node.js + Express. Endpoint `GET /api/health` dan `GET /api/db-check` tersedia; endpoint transaksi, produk, harga/stok, sinkronisasi, dan penghubung WhatsApp/AI masih akan dibuat.
- **Database server:** PostgreSQL melalui driver `pg`. Migration awal dan mekanisme pencatatan migration telah diterapkan untuk penyimpanan produk, stok, dan transaksi online.
- **Layanan AI:** model klasifikasi dengan FastAPI **atau** Flask, serta akses ke API proprietary untuk saran jawaban.
- **WhatsApp:** integrasi berbasis nomor uji/sandbox, bergantung akses yang disediakan dan ketentuan platform.
- **Data Science:** Python/Pandas untuk olah data, analisis, validasi, dan dataset contoh.

### 10.2 Baseline skema database (sudah diimplementasikan)

| Entitas | Field utama | Catatan |
| --- | --- | --- |
| `products` | id, sku, name, description, price, stock, unit, is_active | Harga saat ini; soft delete memakai `is_active`. |
| `transactions` | id, client_transaction_id, invoice_number, transaction_date, total_amount, payment_method, payment_status | UUID perangkat dan nomor nota unik. |
| `transaction_items` | transaction_id, product_id, product_name_snapshot, unit_snapshot, quantity, unit_price, subtotal | Snapshot memastikan nota lama tidak berubah. |
| `stock_movements` | product_id, transaction_id, movement_type, quantity_change, stock_before, stock_after | Audit immutable; trigger mengubah stok secara atomik dan mencegah nilai negatif. |
| `sync_records` | client_transaction_id, device_id, server_transaction_id, status, error_message | Gate idempotency untuk retry transaksi offline. |

Skema ini adalah baseline implementasi untuk MVP. Perubahan kompatibel ditambahkan melalui migration baru; jangan mengubah migration yang telah dijalankan. ERD, tipe data, constraint, indeks, dan kontrak idempotency dirinci dalam [Database Schema](./docs/database-schema.md).

### 10.3 Endpoint awal (contoh kontrak untuk diskusi)

| Operasi | Usulan endpoint | Tujuan |
| --- | --- | --- |
| Health check | `GET /api/health` | **Sudah tersedia** untuk memeriksa backend. |
| Database check | `GET /api/db-check` | **Sudah tersedia** untuk memeriksa koneksi PostgreSQL. |
| Daftar / ubah produk | `GET/POST/PATCH /api/products` | CRUD produk dan harga |
| Simpan nota | `POST /api/invoices` | Menyimpan transaksi valid |
| Riwayat nota | `GET /api/invoices` | Menampilkan transaksi terdahulu |
| Sinkronisasi batch | `POST /api/sync/invoices` | Mengirim transaksi offline secara idempoten |
| Baca stok/harga | `GET /api/products/:id` | Lookup data server untuk aplikasi/bot |
| Klasifikasi intent | `POST /ai/predict-intent` | Inferensi model yang disajikan FastAPI/Flask |
| Saran respons | `POST /ai/suggest-reply` | Memanggil API generatif di sisi server |
| Pesan masuk | Webhook sesuai platform WhatsApp yang dipilih | Menerima pesan nomor uji |

Selain health check dan database check, path di atas masih **contoh rancangan**, bukan endpoint yang sudah dibuat. Gunakan satu database transaction untuk penyimpanan nota, item, pergerakan stok, dan status sinkronisasi; gunakan skema error, autentikasi, dan rate limit yang ditetapkan tim pada implementasi.

## 11. Rencana pengujian dan acceptance scenarios

| ID | Skenario | Hasil yang diharapkan |
| --- | --- | --- |
| TC-01 | Harga Rp20.000 × 3 item, lalu input kosong/nol/huruf | Total Rp60.000 tersimpan; input invalid ditolak. |
| TC-02 | Ubah harga produk lalu cek nota historis | Nota baru memakai harga terbaru; nota lama tetap sama. |
| TC-03 | Stok 10, jual 3, lalu coba jual 20 | Stok menjadi 7; permintaan berlebih mendapat peringatan. |
| TC-04 | Buat tiga nota offline lalu sambungkan internet; putus koneksi saat retry | Ketiganya muncul tepat sekali di server dan stok konsisten. |
| TC-05 | Cetak nota 1 dan 10 item; matikan printer | Cetak terbaca di 58 mm; kegagalan menampilkan pesan dan nota tidak hilang. |
| TC-06 | Backup di HP A, restore di HP B; ulangi dengan berkas rusak | Data pulih setara; file invalid ditolak tanpa kerusakan. |
| TC-07 | Pesan “halo”, “mau pesan”, pesan tak dikenali | Sapaan, format pemesanan, dan fallback sesuai kebutuhan. |
| TC-08 | Pesan “stok telur ada?”, “harga gula berapa?”, salah ketik dan produk tidak ada | Jawaban sesuai data server; kesalahan/produk tak dikenal ditangani sopan. |
| TC-09 | Evaluasi dua model/config menggunakan data dan metrik sama | Tabel perbandingan dan alasan pilihan model terdokumentasi. |
| TC-10 | Panggil REST API AI dengan input valid/invalid dan saat layanan generatif gagal | Respons terstruktur; kesalahan ditangani aman dan dapat ditelusuri. |
| TC-11 | Akses URL web melalui browser HP; coba loading, error, success | Website dapat dibuka dan status antarmuka mudah dipahami. |
| TC-12 | Periksa dataset DS untuk kosong, duplikat, tipe/format, dan perhitungan sampel | Data bersih, sumber/asumsi tercatat, temuan dapat diverifikasi. |
| TC-13 | Unduh CSV transaksi | Berkas terbuka dengan tanggal, item/nominal sesuai riwayat. |
| TC-14 | Bagikan gambar/PDF nota | Isi sama dengan nota yang tersimpan. |
| TC-15 | Minta pemilik mencoba alur lengkap saat demo | Feedback, kendala, dan tindakan lanjut dicatat. |

**Pelacakan:** catat input, expected, actual, pass/fail, bug, PIC, tanggal retest melalui GitHub Issues/project board dan lembar hasil uji. Hasil pengujian aktual belum tersedia.

**Hasil pengujian database awal (21 November 2026):** migration diterapkan dan dapat dijalankan ulang tanpa duplikasi; lima tabel aplikasi dan lima foreign key terdeteksi; harga negatif, stok negatif, kuantitas nol, dan penjualan yang menghasilkan stok negatif ditolak. Pengujian menggunakan transaksi yang di-rollback sehingga tidak meninggalkan data dummy. Skenario lain pada tabel ini masih merupakan rencana pengujian.

## 12. Roadmap dan pembagian pekerjaan

| Pekan | Full-Stack (Naufal, Ikhwan, Ridwan) | Data Science (Ridwanansyah, Jovan) | Gen AI (Winsen) |
| --- | --- | --- | --- |
| 1 | Wireframe, React dasar, CRUD produk, nota/riwayat, uji awal printer | Pertanyaan bisnis, data contoh, data dictionary, validasi awal | Rumusan intent, format dataset, preprocessing awal |
| 2 | Stok, kasir offline, backup, backend/database, uji fitur | Data wrangling, analisis, rekomendasi awal, dataset bagi AI | Latih dua model/config, integrasi API generatif, rancangan REST API |
| 3 | Sinkronisasi, cetak/bagikan nota, status aksi, integrasi chatbot | Validasi hasil, serahkan data/artefak final | Bandingkan model, REST API online, chatbot nomor uji |
| 4 | E2E testing, bug fixing, URL publik, panduan dan demo | Pemeriksaan ulang kualitas analisis, dokumentasi | Pengujian layanan AI, laporan evaluasi, README AI |

Target alur utama terintegrasi adalah **akhir pekan ketiga**. Pekan keempat dipakai untuk hardening, pengujian, perbaikan, dokumentasi dan feedback. Tanggal pelaksanaan resmi **belum dilengkapi** dalam Project Plan.

## 13. Risiko dan mitigasi

| Risiko | Dampak | Mitigasi / fallback |
| --- | --- | --- |
| Web–printer Bluetooth tidak kompatibel | Cetak terhambat | Uji pada pekan 1; aplikasi cetak pendamping atau bagikan PDF/gambar. |
| Data browser terhapus/perangkat rusak | Kehilangan nota dan stok | Backup/restore file, gunakan salinan server yang sudah sinkron. |
| Server stok tertinggal transaksi offline | Jawaban chatbot tidak akurat | Tandai stok perkiraan; pemilik dapat menonaktifkan auto-reply stok. |
| Retry sinkronisasi menggandakan transaksi | Nota dan stok ganda | ID unik nota dan proses idempoten, uji putus koneksi. |
| Dataset terbatas/dummy | Analisis/model tidak representatif | Dokumentasikan keterbatasan dan validasi hasil dengan pemilik. |
| Kuota/error proprietary AI | Balasan tidak tersedia | Timeout, penanganan error, template balasan aturan sederhana. |
| WhatsApp sandbox/webhook tidak tersedia | Bot tidak dapat didemokan langsung | Siapkan simulasi payload/chat test, tetapi fitur integrasi tetap dalam rencana. |
| Cakupan terlalu besar untuk empat minggu | MVP terlambat | Uji per pekan, prioritaskan demo E2E, dokumentasikan status dan eskalasi. |
| Perluasan scope belum mendapat persetujuan | Ketidaksesuaian persyaratan use case | Konfirmasi tertulis ke PIC UMKM dan Tim Asah; jangan klaim sudah disetujui. |

