# Daftar Perubahan terhadap Laporan Perancangan JedaCut

Dokumen ini merangkum semua perbedaan antara **Laporan Perancangan JedaCut** dan aplikasi yang sudah diimplementasikan (repo `ch4nnndra/Jeda-Cut`, sampai commit `f15d555`). Tujuannya sebagai panduan merombak isi laporan supaya sesuai dengan aplikasi.

Keterangan status:

- **Wajib direvisi**: isi laporan sekarang bertentangan dengan aplikasi.
- **Disarankan**: laporan tidak salah, tetapi perlu penjelasan tambahan agar sesuai implementasi.
- **Tambahan baru**: hal yang belum ada di laporan sama sekali.

---

## Ringkasan

| No | Perubahan | Status | Bagian laporan yang terdampak |
|----|-----------|--------|-------------------------------|
| 1 | Tiga metode threshold diganti satu metode Adaptif (Midpoint dan Dual jadi pembanding) | Wajib direvisi | Tabel 2.4 no. 2 sampai 5, Gambar 3.1, 3.2.5, 3.2.6, 3.2.8, 3.2.9 (contoh EDL), Tabel 3.2, Gambar 3.3, 3.4, 4.1 no. 1 |
| 2 | Crossfade video (3 frame) dihapus | Wajib direvisi | 2.2.3, Tabel 2.4 no. 12, 3.2.10, Tabel 3.2, 3.3.3 (Layar Unggah), Gambar 3.3 |
| 3 | Tombol Ekspor EDL (.json dan .csv) dihapus | Wajib direvisi | 3.2.9, 3.3.3 (Layar Tinjau), Gambar 3.4 |
| 4 | Vue Router dan Pinia tidak dipakai | Wajib direvisi | 3.3.2, Tabel 3.3 |
| 5 | Komponen DropZone dan VideoPreview digabung ke view | Wajib direvisi | Tabel 3.3 |
| 6 | Render per bagian diwujudkan dengan input yang di-seek (ekspor 30 menit: 34 menit menjadi 91 detik) | Wajib direvisi | 3.2.10 |
| 7 | Crossfade audio diwujudkan sebagai fade out + fade in 15 ms | Disarankan | 3.2.10, Gambar 3.1 |
| 8 | Ekstraksi audio langsung ke memori, tanpa file WAV | Disarankan | 3.2.1, Gambar 3.1 |
| 9 | Encoder Otomatis memeriksa apakah h264_nvenc benar-benar bisa dipakai | Disarankan | 3.2.10, Tabel 3.2, Gambar 3.3 |
| 10 | Segmen Pertahankan yang bersebelahan digabung sebelum render | Disarankan | 3.2.9 |
| 11 | Endpoint tambahan `GET /api/defaults` dan `POST /api/cancel/{id}` (batalkan render), preview tanpa endpoint | Disarankan | Tabel 3.4 |
| 12 | Penyesuaian tampilan (aksesibilitas WCAG 2.1 AA, warna, responsive HP, bilah aksi) | Tambahan baru | 3.3.3, Gambar 3.3, Gambar 3.4 |
| 13 | Arsitektur deploy: Vercel + backend di laptop lewat Cloudflare Tunnel | Tambahan baru | 3.3.1, Gambar 3.2 |
| 14 | Script evaluasi sudah dibuat, dengan beberapa keputusan teknis | Disarankan | 3.4 |
| 15 | Temuan teknis selama implementasi | Tambahan baru | Bab IV (Saran) atau lampiran |

---

## 1. Tiga metode threshold diganti satu metode Adaptif

**Di laporan:** ada tiga metode threshold yang bisa dipilih pengguna, yaitu Statistik (μ~noise~ + 3σ~noise~, Persamaan 3.3) sebagai bawaan, serta Dual threshold (3.4 sampai 3.6) dan Midpoint (3.7) sebagai alternatif. Noise floor diambil dari rata-rata 10% frame terpelan, dan threshold atas dikunci maksimal -20 dBFS.

**Di aplikasi:** hanya ada **satu metode, yaitu threshold Adaptif**, yang bekerja otomatis. Dropdown "Metode threshold" dihapus dari antarmuka. Midpoint dan Dual threshold tidak lagi menjadi fitur, tetapi dipertahankan di `evaluate.py` sebagai **metode pembanding** untuk evaluasi.

**Cara kerja metode Adaptif:**

