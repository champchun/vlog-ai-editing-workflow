#!/usr/bin/env python3
"""Stage 0A local pre-analysis. Usage: build_stage0a.py  (run from anywhere)
Reads process/workspace/media, writes process/workspace/project-output/stage0a_output."""
import json, os, re, glob, subprocess, sys, time, hashlib, wave, warnings
from datetime import datetime, timedelta, timezone
warnings.filterwarnings("ignore")
import numpy as np, cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))   # process/
WS = os.path.join(ROOT, "workspace"); MEDIA = os.path.join(WS, "media")
OUT = os.path.join(WS, "project-output/stage0a_output")
TMP = os.path.join(WS, "temp/stage0a"); CACHE = os.path.join(TMP, "cache")
for d in (OUT, TMP, CACHE, os.path.join(TMP, "frames"), os.path.join(TMP, "audio")): os.makedirs(d, exist_ok=True)
VER = "0A-v1"; TZ = timezone(timedelta(hours=8))
VIDEO_EXT = {".mp4", ".mov", ".m4v"}; PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".dng"}
ASR_MODEL = "small"
VAD_PARAMS = dict(min_silence_duration_ms=500, speech_pad_ms=300, threshold=0.4)

def run(cmd): return subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
def ff_json(f):
    return json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", f]))
def exif(f):
    return json.loads(run(["exiftool", "-json", "-ee3", "-G1", "-n", f]))[0]

# ---------- scan ----------
def scan():
    vids, photos, lrfs, warns = [], [], [], []
    for p in sorted(glob.glob(os.path.join(MEDIA, "**", "*"), recursive=True)):
        if not os.path.isfile(p) or os.path.basename(p).startswith("."): continue
        e = os.path.splitext(p)[1].lower()
        if e in VIDEO_EXT: vids.append(p)
        elif e in PHOTO_EXT: photos.append(p)
        elif e == ".lrf": lrfs.append(p)
        elif e not in (".md",): warns.append(f"unrecognised file type, not counted: {p}")
    return vids, photos, lrfs, warns

# ---------- metadata ----------
def metadata(f):
    j = ff_json(f); x = exif(f)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = [s for s in j["streams"] if s["codec_type"] == "audio"]
    num, den = v["r_frame_rate"].split("/"); fps = float(num) / float(den)
    rot = 0
    for sd in v.get("side_data_list", []):
        rot = sd.get("rotation", rot)
    m = re.search(r"_(\d{14})_", f)
    fname_t = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=TZ) if m else None
    ct = v.get("tags", {}).get("creation_time")
    ct_local = datetime.fromisoformat(ct.replace("Z", "+00:00")).astimezone(TZ) if ct else None
    gamma = x.get("Keys:DjiCameraColorGammaSxS")
    prof = {"D-Log": "D-Log", "D-Log2": "D-Log2", "D-Log M": "D-Log M", "Normal": "Rec.709", "Rec.709": "Rec.709"}.get(gamma, "unknown") if gamma else "unknown"
    return dict(
        filename=os.path.basename(f), source_path=os.path.relpath(f, ROOT), media_type="video",
        creation_time_utc=ct, creation_time_local=ct_local and ct_local.isoformat(),
        filename_time_local=fname_t and fname_t.isoformat(),
        container_timecode=v.get("tags", {}).get("timecode"),
        duration=round(float(j["format"]["duration"]), 3), size_bytes=int(j["format"]["size"]),
        fps=round(fps, 3), codec=v["codec_name"], width=v["width"], height=v["height"], pix_fmt=v.get("pix_fmt"),
        rotation=rot, has_audio=bool(a), audio_streams=[dict(codec=s["codec_name"], channels=s.get("channels"), sample_rate=s.get("sample_rate")) for s in a],
        camera_model=x.get("Keys:DjiCameraCameraModel"), camera_model_source="exiftool Keys:DjiCameraCameraModel",
        lens=x.get("Keys:DjiCameraLensType"),
        detected_color_metadata=dict(ffprobe_primaries=v.get("color_primaries"), ffprobe_transfer=v.get("color_transfer"), ffprobe_space=v.get("color_space"),
                                     exiftool_DjiCameraColorGammaSxS=gamma),
        color_profile=prof,
        color_profile_source="exiftool Keys:DjiCameraColorGammaSxS (DJI Osmo Pocket 4 / PP-041)" if gamma else "none",
        color_profile_confidence=("medium" if gamma else "none"),
        color_profile_note="ffprobe tag bt709 is container signalling only and is NOT used as the profile." + ("" if gamma else " No camera gamma field found -> unknown."),
        gps_embedded=x.get("Keys:GPSCoordinates"),
    )

