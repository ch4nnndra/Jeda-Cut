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

Frontend di Vercel, backend berjalan di laptop sendiri dan dibuka ke internet lewat Cloudflare Tunnel (gratis).
Backend tidak bisa di Vercel karena batas upload 4,5 MB dan render berjalan di background.

### 1. Backend di laptop + Cloudflare Tunnel

Pasang cloudflared sekali saja (Windows): `winget install Cloudflare.cloudflared`

Terminal 1, jalankan backend. `CORS_ORIGINS` diisi alamat Vercel (tanpa env ini semua domain diizinkan):

```powershell
$env:CORS_ORIGINS = "https://NAMA-PROJECT.vercel.app"
python backend/main.py
```

Terminal 2, buka tunnel ke backend:

```bash
cloudflared tunnel --url http://localhost:8000
```

Salin alamat `https://xxxx.trycloudflare.com` yang muncul di log. Itu alamat backend.

### 2. Frontend di Vercel

1. Project Vercel: Root Directory `frontend`, framework Vite.
2. **Settings → Environment Variables**: `VITE_API_URL` = alamat tunnel, contoh `https://xxxx.trycloudflare.com`.
3. **Redeploy**. Nilai `VITE_API_URL` dibaca saat build, jadi wajib build ulang setelah diubah.

Catatan:
- Alamat tunnel berubah setiap cloudflared dijalankan ulang, jadi `VITE_API_URL` harus diganti lalu redeploy.
- Laptop harus tetap menyala (jangan sleep) selama aplikasi dipakai.
- Upload lewat Cloudflare gratis maksimal 100 MB per file.
- File upload di `backend/storage/` dihapus setiap backend dijalankan ulang.
- Opsional: `backend/Dockerfile` dan `backend/README.md` siap dipakai untuk Hugging Face Spaces (butuh paket PRO).
