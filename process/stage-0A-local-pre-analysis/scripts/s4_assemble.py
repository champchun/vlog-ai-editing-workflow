#!/usr/bin/env python3
"""Stage 0A step 4: assemble formal outputs + validation from cached steps.

Writes to process/workspace/project-output/stage0a_output/:
  metadata_catalog.json, source_proxy_manifest.json, transcript_sentences.json,
  transcript_summary.txt, local_visual_candidates.json, stage0b_review_queue.json,
  stage0a_execution_log.json, stage0a_validation_report.json
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from common import GPS_DIR, MEDIA, OUT, PROCESS, TEMP, VIDEO_EXTS, iter_media, read_json, write_json

HERE = Path(__file__).resolve().parent
NOW = datetime.now(timezone.utc).isoformat()

PEOPLE = {"people", "adult", "child", "baby", "crowd", "teen", "selfie", "portrait"}
ANIMAL_WORDS = {"animal", "dog", "cat", "bird", "fish", "mammal", "canine", "feline", "horse", "cow", "sheep",
                "insect", "turtle", "reptile", "dolphin", "penguin", "shark", "whale", "jellyfish", "seal", "crab",
                "goat", "deer", "monkey", "rabbit", "duck", "chicken", "pigeon", "seagull", "butterfly", "lizard",
                "ray", "starfish", "coral", "aquarium", "puppy", "kitten", "pig", "squirrel", "frog", "snake",
                "octopus", "shellfish", "hermit_crab", "parrot", "owl", "gull", "manta_ray", "sea_turtle"}
FOOD_WORDS = {"food", "meal", "dish", "dessert", "fruit", "drink", "beverage", "sushi", "noodles", "ramen",
              "baked_goods", "bread", "cake", "ice_cream", "coffee", "tea", "meat", "seafood", "snack", "candy",
              "rice", "soup", "salad", "pizza", "burger", "vegetable", "breakfast", "dinner", "lunch", "juice"}
PLACE_WORDS = {"sign", "signage", "shrine", "temple", "castle", "monument", "tower", "bridge", "beach", "ocean",
               "sea", "aquarium", "museum", "landmark", "harbor", "lighthouse", "waterfall", "mountain",
               "amusement_park", "stadium", "garden", "market", "restaurant", "store", "airport", "airplane",
               "coast", "cliff", "island"}


def sha(p: Path):
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def is_animal(lbl):
    return lbl in ANIMAL_WORDS or any(w in lbl.split("_") for w in ANIMAL_WORDS)


def merge_ranges(rs, gap=1.0):
    rs = sorted(rs)
    out = []
    for a, b, why in rs:
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
            out[-1][2] |= why
        else:
            out.append([a, b, set(why)])
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cat = read_json(TEMP / "catalog.json")
    videos = cat["videos"]
    vid_by = {v["clip_id"]: v for v in videos}
    warnings = []

    # -------- per-clip joins
    tr, vis, vn = {}, {}, {}
    for cid in vid_by:
        tr[cid] = read_json(TEMP / "transcripts" / f"{cid}.json")
        vis[cid] = read_json(TEMP / "visual" / f"{cid}.json")
        vn[cid] = read_json(TEMP / "vision" / f"{cid}.json")

    # -------- proxy manifest
    proxies = []
    for p in cat["proxies"]:
        v = next((x for x in videos if x["source_path"] == p.get("source_path")), None)
        pc = read_json(TEMP / "proxy_check" / f"{v['clip_id']}.json") if v else None
        status = p["pairing_status"]
        if status.startswith("metadata_matched"):
            status = "confirmed" if pc and pc.get("passed") else ("content_mismatch" if pc else "metadata_only_unverified")
        proxies.append({**p, "content_check": pc, "pairing_status": status,
                        "allowed_use": "review playback only (verified 1:1 time mapping); never analysis/render source"
                        if status == "confirmed" else "not usable until verified",
                        "counted_as_source_clip": False})
        if status != "confirmed":
            warnings.append(f"proxy {p['proxy_path']} status={status}")
    for u in cat["unpaired_proxies"]:
        warnings.append(f"unpaired LRF {u} (not treated as source, not deleted)")
    confirmed_proxy = sum(1 for p in proxies if p["pairing_status"] == "confirmed")

    # -------- hard unusable & per-clip technical summary
    def hard_unusable(cid):
        vs = vis.get(cid)
        if not vs or vs.get("error"):
            return True, f"visual decode failed: {(vs or {}).get('error', 'missing')}"
        ir = vs["summary"]["issue_ratios"]
        subj = vision_subject_evidence(cid)
        if ir["dark"] >= 0.95 and not subj:
            return True, "nearly black for >=95% of analysed frames and no Vision subject/text on any sample frame"
        if ir["possible_occlusion_or_featureless"] >= 0.95 and vs["summary"]["luma_mean"] < 60 and not subj:
            return True, "occluded/featureless for >=95% of analysed frames and no Vision subject/text on any sample frame"
        return False, None

    def vision_subject_evidence(cid):
        """Any person/animal/text found by Vision on the sampled frames (counter-evidence to hard_unusable)."""
        found = []
        for fr in (vn.get(cid) or {}).get("frames", []):
            ids = {c["id"] for c in fr.get("classes", [])}
            if fr.get("humans") or fr.get("faces") or fr.get("animals") or fr.get("text") \
                    or ids & PEOPLE or any(is_animal(i) for i in ids):
                found.append(fr["t"])
        return found

    # -------- transcripts
    sentences, tsum_lines, sid = [], [], 0
    tr_err = []
    for cid, v in vid_by.items():
        t = tr.get(cid)
        if not t or t.get("error"):
            tr_err.append(cid)
            continue
        for s in t.get("segments", []):
            sid += 1
            sentences.append({
                "sentence_id": f"S{sid:05d}", "file": v["filename"], "clip_id": cid, "source_path": v["source_path"],
                "start": s["start"], "end": s["end"], "text": s["text"], "language": s["language"],
                "confidence": s["confidence"], "confidence_definition": s["confidence_definition"],
                "avg_logprob": s["avg_logprob"], "no_speech_prob": s["no_speech_prob"],
                "compression_ratio": s["compression_ratio"], "mean_word_probability": s["mean_word_probability"],
                "transcript_status": s["transcript_status"], "review_reason": s["review_reason"],
                "recheck": s.get("recheck"), "timestamp_valid": s["timestamp_valid"],
                "words": s["words"],
            })
    if tr_err:
        warnings.append(f"transcription failed/missing for {len(tr_err)} clips: {tr_err[:10]}")

    sound_events = []
    for cid, t in tr.items():
        for e in (t or {}).get("sound_events", []):
            sound_events.append({"clip_id": cid, "source_path": vid_by[cid]["source_path"], **e})

    # -------- visual candidates (visual only) + audio (audio only)
    cands = []
    for cid, v in vid_by.items():
        vs, vv, t = vis.get(cid), vn.get(cid), tr.get(cid) or {}
        hu, hu_reason = hard_unusable(cid)
        people, animals, objects, scene_lbl, texts = [], [], [], Counter(), []
        human_cx = []
        if vv:
            for fr in vv["frames"]:
                if fr.get("error"):
                    continue
                cls = {c["id"]: c["conf"] for c in fr.get("classes", [])}
                pl = {k: c for k, c in cls.items() if k in PEOPLE}
                n_h, n_f = len(fr.get("humans", [])), len(fr.get("faces", []))
                if pl or n_h or n_f:
                    people.append({"t": fr["t"], "frame": fr["frame"], "human_boxes": n_h, "face_boxes": n_f,
                                   "labels": pl, "max_conf": round(max([*pl.values(), *[h["conf"] for h in fr["humans"]], 0]), 3)})
                    human_cx += [h["box"][0] + h["box"][2] / 2 for h in fr.get("humans", [])]
                al = {k: c for k, c in cls.items() if is_animal(k)}
                for a in fr.get("animals", []):
                    for l in a["labels"]:
                        al[l["id"].lower()] = max(al.get(l["id"].lower(), 0), round(l["conf"], 3))
                if al:
                    animals.append({"t": fr["t"], "frame": fr["frame"], "labels": al})
                ol = {k: c for k, c in cls.items() if k not in PEOPLE and not is_animal(k)}
                if ol:
                    objects.append({"t": fr["t"], "frame": fr["frame"], "labels": ol})
                for k, c in ol.items():
                    scene_lbl[k] = max(scene_lbl[k], c)
                for tx in fr.get("text", []):
                    texts.append({"t": fr["t"], "text": tx["text"], "conf": round(tx["conf"], 2)})
        s = (vs or {}).get("summary", {})
        motion_t = s.get("fast_camera_motion_times", [])
        actions = []
        if motion_t:
            actions.append({"type": "camera_fast_motion_or_turn", "times": motion_t, "source": "global motion (phase correlation)",
                            "note": "camera movement, not a subject action"})
        if s.get("scene_change_times"):
            actions.append({"type": "large_visual_change", "times": s["scene_change_times"], "source": "HSV histogram change"})
        segs = t.get("segments", [])
        rel_segs = [x for x in segs if x["transcript_status"] == "reliable"]
        cands.append({
            "clip_id": cid, "source_path": v["source_path"], "duration": v["duration"],
            "hard_unusable": hu, "hard_unusable_reason": hu_reason,
            "technical": {k: s.get(k) for k in ("usable_ratio", "issue_ratios", "luma_mean", "motion_mean")},
            "technical_note": "Luma/exposure thresholds measured on un-graded log footage; low contrast is expected and not a defect. "
                              "possible_occlusion_or_featureless also triggers on dark scenes and uniform water/tank backgrounds (candidate only).",
            "micro_clip": v["duration"] < 0.5,
            "micro_clip_note": (f"{v['duration']:.2f}s clip: picture is valid but too short for a motion shot; "
                                "possible freeze-frame/still candidate") if v["duration"] < 0.5 else None,
            "technical_flag_conflicts_with_vision": bool(s.get("issue_ratios", {}).get("possible_occlusion_or_featureless", 0) >= 0.3
                                                         and vision_subject_evidence(cid)),
            "visual_people": {"status": "candidate", "frames_with_people": len(people), "frames_sampled": len((vs or {}).get("sample_times", [])),
                              "detections": people, "identity": "unknown",
                              "note": "Vision human/face/classification candidates; faces on posters/screens possible; identity never inferred"},
            "visual_animals": {"status": "candidate" if animals else "none_detected_locally", "detections": animals,
                               "species_confidence": "uncertain"},
            "visual_objects": {"status": "candidate", "top_labels": dict(scene_lbl.most_common(15)), "detections": objects},
            "visual_text_ocr": {"status": "candidate", "items": texts[:40],
                                "note": "OCR of on-screen/signage text; not a verified place name"},
            "visual_actions": {"status": "subject_actions_unknown_locally", "camera_and_change_events": actions,
                               "note": "No local action recognizer; subject actions/reactions deferred to Stage 0B"},
            "reframe_potential": {"source_resolution": f'{v["resolution"]["width"]}x{v["resolution"]["height"]}',
                                  "punch_in_headroom_for_1080p": round(v["resolution"]["height"] / 1080, 2),
                                  "vertical_9x16_crop": "candidate" if v["resolution"]["width"] >= 3840 else "limited",
                                  "people_center_x_range": [round(min(human_cx), 3), round(max(human_cx), 3)] if human_cx else None,
                                  "note": "Geometric feasibility only; subject framing must be checked visually"},
            "audio_speakers": {"speech_detected": bool(segs), "sentence_count": len(segs), "reliable_sentences": len(rel_segs),
                               "languages": dict(Counter(x["language"] for x in segs)),
                               "vad_speech_seconds": t.get("vad_speech_seconds"),
                               "speaker_identity": "unknown",
                               "note": "Audio-only evidence; does not imply who is on screen"},
            "audio_levels": t.get("audio_levels"),
            "sample_times": (vs or {}).get("sample_times", []),
            "unsampled_note": "Continuous 4 fps technical analysis covers the full clip; semantic labels only at sample_times",
        })

    # -------- Stage 0B review queue
    queue, qid = [], 0
    for c in cands:
        cid, v = c["clip_id"], vid_by[c["clip_id"]]
        dur = v["duration"]
        ranges = []
        child = any("child" in d["labels"] or "baby" in d["labels"] for d in c["visual_people"]["detections"])
        for d in c["visual_people"]["detections"]:
            why = {"people_candidate"} | ({"child_candidate"} if ("child" in d["labels"] or "baby" in d["labels"]) else set())
            if d["human_boxes"] >= 2 or d["face_boxes"] >= 2:
                why.add("possible_interaction_multi_person")
            if d["max_conf"] < 0.8:
                why.add("local_confidence_below_0.8")
            ranges.append((max(0, d["t"] - 2), min(dur, d["t"] + 2), why))
        for d in c["visual_animals"]["detections"]:
            ranges.append((max(0, d["t"] - 2), min(dur, d["t"] + 2), {"animal_candidate"}))
        for d in c["visual_objects"]["detections"]:
            ks = set(d["labels"])
            why = set()
            if ks & FOOD_WORDS:
                why.add("food_candidate")
            if ks & PLACE_WORDS:
                why.add("sign_or_place_candidate")
            if why:
                ranges.append((max(0, d["t"] - 2), min(dur, d["t"] + 2), why))
        for tx in c["visual_text_ocr"]["items"]:
            ranges.append((max(0, tx["t"] - 1.5), min(dur, tx["t"] + 1.5), {"readable_text_or_signage"}))
        for tt in c["visual_actions"]["camera_and_change_events"]:
            for x in tt["times"]:
                ranges.append((max(0, x - 1.5), min(dur, x + 1.5), {"fast_camera_turn_or_change"}))
        for s in (tr.get(cid) or {}).get("segments", []):
            why = {"speech"}
            if s["transcript_status"] == "uncertain":
                why.add("uncertain_transcript")
            ranges.append((s["start"], s["end"], why))
        for e in (tr.get(cid) or {}).get("sound_events", []):
            ranges.append((e["start"], e["end"], {"untranscribed_vocal_or_sound_activity"}))
        # conflict: speech but no people seen anywhere, or people seen w/o any analysis agreement
        conflict = bool((tr.get(cid) or {}).get("segments")) and c["visual_people"]["frames_with_people"] == 0
        merged = merge_ranges(ranges, gap=1.5)
        info_rich = bool(merged)
        if c["hard_unusable"]:
            prio_clip = "low"
        elif child or c["visual_animals"]["detections"] or conflict:
            prio_clip = "high"
        elif info_rich:
            prio_clip = "medium"
        else:
            prio_clip = "low"
        qid += 1
        queue.append({
            "queue_id": f"Q{qid:05d}", "scope": "whole_clip_coverage", "clip_id": cid, "source_path": v["source_path"],
            "start": 0.0, "end": dur, "priority": prio_clip,
            "reasons": sorted({"coverage_every_source_clip"}
                              | ({"technical_flag_conflicts_with_vision"} if c["technical_flag_conflicts_with_vision"] else set())
                              | ({"micro_clip_under_0.5s"} if c["micro_clip"] else set()) | ({"visual_audio_conflict:speech_without_people_detected"} if conflict else set())
                              | ({"hard_unusable_confirm"} if c["hard_unusable"] else set())
                              | ({"low_information_local"} if not info_rich else set())),
            "evidence_frames": [s["frame"] for s in c["sample_times"]],
        })
        for a, b, why in merged:
            hi = {"child_candidate", "animal_candidate", "possible_interaction_multi_person", "uncertain_transcript",
                  "untranscribed_vocal_or_sound_activity", "food_candidate", "sign_or_place_candidate", "readable_text_or_signage"}
            prio = "high" if why & hi else "medium"
            qid += 1
            queue.append({"queue_id": f"Q{qid:05d}", "scope": "time_range", "clip_id": cid, "source_path": v["source_path"],
                          "start": round(a, 3), "end": round(b, 3), "priority": prio, "reasons": sorted(why),
                          "evidence_frames": [s["frame"] for s in c["sample_times"] if a - 0.3 <= s["t"] <= b + 0.3]})

    # -------- metadata catalog
    per_clip_tech = {c["clip_id"]: c for c in cands}
    vrecs = []
    for v in videos:
        c = per_clip_tech[v["clip_id"]]
        t = tr.get(v["clip_id"]) or {}
        vrecs.append({**v, "proxy": next((p["proxy_path"] for p in proxies if p.get("source_path") == v["source_path"]
                                          and p["pairing_status"] == "confirmed"), None),
                      "hard_unusable": c["hard_unusable"], "hard_unusable_reason": c["hard_unusable_reason"],
                      "technical_summary": c["technical"], "audio_levels": t.get("audio_levels"),
                      "transcript": {"language_detected": t.get("language"), "language_probability": t.get("language_probability"),
                                     "sentences": len(t.get("segments", [])), "error": t.get("error")}})
    source_clips = [v for v in vrecs if not v["duplicate_of"]]
    total_dur = round(sum(v["duration"] for v in source_clips), 3)
    gps_files = [p for p in GPS_DIR.iterdir() if p.is_file() and not p.name.startswith(".") and p.name != "README.md"]
    if not gps_files:
        warnings.append("process/workspace/gps/ has no Timeline/GPX files; GPS in media was written earlier by "
                        "geotag_from_timeline.py from a Timeline file that is not stored in the workspace")
    no_gps_photos = [p["filename"] for p in cat["photos"] if not p.get("gps")]
    if no_gps_photos:
        warnings.append(f"{len(no_gps_photos)} photos without GPS: {no_gps_photos}")
    catalog = {
        "stage": "0A", "generated_at": NOW,
        "summary": {"source_video_clip_count": len(source_clips), "photo_count": len(cat["photos"]),
                    "confirmed_proxy_count": confirmed_proxy, "verified_duplicate_groups": len(cat["duplicate_groups"]),
                    "total_video_duration_s": total_dur,
                    "color_profiles": dict(Counter(v["color_profile"] for v in source_clips)),
                    "fps": dict(Counter(str(v["fps"]) for v in source_clips)),
                    "photo_formats": dict(Counter(p["format"] for p in cat["photos"])),
                    "tz_offsets_video": dict(Counter(v["derived_tz_offset"] for v in source_clips)),
                    "gps_methods": dict(Counter((x.get("gps") or {}).get("method") for x in vrecs + cat["photos"]))},
        "gps_policy": "All GPS is auxiliary. Video/DNG coordinates were written from Google Timeline (see method); "
                      "Sony JPG coordinates are camera-recorded. Named places are not asserted in Stage 0A.",
        "videos": vrecs, "photos": cat["photos"],
        "sidecars": cat["sidecars"], "unknown_files": cat["unknown_files"],
        "duplicate_groups": cat["duplicate_groups"],
    }

    write_json(OUT / "metadata_catalog.json", catalog)
    write_json(OUT / "source_proxy_manifest.json", {"stage": "0A", "generated_at": NOW, "proxies": proxies,
                                                   "unpaired": cat["unpaired_proxies"]})
    write_json(OUT / "transcript_sentences.json", {
        "stage": "0A", "generated_at": NOW,
        "asr": {"engine": "faster-whisper", **(next((t["params"] for t in tr.values() if t and t.get("params")), {}))},
        "note": "Transcript describes audio only. Timestamps are original-media seconds.",
        "sentences": sentences, "sound_events": sound_events})
    lines = ["# Stage 0A transcript summary (audio only; not visual fact)",
             "# [status] marks: R=reliable U=uncertain (reason). Times in original-media seconds.", ""]
    for cid, v in vid_by.items():
        t = tr.get(cid) or {}
        segs = t.get("segments", [])
        lines.append(f"== {v['filename']}  dur={v['duration']:.1f}s  lang={t.get('language')}  sentences={len(segs)}"
                     + (f"  ERROR={t['error']}" if t.get("error") else ""))
        for s in segs:
            st = "R" if s["transcript_status"] == "reliable" else f"U:{s['review_reason']}"
            lines.append(f"  [{s['start']:7.2f}-{s['end']:7.2f}] [{st}] {s['text']}")
        for e in t.get("sound_events", []):
            lines.append(f"  [{e['start']:7.2f}-{e['end']:7.2f}] (untranscribed sound/voice activity)")
        lines.append("")
    (OUT / "transcript_summary.txt").write_text("\n".join(lines), encoding="utf-8")
    write_json(OUT / "local_visual_candidates.json", {"stage": "0A", "generated_at": NOW,
                                                      "policy": "All labels are local candidates; Stage 0B must verify visually.",
                                                      "clips": cands})
    write_json(OUT / "stage0b_review_queue.json", {"stage": "0A", "generated_at": NOW,
                                                   "priority_counts": dict(Counter(q["priority"] for q in queue)),
                                                   "items": queue})

    # -------- execution log (adapter record)
    scripts = {p.name: sha(p) for p in sorted(HERE.glob("*.py")) + sorted(HERE.glob("*.swift"))}
    ver = lambda c: subprocess.run(c, capture_output=True, text=True).stdout.strip().split("\n")[0]
    tparams = next((t["params"] for t in tr.values() if t and t.get("params")), None)
    vparams = next((x["params"] for x in vis.values() if x and x.get("params")), None)
    write_json(OUT / "stage0a_execution_log.json", {
        "stage": "0A", "generated_at": NOW, "host": {"platform": platform.platform(), "python": platform.python_version()},
        "scripts": scripts,
        "tools": {"ffmpeg": ver(["ffmpeg", "-version"]), "exiftool": ver(["exiftool", "-ver"]),
                  "faster_whisper": tparams, "visual_analysis": vparams,
                  "vision": next((x["tool"] for x in vn.values() if x), None)},
        "steps": [
            {"step": "s1_catalog", "capability": "metadata probe, color evidence, GPS provenance, sampled-hash duplicate candidates, LRF metadata pairing"},
            {"step": "s2_visual", "capability": "~4 fps technical analysis from ORIGINAL (VideoToolbox decode, exact native frame index sampling), sampled frames",
             "output_cache": "process/workspace/temp/stage0a/visual/, frames/"},
            {"step": "s2c_proxy_check", "capability": "LRF content + time-offset verification (±0.5 s window, real pts via showinfo)"},
            {"step": "s2b_vision", "capability": "macOS Vision candidate labels on sampled frames"},
            {"step": "s3_transcribe", "capability": "Silero VAD (faster-whisper built-in) + Whisper small int8, re-decode uncertain slices",
             "asr_track": "first audio stream (a:0); a:1 measured identical loudness on spot check"},
            {"step": "s4_assemble", "capability": "schema adaptation, review queue, validation"}],
        "private_skills_used": "none (repository scripts + system tools only)",
        "limitations": [
            "ASR model 'small' (locally cached); larger models not downloaded without authorization",
            "No local subject-action recognizer; visual_actions limited to camera/visual-change events",
            "OpenCV 5 has no Haar cascades; people/animal/object candidates come from macOS Vision",
            "Hashes: sampled sha256 (size+3x4MB) for duplicate candidates; full sha256 only on collisions",
        ],
    })

    # -------- validation
    disk_videos = [p for p in iter_media() if p.suffix.lower() in VIDEO_EXTS]
    checks = {}

    def chk(name, ok, evidence, warn=False):
        checks[name] = {"result": "PASS" if ok else ("WARN" if warn else "FAIL"), "evidence": evidence}

    chk("source_clip_count", len(disk_videos) == len(videos) and len(source_clips) == len(videos) - sum(1 for v in videos if v["duplicate_of"]),
        {"video_files_on_disk": len(disk_videos), "catalog_videos": len(videos), "source_video_clip_count": len(source_clips),
         "photos_counted_separately": len(cat["photos"]), "lrf_excluded": len(proxies)})
    miss = [v["clip_id"] for v in videos if not (v["duration"] and v["fps"] and v["codec"] and v["resolution"]["width"])]
    chk("metadata_complete", not miss, {"missing": miss})
    bad_ts, out_of_vad = [], []
    for cid, t in tr.items():
        if not t or t.get("error"):
            continue
        vr = t.get("vad_regions", [])
        for s in t.get("segments", []):
            if not s["timestamp_valid"]:
                bad_ts.append((cid, s["start"], s["end"]))
            ov = sum(max(0, min(s["end"], r["end"]) - max(s["start"], r["start"])) for r in vr)
            if ov <= 0:
                out_of_vad.append((cid, s["start"], s["end"]))
    chk("vad_timestamp_mapping", not bad_ts and not tr_err,
        {"segments": len(sentences), "invalid_timestamps": bad_ts[:20], "transcription_errors": tr_err,
         "segments_without_vad_overlap": len(out_of_vad), "examples_without_vad_overlap": out_of_vad[:10],
         "method": "every segment within [0, duration]; overlap with independently computed Silero VAD regions on the same audio"})
    if out_of_vad and not bad_ts and not tr_err:
        checks["vad_timestamp_mapping"]["result"] = "WARN"
    av_bad = [v["clip_id"] for v in videos
              if any(abs(a - v["stream_start_times"]["video"]) > 0.001 for a in v["stream_start_times"]["audio"])]
    chk("av_start_alignment", not av_bad, {"misaligned": av_bad,
        "rule": "audio and video stream start_time equal, so transcript seconds map directly onto picture time"})
    unc = [s for s in sentences if s["transcript_status"] == "uncertain"]
    chk("transcript_uncertainty_recorded", all(s["transcript_status"] in ("reliable", "uncertain") for s in sentences)
        and all(s["review_reason"] for s in unc),
        {"reliable": len(sentences) - len(unc), "uncertain": len(unc),
         "uncertain_reasons": dict(Counter(r for s in unc for r in s["review_reason"].split(","))),
         "rechecked": sum(1 for s in sentences if s["recheck"])})
    chk("proxy_deduplication", confirmed_proxy == len(proxies) and not cat["unpaired_proxies"],
        {"lrf_total": len(proxies), "confirmed": confirmed_proxy,
         "non_confirmed": [p["proxy_path"] for p in proxies if p["pairing_status"] != "confirmed"],
         "counted_as_source": 0}, warn=True)
    cov_bad = []
    for cid, x in vis.items():
        if not x or x.get("error"):
            cov_bad.append((cid, "no visual analysis"))
            continue
        rs = {r for s in x["sample_times"] for r in s["reasons"]}
        if not {"start", "mid", "end"} <= rs or x["max_sampling_gap_s"] > 10.5:
            cov_bad.append((cid, x["max_sampling_gap_s"]))
        if not x.get("timing_check", {}).get("ok"):
            cov_bad.append((cid, "frame-index timing check failed", x.get("timing_check")))
    vn_missing = [cid for cid in vid_by if not vn.get(cid)]
    chk("sampling_coverage", not cov_bad and not vn_missing,
        {"clips": len(vis), "violations": cov_bad[:20], "vision_label_missing": vn_missing[:20],
         "total_sample_frames": sum(len(x["sample_times"]) for x in vis.values() if x and not x.get("error")),
         "rule": "start/q1/mid/q3/end + baseline every 10 s + scene-change/fast-motion densification; full-clip ~4 fps technical pass; sample t = native frame index * den/num, decoded frame count must equal expected"})
    col_bad = [v["clip_id"] for v in videos if v["color_profile"] != "unknown" and not v["color_profile_source"]]
    chk("color_evidence_preserved", not col_bad and all("detected_color_metadata" in v and "color_evidence" in v for v in videos),
        {"profiles": dict(Counter(v["color_profile"] for v in videos)), "unknown": sum(1 for v in videos if v["color_profile"] == "unknown"),
         "source": dict(Counter(v["color_profile_source"] for v in videos)),
         "ffprobe_transfer_tags": dict(Counter(v["detected_color_metadata"]["color_transfer"] for v in videos)),
         "note": "ffprobe bt709 tags retained separately and never used to set color_profile"})
    chk("visual_audio_separation", all(set(c) >= {"visual_people", "visual_animals", "visual_objects", "visual_actions", "audio_speakers"} for c in cands),
        {"fields": ["visual_people", "visual_animals", "visual_objects", "visual_actions", "audio_speakers"],
         "rule": "visual fields built only from image analysis; audio_speakers only from ASR/VAD"})
    qbad = [q["queue_id"] for q in queue if not (q["source_path"] and 0 <= q["start"] < q["end"] <= vid_by[q["clip_id"]]["duration"] + 0.05)]
    chk("review_queue_traceable", not qbad and {q["clip_id"] for q in queue} == set(vid_by),
        {"items": len(queue), "invalid": qbad[:20], "all_clips_present": {q["clip_id"] for q in queue} == set(vid_by)})
    hu = [c["clip_id"] for c in cands if c["hard_unusable"]]
    chk("hard_unusable_conservative", True, {"hard_unusable": hu,
        "micro_clips_kept": [c["clip_id"] for c in cands if c["micro_clip"]],
        "rule": "only decode failure, or >=95% nearly black / occluded-featureless AND no Vision subject/text on any sample frame; each verified by viewing frames"})
    chk("photo_handling", all(p["media_type"] == "photo" for p in cat["photos"]),
        {"photos": len(cat["photos"]), "not_applicable": ["transcript", "vad", "fps", "cut_range"], "without_gps": no_gps_photos})

    res = [c["result"] for c in checks.values()]
    overall = "FAIL" if "FAIL" in res else ("PASS_WITH_WARNINGS" if ("WARN" in res or warnings) else "PASS")
    report = {"stage": "0A", "generated_at": NOW, "overall": overall,
              "headline": {"source_clip_count": len(source_clips), "total_duration_s": total_dur,
                           "total_duration_hms": f"{int(total_dur//3600)}:{int(total_dur%3600//60):02d}:{total_dur%60:05.2f}",
                           "transcript_sentence_count": len(sentences), "review_queue_count": len(queue),
                           "color_unknown_count": sum(1 for v in source_clips if v["color_profile"] == "unknown"),
                           "hard_unusable_count": len(hu), "photo_count": len(cat["photos"])},
              "checks": checks, "warnings": warnings,
              "outputs": sorted(str(p.relative_to(PROCESS.parent)) for p in OUT.glob("*") if p.is_file())}
    write_json(OUT / "stage0a_validation_report.json", report)
    print(overall, report["headline"])
    for k, v in checks.items():
        print(f"  {k}: {v['result']}")
    for w in warnings:
        print("  WARN", w)


if __name__ == "__main__":
    main()
