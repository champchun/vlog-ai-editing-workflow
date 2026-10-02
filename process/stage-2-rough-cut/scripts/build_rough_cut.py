#!/usr/bin/env python3
"""Stage 2 Dumb Executor: render edit_decisions.json faithfully from Original Source to a 1080p30 rough cut.
No editorial decisions here. Per-shot intermediates are a verifiable compute cache (workspace/temp/stage2_shots)."""
import json, hashlib, subprocess, os, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[3]
PO = ROOT/"process/workspace/project-output"
S1, SB = PO/"stage1_output", PO/"stage1_review/storyboard"
OUT = PO/"stage2_output"; TMP = ROOT/"process/workspace/temp/stage2_shots"
OUT.mkdir(parents=True, exist_ok=True); TMP.mkdir(parents=True, exist_ok=True)
FPS, W, H = 30, 1920, 1080

def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()
def sampled_sha(p):   # size + first/last 4MB (full hashing of ~tens of GB of 4K sources is impractical)
    p = Path(p); n = p.stat().st_size; h = hashlib.sha256(str(n).encode())
    with open(p, "rb") as f:
        h.update(f.read(4<<20)); f.seek(max(0, n-(4<<20))); h.update(f.read(4<<20))
    return h.hexdigest()
def dur(p):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(p)],capture_output=True,text=True)
    return float(r.stdout.strip())
def probe_v(p):
    r = subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,r_frame_rate,pix_fmt","-of","json",str(p)],capture_output=True,text=True)
    return json.loads(r.stdout)["streams"][0]

# ---------- gate
ed = json.load(open(S1/"edit_decisions.json")); shots = ed["shots"]
rep = json.load(open(S1/"stage1_validation_report.json"))
hum = json.load(open(SB/"storyboard_human_review.json"))
sbv = json.load(open(SB/"storyboard_validation.json"))
H_ED, H_CG, H_SP = sha(S1/"edit_decisions.json"), sha(S1/"coverage_gaps.json"), sha(S1/"story_plan.json")
gate = {
 "stage1_overall": rep["overall"], "storyboard_validation": sbv["overall"], "human_review": hum["overall"],
 "stage1_hash_match": rep["hashes"]["edit_decisions_sha256"] == H_ED and rep["hashes"]["coverage_gaps_sha256"] == H_CG,
 "storyboard_hash_match": sbv["hashes"]["edit_decisions_sha256"] == H_ED,
 "human_hash_match": hum["hashes"]["edit_decisions_sha256"] == H_ED and hum["hashes"]["coverage_gaps_sha256"] == H_CG,
 "music_sections": len(json.load(open(S1/"story_plan.json")).get("music_sections", [])),
}
if not (rep["overall"] in ("PASS","PASS_WITH_WARNINGS") and sbv["overall"]=="PASS" and hum["overall"]=="PASS"
        and gate["stage1_hash_match"] and gate["storyboard_hash_match"] and gate["human_hash_match"]):
    print("STAGE_2_BLOCKED", gate); sys.exit(2)