1. Frame hening digital (energi -100 dB, misalnya mic di-mute) diabaikan.
2. **Noise floor** = median dari 5% frame terpelan, dan sebaran derau = simpangan baku robust (1,4826 × MAD).
3. **Threshold atas** = noise floor + maks(6 dB, 3 × sebaran), dibatasi 10 dB di bawah level ucapan (persentil ke-90 energi). Batas bawah noise floor + 6 dB selalu menang.
4. **Threshold bawah** = min(threshold atas - 3 dB, noise floor + 6 dB). Histeresisnya lebar, jadi ekor kata yang meluruh tetap dipertahankan.
5. **Filter blip lemah:** suara terisolasi yang lebih pendek dari 0,6 detik dan puncaknya lebih dari 25 dB di bawah level ucapan dibuang, karena itu napas atau gesekan mic.

**Alasan dan bukti (benchmark sintetis, `python evaluate.py synth`):**

Korpus disusun dari 24 kalimat text-to-speech (2 suara) dengan jeda yang disisipkan sendiri, sehingga posisi ucapan dan jeda diketahui tepat. Ada 20 kondisi rekaman:
- bersih,
- derau pink, putih, dan brown (SNR 30, 20, dan 10 dB),
- dengung listrik,
- pembicara jauh dari mic,
- volume ucapan berubah-ubah (12 dan 18 dB),
- rekaman padat, jarang, atau tanpa jeda awal,
- napas dan klik di dalam jeda,
- gema ruangan,
- hening digital,
- orang lain bicara di latar.

**Aksi tinjau** = jumlah koreksi manual yang dibutuhkan pengguna: ucapan yang ikut terpotong lebih dari 30 ms, ditambah jeda panjang (0,8 detik atau lebih) yang kurang dari separuhnya terpotong.

| Metode | Aksi tinjau | Ucapan terpotong | Jeda terlewat | SCR | F1 |
|--------|-------------|------------------|---------------|-----|----|
| **Adaptif (JedaCut)** | **112** | **55** | 57 | **0,21%** | 0,943 |
| Midpoint (rancangan awal) | 314 | 287 | 27 | 1,34% | 0,950 |
| Dual threshold (rancangan awal) | 456 | 439 | 17 | 4,85% | 0,936 |
| Statistik (rancangan awal) | 204 | 138 | 66 | 1,71% | - |
| FFmpeg silencedetect (R5) | 735 | 116 | 619 | 0,73% | 0,873 |
| RMS ambang tetap (R4) | 841 | 130 | 711 | 0,71% | 0,862 |
| Statistik sampel awal (R2) | 1707 | 1664 | 43 | 37,4% | 0,758 |

Angka di atas berasal dari 80 klip (1.920 ucapan, 806 jeda panjang). Uji ulang dengan seed lain (120 klip) memberi pola yang sama: Adaptif 197 aksi, Midpoint 539, dan Dual 712.

Temuan penting dari uji ini:
- Midpoint dan Dual meletakkan ambang terlalu tinggi, sehingga suku kata pelan di awal dan akhir kalimat ikut terpotong. Dual paling buruk hampir di semua kondisi.
- Metode Statistik asli gagal total pada rekaman dengan hening digital (74 kalimat terpotong). Ini sama dengan kegagalan pada video nyata a025a9, yang hanya tersisa 2 sampai 6%.
- Batas tetap -20 dBFS membuat ucapan pelan terpotong pada video nyata yang padat ucapan (053068, 5d7ed4, 731064 hanya tersisa 77 sampai 95%).
- Satu-satunya kondisi di mana Midpoint dan Dual lebih baik adalah "orang lain bicara di latar". Kondisi ini di luar batasan masalah (1.5 no. 3).

**Bagian laporan yang perlu direvisi:**

- **Tabel 2.4 no. 2 sampai 5**: keputusannya disesuaikan menjadi "noise floor robust dari 5% frame terpelan, threshold atas = noise floor + margin adaptif, dibatasi relatif terhadap level ucapan". R1, R2, dan R4 tetap dirujuk sebagai sumber ide (ambang ganda, batas 3σ, ambang di antara diam dan ucapan).
- **Gambar 3.1, kotak 5**: "statistik / dual threshold / midpoint" diganti menjadi "noise floor robust + threshold adaptif".
- **3.2.5**: ditulis ulang. Usulan teks ada di bawah.
- **3.2.6**: threshold bawah sekarang min(atas - 3 dB, noise floor + 6 dB), bukan "3 dB di bawah threshold atas". Kalimat tentang T~1~/T~2~ untuk dual threshold dihapus.
- **3.2.8**: tambahkan aturan filter blip lemah (pendek di bawah 0,6 detik dan lebih dari 25 dB di bawah level ucapan).
- **3.2.9, contoh EDL**: hapus `"threshold_method": "stat"`.
- **Tabel 3.2**:
  - Baris Metode threshold diganti "Adaptif (otomatis), tidak bisa dipilih".
  - Baris k (pengali σ) dihapus.
  - Selisih histeresis menjadi "min(atas - 3 dB, noise floor + 6 dB)".
  - Tambah baris "Filter blip lemah: 0,6 detik dan 25 dB".
