"""Self-check deteksi jeda dengan sinyal sintetis. Jalankan: python test_analysis.py"""
import numpy as np

from analysis import SR, TrimParams, detect
from render import build_graph, keep_ranges

rng = np.random.default_rng(0)


def part(sec, amp):
    return amp * rng.standard_normal(int(sec * SR))


# Susunan (detik): diam 1 | suara 2 | jeda pendek 0,3 | suara 1 | diam 1,5 | klik 0,05 | diam 1,5 | suara 1 | diam 1
x = np.concatenate([part(1, 1e-3), part(2, 0.3), part(0.3, 1e-3), part(1, 0.3), part(1.5, 1e-3),
                    part(0.05, 0.5), part(1.5, 1e-3), part(1, 0.3), part(1, 1e-3)]).astype(np.float32)
duration = len(x) / SR

for method in ("stat", "dual", "midpoint"):
    p = TrimParams(threshold_method=method).model_dump()
    segs = detect(x, duration, p)["segments"]
    keeps = [(s["start"], s["end"]) for s in segs if s["action"] == "keep"]
    # Jeda 0,3 s tidak dipotong, klik 50 ms dibuang, padding 0,15/0,20 s terpasang.
    assert len(keeps) == 2, (method, keeps)
    assert abs(keeps[0][0] - 0.85) < 0.05 and abs(keeps[0][1] - 4.5) < 0.05, (method, keeps)
    assert abs(keeps[1][0] - 7.2) < 0.05 and abs(keeps[1][1] - 8.55) < 0.05, (method, keeps)
    # Segmen EDL harus menutup seluruh durasi tanpa celah.
    assert segs[0]["start"] == 0 and abs(segs[-1]["end"] - duration) < 1e-3
    assert all(a["end"] == b["start"] for a, b in zip(segs, segs[1:]))

# Render: keep yang bersebelahan digabung jadi satu rentang, concat menerima semua pad.
edl = [{"start": 0, "end": 1, "action": "keep"}, {"start": 1, "end": 2, "action": "keep"},
       {"start": 2, "end": 3, "action": "cut"}, {"start": 3, "end": 4, "action": "keep"}]
assert keep_ranges(edl) == [[0, 2], [3, 4]]
graph, v, a = build_graph(keep_ranges(edl), True, 0.015, 0)
assert "concat=n=2:v=1:a=1[v][a]" in graph and (v, a) == ("v", "a")

print("OK")
