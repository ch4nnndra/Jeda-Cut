# JedaCut

Aplikasi web pemotong jeda otomatis pada video menggunakan Short-Time Energy dan Zero Crossing Rate.

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
