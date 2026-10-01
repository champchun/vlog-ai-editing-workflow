#!/usr/bin/env python3
"""Stage 0B step 5: deterministic selection of what the reviewing Agent must open.

Categories (fixed rules, no model judgement):
  1 vlm_hero        : VLM hero=true
  2 agent_hero      : >=2 co-occurring 0A/VLM signals in a 15 s window (kids + untranscribed vocal
                      activity, animals, interaction, activity cues in VLM text, camera turn, scenic)
  3 conflict        : VLM vs Stage 0A disagreements, or VLM internal inconsistency
  4 vlm_uncertain   : animal species unsure, readable text claimed, severe quality claim
  5 random_audit    : ~5% stratified by date/clip (content-blind), seed fixed
  + segment_overview: one whole-clip overview per clip >= 180 s (segment boundary check)

Output: temp/stage0b/review_selection.json
"""
from __future__ import annotations

import glob
import json
import random
import re
from collections import defaultdict

from common0b import IN0A, REPO, TEMP, load_json, read_json, write_json

CUE = re.compile(r"笑|玩|跳|跑|餵|喂|抱|親|划|游|潛|丟|追|拍手|驚|衝|爬|滑|踢|盪|騎|接|舉|轉圈|跳舞|潑|浮潛|玩水|玩沙")
SCENIC = re.compile(r"海|沙灘|山|夕陽|日落|天空|雲|海灘|海浪|瀑布|夜景|煙火|燈")
SIMP = set("们这个来时说国对会没见还发经动实门问间开关东车长马鸟鱼猫买卖饮贩机边远场处台湾爱让为从")
ANIMAL_0A = {"cat", "dog", "bird", "fish", "animal", "mammal", "penguin", "dolphin", "turtle", "jellyfish", "shark",
             "seal", "crab", "ibis", "heron", "egret", "camel", "goat", "rabbit", "horse", "cow", "duck"}


