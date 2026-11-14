"""Modul analisis audio JedaCut: file media -> EDL (subbab 3.2.1 sampai 3.2.9)."""
import json
import subprocess
from fractions import Fraction
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from scipy.signal import butter, medfilt, oaconvolve, sosfiltfilt

SR = 16000    # sampling jalur analisis, mono 16 kHz (3.2.1)
FRAME = 320   # frame 20 ms (3.2.3)
HOP = 160     # hop 10 ms
EPS = 1e-10   # mencegah log10(0) pada Persamaan (3.1)

# Threshold adaptif (3.2.5). Angka dipilih dari benchmark 20 kondisi rekaman, lihat evaluate.py synth.
MARGIN_DB = 6     # threshold atas minimal 6 dB (amplitudo 2x) di atas noise floor
CEIL_DB = 10      # threshold atas maksimal 10 dB di bawah level ucapan (P90 energi)
HYST_DB = 3       # selisih minimal threshold atas dan bawah (3.2.6)
WEAK_DB = 25      # blip terisolasi yang puncaknya 25 dB di bawah level ucapan dianggap derau/napas
                  # (25, bukan 20: hasil benchmark sama, tapi ucapan pelan sampai -25 dB tetap aman)
WEAK_MAX = 0.6    # ... asalkan lebih pendek dari 0,6 detik


class TrimParams(BaseModel):
    """Parameter trim. Nilai bawaan mengikuti Tabel 3.2, batas ge/le adalah validasi input."""
    min_silence: float = Field(0.5, ge=0.1, le=5)
    min_speech: float = Field(0.15, ge=0, le=2)
    pad_start: float = Field(0.15, ge=0, le=1)
    pad_end: float = Field(0.20, ge=0, le=1)
    median: int = Field(5, ge=1, le=15)
    zcr_rescue: bool = True
    audio_crossfade_ms: float = Field(15, ge=0, le=50)
    encoder: Literal["auto", "h264_nvenc", "libx264"] = "auto"


def probe(path):
    """Baca info stream dengan ffprobe (3.2.1)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    streams = info.get("streams", [])
    # Cover art pada MP3 terbaca sebagai stream video (attached_pic), jadi diabaikan.
    video = next((s for s in streams if s["codec_type"] == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    return {
        "duration": float(info["format"].get("duration", 0)),
        "has_audio": any(s["codec_type"] == "audio" for s in streams),
        "has_video": video is not None,
        "fps": float(Fraction(video["r_frame_rate"])) if video else 0,
    }


def load_audio(path):
    """Ambil audio pertama sebagai mono 16 kHz float32 lewat pipe (tanpa file WAV sementara)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1",
         "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def preprocess(x):
    """High-pass 80 Hz lalu band-pass 300-3400 Hz, Butterworth orde 4, dua arah (3.2.2)."""
    hp = butter(4, 80, "highpass", fs=SR, output="sos")
    bp = butter(4, [300, 3400], "bandpass", fs=SR, output="sos")
    # sosfiltfilt menjalankan filter maju lalu mundur sehingga tidak ada pergeseran fase/waktu.
    y = sosfiltfilt(bp, sosfiltfilt(hp, x))
    peak = np.abs(y).max()
    return y / peak if peak > 0 else y


def features(y):
    """Energi dB (Persamaan 3.1) dan ZCR (Persamaan 3.2) per frame."""
    n = 1 + (len(y) - FRAME) // HOP
    w2 = np.hanning(FRAME) ** 2
    # Sum (x*w)^2 per frame = korelasi y^2 dengan w^2, diambil tiap HOP sampel.
    # Cara ini tidak membuat matriks frame (n x 320) sehingga hemat memori untuk video panjang.
    power = oaconvolve(y * y, w2[::-1], mode="valid")[::HOP][:n] / FRAME
    energy = 10 * np.log10(np.maximum(power, 0) + EPS)  # FFT bisa menghasilkan nilai negatif kecil

    # ZCR: tandai tiap pergantian tanda antar sampel (0/1), lalu jumlahkan per frame dengan cumsum.
    s = np.sign(y)
    s[s == 0] = 1
    flips = np.concatenate([[0], np.cumsum(s[1:] != s[:-1])])
    start = np.arange(n) * HOP
    zcr = (flips[start + FRAME - 1] - flips[start]) / FRAME
    return energy, zcr