- **Gambar 3.3**: dropdown Metode threshold dihapus.
- **3.4**: Midpoint dan Dual threshold ditambahkan sebagai metode pembanding, dan metrik aksi tinjau ditambahkan (lihat bagian 14).
- **4.1 Kesimpulan no. 1**: diganti dengan metode Adaptif beserta angka benchmark di atas.

**Usulan teks pengganti untuk 3.2.5:**

> Ambang tidak ditentukan dengan satu angka tetap, karena setiap rekaman punya tingkat derau yang berbeda. *Frame* yang benar-benar hening secara digital (misalnya saat mikrofon dimatikan) diabaikan, lalu *noise floor* diperkirakan dari median 5% *frame* terpelan. Persentil kecil dan median dipilih karena tetap mewakili derau walaupun rekaman hampir tanpa jeda, kondisi di mana 10% *frame* terpelan masih berisi ucapan pelan. Sebaran derau dihitung dengan simpangan baku robust (1,4826 × MAD). *Threshold* atas adalah *noise floor* ditambah margin, yaitu nilai terbesar antara 6 dB dan tiga kali sebaran derau, mengikuti batas 3σ pada R1 dan R2. *Threshold* ini dibatasi paling tinggi 10 dB di bawah level ucapan (persentil ke-90 energi) agar ucapan pelan tidak ikut terpotong, tetapi tidak pernah lebih rendah dari *noise floor* + 6 dB agar jeda tetap terpotong pada rekaman yang bising. Rancangan awal menyediakan tiga metode (statistik, *dual threshold*, dan *midpoint*). Namun pada pengujian 20 kondisi rekaman, metode adaptif ini membutuhkan 112 koreksi manual, dibandingkan 314 untuk *midpoint* dan 456 untuk *dual threshold*. Karena itu aplikasi memakai satu metode adaptif, sedangkan *midpoint* dan *dual threshold* dipakai sebagai pembanding pada evaluasi.

**Catatan:** subbab 2.2.1, 2.2.2, dan 2.2.4 tetap boleh membahas R1, R2, dan R4 sebagai tinjauan literatur. Yang berubah adalah keputusan rancangannya.

---

## 2. Crossfade video dihapus

**Di laporan:** pengguna bisa menyalakan crossfade video 3 frame (maksimal 4 frame, mengacu H = 4 pada Wang dkk., 2024).

**Di aplikasi:** fitur ini dihapus. Transisi di titik potong hanya memakai fade audio 15 ms (lihat nomor 7).

**Alasan:** fitur ini nonaktif secara bawaan sehingga tidak memengaruhi hasil normal, dan kode render menjadi lebih sederhana (hanya trim + concat).

**Bagian laporan yang perlu direvisi:**

- **2.2.3, paragraf terakhir**: "berupa crossfade audio yang singkat dan crossfade video opsional beberapa frame" diganti menjadi "berupa crossfade audio yang singkat".
- **Tabel 2.4 no. 12**: keputusan "Crossfade audio 15 ms, crossfade video opsional" diganti menjadi "Crossfade audio 15 ms".
- **3.2.10, paragraf kedua**: kalimat "Pengguna juga bisa menyalakan crossfade video 3 frame ... tanpa menambah durasi" dihapus.
- **Tabel 3.2**: baris Crossfade video dihapus.
- **3.3.3 Layar Unggah**: "crossfade video" dihapus dari daftar Pengaturan lanjutan.
- **Gambar 3.3**: checkbox "Crossfade video" dihapus.
- **4.2 Saran no. 3** (transisi visual) tetap relevan dan bisa dipertahankan sebagai pengembangan lanjutan.

---

## 3. Tombol Ekspor EDL dihapus

**Di laporan:** EDL bisa diekspor (tombol Ekspor EDL di layar Tinjau) lalu dipakai untuk render ulang kapan saja.

**Di aplikasi:** tombol Ekspor EDL (.json) dan (.csv) dihapus agar layar Tinjau fokus pada alur utama. EDL tetap dibuat, disimpan di memori server selama sesi berjalan (tidak ditulis ke file), bisa diubah lewat tabel Daftar Potongan, dan dipakai saat render.

**Bagian laporan yang perlu direvisi:**

