#!/usr/bin/env python3
"""Stage 0B step 4: intra-clip segment candidates for long continuous takes.

For every clip >= 60 s, consecutive review frames are compared on
  - visual change: HSV histogram distance of the review frames (location change, type a)
  - activity change: dissimilarity of the VLM's own 'people_do' / 'objs' / 'env' text and
    people counts (same place, different activity, type b)
  - camera motion from the Stage 0A 4 fps timeline (walking between activities)
Boundaries use a 2-sample window before vs after to ignore single-frame noise;
minimum segment length 20 s. Segments are CANDIDATES (visual structure only),
not Events (Stage 0C) and not selections.

Output: temp/stage0b/segments.json
"""
from __future__ import annotations

import glob
import json

import cv2
import numpy as np

from common0b import IN0A, REPO, TEMP, load_json, read_json, write_json

MIN_DUR, MIN_SEG = 60.0, 20.0


def bigrams(s):
    s = "".join(ch for ch in s if not ch.isspace() and ch not in "，。、；：！？,.")
    return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def jacc(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def hist(path):
    img = cv2.imread(str(REPO / path))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [24, 12], [0, 180, 0, 256])
    return cv2.normalize(h, h).flatten()


def main():
    vids = {v["clip_id"]: v for v in load_json(IN0A / "metadata_catalog.json")["videos"]}
    fman = {f["frame_id"]: f for f in read_json(TEMP / "frames_manifest.json")["frames"]}
    vlm = {}
    for f in glob.glob(str(TEMP / "vlm" / "Q*.json")):
        d = json.load(open(f))
        if d["status"] == "OK":
            for r in d["results"]:
                vlm[r["frame_ids"][0]] = r["output"]["frames"][0]
    out = {}
    for cid, v in vids.items():
        if v["duration"] < MIN_DUR:
            continue
        frames = sorted((f for f in fman.values() if f["clip_id"] == cid and f["frame_id"] in vlm), key=lambda f: f["t"])
        if len(frames) < 4:
            continue
        vis = read_json(REPO / "process/workspace/temp/stage0a/visual" / f"{cid}.json")
        tl = vis["timeline"]
        feats = []
        for f in frames:
            o = vlm[f["frame_id"]]
            feats.append({"t": f["t"], "frame_id": f["frame_id"], "h": hist(f["path"]),
                          "act": bigrams(o["people_do"]) | bigrams(" ".join(o["objs"])),
                          "env": bigrams(o["env"]), "np": o["adults"] + o["kids"], "kids": o["kids"],
                          "d": o["d"], "people_do": o["people_do"],
                          "motion": float(np.mean([r["motion"] for r in tl if abs(r["t"] - f["t"]) <= 3] or [0]))})
        scores = []
        for i in range(1, len(feats)):
            A, B = feats[max(0, i - 2):i], feats[i:i + 2]
            vd = float(np.mean([cv2.compareHist(a["h"], b["h"], cv2.HISTCMP_BHATTACHARYYA) for a in A for b in B]))
            ad = 1 - float(np.mean([jacc(a["act"], b["act"]) for a in A for b in B]))
            ed = 1 - float(np.mean([jacc(a["env"], b["env"]) for a in A for b in B]))
            pd = abs(np.mean([a["np"] for a in A]) - np.mean([b["np"] for b in B]))
            walk = feats[i - 1]["motion"] > 12 or feats[i]["motion"] > 12
            s = 1.2 * vd + 0.6 * ad + 0.5 * ed + 0.25 * min(pd, 2) + (0.2 if walk else 0)
            scores.append({"t_between": round((feats[i - 1]["t"] + feats[i]["t"]) / 2, 2), "i": i, "score": round(s, 3),
                           "visual": round(vd, 3), "activity": round(ad, 3), "env": round(ed, 3),
                           "people_delta": round(float(pd), 2), "camera_walk": walk})
        thr = max(0.95, float(np.percentile([s["score"] for s in scores], 80)))
        cuts, last = [], feats[0]["t"]
        for s in sorted(scores, key=lambda s: -s["score"]):
            if s["score"] < thr:
                break
            tb = feats[s["i"]]["t"]
            if all(abs(tb - c) >= MIN_SEG for c in cuts) and tb - feats[0]["t"] >= MIN_SEG and v["duration"] - tb >= MIN_SEG:
                cuts.append(tb)
        cuts.sort()
        bounds = [0.0] + cuts + [v["duration"]]
        segs = []
        for k in range(len(bounds) - 1):
            a, b = bounds[k], bounds[k + 1]
            inside = [f for f in feats if a <= f["t"] < b] or [min(feats, key=lambda f: abs(f["t"] - (a + b) / 2))]
            acts = list(dict.fromkeys(f["people_do"] for f in inside))
            segs.append({"segment_id": f"{cid}#S{k+1:02d}", "start": round(a, 3), "end": round(b, 3),
                         "frames": [f["frame_id"] for f in inside],
                         "vlm_activities": acts[:5], "vlm_first_summary": inside[0]["d"],
                         "max_people": max(f["np"] for f in inside), "kids_seen": any(f["kids"] for f in inside),
                         "boundary_in": next((s for s in scores if feats[s["i"]]["t"] == a), None)})
        out[cid] = {"duration": v["duration"], "threshold": round(thr, 3), "segments": segs, "boundary_scores": scores}
    write_json(TEMP / "segments.json", {
        "method": "window(2v2) score = 1.2*HSV-hist Bhattacharyya + 0.6*VLM activity-text dissimilarity + 0.5*VLM env-text "
                  "dissimilarity + 0.25*people-count delta + 0.2*camera walking; cut if score >= max(0.95, clip p80); min 20 s",
        "status": "candidate", "clips": out})
    n = sum(len(c["segments"]) for c in out.values())
    print(f"clips {len(out)} segments {n}")
    for cid, c in sorted(out.items(), key=lambda x: -x[1]["duration"])[:6]:
        print(cid, round(c["duration"]), [(s["start"], s["vlm_activities"][:2]) for s in c["segments"]])


if __name__ == "__main__":
    main()
