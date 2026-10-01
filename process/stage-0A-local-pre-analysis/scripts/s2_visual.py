#!/usr/bin/env python3
"""Stage 0A step 2: technical/candidate visual analysis from the ORIGINAL source.

One ffmpeg pass per clip (VideoToolbox decode, every K-th native frame with
K=round(fps/4), 640px, passthrough timing) piped as raw RGB. Each analysed frame
keeps its native frame index n; t = n * den / num (exact source time, CFR
verified by frame count). Note: the ffmpeg fps filter was NOT used because on
this footage it labels frames ~0.1 s earlier than their real source time.
Metrics per analysed frame: luma mean, dark/over-exposed fraction, Laplacian
sharpness, global motion (phase correlation), histogram change, low-texture
fraction. Representative frames (raw + display-levelled _view) are written to
temp/stage0a/frames/<clip_id>/ (rebuildable cache, never a render source).
 LRF proxy verification lives in s2c_proxy_check.py.

Per-clip cache: temp/stage0a/visual/<clip_id>.json
"""
from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from common import PROCESS, TEMP, cache_key, read_json, write_json

W, H, FPS = 640, 360, 4.0
BASE_INTERVAL = 10.0   # baseline coverage: one kept frame at least every 10 s
PARAMS = {"w": W, "h": H, "target_fps": FPS, "sampling": "native frame index every K=round(fps/4)",
          "base": BASE_INTERVAL, "rev": 5}


def auto_levels(rgb):
    """Display-only 1-99 percentile stretch (flat D-Log is hard to read). Not a grade."""
    lo, hi = np.percentile(rgb, (1, 99))
    return np.clip((rgb.astype(np.float32) - lo) * 255.0 / max(hi - lo, 1), 0, 255).astype(np.uint8)


