#!/usr/bin/env python3
"""Stage 0A step 3: VAD-gated faster-whisper transcription with uncertainty
flags, local re-recognition of uncertain segments, VAD-only sound activity
events, and simple audio level inspection.

Per-clip cache: temp/stage0a/transcripts/<clip_id>.json
Timestamps are original-media seconds (faster-whisper restores VAD-removed gaps;
we additionally verify every timestamp against the source duration).
"""
from __future__ import annotations

import difflib
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
import faster_whisper
from faster_whisper import WhisperModel, decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps

from common import PROCESS, TEMP, cache_key, read_json, write_json

MODEL_NAME = "small"   # locally cached Systran/faster-whisper-small; larger models not downloaded (not authorized)
COMPUTE = "int8"
SR = 16000
VAD = {"threshold": 0.35, "min_speech_duration_ms": 120, "min_silence_duration_ms": 600, "speech_pad_ms": 400}
DECODE = {"beam_size": 5, "temperature": [0.0, 0.2, 0.4], "condition_on_previous_text": False,
          "word_timestamps": True, "multilingual": True, "language": None}
PARAMS = {"model": MODEL_NAME, "compute": COMPUTE, "vad": VAD, "decode": {k: v for k, v in DECODE.items()},
          "fw": faster_whisper.__version__, "rev": 2}

HALLUCINATION = re.compile(r"(字幕|订阅|訂閱|点赞|點贊|謝謝觀看|谢谢观看|Amara|优优独播|明鏡|請不吝|by\s+\w+\s*$|ご視聴)", re.I)
CJK = re.compile(r"[぀-ヿ㐀-鿿]")


def norm(t: str) -> str:
    return re.sub(r"[\s\W_]+", "", t.lower())


