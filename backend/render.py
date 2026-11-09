"""Modul render JedaCut: EDL -> MP4 dengan FFmpeg (subbab 3.2.10)."""
import subprocess
from functools import lru_cache


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


def build_graph(keeps, has_video, fade, xfade):
    """Susun filtergraph: trim/atrim per segmen keep, lalu concat (atau xfade/acrossfade).

    fade  = durasi fade audio (detik) di tiap titik potong, mode tanpa crossfade video.
    xfade = durasi crossfade video (detik), 0 jika nonaktif.
    Return (graph, label video, label audio).
    """
    lines = []
    for i, (s, e) in enumerate(keeps):
        if has_video:
            lines.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        a = f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS"
        if fade and not xfade:
            # Fade out + fade in 15 ms di tiap sambungan, bukan acrossfade yang saling tumpang.
            # acrossfade memendekkan audio 15 ms per potongan sehingga 100 potongan = 1,5 s tidak sinkron.
            a += f",afade=t=in:d={fade},afade=t=out:st={max(0, e - s - fade):.4f}:d={fade}"
        lines.append(a + f"[a{i}]")

    if xfade and has_video:
        # Crossfade video beberapa frame. Tiap sambungan overlap sebesar xfade detik, dan audio
        # memakai acrossfade dengan durasi yang sama supaya audio dan video tetap sinkron.
        # offset = panjang hasil sejauh ini dikurangi xfade.
        v, a, length = "v0", "a0", keeps[0][1] - keeps[0][0]
        for i in range(1, len(keeps)):
            offset = length - xfade
            lines.append(f"[{v}][v{i}]xfade=transition=fade:duration={xfade:.4f}:offset={offset:.4f}[vx{i}]")
            lines.append(f"[{a}][a{i}]acrossfade=d={xfade:.4f}[ax{i}]")
            v, a, length = f"vx{i}", f"ax{i}", offset + keeps[i][1] - keeps[i][0]
        return ";\n".join(lines), v, a

    pads = "".join((f"[v{i}]" if has_video else "") + f"[a{i}]" for i in range(len(keeps)))
    lines.append(f"{pads}concat=n={len(keeps)}:v={int(has_video)}:a=1" + ("[v]" if has_video else "") + "[a]")
    return ";\n".join(lines), "v", "a"


def render(src, edl, info, out, on_progress=lambda pct: None):
    """Render video dari EDL. Return nama encoder yang dipakai."""
    p = edl["params"]
    keeps = keep_ranges(edl["segments"])
    if not keeps:
        raise ValueError("Tidak ada segmen Pertahankan di EDL")

    has_video = info["has_video"]
    xfade = 3 / info["fps"] if p.get("video_crossfade") and has_video and info["fps"] else 0
    graph, v, a = build_graph(keeps, has_video, p.get("audio_crossfade_ms", 15) / 1000, xfade)
    total = sum(e - s for s, e in keeps) - xfade * (len(keeps) - 1)

    # Graph ditulis ke file, karena ratusan potongan bisa melebihi batas panjang command line Windows.
    # Ini pengganti render per bagian (3.2.10).
    # ponytail: satu proses FFmpeg untuk semua segmen, pecah per bagian jika memori jadi masalah.
    graph_file = out.with_suffix(".filter.txt")
    graph_file.write_text(graph, encoding="utf-8")

    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-/filter_complex", str(graph_file)]
    encoder = None
    if has_video:
        encoder = pick_encoder(p.get("encoder", "auto"))
        cmd += ["-map", f"[{v}]"]
        cmd += (["-c:v", "h264_nvenc", "-rc", "vbr", "-cq", "20", "-b:v", "0"] if encoder == "h264_nvenc"
                else ["-c:v", "libx264", "-crf", "20", "-preset", "medium"])
        cmd += ["-pix_fmt", "yuv420p"]  # agar bisa diputar di semua browser/pemutar
    cmd += ["-map", f"[{a}]", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(out)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # -progress menulis baris "out_time_us=..." berkala ke stdout, dipakai untuk persen progres.
    for line in proc.stdout:
        key, _, val = line.strip().partition("=")
        if key == "out_time_us" and val.isdigit() and total > 0:
            on_progress(min(99.0, int(val) / 1e6 / total * 100))
    err = proc.stderr.read()
    if proc.wait() != 0:
        raise RuntimeError(err.strip()[-800:] or "FFmpeg gagal")
    return encoder
