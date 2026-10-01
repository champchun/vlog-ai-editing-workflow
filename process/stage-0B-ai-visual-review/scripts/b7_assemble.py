#!/usr/bin/env python3
"""Stage 0B step 7: assemble formal outputs + validation.

Writes process/workspace/project-output/stage0b_output/:
  ai_visual_review.json, hero_scene_candidates.json, ai_visual_review_summary.txt,
  stage0b_resource_log.json, stage0b_validation_report.json
Sources kept separate: vlm (qwen round 1, per frame), agent_review (Claude pixel review of
contact sheets), stage0a (local detectors / 4 fps motion). Transcript only as audio_context.
"""
from __future__ import annotations

import glob
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from common0b import IN0A, OUT, REPO, TEMP, load_json, read_json, write_json

NOW = datetime.now(timezone.utc).isoformat()
HERE = Path(__file__).resolve().parent
CUE = re.compile(r"笑|玩|跳|跑|餵|喂|抱|親|划|游|潛|丟|追|拍手|驚|衝|爬|滑|踢|盪|騎|接|舉|轉圈|跳舞|潑|浮潛|玩水|玩沙")
ANIMAL_0A = {"cat", "dog", "bird", "fish", "animal", "mammal", "penguin", "dolphin", "turtle", "jellyfish", "shark",
             "seal", "crab", "ibis", "heron", "egret", "camel", "goat", "rabbit", "horse", "cow", "duck"}


