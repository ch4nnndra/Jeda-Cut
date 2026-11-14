"""Modul render JedaCut: EDL -> MP4 dengan FFmpeg (subbab 3.2.10)."""
import math
import subprocess
from functools import lru_cache

GROUP_MIN = 20    # bagian keep per kelompok input
MAX_INPUTS = 25   # batas jumlah input (tiap input = satu decoder, sekitar 30 MB memori)


@lru_cache(maxsize=None)
def nvenc_ok():
    """Cek sekali apakah h264_nvenc benar-benar bisa dipakai. Ada encoder belum tentu jalan (versi driver)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1",
                        "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


def pick_encoder(encoder):
    """auto, atau h264_nvenc yang tidak bisa jalan, jatuh ke libx264."""
    if encoder == "libx264":
        return encoder
    return "h264_nvenc" if nvenc_ok() else "libx264"


def keep_ranges(segments):
    """Ambil segmen keep dan gabungkan yang bersebelahan (misal user mengubah cut di antaranya jadi keep)."""
    keeps = []
    for s in segments:
        if s["action"] != "keep":
            continue
        if keeps and s["start"] - keeps[-1][1] < 1e-3:
            keeps[-1][1] = s["end"]
        else:
            keeps.append([s["start"], s["end"]])
    return keeps


def build_graph(src, keeps, has_video, fade):
    """Susun argumen input dan filtergraph: trim/atrim per bagian keep, lalu concat ke [v] dan [a].

    Render per kelompok (3.2.10): bagian keep dikelompokkan, dan tiap kelompok membaca file sumber
    sebagai input tersendiri yang di-seek (-ss/-t) hanya ke rentangnya. Kalau semua trim membaca satu
    input, setiap frame dikirim ke ratusan filter trim sekaligus, sehingga bebannya naik kuadratik
    terhadap durasi (video 30 menit: 34 menit ekspor, versi kelompok: kurang dari 3 menit).

    fade = durasi fade audio (detik) di tiap titik potong, 0 jika nonaktif.
    Return (argumen input ffmpeg, filtergraph).
    """
    size = max(GROUP_MIN, math.ceil(len(keeps) / MAX_INPUTS))
    args, lines, pads = [], [], ""
    for g, i in enumerate(range(0, len(keeps), size)):
        group = keeps[i:i + size]
        a, b = group[0][0], group[-1][1]
        # -ss sebagai opsi input + re-encode tetap akurat per frame: FFmpeg seek ke keyframe
        # sebelumnya lalu membuang frame sampai titik a.
        args += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src)]
        for j, (s, e) in enumerate(group):
            s, e, n = s - a, e - a, f"{g}_{j}"  # waktu relatif terhadap awal input kelompok
            if has_video:
                lines.append(f"[{g}:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{n}]")
                pads += f"[v{n}]"
            au = f"[{g}:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS"
            if fade:
                # Fade out + fade in 15 ms di tiap sambungan, bukan acrossfade yang saling tumpang.
                # acrossfade memendekkan audio 15 ms per potongan sehingga 100 potongan = 1,5 s tidak sinkron.
                au += f",afade=t=in:d={fade},afade=t=out:st={max(0, e - s - fade):.4f}:d={fade}"
            lines.append(au + f"[a{n}]")
            pads += f"[a{n}]"

    lines.append(f"{pads}concat=n={len(keeps)}:v={int(has_video)}:a=1" + ("[v]" if has_video else "") + "[a]")
    return args, ";\n".join(lines)


def render(src, edl, info, out, on_progress=lambda pct: None, on_start=lambda proc: None):
    """Render video dari EDL. Return nama encoder yang dipakai.

    on_start menerima proses FFmpeg begitu dijalankan, supaya pemanggil bisa membatalkannya.
    """
    p = edl["params"]
    keeps = keep_ranges(edl["segments"])
    if not keeps:
        raise ValueError("Tidak ada segmen Pertahankan di EDL")

    has_video = info["has_video"]
    inputs, graph = build_graph(src, keeps, has_video, p.get("audio_crossfade_ms", 15) / 1000)
    total = sum(e - s for s, e in keeps)

    # Graph ditulis ke file, karena ratusan potongan bisa melebihi batas panjang command line Windows.
    graph_file = out.with_suffix(".filter.txt")
    graph_file.write_text(graph, encoding="utf-8")

    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-/filter_complex", str(graph_file)]
    encoder = None
    if has_video:
        encoder = pick_encoder(p.get("encoder", "auto"))
        cmd += ["-map", "[v]"]
        cmd += (["-c:v", "h264_nvenc", "-rc", "vbr", "-cq", "20", "-b:v", "0"] if encoder == "h264_nvenc"
                else ["-c:v", "libx264", "-crf", "20", "-preset", "medium"])
        cmd += ["-pix_fmt", "yuv420p"]  # agar bisa diputar di semua browser/pemutar
    cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(out)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    on_start(proc)
    # -progress menulis baris "out_time_us=..." berkala ke stdout, dipakai untuk persen progres.
    for line in proc.stdout:
        key, _, val = line.strip().partition("=")
        if key == "out_time_us" and val.isdigit() and total > 0:
            on_progress(min(99.0, int(val) / 1e6 / total * 100))
    err = proc.stderr.read()
    if proc.wait() != 0:
        raise RuntimeError(err.strip()[-800:] or "FFmpeg gagal")
    return encoder