- **3.2.9**: kalimat "EDL juga bisa diekspor, lalu dipakai untuk render ulang kapan saja" diganti, misalnya "EDL disimpan di server sehingga render ulang bisa dilakukan tanpa mengulang analisis".
- **3.3.3 Layar Tinjau**: "serta tombol Ekspor EDL dan Render Video" diganti menjadi "serta tombol Kembali ke pengaturan dan Render Video".
- **Gambar 3.4**: tombol "Ekspor EDL (.json)" dan "Ekspor EDL (.csv)" dihapus dari wireframe.

---

## 4. Vue Router dan Pinia tidak dipakai

**Di laporan:** perpindahan layar diatur Vue Router, dan data bersama disimpan di Pinia.

**Di aplikasi:** antarmuka memakai **Vue 3 + Vite saja**. Data bersama (info file, pengaturan trim, EDL, data timeline) disimpan dalam satu objek reaktif (`reactive()`) di `store.js`. Perpindahan layar diatur dengan nilai `step` (1 Unggah, 2 Tinjau, 3 Ekspor).

**Alasan:** aplikasi hanya punya tiga layar berurutan, sehingga Router dan Pinia menambah dependency tanpa manfaat berarti. Data tetap tidak hilang saat berpindah layar.

**Bagian laporan yang perlu direvisi:**

- **3.3.2, paragraf kedua**: kalimat tentang Vue Router dan Pinia diganti.
- **Tabel 3.3, baris EdlTable**: "langsung disimpan ke EDL di Pinia" diganti menjadi "langsung disimpan ke EDL di state bersama".

**Usulan teks pengganti untuk 3.3.2 (paragraf kedua):**

> Proyek Vue dibuat dengan Vite, yaitu alat untuk menjalankan dan membangun aplikasi Vue. Karena aplikasi hanya terdiri dari tiga layar yang berurutan, perpindahan antara layar Unggah, Tinjau, dan Ekspor cukup diatur dengan satu variabel langkah, tanpa Vue Router. Data yang dipakai bersama oleh ketiga layar, seperti informasi file, pengaturan *trim*, dan EDL, disimpan dalam satu objek reaktif bawaan Vue (`reactive`), tanpa Pinia. Dengan cara ini data tidak hilang saat pengguna berpindah layar, dan jumlah *dependency* tetap sedikit.

---

## 5. Komponen DropZone dan VideoPreview digabung

**Di laporan (Tabel 3.3):** UploadView + DropZone, ReviewView + VideoPreview.

**Di aplikasi:** area tarik dan lepas file ada langsung di `UploadView`, dan pemutar video ada langsung di `ReviewView`. Komponen terpisah yang ada adalah `TrimSettings`, `EdlTable`, dan `AudioTimeline`.

**Revisi Tabel 3.3:** kolom Komponen menjadi `UploadView`, `TrimSettings`, `ReviewView`, `EdlTable`, `AudioTimeline`, `ExportView`.

---

## 6. Render per bagian diwujudkan dengan input yang di-seek

**Di laporan (3.2.10, kalimat terakhir):** "Untuk video yang sangat panjang dengan ratusan potongan, render dilakukan per bagian lalu digabung, agar perintah FFmpeg tidak terlalu besar."

**Di aplikasi:** prinsip render per bagian tetap dipakai, tetapi dalam **satu proses FFmpeg**:
- Bagian yang dipertahankan dikelompokkan, 20 bagian per kelompok dengan maksimal 25 kelompok.
- Tiap kelompok membaca file sumber sebagai input tersendiri yang di-seek (`-ss`/`-t`) hanya ke rentangnya.
- Semua bagian lalu digabung dengan filter concat.
- Susunan filter ditulis ke file dan dibaca dengan `-/filter_complex <file>`, supaya perintah tidak melebihi batas panjang command line.

**Alasan dan bukti:** kalau semua trim membaca satu input, setiap frame dikirim ke ratusan filter trim sekaligus, sehingga beban naik kuadratik terhadap durasi. Pengukuran pada video 30 menit dengan 390 bagian:

| Cara render | Kecepatan | Waktu ekspor |
|-------------|-----------|--------------|
| Satu input untuk semua trim | 0,51× realtime | sekitar 34 menit |
| Per kelompok dengan input di-seek | 6,3× realtime (libx264) | 91 detik (h264_nvenc) |

Audio dan video tetap sinkron (selisih 33 ms, sekitar 1 frame). `-ss` sebagai opsi input dengan re-encode tetap akurat per frame.

**Revisi 3.2.10:** kalimat terakhir diganti, misalnya:

> Untuk video panjang dengan ratusan potongan, bagian yang dipertahankan dikelompokkan, dan tiap kelompok membaca video sumber hanya pada rentangnya (*input seeking*). Dengan cara ini setiap *frame* hanya diproses oleh filter milik kelompoknya, sehingga waktu ekspor video 30 menit turun dari sekitar 34 menit menjadi kurang dari 2 menit.