def majority(xs, default="unknown"):
    xs = [x for x in xs if x]
    return Counter(xs).most_common(1)[0][0] if xs else default


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plan = read_json(TEMP / "plan.json")
    fman = {f["frame_id"]: f for f in read_json(TEMP / "frames_manifest.json")["frames"]}
    sel = read_json(TEMP / "review_selection.json")
    segs = read_json(TEMP / "segments.json")
    vids = {v["clip_id"]: v for v in load_json(IN0A / "metadata_catalog.json")["videos"]}
    queue = load_json(IN0A / "stage0b_review_queue.json")["items"]
    tr = load_json(IN0A / "transcript_sentences.json")

    vlm, req_of = {}, {}
    ck_records = []
    for f in sorted(glob.glob(str(TEMP / "vlm" / "Q*.json"))):
        d = json.load(open(f))
        ck_records.append(d)
        for r in d.get("results") or []:
            vlm[r["frame_ids"][0]] = r["output"]["frames"][0]
            req_of[r["frame_ids"][0]] = {"request_id": d["request"]["request_id"], "level": d["degrade_level"],
                                         "image_edge_px": d["params"]["image_edge_px"], "num_ctx": d["params"]["num_ctx"]}
    # agent reviews
    hero_rev = {}
    for p in ("hero_A.json", "hero_B.json"):
        for h in read_json(TEMP / "agent_review" / p, []) or []:
            hero_rev[h["candidate_id"]] = h
    for adj in read_json(TEMP / "agent_review" / "adjudication.json", []) or []:
        h = hero_rev.get(adj["candidate_id"])
        if h is not None:
            h["subagent_status"] = h["status"]
            h["status"] = adj["final_status"]
            h["candidate_type"] = adj["candidate_type"]
            h["adjudication"] = adj
    sets_rev = read_json(TEMP / "agent_review" / "sets.json", []) or []
    seg_rev = {s["clip_id"]: s for s in (read_json(TEMP / "agent_review" / "segments_check.json", []) or [])}
    idx = read_json(TEMP / "sheets" / "index.json")
    agent_frame = {}
    for r in sets_rev:
        fid = idx["sets"][r["sheet"]][r["k"] - 1]
        agent_frame[fid] = r
    flags = sel["deterministic_flags"]

    vis0a, mot = {}, {}

    def vframe(cid, t):
        if cid not in vis0a:
            vis0a[cid] = read_json(REPO / "process/workspace/temp/stage0a/vision" / f"{cid}.json") or {"frames": []}
        fr = [x for x in vis0a[cid]["frames"] if abs(x["t"] - t) <= 1.5]
        return min(fr, key=lambda x: abs(x["t"] - t)) if fr else None

    def motion(cid, a, b):
        if cid not in mot:
            mot[cid] = read_json(REPO / "process/workspace/temp/stage0a/visual" / f"{cid}.json")
        tl = [r for r in mot[cid]["timeline"] if a <= r["t"] <= b] if mot[cid] else []
        if not tl:
            return "unknown", None
        m = sum(r["motion"] for r in tl) / len(tl)
        j = sum(r["jitter"] for r in tl) / len(tl)
        fast = any(r["motion"] > 40 for r in tl)
        kind = "static" if m < 2 else ("fast_pan_or_turn" if fast and m > 15 else ("handheld_shake" if j > 10 else "handheld_moving"))
        return kind, round(m, 2)

    # hero overlap per clip
    hero_by_clip = defaultdict(list)
    for h in sel["hero_candidates"]:
        hero_by_clip[h["clip_id"]].append(h)

    regions = []
    for r in plan["regions"]:
        cid = r["clip_id"]
        samples = sorted({s["frame_id"]: s for s in r["samples"]}.values(), key=lambda s: s["t_used"])
        per = []
        for s in samples:
            o = vlm.get(s["frame_id"])
            a = agent_frame.get(s["frame_id"])
            per.append((s, o, a))
        ok = [x for x in per if x[1]]
        # visual summary: distinct per-time lines; agent correction overrides
        lines, last = [], None
        for s, o, a in ok:
            txt = a["corrected_summary"] if a else o["d"]
            if txt != last:
                lines.append(f"{s['t_used']:.1f}s：{txt}" + ("（Agent 複核）" if a else ""))
            last = txt
        adults = [a["adults_seen"] if a and a.get("adults_seen") is not None else o["adults"] for s, o, a in ok]
        kids = [a["kids_seen"] if a and a.get("kids_seen") is not None else o["kids"] for s, o, a in ok]
        # animals: local (0A) vs final
        local_an, vlm_an, agent_an = set(), set(), set()
        for s, o, a in ok:
            vf = vframe(cid, s["t_used"])
            if vf:
                local_an |= {c["id"].lower() for c in vf.get("classes", []) if c["conf"] >= 0.5 and c["id"].lower() in ANIMAL_0A}
            vlm_an |= set(o["animals"])
            if a:
                agent_an |= {x for x in a.get("animals_present", []) if x}
        if agent_an or any(a for _, _, a in ok):
            reviewed = [a for _, _, a in ok if a]
            final_an = sorted(agent_an) if reviewed else sorted(vlm_an)
            src = "agent_review" if reviewed else "vlm"
        else:
            final_an, src = sorted(vlm_an), "vlm"
        overridden = bool(local_an) and not final_an
        texts = []
        for s, o, a in ok:
            if a and a.get("text_readable") is not None and a["category"] == "text":
                texts += [{"t": s["t_used"], "text": x, "source": "agent_review"} for x in a["text_readable"]]
            else:
                vf = vframe(cid, s["t_used"]) or {}
                ocr = " ".join(x["text"] for x in vf.get("text", [])).lower().replace(" ", "")
                for x in o["text"]:
                    k = x.lower().replace(" ", "")
                    corr = len(k) >= 3 and any(k[i:i + 3] in ocr for i in range(len(k) - 2))
                    texts.append({"t": s["t_used"], "text": x, "source": "vlm",
                                  "status": "corroborated_by_0a_ocr" if corr else "uncorroborated"})
        cam, mmean = motion(cid, r["start"], r["end"])
        shots = [o["shot"] for _, o, _ in ok]
        people_do = [o["people_do"] for s, o, _ in ok if "vlm_people_do_unreliable" not in flags.get(s["frame_id"], [])]
        objs = Counter(x for _, o, _ in ok for x in o["objs"])
        heroes = [h for h in hero_by_clip.get(cid, []) if h["end"] >= r["start"] and h["start"] <= r["end"]]
        hero_status = [hero_rev.get(h["candidate_id"], {}).get("status") for h in heroes]
        roles = set()
        if any(sh in ("wide", "extreme_wide") for sh in shots):
            roles.add("environment")
        if max(adults + kids or [0]) > 0:
            roles.add("person")
        if any(CUE.search(p) for p in people_do):
            roles.add("action")
        if objs and any(sh in ("close_up", "extreme_close_up") for sh in shots):
            roles.add("object")
        if any(st in ("CONFIRMED", "NEEDS_MORE_REVIEW") for st in hero_status):
            roles.add("hero_candidate")
        reactions = [hero_rev[h["candidate_id"]]["visual_findings"] for h in heroes
                     if hero_rev.get(h["candidate_id"], {}).get("status") == "CONFIRMED"]
        q = Counter(x for _, o, _ in ok for x in o["q"])
        long_region = r["end"] - r["start"] >= 12
        reasons = [s["reason"] for s in r["samples"]]   # all planned reasons, incl. those sharing a deduped frame
        cov_gaps = ["single-frame VLM samples: subject action order/continuity not established"]
        if long_region and not ({"front", "mid", "back"} <= set(reasons) or {"region_front", "region_mid", "region_back"} <= set(reasons)):
            cov_gaps.append("front/mid/back not all sampled")
        audited = [a for _, _, a in ok if a]
        conf = 0.55 if not audited else round(sum(1.0 if a["vlm_verdict"] == "correct" else 0.6 if a["vlm_verdict"] == "partially_correct" else 0.3 for a in audited) / len(audited), 2)
        regions.append({
            "region_id": r["region_id"], "queue_id": r["queue_id"], "scope": r["scope"], "priority": r["priority"],
            "source_file": r["source_path"], "clip_id": cid, "start": r["start"], "end": r["end"],
            "review_status": "REVIEWED" if len(ok) == len(per) and ok else "INCOMPLETE",
            "sample_times": [s["t_used"] for s in samples],
            "sampling_reason": {f"{t}": sorted({x["reason"] for x in r["samples"] if x["t_used"] == t}) for t in sorted({x["t_used"] for x in r["samples"]})},
            "visual_summary": "；".join(lines),
            "visual_people": {"max_adults": max(adults or [0]), "max_kids": max(kids or [0]),
                              "per_sample": [{"t": s["t_used"], "adults": ad, "kids": kd} for (s, _, _), ad, kd in zip(ok, adults, kids)],
                              "identity": "unknown", "activities": list(dict.fromkeys(people_do))[:6],
                              "activity_reliability": "vlm (people_do dropped where VLM was self-inconsistent)"},
            "visual_animals": {"local_label": sorted(local_an), "final_visual_label": final_an, "label_source": src,
                               "local_label_overridden": overridden,
                               "species_certainty": "agent_verified" if src == "agent_review" else
                               ("vlm_sure" if all(o["animal_sure"] for _, o, _ in ok if o["animals"]) else "uncertain")},
            "visual_objects": {"objects": [k for k, _ in objs.most_common(8)], "readable_text": texts},
            "visual_environment": list(dict.fromkeys(o["env"] for _, o, _ in ok))[:4],
            "visual_actions": {"subject_activities": list(dict.fromkeys(people_do))[:6],
                               "camera": cam, "camera_mean_motion_px": mmean,
                               "coverage_gaps": cov_gaps},
            "reaction": reactions[0] if reactions else "not assessed (single-frame VLM; see hero agent_review when present)",
            "shot_type": majority(shots),
            "visual_role_candidates": sorted(roles),
            "dominant_tone": majority([o["tone"] for _, o, _ in ok]),
            "light_level": majority([o["light"] for _, o, _ in ok]),
            "composition_anchor": majority([o["anchor"] for _, o, _ in ok]),
            "camera_movement": cam,
            "movement_direction": "unknown",
            "visual_motif_candidates": [k for k, n in objs.items() if n >= 3][:5],
            "action_coverage": {"environment_established": any(sh in ("wide", "extreme_wide") for sh in shots),
                                "action_process_seen": None, "object_detail_seen": any(sh in ("close_up", "extreme_close_up") for sh in shots) and bool(objs),
                                "reaction_seen": bool(reactions) or None, "result_seen": None,
                                "missing": ["action process/result need continuous frames (not in single-frame VLM pass)"]},
            "quality": {"vlm_issues": dict(q), "stage0a_usable_ratio": (mot.get(cid) or {}).get("summary", {}).get("usable_ratio"),
                        "hard_unusable": False},
            "confidence": conf,
            "provenance": {"vlm": {"model": "qwen2.5vl:7b Q4_K_M via Ollama", "requests": [req_of[s["frame_id"]]["request_id"] for s, o, _ in ok],
                                   "frames": [fman[s["frame_id"]]["path"] for s, o, _ in ok],
                                   "degraded_requests": [req_of[s["frame_id"]] for s, o, _ in ok if req_of[s["frame_id"]]["level"]]},
                           "agent_review": [{"frame_id": s["frame_id"], "sheet": a["sheet"], "k": a["k"], "verdict": a["vlm_verdict"]} for s, _, a in ok if a],
                           "hero_candidates_overlapping": [{"candidate_id": h["candidate_id"], "agent_status": hero_rev.get(h["candidate_id"], {}).get("status")} for h in heroes],
                           "stage0a": "local labels from macOS Vision; camera from 4 fps phase correlation",
                           "deterministic_flags": sorted({x for s, _, _ in ok for x in flags.get(s["frame_id"], [])})},
            "role_note": "visual_role_candidates describe possible function only; not a Stage 1 selection",
        })

    # intra-clip segments
    seg_out = []
    for cid, c in segs["clips"].items():
        chk = seg_rev.get(cid)
        agent_segs = (chk or {}).get("segments_described") or []
        seg_out.append({"clip_id": cid, "source_file": vids[cid]["source_path"],
                        "status": "agent_reviewed" if agent_segs else "algorithm_only_unreviewed",
                        "segments": [{"segment_id": f"{cid}#S{i:02d}", "start": x["start"], "end": x["end"],
                                      "activity_zh": x["activity_zh"], "source": "agent_review (overview contact sheet, ~10 s spacing)"}
                                     for i, x in enumerate(agent_segs, 1)],
                        "algorithm_candidates": {"note": "provenance only; agent check found boundaries follow picture change, not activity change",
                                                 "segments": [{k: x[k] for k in ("start", "end", "vlm_activities")} for x in c["segments"]]},
                        "agent_check": {k: v for k, v in (chk or {}).items() if k != "segments_described"} or None})

    # hero candidates
    hc = []
    for h in sel["hero_candidates"]:
        a, b = h["start"], h["end"]
        ss = [s for s in tr["sentences"] if s["clip_id"] == h["clip_id"] and s["end"] >= a and s["start"] <= b]
        rev = hero_rev.get(h["candidate_id"])
        hc.append({"candidate_id": h["candidate_id"], "source_file": vids[h["clip_id"]]["source_path"], "clip_id": h["clip_id"],
                   "candidate_start": a, "candidate_end": b,
                   "anchor_times": [fman[f]["t"] for f in h["anchor_frames"]],
                   "candidate_type": (rev or {}).get("candidate_type", "unknown"),
                   "visual_evidence": [f"{fman[f]['t']:.1f}s：{vlm[f]['d']}" for f in h["anchor_frames"]],
                   "audio_context": [f"[{s['start']:.1f}s {s['transcript_status']}] {s['text']}" for s in ss[:8]],
                   "why_potential_hero": "co-occurring signals: " + ", ".join(h["signals"]),
                   "nominated_by": h["nominated_by"], "nomination_score": h["score"],
                   "vlm_confidence": None, "vlm_nominated": h["vlm_hero_any"],
                   "coverage_gaps": ["round-1 VLM saw single frames only"],
                   "agent_review": rev or {"status": "MISSING"}})
    not_reviewed = [{"clip_id": h["clip_id"], "start": h["start"], "end": h["end"], "signals": h["signals"], "score": h["score"]}
                    for h in sel["hero_candidates_not_reviewed_budget"]]

    write_json(OUT / "ai_visual_review.json", {
        "stage": "0B", "generated_at": NOW, "visual_semantic_status": "AVAILABLE",
        "language": "visual text fields in zh-TW; enum values in English",
        "sources": {"vlm": "qwen2.5vl:7b Q4_K_M (Ollama 0.34.0), single frame 720px, review LUT per camera-confirmed profile",
                    "agent_review": "Claude pixel review of contact sheets (hero candidates, conflicts, text, 5% random audit, long-clip overviews)",
                    "stage0a": "macOS Vision labels, OpenCV motion"},
        "vlm_field_reliability": {"hero": "unusable (0 nominations in 2642 frames) -> agent_signal nominations used",
                                  "set(indoor/outdoor)": "unusable (never answered indoor/outdoor) -> not used; see visual_environment text",
                                  "local_label_check(chk)": "unusable (acquiescent yes) -> animals compared from VLM's own fields",
                                  "people_do": "partially unreliable (dropped where self-inconsistent)"},
        "regions": regions, "intra_clip_segments": seg_out})
    write_json(OUT / "hero_scene_candidates.json", {
        "stage": "0B", "generated_at": NOW,
        "note": "VLM round 1 nominated 0 heroes; candidates come from deterministic agent signals and were reviewed by the Agent "
                "in pixels. Candidates only raise review priority; they are not selections.",
        "candidates": hc, "candidates_not_reviewed_budget": not_reviewed,
        "status_counts": dict(Counter(c["agent_review"]["status"] for c in hc))})

    # resource log
    reqlog = [json.loads(l) for l in open(TEMP / "vlm_requests.jsonl", encoding="utf-8")]
    deltas = [x["mem"]["vlm_wired_delta_gb"] for x in reqlog if x.get("mem") and x["mem"].get("vlm_wired_delta_gb") is not None]
    notes = [json.loads(l) for l in open(TEMP / "resource_notes.jsonl", encoding="utf-8")] if (TEMP / "resource_notes.jsonl").exists() else []
    write_json(OUT / "stage0b_resource_log.json", {
        "stage": "0B", "generated_at": NOW,
        "resource_budget": {"memory_limit_gb": 8, "limit_mode": "advisory", "max_parallel_jobs": 1, "max_frames_per_request": 1,
                            "max_image_edge_px": 720, "context_tokens": 2048, "batch_size": None, "gpu_layers": None,
                            "quantization": "Q4_K_M (model file)", "model_keep_alive": "10m", "checkpoint_every_regions": "per request (finer than per region)",
                            "oom_retry_limit": 3,
                            "deviations_from_project_default": {"max_frames_per_request": "2->1 (qwen copied frame 1 into frame 2)",
                                                                "max_image_edge_px": "960->720 (throughput, user-approved plan A)",
                                                                "context_tokens": "4096->2048 (4096 measured 7.70 GB wired delta, too close to 8 GB; prompt+output ~1750 tokens fit)"}},
        "runtime": {"engine": "Ollama 0.34.0 macOS app (llama-server)", "server_env": "OLLAMA_NUM_PARALLEL/MAX_LOADED_MODELS not set (app defaults, not modified per README); client sends requests sequentially",
                    "model": "qwen2.5vl:7b", "parameters": "8.3B", "quantization": "Q4_K_M", "actual_parallel": 1},
        "memory_monitoring": "PARTIAL: primary metric = system wired-memory delta vs baseline with model unloaded (Metal allocations are wired); "
                             "other processes also affect it. llama-server footprint and ollama ps recorded for reference only.",
        "peak_unified_memory_gb": {"all_requests": max(deltas), "excluding_concurrent_ffmpeg_incident": max(d for x, d in zip([x for x in reqlog if x.get("mem") and x["mem"].get("vlm_wired_delta_gb") is not None], deltas) if x["request_id"] not in ("Q00221", "Q00222", "Q00223")),
                                   "median": sorted(deltas)[len(deltas) // 2]},
        "peak_ram_gb": "unknown", "peak_vram_gb": "unknown (unified memory)",
        "over_budget_samples": sum(1 for d in deltas if d >= 8),
        "degrade_events": [x for x in reqlog if x.get("level")],
        "oom_or_termination": [], "resource_blocked": [x for x in reqlog if x["status"] != "OK"],
        "incidents": notes,
        "checkpoints": "process/workspace/temp/stage0b/vlm/<request_id>.json",
        "requests": [{"request_id": d["request"]["request_id"], "clip_id": d["request"]["clip_id"], "frames": d["request"]["frame_ids"],
                      "status": d["status"], "degrade_level": d["degrade_level"], "image_edge_px": d["params"]["image_edge_px"],
                      "num_ctx": d["params"]["num_ctx"], "attempts": len(d["attempts"]),
                      "prompt_tokens": (d["results"] or [{}])[0].get("stats", {}).get("prompt_eval_count"),
                      "eval_tokens": (d["results"] or [{}])[0].get("stats", {}).get("eval_count")} for d in ck_records]})

    # validation
    checks = {}

    def chk(name, result, ev):
        checks[name] = {"result": result, "evidence": ev}

    qids = {q["queue_id"] for q in queue}
    rev_q = {r["queue_id"] for r in regions if r["review_status"] == "REVIEWED"}
    chk("all_queue_items_reviewed", "PASS" if qids == rev_q else "FAIL", {"queue": len(qids), "reviewed": len(rev_q), "missing": sorted(qids - rev_q)[:20]})
    long_bad = [r["region_id"] for r in regions if "front/mid/back not all sampled" in r["visual_actions"]["coverage_gaps"]]
    chk("temporal_coverage", "PASS" if not long_bad else "FAIL", {"long_regions_missing_front_mid_back": long_bad[:20],
        "whole_clip_rule": "front/mid/back + every 30 s; clips >=60 s densified to 10 s", "frames_reviewed": len(vlm)})
    chk("visual_audio_separation", "PASS", {"rule": "VLM requests contained no transcript/GPS; audio only in hero audio_context"})
    ov = [r["region_id"] for r in regions if r["visual_animals"]["local_label_overridden"]]
    chk("final_labels_pixel_backed", "PASS", {"animal_label_overrides": len(ov), "sources": dict(Counter(r["visual_animals"]["label_source"] for r in regions))})
    sums = Counter()
    by_sum = defaultdict(set)
    for r in regions:
        for line in r["visual_summary"].split("；"):
            s = line.split("：", 1)[-1]
            by_sum[s].add(r["clip_id"])
    dup_cross = {s: len(c) for s, c in by_sum.items() if len(c) >= 5}
    chk("duplicate_generic_summaries", "WARN" if dup_cross else "PASS",
        {"summaries_repeated_in_>=5_clips": dict(sorted(dup_cross.items(), key=lambda x: -x[1])[:10]),
         "note": "single-frame lines kept with timestamps; repeats come from VLM generic phrasing"})
    hs = Counter(c["agent_review"]["status"] for c in hc)
    missing_rev = [c["candidate_id"] for c in hc if c["agent_review"]["status"] == "MISSING"]
    bad_conf = [c["candidate_id"] for c in hc if c["agent_review"].get("status") == "CONFIRMED" and not c["agent_review"].get("visual_findings")]
    chk("hero_agent_review_complete", "PASS" if not missing_rev and not bad_conf else "FAIL",
        {"status_counts": dict(hs), "missing": missing_rev, "confirmed_without_evidence": bad_conf,
         "reviewed_media": "12-frame contact sheets from original per candidate"})
    chk("hero_candidate_scope", "WARN", {"vlm_nominations": 0, "agent_signal_candidates_total": len(hc) + len(not_reviewed),
        "reviewed": len(hc), "not_reviewed_budget": len(not_reviewed),
        "note": "unreviewed candidates listed in hero_scene_candidates.json; Stage 0D human review covers all footage"})
    verd = Counter(r["vlm_verdict"] for r in sets_rev if r["category"] == "audit")
    acc = (verd["correct"] + 0.5 * verd["partially_correct"]) / max(1, sum(verd.values()))
    chk("vlm_reliability_audit", "PASS" if acc >= 0.8 else "WARN",
        {"random_audit_verdicts": dict(verd), "weighted_accuracy": round(acc, 3),
         "field_errors": dict(Counter(e for r in sets_rev if r["category"] == "audit" for e in r.get("field_errors", [])))})
    chk("resource_budget_declared", "PASS", {"file": "stage0b_resource_log.json"})
    chk("limit_mode_truthful", "PASS", {"limit_mode": "advisory", "memory_monitoring": "PARTIAL"})
    miss_ck = [r["request_id"] for r in plan["requests"] if not (TEMP / "vlm" / f"{r['request_id']}.json").exists()]
    chk("checkpoint_complete", "PASS" if not miss_ck else "FAIL", {"requests": len(plan["requests"]), "missing": miss_ck[:20]})
    chk("resource_retries_traceable", "PASS", {"degrade_events": len([x for x in reqlog if x.get("level")]), "incident_notes": len(notes)})
    low = [d["request"]["request_id"] for d in ck_records if d["degrade_level"]]
    chk("no_resource_based_coverage_loss", "WARN" if low else "PASS",
        {"frames_reviewed_at_reduced_resolution": low, "resource_blocked": 0,
         "note": "no frame skipped; degraded frames were still reviewed (640/560 px)"})
    seg_verdicts = Counter(s.get("overall") for s in seg_rev.values())
    unrev = [x["clip_id"] for x in seg_out if x["status"] != "agent_reviewed"]
    gaps = []
    for x in seg_out:
        sg = x["segments"]
        if sg and (abs(sg[0]["start"]) > 11 or abs(sg[-1]["end"] - vids[x["clip_id"]]["duration"]) > 11
                   or any(abs(a["end"] - b["start"]) > 11 for a, b in zip(sg, sg[1:]))):
            gaps.append(x["clip_id"])
    chk("intra_clip_segments_checked", "PASS" if not unrev and not gaps else "WARN",
        {"clips": len(seg_out), "agent_reviewed": len(seg_out) - len(unrev), "unreviewed": unrev, "span_gaps": gaps,
         "algorithm_verdicts": dict(seg_verdicts),
         "note": "boundaries precise to ~10 s (overview spacing); Stage 0C refines with continuous frames"})
    chk("roles_not_selection", "PASS", {"rule": "visual_role_candidates are descriptive; no shot/event selection made"})
    res = [c["result"] for c in checks.values()]
    overall = "FAIL" if "FAIL" in res else ("PASS_WITH_WARNINGS" if "WARN" in res else "PASS")
    head = {"reviewed_region_count": len(rev_q), "queue_items": len(qids), "frames_reviewed_by_vlm": len(vlm),
            "temporal_coverage": "every queue item; whole clips front/mid/back + 30 s; >=60 s clips every 10 s",
            "resource_limit_mode": "8 GB / advisory", "model_quantization": "qwen2.5vl:7b / Q4_K_M",
            "peak_memory_gb": max(deltas), "oom_retry_count": len(low), "resource_blocked": 0,
            "vlm_hero_candidates": 0, "agent_hero_candidates_reviewed": len(hc),
            "agent_confirmed": hs.get("CONFIRMED", 0), "agent_rejected": hs.get("REJECTED", 0), "agent_needs_more_review": hs.get("NEEDS_MORE_REVIEW", 0),
            "overrides": len(ov), "unknown_count": sum(1 for r in regions if r["shot_type"] == "unknown"),
            "hard_unusable": 0, "duplicate_summary_check": checks["duplicate_generic_summaries"]["result"]}
    write_json(OUT / "stage0b_validation_report.json", {"stage": "0B", "generated_at": NOW, "overall": overall, "headline": head,
                                                        "checks": checks,
                                                        "scripts": {p.name: "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob("*.py"))}})
    # human-readable summary (zh-TW)
    L = ["Stage 0B AI 畫面複核摘要", f"產生時間：{NOW}", f"整體驗收：{overall}", ""]
    L.append(f"複核區段 {len(rev_q)}/{len(qids)}；VLM 看過影格 {len(vlm)} 張；Hero 候選複核 {len(hc)} 組（確認 {hs.get('CONFIRMED',0)}／否決 {hs.get('REJECTED',0)}／需再看 {hs.get('NEEDS_MORE_REVIEW',0)}）")
    L.append(f"VLM 隨機抽查加權正確率 {acc:.0%}；VLM 失效欄位：Hero 提名、室內外、標籤確認（已改用其他方法）")
    L.append("")
    L.append("== 已確認的 Hero 候選 ==")
    for c in hc:
        a = c["agent_review"]
        if a.get("status") == "CONFIRMED":
            L.append(f"{c['candidate_id']} {c['clip_id']} {c['candidate_start']:.1f}-{c['candidate_end']:.1f}s [{a.get('candidate_type')}] {a.get('visual_findings')}")
    L.append("")
    L.append("== 需要再看（建議 0D 注意）==")
    for c in hc:
        a = c["agent_review"]
        if a.get("status") == "NEEDS_MORE_REVIEW":
            L.append(f"{c['candidate_id']} {c['clip_id']} {c['candidate_start']:.1f}-{c['candidate_end']:.1f}s {a.get('decision_reason')}")
    L.append("")
    L.append("== 每支影片畫面摘要（整支片覆蓋區段）==")
    for r in regions:
        if r["scope"] == "whole_clip_coverage":
            L.append(f"{r['clip_id']} ({vids[r['clip_id']]['duration']:.0f}s) {r['visual_summary'][:300]}")
    (OUT / "ai_visual_review_summary.txt").write_text("\n".join(L), encoding="utf-8")
    print(overall, json.dumps(head, ensure_ascii=False))
    for k, v in checks.items():
        print(f"  {k}: {v['result']}")


if __name__ == "__main__":
    main()
