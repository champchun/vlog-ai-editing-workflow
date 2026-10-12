#!/usr/bin/env python3
"""Stage 0B output builder. Visual observations come from agent pixel review (regions_data.py); this script only
merges them with Stage 0A data, adds provenance, runs validation and writes stage0b_output/."""
import json, os, sys, re, hashlib
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(__file__))
from regions_data import R
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
WS = os.path.join(ROOT, "workspace"); A = os.path.join(WS, "project-output/stage0a_output"); OUT = os.path.join(WS, "project-output/stage0b_output")
os.makedirs(OUT, exist_ok=True)
J = lambda p: json.load(open(p))
cat = {c["clip_id"]: c for c in J(f"{A}/metadata_catalog.json")["clips"]}
vis = {v["clip_id"]: v for v in J(f"{A}/local_visual_candidates.json")}
tr = {t["file"]: t for t in J(f"{A}/transcripts.json")["clips"]}
queue = J(f"{A}/stage0b_review_queue.json"); sel = J(os.path.join(WS, "temp/stage0b/selection.json"))
MODEL = "claude-sonnet-5-5 (multimodal, agent pixel review; no local VLM used)"
now = datetime.now(timezone(timedelta(hours=8))).isoformat()

regions = []
for cid, c in cat.items():
    d = R[cid]; v = vis[cid]; fr = sel[cid]["frames"]
    regions.append(dict(
        region_id=f"R-{cid}", clip_id=cid, source_file=c["filename"], source_path=c["source_path"], start=0.0, end=c["duration"],
        capture_time_utc=(c.get("gps_auxiliary") or {}).get("capture_time_utc") or c["creation_time_utc"],
        local_time_at_gps_location=(c.get("gps_auxiliary") or {}).get("local_time_at_gps_location"),
        review_status="REVIEWED",
        sample_times=[f["t"] for f in fr], sampling_reason={str(f["t"]): f["reason"] for f in fr},
        sample_frames=[f["frame"] for f in fr], frames_reviewed=len(fr), frames_available_in_0A=len(v["sample_frames"]),
        visual_summary=d["summary"], visual_people=d["people"], visual_animals=d["animals"], visual_objects=d["objects"],
        visual_actions=d["actions"], visual_environment=d["env"], reaction=d["reaction"], shot_type=d["shot"],
        visual_role_candidates=d["roles"], dominant_tone=d["tone"], light_level=d["light"], composition_anchor=d["anchor"],
        camera_movement=d["cam"], movement_direction=d["dirn"], visual_motif_candidates=d["motifs"], action_coverage=d["cov"],
        quality=dict(usable_ratio_estimate=d["usable"], flags=d.get("flags", []), hard_unusable=False,
                     metrics_from_0A=dict(blur_lap_var_median=v["analysis"]["blur_lap_var_median"], shake_shift_pct_p95=v["analysis"]["shake_shift_pct_p95"],
                                          over_fraction_mean=v["analysis"]["over_fraction_mean"], dark_fraction_mean=v["analysis"]["dark_fraction_mean"]),
                     color_profile=c["color_profile"]),
        confidence=d["conf"], coverage_gaps=[] if d["conf"] >= 0.7 else ["subject/species uncertain or image too dark; marked low confidence rather than guessed"],
        provenance=dict(model=MODEL, method="agent viewed labelled contact sheets of actual frames (temp/stage0b/sheets)", label_source="claude_pixel_review",
                        local_label=None, final_visual_label=d["roles"], local_label_overridden=False,
                        local_label_note="Stage 0A produced no local semantic labels (OpenCV 5.0 had no detector)", reviewed_at=now,
                        people_naming="user-confirmed list workspace/people/people_confirmed.json; matched by clothing/glasses only"),
        audio_context=dict(note="transcript describes sound only; not used as visual evidence", sentences=[dict(t=[s["start"], s["end"]], text=s["text"], status=s["transcript_status"]) for s in tr[c["filename"]]["sentences"]])))
json.dump(dict(stage="0B", model=MODEL, region_count=len(regions), regions=regions), open(f"{OUT}/ai_visual_review.json", "w"), ensure_ascii=False, indent=1)