**Catatan teknis:** opsi `-/filter_complex` membutuhkan FFmpeg versi 7.0 atau lebih baru. Opsi lama `-filter_complex_script` sudah dihapus di FFmpeg 9.

---

## 7. Crossfade audio diwujudkan sebagai fade out + fade in 15 ms

**Di laporan:** "Di setiap titik potong diberi crossfade audio 15 ms."

**Di aplikasi:** setiap segmen yang dipertahankan diberi **fade in 15 ms di awal dan fade out 15 ms di akhir**. Audio dari dua segmen tidak ditumpuk (overlap).

**Alasan:** crossfade yang menumpuk memendekkan audio 15 ms di setiap potongan, sedangkan videonya tidak ikut memendek. Dengan 100 potongan, audio akan lebih cepat 1,5 detik dari video. Fade out + fade in tetap mencegah bunyi klik tanpa mengubah durasi, sehingga audio dan video tetap sinkron (selisih hasil uji 3 sampai 30 ms, sekitar 1 frame).

**Revisi 3.2.10:** tambahkan penjelasan bahwa crossfade diwujudkan sebagai fade out dan fade in singkat di kedua sisi titik potong, beserta alasannya. Istilah "crossfade" di antarmuka dan Tabel 3.5 tetap boleh dipakai.

**Gambar 3.1, kotak 10:** "trim + concat, crossfade, re-encode" bisa diganti menjadi "trim + concat, fade audio 15 ms, re-encode".

---

## 8. Ekstraksi audio langsung ke memori

**Di laporan (3.2.1):** audio diambil dengan FFmpeg lalu diubah menjadi WAV mono 16 kHz.

**Di aplikasi:** FFmpeg mengeluarkan audio mono 16 kHz 16-bit (PCM) langsung ke program Python lewat *pipe*, tanpa menulis file WAV sementara. Format sinyalnya sama, hanya tidak disimpan sebagai file.

**Revisi:** 3.2.1 dan Gambar 3.1 kotak 1 ("WAV mono 16 kHz") bisa diganti menjadi "PCM mono 16 kHz". Kalau ingin, cukup tambahkan satu kalimat penjelasan.

**Tambahan kecil:** cover art pada file MP3 (yang terbaca sebagai stream video) diabaikan, dan audio yang lebih pendek dari 0,5 detik ditolak dengan pesan kesalahan.

---

## 9. Encoder Otomatis

**Di laporan:** video di-encode dengan h264_nvenc jika ada GPU NVIDIA, atau libx264 CRF 20 jika tidak ada.

**Di aplikasi:**

- Pilihan encoder ada tiga: **Otomatis** (bawaan), `h264_nvenc`, dan `libx264 (CRF 20)`.
- Mode Otomatis tidak hanya melihat apakah ada GPU NVIDIA, tetapi **mencoba encode singkat dengan h264_nvenc**. Kalau gagal (misalnya versi driver tidak cocok), aplikasi otomatis memakai libx264.
- Output diberi format piksel `yuv420p` agar bisa diputar di semua browser, dan `faststart` agar video bisa mulai diputar sebelum selesai diunduh.

**Temuan:** pada laptop pengembang (RTX 4060), h264_nvenc gagal karena FFmpeg 9 membutuhkan driver NVIDIA versi 610 atau lebih baru, sehingga render berjalan dengan libx264.

**Revisi:** Tabel 3.2 baris Encoder (nilai bawaan "Otomatis: h264_nvenc jika bisa dipakai, selain itu libx264 CRF 20"), 3.2.10, dan Gambar 3.3 (dropdown encoder menampilkan "Otomatis").

---

## 10. Segmen Pertahankan yang bersebelahan digabung

**Di aplikasi:** jika pengguna mengubah segmen Potong di antara dua segmen Pertahankan menjadi Pertahankan, ketiganya digabung menjadi satu rentang sebelum render. Dengan begitu tidak ada fade audio yang tidak perlu di tengah ucapan.

**Revisi (opsional):** tambahkan satu kalimat di 3.2.9 atau 3.2.10.

---

## 11. Perubahan REST API

**Di aplikasi (dibanding Tabel 3.4):**

