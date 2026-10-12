#!/usr/bin/env python3
"""Stage 0D builder (adapted from examples/build_stage0d.py to this project's schema: lists/dicts, relative paths, no Stage 1 dependency)."""
import json, os, sys, subprocess, shutil, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from clip_reviews import REV, HERO_T, HERO_WHY, TRANS
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
WS = os.path.join(ROOT, "workspace"); P = WS + "/project-output"; S0C = P + "/stage0c_output"; OUT = P + "/stage0d_master_review"
KIT = os.path.join(ROOT, "stage-0D-master-footage-review")
FR, PX = OUT + "/frames", OUT + "/proxy"
for d in (OUT, FR, PX): os.makedirs(d, exist_ok=True)
J = lambda p: json.load(open(p))
cat = J(S0C + "/metadata_catalog.json")["clips"]; vis = {r["clip_id"]: r for r in J(S0C + "/visual_summary.json")["regions"]}
ev = J(S0C + "/event_candidates.json")["events"]; hs = J(S0C + "/hero_scene_candidates.json")["candidates"]
b0 = {r["clip_id"]: r for r in J(P + "/stage0b_output/ai_visual_review.json")["regions"]}
tr = {t["file"]: t for t in J(P + "/stage0a_output/transcripts.json")["clips"]}
assert J(S0C + "/stage0_validation_report.json")["overall"] in ("PASS", "PASS_WITH_WARNINGS")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
in_hash = {n: sha(f"{S0C}/{n}") for n in ("metadata_catalog.json", "visual_summary.json", "event_candidates.json", "hero_scene_candidates.json", "stage0_validation_report.json")}
ev_by = {}
for e in ev:
    for c in e["clip_ids"]: ev_by.setdefault(c, []).append(dict(event_id=e["event_id"], title=e["title"], type=e["event_type"]))
hs_by = {}
for h in hs: hs_by.setdefault(h["clip_id"], []).append(dict(candidate_id=h["candidate_id"], agent_status=h["agent_review"]["status"], start=h["candidate_start"], end=h["candidate_end"], reason=h["why_potential_hero"], event_id=h.get("event_id")))
STAT = {"CONFIRMED": "Agent 複核確認", "REJECTED": "Agent 複核否決", "NEEDS_MORE_REVIEW": "尚待複核"}

