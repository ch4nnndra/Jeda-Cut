"""Evaluasi JedaCut (subbab 3.4).

Objektif (Tabel 3.6). Tiap file media butuh label Audacity bernama sama (klip1.mp4 -> klip1.txt),
setiap region label = suara:
    python evaluate.py detect klip1.mp4 klip2.mp4 --snr 30 20 10 [--noise kipas.wav] [--render] [--csv hasil.csv]

Subjektif (Likert dan skor kuis, paired t-test atau Wilcoxon, alpha 0,05):
    python evaluate.py likert responses.csv
"""
import argparse
import csv
import re
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.io import wavfile

import analysis
import render
from analysis import SR, TrimParams

STEP = 0.01             # resolusi label 10 ms
W = int(SR * STEP)      # jumlah sampel per langkah label
rng = np.random.default_rng(0)


def load_labels(path):
    """Label track Audacity: 'start<TAB>end<TAB>teks' per baris."""
    ranges = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        try:
            ranges.append((float(cols[0]), float(cols[1])))
        except (ValueError, IndexError):
            pass  # baris info spektral Audacity (diawali "\") dilewati
    return ranges


def to_mask(ranges, n):
    m = np.zeros(n, bool)
    for s, e in ranges:
        m[int(round(s / STEP)):int(round(e / STEP))] = True
    return m


def fit(m, n):
    """Samakan panjang mask dengan jumlah frame acuan."""
    return np.pad(m, (0, max(0, n - len(m))))[:n]


def runs(mask):
    """Pasangan (awal, akhir) indeks untuk tiap rentetan True."""
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


# ---------- Metode yang dibandingkan. Semua mengembalikan mask keep per 10 ms. ----------

def jedacut(x, dur, n, **override):
    p = {**TrimParams().model_dump(), **override}
    segs = analysis.detect(x, dur, p)["segments"]
    return to_mask([(s["start"], s["end"]) for s in segs if s["action"] == "keep"], n)


