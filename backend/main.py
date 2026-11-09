"""Server REST API JedaCut (Tabel 3.4). Jalankan: python main.py"""
import json
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import List, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import analysis
import render
from analysis import TrimParams

STORAGE = Path(__file__).parent / "storage"
ALLOWED = {".mp4", ".mkv", ".mov", ".webm", ".wav", ".mp3"}

# File hanya disimpan sementara selama proses (3.3.1), jadi dibersihkan tiap server start.
shutil.rmtree(STORAGE, ignore_errors=True)
STORAGE.mkdir()

# ponytail: job disimpan di memori, hilang saat server restart. Pakai database jika butuh multi-user.
jobs = {}

app = FastAPI(title="JedaCut")


class Segment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    action: Literal["keep", "cut"]


class Edl(BaseModel):
    source: str
    params: TrimParams
    segments: List[Segment]


def get_job(jid):
    if jid not in jobs:
        raise HTTPException(404, "ID tidak ditemukan, silakan unggah ulang")
    return jobs[jid]


def save_edl(job, edl):
    job["edl"] = edl
    (job["dir"] / "edl.json").write_text(json.dumps(edl, indent=2), encoding="utf-8")


@app.get("/api/defaults")
def defaults():
    """Nilai preset Default (Tabel 3.2), satu sumber untuk server dan antarmuka."""
    return TrimParams().model_dump()


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "Format tidak didukung. Gunakan MP4, MKV, MOV, WEBM, WAV, atau MP3")

    jid = uuid.uuid4().hex[:12]
    folder = STORAGE / jid
    folder.mkdir()
    src = folder / f"source{ext}"
    with src.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        info = analysis.probe(src)
    except (subprocess.CalledProcessError, KeyError, ValueError):
        info = None
    if not info or not info["has_audio"]:
        shutil.rmtree(folder, ignore_errors=True)
        msg = "File tidak bisa dibaca" if not info else "File tidak memiliki audio, deteksi jeda tidak bisa dilakukan"
        raise HTTPException(400, msg)

    jobs[jid] = {"dir": folder, "src": src, "name": file.filename, "size": src.stat().st_size,
                 "info": info, "status": "idle", "progress": 0}
    return {"id": jid, "name": file.filename, "size": jobs[jid]["size"], **info}


@app.post("/api/analyze/{jid}")
def analyze(jid: str, params: TrimParams):
    job = get_job(jid)
    p = params.model_dump()
    try:
        result = analysis.analyze(job["src"], job["info"]["duration"], p)
    except ValueError as e:
        raise HTTPException(400, str(e))
    edl = {"source": job["name"], "params": p, "segments": result["segments"]}
    save_edl(job, edl)
    return {"edl": edl, "timeline": result["timeline"]}


@app.put("/api/edl/{jid}")
def update_edl(jid: str, edl: Edl):
    job = get_job(jid)
    limit = job["info"]["duration"] + 0.01
    if any(s.start >= s.end or s.end > limit for s in edl.segments):
        raise HTTPException(400, "Segmen EDL tidak valid")
    save_edl(job, edl.model_dump())
    return {"ok": True}


def run_render(job):
    out = job["dir"] / "output.mp4"
    try:
        encoder = render.render(job["src"], job["edl"], job["info"], out,
                                lambda pct: job.update(progress=round(pct, 1)))
        job.update(status="done", progress=100, encoder=encoder,
                   out_size=out.stat().st_size, out_duration=analysis.probe(out)["duration"])
    except Exception as e:  # semua error render dikirim ke layar Ekspor
        job.update(status="error", error=str(e))


@app.post("/api/render/{jid}")
def start_render(jid: str):
    job = get_job(jid)
    if "edl" not in job:
        raise HTTPException(400, "Jalankan analisis terlebih dahulu")
    if job["status"] == "rendering":
        raise HTTPException(409, "Render sedang berjalan")
    job.update(status="rendering", progress=0, error=None)
    threading.Thread(target=run_render, args=(job,), daemon=True).start()
    return {"status": "rendering"}


@app.get("/api/status/{jid}")
def status(jid: str):
    job = get_job(jid)
    keys = ("status", "progress", "error", "encoder", "out_size", "out_duration", "size")
    return {k: job.get(k) for k in keys}


@app.get("/api/download/{jid}")
def download(jid: str):
    job = get_job(jid)
    out = job["dir"] / "output.mp4"
    if job["status"] != "done" or not out.exists():
        raise HTTPException(404, "Hasil render belum tersedia")
    return FileResponse(out, media_type="video/mp4", filename=f"{Path(job['name']).stem}_jumpcut.mp4")


# Setelah `npm run build`, antarmuka bisa dilayani langsung dari server ini (satu port).
DIST = Path(__file__).parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
