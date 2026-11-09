# JedaCut

Aplikasi web pemotong jeda otomatis pada video menggunakan Short-Time Energy dan Zero Crossing Rate.
Implementasi dari Laporan Perancangan JedaCut (Bab III).

## Kebutuhan

- Python 3.9+
- Node.js 18+
- FFmpeg (ffmpeg dan ffprobe ada di PATH). Windows: `winget install Gyan.FFmpeg`

## Menjalankan

Backend (FastAPI, port 8000):

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Frontend, mode development (Vite, port 5173, request `/api` diteruskan ke port 8000):

```bash
cd frontend
npm install
npm run dev
```

Atau build sekali, lalu cukup buka http://localhost:8000 dari backend:

```bash
cd frontend
npm run build
```

## Struktur

```
backend/
  analysis.py       ekstraksi audio, pra-proses, framing, fitur, threshold, histeresis, smoothing, aturan segmen, EDL (3.2.1 - 3.2.9)
  render.py         render EDL ke MP4 dengan FFmpeg, fade/crossfade, pilih encoder (3.2.10)
  main.py           REST API (Tabel 3.4)
  evaluate.py       evaluasi objektif dan subjektif (3.4)
  test_analysis.py  self-check deteksi dan render graph
frontend/src/
  store.js          state bersama dan pemanggil API
  App.vue           header langkah dan tema
  views/            UploadView, ReviewView, ExportView (layar Unggah, Tinjau, Ekspor)
  components/       TrimSettings, EdlTable, AudioTimeline
```

## Evaluasi

Label acuan dibuat di Audacity (label track, setiap region = suara), lalu diekspor sebagai `.txt`
dengan nama yang sama seperti file medianya (`klip1.mp4` dan `klip1.txt`).

```bash
cd backend
python evaluate.py detect data/*.mp4 --snr 30 20 10 --render --csv hasil.csv
python evaluate.py detect data/*.mp4 --snr 30 20 10 --noise kipas.wav
python evaluate.py likert responses.csv
```

Metode yang dibandingkan: JedaCut, ablasi (tanpa ZCR rescue, tanpa smoothing, tanpa padding),
FFmpeg silencedetect -40 dB (R5), statistik sampel awal (R2), dan RMS ambang tetap (R4).
auto-editor dijalankan terpisah karena merupakan aplikasi eksternal.

Format `responses.csv` untuk uji Likert dan kuis (satu baris per responden per aspek):

```
aspect,original,result
clarity,4,5
quiz,3,3
```

## Catatan

- Encoder `auto` memakai h264_nvenc jika GPU NVIDIA dan driver-nya mendukung, selain itu libx264 CRF 20.
  FFmpeg 9 butuh driver NVIDIA 610 atau lebih baru untuk h264_nvenc.
- File unggahan disimpan sementara di `backend/storage/` dan dihapus setiap server dijalankan ulang.
- Test: `cd backend && python test_analysis.py`
