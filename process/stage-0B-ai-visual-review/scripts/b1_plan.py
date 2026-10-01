#!/usr/bin/env python3
"""Stage 0B step 1: sampling plan.

Turns every Stage 0A review-queue item into a review region with explicit
sample_times + sampling_reason, snaps every time onto the native frame grid of
the original, dedupes frames shared between regions, and groups frames into
VLM requests of <= max_frames_per_request (consecutive frames of one clip).

Output: temp/stage0b/plan.json
"""
from __future__ import annotations

from collections import defaultdict

from common0b import IN0A, TEMP, load_json, write_json

MAX_FRAMES = 1                # plan A: one frame per request (2-frame requests made qwen copy frame 1 into frame 2)
BASELINE_WHOLE = 30.0       # whole-clip coverage: front/mid/back + every 30 s
DEDUPE = 1.0                # frames closer than this are shared between regions
PAIR_GAP_MAX = 3.0          # consecutive frames within 3 s are sent together (temporal change is asked)
ACTION_REASONS = {"possible_interaction_multi_person", "child_candidate", "fast_camera_turn_or_change",
                  "animal_candidate", "untranscribed_vocal_or_sound_activity"}


def main():
    cat = load_json(IN0A / "metadata_catalog.json")
    vc = {c["clip_id"]: c for c in load_json(IN0A / "local_visual_candidates.json")["clips"]}
    queue = load_json(IN0A / "stage0b_review_queue.json")["items"]
    vids = {v["clip_id"]: v for v in cat["videos"]}

    def snap(cid, t):
        v = vids[cid]
        num, den = (int(x) for x in v["fps_rational"].split("/"))
        last = max(0, int(v["video_duration"] * num / den) - 1)
        n = min(last, max(0, round(t * num / den)))
        return n, round(n * den / num, 4)

    regions = []
    for q in queue:
        cid, a, b = q["clip_id"], q["start"], q["end"]
        dur = vids[cid]["duration"]
        pts = []
        if q["scope"] == "whole_clip_coverage":
            for lbl, x in (("front", min(0.5, dur / 2)), ("mid", dur * .5), ("back", max(0, dur - 0.5))):
                pts.append((x, lbl))
            x = BASELINE_WHOLE
            while x < dur - 1:
                pts.append((x, "baseline_30s"))
                x += BASELINE_WHOLE
            for s in vc[cid]["visual_actions"]["camera_and_change_events"]:
                if s["type"] == "large_visual_change":
                    for x in s["times"]:
                        pts.append((x, "scene_change_0a"))
        else:
            L = b - a
            if L >= 12:
                pts += [(a + 0.3, "region_front"), ((a + b) / 2, "region_mid"), (b - 0.3, "region_back")]
            elif L >= 6:
                pts += [(a + L * .25, "region_front"), (a + L * .75, "region_back")]
            else:
                pts += [((a + b) / 2, "region_mid")]
        snapped = []
        for x, lbl in pts:
            n, t = snap(cid, x)
            snapped.append({"t": t, "n": n, "reason": lbl})
        regions.append({"region_id": "R" + q["queue_id"][1:], "queue_id": q["queue_id"], "scope": q["scope"],
                        "clip_id": cid, "source_path": q["source_path"], "start": a, "end": b,
                        "priority": q["priority"], "queue_reasons": q["reasons"], "samples": snapped})

    # dedupe frames per clip
    frames = defaultdict(list)   # cid -> list of {t,n}
    for r in regions:
        for s in r["samples"]:
            fl = frames[r["clip_id"]]
            hit = next((f for f in fl if abs(f["t"] - s["t"]) <= DEDUPE), None)
            if hit is None:
                hit = {"t": s["t"], "n": s["n"], "frame_id": None}
                fl.append(hit)
            s["frame_ref"] = (r["clip_id"], hit["t"])
            s["t_used"] = hit["t"]
    frame_list, requests = [], []
    for cid, fl in frames.items():
        fl.sort(key=lambda f: f["t"])
        for i, f in enumerate(fl):
            f["frame_id"] = f"{cid}@{f['n']}"
            frame_list.append({"frame_id": f["frame_id"], "clip_id": cid, "source_path": vids[cid]["source_path"],
                               "t": f["t"], "n": f["n"]})
        i = 0
        while i < len(fl):
            grp = [fl[i]]
            while len(grp) < MAX_FRAMES and i + len(grp) < len(fl) and fl[i + len(grp)]["t"] - grp[-1]["t"] <= PAIR_GAP_MAX:
                grp.append(fl[i + len(grp)])
            requests.append({"request_id": f"Q{len(requests)+1:05d}", "clip_id": cid,
                             "frame_ids": [g["frame_id"] for g in grp], "times": [g["t"] for g in grp]})
            i += len(grp)
    fid = {(f["clip_id"], f["t"]): f["frame_id"] for f in frame_list}
    for r in regions:
        for s in r["samples"]:
            s["frame_id"] = fid[tuple(s.pop("frame_ref"))]
    write_json(TEMP / "plan.json", {"params": {"max_frames_per_request": MAX_FRAMES, "baseline_whole_s": BASELINE_WHOLE,
                                               "dedupe_s": DEDUPE, "pair_gap_max_s": PAIR_GAP_MAX},
                                    "regions": regions, "frames": frame_list, "requests": requests})
    print(f"regions {len(regions)} unique frames {len(frame_list)} requests {len(requests)} "
          f"(pairs {sum(1 for r in requests if len(r['frame_ids'])==2)})")


if __name__ == "__main__":
    main()
