"""Create source-relative beat data; never modifies the input audio."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    args = parser.parse_args()
    source = args.audio.resolve()
    info = sf.info(source)
    sample_rate, hop = 22050, 512
    samples, sr = librosa.load(source, sr=sample_rate, mono=True)
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError("Audio must contain finite, nonempty samples")
    duration = len(samples) / sr
    envelope = librosa.onset.onset_strength(y=samples, sr=sr, hop_length=hop)
    tempo, frames = librosa.beat.beat_track(
        onset_envelope=envelope, sr=sr, hop_length=hop, trim=True
    )
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    beats = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
    beats = beats[(beats >= 0) & (beats < duration)]
    intervals = np.diff(beats)
    window = 2 * sr
    energy = np.array([
        float(np.sqrt(np.mean(samples[i:i + window].astype(np.float64) ** 2)))
        for i in range(0, len(samples), window)
    ])
    energy_db = 20 * np.log10(np.maximum(energy, 1e-12))
    low, high = np.quantile(energy_db, [1 / 3, 2 / 3])
    sections = []
    for i, db in enumerate(energy_db):
        label = "low" if db < low else "high" if db > high else "medium"
        start, end = float(i * 2), min(float((i + 1) * 2), duration)
        if sections and sections[-1]["energy"] == label:
            sections[-1]["end"] = round(end, 6)
        else:
            sections.append({"start": start, "end": round(end, 6), "energy": label})
    data = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"file": source.name,
                   "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "size_bytes": source.stat().st_size,
                   "sample_rate_hz": info.samplerate, "channels": info.channels,
                   "duration_seconds": info.frames / info.samplerate},
        "analysis": {"script": Path(__file__).name,
                     "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "versions": {name: version(name) for name in ("librosa", "numpy", "soundfile")},
                     "sample_rate_hz": sample_rate, "mono": True, "hop_length": hop,
                     "beat_method": "librosa onset_strength + beat_track; trim=True; remaining parameters use library defaults",
                     "energy_method": "2-second nonoverlapping RMS windows; track-relative dB tertiles",
                     "energy_thresholds_dbfs": {"low": float(low), "high": float(high)}},
        "bpm_estimate": bpm,
        "beats_seconds": [round(float(t), 6) for t in beats],
        "beat_count": len(beats),
        "interval_statistics_seconds": {
            "median": float(np.median(intervals)) if len(intervals) else None,
            "minimum": float(np.min(intervals)) if len(intervals) else None,
            "maximum": float(np.max(intervals)) if len(intervals) else None},
        "energy_sections": sections,
        "time_reference": "seconds from start of original BGM file",
        "timeline_mapping": "timeline_start + (source_beat - music_source_start) / playback_speed; only beats within selected source range",
        "review_status": "AUTOMATIC_UNREVIEWED",
        "limitations": ["Beat estimates may have half/double-tempo or alignment errors; audition before adopting cuts.",
                        "No downbeat, meter, chorus, emotion or semantic section detection.",
                        "Energy labels are relative RMS levels, not integrated LUFS.",
                        "Quantized to analysis hop size; six decimal places do not imply microsecond accuracy.",
                        "Dialogue, action and reaction completeness take priority over beat alignment."]}
    output = source.with_suffix(".beats.json")
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "bpm": bpm, "beats": len(beats), "duration": duration}))


if __name__ == "__main__":
    main()