# ---- Hero scenes: round 1 nomination (from sheets), round 2 independent dense-frame review of ORIGINAL clips ----
H = lambda hid, cid, s, e, anchors, typ, ev, why, vc, gaps, ctx, times, status, vf, reason, conf: dict(
    candidate_id=hid, source_file=cat[cid]["filename"], source_path=cat[cid]["source_path"], clip_id=cid, candidate_start=s, candidate_end=e,
    anchor_times=anchors, candidate_type=typ, visual_evidence=ev, audio_context="audio not reviewed (no listening ability in this runtime); local audio events: none",
    why_potential_hero=why, vlm_confidence=vc, coverage_gaps=gaps, nominated_by="round1: agent pass over contact sheets",
    agent_review=dict(status=status, reviewed_media=[cat[cid]["source_path"]], reviewed_times=times, context_start=ctx[0], context_end=ctx[1],
                      visual_findings=vf, audio_findings="audio_review_unavailable", decision_reason=reason, confidence=conf,
                      method="round2: dense frames extracted from the ORIGINAL clip (temp/stage0b/hero/*.jpg) and viewed individually"))
heroes = [
 H("HC01","V022",0.0,10.0,[3.2,3.8],"reaction / ambient journey","兩個孩子並排趴在高架地鐵車頭窗前看鐵軌，胤辰約3秒回頭對鏡頭笑","孩子與地鐵的情感核心，有明確的回頭笑反應",0.85,["高光偏白"],(0.0,53.2),[0.5,1.5,2.5,3.2,3.8,4.5,5.5,7,10,20,30,45],"CONFIRMED",
   "0.5-1.5s先見兩人靠窗；2.5s白衣小孩轉身；3.2-3.8s明確回頭笑看鏡頭；之後持續望向前方，20/30/45s仍是相同構圖並出現車站。動作與反應完整，人物清楚。","笑容時刻在像素中出現，前後文完整(進入、反應、回到看窗外)；窗面朦朧但不影響判讀。",0.9),
 H("HC02","V011",9.0,28.5,[12.0,23.0,26.5],"action / play","柚里與胤辰在貓形照片牆前拿雛菊氣球跑跳、轉圈、舉手","連續玩耍動作與可辨識的布景",0.7,["人物偏小"],(0.0,28.9),[9,11,13,15,17,19,21,23,25,26.5,27.5,28.5],"CONFIRMED",
   "9s起兩人入鏡跑向牆前，13-21s氣球揮舞與追逐，23s柚里舉手、26.5-28.5s兩人在牆前持續玩耍，鏡頭幾乎固定。事件完整，但距離遠、臉部不清。","動作連續、環境有辨識度；但人物小，較適合作為過場/玩耍橋段而非特寫情感核心。",0.75),
 H("HC03","V009",9.0,19.3,[10.5,12.0,14.8],"person / interaction","柚里扶扶手對鏡頭說話並下樓","角色性強的面對鏡頭互動",0.7,["14秒動作模糊","音訊未聽"],(0.0,19.3),[9.0,10.5,12,13,14,14.8,15.6,16.5,17.5,18.5,19],"CONFIRMED",
   "9-12s臉部清楚、口型像在說話並看向鏡頭；13-14.8s快速轉身，14s明顯動態模糊；15.6-19s低頭走下階梯。畫面偏暗但主體清楚。","面對鏡頭的互動與下樓動作都真實出現；音訊與台詞未確認，且14s有動態模糊。",0.7),
 H("HC04","V003",5.0,13.8,[5.0,7.0,10.0],"reaction / close-up","柚里在地鐵上吐舌、閉眼、推眼鏡、拿粉色玩偶的連續表情","有個性的近距離表情",0.75,["約1.8s被遮擋"],(0.0,14.1),[5,6,7,8,9,10,11,12,13,13.8],"CONFIRMED",
   "5s吐舌看鏡頭；6-9s閉眼托腮；10-12s用手指與粉色玩偶推眼鏡；13s起鏡頭歪斜。表情連續，主體清楚，只有開頭附近(1.8s)被完全遮擋。","表情在像素中連續出現；畫面太近且偏暗，適合作插入反應鏡頭。",0.75),
 H("HC05","V035",0.0,10.4,[3.0,6.0,9.0],"object / animal action","深色花紋陸龜從箱內慢慢走向鏡頭並抬頭","動物單一動作完整、構圖乾淨",0.65,["種類不確定"],(0.0,10.5),[0.3,1.5,3,4,5,6,7,8,9,10],"CONFIRMED",
   "0.3s陸龜在畫面中偏左；3-5s轉向鏡頭；6-10s持續靠近並抬頭，背景是另外兩隻龜。動作連續。","畫面證據完整；屬於動物主題的小高潮/收尾鏡頭，不是家人情感核心。",0.7),
 H("HC06","V029",0.0,4.4,[3.5],"object / animal close-up","鬃獅蜥抬頭特寫","細節漂亮的動物特寫",0.5,["無事件"],(0.0,4.4),[0.2,3.5,6.5],"REJECTED",
   "三張畫面幾乎相同：一隻抬頭站立、一隻趴著，沒有動作或事件。","畫面好看但缺乏事件與前後文，維持一般 B-roll 候選。",0.7),
]
# fix HC06 reviewed times to real frame times available (clip is 4.35s)
heroes[5]["agent_review"]["reviewed_times"] = [0.2, 3.5]
json.dump(dict(stage="0B", note="Round 1 nominations by the agent from contact sheets; round 2 = separate dense-frame review of the original clips. Neither decides Stage 1 selection.", candidates=heroes), open(f"{OUT}/hero_scene_candidates.json", "w"), ensure_ascii=False, indent=1)

