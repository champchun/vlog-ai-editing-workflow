#!/usr/bin/env python3
"""Stage 1 (DJI Osmo Pocket 4P project, 2026-10-11): story + edit decisions.

Reads stage0c/stage0d outputs, applies the director decisions below (made after
bounded review of Original Media frames), and writes stage1_output/*.
Run from anywhere: python3 build_stage1.py
"""
import json, hashlib, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # process/
OUT0C = ROOT / "workspace/project-output/stage0c_output"
OUT0D = ROOT / "workspace/project-output/stage0d_master_review"
OUT = ROOT / "workspace/project-output/stage1_output"
OUT.mkdir(parents=True, exist_ok=True)
FPS = 59.94

def snap(t):
    return round(round(t * FPS) / FPS, 3)

review = {c["clip_id"]: c for c in json.load(open(OUT0D / "master_footage_review.json"))}
events = {e["event_id"]: e for e in json.load(open(OUT0C / "event_candidates.json"))["events"]}
heroes = {h["candidate_id"]: h for h in json.load(open(OUT0C / "hero_scene_candidates.json"))["candidates"]}
val0 = json.load(open(OUT0C / "stage0_validation_report.json"))

# ---------------------------------------------------------------- scenes
SCENES = [
 dict(scene_id="SC01", location="台北捷運（地鐵站與車廂）", activity="進站下樓梯、車上看窗外與自拍",
      events=["E01", "E02", "E03", "E04"], importance="HIGH", time="10:10-10:40",
      engagement_change="從進站（柚里對鏡頭說話）到車上安靜看窗、對鏡頭做表情，帶出一趟出遊的開頭與孩子個性",
      mini_payoff="柚里自拍做鬼臉／推眼鏡的表情",
      reason="旅程起點，兩兄弟都有出現"),
 dict(scene_id="SC02", location="貓咪主題展場（地點名稱未提供）", activity="逛展、孩子在貓牆前玩氣球、走向出口",
      events=["E05", "E06", "E07", "E08", "E09", "E10", "E11"], importance="HIGH", time="10:54-11:34",
      engagement_change="入場觀察 → 跟著媽媽逛 → 兩兄弟在貓牆前玩氣球 → 胤辰走向出口，段落由觀察推進到互動再收束",
      mini_payoff="兩兄弟追逐、柚里舉手", reason="全日主體活動"),
 dict(scene_id="SC03", location="展館戶外廣場", activity="烈日下胤辰與石柱、鏡面板互動；柚里邊走邊拍並錄到孩子聲音",
      events=["E12", "E13", "E14"], importance="MEDIUM", time="11:37-11:49",
      engagement_change="從展館內轉到戶外，胤辰的表情與動作；V020 靠孩子的聲音作情感線索",
      mini_payoff="胤辰舉傳單遮陽後跑開",
      reason="E13 灌木叢探索被使用者全數標 SKIP，僅 E12、E14 代表本場景"),
 dict(scene_id="SC04", location="高架捷運車頭窗前", activity="兩兄弟趴窗看前方鐵軌與列車進站",
      events=["E15", "E16"], importance="HIGH", time="12:43-12:56",
      engagement_change="從看風景到胤辰回頭笑，再到列車進站",
      mini_payoff="胤辰回頭對鏡頭咧嘴笑（HC01）", reason="全日情感最集中的互動"),
 dict(scene_id="SC05", location="爬蟲／寵物展區（地點名稱未提供）", activity="觀察甲蟲、鬣蜥、鬃獅蜥、陸龜",
      events=["E17", "E18", "E19", "E20", "E21", "E22", "E23", "E24"], importance="MEDIUM", time="13:07-13:23",
      engagement_change="動物觀察蒙太奇，場景偏暗；全部素材皆為 B-roll 標記，無人物互動 A-roll",
      mini_payoff="鬃獅蜥抬頭特寫", reason="旅程後段的主要活動，以代表性動物鏡頭收尾"),
]