def decode_frames(src: Path, step: int, hw: bool = True):
    vf = f"select='not(mod(n\\,{step}))',scale={W}:{H}:flags=area,format=rgb24"
    cmd = ["ffmpeg", "-v", "error", "-nostdin"] + (["-hwaccel", "videotoolbox"] if hw else []) + \
          ["-i", str(src), "-map", "0:v:0", "-vf", vf, "-fps_mode", "passthrough", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(p.stderr.read().decode()[-500:])


def analyse(v: dict, proxy: dict | None):
    src = PROCESS.parent / v["source_path"]
    dur = v["duration"]
    fdir = TEMP / "frames" / v["clip_id"]
    fdir.mkdir(parents=True, exist_ok=True)
    rows, keep_small = [], {}
    prev_gray, prev_hist = None, None
    num, den = (int(x) for x in v["fps_rational"].split("/"))
    fps = num / den
    step = max(1, round(fps / FPS))
    try:
        frames = list(enumerate(decode_frames(src, step)))
    except RuntimeError:
        frames = list(enumerate(decode_frames(src, step, hw=False)))
    expected = int(np.ceil(round(v["video_duration"] * fps) / step))
    timing_check = {"native_fps": v["fps_rational"], "step": step, "decoded": len(frames),
                    "expected_from_duration": expected, "ok": abs(len(frames) - expected) <= 1}
    for i, rgb in frames:
        n_idx = i * step
        t = round(n_idx * den / num, 4)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        g32 = gray.astype(np.float32)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        blocks = gray[: H // 10 * 10, : W // 10 * 10].reshape(H // 10, 10, W // 10, 10).std(axis=(1, 3))
        r = {"t": t, "n": n_idx,
             "luma": round(float(gray.mean()), 1),
             "dark_frac": round(float((gray < 20).mean()), 3),
             "over_frac": round(float((gray > 245).mean()), 3),
             "sharp": round(float(cv2.Laplacian(gray, cv2.CV_32F).var()), 1),
             "lowtex_frac": round(float((blocks < 2.0).mean()), 3)}
        if prev_gray is not None:
            (dx, dy), resp = cv2.phaseCorrelate(prev_gray, g32)
            r["motion"] = round(float(np.hypot(dx, dy)), 2)
            r["hist_change"] = round(1 - float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)), 3)
        else:
            r["motion"], r["hist_change"] = 0.0, 0.0
        rows.append(r)
        keep_small[t] = rgb
        prev_gray, prev_hist = g32, hist
    if not rows:
        raise RuntimeError("no frames decoded")

    motion = np.array([r["motion"] for r in rows])
    # shake = high-frequency jitter of global motion (smooth pans are low)
    jitter = np.abs(np.diff(motion, prepend=motion[0]))
    for r, j in zip(rows, jitter):
        r["jitter"] = round(float(j), 2)
    sharp_ref = np.percentile([r["sharp"] for r in rows], 90) or 1.0

    def bad(r):
        reasons = []
        if r["luma"] < 14 and r["dark_frac"] > 0.85:
            reasons.append("dark")
        if r["over_frac"] > 0.35:
            reasons.append("overexposed")
        if r["sharp"] < 0.15 * sharp_ref and r["sharp"] < 30:
            reasons.append("blur")
        if r["jitter"] > 18:
            reasons.append("shake")
        if r["lowtex_frac"] > 0.85 and not (r["luma"] > 150):
            reasons.append("possible_occlusion_or_featureless")
        return reasons

    for r in rows:
        r["issues"] = bad(r)
    n = len(rows)
    usable = sum(1 for r in rows if not r["issues"]) / n

    # scene change / camera turn candidates
    scene = [r["t"] for r in rows if r["hist_change"] > 0.45]
    fast_turn = [r["t"] for r in rows if r["motion"] > 40]

    # sampling plan: fixed start/25/50/75/end + baseline every 10 s + densified events
    ts = sorted(keep_small)
    def near(x):
        return min(ts, key=lambda k: abs(k - x))
    samples = {}
    for label, x in [("start", 0.5), ("q1", dur * .25), ("mid", dur * .5), ("q3", dur * .75), ("end", dur - 0.5)]:
        samples.setdefault(near(max(0, x)), set()).add(label)
    x = 0.0
    while x < dur:
        samples.setdefault(near(x), set()).add("baseline_10s")
        x += BASE_INTERVAL
    for t in scene:
        samples.setdefault(near(t), set()).add("scene_change")
    for t in fast_turn[:: max(1, len(fast_turn) // 8 or 1)]:
        samples.setdefault(near(t), set()).add("fast_camera_motion")
    sample_list = []
    for t in sorted(samples):
        fn = fdir / f"t{t:08.2f}.jpg"
        fv = fdir / f"t{t:08.2f}_view.jpg"
        cv2.imwrite(str(fn), cv2.cvtColor(keep_small[t], cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        cv2.imwrite(str(fv), cv2.cvtColor(auto_levels(keep_small[t]), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        sample_list.append({"t": t, "reasons": sorted(samples[t]), "frame": str(fn.relative_to(PROCESS.parent)),
                            "view_frame": str(fv.relative_to(PROCESS.parent))})
    gaps = np.diff([0.0] + [s["t"] for s in sample_list] + [dur])

    return {
        "clip_id": v["clip_id"], "source_path": v["source_path"], "duration": dur, "params": PARAMS,
        "analysed_frames": n, "analysed_fps": round(fps / step, 4), "timing_check": timing_check,
        "timeline": rows,
        "summary": {
            "usable_ratio": round(usable, 3),
            "issue_ratios": {k: round(sum(1 for r in rows if k in r["issues"]) / n, 3)
                             for k in ["dark", "overexposed", "blur", "shake", "possible_occlusion_or_featureless"]},
            "luma_mean": round(float(np.mean([r["luma"] for r in rows])), 1),
            "motion_mean": round(float(motion.mean()), 2),
            "scene_change_times": scene,
            "fast_camera_motion_times": fast_turn,
        },
        "sample_times": sample_list,
        "max_sampling_gap_s": round(float(gaps.max()), 2),
    }


def work(args):
    v, _ = args
    op = TEMP / "visual" / f"{v['clip_id']}.json"
    key = cache_key(PROCESS.parent / v["source_path"], PARAMS)
    old = read_json(op)
    if old and old.get("cache_key") == key:
        return v["clip_id"], "cached"
    t0 = time.time()
    try:
        r = analyse(v, None)
    except Exception as e:
        r = {"clip_id": v["clip_id"], "source_path": v["source_path"], "error": repr(e)}
        key = None
    r["cache_key"] = key
    write_json(op, r)
    return v["clip_id"], f"{time.time()-t0:.0f}s {r.get('error','')}"


def main():
    cat = read_json(TEMP / "catalog.json")
    prox = {p["source_path"]: p for p in cat["proxies"] if p.get("source_path")}
    vids = [v for v in cat["videos"] if not v["duplicate_of"]]
    if len(sys.argv) > 1:
        vids = [v for v in vids if v["clip_id"] in sys.argv[1:]]
    (TEMP / "visual").mkdir(parents=True, exist_ok=True)
    workers = 3
    t0 = time.time()
    with ProcessPoolExecutor(workers) as pool:
        for i, (cid, msg) in enumerate(pool.map(work, [(v, prox.get(v["source_path"])) for v in vids])):
            print(f"[{i+1}/{len(vids)}] {cid} {msg} elapsed={(time.time()-t0)/60:.1f}m", flush=True)


if __name__ == "__main__":
    main()