def thresholds(energy, zcr):
    """Threshold adaptif (3.2.5). Hasil: upper, lower, noise floor, batas ZCR, level ucapan (P90)."""
    # Frame hening digital (energi = log10(EPS) = -100 dB, misal mic di-mute) diabaikan: kalau ikut
    # dihitung, sebaran noise floor membengkak dan threshold naik sampai ucapan pelan terpotong.
    idx = np.flatnonzero(energy > -90)
    idx = idx if idx.size else np.arange(len(energy))
    # Noise floor = median 5% frame terpelan. Persentil kecil + median membuatnya tetap mewakili
    # derau walau rekaman hampir tanpa jeda (10% frame terpelan masih berisi ucapan pelan).
    quiet = idx[np.argsort(energy[idx])[: max(1, idx.size // 20)]]
    floor = np.median(energy[quiet])
    spread = 1.4826 * np.median(np.abs(energy[quiet] - floor))  # simpangan baku versi robust (MAD)
    level = np.percentile(energy[idx], 90)                      # level ucapan keras
    z_lim = zcr[quiet].mean() + 2 * zcr[quiet].std()

    # Threshold atas = noise floor + margin (min 6 dB, atau 3x sebaran derau bila derau berfluktuasi),
    # dibatasi 10 dB di bawah level ucapan agar ucapan pelan tidak hilang. Lantai floor + 6 dB selalu
    # menang, supaya pada rekaman sangat bising (SNR rendah) jeda tetap terpotong.
    upper = max(min(floor + max(MARGIN_DB, 3 * spread), level - CEIL_DB), floor + MARGIN_DB)
    # Threshold bawah dekat noise floor (histeresis lebar): sekali ucapan mulai, ekor kata yang meluruh
    # pelan tetap dipertahankan sampai energi benar-benar turun ke tingkat derau.
    lower = min(upper - HYST_DB, floor + MARGIN_DB)
    return float(upper), float(lower), float(floor), float(z_lim), float(level)


def classify(energy, zcr, upper, lower, z_lim, rescue=True):
    """Label suara/jeda per frame dengan histeresis + ZCR rescue (3.2.6)."""
    speech = np.zeros(len(energy), bool)
    on = False
    # Masuk status suara jika energi > upper, keluar hanya jika energi < lower.
    # ponytail: loop Python per frame (~0,3 s per jam audio), vektorisasi jika jadi bottleneck.
    for i, e in enumerate(energy.tolist()):
        on = e >= lower if on else e > upper
        speech[i] = on

    if rescue:
        # Frame di antara dua threshold dengan ZCR tinggi (konsonan desis /s/, /f/, /h/)
        # dan menempel pada ucapan ikut dianggap suara. Dua pass: maju lalu mundur,
        # supaya rentetan frame kandidat di depan maupun di belakang ucapan ikut terambil.
        cand = (energy >= lower) & (energy <= upper) & (zcr > z_lim)
        for i in range(1, len(speech)):
            speech[i] |= cand[i] and speech[i - 1]
        for i in range(len(speech) - 2, -1, -1):
            speech[i] |= cand[i] and speech[i + 1]
    return speech


def speech_ranges(speech, energy, weak_db, duration, p):
    """Label per frame -> rentang keep (detik) dengan aturan segmen (3.2.8).

    weak_db: blip terisolasi < WEAK_MAX detik yang puncak energinya di bawah nilai ini dibuang.
    None = aturan ini tidak dipakai.
    """
    sec = lambda f: f * HOP / SR  # indeks frame -> detik
    edges = np.diff(np.concatenate([[0], speech.astype(np.int8), [0]]))
    runs = [[s, e] for s, e in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))]

    # Aturan 1: jeda lebih pendek dari min_silence tidak dipotong, rentang suara digabung.
    # Rentang disimpan sebagai indeks frame [awal, akhir) supaya energinya bisa dicek di aturan 2.
    merged = []
    for s, e in runs:
        if merged and sec(s) - (sec(merged[-1][1] - 1) + FRAME / SR) < p["min_silence"]:
            merged[-1][1] = e
        else:
            merged.append([s, e])

    # Aturan 2: suara berdiri sendiri dibuang jika lebih pendek dari min_speech (klik, ketukan),
    # atau pendek dan jauh lebih pelan dari ucapan (napas, gesekan mic di tengah jeda).
    kept = []
    for s, e in merged:
        start, end = sec(s), sec(e - 1) + FRAME / SR
        if end - start < p["min_speech"]:
            continue
        if weak_db is not None and end - start < WEAK_MAX and energy[s:e].max() < weak_db:
            continue
        kept.append([start, end])

    # Aturan 3 dan 4: padding, gabung yang tumpang tindih, potong ke batas file.
    keeps = []
    for s, e in kept:
        s, e = max(0.0, s - p["pad_start"]), min(duration, e + p["pad_end"])
        if keeps and s <= keeps[-1][1]:
            keeps[-1][1] = max(keeps[-1][1], e)
        else:
            keeps.append([s, e])
    return keeps


def build_segments(keeps, duration):
    """Rentang keep -> daftar segmen EDL keep/cut yang menutup seluruh durasi (3.2.9)."""
    segs, t = [], 0.0
    for s, e in keeps + [[duration, duration]]:  # sentinel agar sisa di akhir jadi cut
        if s - t > 1e-3:
            segs.append({"start": round(t, 3), "end": round(s, 3), "action": "cut"})
        if e - s > 1e-3:
            segs.append({"start": round(s, 3), "end": round(e, 3), "action": "keep"})
        t = e
    return segs


def detect(x, duration, p, thr=thresholds):
    """Pipeline deteksi pada sinyal mono 16 kHz. Dipisah dari load_audio agar bisa diuji/ditambah derau.

    thr bisa diganti fungsi threshold lain (dipakai evaluate.py untuk metode pembanding).
    """
    if len(x) < SR // 2:
        raise ValueError("Audio terlalu pendek untuk dianalisis (minimal 0,5 detik)")
    energy, zcr = features(preprocess(x))
    upper, lower, floor, z_lim, level = thr(energy, zcr)
    speech = classify(energy, zcr, upper, lower, z_lim, p["zcr_rescue"])
    # Smoothing median (3.2.7). Kernel wajib ganjil, kernel 1 = tanpa smoothing.
    speech = medfilt(speech.astype(float), p["median"] | 1) > 0.5
    keeps = speech_ranges(speech, energy, None if level is None else level - WEAK_DB, duration, p)

    # Ringkasan energi untuk timeline: nilai maksimum per 100 ms (10 frame) agar data tetap ringan.
    env = energy[: len(energy) // 10 * 10].reshape(-1, 10).max(axis=1)
    return {
        "segments": build_segments(keeps, duration),
        "timeline": {"step": 0.1, "energy": np.round(env, 1).tolist(),
                     "upper": upper, "lower": lower, "noise_floor": floor},
    }


def analyze(path, duration, p):
    return detect(load_audio(path), duration, p)
