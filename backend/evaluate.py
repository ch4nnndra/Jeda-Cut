"""Evaluasi JedaCut (subbab 3.4).

Objektif (Tabel 3.6). Tiap file media butuh label Audacity bernama sama (klip1.mp4 -> klip1.txt),
setiap region label = satu ucapan:
    python evaluate.py detect klip1.mp4 klip2.mp4 --snr 30 20 10 [--noise kipas.wav] [--render] [--csv hasil.csv]

Benchmark sintetis 20 kondisi rekaman dengan ground truth pasti. Folder berisi WAV kalimat bersih,
satu kalimat per file, nama "suara_nomor.wav" (buat di Windows dengan make_sentences.ps1):
    python evaluate.py synth sentences --seeds 1 2

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
from scipy.signal import fftconvolve

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
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


# ---------- Metode yang dibandingkan. Semua mengembalikan mask keep per 10 ms. ----------

def jedacut(x, dur, n, thr=analysis.thresholds, **override):
    p = {**TrimParams().model_dump(), **override}
    segs = analysis.detect(x, dur, p, thr)["segments"]
    return to_mask([(s["start"], s["end"]) for s in segs if s["action"] == "keep"], n)


def report_thresholds(method):
    """Threshold rancangan awal laporan sebagai pembanding: midpoint (3.7) atau dual threshold
    Rao dkk. (3.4-3.6), noise floor = rata-rata 10% frame terpelan, batas atas -20 dBFS."""
    def thr(energy, zcr):
        quiet = np.argsort(energy)[: max(1, len(energy) // 10)]
        mu = energy[quiet].mean()
        z_lim = zcr[quiet].mean() + 2 * zcr[quiet].std()
        lower = None
        if method == "dual":
            e = 10 ** (energy / 10)  # rumus Rao dkk. berlaku pada energi linear
            emin = max(np.percentile(e, 5), analysis.EPS)
            t1 = emin * (5 + 2 * np.log10(e.max() / emin))
            above = e[e > t1]
            t2 = t1 + 0.25 * ((above.mean() if above.size else t1) - t1)
            upper, lower = 10 * np.log10(t2), 10 * np.log10(t1)
        else:
            upper = (np.percentile(energy, 10) + np.percentile(energy, 90)) / 2
        upper = min(max(upper, mu + 6), -20)
        lower = upper - analysis.HYST_DB if lower is None else min(lower, upper)
        return upper, lower, mu, z_lim, None  # None: tanpa filter blip lemah, sesuai rancangan awal
    return thr


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
    "JedaCut tanpa filter blip": lambda x, d, n: jedacut(
        x, d, n, thr=lambda e, z: analysis.thresholds(e, z)[:4] + (None,)),
    # Metode threshold rancangan awal (dihapus dari aplikasi, dipertahankan sebagai pembanding).
    "Midpoint (rancangan)": lambda x, d, n: jedacut(x, d, n, thr=report_thresholds("midpoint")),
    "Dual threshold (rancangan)": lambda x, d, n: jedacut(x, d, n, thr=report_thresholds("dual")),
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
    """Hitungan mentah per klip. Dijumlah antarklip (micro-average) sebelum jadi metrik.

    Aksi tinjau = jumlah koreksi manual yang dibutuhkan pengguna di layar Tinjau:
    ucapan terpotong (> 30 ms ucapan ikut dibuang) + jeda panjang (>= 0,8 s) yang kurang dari separuhnya dipotong.
    """
    long_sil = np.zeros_like(gt)
    sil = runs(~gt)
    pauses = [(s, e) for s, e in sil if e - s >= 80]
    for s, e in sil:
        if e - s >= 50:  # SRR hanya menghitung jeda acuan >= 0,5 s
            long_sil[s:e] = True
    utts = runs(gt)
    return {"tp": np.sum(pred & gt), "fp": np.sum(pred & ~gt), "fn": np.sum(~pred & gt),
            "long": long_sil.sum(), "removed": np.sum(long_sil & ~pred), "kept": pred.sum(), "n": len(gt),
            "utt": len(utts), "clipped": sum(np.sum(~pred[s:e]) > 3 for s, e in utts),
            "pauses": len(pauses), "missed": sum(np.mean(~pred[s:e]) < 0.5 for s, e in pauses)}


def metrics(c):
    div = lambda a, b: a / b if b else float("nan")
    p, r = div(c["tp"], c["tp"] + c["fp"]), div(c["tp"], c["tp"] + c["fn"])
    return {"precision": p, "recall": r, "f1": div(2 * p * r, p + r),
            "scr": div(c["fn"], c["tp"] + c["fn"]),  # frame ucapan yang ikut terbuang
            "srr": div(c["removed"], c["long"]),     # frame jeda >= 0,5 s yang berhasil dibuang
            "ratio": div(c["kept"], c["n"]), "rtf": div(c["time"], c["dur"]),
            "clipped": int(c["clipped"]), "missed": int(c["missed"]), "review": int(c["clipped"] + c["missed"])}


def evaluate_clips(clips, methods):
    """clips: list (x, durasi, mask ground truth). Return {metode: hitungan mentah yang dijumlah}."""
    totals = {}
    for name, method in methods.items():
        total = {}
        for x, dur, gt in clips:
            t0 = time.perf_counter()
            pred = method(x, dur, len(gt))
            c = score(pred, gt)
            c.update(time=time.perf_counter() - t0, dur=dur)
            for k, v in c.items():
                total[k] = total.get(k, 0) + v
        totals[name] = total
    return totals


def print_rows(rows):
    cols = ["precision", "recall", "f1", "scr", "srr", "ratio", "rtf"]
    print(f"{'kondisi':<12} {'metode':<28}" + "".join(f"{c:>10}" for c in cols) + f"{'aksi tinjau':>14}")
    for r in rows:
        print(f"{r['condition']:<12} {r['method']:<28}" + "".join(f"{r[c]:>10.4f}" for c in cols)
              + f"{r['review']:>6} ({r['clipped']}/{r['missed']})")


def run_detect(args):
    clips = []
    for f in args.files:
        label = Path(f).with_suffix(".txt")
        if not label.exists():
            raise SystemExit(f"Label tidak ditemukan: {label}")
        x = analysis.load_audio(f)
        dur = len(x) / SR
        clips.append((f, x, dur, to_mask(load_labels(label), int(dur / STEP))))
    noise = analysis.load_audio(args.noise) if args.noise else None

    rows = []
    for snr in [None] + args.snr:
        cond = "bersih" if snr is None else f"SNR {snr} dB"
        noisy = [(x if snr is None else add_noise(x, gt, snr, noise), dur, gt) for _, x, dur, gt in clips]
        for name, total in evaluate_clips(noisy, METHODS).items():
            rows.append({"condition": cond, "method": name, **metrics(total)})
    print_rows(rows)

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


# ---------- Benchmark sintetis ----------

# Kondisi rekaman. Ground truth pasti karena jeda disisipkan sendiri di antara kalimat bersih.
CONDS = {
    "clean":        {},
    "pink30":       {"noise": ("pink", 30)},
    "pink20":       {"noise": ("pink", 20)},
    "pink10":       {"noise": ("pink", 10)},
    "white20":      {"noise": ("white", 20)},
    "white10":      {"noise": ("white", 10)},
    "brown15":      {"noise": ("brown", 15)},          # dengung frekuensi rendah
    "hum":          {"hum": 10, "noise": ("pink", 35)},  # dengung listrik 50 Hz + harmonik
    "quiet":        {"gain": -26, "abs_noise": -66},   # pembicara jauh dari mic, level sangat kecil
    "vary12":       {"vary": 12, "noise": ("pink", 25)},  # separuh kalimat 12 dB lebih pelan
    "vary18":       {"vary": 18, "noise": ("pink", 30)},
    "dense":        {"profile": "dense", "noise": ("pink", 25)},
    "sparse":       {"profile": "sparse", "noise": ("pink", 25)},
    "nolead":       {"nolead": True, "noise": ("pink", 25)},  # langsung bicara tanpa jeda awal/akhir
    "breath_click": {"events": True, "noise": ("pink", 30)},  # napas dan klik di dalam jeda
    "reverb":       {"reverb": True, "noise": ("pink", 30)},
    "babble":       {"babble": 20, "noise": ("pink", 30)},    # orang lain bicara di latar (di luar batasan)
    "packed":       {"profile": "packed", "reverb": True, "noise": ("pink", 25)},  # hampir tanpa jeda
    "packed_vary":  {"profile": "packed", "reverb": True, "vary": 10, "noise": ("pink", 25)},
    "digital_mix":  {"digital": True, "noise": ("pink", 25)},  # sebagian jeda hening digital (mic di-mute)
}


def colored(r, n, kind):
    """Derau putih, pink (1/f), atau brown (1/f^2)."""
    w = r.standard_normal(n)
    if kind == "white":
        return w
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    return np.fft.irfft(np.fft.rfft(w) / (np.sqrt(f) if kind == "pink" else f), n)


def rms(v):
    return np.sqrt(np.mean(v ** 2) + 1e-20)


def build_clip(sents, other, cond, seed):
    """Susun satu klip dari kalimat bersih + jeda acak + gangguan sesuai kondisi. Return (x, mask suara)."""
    r = np.random.default_rng(seed)
    order = r.permutation(len(sents))
    prof = cond.get("profile")

    def gap():
        u = r.random()
        if prof == "dense":
            return r.uniform(0.1, 0.4) if u < 0.85 else r.uniform(0.6, 1.2)
        if prof == "sparse":
            return r.uniform(0.15, 0.45) if u < 0.2 else r.uniform(1.5, 5.0)
        if prof == "packed":
            return r.uniform(0.06, 0.2) if u < 0.85 else r.uniform(0.6, 1.0)
        return r.uniform(0.15, 0.45) if u < 0.6 else r.uniform(0.7, 3.0)

    edge = 0 if cond.get("nolead") else 1
    parts, spans, gaps, t = [], [], [], 0.0

    def silence(d):
        nonlocal t
        k = int(d * SR)
        parts.append(np.zeros(k))
        gaps.append((t, t + k / SR))
        t += k / SR

    if edge:
        silence(r.uniform(0.5, 2.0))
    for i, j in enumerate(order):
        g = 10 ** (-cond["vary"] / 20) if cond.get("vary") and r.random() < 0.5 else 1.0
        parts.append(sents[j] * g)
        spans.append((t, t + len(sents[j]) / SR))
        t += len(sents[j]) / SR
        if i < len(order) - 1:
            silence(gap())
    if edge:
        silence(r.uniform(0.5, 2.0))

    x = np.concatenate(parts)
    n = len(x)
    gt = to_mask(spans, int(round(n / SR / STEP)))
    ps = rms(np.concatenate([x[int(a * SR):int(b * SR)] for a, b in spans]))

    if cond.get("reverb"):  # gema ruangan: respons impuls eksponensial RT60 0,5 s
        tt = np.arange(int(0.8 * SR)) / SR
        h = r.standard_normal(tt.size) * np.exp(-6.9 * tt / 0.5)
        h[0] = 0
        wet = fftconvolve(x, h)[:n]
        x = x + 0.5 * wet * rms(x) / rms(wet)
    if cond.get("events"):  # klik pendek keras + napas lemah 0,3 s di tiap jeda > 1 s
        for a, b in gaps:
            if b - a > 1.0:
                c, k = int((a + 0.3) * SR), int(r.uniform(0.005, 0.03) * SR)
                x[c:c + k] += r.standard_normal(k) * ps * 1.5
                c, k = int((a + b) / 2 * SR), int(0.3 * SR)
                bn = colored(r, k, "pink")
                x[c:c + k] += bn / rms(bn) * ps * 10 ** (-24 / 20) * np.hanning(k)
    if cond.get("babble"):
        bab = np.resize(np.concatenate(other), n)
        x = x + bab / rms(bab) * ps * 10 ** (-cond["babble"] / 20)
    if "noise" in cond:
        kind, snr = cond["noise"]
        nz = colored(r, n, kind)
        nz = nz / rms(nz) * ps * 10 ** (-snr / 20)
        if cond.get("digital"):
            for a, b in gaps:
                if b - a > 0.6 and r.random() < 0.4:
                    nz[int(a * SR):int(b * SR)] = 0
        x = x + nz
    if cond.get("hum"):
        tt = np.arange(n) / SR
        hm = sum(np.sin(2 * np.pi * f * tt) / k for k, f in enumerate([50, 100, 150, 250, 350], 1))
        x = x + hm / rms(hm) * ps * 10 ** (-cond["hum"] / 20)
    if cond.get("gain"):
        nz = colored(r, n, "pink")
        x = x * 10 ** (cond["gain"] / 20) + nz / rms(nz) * 10 ** (cond["abs_noise"] / 20)
    return np.clip(x, -1, 1).astype(np.float32), gt


def run_synth(args):
    voices = {}
    for f in sorted(Path(args.folder).glob("*.wav")):
        y = analysis.load_audio(f)
        nz = np.flatnonzero(np.abs(y) > 2e-3)  # buang hening di awal/akhir file kalimat
        if not nz.size:
            print(f"Dilewati, file tanpa suara: {f.name}")
            continue
        voices.setdefault(f.stem.split("_")[0], []).append(y[nz[0]: nz[-1] + 1].astype(np.float64))
    if not voices:
        raise SystemExit(f"Tidak ada file WAV di {args.folder}")

    names = list(METHODS) if args.all else ["JedaCut", "Midpoint (rancangan)", "Dual threshold (rancangan)"]
    methods = {k: METHODS[k] for k in names}
    total, per = {}, {}
    for ci, (cname, cond) in enumerate(CONDS.items()):
        clips = []
        for vi, (voice, sents) in enumerate(voices.items()):
            other = voices[list(voices)[(vi + 1) % len(voices)]]
            for seed in args.seeds:
                x, gt = build_clip(sents, other, cond, seed * 1000 + ci * 10 + vi)
                clips.append((x, len(x) / SR, gt))
        per[cname] = evaluate_clips(clips, methods)
        for m, c in per[cname].items():
            for k, v in c.items():
                total.setdefault(m, {})[k] = total.get(m, {}).get(k, 0) + v

    short = [m[:20] for m in names]
    print(f"Aksi tinjau per kondisi (ucapan terpotong/jeda terlewat)\n{'kondisi':<13}"
          + "".join(f"{s:>22}" for s in short))
    for cname in CONDS:
        print(f"{cname:<13}" + "".join(
            f"{per[cname][m]['clipped'] + per[cname][m]['missed']:>12} ({per[cname][m]['clipped']}/{per[cname][m]['missed']})".rjust(22)
            for m in names))
    t = total[names[0]]
    print(f"\nTotal {len(CONDS)} kondisi, {len(voices)} suara x {len(args.seeds)} seed: "
          f"{t['utt']} ucapan, {t['pauses']} jeda panjang\n")
    print_rows([{"condition": "semua", "method": m, **metrics(total[m])} for m in names])


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
    s = sub.add_parser("synth", help="benchmark sintetis 20 kondisi dengan ground truth pasti")
    s.add_argument("folder", help="folder WAV kalimat bersih (suara_nomor.wav)")
    s.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    s.add_argument("--all", action="store_true", help="tampilkan juga ablasi dan pembanding R2/R4/R5")
    lk = sub.add_parser("likert", help="uji beda skor Likert/kuis video asli vs hasil")
    lk.add_argument("file")
    args = ap.parse_args()
    {"detect": run_detect, "synth": run_synth, "likert": run_likert}[args.cmd](args)