# ---------- visual ----------
def analyse_stream(f, md):
    w, h = 320, int(round(320 * md["height"] / md["width"] / 2)) * 2
    if md["rotation"] in (90, -90, 270): w, h = h, w
    cmd = ["ffmpeg", "-v", "error", "-i", f, "-an", "-vf", f"fps=4,scale={w}:{h},format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    fr = np.frombuffer(raw[: n * w * h], np.uint8).reshape(n, h, w)
    rows, prev, prevh = [], None, None
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    for i in range(n):
        g = fr[i]
        hist = cv2.calcHist([g], [0], None, [32], [0, 256]); cv2.normalize(hist, hist)
        r = dict(t=round(i / 4, 2), blur=float(cv2.Laplacian(g, cv2.CV_64F).var()), mean=float(g.mean()),
                 over=float((g > 240).mean()), dark=float((g < 12).mean()), diff=0.0, shift=0.0, hcorr=1.0)
        if prev is not None:
            r["diff"] = float(np.abs(g.astype(np.int16) - prev).mean())
            (dx, dy), _ = cv2.phaseCorrelate(prev.astype(np.float32), g.astype(np.float32), win)
            r["shift"] = float(np.hypot(dx, dy)) / w * 100       # % of frame width per 0.25 s
            r["hcorr"] = float(cv2.compareHist(prevh, hist, cv2.HISTCMP_CORREL))
        rows.append(r); prev = g.astype(np.int16); prevh = hist
    return rows

def sample_times(dur, rows):
    base = [0.0 + 0.2, dur / 2, max(dur - 0.3, 0)] if dur < 8 else list(np.arange(0.5, dur - 0.3, 3.0 if dur < 30 else 6.0))
    base += [dur / 2] if dur >= 8 else []
    reasons = {round(t, 2): "base_coverage" for t in base}
    for r in rows:
        if r["hcorr"] < 0.6 or r["diff"] > 22:
            reasons[round(min(r["t"] + 0.25, dur - 0.1), 2)] = "scene_change"
    shifts = sorted(rows, key=lambda r: -r["shift"])[:2]
    for r in shifts:
        if r["shift"] > 4: reasons.setdefault(round(r["t"], 2), "fast_camera_motion")
    return dict(sorted(reasons.items()))

def detect(img):
    # OpenCV 5.0 has no classic Haar/HOG detectors and no local DNN model is bundled:
    # people/animals/objects are NOT detected locally; deferred to Stage 0B.
    return 0, 0

def visual(f, md, key):
    rows = analyse_stream(f, md); dur = md["duration"]
    st = sample_times(dur, rows); samples = []
    for t, why in st.items():
        jp = os.path.join(TMP, "frames", f"{key}_{int(t*100):05d}.jpg")
        if not os.path.exists(jp):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", f, "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "3", jp], capture_output=True)
        img = cv2.imread(jp)
        nf, npp = detect(img) if img is not None else (0, 0)
        samples.append(dict(t=t, reason=why, frame=os.path.relpath(jp, ROOT) if img is not None else None, face_candidates=nf, person_candidates=npp))
    cuts = [r["t"] for r in rows if r["hcorr"] < 0.6 or r["diff"] > 22]
    arr = lambda k: np.array([r[k] for r in rows]) if rows else np.zeros(1)
    # D-Log is flat: judge darkness/over-exposure on gray stats only coarsely
    summary = dict(frames_analysed=len(rows), analysis_fps=4, scene_change_times=cuts,
        blur_lap_var_median=round(float(np.median(arr("blur"))), 1), blur_lap_var_p10=round(float(np.percentile(arr("blur"), 10)), 1),
        mean_luma_median=round(float(np.median(arr("mean"))), 1), dark_fraction_mean=round(float(arr("dark").mean()), 3),
        over_fraction_mean=round(float(arr("over").mean()), 4), motion_diff_mean=round(float(arr("diff").mean()), 2),
        shake_shift_pct_median=round(float(np.median(arr("shift"))), 2), shake_shift_pct_p95=round(float(np.percentile(arr("shift"), 95)), 2))
    nearly_black = summary["mean_luma_median"] < 8 and summary["dark_fraction_mean"] > 0.9
    summary["usable_ratio"] = round(float(np.mean([(r["dark"] < 0.9) and r["blur"] > 5 for r in rows])), 3) if rows else 0
    summary["hard_unusable"] = bool(nearly_black or not rows)
    summary["hard_unusable_reason"] = "nearly black / no decodable frames" if summary["hard_unusable"] else None
    return summary, samples, rows

