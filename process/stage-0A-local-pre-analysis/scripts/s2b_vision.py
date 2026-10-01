#!/usr/bin/env python3
"""Stage 0A step 2b: run macOS Vision candidate labelling on the sampled
display-levelled frames produced by s2_visual.py.

Per-clip cache: temp/stage0a/vision/<clip_id>.json
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from common import PROCESS, TEMP, read_json, write_json

HERE = Path(__file__).resolve().parent
SWIFT_SRC = HERE / "vision_labels.swift"
BIN = TEMP / "bin" / "vision_labels"


def ensure_bin():
    if not BIN.exists() or BIN.stat().st_mtime < SWIFT_SRC.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(SWIFT_SRC), "-o", str(BIN)], check=True)


def main():
    ensure_bin()
    tool_hash = "sha256:" + hashlib.sha256(SWIFT_SRC.read_bytes()).hexdigest()
    sw = subprocess.run(["swift", "--version"], capture_output=True, text=True).stdout.strip().split("\n")[0]
    osv = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True).stdout.strip()
    cat = read_json(TEMP / "catalog.json")
    todo = []
    for v in cat["videos"]:
        vis = read_json(TEMP / "visual" / f"{v['clip_id']}.json")
        if not vis or vis.get("error"):
            continue
        op = TEMP / "vision" / f"{v['clip_id']}.json"
        key = vis["cache_key"] + tool_hash[-12:]
        old = read_json(op)
        if old and old.get("cache_key") == key:
            continue
        todo.append((v["clip_id"], vis, op, key))
    if not todo:
        print("nothing to do")
        return
    frames = [(cid, s) for cid, vis, _, _ in todo for s in vis["sample_times"]]
    p = subprocess.Popen([str(BIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, cwd=PROCESS.parent)
    inp = "\n".join(s["view_frame"] for _, s in frames) + "\n"
    out, _ = p.communicate(inp)
    by_path = {}
    for line in out.splitlines():
        d = json.loads(line)
        by_path[d.pop("path")] = d
    for cid, vis, op, key in todo:
        res = []
        for s in vis["sample_times"]:
            d = by_path.get(s["view_frame"], {"error": "missing"})
            res.append({"t": s["t"], "frame": s["frame"], **d})
        write_json(op, {"clip_id": cid, "cache_key": key,
                        "tool": {"name": "macOS Vision (VNDetectFaceRectangles, VNDetectHumanRectangles, "
                                         "VNRecognizeAnimals, VNClassifyImage, VNRecognizeText accurate)",
                                 "source": str(SWIFT_SRC.relative_to(PROCESS.parent)), "source_hash": tool_hash,
                                 "swift": sw, "macos": osv,
                                 "input": "display-levelled 640x360 frames decoded from the original source"},
                        "frames": res})
    print(f"labelled {len(frames)} frames across {len(todo)} clips")


if __name__ == "__main__":
    main()
