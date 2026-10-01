#!/usr/bin/env python3
"""Stage 0A step 2c: LRF proxy content + time-mapping verification.

For each clip, the original-source sample frames at start/q1/mid/q3/end (saved by
s2_visual.py from the ORIGINAL) are compared with every LRF frame inside a
±0.5 s window. We record best NCC and its time offset per point. The pairing is
confirmed when >=4 of 5 points reach NCC>=0.9 and the offsets agree
(median |offset| <= 0.05 s, spread <= 0.05 s, i.e. within ~1 LRF frame) -> verified 1:1 time mapping.

Per-clip cache: temp/stage0a/proxy_check/<clip_id>.json
"""
from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from common import PROCESS, TEMP, read_json, write_json

WIN = 0.5
PARAMS = {"win": WIN, "thumb": [64, 36], "ncc_min": 0.9, "min_points": 4, "max_offset": 0.05, "rev": 3}


def ncc(a, b):
    a = (a - a.mean()) / (a.std() + 1e-6)
    b = (b - b.mean()) / (b.std() + 1e-6)
    return float((a * b).mean())


def lrf_window(lrf, t0, dur, fps):
    """LRF frames in [t0-WIN, t0+WIN] with their real pts (showinfo, -copyts)."""
    a, b = max(0.0, t0 - WIN), t0 + WIN
    cmd = ["ffmpeg", "-v", "info", "-nostdin", "-copyts", "-ss", f"{max(0.0, a - 2):.3f}", "-i", str(lrf),
           "-map", "0:v:0", "-vf", f"select='between(t\\,{a:.4f}\\,{b:.4f})',showinfo,scale=64:36:flags=area,format=gray",
           "-fps_mode", "passthrough", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True)
    ts = [float(m) for m in re.findall(rb"pts_time:\s*([0-9.]+)", r.stderr)]
    n = len(r.stdout) // (64 * 36)
    fr = np.frombuffer(r.stdout[: n * 64 * 36], np.uint8).reshape(n, 36, 64).astype(np.float32)
    return list(zip([round(t, 4) for t in ts[:n]], fr))


def luma_series_check(v, vis, lrf):
    """Crop/stabilisation-insensitive time-mapping check: whole-clip mean-luma
    curve of the original (s2 timeline, exact frame times) vs the LRF (real pts)."""
    cmd = ["ffmpeg", "-v", "info", "-nostdin", "-i", str(lrf), "-map", "0:v:0",
           "-vf", "scale=64:36:flags=area,format=gray,showinfo", "-fps_mode", "passthrough", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True)
    ts = np.array([float(m) for m in re.findall(rb"pts_time:\s*([0-9.]+)", r.stderr)])
    n = min(len(ts), len(r.stdout) // 2304)
    lm = np.frombuffer(r.stdout[: n * 2304], np.uint8).reshape(n, 2304).mean(axis=1)
    ts = ts[:n]
    ot = np.array([x["t"] for x in vis["timeline"]])
    ol = np.array([x["luma"] for x in vis["timeline"]])
    if len(ot) < 8 or n < 8:
        return {"method": "mean-luma time series", "passed": False, "note": "too few frames"}
    best = (-2.0, None)
    for lag in np.arange(-0.5, 0.5001, 1 / 60):
        li = np.interp(ot + lag, ts, lm)
        c = float(np.corrcoef(ol, li)[0, 1])
        if c > best[0] + 1e-4 or (abs(c - best[0]) <= 1e-4 and abs(lag) < abs(best[1])):
            best = (c, float(lag))
    ok = best[0] >= 0.95 and abs(best[1]) <= 0.05
    return {"method": "whole-clip mean-luma curve cross-correlation (original timeline vs LRF, lag ±0.5 s step 1/60 s)",
            "samples": int(len(ot)), "best_corr": round(best[0], 4), "best_lag_s": round(best[1], 4),
            "rule": "corr>=0.95 and |lag|<=0.05 s", "passed": bool(ok)}


def check(v, proxy):
    vis = read_json(TEMP / "visual" / f"{v['clip_id']}.json")
    lrf = PROCESS.parent / proxy["proxy_path"]
    pts = []
    for label in ("start", "q1", "mid", "q3", "end"):
        s = next((x for x in vis["sample_times"] if label in x["reasons"]), None)
        if not s or any(p["t"] == s["t"] for p in pts):
            continue
        img = cv2.imread(str(PROCESS.parent / s["frame"]), cv2.IMREAD_GRAYSCALE)
        a = cv2.resize(img, (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)
        cands = [(ncc(a, f), t) for t, f in lrf_window(lrf, s["t"], v["duration"], proxy["proxy_fps"] or 29.97)]
        best = (None, None)
        if cands:
            top = max(c for c, _ in cands)
            # static content ties: among near-equal matches take the one closest to zero offset
            best = min((c for c in cands if c[0] >= top - 0.002), key=lambda c: abs(c[1] - s["t"]))
        pts.append({"label": label, "t": s["t"], "best_ncc": round(best[0], 3) if best[0] is not None else None,
                    "best_lrf_t": best[1], "offset_s": round(best[1] - s["t"], 3) if best[1] is not None else None})
    good = [p for p in pts if p["best_ncc"] is not None and p["best_ncc"] >= PARAMS["ncc_min"]]
    offs = [p["offset_s"] for p in good]
    need = min(PARAMS["min_points"], len(pts))
    med = float(np.median(offs)) if offs else None
    spread = float(max(offs) - min(offs)) if offs else None
    passed = len(good) >= need and med is not None and abs(med) <= PARAMS["max_offset"] and spread <= PARAMS["max_offset"]
    luma = None
    if not passed:
        luma = luma_series_check(v, vis, lrf)
        passed = luma["passed"]
    return {"clip_id": v["clip_id"], "proxy_path": proxy["proxy_path"], "params": PARAMS,
            "secondary_luma_timeseries_check": luma,
            "method": "original sample frame vs every LRF frame within ±0.5 s; grayscale 64x36 NCC; best match + offset",
            "points": pts, "good_points": len(good), "median_offset_s": round(med, 3) if med is not None else None,
            "offset_spread_s": round(spread, 3) if spread is not None else None, "passed": bool(passed)}


def main():
    cat = read_json(TEMP / "catalog.json")
    prox = {p["source_path"]: p for p in cat["proxies"] if p.get("source_path")}
    jobs = [(v, prox[v["source_path"]]) for v in cat["videos"] if v["source_path"] in prox]
    (TEMP / "proxy_check").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(6) as pool:
        res = list(pool.map(lambda a: check(*a), jobs))
    for r in res:
        write_json(TEMP / "proxy_check" / f"{r['clip_id']}.json", r)
    fails = [r for r in res if not r["passed"]]
    print(f"checked {len(res)} passed {len(res)-len(fails)} failed {len(fails)}")
    for r in fails:
        print(r["clip_id"], r["good_points"], r["median_offset_s"], [(p["label"], p["best_ncc"], p["offset_s"]) for p in r["points"]])


if __name__ == "__main__":
    main()