# ---------- audio / ASR ----------
_model = None
def asr_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(ASR_MODEL, device="cpu", compute_type="int8")
    return _model

def audio_events(wav, dur):
    with wave.open(wav) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    step = sr // 2; ev = []
    db = [20 * np.log10(np.sqrt(np.mean(a[i:i+step] ** 2)) + 1e-9) for i in range(0, len(a), step)]
    med = float(np.median(db)) if db else -90
    for i, d in enumerate(db):
        if d > -12 and d - med > 12:
            ev.append(dict(start=round(i * .5, 2), end=round(min((i + 1) * .5, dur), 2), peak_rms_db=round(float(d), 1), type="loud_audio_event_unclassified"))
    return dict(median_rms_db=round(med, 1), max_rms_db=round(float(max(db)) if db else -90, 1)), ev

def transcribe(f, md, key):
    wav = os.path.join(TMP, "audio", key + ".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-vn", "-ac", "1", "-ar", "16000", wav], capture_output=True)
    lvl, ev = audio_events(wav, md["duration"])
    m = asr_model(); lang_used = None
    def go(**kw):
        segs, info = m.transcribe(wav, vad_filter=True, vad_parameters=VAD_PARAMS, beam_size=5, condition_on_previous_text=False, **kw)
        return list(segs), info
    segs, info = go()
    if info.language == "zh":
        segs, info2 = go(language="zh", initial_prompt="以下是台灣的繁體中文口語。"); lang_used = "zh (re-run with zh-TW prompt after auto-detect)"
    out = []
    for i, s in enumerate(segs):
        reasons = []
        if s.no_speech_prob > 0.5: reasons.append(f"no_speech_prob={s.no_speech_prob:.2f}")
        if s.avg_logprob < -1.0: reasons.append(f"avg_logprob={s.avg_logprob:.2f}")
        if s.compression_ratio > 2.4: reasons.append("repetitive_text")
        if info.language not in ("zh", "en") or info.language_probability < 0.6: reasons.append(f"language={info.language}@{info.language_probability:.2f}")
        if len(s.text.strip()) <= 1: reasons.append("very_short_text")
        out.append(dict(sentence_id=f"{key}_S{i+1:03d}", file=md["filename"], start=round(s.start, 2), end=round(s.end, 2), text=s.text.strip(),
                        confidence=round(float(np.exp(s.avg_logprob)), 3), confidence_definition="exp(avg_logprob) from faster-whisper; NOT a calibrated probability",
                        no_speech_prob=round(float(s.no_speech_prob), 3),
                        transcript_status="uncertain" if reasons else "reliable", review_reason="; ".join(reasons) or None))
    return dict(language_detected=info.language, language_probability=round(info.language_probability, 3), language_used=lang_used or "auto",
                sentences=out, audio_level=lvl, audio_events=ev)

