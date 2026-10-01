#!/usr/bin/env python3
"""Stage 0B step 1b: densify long clips for intra-clip segmentation.

User footage often holds several activities in one continuous take at the same
place (gradual transitions that histogram scene detection misses). For every
clip >= 60 s, add one frame every 10 s wherever no planned frame lies within
4 s. Frames/requests are APPENDED to plan.json with new ids (existing request
ids and checkpoints are untouched) and attached to the clip's whole-clip region
with sampling reason "segment_densify_10s".
"""
from __future__ import annotations

from common0b import IN0A, TEMP, load_json, read_json, write_json

MIN_DUR, STEP, NEAR = 60.0, 10.0, 4.0


def main():
    plan = read_json(TEMP / "plan.json")
    if plan["params"].get("densify"):
        print("already densified")
        return
    vids = {v["clip_id"]: v for v in load_json(IN0A / "metadata_catalog.json")["videos"]}
    have = {}
    for f in plan["frames"]:
        have.setdefault(f["clip_id"], []).append(f["t"])
    whole = {r["clip_id"]: r for r in plan["regions"] if r["scope"] == "whole_clip_coverage"}
    next_id = 10001
    added = 0
    for cid, v in vids.items():
        if v["duration"] < MIN_DUR:
            continue
        num, den = (int(x) for x in v["fps_rational"].split("/"))
        last = max(0, int(v["video_duration"] * num / den) - 1)
        t = STEP / 2
        while t < v["duration"] - 1:
            if not any(abs(t - x) <= NEAR for x in have.get(cid, [])):
                n = min(last, round(t * num / den))
                ts = round(n * den / num, 4)
                fid = f"{cid}@{n}"
                plan["frames"].append({"frame_id": fid, "clip_id": cid, "source_path": v["source_path"], "t": ts, "n": n})
                plan["requests"].append({"request_id": f"Q{next_id:05d}", "clip_id": cid, "frame_ids": [fid], "times": [ts]})
                whole[cid]["samples"].append({"t": ts, "n": n, "reason": "segment_densify_10s", "t_used": ts, "frame_id": fid})
                have.setdefault(cid, []).append(ts)
                next_id += 1
                added += 1
            t += STEP
    plan["params"]["densify"] = {"min_clip_s": MIN_DUR, "step_s": STEP, "near_s": NEAR, "added_frames": added,
                                 "reason": "intra-clip activity segmentation for long continuous takes"}
    write_json(TEMP / "plan.json", plan)
    print(f"added {added} frames/requests; total requests {len(plan['requests'])}")


if __name__ == "__main__":
    main()