- **Endpoint tambahan** `GET /api/defaults`: mengirim nilai preset Default dari server, supaya nilai bawaan hanya ditulis di satu tempat.
- **Endpoint tambahan** `POST /api/cancel/{id}`: menghentikan render yang sedang berjalan dan membuang file setengah jadi. Pengguna kembali ke layar Periksa lalu bisa render ulang.
- `PUT /api/edl/{id}` juga menolak segmen yang tidak urut atau tumpang tindih, karena bagian yang tumpang tindih akan ter-render dua kali.
- **Preview video asli** di layar Tinjau memakai file langsung dari browser (object URL), jadi tidak butuh endpoint untuk mengambil video asli dari server.
- EDL dikirim ke server (`PUT /api/edl/{id}`) tepat sebelum render, bukan setiap kali ada perubahan.
- Input dari pengguna divalidasi di server: format file, ada tidaknya audio, rentang nilai pengaturan, dan validitas segmen EDL.

**Revisi:** tambahkan baris `GET /api/defaults` dan `POST /api/cancel/{id}` di Tabel 3.4.

---

## 12. Penyesuaian tampilan

Perubahan pada antarmuka dibanding wireframe:

- **Timeline Audio:** label nilai garis threshold atas, threshold bawah, dan noise floor ditampilkan di legenda di bawah grafik, bukan di dalam grafik. Ini agar label tidak saling tumpuk di layar sempit.
- **Preview Hasil tanpa render:** mode Hasil memutar video asli sambil melompati segmen Potong secara langsung, sehingga pengguna bisa mendengar hasil potongan sebelum render.
- **Tombol Kembali ke pengaturan:** dibuat sebagai tombol, bukan tautan teks, agar lebih jelas.
- **Responsive HP:** tampilan menyesuaikan layar HP (lebar sekitar 375 px).
  - Header hanya menampilkan logo.
  - Kolom ditumpuk menjadi satu.
  - Tombol dibuat selebar layar.
  - Tabel EDL dipadatkan.
- **Tema gelap** sudah diterapkan sesuai rencana high-fidelity di 3.3.3.
- **Pengaturan lanjutan tertutup secara bawaan**, karena nilai Default sudah teruji dan pengguna tidak perlu mengatur apa pun. Kartu "Mode: Trim jeda otomatis" dibuat sebagai info statis, bukan kotak bergaris putus-putus yang terlihat seperti tombol.
- **Bilah aksi menempel** (desktop): tombol Kembali dan Render Video selalu terlihat di bawah layar Tinjau, jadi pengguna tidak perlu scroll ke dasar halaman.
- **Aksesibilitas WCAG 2.1 AA** (diaudit dengan skill design: accessibility-review dan design-critique):
  - **Kontras warna:** tombol utama `#2563eb` (5,2:1), teks potong `#f87171` (6,1:1), dan garis tepi kontrol `#6b7386` (minimal 3:1). Sebelumnya tombol 3,2:1 dan garis tepi 1,5:1.
  - **Keyboard:** area unggah bisa dibuka dengan Tab lalu Enter, waktu mulai di tabel EDL berupa tombol untuk melompat ke segmen, dan cincin fokus terlihat di semua kontrol.
  - **Pembaca layar:** label form terhubung ke inputnya, tombol ikon dan dropdown tabel diberi nama, error diumumkan (`role="alert"`), dan progres unggah/render memakai `role="progressbar"`.
  - **Target sentuh** minimal 44 px di layar sentuh, dan animasi dimatikan untuk pengguna yang memilih "kurangi gerakan".

- **Video portrait (HP):** kotak video dikunci 16:9 dengan bingkai hitam (`object-fit: contain`), seperti monitor preview editor video, jadi video portrait tidak memanjang dan timeline tetap dekat. Di HP tinggi video dibatasi 40% layar, urutannya video, timeline, lalu tabel, dan preview menempel di atas saat digulir.
- **Bahasa yang lebih mudah dipahami** (diulas dengan skill design: ux-copy):
  - Langkah 2 "Tinjau" menjadi **"Periksa"**, dan judulnya **"Periksa Hasil Potongan"**.
  - Ringkasan memakai kalimat biasa, misalnya "Video jadi lebih singkat 22 menit 4 detik. 45 menit 3 detik → 22 menit 59 detik · 391 jeda dihapus", dengan kartu "Waktu dihemat".
  - Proses render ditulis "Menyusun video... Jeda sedang dihapus dan video disusun ulang", tanpa kata FFmpeg atau encode, dengan perkiraan sisa waktu dan tombol **Batalkan**.
  - Hasil akhir ditulis "Video siap". Pesan gagal menjelaskan cara mengatasinya, dan detail teknis disembunyikan di bagian "Detail teknis".
  - "Daftar Potongan (EDL)" menjadi "Daftar Potongan". Istilah EDL tetap dipakai di laporan dan kode.