def silencedetect(x, dur, n):
    """Replikasi R5: FFmpeg silencedetect, ambang tetap -40 dBFS, durasi 0,5 s."""
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        wavfile.write(wav, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
        log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af",
                              "silencedetect=noise=-40dB:d=0.5", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
    starts = [float(v) for v in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(v) for v in re.findall(r"silence_end: ([\d.]+)", log)]
    ends += [dur] * (len(starts) - len(ends))  # jeda sampai akhir file tidak punya silence_end
    return ~to_mask(zip(starts, ends), n)


def r2_statistic(x, dur, n):
    """Replikasi R2: mu dan sigma dari 1600 sampel awal, bersuara jika |x - mu| > 3 sigma, voting per 10 ms."""
    mu, sd = x[:1600].mean(), x[:1600].std()
    voiced = np.abs(x - mu) > 3 * sd
    votes = voiced[: len(voiced) // W * W].reshape(-1, W).mean(axis=1) > 0.5
    return fit(votes, n)


def r4_rms(x, dur, n, thr=0.001135):
    """Replikasi R4: RMS (akar rata-rata kuadrat) per segmen 100 ms dengan ambang tetap 0,001135."""
    seg = SR // 10
    rms = np.sqrt((x[: len(x) // seg * seg].reshape(-1, seg) ** 2).mean(axis=1))
    return fit(np.repeat(rms > thr, 10), n)


METHODS = {
    "JedaCut": jedacut,
    # Uji ablasi: satu komponen dimatikan per baris.
    "JedaCut tanpa ZCR rescue": lambda x, d, n: jedacut(x, d, n, zcr_rescue=False),
    "JedaCut tanpa smoothing": lambda x, d, n: jedacut(x, d, n, median=1),
    "JedaCut tanpa padding": lambda x, d, n: jedacut(x, d, n, pad_start=0, pad_end=0),
    "silencedetect -40 dB (R5)": silencedetect,
    "Statistik sampel awal (R2)": r2_statistic,
    "RMS ambang tetap (R4)": r4_rms,
}


def add_noise(x, gt, snr, noise=None):
    """Tambah derau pada SNR tertentu. Daya sinyal dihitung dari sampel suara acuan saja."""
    speech = np.repeat(gt, W)[: len(x)]
    ps = np.mean(x[: len(speech)][speech] ** 2)
    nz = rng.standard_normal(len(x)) if noise is None else np.resize(noise, len(x)).astype(np.float64)
    nz *= np.sqrt(ps / 10 ** (snr / 10) / np.mean(nz ** 2))
    return (x + nz).astype(np.float32)


def score(pred, gt):
    """Hitungan mentah per klip. Dijumlah antarklip (micro-average) sebelum jadi metrik."""
    long_sil = np.zeros_like(gt)
    for s, e in runs(~gt):
        if e - s >= 50:  # SRR hanya menghitung jeda acuan >= 0,5 s
            long_sil[s:e] = True
    return {"tp": np.sum(pred & gt), "fp": np.sum(pred & ~gt), "fn": np.sum(~pred & gt),
            "long": long_sil.sum(), "removed": np.sum(long_sil & ~pred), "kept": pred.sum(), "n": len(gt)}


def metrics(c):
    div = lambda a, b: a / b if b else float("nan")
    p, r = div(c["tp"], c["tp"] + c["fp"]), div(c["tp"], c["tp"] + c["fn"])
    return {"precision": p, "recall": r, "f1": div(2 * p * r, p + r),
            "scr": div(c["fn"], c["tp"] + c["fn"]),  # frame ucapan yang ikut terbuang
            "srr": div(c["removed"], c["long"]),     # frame jeda >= 0,5 s yang berhasil dibuang
            "ratio": div(c["kept"], c["n"]), "rtf": div(c["time"], c["dur"])}


def run_detect(args):
    clips = []
    for f in args.files:
        label = Path(f).with_suffix(".txt")
        if not label.exists():
            raise SystemExit(f"Label tidak ditemukan: {label}")
        x = analysis.load_audio(f)
        dur = len(x) / SR
        n = int(dur / STEP)
        clips.append((f, x, dur, to_mask(load_labels(label), n)))
    noise = analysis.load_audio(args.noise) if args.noise else None

    rows = []
    for snr in [None] + args.snr:
        cond = "bersih" if snr is None else f"SNR {snr} dB"
        for name, method in METHODS.items():
            total = {}
            for _, x, dur, gt in clips:
                xi = x if snr is None else add_noise(x, gt, snr, noise)
                t0 = time.perf_counter()
                pred = method(xi, dur, len(gt))
                c = score(pred, gt)
                c.update(time=time.perf_counter() - t0, dur=dur)
                for k, v in c.items():
                    total[k] = total.get(k, 0) + v
            rows.append({"condition": cond, "method": name, **metrics(total)})

    cols = ["precision", "recall", "f1", "scr", "srr", "ratio", "rtf"]
    print(f"{'kondisi':<12} {'metode':<28}" + "".join(f"{c:>10}" for c in cols))
    for r in rows:
        print(f"{r['condition']:<12} {r['method']:<28}" + "".join(f"{r[c]:>10.4f}" for c in cols))

    if args.render:
        # RTF penuh seperti di aplikasi: decode + analisis, lalu render (dihitung terpisah).
        print("\nRTF aplikasi penuh (JedaCut, file asli):")
        p = TrimParams().model_dump()
        for f, _, dur, _ in clips:
            info = analysis.probe(f)
            t0 = time.perf_counter()
            segs = analysis.analyze(f, info["duration"], p)["segments"]
            t1 = time.perf_counter()
            with tempfile.TemporaryDirectory() as d:
                render.render(f, {"params": p, "segments": segs}, info, Path(d) / "out.mp4")
            t2 = time.perf_counter()
            print(f"  {Path(f).name}: analisis {(t1 - t0) / dur:.4f}, render {(t2 - t1) / dur:.4f}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        print(f"\nTersimpan: {args.csv}")


def run_likert(args):
    """CSV kolom: aspect, original, result. Satu baris per responden per aspek (skor kuis juga boleh)."""
    data = {}
    with open(args.file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            data.setdefault(row["aspect"], []).append((float(row["original"]), float(row["result"])))

    print(f"{'aspek':<24}{'n':>4}{'asli':>8}{'hasil':>8}  {'uji':<14}{'statistik':>10}{'p':>9}  signifikan")
    for aspect, pairs in data.items():
        a, b = np.array(pairs).T
        diff = b - a
        # Selisih berdistribusi normal (Shapiro-Wilk p >= 0,05) -> paired t-test, selain itu Wilcoxon.
        normal = len(diff) < 3 or np.ptp(diff) == 0 or stats.shapiro(diff).pvalue >= 0.05
        res = stats.ttest_rel(b, a) if normal else stats.wilcoxon(b, a)
        test = "paired t-test" if normal else "Wilcoxon"
        sig = "ya" if res.pvalue < 0.05 else "tidak"
        print(f"{aspect:<24}{len(a):>4}{a.mean():>8.2f}{b.mean():>8.2f}  {test:<14}"
              f"{res.statistic:>10.3f}{res.pvalue:>9.4f}  {sig}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Evaluasi JedaCut")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect", help="metrik objektif terhadap label manual")
    d.add_argument("files", nargs="+")
    d.add_argument("--snr", type=float, nargs="*", default=[], help="contoh: --snr 30 20 10")
    d.add_argument("--noise", help="file derau nyata (kipas, keramaian); default derau putih")
    d.add_argument("--render", action="store_true", help="ukur juga RTF analisis penuh dan render")
    d.add_argument("--csv", help="simpan tabel hasil ke CSV")
    lk = sub.add_parser("likert", help="uji beda skor Likert/kuis video asli vs hasil")
    lk.add_argument("file")
    args = ap.parse_args()
    run_detect(args) if args.cmd == "detect" else run_likert(args)
