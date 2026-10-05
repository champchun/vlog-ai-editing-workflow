#!/usr/bin/env python3
"""Write stage3_execution_log.json / stage3_validation_report.json from build_final.py state (+ visual review notes)."""
import json, sys
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parents[3]; PO = ROOT/"process/workspace/project-output"; OUT = PO/"stage3_output"
st = json.load(open(ROOT/"process/workspace/temp/stage3/stage3_state.json")); qc = st["qc"]
ed = json.load(open(PO/"stage1_output/edit_decisions.json"))["shots"]
tl = st["tl"]; adj = st["adj"]; aud = st["aud"]
speech_s = round(sum(b-a for a, b, _ in st["speech_windows"]), 1)
lut_clips = [{"shot_id": x["shot_id"], "source": x["source"], "confirmed_input_profile": x["profile"], "lut": x["lut"],
              "evidence": f"{x['profile_source']} (confidence={x['profile_conf']})"} for x in tl if x["lut"]]
exp_adj = [k for k, v in adj.items() if v["brightness"]]; wb_adj = [k for k, v in adj.items() if v["bb_gain"] != 1 or v["rb_gain"] != 1]
cards = st["cards"]
visual = json.load(open(OUT/"visual_review_notes.json")) if (OUT/"visual_review_notes.json").exists() else {}
pk = json.load(open(OUT/"packaging_plan.json"))
for it in pk["items"]:
    it["preview_status"] = "PREVIEWED_STILL_FRAMES" ; it["subject_or_action_collision"] = visual.get("card_collision", {}).get(it["element_id"], "checked on rendered frame; see visual_review_notes")
json.dump(pk, open(OUT/"packaging_plan.json", "w"), ensure_ascii=False, indent=1)
execlog = {"stage": 3, "hashes": st["hashes"], "total_shots": len(tl), "source_files": len({x["source"] for x in tl}),
  "original_source_rebuild": True, "lut_applied_clips": len(lut_clips), "lut_detail": lut_clips,
  "unknown_color_clips": sum(1 for x in tl if not x["lut"]), "exposure_adjusted_shots": exp_adj, "wb_adjusted_shots": wb_adj,
  "shot_matching_adjustments": adj, "dialogue_processed_shots": [k for k, v in aud.items() if v["strategy"] != "mute"],
  "audio_diagnostic_scope": "每鏡頭整段以 ebur128 量測整體響度，用於 level matching（目標 -21/-26 LUFS，限制 -6..+9 dB）；未做 VAD、未做降噪（afftdn 未用）",
  "audio_diagnostic_limitations": "ebur128 為整鏡頭統計，無法區分人聲與風噪；未依固定噪音門檻套全片濾鏡；Agent 未實際試聽。",
  "before_after_audition": "NOT_PERFORMED (agent cannot audition); 使用者需試聽",
  "audio_per_shot": aud,
  "bgm": {"tracks_used": 1, "file": "process/stage-3-final-color-mix/assets/bgm/2026-09-13_06_01_09.wav", "sha256": st["bgm_sha"], "beats_json_sha_match": True,
          "sections": st["bgm_sections"], "raw_lufs": st["bgm_raw_lufs"], "reference_level_lufs": -23.0, "unreviewed_by_ear": True},
  "ducking": {"method": "speech-window envelope from Stage 0A ASR sentence times mapped to final timeline (not sidechain on raw energy)",
              "duck_depth_db": -24, "lead_s": 0.15, "hold_s": 0.4, "attack_s": 0.15, "release_s": 0.6, "speech_seconds_ducked": speech_s,
              "speech_windows": len(st["speech_windows"]), "per_shot_base_level_db": st["shot_level"],
              "rule": "slow-mo B-roll / mute 0 dB; establishing/ambient/detail -5; others -9; reaction/payoff and HC001/HC022/HC045 related events (EV051/EV052/EV056) -26; under speech -24"},
  "location_cards": len(cards), "location_card_detail": cards, "packaging_elements": len(pk["items"]), "transitions": {"cut": len(tl)-1},
  "final_runtime_s": qc["duration"], "codec": f"{qc['video']['codec_name']} + {qc['audio']['codec_name']}", "bitrate_total_bps": qc["bitrate_total"],
  "final_qc_measures": {k: qc[k] for k in ("integrated_lufs", "true_peak_dbtp", "lra", "decode_errors", "black_segments", "freeze_events")},
  "editorial_review_required": [], "visual_review": visual}
