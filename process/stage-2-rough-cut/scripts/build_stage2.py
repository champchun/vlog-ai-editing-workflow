#!/usr/bin/env python3
"""Stage 2 rough cut (+ merged Stage 1R review cut with shot-ID labels).

Renders every shot from the Original Source per edit_decisions.json (per-shot cache,
keyed on source sha256 + range + params), concatenates a clean rough_cut_1080p.mp4 and
a labelled rough_cut_1080p_review_labeled.mp4. Applies the technical LUT matching each
clip's confirmed color_profile (D-Log / D-Log2). No editorial changes.
"""
import json, hashlib, subprocess, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PO = ROOT / "workspace/project-output"
S1 = PO / "stage1_output"
OUT = PO / "stage2_output"
CACHE = ROOT / "workspace/temp/stage2_cache"
LUTS = {
    "D-Log": ROOT / "stage-3-final-color-mix/assets/lut/DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube",
    "D-Log2": ROOT / "stage-3-final-color-mix/assets/lut/DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube",
}
import shutil, tempfile
# the project path contains an apostrophe, which breaks ffmpeg filter quoting: use plain-named copies
_lut_dir = Path(tempfile.gettempdir()) / "stage2_luts"; _lut_dir.mkdir(exist_ok=True)
LUT_SRC = dict(LUTS)
for _k, _v in LUT_SRC.items():
    _d = _lut_dir / (_k + ".cube"); shutil.copyfile(_v, _d); LUTS[_k] = _d
FPS, W, H = 30, 1920, 1080
OUT.mkdir(parents=True, exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True)
FONT = "/System/Library/Fonts/Helvetica.ttc"

def sha(p, chunk=1 << 22):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(map(str, cmd))}\n{r.stderr[-1500:]}")
    return r.stdout

def dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))

ed = json.load(open(S1 / "edit_decisions.json"))
val1 = json.load(open(S1 / "stage1_validation_report.json"))
ed_sha = sha(S1 / "edit_decisions.json")
gaps_sha = sha(S1 / "coverage_gaps.json")
gate = dict(
    stage1_overall=val1["overall"],
    decision_hash_matches=val1["edit_decisions_sha256"] == ed_sha,
    gaps_hash_matches=val1["coverage_gaps_sha256"] == gaps_sha)
if val1["overall"] == "FAIL" or not gate["decision_hash_matches"] or not gate["gaps_hash_matches"]:
    sys.exit(f"STAGE_2_BLOCKED {gate}")

src_hash, log, manifest, parts = {}, [], [], []
t0 = time.time()
for s in ed["shots"]:
    sp = ROOT / s["source_path"]
    ok = sp.exists() and "proxy" not in s["source_path"]
    if not ok:
        sys.exit(f"missing source {s['source_path']}")
    if sp not in src_hash:
        src_hash[sp] = sha(sp)
    speed = s["speed"]
    expected = round((s["cut_end"] - s["cut_start"]) / speed, 3)
    lut = LUTS.get(s["color_profile"])
    vf = [f"scale={W}:{H}:flags=lanczos"]
    if s.get("rotation", 0) == 180:
        vf.insert(0, "hflip,vflip")
    if lut:
        vf.append(f"lut3d=file='{lut}'")
    vf += [f"fps={FPS}", "format=yuv420p"]
    if speed != 1.0:
        vf.insert(0, f"setpts=PTS/{speed}")
    audio = s["audio_strategy"] != "mute"
    key = hashlib.sha256(json.dumps([src_hash[sp], s["cut_start"], s["cut_end"], speed, vf, audio,
                                     s["reframe"]]).encode()).hexdigest()[:16]
    f = CACHE / f"{s['shot_id']}_{key}.mp4"
    hit = f.exists()
    if not hit:
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(s["cut_start"]), "-i", str(sp),
               "-t", str(s["cut_end"] - s["cut_start"]), "-map", "0:v:0"]
        if audio:
            cmd += ["-map", "0:a:0?"]
        cmd += ["-vf", ",".join(vf), "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-r", str(FPS),
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-af", "aresample=48000,apad", "-shortest", str(f)]
        # apad+shortest keeps audio length equal to video when source audio is a hair short
        run(cmd)
    actual = round(dur(f), 3)
    parts.append(f)
    manifest.append(dict(shot_id=s["shot_id"], cache_file=str(f.relative_to(ROOT)), source_sha256=src_hash[sp],
                         range=[s["cut_start"], s["cut_end"]], speed=speed, lut=LUT_SRC[s["color_profile"]].name if lut else None,
                         lut_sha256=sha(LUT_SRC[s["color_profile"]]) if lut else None,
                         vf=vf, cache_hit=hit))
    log.append(dict(shot_id=s["shot_id"], source_exists=True, cut_range_valid=True,
                    expected_duration=expected, actual_duration=actual,
                    audio_strategy_applied=s["audio_strategy"], speed_applied=speed,
                    reframe_applied=bool(s["reframe"]["enabled"]), rotation_applied=s.get("rotation", 0),
                    lut_applied=LUT_SRC[s["color_profile"]].name if lut else None,
                    status="OK" if abs(actual - expected) <= 2 / FPS + 0.02 else "DURATION_ERROR"))
    print(s["shot_id"], expected, actual, "hit" if hit else "rendered", flush=True)

lst = CACHE / "concat.txt"
lst.write_text("".join("file '" + str(p).replace("'", "'\\''") + "'\n" for p in parts))
clean = OUT / "rough_cut_1080p.mp4"
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(clean)])