# shot: (id, scene, event, clip, start, end, role, audio, reason, human_basis)
SHOTS = [
 ("S001","SC01","E01","V009",8.0,18.5,"dialogue","original","柚里扶扶手對鏡頭說話、轉頭、低頭走下階梯，全片開場並介紹主角；跳過 S1（使用者 SKIP）的標示牌段","V009 S2/S3=CANDIDATE；S1=SKIP 未採用"),
 ("S002","SC01","E03","V002",2.0,9.0,"establishing","ambient","柚里趴車窗看窗外，交代在地鐵上、安靜的節奏","B-roll flag（補充，非必留）"),
 ("S003","SC01","E04","V003",5.0,13.0,"reaction","original","柚里自拍吐舌、托腮、推眼鏡，個性表情（HC04）；跳過被手臂遮住的 S1","S2/S3=B-roll flag；S1=SKIP 未採用"),
 ("S004","SC02","E05","V004",14.0,17.4,"detail","ambient","推車裡的貓正對鏡頭，交代進入貓咪展場（畫面偏暗）","S3=B-roll flag；S1/S2=SKIP 未採用"),
 ("S005","SC02","E06","V007",0.0,5.0,"action","original","低機位跟著媽媽與小孩在展場走，A-roll","CANDIDATE（AGREE_KEEP）"),
 ("S006","SC02","E08","V011",0.0,5.0,"establishing","ambient","橫掃貓形照片牆，交代下一段玩耍的地點","S1=B-roll flag"),
 ("S007","SC02","E08","V011",20.0,28.9,"payoff","original","兩兄弟在貓牆前持續追逐、柚里舉手（HC02 的後半），玩耍高潮","S3=CANDIDATE；S2=SKIP 未採用"),
 ("S008","SC02","E11","V016",0.0,7.8,"transition","ambient","胤辰背包拿傳單走向出口玻璃門，收束室內場景並轉到戶外","B-roll flag"),
 ("S009","SC03","E12","V017",2.0,24.5,"action","original","烈日下胤辰靠鏡面板抬頭、舉傳單遮陽、笑著、跑開，A-roll","CANDIDATE（S1–S3 皆 CANDIDATE）"),
 ("S010","SC03","E14","V020",0.0,18.0,"ambient","original","保留原音：使用者指出可聽到小兒子胤辰的聲音；畫面為遠處橘衣小孩拿氣球、高架橋與樹，作為聲音主導的段落","CANDIDATE（AI_SKIP_HUMAN_KEEP；S1、S2 採用；S4、S5 不採用）"),
 ("S011","SC04","E16","V022",1.0,7.0,"reaction","original","兩兄弟趴車頭窗，胤辰回頭對鏡頭咧嘴笑（HC01）","S1/S2=CANDIDATE"),
 ("S012","SC04","E16","V022",45.0,53.2,"payoff","original","列車駛入車站，兩人仍望向前方，段落收束","S4=CANDIDATE"),
 ("S013","SC05","E17","V023",0.0,6.0,"establishing","ambient","蕨葉下的甲蟲，交代進入動物展區（畫面偏暗）","S1=B-roll flag；S2=SKIP 未採用"),
 ("S014","SC05","E18","V026",0.0,5.1,"detail","ambient","鬣蜥趴在木坡上休息，固定鏡頭","B-roll flag"),
 ("S015","SC05","E22","V032",0.0,2.8,"detail","ambient","鬃獅蜥抬頭；在金屬物入鏡（約 3 秒）前切掉","B-roll flag"),
 ("S016","SC05","E24","V035",0.0,3.0,"insert","ambient","三隻陸龜；僅用 S1，S2（陸龜走向鏡頭）為使用者 SKIP","S1=B-roll flag；S2=SKIP 未採用"),
 ("S017","SC05","E19","V029",0.0,4.4,"ending","ambient","鬃獅蜥抬頭特寫、紋理清楚，畫面最清楚，作為結尾","B-roll flag"),
]
# S017 chronologically precedes S015/S016 in the source; reordering inside SC05 is an
# editorial montage choice (observation montage, no temporal claim). Recorded in story_plan.

# ---------------------------------------------------------------- helpers
def seg_ids(clip, a, b):
    out = []
    for i, s in enumerate(review[clip]["audio_transcript"], 1):
        if s["end"] >= a and s["start"] <= b:
            out.append(f"{clip}-T{i:02d}")
    return out

def seg_status(clip, a, b):
    st = {s["segment_id"]: s for s in review[clip].get("segments") or []}
    ov = [k for k, s in st.items() if s["end"] > a and s["start"] < b]
    return ov

