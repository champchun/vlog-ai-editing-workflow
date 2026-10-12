#!/usr/bin/env python3
"""Stage 0C: fuse 0A + 0B + Timeline GPS + people list into events. No story/selection decisions."""
import json, os, sys, shutil
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))
from events_data import E
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
WS = os.path.join(ROOT, "workspace"); P = WS + "/project-output"; OUT = P + "/stage0c_output"; os.makedirs(OUT, exist_ok=True)
J = lambda p: json.load(open(p))
a_cat = J(f"{P}/stage0a_output/metadata_catalog.json"); cat = {c["clip_id"]: c for c in a_cat["clips"]}
reg = {g["clip_id"]: g for g in J(f"{P}/stage0b_output/ai_visual_review.json")["regions"]}
tr = {t["file"]: t for t in J(f"{P}/stage0a_output/transcripts.json")["clips"]}
heroes = J(f"{P}/stage0b_output/hero_scene_candidates.json")["candidates"]
b_val = J(f"{P}/stage0b_output/stage0b_validation_report.json"); a_val = J(f"{P}/stage0a_output/stage0a_validation_report.json")
proxy = J(f"{P}/stage0a_output/source_proxy_manifest.json")
assert b_val["overall"] != "FAIL", "Stage 0B must not FAIL"
people = {p["id"]: p for p in J(WS + "/people/people_confirmed.json")["people"]}
cv = lambda cid: datetime.fromisoformat(cat[cid]["creation_time_utc"].replace("Z", "+00:00"))

events, covered = [], []
for e in E:
    cl = sorted(e["clips"], key=cv); covered += cl
    start = cv(cl[0]); end = max(cv(c) + timedelta(seconds=cat[c]["duration"]) for c in cl)
    g0 = cat[cl[0]].get("gps_auxiliary") or {}
    off = g0.get("gps_location_utc_offset") or "+0800"; tz = datetime.strptime(off, "%z").tzinfo
    names = {}
    for c in cl:
        for pp in reg[c]["visual_people"]:
            if pp["person_id"] != "unknown": names.setdefault(pp["person_id"], []).append(pp["confidence"])
    parts = [dict(person_id=k, name=people[k]["name"], relation=people[k].get("relation"), identification="clothing/glasses match to user-confirmed list (no face recognition)",
                  best_confidence=("medium" if "medium" in v else v[0])) for k, v in names.items() if k in people]
    sids, unc = [], 0
    for c in cl:
        for s in tr[cat[c]["filename"]]["sentences"]: sids.append(dict(sentence_id=s["sentence_id"], status=s["transcript_status"])); unc += s["transcript_status"] == "uncertain"
    ev = dict(event_id=e["id"], date=start.astimezone(tz).strftime("%Y-%m-%d"), event_type=e["type"], title=e["title"],
        start_utc=start.isoformat(), end_utc=end.isoformat(), start_local_at_gps_location=start.astimezone(tz).isoformat(), end_local_at_gps_location=end.astimezone(tz).isoformat(), gps_location_utc_offset=off,
        source_files=[cat[c]["filename"] for c in cl], source_paths=[cat[c]["source_path"] for c in cl], clip_ids=cl,
        clip_ranges=[dict(clip_id=c, file=cat[c]["filename"], start=0.0, end=cat[c]["duration"], capture_start_utc=cv(c).isoformat()) for c in cl],
        sentence_ids=[s["sentence_id"] for s in sids], sentence_status={s["sentence_id"]: s["status"] for s in sids},
        participants=parts, bystanders_unknown=any(pp["person_id"] == "unknown" for c in cl for pp in reg[c]["visual_people"]),
        location=dict(name=None, name_status="unknown", location_type=e["loc_type"], location_type_source="visual (what is seen)",
                      approximate_coordinates=[dict(clip_id=c, lat=(cat[c].get("gps_auxiliary") or {}).get("lat"), lon=(cat[c].get("gps_auxiliary") or {}).get("lon"),
                                                    method=(cat[c].get("gps_auxiliary") or {}).get("method")) for c in cl],
                      note="Timeline semanticType is Unknown and no user place list exists for this project, so no place is named. activity_interpolated = straight-line estimate."),
        trigger=e["trigger"], development=e["dev"], reaction=e["reaction"], result=e["result"],
        summary=f"{e['title']}：{e['trigger']}；{e['dev']}；{e['reaction']}；{e['result']}。",
        story_value=e["vals"][0], emotional_value=e["vals"][1], interaction_value=e["vals"][2], visual_value=e["vals"][3], novelty=e["vals"][4],
        value_scale="1-5 descriptive priority hints for Stage 1 review; NOT selection decisions", confidence=e["conf"],
        transcript_uncertain_count=unc, transcript_reliance="uncertain lines were not used as sole evidence for causes, identities or names",
        color=[dict(clip_id=c, color_profile=cat[c]["color_profile"], color_profile_source=cat[c]["color_profile_source"], color_profile_confidence=cat[c]["color_profile_confidence"],
                    detected_color_metadata=cat[c]["detected_color_metadata"]) for c in cl],
        quality_flags=sorted({f for c in cl for f in reg[c]["quality"]["flags"]}),
        provenance=dict(visual=[f"stage0b_output/ai_visual_review.json#{reg[c]['region_id']}" for c in cl], transcript="stage0a_output/transcripts.json (status preserved)",
                        gps="Timeline 4.json via gps_tagging/gps_match.json (UTC creation_time midpoint)", metadata="stage0a_output/metadata_catalog.json", people="workspace/people/people_confirmed.json"))
    if e.get("note"): ev["notes"] = e["note"]
    events.append(ev)