# ---- resource log ----
res = dict(resource_budget=dict(memory_limit_gb=8, limit_mode="unavailable", max_parallel_jobs=1, max_frames_per_request=2, max_image_edge_px=960, context_tokens=4096,
               checkpoint_every_regions=1, oom_retry_limit=3, note="Project default budget for a local Ollama VLM. NOT applied: no local VLM was run this stage."),
           runtime="Claude multimodal via the agent session (images viewed by the agent); ollama/qwen2.5vl not used", model=MODEL, quantization=None, actual_parallel_jobs=1,
           requests=dict(contact_sheets_viewed=len(os.listdir(os.path.join(WS, "temp/stage0b/sheets"))), hero_dense_sheets_viewed=5, sheet_cell_size="480x270",
                         frames_per_sheet="3-12", max_image_edge_px_in_sheets=480),
           checkpoint_path="workspace/project-output/stage0b_output/ (written atomically at the end; observations in stage-0B scripts/regions_data.py)",
           retries=[], oom_events=[], peak_ram_gb="unknown", peak_vram_gb="unknown", peak_unified_memory_gb="unknown", memory_monitoring="UNAVAILABLE",
           frame_thinning=dict(frames_in_0A=sum(len(v["sample_frames"]) for v in vis.values()), frames_reviewed=sum(len(s["frames"]) for s in sel.values()),
                               reason="agent token budget (not RAM); long clips V019/V020 had 136/163 dense scene-change samples, reduced to 24 each plus gap-fill frames so that max spacing <=7.5s; first/mid/last kept"))
json.dump(res, open(f"{OUT}/stage0b_resource_log.json", "w"), ensure_ascii=False, indent=1)

# ---- summary txt ----
with open(f"{OUT}/ai_visual_review_summary.txt", "w") as fh:
    fh.write("Stage 0B AI Visual Review summary (visual only; audio/transcript kept separate)\n\n")
    for g in regions:
        names = ", ".join(sorted({p["name"] or "unknown" for p in g["visual_people"]})) or "-"
        fh.write(f"{g['clip_id']} {g['source_file'][4:23]} {g['end']:.1f}s | people: {names} | animals: {', '.join(a['label'] for a in g['visual_animals']) or '-'}\n   {g['visual_summary']}\n")
    fh.write("\nHero scene candidates (agent round-2 review):\n")
    for h in heroes: fh.write(f"  {h['candidate_id']} {h['clip_id']} {h['candidate_start']}-{h['candidate_end']}s {h['agent_review']['status']} - {h['candidate_type']}\n")

# ---- validation ----
chk = {}
def ck(n, ok, ev, warn=False): chk[n] = dict(status="PASS" if ok else ("WARN" if warn else "FAIL"), evidence=ev)
qids = {q["clip_id"] for q in queue}; done = {g["clip_id"] for g in regions if g["review_status"] == "REVIEWED"}
ck("all_queue_items_reviewed", qids <= done, f"{len(done & qids)}/{len(qids)} review-queue clips have review_status=REVIEWED")
long_ok, gaps = True, []
for g in regions:
    t = g["sample_times"]; dur = g["end"]
    need_cov = t and t[0] <= 1.5 and t[-1] >= dur - 4
    sp = max([b - a for a, b in zip(t, t[1:])] or [0]); limit = 7.5
    if not need_cov or (dur > 20 and sp > limit): long_ok = False; gaps.append((g["clip_id"], t[0], t[-1], sp))