def flags_for(seg, words, prev_text):
    f = []
    dur = max(seg.end - seg.start, 0.01)
    txt = seg.text.strip()
    if seg.avg_logprob < -1.0:
        f.append("low_avg_logprob")
    if seg.no_speech_prob > 0.6:
        f.append("possible_non_speech")
    if seg.compression_ratio > 2.4:
        f.append("repetitive_text")
    chars = len(norm(txt))
    if chars / dur > (9 if CJK.search(txt) else 22):
        f.append("implausible_speech_rate")
    if words:
        mp = float(np.mean([w.probability for w in words]))
        if mp < 0.5:
            f.append("low_word_probability")
    if prev_text and norm(prev_text) and norm(prev_text) == norm(txt):
        f.append("repeated_text")
    if HALLUCINATION.search(txt):
        f.append("known_asr_hallucination_pattern")
    if not chars:
        f.append("empty_text")
    return f


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def audio_levels(a: np.ndarray):
    if a.size == 0:
        return None
    win = SR // 2
    n = a.size // win
    rms = np.sqrt(np.mean(a[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12) if n else np.array([np.sqrt(np.mean(a ** 2))])
    db = 20 * np.log10(rms + 1e-12)
    return {"method": "16kHz mono downmix of ASR track, 0.5s windows (inspection only, not loudness-standard)",
            "rms_dbfs_median": round(float(np.median(db)), 1),
            "rms_dbfs_p95": round(float(np.percentile(db, 95)), 1),
            "peak_dbfs": round(float(20 * np.log10(np.max(np.abs(a)) + 1e-12)), 1),
            "clipping_ratio": round(float(np.mean(np.abs(a) >= 0.999)), 5),
            "near_silent_window_ratio": round(float(np.mean(db < -55)), 3)}


def transcribe_clip(model, v):
    src = PROCESS.parent / v["source_path"]
    dur = v["duration"]
    audio = decode_audio(str(src), sampling_rate=SR)  # first audio stream (= catalog asr_track)
    res = {"clip_id": v["clip_id"], "source_path": v["source_path"], "duration": dur,
           "asr_track_index": v["audio"]["asr_track"], "params": PARAMS}
    res["audio_levels"] = audio_levels(audio)

    # VAD regions on the raw audio (for provenance + non-speech sound activity)
    opts = VadOptions(**VAD)
    speech = [{"start": round(s["start"] / SR, 3), "end": round(s["end"] / SR, 3)}
              for s in get_speech_timestamps(audio, opts, sampling_rate=SR)]
    res["vad_regions"] = speech
    res["vad_speech_seconds"] = round(sum(s["end"] - s["start"] for s in speech), 2)
    if not speech:
        res.update(language=None, language_probability=None, segments=[], sound_events=[])
        return res

    segs, info = model.transcribe(audio, vad_filter=True, vad_parameters=VAD, **DECODE)
    segs = list(segs)
    res["language"] = info.language
    res["language_probability"] = round(float(info.language_probability), 3)
    out, prev = [], None
    for i, s in enumerate(segs):
        words = list(s.words or [])
        fl = flags_for(s, words, prev)
        seg_lang = getattr(s, "language", None) or info.language
        if seg_lang not in ("zh", None):
            fl.append(f"non_zh_language:{seg_lang}")
        out.append({
            "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
            "language": seg_lang,
            "confidence": round(math.exp(s.avg_logprob), 3),
            "confidence_definition": "exp(avg_logprob) from faster-whisper; uncalibrated, not a probability of correctness",
            "avg_logprob": round(s.avg_logprob, 3), "no_speech_prob": round(s.no_speech_prob, 3),
            "compression_ratio": round(s.compression_ratio, 3),
            "mean_word_probability": round(float(np.mean([w.probability for w in words])), 3) if words else None,
            "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word,
                       "probability": round(w.probability, 3)} for w in words],
            "flags": fl,
        })
        prev = s.text

    # Local re-recognition of flagged segments (slice from the same original audio).
    for seg in out:
        if not seg["flags"] or "empty_text" in seg["flags"]:
            continue
        a0, a1 = max(0.0, seg["start"] - 0.5), min(dur, seg["end"] + 0.5)
        clip = audio[int(a0 * SR): int(a1 * SR)]
        lang = seg["language"] if seg["language"] else None
        rs, _ = model.transcribe(clip, vad_filter=False, beam_size=8, temperature=0.0,
                                 condition_on_previous_text=False, language=lang)
        rs = list(rs)
        rtext = "".join(r.text for r in rs).strip()
        ratio = difflib.SequenceMatcher(None, norm(seg["text"]), norm(rtext)).ratio() if rtext else 0.0
        rlp = float(np.mean([r.avg_logprob for r in rs])) if rs else None
        seg["recheck"] = {"method": "re-decode slice ±0.5s, no VAD, beam 8, temp 0, same language",
                          "text": rtext, "similarity": round(ratio, 3),
                          "avg_logprob": round(rlp, 3) if rlp is not None else None}
        soft = {"low_avg_logprob", "low_word_probability"}
        if ratio >= 0.85 and rlp is not None and rlp > -0.8 and set(seg["flags"]) <= soft:
            seg["recheck"]["resolved_flags"] = list(seg["flags"])
            seg["flags"] = []

    for seg in out:
        seg["transcript_status"] = "uncertain" if seg["flags"] else "reliable"
        seg["review_reason"] = ",".join(seg["flags"]) if seg["flags"] else None
        seg["timestamp_valid"] = bool(0 <= seg["start"] < seg["end"] <= dur + 0.05)

    # VAD sound activity without any transcript text -> non-speech/unclassified events
    events = []
    for r in speech:
        cov = sum(overlap(r["start"], r["end"], s["start"], s["end"]) for s in out)
        if cov < 0.2 * (r["end"] - r["start"]):
            events.append({"start": r["start"], "end": r["end"], "type": "vad_activity_without_transcript",
                           "note": "Possible laughter, child vocalization, ambience or unintelligible speech; not transcribed, needs listening"})
    res["segments"] = out
    res["sound_events"] = events
    return res


def main():
    cat = read_json(TEMP / "catalog.json")
    vids = [v for v in cat["videos"] if not v["duplicate_of"]]
    if len(sys.argv) > 1:
        vids = [v for v in vids if v["clip_id"] in sys.argv[1:]]
    outdir = TEMP / "transcripts"
    outdir.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE, cpu_threads=6)
    t0 = time.time()
    done_s = 0.0
    total_s = sum(v["duration"] for v in vids)
    for i, v in enumerate(vids):
        key = cache_key(PROCESS.parent / v["source_path"], PARAMS)
        op = outdir / f"{v['clip_id']}.json"
        old = read_json(op)
        if old and old.get("cache_key") == key:
            done_s += v["duration"]
            continue
        try:
            r = transcribe_clip(model, v)
            r["cache_key"] = key
        except Exception as e:  # recorded, not hidden
            r = {"clip_id": v["clip_id"], "source_path": v["source_path"], "error": repr(e), "cache_key": None}
        write_json(op, r)
        done_s += v["duration"]
        el = time.time() - t0
        print(f"[{i+1}/{len(vids)}] {v['clip_id']} {v['duration']:.0f}s segs={len(r.get('segments', []))} "
              f"lang={r.get('language')} elapsed={el/60:.1f}m progress={done_s/total_s:.1%}", flush=True)


if __name__ == "__main__":
    main()