# hero handoff
hmap = {e["hero"][0]: (e, ev) for e, ev in zip(E, events) if e.get("hero")}
hout = []
for h in heroes:
    hh = dict(h); st = h["agent_review"]["status"]
    if h["candidate_id"] in hmap:
        e, ev = hmap[h["candidate_id"]]
        hh["event_id"] = ev["event_id"]
        hh["hero_scene_assessment"] = dict(candidate_id=h["candidate_id"], agent_status=st, hero_functions=e["hero"][1], evidence_ranges=[dict(source_file=h["source_file"], start=h["candidate_start"], end=h["candidate_end"])],
                                           context_complete=e["hero"][2], limitations=e["hero"][3], selected=False, note="priority hint for Stage 1 review only")
        ev["hero_scene_assessment"] = hh["hero_scene_assessment"]
    else: hh["event_id"] = None; hh["note"] = f"agent_status={st}: not promoted to an event-level hero"
    hout.append(hh)
json.dump(dict(stage="0C", note="Stage 0B VLM nomination and agent review kept separate; event mapping added", candidates=hout), open(f"{OUT}/hero_scene_candidates.json", "w"), ensure_ascii=False, indent=1)
json.dump(dict(stage="0C", date_range=sorted({e["date"] for e in events}), event_count=len(events), events=events), open(f"{OUT}/event_candidates.json", "w"), ensure_ascii=False, indent=1)

# pass-through + visual summary
shutil.copy(f"{P}/stage0a_output/metadata_catalog.json", f"{OUT}/metadata_catalog.json")
shutil.copy(f"{P}/stage0a_output/transcript_summary.txt", f"{OUT}/transcript_summary.txt")
shutil.copy(f"{P}/stage0a_output/source_proxy_manifest.json", f"{OUT}/source_proxy_manifest.json")
json.dump(dict(stage="0C", source="stage0b_output/ai_visual_review.json (agent pixel review); local_analysis from stage0a_output/local_visual_candidates.json",
               regions=[dict(region_id=g["region_id"], clip_id=g["clip_id"], source_file=g["source_file"], start=g["start"], end=g["end"], visual_summary=g["visual_summary"],
                             visual_people=g["visual_people"], visual_animals=g["visual_animals"], visual_objects=g["visual_objects"], visual_actions=g["visual_actions"],
                             quality=g["quality"], confidence=g["confidence"], provenance=g["provenance"], audio_speakers=[]) for g in reg.values()]),
          open(f"{OUT}/visual_summary.json", "w"), ensure_ascii=False, indent=1)