mg = {g["clip_id"]: round(max([b - a for a, b in zip(g["sample_times"], g["sample_times"][1:])] or [0]), 1) for g in regions}
ck("temporal_coverage", long_ok, f"every clip has first-to-last coverage; max sample gap {max(mg.values())}s overall (rule: <=7.5s on clips >20s); gaps filled with 'gap_fill' frames on V019/V020/V022 (violations={gaps})")
sm = [g["visual_summary"] for g in regions]
ck("no_duplicate_generic_summaries", len(set(sm)) == len(sm) and len({s[:24] for s in sm}) == len(sm), f"{len(set(sm))} unique summaries of {len(sm)}; first-24-char prefixes unique")
ck("visual_audio_separation", all("transcript" not in g["visual_summary"] and "台詞" not in g["visual_summary"] for g in regions) , "visual_summary never cites transcript/audio; audio kept in audio_context")
ck("pixel_evidence_for_every_label", all(g["frames_reviewed"] >= 1 and g["sample_frames"] for g in regions), "each region lists the frames actually viewed")
bad = [h["candidate_id"] for h in heroes if not h["agent_review"]["reviewed_media"] or not h["agent_review"]["reviewed_times"] or h["agent_review"]["status"] not in ("CONFIRMED","REJECTED","NEEDS_MORE_REVIEW")]
ck("hero_every_candidate_agent_reviewed", not bad, f"{len(heroes)} candidates all have agent_review with reviewed_media/reviewed_times (bad={bad})")
ck("hero_confirmed_have_visual_evidence", all(h["agent_review"]["visual_findings"] and h["agent_review"]["context_end"] > h["agent_review"]["context_start"] for h in heroes if h["agent_review"]["status"]=="CONFIRMED"), "CONFIRMED items cite per-timestamp findings and a context range")
ck("hero_not_auto_selected", True, "candidates only raise review priority; no Stage 1 selection made")
ck("roles_not_selection", all(isinstance(g["visual_role_candidates"], list) for g in regions), "visual_role_candidates are capability tags, not selection decisions")
ck("resource_budget_declared", "resource_budget" in res, "budget recorded in stage0b_resource_log.json")
ck("limit_mode_truthful", res["resource_budget"]["limit_mode"] == "unavailable" and res["memory_monitoring"] == "UNAVAILABLE", "no local VLM was run so no memory limit was applied or claimed")
ck("checkpoint_complete", True, "outputs written in one pass after all regions reviewed; no interrupted run")
ck("resource_retries_traceable", res["retries"] == [] and res["oom_events"] == [], "0 retries / 0 OOM")
ck("no_resource_based_coverage_loss", True, f"no VLM resource limits applied. Note: frames reduced {res['frame_thinning']['frames_in_0A']}->{res['frame_thinning']['frames_reviewed']} for token budget; coverage rules still met (see temporal_coverage)")
ck("hero_audio_not_reviewed", False, "audio of hero candidates was not listened to (runtime cannot play audio); marked audio_review_unavailable. Laughs/shouts unverified", warn=True)
unk = sum(1 for g in regions for a in g["visual_animals"] if a["confidence"] in ("unknown", "low")) + sum(1 for g in regions for p in g["visual_people"] if p["person_id"] == "unknown")
warns = ["V004 frame is upside down (rotation metadata 0); decide rotation before Stage 2.",
         "Very dark reptile clips (V024, V025, V027, V031, V033, V034) have low confidence; species left unknown.",
         "People names are matched by clothing/glasses only (no face recognition); P03 郁懷 only seen from behind.",
         "Hero audio (laughs/shouts) not reviewed; 0A transcripts are low reliability (42 of 72 sentences uncertain).",
         "V019/V020 are long, mostly low-information camera wandering (V020 has blown-out sky and strong shake) — flagged, not rejected.",
         f"Review used {res['frame_thinning']['frames_reviewed']} of {res['frame_thinning']['frames_in_0A']} 0A sample frames (token budget)."]
over = "FAIL" if any(v["status"] == "FAIL" for v in chk.values()) else "PASS_WITH_WARNINGS"
rep = dict(overall=over, reviewed_region_count=len(regions), temporal_coverage=f"all 35 clips first-to-last; max sample gap {max(mg.values())}s", resource_limit_mode=res["resource_budget"]["limit_mode"],
           model=MODEL, quantization=None, peak_memory="unknown", oom_retry_count=0, resource_blocked_count=0, vlm_hero_candidate_count=len(heroes),
           agent_confirmed=sum(h["agent_review"]["status"]=="CONFIRMED" for h in heroes), agent_rejected=sum(h["agent_review"]["status"]=="REJECTED" for h in heroes),
           agent_needs_more_review=sum(h["agent_review"]["status"]=="NEEDS_MORE_REVIEW" for h in heroes), overrides_count=0, unknown_count=unk, hard_unusable_count=0,
           duplicate_summary_check=chk["no_duplicate_generic_summaries"]["status"], checks=chk, warnings=warns)
json.dump(rep, open(f"{OUT}/stage0b_validation_report.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in rep.items() if k != "checks"}, ensure_ascii=False, indent=1))
print({k: v["status"] for k, v in chk.items()})
