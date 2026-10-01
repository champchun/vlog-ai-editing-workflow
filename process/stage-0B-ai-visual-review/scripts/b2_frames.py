#!/usr/bin/env python3
"""Stage 0B step 2: extract review frames from the ORIGINAL source.

Each planned frame is decoded at its exact native frame index (accurate seek to
half a frame before its pts, first frame taken; pts verified with showinfo),
scaled to 960x540 (aspect kept) and converted for REVIEW DISPLAY ONLY with the
DJI technical LUT that matches the clip's camera-confirmed color_profile
(Stage 0A: Keys/com.dji.camera.ColorGammaSxS). Clips with unknown profile get
no LUT. This is not a grade and never a render source.

Output: temp/stage0b/frames/<clip_id>/n<frame>.jpg + temp/stage0b/frames_manifest.json
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

from common0b import IN0A, PROCESS, REPO, TEMP, load_json, read_json, write_json

LUT_DIR = PROCESS / "stage-3-final-color-mix" / "assets" / "lut"
LUTS = {"D-Log": "DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube",
        "D-Log2": "DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube"}
LUT_CAMERA = "PP-041"   # both LUTs are for DJI Osmo Pocket 4P
EDGE = 960


def sha(p):
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def extract(f, v):
    out = TEMP / "frames" / f["clip_id"] / f"n{f['n']:06d}.jpg"
    if out.exists() and out.stat().st_size > 0 and out.with_suffix(".pts").exists():
        return {**f, "path": str(out.relative_to(REPO)), "pts": float(out.with_suffix(".pts").read_text()), "cached": True}
    num, den = (int(x) for x in v["fps_rational"].split("/"))
    ss = max(0.0, f["t"] - 0.5 * den / num)
    prof = v["color_profile"]
    lut = LUTS.get(prof) if v["source_id"]["camera_model"] == LUT_CAMERA else None
    vf = f"scale={EDGE}:-2:flags=lanczos,showinfo"
    if lut:
        vf += f",format=rgb48le,lut3d=file='{lut}'"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "info", "-nostdin", "-y", "-hwaccel", "videotoolbox", "-copyts", "-ss", f"{ss:.4f}", "-i", str(REPO / v["source_path"]),
           "-map", "0:v:0", "-frames:v", "1", "-vf", vf, "-q:v", "3", str(out)]
    r = subprocess.run(cmd, capture_output=True, cwd=LUT_DIR)
    m = re.search(rb"pts_time:\s*([0-9.]+)", r.stderr)
    pts = float(m.group(1)) if m else None
    if r.returncode or pts is None:
        return {**f, "error": r.stderr.decode(errors="ignore")[-300:]}
    out.with_suffix(".pts").write_text(str(pts))
    return {**f, "path": str(out.relative_to(REPO)), "pts": pts, "lut": lut, "color_profile": prof, "cached": False}


def main():
    plan = read_json(TEMP / "plan.json")
    vids = {v["clip_id"]: v for v in load_json(IN0A / "metadata_catalog.json")["videos"]}
    with ThreadPoolExecutor(4) as pool:
        res = list(pool.map(lambda f: extract(f, vids[f["clip_id"]]), plan["frames"]))
    errs = [r for r in res if r.get("error")]
    off = [r for r in res if not r.get("error") and abs(r["pts"] - r["t"]) > 0.002]
    write_json(TEMP / "frames_manifest.json", {
        "method": "accurate seek to t-0.5 frame, first decoded frame; pts verified via showinfo; 960px long edge; "
                  "review-display LUT per camera-confirmed profile",
        "luts": {k: {"file": str((LUT_DIR / n).relative_to(REPO)), "hash": sha(LUT_DIR / n)} for k, n in LUTS.items()},
        "frames": res, "errors": len(errs), "pts_mismatch": len(off)})
    print(f"frames {len(res)} errors {len(errs)} pts_mismatch {len(off)}")
    for r in (errs + off)[:10]:
        print(r)


if __name__ == "__main__":
    main()