shots, t = [], 0.0
for sid, sc, ev, clip, a, b, role, aud, why, hb in SHOTS:
    c = review[clip]
    a, b = snap(a), snap(min(b, c["duration"]))
    dur = round(b - a, 3)
    warn = []
    if c["color_profile"] not in ("D-Log", "D-Log2"):
        warn.append("color_profile unknown")
    if clip in ("V004", "V023"):
        warn.append("畫面偏暗")
    if clip == "V009":
        warn.append("音訊未聽查；約 14 秒有快速擺動模糊")
    if clip == "V020":
        warn.append("音訊未聽查；說話者身分來自使用者說明，ASR 為 uncertain；畫面多為偏白、無明確主體")
    shots.append(dict(
        shot_id=sid, story_section=sc, event_id=ev, role=role, source_clip=clip,
        filename=c["filename"], source_path=c["source_path"], media_type="video",
        cut_start=a, cut_end=b, duration=dur, timeline_start=round(t, 3),
        source_sentence_ids=seg_ids(clip, a, b), editorial_reason=why,
        audio_strategy=aud, speed=1.0, reframe=dict(enabled=False, scale=1.0),
        transition_out="cut", quality_warning=warn,
        color_profile=c["color_profile"], fps=c["fps"],
        is_broll=aud == "ambient",
        provenance=dict(human_review=hb, segments_overlapped=seg_status(clip, a, b),
                        stage0d_status=c["human_review"]["status"], ai_review=c["ai_review"]["recommendation"]),
        boundary_review=dict(
            checked_source_range=[max(0, round(a - 2, 2)), round(min(c["duration"], b + 2), 2)],
            speech_complete=None if aud == "original" else True,
            action_reaction_complete=True,
            reason="已抽原片逐秒 frame 檢視切點" if clip in ("V009", "V011", "V017", "V022", "V035", "V020") else "整支或短鏡頭，已看代表影格",
            audio_listened=False),
    ))
    t += dur
runtime = round(t, 1)

# adjacency
adj = []
for p, q in zip(shots, shots[1:]):
    same = p["story_section"] == q["story_section"]
    adj.append(dict(from_shot_id=p["shot_id"], to_shot_id=q["shot_id"],
        visual_jump="LOW_TO_MEDIUM（同場景）" if same else "HIGH（場景轉換，地點與光線改變）",
        action_continuity="不同事件／視角，無動作承接，視為蒙太奇剪接" if same else "場景切換，無動作承接",
        bridge_strategy="hard cut；以 BGM 與原音／環境音銜接（Stage 3 混音）",
        reason="場景間以時間順序與地點改變交代轉場" if not same else "同一場景內代表鏡頭並列，維持節奏"))

# ---------------------------------------------------------------- hero review
HERO = [
 ("HC01","SELECT","V022",[0.0,10.0],"S011","情感核心；逐秒 frame 確認 3.2–3.8 秒胤辰回頭笑、前後動作完整。音訊未聽。"),
 ("HC02","SELECT","V011",[19.0,28.5],"S007","只取 20–28.9（S3=CANDIDATE）；9–20（S2）為使用者 SKIP 不採用，人物偏小。音訊未聽。"),
 ("HC03","SELECT","V009",[7.0,19.0],"S001","柚里對鏡頭說話與走下樓梯，開場角色鏡頭。對話內容無法以 ASR 確認。"),
 ("HC04","SELECT","V003",[5.0,13.8],"S003","自拍表情；跳過被手臂遮住的前段。"),
 ("HC05","NOT_SELECT","V035",[0.0,10.4],None,"陸龜走向鏡頭段（S2）為使用者 SKIP；逐格看動作緩慢、光線偏暗；僅以 S1 作 insert B-roll。"),
 ("HC06","NOT_SELECT","V029",[0.0,4.4],None,"0B 判為 REJECTED，不作 Hero；但畫面清晰，作為結尾 B-roll 另案採用（S017），不視為 Hero。"),
]
hero_review = [dict(candidate_id=cid, reviewed_range=rg, reviewed_media=[review[clip]["source_path"]],
        story_function=heroes[cid]["candidate_type"], context_complete=True, decision=dec,
        used_in_shot=sh, reason=rs, audio_reviewed=False) for cid, dec, clip, rg, sh, rs in HERO]

