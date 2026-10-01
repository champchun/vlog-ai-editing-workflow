#!/usr/bin/env python3
"""Stage 0B step 6: contact sheets for the Agent's own pixel review.

- hero/<HCxxx>.jpg : 12 frames decoded from the ORIGINAL at exact frame indices,
  evenly spaced over [start-2 s, end+2 s] (context included), review LUT, time labels.
- set/<name>_NN.jpg + .txt : 12 existing review frames per sheet, numbered; the .txt
  lists clip/time and the VLM output for each number (for correction/audit).
- overview/<clip>.jpg : every review frame of a long clip (time-ordered), segment starts
  outlined in red.
All sheets live in temp/stage0b/sheets/ (rebuildable, never a render source).
"""
from __future__ import annotations

import glob
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from common0b import IN0A, PROCESS, REPO, TEMP, load_json, read_json, write_json

LUT_DIR = PROCESS / "stage-3-final-color-mix" / "assets" / "lut"
LUTS = {"D-Log": "DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube",
        "D-Log2": "DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube"}
SH = TEMP / "sheets"
TW, TH = 400, 225


def label(img, text, color=(255, 255, 255)):
    cv2.rectangle(img, (0, 0), (min(img.shape[1], 12 + 11 * len(text)), 26), (0, 0, 0), -1)
    cv2.putText(img, text, (5, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)
    return img


def grid(tiles, cols):
    while len(tiles) % cols:
        tiles.append(np.zeros((TH, TW, 3), np.uint8))
    return np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])


def grab(v, t):
    num, den = (int(x) for x in v["fps_rational"].split("/"))
    n = round(t * num / den)
    ts = n * den / num
    vf = f"scale={TW}:{TH}:flags=area"
    lut = LUTS.get(v["color_profile"]) if v["source_id"]["camera_model"] == "PP-041" else None
    if lut:
        vf += f",format=rgb48le,lut3d=file='{lut}',format=bgr24"
    else:
        vf += ",format=bgr24"
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-hwaccel", "videotoolbox", "-copyts", "-ss", f"{max(0, ts - 0.5 * den / num):.4f}",
           "-i", str(REPO / v["source_path"]), "-map", "0:v:0", "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-"]
    b = subprocess.run(cmd, capture_output=True, cwd=LUT_DIR).stdout
    img = np.frombuffer(b, np.uint8).reshape(TH, TW, 3).copy() if len(b) == TW * TH * 3 else np.zeros((TH, TW, 3), np.uint8)
    return round(ts, 3), n, img


def main():
    sel = read_json(TEMP / "review_selection.json")
    vids = {v["clip_id"]: v for v in load_json(IN0A / "metadata_catalog.json")["videos"]}
    fman = {f["frame_id"]: f for f in read_json(TEMP / "frames_manifest.json")["frames"]}
    vlm = {}
    for f in glob.glob(str(TEMP / "vlm" / "Q*.json")):
        d = json.load(open(f))
        for r in d.get("results") or []:
            vlm[r["frame_ids"][0]] = r["output"]["frames"][0]
    for sub in ("hero", "set", "overview"):
        (SH / sub).mkdir(parents=True, exist_ok=True)
    index = {"hero": {}, "sets": {}, "overview": {}}

    # hero sheets (dense, from original)
    def hero_sheet(h):
        v = vids[h["clip_id"]]
        a, b = max(0.0, h["start"] - 2), min(v["duration"] - 0.05, h["end"] + 2)
        ts = np.linspace(a, b, 12)
        tiles, meta = [], []
        for k, t in enumerate(ts, 1):
            t2, n, img = grab(v, float(t))
            tiles.append(label(img, f"{k} {t2:.1f}s"))
            meta.append({"k": k, "t": t2, "n": n})
        cv2.imwrite(str(SH / "hero" / f"{h['candidate_id']}.jpg"), grid(tiles, 4), [cv2.IMWRITE_JPEG_QUALITY, 82])
        return h["candidate_id"], {"clip_id": h["clip_id"], "range": [round(a, 3), round(b, 3)], "frames": meta,
                                   "path": str((SH / "hero" / f"{h['candidate_id']}.jpg").relative_to(REPO))}
    with ThreadPoolExecutor(4) as pool:
        for cid, m in pool.map(hero_sheet, sel["hero_candidates"]):
            index["hero"][cid] = m

    # numbered sets from existing review frames
    def vtxt(o):
        return (f"d={o['d']} | 大人{o['adults']} 小孩{o['kids']} | 做:{o['people_do']} | 動物:{o['animals']}"
                f"{'' if o['animal_sure'] else '(不確定)'} | 字:{o['text']} | 景:{o['env']} {o['shot']} {o['light']}")
    sets = {"conflict": [(c["frame_id"], "; ".join(c["conflicts"])) for c in sel["conflicts"]],
            "text": [(u["frame_id"], "; ".join(u["uncertain"])) for u in sel["vlm_uncertain"]],
            "audit": [(f, "random_audit") for f in sel["random_audit"]]}
    for name, lst in sets.items():
        for si in range(0, len(lst), 12):
            chunk = lst[si:si + 12]
            tiles, lines = [], []
            for k, (fid, why) in enumerate(chunk, 1):
                f = fman[fid]
                img = cv2.resize(cv2.imread(str(REPO / f["path"])), (TW, TH), interpolation=cv2.INTER_AREA)
                tiles.append(label(img, f"{k}"))
                lines.append(f"{k}. {f['clip_id']} t={f['t']} [{why}] VLM: {vtxt(vlm[fid])}")
            sid = f"{name}_{si // 12 + 1:02d}"
            cv2.imwrite(str(SH / "set" / f"{sid}.jpg"), grid(tiles, 4), [cv2.IMWRITE_JPEG_QUALITY, 82])
            (SH / "set" / f"{sid}.txt").write_text("\n".join(lines), encoding="utf-8")
            index["sets"][sid] = [fid for fid, _ in chunk]

    # long-clip overviews with segment boundaries
    seg = read_json(TEMP / "segments.json")["clips"]
    for cid in sel["segment_overview_clips"]:
        frames = sorted((f for f in fman.values() if f["clip_id"] == cid), key=lambda f: f["t"])
        starts = {s["start"] for s in seg.get(cid, {}).get("segments", [])[1:]}
        tiles = []
        for f in frames[:48]:
            img = cv2.resize(cv2.imread(str(REPO / f["path"])), (TW // 2, TH // 2), interpolation=cv2.INTER_AREA)
            is_start = any(abs(f["t"] - s) < 0.01 for s in starts)
            if is_start:
                cv2.rectangle(img, (0, 0), (img.shape[1] - 1, img.shape[0] - 1), (0, 0, 255), 5)
            cv2.putText(img, f"{f['t']:.0f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
            tiles.append(img)
        cols = 8
        while len(tiles) % cols:
            tiles.append(np.zeros((TH // 2, TW // 2, 3), np.uint8))
        img = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
        cv2.imwrite(str(SH / "overview" / f"{cid}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        index["overview"][cid] = {"frames_shown": [f["frame_id"] for f in frames[:48]], "total_frames": len(frames),
                                  "segment_starts": sorted(starts)}
    write_json(SH / "index.json", index)
    print({k: len(v) for k, v in index.items()})


if __name__ == "__main__":
    main()