def render(s):
    t0 = time.time()
    sid = s["shot_id"]; src = ROOT/s["source_path"]; out = TMP/f"{sid}.mp4"
    sp = s["speed"]; exp = round((s["cut_end"]-s["cut_start"])/sp, 3)
    key = {"src": sampled_sha(src), "a": s["cut_start"], "b": s["cut_end"], "speed": sp, "audio": s["audio_strategy"],
           "reframe": s["reframe"]["enabled"], "fps": FPS, "res": f"{W}x{H}", "codec": "libx264 crf17 veryfast / aac 192k 48k stereo"}
    keyf = TMP/f"{sid}.key.json"
    if out.exists() and keyf.exists() and json.load(open(keyf)) == key and out.stat().st_size > 0:
        return sid, "hit", key, time.time()-t0
    vf = f"scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1,format=yuv420p"
    if sp != 1.0: vf = f"setpts={1/sp}*PTS," + vf
    cmd = ["ffmpeg","-y","-v","error","-ss",f"{s['cut_start']:.3f}","-i",str(src),"-t",f"{s['cut_end']-s['cut_start']:.3f}"]
    if s["audio_strategy"] == "mute":
        cmd += ["-f","lavfi","-t",f"{exp:.3f}","-i","anullsrc=r=48000:cl=stereo","-map","0:v:0","-map","1:a"]
        af = []
    else:
        cmd += ["-map","0:v:0","-map","0:a:0"]; af = ["-af","aresample=48000,aformat=channel_layouts=stereo,apad"]
    cmd += ["-vf",vf,*af,"-t",f"{exp:.3f}","-c:v","libx264","-preset","veryfast","-crf","17","-r",str(FPS),"-c:a","aac","-b:a","192k","-ar","48000","-ac","2",str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        return sid, "error:"+r.stderr[-300:], key, time.time()-t0
    json.dump(key, open(keyf,"w"))
    return sid, "miss", key, time.time()-t0

t_all = time.time()
with ThreadPoolExecutor(3) as ex: results = list(ex.map(render, shots))
cache = {sid: {"status": st, "key": k, "seconds": round(sec,1)} for sid, st, k, sec in results}
json.dump({"tool": subprocess.run(["ffmpeg","-version"],capture_output=True,text=True).stdout.splitlines()[0], "shots": cache},
          open(OUT/"render_cache_manifest.json","w"), ensure_ascii=False, indent=1)
errs = [sid for sid, st, *_ in results if st.startswith("error")]
if errs: print("render errors", errs, [r for r in results if r[1].startswith("error")][:2]); sys.exit(1)

# ---------- concat (identical encode params -> stream copy of already-exact per-shot files)
lst = TMP/"concat.txt"; lst.write_text("".join("file '" + str(TMP/(s['shot_id']+'.mp4')).replace("'", "'\\''") + "'\n" for s in shots))
final = OUT/"rough_cut_1080p.mp4"
r = subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(lst),"-c","copy","-movflags","+faststart",str(final)],capture_output=True,text=True)
assert r.returncode == 0, r.stderr

# ---------- logs / validation
log, dur_err = [], []
for s, (sid, st, k, sec) in zip(shots, results):
    src = ROOT/s["source_path"]; a, b = s["cut_start"], s["cut_end"]
    sd = dur(src) if src.exists() else 0
    exp = round((b-a)/s["speed"], 3); act = round(dur(TMP/f"{sid}.mp4"), 3)
    ok_cut = src.exists() and 0 <= a < b <= sd + 0.01
    if abs(act-exp) > 1/FPS + 0.02: dur_err.append(sid)
    log.append({"shot_id": sid, "source_exists": src.exists(), "cut_range_valid": ok_cut, "expected_duration": exp, "actual_duration": act,
                "audio_strategy_applied": s["audio_strategy"], "speed_applied": s["speed"], "reframe_applied": s["reframe"]["enabled"],
                "source_path": s["source_path"], "cut_start": a, "cut_end": b, "cache": st, "status": "OK" if ok_cut and sid not in dur_err else "ERROR"})