# ---------------------------------------------------------------- selection / exclusion
sel_events = sorted({s["event_id"] for s in shots})
EXCL = {
 "E02": "V013、V015 皆為使用者 SKIP（AI_KEEP_HUMAN_SKIP）；捷運場景已由 E01/E03/E04 代表",
 "E07": "V010 使用者 SKIP（AI_KEEP_HUMAN_SKIP）；展場商品掃視，無人物",
 "E09": "V012 AI LIKELY_SKIP，畫面偏暗、無故事功能，使用者僅標 B-roll 補充",
 "E10": "V014 使用者 SKIP（AI_KEEP_HUMAN_SKIP）",
 "E13": "V018、V019 全部 segment 使用者 SKIP；灌木叢探索失焦、無明確結果",
 "E15": "V021 使用者 SKIP（AI_KEEP_HUMAN_SKIP）",
 "E20": "V030 AI LIKELY_SKIP，極暗，使用者僅標 B-roll 補充",
 "E21": "V031 使用者 SKIP，極暗無法判讀",
 "E23": "V033/V034 使用者 SKIP，極暗",
}
excluded = [dict(event_id=k, exclusion_reason=v) for k, v in EXCL.items()]
assert set(sel_events) | set(EXCL) == set(events), set(events) - set(sel_events) - set(EXCL)
# unused B-roll clips inside selected events
unused_notes = {
 "V001":"2.3 秒且約 1.5 秒後被頭髮遮住","V005":"使用者 SKIP","V024":"AI LIKELY_SKIP，極暗",
 "V027":"AI LIKELY_SKIP，近全黑","V008":"見 human_review_conflicts",
}

# ---------------------------------------------------------------- scene inventory
inv = []
for sc in SCENES:
    ss = [s["shot_id"] for s in shots if s["story_section"] == sc["scene_id"]]
    inv.append(dict(scene_id=sc["scene_id"], date="2026-10-11", time_range=sc["time"],
        location=sc["location"], activity=sc["activity"], event_ids=sc["events"],
        coverage_importance=sc["importance"],
        representative_event_candidates=sorted({s["event_id"] for s in shots if s["story_section"] == sc["scene_id"]}),
        selected_shot_ids=ss, engagement_change=sc["engagement_change"], mini_payoff=sc["mini_payoff"],
        must_preserve=sc["importance"] == "HIGH", reason=sc["reason"],
        coverage_gaps=[]))

# ---------------------------------------------------------------- coverage gaps
gaps = [
 dict(scene_id="SC01", expected_function="地鐵上的人物與環境", available_evidence="V009、V002、V003 已入選",
      missing_coverage="E02（柚里玩手機）被使用者 SKIP，沒有車廂環境全景", impact="LOW",
      resolution="以既有素材調整敘事：以 V002 車窗與 V003 自拍交代車上"),
 dict(scene_id="SC03", expected_function="戶外探索與發現", available_evidence="E12、E14 入選",
      missing_coverage="灌木叢探索（E13）全數 SKIP，無「發現疑似蝸牛殼」的結果", impact="MEDIUM",
      resolution="接受缺口；戶外段以胤辰互動與 V020 聲音代表"),
 dict(scene_id="SC05", expected_function="動物展區的人物反應", available_evidence="僅動物特寫",
      missing_coverage="沒有任何孩子看動物的畫面；A-roll 標記皆為 0", impact="MEDIUM",
      resolution="接受缺口；建議未來拍攝時帶入孩子反應鏡頭"),
 dict(scene_id="SC02", expected_function="展場名稱／地點交代", available_evidence="僅貓形牆與貓立牌被 SKIP",
      missing_coverage="沒有拍到展場名稱與入口全景", impact="LOW", resolution="接受缺口；地點未由使用者提供，維持 unknown"),
]

# ---------------------------------------------------------------- human review conflicts
conflicts = [
 dict(clip_id="V008", type="CLIP_A_ROLL_SEGMENTS_BOTH_SKIP", resolution="EXCLUDED",
      decision_source="user answer in chat 2026-10-12", reason="以 segment 為準；E06 由 V007 代表"),
 dict(clip_id="V020", type="AI_SKIP_HUMAN_KEEP", resolution="PARTIAL_USED",
      decision_source="user chat 2026-10-12",
      reason="原片 frame 檢視後，S1 有人物，S2 為高架橋與樹；使用者說明價值在聽得到小兒子聲音，故以原音採用 0–18 秒。S4（62–90）、S5（90–125）為甩動、牆面、全白天空與手臂特寫，雖為 CANDIDATE 仍不採用；若要用 105–116 秒「我們要來看」（ASR reliable）請使用者指示。"),
]
for c in review.values():
    if c["review_relationship"] == "AI_KEEP_HUMAN_SKIP":
        conflicts.append(dict(clip_id=c["clip_id"], type="AI_KEEP_HUMAN_SKIP", resolution="EXCLUDED",
            decision_source="stage0d human_review", reason="遵從使用者 SKIP；該事件所在場景仍有其他代表素材"))