- **Celah yang ditutup** (diulas dengan skill design: design-critique):
  - Render bisa dibatalkan.
  - Ganti file saat unggahan belum selesai tidak lagi membuat video yang salah ikut dianalisis.
  - Ada petunjuk saat slider diubah tetapi belum dianalisis ulang.
  - Muncul konfirmasi sebelum "Analisis ulang" menimpa perubahan manual.
  - Muncul peringatan browser sebelum halaman ditutup atau di-refresh.
  - Ada pesan jelas untuk file yang terlalu besar dan format yang salah. Format dicek sebelum file diunggah.
  - Filter "Hanya yang dipotong" untuk video panjang dengan ratusan baris.
  - Pesan server tidak aktif disertai tombol "Coba lagi".

**Revisi:**

- **3.3.3:** tambahkan paragraf tentang tampilan responsive untuk HP dan pemenuhan WCAG 2.1 AA (kontras, keyboard, label, target sentuh).
- **Gambar 3.3:** Pengaturan lanjutan dalam keadaan tertutup, tanpa dropdown Metode threshold dan tanpa checkbox Crossfade video.
- **Gambar 3.4:** sesuaikan dengan legenda threshold, tombol Kembali, bilah aksi di bawah, dan tanpa tombol Ekspor EDL.

---

## 13. Arsitektur deploy (belum ada di laporan)

**Di aplikasi:**

- **Frontend** di-deploy ke **Vercel**.
- **Backend (FastAPI + FFmpeg)** berjalan di **laptop sendiri** dan dibuka ke internet lewat **Cloudflare Tunnel**.
- Frontend memanggil backend lewat alamat yang diatur di variabel `VITE_API_URL`.
- Backend membatasi domain yang boleh mengakses lewat variabel `CORS_ORIGINS`.

**Alasan memilih cara ini:**

| Pilihan | Masalah |
|---------|---------|
| Backend di Vercel | Batas upload 4,5 MB, durasi maksimal 300 detik (paket Hobby), FFmpeg tidak tersedia, instance tanpa state |
| Hugging Face Spaces (Docker) | Sekarang membutuhkan paket berbayar (PRO) |
| Render (paket gratis) | 0,1 CPU dan 512 MB RAM, sedangkan analisis butuh sekitar 45 MB RAM per menit audio |

**Keterbatasan:**

- Laptop harus menyala selama aplikasi dipakai.
- Alamat tunnel berubah setiap kali dijalankan ulang.
- Upload lewat Cloudflare gratis maksimal 100 MB per file.

**Revisi:** tambahkan penjelasan deploy di 3.3.1. Gambar 3.2 juga bisa diperbarui: Antarmuka web (Vercel), lalu Cloudflare Tunnel, lalu Server di laptop. `Dockerfile` untuk Hugging Face Spaces sempat dibuat, tetapi sudah dihapus karena tidak dipakai. File itu masih bisa diambil dari riwayat git kalau nanti memakai paket berbayar.

---

## 14. Script evaluasi (3.4)

**Di aplikasi:** `backend/evaluate.py` sudah dibuat sesuai rencana evaluasi.

**Yang sudah sesuai dengan laporan:**

- Metrik: Precision, Recall, F1, Speech Clipping Rate, Silence Removal Rate (jeda ≥ 0,5 detik), rasio durasi, dan Real-Time Factor (analisis dan render dihitung terpisah).
- Penambahan derau putih atau derau nyata (dari file) pada SNR 30, 20, dan 10 dB.
- Pembanding: FFmpeg silencedetect -40 dB dengan durasi 0,5 detik (R5), statistik sampel awal dengan voting 10 ms (R2), dan RMS ambang tetap per 100 ms (R4). **Ditambah** Midpoint dan Dual threshold dari rancangan awal.
- Uji ablasi: tanpa ZCR rescue, tanpa smoothing, tanpa padding, dan **tanpa filter blip lemah**.

**Tambahan baru:**

- **Metrik aksi tinjau** = ucapan yang ikut terpotong lebih dari 30 ms, ditambah jeda panjang (0,8 detik atau lebih) yang kurang dari separuhnya terpotong. Metrik ini langsung mengukur tujuan "minim peninjauan" dan juga dihitung untuk data asli berlabel Audacity.
- **Benchmark sintetis** `python evaluate.py synth <folder-kalimat>`: 20 kondisi rekaman dengan ground truth pasti. Kalimat bersih dibuat dengan `make_sentences.ps1` (text-to-speech Windows) atau rekaman sendiri. Hasilnya ada di bagian 1.
- **Hasil ablasi (benchmark sintetis):**
  - Padding paling penting: tanpa padding aksi tinjau naik dari 112 menjadi 415.
  - Filter blip memangkas 15 aksi (127 menjadi 112).
  - ZCR rescue memangkas 4 aksi.
  - Smoothing tidak membantu pada suara sintetis (109 vs 112), tetapi tetap dipakai karena label pada rekaman asli lebih berkedip.
