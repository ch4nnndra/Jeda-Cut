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


class TrimParams(BaseModel):
    """Parameter trim. Nilai bawaan mengikuti Tabel 3.2, batas ge/le adalah validasi input."""
    min_silence: float = Field(0.5, ge=0.1, le=5)
    min_speech: float = Field(0.15, ge=0, le=2)
    pad_start: float = Field(0.15, ge=0, le=1)
    pad_end: float = Field(0.20, ge=0, le=1)
    # Metode statistik (mu + k sigma) dihapus: noise floor sering terisi ucapan pelan sehingga
    # threshold terlalu tinggi dan ucapan pelan ikut terpotong. Bawaan diganti midpoint.
    threshold_method: Literal["midpoint", "dual"] = "midpoint"
    hysteresis_db: float = Field(3, ge=0, le=12)
    median: int = Field(5, ge=1, le=15)
    zcr_rescue: bool = True
    audio_crossfade_ms: float = Field(15, ge=0, le=50)
    video_crossfade: bool = False
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


def thresholds(energy, zcr, p):
    """Noise floor + threshold adaptif (3.2.5). Hasil: upper, lower, noise floor, batas ZCR."""
    # Noise floor dari 10% frame paling pelan di seluruh rekaman, bukan dari bagian awal saja.
    quiet = np.argsort(energy)[: max(1, len(energy) // 10)]
    mu = energy[quiet].mean()
    z_lim = zcr[quiet].mean() + 2 * zcr[quiet].std()

    if p["threshold_method"] == "dual":
        # Rumus Rao dkk. berlaku pada energi linear, jadi dB dikembalikan ke linear dulu.
        e = 10 ** (energy / 10)
        emin = max(np.percentile(e, 5), EPS)  # persentil ke-5 agar tidak nol saat ada hening total
        t1 = emin * (5 + 2 * np.log10(e.max() / emin))      # (3.4)
        above = e[e > t1]
        sl = above.mean() if above.size else t1             # (3.5)
        t2 = t1 + 0.25 * (sl - t1)                          # (3.6)
        upper, lower = 10 * np.log10(t2), 10 * np.log10(t1)
    else:
        upper = (np.percentile(energy, 10) + np.percentile(energy, 90)) / 2  # midpoint (3.7)
        lower = None

    # Pengaman: minimal 6 dB di atas noise floor, maksimal -20 dBFS.
    upper = min(max(upper, mu + 6), -20)
    lower = upper - p["hysteresis_db"] if lower is None else min(lower, upper)
    return float(upper), float(lower), float(mu), float(z_lim)


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


def speech_ranges(speech, duration, p):
    """Label per frame -> rentang keep (detik) dengan aturan segmen (3.2.8)."""
    edges = np.diff(np.concatenate([[0], speech.astype(np.int8), [0]]))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    runs = [[s * HOP / SR, ((e - 1) * HOP + FRAME) / SR] for s, e in zip(starts, ends)]

    # Aturan 1: jeda lebih pendek dari min_silence tidak dipotong, rentang suara digabung.
    merged = []
    for s, e in runs:
        if merged and s - merged[-1][1] < p["min_silence"]:
            merged[-1][1] = e
        else:
            merged.append([s, e])

    # Aturan 2: suara berdiri sendiri yang lebih pendek dari min_speech (klik, ketukan) dibuang.
    merged = [r for r in merged if r[1] - r[0] >= p["min_speech"]]

    # Aturan 3 dan 4: padding, gabung yang tumpang tindih, potong ke batas file.
    keeps = []
    for s, e in merged:
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


def detect(x, duration, p):
    """Pipeline deteksi pada sinyal mono 16 kHz. Dipisah dari load_audio agar bisa diuji/ditambah derau."""
    if len(x) < SR // 2:
        raise ValueError("Audio terlalu pendek untuk dianalisis (minimal 0,5 detik)")
    energy, zcr = features(preprocess(x))
    upper, lower, floor, z_lim = thresholds(energy, zcr, p)
    speech = classify(energy, zcr, upper, lower, z_lim, p["zcr_rescue"])
    if p["median"] > 1:
        # Smoothing median (3.2.7). Kernel medfilt wajib ganjil.
        speech = medfilt(speech.astype(float), p["median"] | 1) > 0.5
    keeps = speech_ranges(speech, duration, p)

    # Ringkasan energi untuk timeline: nilai maksimum per 100 ms (10 frame) agar data tetap ringan.
    n = len(energy) // 10 * 10
    env = energy[:n].reshape(-1, 10).max(axis=1) if n else energy
    return {
        "segments": build_segments(keeps, duration),
        "timeline": {"step": 0.1, "energy": np.round(env, 1).tolist(),
                     "upper": upper, "lower": lower, "noise_floor": floor},
    }


def analyze(path, duration, p):
    return detect(load_audio(path), duration, p)