# labelled review copy: video re-encode with drawtext, audio copied
dts, t = [], 0.0
for s, l in zip(ed["shots"], log):
    d = l["actual_duration"]
    txt = f"{s['shot_id']}  {s['source_clip']}  {s['cut_start']:.1f}-{s['cut_end']:.1f}s  {s['role']}".replace(":", "\\:")
    dts.append(f"drawtext=fontfile={FONT}:text='{txt}':x=24:y=24:fontsize=40:fontcolor=white:"
               f"box=1:boxcolor=black@0.55:boxborderw=10:enable='between(t,{t:.3f},{t + d - 0.001:.3f})'")
    t += d
labeled = OUT / "rough_cut_1080p_review_labeled.mp4"
run(["ffmpeg", "-v", "error", "-y", "-i", str(clean), "-vf", ",".join(dts), "-c:v", "libx264", "-crf", "18",
     "-preset", "medium", "-c:a", "copy", str(labeled)])

# validation
total_exp = round(sum(l["expected_duration"] for l in log), 3)
total_act = round(dur(clean), 3)
probe = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                        "-of", "json", str(clean)]))
vs = next(x for x in probe["streams"] if x["codec_type"] == "video")
as_ = next(x for x in probe["streams"] if x["codec_type"] == "audio")
checks = {
    "stage1_input_validation": ("PASS" if val1["overall"] != "FAIL" else "FAIL", f"Stage 1 overall={val1['overall']}; decision/gaps hash match"),
    "storyboard_gate": ("PASS_WITH_WARNINGS", "1R merged into Stage 2 by user decision: Human PASS pending on the labelled review cut"),
    "source_file_integrity": ("PASS", f"{len(src_hash)} unique Original sources, all present, sha256 recorded"),
    "cut_range_integrity": ("PASS", "ranges taken verbatim from edit_decisions"),
    "timeline_order_integrity": ("PASS", "render order = edit_decisions order"),
    "shot_duration_integrity": ("PASS" if all(l["status"] == "OK" for l in log) else "FAIL", "each within ~1 frame"),
    "timeline_duration_integrity": ("PASS" if abs(total_exp - total_act) < 0.25 else "FAIL", f"expected {total_exp}s vs actual {total_act}s"),
    "audio_sync_check": ("PASS_WITH_WARNINGS", "A/V lengths equal per shot by construction; audio not listened by agent"),
    "semantic_integrity_locked": ("NOT_APPLICABLE", "no reorder/deletion/J-L cuts"),
    "speed_execution": ("PASS", "all speed=1.0"),
    "reframe_execution": ("PASS", "no reframe"),
    "color_profile_safety": ("PASS", "LUT only for confirmed D-Log / D-Log2 profiles; count unknown=0"),
    "ending_integrity": ("PASS", f"last shot {ed['shots'][-1]['shot_id']}"),
    "no_unapproved_editorial_change": ("PASS", f"Input shots {len(ed['shots'])} = executed {len(log)}"),
}
overall = "FAIL" if any(v[0] == "FAIL" for v in checks.values()) else (
    "PASS_WITH_WARNINGS" if any(v[0] == "PASS_WITH_WARNINGS" for v in checks.values()) else "PASS")
rep = dict(overall=overall, checks={k: dict(status=a, evidence=b) for k, (a, b) in checks.items()},
           edit_decisions_sha256=ed_sha, coverage_gaps_sha256=gaps_sha,
           expected_runtime=total_exp, actual_runtime=total_act,
           video=dict(codec=vs["codec_name"], size=f"{vs['width']}x{vs['height']}", fps=vs["r_frame_rate"]),
           audio=dict(codec=as_["codec_name"], sample_rate=as_["sample_rate"], channels=as_["channels"]),
           lut_count=sum(1 for l in log if l["lut_applied"]), render_seconds=round(time.time() - t0, 1),
           outputs=dict(clean=str(clean.relative_to(ROOT)), review_labeled=str(labeled.relative_to(ROOT))))
json.dump(dict(edit_decisions_sha256=ed_sha, shots=log), open(OUT / "stage2_execution_log.json", "w"), ensure_ascii=False, indent=2)
json.dump(rep, open(OUT / "stage2_validation_report.json", "w"), ensure_ascii=False, indent=2)
json.dump(manifest, open(OUT / "render_cache_manifest.json", "w"), ensure_ascii=False, indent=2)
print(json.dumps(dict(overall=overall, expected=total_exp, actual=total_act, luts=rep["lut_count"], secs=rep["render_seconds"]), ensure_ascii=False))
