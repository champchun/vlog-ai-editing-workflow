#!/usr/bin/env python3
"""Stage 0B hero round 2: dense frames pulled from the ORIGINAL clips around each VLM/agent nomination."""
import json, os, subprocess, cv2, numpy as np, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
WS = os.path.join(ROOT, "workspace"); cat = {c["clip_id"]: c for c in json.load(open(os.path.join(WS, "project-output/stage0a_output/metadata_catalog.json")))["clips"]}
T = os.path.join(WS, "temp/stage0b/hero"); os.makedirs(T, exist_ok=True)
C = {"HC01": ("V022", [0.5, 1.5, 2.5, 3.2, 3.8, 4.5, 5.5, 7, 10, 20, 30, 45]),
     "HC02": ("V011", [9, 11, 13, 15, 17, 19, 21, 23, 25, 26.5, 27.5, 28.5]),
     "HC03": ("V009", [9.0, 10.5, 12, 13, 14, 14.8, 15.6, 16.5, 17.5, 18.5, 19]),
     "HC04": ("V003", [5, 6, 7, 8, 9, 10, 11, 12, 13, 13.8]),
     "HC05": ("V035", [0.3, 1.5, 3, 4, 5, 6, 7, 8, 9, 10])}
for hid, (cid, ts) in C.items():
    f = os.path.join(ROOT, cat[cid]["source_path"]); ims = []
    for t in ts:
        jp = os.path.join(T, f"{hid}_{int(t*10):04d}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", f, "-frames:v", "1", "-vf", "scale=480:-2", jp], capture_output=True)
        im = cv2.imread(jp)
        if im is None: im = np.zeros((270, 480, 3), np.uint8)
        im = cv2.resize(im, (480, 270)); cv2.rectangle(im, (0, 0), (170, 26), (0, 0, 0), -1)
        cv2.putText(im, f"{hid} {cid} t={t}", (4, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1); ims.append(im)
    while len(ims) % 4: ims.append(np.zeros((270, 480, 3), np.uint8))
    cv2.imwrite(os.path.join(T, f"{hid}.jpg"), np.vstack([np.hstack(ims[i:i+4]) for i in range(0, len(ims), 4)]), [cv2.IMWRITE_JPEG_QUALITY, 82])
print("ok")
