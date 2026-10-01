#!/usr/bin/env python3
"""Stage 0C step 1: deterministic grouping of footage units into Event groups.

Units: each agent-reviewed segment of clips >= 60 s, and each whole clip < 60 s.
Units are ordered by absolute time (creation_time_utc) and joined into one group
only when ALL hold: same local date; gap between units <= 5 min; GPS distance
<= 300 m when both have coordinates; and the activity text is similar enough
(char-bigram Jaccard >= 0.12 against the group so far) OR the gap is <= 45 s
(continuous shooting of the same moment). Different agent segments of one clip
are separate units (they were split because the activity changed), so they only
re-join when the text similarity rule says so. Grouping never deletes footage.

Output: temp/stage0c/groups.json
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROCESS = Path(__file__).resolve().parents[2]
REPO = PROCESS.parent
sys.path.insert(0, str(PROCESS / "stage-0A-local-pre-analysis" / "scripts"))
from common import read_json, write_json  # noqa: E402

W = PROCESS / "workspace"
IN0A, IN0B = W / "project-output/stage0a_output", W / "project-output/stage0b_output"
TEMP = W / "temp/stage0c"
GAP_MAX, GAP_CONT, DIST_MAX, SIM_MIN = 300.0, 45.0, 300.0, 0.12


def bigrams(s):
    s = "".join(ch for ch in (s or "") if not ch.isspace() and ch not in "，。、；：！？,.()（）")
    return {s[i:i + 2] for i in range(len(s) - 1)}


def jacc(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def dist(a, b):
    if not a or not b:
        return None
    R = 6371000
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def main():
    cat = read_json(IN0A / "metadata_catalog.json")
    rev = read_json(IN0B / "ai_visual_review.json")
    segs = {s["clip_id"]: s for s in rev["intra_clip_segments"]}
    whole = {r["clip_id"]: r for r in rev["regions"] if r["scope"] == "whole_clip_coverage"}
    units = []
    for v in cat["videos"]:
        t0 = datetime.fromisoformat(v["creation_time_utc"].replace("Z", "+00:00"))
        off = v["derived_tz_offset"] or "+00:00"
        sign = 1 if off[0] == "+" else -1
        tz = timedelta(hours=int(off[1:3]), minutes=int(off[4:6])) * sign
        local_date = (t0 + tz).date().isoformat()
        g = v.get("gps")
        gps = {"lat": g["lat"], "lon": g["lon"], "method": g.get("method")} if g else None
        if v["clip_id"] in segs and segs[v["clip_id"]]["segments"]:
            for s in segs[v["clip_id"]]["segments"]:
                units.append({"unit_id": s["segment_id"], "clip_id": v["clip_id"], "source_path": v["source_path"],
                              "start": float(s["start"]), "end": float(s["end"]), "abs_start": t0 + timedelta(seconds=float(s["start"])),
                              "local_date": local_date, "tz": off, "gps": gps, "text": s["activity_zh"],
                              "text_source": "agent_segment"})
        else:
            r = whole[v["clip_id"]]
            units.append({"unit_id": f"{v['clip_id']}#W", "clip_id": v["clip_id"], "source_path": v["source_path"],
                          "start": 0.0, "end": v["duration"], "abs_start": t0, "local_date": local_date, "tz": off, "gps": gps,
                          "text": r["visual_summary"], "text_source": "vlm_whole_clip" + ("+agent" if r["provenance"]["agent_review"] else "")})
    units.sort(key=lambda u: u["abs_start"])
    groups, cur = [], None
    for u in units:
        u["abs_end"] = u["abs_start"] + timedelta(seconds=u["end"] - u["start"])
        join, why = False, "first"
        if cur:
            last = cur["units"][-1]
            gap = (u["abs_start"] - last["abs_end"]).total_seconds()
            d = dist(u["gps"], last["gps"])
            sim = max(jacc(bigrams(u["text"]), bigrams(x["text"])) for x in cur["units"][-3:])
            same_clip_next_seg = u["clip_id"] == last["clip_id"]
            if u["local_date"] != last["local_date"]:
                why = "date_change"
            elif gap > GAP_MAX:
                why = f"gap {gap:.0f}s"
            elif d is not None and d > DIST_MAX:
                why = f"gps {d:.0f}m"
            elif same_clip_next_seg and sim < 0.25:
                why = f"agent segment boundary (sim {sim:.2f})"
            elif sim >= SIM_MIN or (gap <= GAP_CONT and not same_clip_next_seg):
                join, why = True, f"gap {gap:.0f}s sim {sim:.2f}"
            else:
                why = f"activity change (sim {sim:.2f}, gap {gap:.0f}s)"
        if join:
            cur["units"].append(u)
            cur["join_reasons"].append(why)
        else:
            cur = {"units": [u], "join_reasons": [], "split_reason": why}
            groups.append(cur)
    out = []
    for i, g in enumerate(groups, 1):
        us = g["units"]
        out.append({"group_id": f"G{i:03d}", "local_date": us[0]["local_date"], "tz": us[0]["tz"],
                    "abs_start": us[0]["abs_start"].isoformat(), "abs_end": us[-1]["abs_end"].isoformat(),
                    "duration_footage_s": round(sum(u["end"] - u["start"] for u in us), 1),
                    "split_reason": g["split_reason"], "join_reasons": g["join_reasons"],
                    "units": [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in u.items()} for u in us]})
    write_json(TEMP / "groups.json", {"rules": __doc__, "units": len(units), "groups": out})
    from collections import Counter
    print("units", len(units), "groups", len(out))
    print("per day", dict(Counter(g["local_date"] for g in out)))
    print("units per group", dict(sorted(Counter(len(g["units"]) for g in out).items())))
    print("largest", sorted(((len(g["units"]), g["group_id"], g["duration_footage_s"]) for g in out), reverse=True)[:5])


if __name__ == "__main__":
    main()