def main():
    plan = read_json(TEMP / "plan.json")
    fman = {f["frame_id"]: f for f in read_json(TEMP / "frames_manifest.json")["frames"]}
    vids = {v["clip_id"]: v for v in load_json(IN0A / "metadata_catalog.json")["videos"]}
    tr = load_json(IN0A / "transcript_sentences.json")
    snd = defaultdict(list)
    for e in tr["sound_events"]:
        snd[e["clip_id"]].append((e["start"], e["end"]))
    vlm = {}
    for f in glob.glob(str(TEMP / "vlm" / "Q*.json")):
        d = json.load(open(f))
        if d["status"] == "OK":
            for r in d["results"]:
                vlm[r["frame_ids"][0]] = r["output"]["frames"][0]
    vis0a = {}

    def vframe(cid, t):
        if cid not in vis0a:
            vis0a[cid] = read_json(REPO / "process/workspace/temp/stage0a/vision" / f"{cid}.json") or {"frames": []}
        fr = [x for x in vis0a[cid]["frames"] if abs(x["t"] - t) <= 1.5]
        return min(fr, key=lambda x: abs(x["t"] - t)) if fr else None

    motion = {}

    def fast_turn(cid, t):
        if cid not in motion:
            vis = read_json(REPO / "process/workspace/temp/stage0a/visual" / f"{cid}.json")
            motion[cid] = vis["summary"]["fast_camera_motion_times"] if vis else []
        return any(abs(t - x) <= 3 for x in motion[cid])

    items, per_frame = [], {}
    for fid, o in vlm.items():
        f = fman[fid]
        cid, t = f["clip_id"], f["t"]
        sig = []
        if o["kids"] > 0:
            sig.append("kids")
        if any(a <= t + 3 and b >= t - 3 for a, b in snd[cid]):
            sig.append("untranscribed_vocal_activity")
        if o["animals"]:
            sig.append("animal")
        if o["adults"] + o["kids"] >= 2:
            sig.append("multi_person")
        if CUE.search(o["people_do"] + o["d"]):
            sig.append("activity_cue")
        if fast_turn(cid, t):
            sig.append("camera_turn")
        if o["shot"] in ("wide", "extreme_wide") and o["light"] == "bright" and SCENIC.search(o["d"] + o["env"]):
            sig.append("scenic")
        # conflicts vs 0A
        conf = []
        vf = vframe(cid, t)
        if vf:
            ids = {c["id"].lower() for c in vf.get("classes", []) if c["conf"] >= 0.5}
            a0 = {i for i in ids if i in ANIMAL_0A} | {l["id"].lower() for a in vf.get("animals", []) for l in a["labels"]}
            if a0 and not o["animals"]:
                conf.append("0a_animal_vlm_none:" + ",".join(sorted(a0)))
            if o["animals"] and not a0 and not ids & {"aquarium", "zoo"}:
                conf.append("vlm_animal_0a_none:" + ",".join(o["animals"]))
            if len(vf.get("humans", [])) >= 2 and o["adults"] + o["kids"] == 0:
                conf.append("0a_humans_vlm_zero")
        flags = []
        if o["adults"] + o["kids"] > 0 and o["people_do"].strip() in ("無人", "无人"):
            flags.append("vlm_people_do_unreliable")   # systematic model quirk; represented by random audit
        if sum(ch in SIMP for ch in o["d"] + o["people_do"]) >= 2:
            flags.append("simplified_chinese_output")   # text-form issue, no visual review needed
        unc = []
        if o["animals"] and not o["animal_sure"]:
            unc.append("animal_species_unsure")
        if o["text"]:
            ocr = " ".join(x["text"] for x in (vf or {}).get("text", [])).lower()
            def shared(a):
                a = re.sub(r"\s", "", a.lower())
                return any(a[i:i + 3] in re.sub(r"\s", "", ocr) for i in range(max(1, len(a) - 2))) if len(a) >= 3 else False
            if not any(shared(x) for x in o["text"]):
                unc.append("readable_text_not_corroborated_by_0a_ocr")
        if set(o["q"]) & {"dark", "occlusion"}:
            unc.append("severe_quality_claim")
        per_frame[fid] = {"clip_id": cid, "t": t, "signals": sig, "conflicts": conf, "uncertain": unc, "flags": flags,
                          "hero": o["hero"]}

    # agent hero: windows of 15 s per clip, >=2 distinct strong signals
    strong = {"kids", "untranscribed_vocal_activity", "animal", "activity_cue", "scenic", "camera_turn", "multi_person"}
    weight = {"untranscribed_vocal_activity": 1.5, "activity_cue": 1.2, "animal": 1.2, "scenic": 1.0, "kids": 0.6,
              "multi_person": 0.4, "camera_turn": 0.4}
    by_clip = defaultdict(list)
    for fid, p in per_frame.items():
        by_clip[p["clip_id"]].append((p["t"], fid))
    hero_c = []
    for cid, lst in by_clip.items():
        lst.sort()
        cur = []
        for t, fid in lst + [(1e9, None)]:
            if cur and (fid is None or t - cur[-1][0] > 15 or t - cur[0][0] > 30):
                sigs = set(s for _, f in cur for s in per_frame[f]["signals"]) & strong
                score = sum(weight[s] for s in sigs) + 0.3 * sum(len(set(per_frame[f]["signals"]) & strong) for _, f in cur) / len(cur)
                if len(sigs - {"multi_person", "kids"}) >= 1 and len(sigs) >= 2 and score >= 2.4:
                    hero_c.append({"clip_id": cid, "start": max(0, cur[0][0] - 3), "end": min(vids[cid]["duration"], cur[-1][0] + 3),
                                   "anchor_frames": [f for _, f in cur], "signals": sorted(sigs), "score": round(score, 2),
                                   "vlm_hero_any": any(per_frame[f]["hero"] for _, f in cur)})
                cur = []
            if fid:
                cur.append((t, fid))
    hero_c.sort(key=lambda h: -h["score"])
    # Review budget 60, spread so one long clip/day cannot absorb it: <=2 per clip, >=3 per day when available.
    # Spreading attention is not a quota of heroes; unreviewed candidates are listed, never silently dropped.
    HERO_MAX, PER_CLIP, PER_DAY_MIN = 60, 2, 3
    chosen, per_clip, per_day = [], defaultdict(int), defaultdict(int)
    days = sorted({h["clip_id"][4:12] for h in hero_c})
    for d in days:
        for h in hero_c:
            if per_day[d] >= PER_DAY_MIN:
                break
            if h["clip_id"][4:12] == d and per_clip[h["clip_id"]] < PER_CLIP and h not in chosen:
                chosen.append(h); per_clip[h["clip_id"]] += 1; per_day[d] += 1
    for h in hero_c:
        if len(chosen) >= HERO_MAX:
            break
        if h not in chosen and per_clip[h["clip_id"]] < PER_CLIP:
            chosen.append(h); per_clip[h["clip_id"]] += 1; per_day[h["clip_id"][4:12]] += 1
    hero_overflow = [h for h in hero_c if h not in chosen]
    hero_c = sorted(chosen, key=lambda h: -h["score"])
    for i, h in enumerate(hero_c, 1):
        h["candidate_id"] = f"HC{i:03d}"
        h["nominated_by"] = "vlm+agent_signals" if h["vlm_hero_any"] else "agent_signals"

    conflicts = [{"frame_id": f, **p} for f, p in per_frame.items() if p["conflicts"]]
    uncertain_all = [{"frame_id": f, **p} for f, p in per_frame.items() if p["uncertain"] and not p["conflicts"]]
    rs = random.Random(7)
    UNC_MAX = 48
    uncertain = sorted(rs.sample(uncertain_all, min(UNC_MAX, len(uncertain_all))), key=lambda x: (x["clip_id"], x["t"]))
    unc_ids = {u["frame_id"] for u in uncertain}
    uncertain_not_reviewed = [u["frame_id"] for u in uncertain_all if u["frame_id"] not in unc_ids]
    rnd = random.Random(20261001)
    strata = defaultdict(list)
    for f, p in per_frame.items():
        strata[p["clip_id"][4:12]].append(f)
    audit = []
    for day, fs in sorted(strata.items()):
        k = max(1, round(len(fs) * 0.05))
        audit += rnd.sample(sorted(fs), k)
    overview = [cid for cid, v in vids.items() if v["duration"] >= 180]
    write_json(TEMP / "review_selection.json", {
        "rules": __doc__, "hero_candidates": hero_c, "hero_candidates_not_reviewed_budget": hero_overflow,
        "conflicts": conflicts, "vlm_uncertain": uncertain, "vlm_uncertain_not_reviewed_sampled_out": uncertain_not_reviewed,
        "deterministic_flags": {f: p["flags"] for f, p in per_frame.items() if p["flags"]},
        "random_audit": audit, "segment_overview_clips": overview,
        "counts": {"vlm_hero_frames": sum(1 for p in per_frame.values() if p["hero"]), "hero_candidates": len(hero_c),
                   "hero_overflow": len(hero_overflow), "conflict_frames": len(conflicts), "uncertain_frames": len(uncertain),
                   "uncertain_total": len(uncertain_all), "audit_frames": len(audit),
                   "overview_clips": len(overview)}})
    from collections import Counter
    print(json.dumps({"hero_candidates": len(hero_c), "hero_overflow": len(hero_overflow), "conflicts": len(conflicts),
                      "uncertain": f"{len(uncertain)}/{len(uncertain_all)}",
                      "audit": len(audit), "overview": len(overview)}))
    print("conflict types", Counter(c.split(":")[0] for x in conflicts for c in x["conflicts"]))
    print("uncertain types", Counter(u for x in uncertain for u in x["uncertain"]))
    print("hero score dist", [h["score"] for h in hero_c[:10]], "... min", hero_c[-1]["score"] if hero_c else None)
    print("hero per day", Counter(h["clip_id"][4:12] for h in hero_c))


if __name__ == "__main__":
    main()
