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
  Dockerfile        image backend untuk Hugging Face Spaces (README.md di folder ini = konfigurasi Space)
frontend/src/
  store.js          state bersama dan pemanggil API
  App.vue           header langkah dan tema
  views/            UploadView, ReviewView, ExportView (layar Unggah, Tinjau, Ekspor)
  components/       TrimSettings, EdlTable, AudioTimeline
```

## Deploy

Frontend di Vercel, backend di Hugging Face Spaces (Docker, CPU Basic gratis: 2 vCPU, 16 GB RAM).
Backend tidak bisa di Vercel karena batas upload 4,5 MB dan render berjalan di background.

### 1. Backend ke Hugging Face Spaces

1. Buat Space baru di https://huggingface.co/new-space, pilih SDK **Docker** (template Blank).
2. Buat access token dengan izin **write** di https://huggingface.co/settings/tokens.
3. Push isi folder `backend/` ke Space (ganti `USERNAME` dan `NAMA-SPACE`). Saat diminta password, isi dengan token tadi.

```bash
git remote add space https://huggingface.co/spaces/USERNAME/NAMA-SPACE
git subtree split --prefix backend -b hf-space
git push --force space hf-space:main
```

Setiap ada perubahan di `backend/`, commit dulu, lalu jalankan ulang dua baris terakhir.
Space akan build otomatis. Alamat backend: `https://USERNAME-NAMA-SPACE.hf.space`.

4. Di Space: **Settings → Variables and secrets → New variable**
   `CORS_ORIGINS` = alamat frontend Vercel, contoh `https://jeda-cut.vercel.app` (pisahkan dengan koma jika lebih dari satu).

### 2. Frontend di Vercel

1. Project Vercel: Root Directory `frontend`, framework Vite.
2. **Settings → Environment Variables**: `VITE_API_URL` = alamat backend, contoh `https://USERNAME-NAMA-SPACE.hf.space`.
3. **Redeploy**. Nilai `VITE_API_URL` dibaca saat build, jadi wajib build ulang setelah diubah.

Catatan: Space gratis tidur setelah 48 jam tidak dipakai dan bangun otomatis saat dibuka (butuh beberapa menit).
File upload di Space hilang setiap restart.