def run(c): return subprocess.run(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def frame(src, t, out):
    p = f"{FR}/{out}"
    if not os.path.exists(p): run(["ffmpeg", "-y", "-ss", str(max(t, 0)), "-i", src, "-frames:v", "1", "-q:v", "4", "-vf", "scale=640:-2", p])
    return os.path.exists(p)

clips, ext = [], 0
for c in cat:
    cid = c["clip_id"]; dur = c["duration"]; src = os.path.join(ROOT, c["source_path"]); r = b0[cid]; g = c.get("gps_auxiliary") or {}
    st = r["sample_times"]
    hero_t = min(HERO_T[cid], max(dur - 0.1, 0)); frame(src, hero_t, f"{cid}_hero.jpg")
    pcts = [] if dur < 15 else ([0.25, 0.5, 0.75] if dur <= 60 else [0.1, 0.3, 0.5, 0.7, 0.9])
    if dur < 15 and dur > 4: pcts = [0.5]
    strip = []
    for p in pcts:
        tgt = dur * p; t = min(st, key=lambda x: abs(x - tgt)) if st else tgt   # content points from 0B first, % as fallback
        if abs(t - hero_t) < 0.8: t = tgt
        name = f"{cid}_c{int(p*100):02d}.jpg"; frame(src, t, name); strip.append(dict(img=name, ts=round(t, 2), basis="0B 抽樣內容點" if st else "百分比"))
    sents = tr[c["filename"]]["sentences"]
    audio = [dict(start=s["start"], end=s["end"], text=s["text"], status=s["transcript_status"], review_reason=s["review_reason"], zh_reference=TRANS.get(s["text"])) for s in sents]
    ppl = [f"{p['name']}（{p['person_id']}）" if p["name"] else "未確認人物" for p in vis[cid]["visual_people"]]
    unconf = [p["evidence"] for p in vis[cid]["visual_people"] if p["person_id"] == "unknown"]
    warnings = []
    if any(s["status"] == "uncertain" for s in audio): warnings.append(f"語音不確定：{sum(s['status']=='uncertain' for s in audio)}／{len(audio)} 句標為不確定，不可當作確定台詞。")
    if unconf: warnings.append("含未確認人物：" + "；".join(unconf))
    if r["coverage_gaps"]: warnings.append("視覺覆蓋缺口：主體或物種不確定，或畫面太暗，已標為低信心而非硬猜。")
    fl = r["quality"]["flags"]
    FL = {"frame_upside_down_rotation_metadata_0": "畫面上下顛倒（旋轉資訊為 0）", "very_dark": "極暗", "subject_unclear": "主體不清楚", "very_short": "片長極短", "long_low_information": "長片但資訊量低",
          "shake_at_110s": "約 110 秒激烈晃動", "overexposed_sky": "天空過曝", "strong_shake": "大幅晃動", "whip_pans": "快速甩動鏡頭", "focus_hunting": "焦點反覆跳動", "mirror_panel_veil_on_right": "右側鏡面反射造成朦朧", "window_haze": "車窗朦朧"}
    if fl: warnings.append("畫質提醒：" + "、".join(FL.get(f, f) for f in fl))
    rec, pri, why = REV[cid]
    rx = r["reaction"]; has_react = rx not in ("n/a", "unknown") and "安靜" not in rx
    nm = lambda l: [x["label"] if isinstance(x, dict) else x for x in l]
    clips.append(dict(
        clip_id=cid, filename=c["filename"], source_path=c["source_path"], duration=dur, resolution=f"{c['width']}x{c['height']}", fps=c["fps"],
        creation_time_utc=c["creation_time_utc"], capture_time_local_at_gps_location=g.get("local_time_at_gps_location"), gps_location_utc_offset=g.get("gps_location_utc_offset"),
        color_profile=c["color_profile"], color_profile_source=c["color_profile_source"],
        hero_frame=f"{cid}_hero.jpg", hero_time=hero_t, hero_basis=HERO_WHY, contact_strip=strip,
        play_url=f"proxy/{cid}_proxy.mp4", visual_summary=vis[cid]["visual_summary"],
        visible_people=ppl, visible_animals=nm(vis[cid]["visual_animals"]), visual_objects=vis[cid]["visual_objects"], visual_actions=vis[cid]["visual_actions"],
        reaction=rx, has_reaction=has_react, audio_transcript=audio,
        audio_summary=("；".join(f"[{a['start']:.0f}-{a['end']:.0f}s]{a['text']}" + (f"（參考翻譯：{a['zh_reference']}，未確認）" if a["zh_reference"] else "") + ("（不確定）" if a["status"] == "uncertain" else "") for a in audio) or "沒有偵測到可辨識的語音"),
        events=ev_by.get(cid, []), hero_scenes=[dict(h, status_label=STAT[h["agent_status"]]) for h in hs_by.get(cid, [])],
        review_warnings=warnings,
        ai_review=dict(recommendation=rec, priority=pri, reason=why, basis="視覺複核、事件價值、Hero 複核、畫質、重複性；不是最終選用決定"),
        human_review=dict(status="NOT_REVIEWED", reason="", summary_feedback=dict(action="NONE", text="", target_fields=[], affects_selection=False, updated_at=None)),
        review_relationship="HUMAN_NOT_REVIEWED"))
# ---- proxies: 720p H.264/AAC, timing 1:1 ----
pm = []
for c in clips:
    out = f"{PX}/{c['clip_id']}_proxy.mp4"; src = os.path.join(ROOT, c["source_path"])
    if not os.path.exists(out):
        run(["ffmpeg", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale=1280:-2,format=yuv420p", "-c:v", "h264_videotoolbox", "-b:v", "3M", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out])
    d = lambda f: float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))
    pd = d(out) if os.path.exists(out) else None
    pm.append(dict(clip_id=c["clip_id"], source=c["source_path"], proxy=os.path.relpath(out, OUT), source_duration=c["duration"], proxy_duration=pd and round(pd, 3),
                   time_offset=pd and round(pd - c["duration"], 3), mapping="1:1" if pd is not None and abs(pd - c["duration"]) < 0.15 else "MISMATCH",
                   use="Stage 0D review only; NOT a source for Stage 1/2/3"))
json.dump(pm, open(OUT + "/proxy_manifest.json", "w"), ensure_ascii=False, indent=1)
json.dump(clips, open(OUT + "/master_footage_review.json", "w"), ensure_ascii=False, indent=1)
if not os.path.exists(OUT + "/human_footage_review.json"): json.dump({}, open(OUT + "/human_footage_review.json", "w"))
if not os.path.exists(OUT + "/review_cases.json"): json.dump([], open(OUT + "/review_cases.json", "w"))
json.dump(in_hash, open(OUT + "/.stage0c_input_hashes.json", "w"), indent=1)
shutil.copy(KIT + "/scripts/app.py", OUT + "/app.py"); shutil.copy(KIT + "/scripts/master_footage_review.html", OUT + "/master_footage_review.html"); shutil.copy(KIT + "/scripts/quick_review.html", OUT + "/quick_review.html")
print("clips", len(clips), "proxies", sum(p["mapping"] == "1:1" for p in pm))