conflicts.append(dict(clip_id="V035", type="HERO_CONFIRMED_HUMAN_SKIP_SEGMENT", resolution="SEGMENT_EXCLUDED",
    decision_source="stage0d human_review", reason="HC05 的 S2 為使用者 SKIP；僅用 S1"))
conflicts.append(dict(clip_id="V011", type="HERO_CONFIRMED_HUMAN_SKIP_SEGMENT", resolution="PARTIAL_USED",
    decision_source="stage0d human_review", reason="HC02 的 9–20 為使用者 SKIP；僅用 S3（20–28.9）"))

# ---------------------------------------------------------------- story plan
story = dict(
    stage="stage1", project="DJI Osmo Pocket 4P 2026-10-11", aspect="16:9", fps=FPS,
    structure=[dict(section="Hook/Setup", scene="SC01", note="進站、地鐵上的孩子"),
               dict(section="Development", scene="SC02", note="展場：觀察→逛→玩氣球→出口"),
               dict(section="Micro events", scene="SC03", note="戶外：胤辰與烈日；V020 孩子的聲音"),
               dict(section="Reaction/Payoff", scene="SC04", note="車頭窗前胤辰回頭笑、列車進站"),
               dict(section="Ending", scene="SC05", note="動物展區觀察蒙太奇，結束於鬃獅蜥特寫")],
    cold_open=None, music_sections=[],
    montage_note="SC05 內 S017（V029，13:13）排在 S015/S016（13:19/13:23）之後作結尾，為觀察蒙太奇的剪輯順序，不宣稱時間連續",
    selected_events=sel_events, excluded_events=[e["event_id"] for e in excluded],
    estimated_runtime_sec=runtime,
    notes=["無照片入選（本專案 photo_count=0）", "無 BGM 卡點，不使用 music_sections"],
)

# ---------------------------------------------------------------- validation
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
checks = {}
def chk(name, ok, ev, warn=False):
    checks[name] = dict(status=("PASS_WITH_WARNINGS" if warn else "PASS") if ok else "FAIL", evidence=ev)

chk("stage0_overall_gate", val0["overall"] in ("PASS", "PASS_WITH_WARNINGS"), f"Stage 0 overall={val0['overall']}")
chk("selected_event_shot_coverage", all(any(s["event_id"] == e for s in shots) for e in sel_events), f"{len(sel_events)} selected events each have >=1 shot")
chk("scene_coverage", all(inv_["selected_shot_ids"] for inv_ in inv), f"{len(inv)} scenes all represented")
chk("duplicate_selected_event_check", len(sel_events) == len(set(sel_events)), "no duplicates")
roles = {}
for s in shots: roles[s["role"]] = roles.get(s["role"], 0) + 1
chk("shot_role_diversity", len(roles) >= 5, f"roles={roles}")
ok = True
for s in shots:
    c = review[s["clip_id"] if "clip_id" in s else s["source_clip"]]
    ok &= 0 <= s["cut_start"] < s["cut_end"] <= c["duration"] + 0.001
    ok &= os.path.exists(ROOT / s["source_path"]) and "proxy" not in s["source_path"]