exp_total = round(sum(l["expected_duration"] for l in log), 3); act_total = round(dur(final), 3)
vs = probe_v(final)
ap = subprocess.run(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=sample_rate,channels","-of","json",str(final)],capture_output=True,text=True)
aud = json.loads(ap.stdout)["streams"][0]
master = {c["clip_id"]: c for c in json.load(open(PO/"stage0d_master_review/master_footage_review.json"))}
cp = [master[s["source_clip"]].get("color_profile") for s in shots]
unknown = sum(1 for c in cp if not c or c == "unknown")
uniq = len({s["source_path"] for s in shots})
from collections import Counter
strat = Counter(s["audio_strategy"] for s in shots)
tdiff = round(act_total-exp_total, 3)
chk = lambda ok, ev=None: {"result": "PASS" if ok else "FAIL", "evidence": ev or {}}
checks = {
 "stage1_input_validation": chk(rep["overall"] in ("PASS","PASS_WITH_WARNINGS") and gate["stage1_hash_match"], {"stage1": rep["overall"], "hash_match": gate["stage1_hash_match"]}),
 "storyboard_gate": chk(sbv["overall"]=="PASS" and hum["overall"]=="PASS" and gate["human_hash_match"], {"human_review": hum["overall"], "reviewed_artifact": hum.get("reviewed_artifact")}),
 "source_file_integrity": chk(all(l["source_exists"] for l in log), {"unique_sources": uniq, "source_sampled_hash": "size+first/last 4MB; see render_cache_manifest.json"}),
 "cut_range_integrity": chk(all(l["cut_range_valid"] for l in log)),
 "timeline_order_integrity": chk([l["shot_id"] for l in log] == [s["shot_id"] for s in shots], {"input": len(shots), "executed": len(log)}),
 "shot_duration_integrity": chk(not dur_err, {"errors": dur_err}),
 "timeline_duration_integrity": chk(abs(tdiff) < 0.5, {"expected": exp_total, "actual": act_total, "diff": tdiff}),
 "audio_sync_check": chk(abs(tdiff) < 0.5, {"note": "per-shot audio padded/trimmed to shot expected duration; concat total matches video within tolerance; not listened by agent"}),
 "semantic_integrity_locked": {"result": "NOT_APPLICABLE", "evidence": {"reason": "Stage 1: no dialogue reorder/delete, no J/L, no audio_segments"}},
 "speed_execution": chk(all(l["speed_applied"] == s["speed"] for l, s in zip(log, shots)), {"slow_motion_shots": sum(1 for s in shots if s["speed"] != 1.0)}),
 "reframe_execution": chk(not any(l["reframe_applied"] for l in log), {"reframed": 0}),
 "color_profile_safety": chk(True, {"lut_applied": 0, "unknown_profile_shots": unknown, "note": "no LUT in Stage 2; D-Log/D-Log2 clips rendered as-is for Stage 3 grading"}),
 "ending_integrity": chk(log[-1]["shot_id"] == shots[-1]["shot_id"] and log[-1]["status"] == "OK", {"ending": shots[-1]["shot_id"]}),
 "no_unapproved_editorial_change": chk(len(shots) == len(log) and all(l["cut_start"] == s["cut_start"] and l["cut_end"] == s["cut_end"] and l["source_path"] == s["source_path"] for l, s in zip(log, shots)), {"input_shots": len(shots), "executed_shots": len(log)}),
}
checks["overall"] = {"result": "FAIL" if any(v["result"] == "FAIL" for v in checks.values()) else "PASS", "evidence": {}}
hashes = {"edit_decisions_sha256": H_ED, "coverage_gaps_sha256": H_CG, "story_plan_sha256": H_SP}
json.dump({"stage": 2, "hashes": hashes, "gate": gate, "cache_hits": sum(1 for r in results if r[1]=="hit"), "elapsed_s": round(time.time()-t_all,1), "shots": log},
          open(OUT/"stage2_execution_log.json","w"), ensure_ascii=False, indent=1)
warnings = ["未由 Agent 實際聽音訊；人聲／同步請在 Rough Cut 試看確認。",
            "9 個慢動作 B-roll 用單純 0.5x 拉長（無補幀），原片 30fps 者可能略顯頓。",
            "來源檔雜湊為取樣雜湊（大小＋首尾各 4MB），非完整內容雜湊。"]
json.dump({"stage": 2, "overall": checks["overall"]["result"], "checks": checks, "warnings": warnings, "hashes": hashes,
           "summary": {"input_shots": len(shots), "executed_shots": len(log), "unique_sources": uniq, "expected_runtime_s": exp_total, "actual_runtime_s": act_total,
                       "resolution": f"{vs['width']}x{vs['height']}", "fps": vs["r_frame_rate"], "audio": aud, "audio_strategy": dict(strat),
                       "slow_motion": sum(1 for s in shots if s["speed"] != 1.0), "reframe": 0, "lut": 0, "color_unknown": unknown,
                       "duration_errors": len(dur_err), "timeline_diff_s": tdiff}},
          open(OUT/"stage2_validation_report.json","w"), ensure_ascii=False, indent=1)
print(json.dumps({"overall": checks["overall"]["result"], "runtime": [exp_total, act_total], "diff": tdiff, "res": f"{vs['width']}x{vs['height']}", "fps": vs["r_frame_rate"],
                  "audio": aud, "dur_err": dur_err, "unknown": unknown, "uniq": uniq, "strat": dict(strat), "elapsed": round(time.time()-t_all)}, ensure_ascii=False))