- **Catatan target Tabel 3.6:** F1 0,943 (target 0,90 atau lebih) dan SCR 0,21% (target 1% atau kurang) terpenuhi. SRR 78% belum memenuhi target 90%, karena padding 0,35 detik per jeda memang sengaja dipertahankan (jeda 1 detik paling banyak hanya bisa terpotong 65%). Sebaiknya SRR didefinisikan ulang di luar wilayah padding, atau memakai metrik jeda terlewat.
- Uji subjektif: paired t-test, atau Wilcoxon jika selisih skor tidak normal (diuji dengan Shapiro-Wilk), pada α = 0,05.

**Keputusan teknis yang perlu ditulis di 3.4:**

- Label acuan memakai label track Audacity dengan resolusi 10 ms, dan setiap region dianggap suara.
- Daya sinyal untuk menghitung SNR diambil dari bagian ucapan saja (sesuai label), bukan dari seluruh rekaman.
- Metrik JedaCut dihitung dari EDL akhir (sesudah padding), karena itulah yang benar-benar dipertahankan di video hasil. Konsekuensinya, Precision JedaCut akan sedikit lebih rendah karena padding.
- Metrik dijumlahkan antarklip dulu baru dihitung (micro-average).
- **Pembanding auto-editor tidak diotomatisasi** dan dijalankan terpisah, karena merupakan aplikasi eksternal.
- Ambang tetap R4 memakai nilai 0,001135 dari makalahnya.

---

## 15. Temuan teknis selama implementasi

Temuan ini bisa dimasukkan ke Bab IV (Saran) atau lampiran:

1. **Batas tetap -20 dBFS sudah diganti** batas yang mengikuti level ucapan rekaman (lihat bagian 1), karena batas tetap memotong ucapan pelan pada video padat ucapan.
2. **Kebutuhan memori analisis** sekitar 45 MB per menit audio (diukur: tambahan sekitar 212 MB untuk 5 menit, 463 MB untuk 10 menit, dan 906 MB untuk 20 menit), karena seluruh audio diproses sekaligus di memori. Untuk video yang sangat panjang atau server kecil, analisis perlu dibuat per bagian.
3. **Kompatibilitas FFmpeg:** opsi `-/filter_complex` butuh FFmpeg 7.0 atau lebih baru, dan h264_nvenc di FFmpeg 9 butuh driver NVIDIA 610 atau lebih baru.
4. **Uji fungsional (bukan evaluasi formal):** video uji 28,2 detik berisi ucapan text-to-speech dengan jeda turun menjadi 15,95 detik. Audio dan video tetap sinkron. Pada laptop pengembang, RTF analisis sekitar 0,0025 dan RTF render sekitar 0,024. Angka ini bukan hasil evaluasi subbab 3.4 dan sebaiknya tidak dilaporkan sebagai hasil pengujian.
5. **Keterbatasan yang tersisa:** suara orang lain di latar (diskusi, keramaian) masih membuat jeda tidak terpotong, karena energinya setara ucapan. Ini sesuai batasan masalah dan bisa diatasi dengan VAD berbasis model (4.2 Saran no. 4).

---

## Bagian laporan yang tidak berubah

Bagian berikut tetap sesuai dengan aplikasi dan tidak perlu direvisi:

- Pra-proses: high-pass 80 Hz dan band-pass 300 sampai 3400 Hz, Butterworth orde 4, dijalankan dua arah, lalu dinormalisasi (3.2.2).
- Framing: frame 20 ms, hop 10 ms, jendela Hann (3.2.3).
- Fitur energi dB dan ZCR, Persamaan (3.1) dan (3.2) (3.2.4).
- Prinsip histeresis dua ambang dan ZCR rescue dengan batas μ~Z~ + 2σ~Z~ (3.2.6). Nilai ambangnya berubah, lihat bagian 1.
- Smoothing median 5 frame (3.2.7).
- Aturan segmen: jeda minimum 0,5 detik, suara minimum 0,15 detik, padding 0,15 dan 0,20 detik, penggabungan, serta batas file (3.2.8). Ditambah filter blip lemah, lihat bagian 1.
- EDL berformat JSON dengan aksi Pertahankan dan Potong (3.2.9).
- Render ulang dengan trim, atrim, dan concat, libx264 CRF 20, audio AAC 192 kb/s (3.2.10).
- Tiga layar Unggah, Tinjau, dan Ekspor, preset Default dan "Diubah", serta istilah asing yang dipertahankan (3.3.3, Tabel 3.5).
- Nama file hasil `nama_berkas_jumpcut.mp4` sesuai wireframe.
