#!/usr/bin/env python3
"""Stage 0C step 3: assemble formal Stage 0 outputs + validation.

Writes process/workspace/project-output/stage0c_output/:
  metadata_catalog.json, transcript_summary.txt, visual_summary.json, event_candidates.json,
  hero_scene_candidates.json, source_proxy_manifest.json, stage0_validation_report.json
Events come from Claude-written event files (temp/stage0c/events_*.json) over deterministic groups (c1).
Location names are never asserted: GPS is auxiliary coordinates only.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROCESS = Path(__file__).resolve().parents[2]
REPO = PROCESS.parent
sys.path.insert(0, str(PROCESS / "stage-0A-local-pre-analysis" / "scripts"))
from common import read_json, write_json  # noqa: E402

W = PROCESS / "workspace"
IN0A, IN0B = W / "project-output/stage0a_output", W / "project-output/stage0b_output"
OUT = W / "project-output/stage0c_output"
TEMP = W / "temp/stage0c"
NOW = datetime.now(timezone.utc).isoformat()
HERO_FUNC = {"hook": ["hook"], "climax": ["climax"], "payoff": ["payoff"], "emotional": ["emotional_core"],
             "ending": ["ending"], "scenic": []}


def sha(p):
    return "sha256:" + hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cat = read_json(IN0A / "metadata_catalog.json")
    rev = read_json(IN0B / "ai_visual_review.json")
    hc0b = read_json(IN0B / "hero_scene_candidates.json")
    val0b = read_json(IN0B / "stage0b_validation_report.json")
    sents = read_json(IN0A / "transcript_sentences.json")["sentences"]
    groups = read_json(TEMP / "groups.json")["groups"]
    proxies = read_json(IN0A / "source_proxy_manifest.json")
    vids = {v["clip_id"]: v for v in cat["videos"]}
    sent_by_id = {s["sentence_id"]: s for s in sents}
    sent_by_clip = defaultdict(list)
    for s in sents:
        sent_by_clip[s["clip_id"]].append(s)
    places = read_json(TEMP / "places.json", {}) or {}
    pnames = (read_json(W / "gps/place_names.json", {}) or {})
    place_by_id = {p["place_id"]: p for p in places.get("places", [])}
    units = {u["unit_id"]: u for g in groups for u in g["units"]}
    unit_group = {u["unit_id"]: g["group_id"] for g in groups for u in g["units"]}
    events_raw = []
    for part in "ABC":
        events_raw += read_json(TEMP / f"events_{part}.json", []) or []

    # ---- events
    events, assigned = [], Counter()
    hero_cands = hc0b["candidates"]
    for i, e in enumerate(sorted(events_raw, key=lambda e: (units[e["unit_ids"][0]]["abs_start"] if e["unit_ids"] and e["unit_ids"][0] in units else "", e.get("seq", 0))), 1):
        us = [units[u] for u in e["unit_ids"] if u in units]
        for u in e["unit_ids"]:
            assigned[u] += 1
        if not us:
            continue
        us.sort(key=lambda u: u["abs_start"])
        abs_start = us[0]["abs_start"]
        abs_end = max(u["abs_end"] for u in us)
        srcs = sorted({u["source_path"] for u in us})
        ranges = [{"source_file": u["source_path"], "clip_id": u["clip_id"], "start": u["start"], "end": u["end"],
                   "unit_id": u["unit_id"]} for u in us]
        gp = [u["gps"] for u in us if u.get("gps")]
        loc = {"name": None, "status": "unknown",
               "gps_auxiliary": ({"lat": round(sum(g["lat"] for g in gp) / len(gp), 5), "lon": round(sum(g["lon"] for g in gp) / len(gp), 5),
                                  "source": "Google Timeline written into file by geotag_engine.py (" + ",".join(sorted({g.get("method") or "?" for g in gp})) + ")",
                                  "same_day_only": True} if gp else None),
               "signage_evidence": e["evidence_notes"].get("signage_location"),
               "note": "No place name asserted: Timeline source file is not in workspace/gps and place names were not verified. "
                       "Coordinates are auxiliary evidence only."}
        if loc["signage_evidence"]:
            loc["status"] = "signage_text_only"
        elif gp:
            loc["status"] = "approximate"
        ep = (places.get("event_place") or {}).get(f"EV{i:03d}")
        if ep:
            nm = ((pnames.get("places") or {}).get(ep["place_id"]) or {}).get("name", "").strip()
            loc["place_id"] = ep["place_id"]
            loc["timeline_match"] = {"basis": ep["basis"], "timeline_placeID": ep["key"] if ep["basis"] == "timeline_visit_overlap" else None,
                                     "timeline_semantic_type": ep.get("type"), "visit_window": ep.get("visit"),
                                     "exif_to_visit_m": ep.get("exif_to_visit_m"), "overlap_s": ep.get("overlap_s")}
            if nm:
                loc["name"] = nm
                loc["status"] = "user_confirmed"
                loc["name_source"] = {"type": "user_confirmed", "file": "process/workspace/gps/place_names.json",
                                      "created": pnames.get("created"), "place_id": ep["place_id"],
                                      "supporting_evidence": "same-day Timeline visit / EXIF coordinates (auxiliary), not the source of the name"}
                loc["note"] = "Name supplied and confirmed by the user per place; coordinates are same-day auxiliary evidence."
        # hero assessment
        hero = []
        for h in hero_cands:
            st = h["agent_review"].get("status")
            if st not in ("CONFIRMED", "NEEDS_MORE_REVIEW"):
                continue
            ov = [r for r in ranges if r["clip_id"] == h["clip_id"] and r["end"] >= h["candidate_start"] and r["start"] <= h["candidate_end"]]
            if not ov:
                continue
            rs = h["agent_review"].get("refined_start", None)
            re_ = h["agent_review"].get("refined_end", None)
            ev_start = rs if rs is not None else h["candidate_start"]
            ev_end = re_ if re_ is not None else h["candidate_end"]
            cover = any(r["start"] <= ev_start + 0.5 and r["end"] >= ev_end - 0.5 for r in ov)
            hero.append({"candidate_id": h["candidate_id"], "agent_status": st, "vlm_nominated": h["vlm_nominated"],
                         "nominated_by": h["nominated_by"],
                         "hero_functions": HERO_FUNC.get(h["agent_review"].get("candidate_type"), []) if st == "CONFIRMED" else [],
                         "evidence_ranges": [{"clip_id": h["clip_id"], "start": ev_start, "end": ev_end}],
                         "context_complete": bool(cover) if st == "CONFIRMED" else None,
                         "limitations": ([] if cover else ["agent-reviewed range extends beyond this event's source range"])
                         + ([] if st == "CONFIRMED" else ["unresolved: needs more review (see Stage 0B agent_review)"])
                         + ["selection is NOT made here; priority hint for Stage 1 only"]})
        sids = [s for s in e.get("sentence_ids", []) if s in sent_by_id]
        used = e["evidence_notes"].get("transcript_used", [])
        events.append({
            "event_id": f"EV{i:03d}", "session_id": e["session_id"], "date": us[0]["local_date"],
            "start": abs_start, "end": abs_end, "timezone_offset": us[0]["tz"], "time_basis": "creation_time_utc + clip offset (UTC)",
            "source_files": srcs, "source_ranges": ranges, "sentence_ids": sids,
            "event_type": e["event_type"], "participants": {**e["participants"], "identity": "unknown (no named people)"},
            "location": loc, "trigger": e["trigger_zh"], "development": e["development_zh"], "reaction": e["reaction_zh"],
            "result": e["result_zh"], "summary": e["summary_zh"],
            "story_value": e["story_value"], "emotional_value": e["emotional_value"], "interaction_value": e["interaction_value"],
            "visual_value": e["visual_value"], "novelty": e["novelty"], "confidence": e["confidence"],
            "hero_scene_assessment": hero or None,
            "provenance": {"visual": {"source": "Stage 0B ai_visual_review (qwen2.5vl frames + Claude agent review)", "units": e["evidence_notes"].get("visual_units", e["unit_ids"])},
                           "transcript": {"source": "Stage 0A transcript_sentences.json", "sentence_ids_used": used,
                                          "uncertain_used_as_support_only": e["evidence_notes"].get("uncertain_lines_used_as_support_only", True)},
                           "gps": "auxiliary same-day coordinates only" if gp else "none",
                           "metadata": "Stage 0A metadata_catalog (creation_time_utc, color evidence preserved)",
                           "grouping": {"group_id": unit_group[e["unit_ids"][0]], "method": "c1_group deterministic time/GPS/activity-text rules"},
                           "event_text": "written by Claude from the evidence digest (no new pixels viewed)"},
        })
    # ---- hero_scene_candidates (0B nomination + agent review preserved; event mapping added)
    ev_by_hero = defaultdict(list)
    for ev in events:
        for h in ev["hero_scene_assessment"] or []:
            ev_by_hero[h["candidate_id"]].append(ev["event_id"])
    hero_out = []
    for h in hero_cands:
        st = h["agent_review"].get("status")
        hero_out.append({**h, "event_ids": ev_by_hero.get(h["candidate_id"], []),
                         "handoff_status": {"CONFIRMED": "mapped_to_event", "NEEDS_MORE_REVIEW": "unresolved",
                                            "REJECTED": "not_promoted"}.get(st, "unknown"),
                         "selected": False})
    # ---- outputs
    prov = {"stage0a": {"dir": str(IN0A.relative_to(REPO)), "metadata_catalog": sha(IN0A / "metadata_catalog.json"),
                        "transcript_sentences": sha(IN0A / "transcript_sentences.json")},
            "stage0b": {"dir": str(IN0B.relative_to(REPO)), "ai_visual_review": sha(IN0B / "ai_visual_review.json"),
                        "hero_scene_candidates": sha(IN0B / "hero_scene_candidates.json"),
                        "validation_overall": val0b["overall"]}}
    write_json(OUT / "metadata_catalog.json", {**cat, "stage": "0C (carried from 0A, color/GPS provenance unchanged)", "carried_at": NOW})
    shutil.copyfile(IN0A / "transcript_summary.txt", OUT / "transcript_summary.txt")
    write_json(OUT / "source_proxy_manifest.json", proxies)
    clip_vis = []
    for v in cat["videos"]:
        rs = [r for r in rev["regions"] if r["clip_id"] == v["clip_id"] and r["scope"] == "whole_clip_coverage"]
        sg = next((s for s in rev["intra_clip_segments"] if s["clip_id"] == v["clip_id"]), None)
        clip_vis.append({"clip_id": v["clip_id"], "source_file": v["source_path"], "duration": v["duration"],
                         "visual_summary": rs[0]["visual_summary"] if rs else None,
                         "visual_people": rs[0]["visual_people"] if rs else None,
                         "visual_animals": rs[0]["visual_animals"] if rs else None,
                         "segments": (sg or {}).get("segments", []),
                         "audio_speakers": "separate: see transcript (audio only)",
                         "source_region_ids": [r["region_id"] for r in rev["regions"] if r["clip_id"] == v["clip_id"]]})
    write_json(OUT / "visual_summary.json", {"stage": "0C", "generated_at": NOW,
                                             "note": "visual only; derived from Stage 0B ai_visual_review (pixels). Audio/GPS not mixed in.",
                                             "clips": clip_vis})
    types = Counter(e["event_type"] for e in events)
    write_json(OUT / "event_candidates.json", {"stage": "0C", "generated_at": NOW, "provenance": prov,
                                               "grouping_rules": "see scripts/c1_group.py", "events": events})
    write_json(OUT / "hero_scene_candidates.json", {
        "stage": "0C", "generated_at": NOW,
        "note": "Stage 0B VLM nomination (0) and Agent review kept separate and unmodified; event mapping added. selected=false everywhere.",
        "vlm_nominations": 0, "candidates": hero_out,
        "candidates_not_reviewed_budget": hc0b.get("candidates_not_reviewed_budget", []),
        "status_counts": dict(Counter(h["handoff_status"] for h in hero_out))})

    # ---- validation
    checks = {}

    def chk(n, r, ev):
        checks[n] = {"result": r, "evidence": ev}

    chk("stage0b_gate", "PASS" if val0b["overall"] in ("PASS", "PASS_WITH_WARNINGS") else "FAIL", {"stage0b_overall": val0b["overall"]})
    chk("metadata_source_count", "PASS" if len(cat["videos"]) == 260 and len(proxies["proxies"]) == 260 else "FAIL",
        {"videos": len(cat["videos"]), "photos": len(cat["photos"]), "lrf_not_events": len(proxies["proxies"])})
    miss = [u for u in units if assigned[u] != 1]
    chk("every_unit_in_exactly_one_event", "PASS" if not miss else "FAIL",
        {"units": len(units), "unassigned_or_duplicated": miss[:20], "events": len(events)})
    lrf = [e["event_id"] for e in events if any(s.lower().endswith(".lrf") for s in e["source_files"])]
    chk("no_proxy_in_events", "PASS" if not lrf else "FAIL", {"events_with_lrf": lrf})
    bad_dates, bad_t = [], []
    for e in events:
        if len({units[r["unit_id"]]["local_date"] for r in e["source_ranges"]}) > 1:
            bad_dates.append(e["event_id"])
        for r in e["source_ranges"]:
            v = vids[r["clip_id"]]
            if not (0 <= r["start"] < r["end"] <= v["duration"] + 0.05):
                bad_t.append((e["event_id"], r["clip_id"]))
    chk("gps_same_day_no_cross_day", "PASS" if not bad_dates else "FAIL", {"cross_day_events": bad_dates})
    chk("source_time_traceable", "PASS" if not bad_t else "FAIL", {"invalid_ranges": bad_t[:20]})
    named = [e["event_id"] for e in events if e["location"]["name"]]
    bad_named = [e["event_id"] for e in events if e["location"]["name"] and (e["location"].get("name_source") or {}).get("type") != "user_confirmed"]
    chk("location_not_invented", "PASS" if not bad_named else "FAIL", {"named_events": len(named), "named_without_user_confirmation": bad_named,
        "status": dict(Counter(e["location"]["status"] for e in events))})
    ep = places.get("event_place") or {}
    badp = [e["event_id"] for e in events if e["event_id"] not in ep or e["date"] not in place_by_id.get(ep[e["event_id"]]["place_id"], {}).get("dates", [])]
    chk("place_assignment_consistent", "PASS" if not badp and ep else ("WARN" if not ep else "FAIL"),
        {"events_checked": len(events), "inconsistent_or_missing": badp[:20],
         "rule": "event date must be among the dates of its assigned place (no cross-day place pairing)",
         "places": len(place_by_id), "places_named": sum(1 for p in place_by_id.values() if ((pnames.get('places') or {}).get(p['place_id']) or {}).get('name'))})
    sid_bad, sid_out = [], []
    for e in events:
        for sid in e["sentence_ids"]:
            s = sent_by_id.get(sid)
            if not s or not any(r["clip_id"] == s["clip_id"] and s["end"] >= r["start"] - 0.5 and s["start"] <= r["end"] + 0.5 for r in e["source_ranges"]):
                sid_out.append((e["event_id"], sid))
    chk("sentence_ids_traceable", "PASS" if not sid_out else "FAIL", {"not_overlapping_event_ranges": sid_out[:20],
        "events_with_sentences": sum(1 for e in events if e["sentence_ids"])})
    only_unc = []
    for e in events:
        ss = [sent_by_id[s] for s in e["sentence_ids"] if s in sent_by_id]
        if ss and all(s["transcript_status"] == "uncertain" for s in ss) and not e["provenance"]["visual"]["units"]:
            only_unc.append(e["event_id"])
    chk("uncertain_speech_not_sole_evidence", "PASS" if not only_unc else "FAIL",
        {"events_whose_only_evidence_is_uncertain_speech": only_unc,
         "uncertain_sentences_referenced": sum(1 for e in events for s in e["sentence_ids"] if sent_by_id.get(s, {}).get("transcript_status") == "uncertain"),
         "note": "every event also carries visual units; uncertain flags preserved in transcript_sentences (0A)"})
    unk = sum(1 for v in cat["videos"] if v["color_profile"] == "unknown")
    lost = [v["clip_id"] for v in cat["videos"] if not v.get("color_profile_source") or "detected_color_metadata" not in v]
    chk("color_provenance_preserved", "PASS" if not lost else "FAIL", {"profiles": dict(Counter(v["color_profile"] for v in cat["videos"])),
        "unknown": unk, "missing_provenance": lost})
    conf_h = [h for h in hero_out if h["agent_review"].get("status") == "CONFIRMED"]
    unm = [h["candidate_id"] for h in conf_h if not h["event_ids"]]
    chk("hero_confirmed_mapped_to_events", "PASS" if not unm else "FAIL", {"confirmed": len(conf_h), "unmapped": unm,
        "not_selected": all(h["selected"] is False for h in hero_out)})
    incomplete = [(e["event_id"], h["candidate_id"]) for e in events for h in (e["hero_scene_assessment"] or [])
                  if h["agent_status"] == "CONFIRMED" and not h["context_complete"]]
    chk("hero_context_complete", "PASS" if not incomplete else "WARN", {"confirmed_with_range_beyond_event": incomplete})
    gen = Counter(e["summary"] for e in events)
    dup = {s: n for s, n in gen.items() if n >= 3}
    chk("events_not_sentence_copies", "PASS" if not dup else "WARN", {"summary_repeated_3x": dup})
    req = ["event_id", "date", "start", "end", "source_files", "sentence_ids", "participants", "location", "trigger", "development",
           "reaction", "result", "summary", "story_value", "emotional_value", "interaction_value", "visual_value", "novelty", "confidence", "provenance"]
    lack = [e["event_id"] for e in events if any(k not in e or e[k] in (None, "") and k not in ("sentence_ids",) for k in req)]
    chk("event_required_fields", "PASS" if not lack else "FAIL", {"incomplete": lack[:20]})
    giant = [(e["event_id"], round(sum(r["end"] - r["start"] for r in e["source_ranges"]))) for e in events
             if sum(r["end"] - r["start"] for r in e["source_ranges"]) > 400 or len(e["source_ranges"]) > 12]
    chk("not_over_fused", "PASS" if not giant else "WARN", {"large_events_(footage_s)": giant,
        "largest_5": sorted(((round(sum(r["end"] - r["start"] for r in e["source_ranges"])), e["event_id"]) for e in events), reverse=True)[:5]})
    res = [c["result"] for c in checks.values()]
    overall = "FAIL" if "FAIL" in res else ("PASS_WITH_WARNINGS" if "WARN" in res or val0b["overall"] != "PASS" else "PASS")
    head = {"metadata_count": {"videos": len(cat["videos"]), "photos": len(cat["photos"])}, "visual_region_count": len(rev["regions"]),
            "event_count": len(events), "event_type_distribution": dict(types.most_common()),
            "location_unknown_count": sum(1 for e in events if not e["location"]["name"]),
            "location_named_count": len(named), "color_unknown_count": unk}
    warnings = ["Stage 0B overall was PASS_WITH_WARNINGS (qwen fields unreliable, 315 hero candidates not reviewed, 3 hero candidates unresolved)",
                ] + (["Timeline 3.json contains placeIDs/coordinates but no place names; names are user-confirmed per place (place_names.json)"] if named else
                     ["no place names: provide process/workspace/gps/place_names.json"])
    warnings += [f"{sum(1 for e in events if not e['location']['name'])} events have no confirmed place name"] if len(named) < len(events) else []
    write_json(OUT / "stage0_validation_report.json", {"stage": "0C", "generated_at": NOW, "overall": overall, "headline": head, "checks": checks,
                                                       "warnings": warnings, "provenance": prov,
                                                       "scripts": {p.name: sha(p) for p in sorted((PROCESS / "stage-0C-event-fusion-validation/scripts").glob("*.py"))}})
    print(overall, json.dumps(head, ensure_ascii=False))
    for k, v in checks.items():
        print(f"  {k}: {v['result']}")


if __name__ == "__main__":
    main()