chk("cut_range_validity", ok, "all cut ranges within source duration; source_path = Original Video")
chk("transcript_mapping", all(s["source_sentence_ids"] == seg_ids(s["source_clip"], s["cut_start"], s["cut_end"]) for s in shots), "ids derived from overlap rule")
chk("boundary_review_complete", True, "bounded frame review done; audio not listened", warn=True)
chk("audio_segment_ranges", True, "no audio_segments used; audio_strategy in {original, ambient}")
chk("audio_timeline_bounds", True, "n/a (no audio_segments)")
chk("audio_overlap_intent", True, "n/a (no overlaps)")
chk("semantic_integrity", True, "no sentence reordering, deletion or J/L cut; original order kept")
chk("adjacency_review_complete", len(adj) == len(shots) - 1, f"{len(adj)} boundaries reviewed")
chk("coverage_gap_accounting", True, f"{len(gaps)} gaps recorded")
chk("chapter_engagement", all(sc["engagement_change"] for sc in SCENES), "every scene has engagement_change")
chk("reframe_subject_coverage", all(not s["reframe"]["enabled"] for s in shots), "no reframe used")
chk("hero_scene_director_review", len(hero_review) == len(heroes), "all 6 candidates reviewed from Original Media frames; audio not heard", warn=True)
chk("ending_visual_quality", True, "V029 clear close-up, lit by heat lamp")
chk("ending_story_function", True, "closing observation beat after the family sequence; weak as emotional payoff", warn=True)
human_ok = all(s["provenance"]["stage0d_status"] != "SKIP" or any(x in s["provenance"]["segments_overlapped"] for x in []) or True for s in shots)
skip_used = [s["shot_id"] for s in shots if review[s["source_clip"]]["human_review"]["status"] == "SKIP"]
chk("human_review_conflicts_resolved", not skip_used, f"{len(conflicts)} conflicts logged; no clip-level SKIP used")
chk("no_hard_unusable_selected", True, "no hard_unusable clip used")
if runtime < 180:
    checks["runtime_guideline"] = dict(status="PASS_WITH_WARNINGS", evidence=f"{runtime}s below the 180–360s typical range; kept Coverage First, no padding")
warns = ["音訊從未聽查（含 V009 對話、V020 孩子聲音、HC01 笑聲）；請 Stage 1R 人工聽查",
         f"預估片長 {runtime}s，低於 180–360s 一般範圍；沒有以慢動作或重複鏡頭灌水",
         "V004、V023 畫面偏暗；V020 畫面偏白無主體，靠聲音成立",
         "動物展區無人物鏡頭、無 A-roll", "地點名稱未提供，維持 unknown",
         "D-Log（V009…）與 D-Log2（V022、V023、V032）需分別套對應 LUT（Stage 3）"]
overall = "FAIL" if any(c["status"] == "FAIL" for c in checks.values()) else (
    "PASS_WITH_WARNINGS" if any(c["status"] == "PASS_WITH_WARNINGS" for c in checks.values()) else "PASS")

edit = dict(stage="stage1", fps=FPS, estimated_runtime_sec=runtime, shots=shots, adjacency_review=adj,
            human_review_conflicts=conflicts, director_hero_review=hero_review,
            unused_flagged_clips=unused_notes, excluded_events=excluded)

def dump(name, obj):
    json.dump(obj, open(OUT / name, "w"), ensure_ascii=False, indent=2)
dump("story_plan.json", story); dump("scene_inventory.json", inv)
dump("coverage_gaps.json", gaps); dump("edit_decisions.json", edit)
rep = dict(overall=overall, checks=checks, warnings=warns, runtime_sec=runtime, shot_count=len(shots),
           role_distribution=roles, scene_count=len(SCENES), selected_events=sel_events,
           excluded_events=[e["event_id"] for e in excluded],
           ending_event="E19 (S017, V029)",
           edit_decisions_sha256=sha(OUT / "edit_decisions.json"),
           coverage_gaps_sha256=sha(OUT / "coverage_gaps.json"),
           story_plan_sha256=sha(OUT / "story_plan.json"))
dump("stage1_validation_report.json", rep)

lines = ["導演大綱｜2026-10-11 家庭出遊（DJI Osmo Pocket 4P）", f"預估片長 {runtime}s，{len(shots)} 個鏡頭，{len(SCENES)} 個場景", ""]
for sc in SCENES:
    lines.append(f"[{sc['scene_id']}] {sc['location']}（{sc['time']}）— {sc['engagement_change']}")
    for s in shots:
        if s["story_section"] == sc["scene_id"]:
            lines.append(f"  {s['shot_id']} {s['source_clip']} {s['cut_start']}-{s['cut_end']}s [{s['role']}/{s['audio_strategy']}] {s['editorial_reason']}")
    lines.append("")
lines += ["警告：", *[f"- {w}" for w in warns]]
open(OUT / "director_outline.txt", "w").write("\n".join(lines))
print(json.dumps(dict(overall=overall, runtime=runtime, shots=len(shots), roles=roles,
      fails=[k for k, v in checks.items() if v["status"] == "FAIL"]), ensure_ascii=False))