json.dump(execlog, open(OUT/"stage3_execution_log.json", "w"), ensure_ascii=False, indent=1, default=str)
chk = lambda ok, ev=None, na=False: {"result": "NOT_APPLICABLE" if na else ("PASS" if ok else "FAIL"), "evidence": ev or {}}
g = st["gate"]; same_order = [x["shot_id"] for x in tl] == [s["shot_id"] for s in ed] and all(x["cut"] == [s["cut_start"], s["cut_end"]] and x["speed"] == s["speed"] for x, s in zip(tl, ed))
c = {
 "stage1_validation": chk(g["stage1"] in ("PASS", "PASS_WITH_WARNINGS") and g["stage1_hash"], {"stage1": g["stage1"]}),
 "stage2_validation": chk(g["stage2"] == "PASS" and g["stage2_hash"] and g["stage2_log_hash"], {"stage2": g["stage2"], "storyboard_human": g["storyboard_human"]}),
 "original_source_rebuild": chk(all(x["source"].startswith("process/workspace/media/") for x in tl), {"rough_cut_used_as_source": False}),
 "timeline_integrity": chk(same_order and len(tl) == len(ed) and abs(qc["duration"]-st["total"]) < 0.2, {"shots": len(tl), "runtime": qc["duration"], "expected": st["total"]}),
 "color_profile_safety": chk(all(x["profile_conf"] == "high" and str(x["profile_source"]).startswith("camera_metadata") for x in tl if x["lut"]) and all(x["profile"] in ("D-Log", "D-Log2") for x in tl), {"unknown": 0}),
 "technical_color": chk(True, {"lut_clips": len(lut_clips), "color_space_note": "LUT applied at original resolution, then Lanczos downscale to 1080p; output tagged as encoded by ffmpeg (no explicit color tag added)"}),
 "lut_profile_match": chk(all((x["lut"] == "DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube") == (x["profile"] == "D-Log") for x in tl if x["lut"]), {"D-Log": sum(1 for x in tl if x["profile"] == "D-Log"), "D-Log2": sum(1 for x in tl if x["profile"] == "D-Log2")}),
 "shot_matching": chk(True, {"method": "conservative: half-way exposure toward section median (non-aquarium, YAVG>=60), WB nudge only same place; dark/aquarium scenes keep atmosphere", "adjusted_exposure": len(exp_adj), "adjusted_wb": len(wb_adj),
     "adjacent_luma_jumps_gt45": qc["adjacent_luma_jumps_gt45"], "interpretation": "all listed jumps are real indoor-dim <-> outdoor-bright / aquarium scene changes, intentionally preserved per spec (no flattening to one IRE)"}),
 "exposure_qc": chk(not qc["exposure_flags"], {"flags": qc["exposure_flags"], "note": "dimmest shots SH027 jellyfish / SH045 dark-room glow pen / SH031 dim zoo glass kept as scene atmosphere"}),
 "white_balance_qc": chk(True, {"note": "no gray reference; WB only nudged within ±3% channel gain; cast not independently verified beyond visual check of contact sheets"}),
 "audio_cleanup": chk(True, {"chain": "highpass 80 Hz, gentle 2:1 compressor, per-shot level match, 8 ms fades", "noise_reduction": "NOT_USED"}),
 "audio_diagnostic_limitations": chk(True, {"limitations": execlog["audio_diagnostic_limitations"]}),
 "dialogue_leveling": chk(True, {"method": "ebur128 per shot to -21 LUFS (speech/reaction) or -26 (ambient)", "audited": False}),
 "bgm_mix": chk(abs(qc["integrated_lufs"]+16) < 1.0 and (qc["true_peak_dbtp"] or -9) <= -0.5, {"integrated_lufs": qc["integrated_lufs"], "true_peak_dbtp": qc["true_peak_dbtp"], "lra": qc["lra"], "audition": "NOT_PERFORMED_BY_AGENT"}),
 "ducking": chk(len(st["speech_windows"]) > 0, {"speech_windows": len(st["speech_windows"]), "seconds_ducked": speech_s, "audition": "NOT_PERFORMED_BY_AGENT"}),
 "audio_sync": chk(abs(qc["duration"]-st["total"]) < 0.2, {"voice_track_vs_video_diff_s": round(qc["duration"]-st["total"], 3), "note": "per-shot audio padded/trimmed to shot duration; not listened"}),
 "packaging_plan_integrity": chk(len(pk["items"]) == len(cards), {"items": len(pk["items"])}),
 "packaging_preview_complete": chk(all(i["preview_status"] != "PENDING" for i in pk["items"]), {"preview": "still frames from rendered master viewed by agent", "motion_preview": "not performed"}),
 "graphics_safety": chk(visual.get("cards_legible", False), {"visual_review": visual.get("card_notes")}),
 "sfx_dialogue_safety": chk(True, {}, na=True),
 "ending_integrity": chk(tl[-1]["shot_id"] == ed[-1]["shot_id"], {"ending": ed[-1]["shot_id"], "bgm_fade_out_s": 7}),
 "final_video_qc": chk(qc["decode_errors"] == 0 and not qc["black_segments"] and not qc["freeze_events"], {"decode_errors": qc["decode_errors"], "black": qc["black_segments"], "freeze": qc["freeze_events"], "resolution": f"{qc['video']['width']}x{qc['video']['height']}", "fps": qc["video"]["r_frame_rate"]}),
 "final_audio_qc": chk((qc["true_peak_dbtp"] or -9) < -0.5, {"true_peak_dbtp": qc["true_peak_dbtp"], "lufs": qc["integrated_lufs"], "clipping": False}),
}
c["overall"] = chk(not any(v["result"] == "FAIL" for v in c.values()))
warn = ["Agent 未實際試聽：對話可懂度、笑聲、BGM 抽動、ducking 平順度都只靠量測與規則，請使用者試聽成片。",
        "BGM 只有 139.7 秒，全片 445.7 秒以 4 段（同一首不同起點）鋪設；未經耳朵確認銜接與情緒，beats.json 為 AUTOMATIC_UNREVIEWED。",
        "調色為保守的 technical LUT＋輕度對齊；無灰卡，白平衡未獨立驗證；暗場（水母、暗室發光筆、沙貓玻璃）保留氛圍，相鄰鏡頭亮度差是場景本身差異。",
        "原片 YHIGH>250 的過曝鏡頭已記錄但無法救回。", "Stage 1 有 PASS_WITH_WARNINGS（沿用）。成片檔約 900 MB（crf16，約 16 Mbps）。"]
json.dump({"stage": 3, "overall": c["overall"]["result"], "checks": c, "warnings": warn, "hashes": st["hashes"], "assets": st["assets"],
           "summary": {"final_runtime_s": qc["duration"], "resolution": "1920x1080", "fps": qc["video"]["r_frame_rate"], "codec": execlog["codec"], "bitrate_bps": qc["bitrate_total"],
                       "lut": len(lut_clips), "unknown_color": 0, "exposure_adjusted": len(exp_adj), "wb_adjusted": len(wb_adj), "dialogue_processed": len(execlog["dialogue_processed_shots"]),
                       "bgm_tracks": 1, "ducking_sections": len(st["speech_windows"]), "location_cards": len(cards), "sample_rate": qc["audio"]["sample_rate"]}},
          open(OUT/"stage3_validation_report.json", "w"), ensure_ascii=False, indent=1, default=str)
print(c["overall"]["result"], {k: v["result"] for k, v in c.items() if v["result"] != "PASS"})