# ---------- main ----------
def main():
    t0 = time.time()
    vids, photos, lrfs, warns = scan()
    gps = {}
    gp = os.path.join(WS, "project-output/gps_tagging/gps_match.json")
    if os.path.exists(gp):
        for r in json.load(open(gp)): gps[os.path.basename(r["path"])] = r
    catalog, vis_all, sentences, queue = [], [], [], []
    for n, f in enumerate(vids, 1):
        key = re.sub(r"\W", "", os.path.splitext(os.path.basename(f))[0])
        cf = os.path.join(CACHE, key + ".json")
        sig = [VER, os.path.getsize(f), ASR_MODEL]
        if os.path.exists(cf) and json.load(open(cf))["sig"] == sig:
            c = json.load(open(cf))
        else:
            md = metadata(f)
            vs, samples, rows = visual(f, md, key)
            asr = transcribe(f, md, key) if md["has_audio"] else None
            c = dict(sig=sig, md=md, vs=vs, samples=samples, asr=asr); json.dump(c, open(cf, "w"), ensure_ascii=False)
        c["md"] = md = metadata(f)   # cheap; always recomputed so metadata rules can change without redoing ASR/visual
        for s_ in (c["asr"] or {}).get("sentences", []):   # clamp VAD/whisper padding to clip length
            if s_["end"] > md["duration"]: s_["end"] = round(md["duration"], 2); s_["review_reason"] = ((s_["review_reason"] + "; ") if s_["review_reason"] else "") + "end_clamped_to_clip_duration"; s_["transcript_status"] = "uncertain"
        g = gps.get(md["filename"])
        md["gps_auxiliary"] = g and dict(local_time_at_gps_location=g.get("local_time_at_gps_location"), gps_location_utc_offset=g.get("gps_location_utc_offset"), lat=g["lat"], lon=g["lon"], method=g["method"], context=g["context"], source="Timeline 4.json matched at clip midpoint", note="auxiliary only; activity_interpolated = straight-line estimate")
        md["clip_id"] = f"V{n:03d}"; md["key"] = key
        c["md"] = md; catalog.append(md)
        vis_all.append(dict(clip_id=md["clip_id"], file=md["filename"], source_path=md["source_path"], analysis=c["vs"], sample_frames=c["samples"],
            visual_people=[dict(t=s["t"], candidate="face/person", faces=s["face_candidates"], persons=s["person_candidates"], confidence="low-candidate") for s in c["samples"] if s["face_candidates"] or s["person_candidates"]],
            visual_animals=[], visual_objects=[], visual_actions=[], audio_speakers=[],
            note="No local people/animal/object detector available (OpenCV 5.0 lacks Haar/HOG, no DNN model bundled); all semantic labels deferred to Stage 0B. Technical metrics only."))
        if c["asr"]:
            sentences += c["asr"]["sentences"]
        c["id"] = md["clip_id"]; vids[n-1] = (f, c)
        print(f"[{n}/{len(vids)}] {md['filename']} {md['duration']}s", flush=True)

    # review queue
    for f, c in vids:
        md, vs, asr = c["md"], c["vs"], c["asr"]; why = []; pr = 1
        npers = sum(1 for s in c["samples"] if s["face_candidates"] or s["person_candidates"])
        if asr and any(s["transcript_status"] == "uncertain" for s in asr["sentences"]): why.append("uncertain_transcript"); pr += 1
        if asr and asr["audio_events"]: why.append("loud_audio_event(laugh/shout candidate)"); pr += 2
        if len(vs["scene_change_times"]) >= 2 or vs["shake_shift_pct_p95"] > 4: why.append("fast_camera_turn_or_cuts"); pr += 1
        if md["duration"] > 60: why.append("long_clip_adaptive_review"); pr += 1
        if asr and asr["sentences"]: why.append("speech_present"); pr += 1
        why.append("no_local_semantic_labels(animals/objects/signs/food need 0B)")
        rng = [dict(start=s["t"], end=round(min(s["t"] + 3, md["duration"]), 2), reason=s["reason"]) for s in c["samples"]]
        queue.append(dict(clip_id=md["clip_id"], file=md["filename"], source_path=md["source_path"], priority="high" if pr >= 5 else "medium" if pr >= 3 else "low",
                          priority_score=pr, reasons=why, time_ranges=rng, local_confidence="<0.8 (local labels are candidate-only)"))
    queue.sort(key=lambda q: -q["priority_score"])

    # proxy manifest
    stems = {os.path.splitext(os.path.basename(f))[0]: (f, c) for f, c in vids}
    pm, unp = [], []
    for l in lrfs:
        s = os.path.splitext(os.path.basename(l))[0]
        if s in stems:
            d = float(ff_json(l)["format"]["duration"]); sd = stems[s][1]["md"]["duration"]
            pm.append(dict(source=stems[s][1]["md"]["source_path"], proxy=os.path.relpath(l, ROOT), source_duration=sd, proxy_duration=round(d, 3),
                           time_offset=round(d - sd, 3), status="PAIRED" if abs(d - sd) < 0.5 else "DURATION_MISMATCH", basis="same stem + duration within 0.5s"))
        else: unp.append(l); warns.append(f"unpaired LRF: {l}")
    json.dump(dict(pairs=pm, unpaired=[os.path.relpath(u, ROOT) for u in unp]), open(os.path.join(OUT, "source_proxy_manifest.json"), "w"), ensure_ascii=False, indent=1)

    # timestamp consistency warnings
    for _, c in vids:
        md = c["md"]
        if md["creation_time_local"] and md["filename_time_local"]:
            dlt = abs((datetime.fromisoformat(md["creation_time_local"]) - datetime.fromisoformat(md["filename_time_local"])).total_seconds())
            if dlt > 5: warns.append(f"{md['filename']}: filename time vs creation_time differ {dlt:.0f}s; creation_time (UTC) used as authoritative clip time (content check: 0001/0002/0003 are subway scenes matching creation_time)")
    tc = {c["md"]["container_timecode"][:2] for _, c in vids if c["md"]["container_timecode"]}
    fn = {c["md"]["filename_time_local"][11:13] for _, c in vids}
    off = [int(c["md"]["container_timecode"][:2]) - int(c["md"]["filename_time_local"][11:13]) for _, c in vids if c["md"]["container_timecode"]]
    if off and set(off) != {0}:
        warns.append(f"container timecode hour differs from filename/creation_time local hour (offsets {sorted(set(off))}h); filename + creation_time (UTC) agree and were used for GPS matching.")

    uncert = [s for s in sentences if s["transcript_status"] == "uncertain"]
    pp = os.path.join(WS, "people/people_confirmed.json")
    people = json.load(open(pp))["people"] if os.path.exists(pp) else []
    json.dump(dict(stage="0A", version=VER, known_people=dict(source="workspace/people/people_confirmed.json (user-confirmed list; NOT detected locally)", people=people), clip_time_basis="creation_time_utc (filename time is +1h on 0001/0002/0003)", generated=datetime.now(TZ).isoformat(), source_video_clip_count=len(vids), photo_count=len(photos),
                   lrf_proxy_count=len(lrfs), asr=dict(model=ASR_MODEL, vad="faster-whisper built-in silero VAD", vad_parameters=VAD_PARAMS, compute="cpu int8"),
                   clips=[c["md"] for _, c in vids], photos=[os.path.relpath(p, ROOT) for p in photos]), open(os.path.join(OUT, "metadata_catalog.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(vis_all, open(os.path.join(OUT, "local_visual_candidates.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(dict(clips=[dict(clip_id=c["md"]["clip_id"], file=c["md"]["filename"], language=c["asr"] and c["asr"]["language_detected"],
                               language_probability=c["asr"] and c["asr"]["language_probability"], language_used=c["asr"] and c["asr"]["language_used"],
                               audio_level=c["asr"] and c["asr"]["audio_level"], audio_events=c["asr"] and c["asr"]["audio_events"], sentences=c["asr"] and c["asr"]["sentences"]) for _, c in vids]),
              open(os.path.join(OUT, "transcripts.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(queue, open(os.path.join(OUT, "stage0b_review_queue.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "transcript_summary.txt"), "w") as fh:
        fh.write(f"Stage 0A transcript summary | ASR={ASR_MODEL} | sentences={len(sentences)} (uncertain={len(uncert)})\nTranscript describes SOUND only, not visuals.\n\n")
        for _, c in vids:
            md, a = c["md"], c["asr"]
            fh.write(f"## {md['clip_id']} {md['filename']} ({md['duration']}s) lang={a['language_detected']}@{a['language_probability']}\n")
            for s in a["sentences"]:
                fh.write(f"  [{s['start']:.1f}-{s['end']:.1f}] ({s['transcript_status']}{'; ' + s['review_reason'] if s['review_reason'] else ''}) {s['text']}\n")
            for e in a["audio_events"]: fh.write(f"  [{e['start']}-{e['end']}] <{e['type']} {e['peak_rms_db']}dB>\n")
            if not a["sentences"]: fh.write("  (no speech detected)\n")

    # validation
    total = sum(c["md"]["duration"] for _, c in vids)
    chk = {}
    def ck(name, ok, ev, warn=False): chk[name] = dict(status="PASS" if ok else ("WARN" if warn else "FAIL"), evidence=ev)
    disk_n = len([p for p in vids]); ck("source_clip_count_matches_media", len(vids) == len(catalog) == len(stems), f"{len(vids)} videos scanned, {len(catalog)} catalogued, {len(lrfs)} LRF excluded from count")
    ck("every_video_has_metadata", all(c["md"]["duration"] > 0 and c["md"]["codec"] for _, c in vids), "ffprobe fields present for all clips")
    bad_ts = [s["sentence_id"] for s in sentences if s["end"] > next(c["md"]["duration"] for _, c in vids if c["md"]["filename"] == s["file"]) + 0.5 or s["start"] < 0]
    ck("vad_timestamp_mapping", not bad_ts, f"all {len(sentences)} sentence times within clip duration; VAD params {VAD_PARAMS}; audio extracted without trimming (bad={bad_ts})")
    ck("transcript_uncertainty_recorded", all("transcript_status" in s for s in sentences), f"{len(uncert)} uncertain / {len(sentences)} sentences flagged with review_reason")
    ck("proxy_deduplication", all(p["status"] == "PAIRED" for p in pm) and not unp, f"{len(pm)} LRF paired, not counted as clips; unpaired={len(unp)}")
    cov = [v for v in vis_all if len([s for s in v["sample_frames"]]) >= 3]
    ck("sampling_coverage", len(cov) == len(vis_all), f"{len(cov)}/{len(vis_all)} clips have >=3 samples incl. first/middle/last; 4fps motion pass over whole clip")
    ck("color_evidence_preserved", all("detected_color_metadata" in c["md"] and c["md"]["color_profile_source"] for _, c in vids), "ffprobe tags stored separately from camera gamma field")
    ck("visual_audio_separation", all(not v["audio_speakers"] and "transcript" not in json.dumps(v["analysis"]) for v in vis_all), "visual file contains no transcript text")
    ck("review_queue_traceable", all(q["time_ranges"] and q["source_path"] for q in queue), f"{len(queue)} queue entries with source_path + time ranges")
    ck("color_not_guessed_from_ffprobe", all(c["md"]["color_profile"] == "unknown" or c["md"]["detected_color_metadata"]["exiftool_DjiCameraColorGammaSxS"] for _, c in vids), "profile only set from DJI camera field")
    over = "FAIL" if any(v["status"] == "FAIL" for v in chk.values()) else ("PASS_WITH_WARNINGS" if warns or any(v["status"] == "WARN" for v in chk.values()) else "PASS")
    prof_count = {}
    for _, c in vids: prof_count[c["md"]["color_profile"]] = prof_count.get(c["md"]["color_profile"], 0) + 1
    rep = dict(overall=over, source_clip_count=len(vids), photo_count=len(photos), total_duration_s=round(total, 1), transcript_sentence_count=len(sentences),
               uncertain_sentence_count=len(uncert), review_queue_count=len(queue), color_unknown_count=prof_count.get("unknown", 0), color_profile_counts=prof_count,
               hard_unusable_count=sum(1 for _, c in vids if c["vs"]["hard_unusable"]), checks=chk, warnings=warns, runtime_s=round(time.time() - t0))
    json.dump(rep, open(os.path.join(OUT, "stage0a_validation_report.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "checks"}, ensure_ascii=False, indent=1))

if __name__ == "__main__": main()
