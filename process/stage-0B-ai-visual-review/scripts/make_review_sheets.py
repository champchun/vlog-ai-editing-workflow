#!/usr/bin/env python3
"""Stage 0B helper: pick review frames from Stage 0A samples and build labelled contact sheets
(for the agent to look at actual pixels). Writes selection.json + sheets under temp/stage0b."""
import json, os, sys, cv2, numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
WS = os.path.join(ROOT, "workspace"); A = os.path.join(WS, "project-output/stage0a_output")
T = os.path.join(WS, "temp/stage0b/sheets"); os.makedirs(T, exist_ok=True)
vis = json.load(open(os.path.join(A, "local_visual_candidates.json")))
sel = {}
for v in vis:
    fr = sorted(v["sample_frames"], key=lambda s: s["t"]); dur = None
    cap = 12 if len(fr) <= 40 else 24
    keep = [fr[0]]
    for s in fr[1:]:
        if s["t"] - keep[-1]["t"] >= 1.2: keep.append(s)
    if len(keep) > cap:
        idx = np.linspace(0, len(keep) - 1, cap).round().astype(int); keep = [keep[i] for i in sorted(set(idx))]
    sel[v["clip_id"]] = dict(file=v["file"], frames=[dict(t=s["t"], frame=s["frame"], reason=s["reason"]) for s in keep])
json.dump(sel, open(os.path.join(ROOT, "workspace/temp/stage0b/selection.json"), "w"), ensure_ascii=False, indent=1)
# sheets: 12 frames per sheet (4x3, 480x270); one clip per sheet group
n = 0
for cid, d in sel.items():
    fr = d["frames"]
    for part in range(0, len(fr), 12):
        chunk = fr[part:part + 12]; ims = []
        for s in chunk:
            im = cv2.resize(cv2.imread(os.path.join(ROOT, s["frame"])), (480, 270))
            cv2.rectangle(im, (0, 0), (150, 26), (0, 0, 0), -1)
            cv2.putText(im, f"{cid} t={s['t']:.1f}", (4, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
            ims.append(im)
        cols = 4 if len(ims) > 6 else 3
        while len(ims) % cols: ims.append(np.zeros((270, 480, 3), np.uint8))
        sheet = np.vstack([np.hstack(ims[i:i + cols]) for i in range(0, len(ims), cols)])
        cv2.imwrite(os.path.join(T, f"{cid}_{part // 12 + 1}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 82]); n += 1
print("clips", len(sel), "frames", sum(len(d["frames"]) for d in sel.values()), "sheets", n)