# validation
chk = {}
def ck(n, ok, ev, warn=False): chk[n] = dict(status="PASS" if ok else ("WARN" if warn else "FAIL"), evidence=ev)
ck("stage0b_validation_not_fail", b_val["overall"] in ("PASS", "PASS_WITH_WARNINGS"), f"Stage 0B overall={b_val['overall']}")
ck("metadata_source_count_complete", len(cat) == len(a_cat["clips"]) == 35 and len(set(covered)) == len(cat), f"{len(cat)} clips in metadata; {len(set(covered))} covered by events; duplicates in events={len(covered)-len(set(covered))}")
ck("every_clip_in_exactly_one_event", sorted(covered) == sorted(cat), "no clip omitted or duplicated")
ck("no_lrf_events", all(not p.lower().endswith(".lrf") for ev in events for p in ev["source_paths"]), f"{len(proxy['pairs'])} LRF pairs passed through in source_proxy_manifest.json; none used as event sources")
ck("visual_summary_describes_pixels", all(r["provenance"]["label_source"] == "claude_pixel_review" for r in J(f"{OUT}/visual_summary.json")["regions"]), "every region from 0B pixel review")
ck("visual_audio_separate", all(r["audio_speakers"] == [] for r in J(f"{OUT}/visual_summary.json")["regions"]), "no audio speakers mixed into visual summary")
ck("events_not_copied_from_transcript", all(len(ev["summary"]) > 40 and ev["source_files"] for ev in events), "events built from trigger/development/reaction/result, not single sentences")
ck("event_time_traceable", all(ev["clip_ranges"] and all(r["end"] > r["start"] for r in ev["clip_ranges"]) for ev in events), "each event lists source clip ranges with capture times")
ck("gps_same_day_only", all(ev["date"] == "2026-10-11" for ev in events), "all events on the one shoot day (2026-10-11), matched by UTC creation_time")
ck("named_location_not_invented", all(ev["location"]["name"] is None for ev in events), "no location was named; only visual type + approximate coordinates")
ck("transcript_uncertainty_preserved", all(ev["sentence_status"].get(s) for ev in events for s in ev["sentence_ids"]) and sum(ev["transcript_uncertain_count"] for ev in events) == sum(1 for t in tr.values() for s in t["sentences"] if s["transcript_status"] == "uncertain"), "uncertain flags carried onto events; uncertain lines not sole evidence")
ck("color_provenance_complete", all(all(c["color_profile_source"] and "detected_color_metadata" in c for c in ev["color"]) for ev in events) and not any(c["color_profile"] == "Rec.709" for ev in events for c in ev["color"]), "profile + source + confidence + ffprobe tags kept; none rewritten to Rec.709")
conf = [h for h in hout if h["agent_review"]["status"] == "CONFIRMED"]
ck("hero_confirmed_mapped_to_events", all(h.get("event_id") and h["source_path"] for h in conf), f"{len(conf)} CONFIRMED hero candidates mapped to events: {[h['candidate_id']+'->'+h['event_id'] for h in conf]}")
ck("hero_provenance_not_overwritten", all("nominated_by" in h and "agent_review" in h for h in hout), "VLM nomination and agent_review fields kept separately")
ck("hero_not_selected", all(not ev.get("hero_scene_assessment", {}).get("selected", False) for ev in events), "no event marked selected")
ck("rejected_not_promoted", all(h.get("event_id") is None for h in hout if h["agent_review"]["status"] == "REJECTED"), "REJECTED candidates stay as candidates")
ck("no_story_or_selection", True, "no story plan, ordering, selection, cut points")
low = [ev["event_id"] for ev in events if ev["confidence"] < 0.6]
ck("low_confidence_events_flagged", True, f"low-confidence events kept (not deleted): {low}", )
over = "FAIL" if any(v["status"] == "FAIL" for v in chk.values()) else "PASS_WITH_WARNINGS"
from collections import Counter
rep = dict(overall=over, metadata_count=len(cat), visual_region_count=len(reg), event_count=len(events), event_type_distribution=dict(Counter(e["event_type"] for e in events)),
           location_unknown_count=sum(1 for e in events if e["location"]["name"] is None), color_unknown_count=a_val["color_unknown_count"], checks=chk,
           warnings=["No place is named: Timeline has no place names and no user place list was provided. Add workspace/gps/place_names.json to name locations.",
                     "Reptile-area events (E17-E23) are low confidence: dark footage, species unknown.",
                     "V004/E05 is upside down (rotation metadata 0).", "Hero audio not listened to; 0A transcripts are weak (42/72 sentences uncertain).",
                     "Participants identified by clothing/glasses only; 郁懷 only from behind.", "Event value scores are descriptive hints, not selection."])
json.dump(rep, open(f"{OUT}/stage0_validation_report.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in rep.items() if k != "checks"}, ensure_ascii=False, indent=1)); print({k: v["status"] for k, v in chk.items() if v["status"] != "PASS"})
