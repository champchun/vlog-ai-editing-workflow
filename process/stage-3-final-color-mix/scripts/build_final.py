#!/usr/bin/env python3
"""Stage 3 finishing: rebuild approved timeline from Original Source with technical LUT (per verified camera profile),
conservative shot matching, audio cleanup, BGM with speech-driven ducking, location cards, final QC.
No editorial change: shot order / cut points / speed come straight from edit_decisions.json."""
import json, hashlib, subprocess, sys, time, re, statistics, shutil, os
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PRJ = ROOT/"process"; PO = PRJ/"workspace/project-output"
S1, S2, SB = PO/"stage1_output", PO/"stage2_output", PO/"stage1_review/storyboard"
A3 = PRJ/"stage-3-final-color-mix/assets"
OUT = PO/"stage3_output"; TMP = PRJ/"workspace/temp/stage3"
for p in (OUT, TMP/"v", TMP/"a", TMP/"meas"): p.mkdir(parents=True, exist_ok=True)
FPS, W, H, SR = 30, 1920, 1080, 48000
LUT_DIR = A3/"lut"
LUTS = {"D-Log": "DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube",
        "D-Log2": "DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube"}
BGM = A3/"bgm/2026-09-13_06_01_09.wav"; BEATS = A3/"bgm/2026-09-13_06_01_09.beats.json"
FONT_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_JP = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sampled_sha(p):
    p = Path(p); n = p.stat().st_size; h = hashlib.sha256(str(n).encode())
    with open(p, "rb") as f:
        h.update(f.read(4 << 20)); f.seek(max(0, n-(4 << 20))); h.update(f.read(4 << 20))
    return h.hexdigest()
def run(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, **kw)
def dur(p): return float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(p)]).stdout.strip())

# ============ gate ============
ed = json.load(open(S1/"edit_decisions.json")); shots = ed["shots"]
rep1 = json.load(open(S1/"stage1_validation_report.json")); rep2 = json.load(open(S2/"stage2_validation_report.json"))
log2 = json.load(open(S2/"stage2_execution_log.json")); hum = json.load(open(SB/"storyboard_human_review.json"))
H_ED = sha(S1/"edit_decisions.json"); H_CG = sha(S1/"coverage_gaps.json"); H_SP = sha(S1/"story_plan.json")
plan = json.load(open(S1/"story_plan.json"))
gate = {"stage1": rep1["overall"], "stage2": rep2["overall"], "storyboard_human": hum["overall"],
        "stage1_hash": rep1["hashes"]["edit_decisions_sha256"] == H_ED, "stage2_hash": rep2["hashes"]["edit_decisions_sha256"] == H_ED,
        "stage2_log_hash": log2["hashes"]["edit_decisions_sha256"] == H_ED, "human_hash": hum["hashes"]["edit_decisions_sha256"] == H_ED}
assets = {"default_bgm": BGM.exists(), "d_log2_lut": (LUT_DIR/LUTS["D-Log2"]).exists(), "d_log_lut": (LUT_DIR/LUTS["D-Log"]).exists()}
log("assets", assets, "gate", gate)
if not (rep1["overall"] in ("PASS","PASS_WITH_WARNINGS") and rep2["overall"] in ("PASS","PASS_WITH_WARNINGS") and hum["overall"]=="PASS" and all(v for k,v in gate.items() if "hash" in k)):
    print("STAGE_3_BLOCKED", gate); sys.exit(2)
beats = json.load(open(BEATS)); bgm_sha = sha(BGM)
assert beats["source"]["sha256"] == bgm_sha, "BGM sha mismatch vs beats.json"
if plan.get("music_sections"): print("music_sections present - not supported by this script"); sys.exit(3)

master = {c["clip_id"]: c for c in json.load(open(PO/"stage0d_master_review/master_footage_review.json"))}
meta = {v["clip_id"]: v for v in json.load(open(PO/"stage0a_output/metadata_catalog.json"))["videos"]}
events = {e["event_id"]: e for e in json.load(open(PO/"stage0c_output/event_candidates.json"))["events"]}
sentences = defaultdict(dict)
for s in json.load(open(PO/"stage0a_output/transcript_sentences.json"))["sentences"]: sentences[s["clip_id"]][s["sentence_id"]] = s

# ---- timeline + profile evidence
tl, t = [], 0.0
for s in shots:
    exp = round((s["cut_end"]-s["cut_start"])/s["speed"], 3)
    m = meta[s["source_clip"]]
    prof, src_, conf = m.get("color_profile"), m.get("color_profile_source"), m.get("color_profile_confidence")
    reliable = prof in LUTS and conf == "high" and str(src_).startswith("camera_metadata")
    tl.append({"s": s, "exp": exp, "t0": round(t, 3), "t1": round(t+exp, 3), "profile": prof, "profile_source": src_, "profile_conf": conf,
               "lut": LUTS[prof] if reliable else None})
    t += exp
TOTAL = round(t, 3)
log("timeline", len(tl), "shots", TOTAL, "s; LUT:", Counter(x["profile"] for x in tl if x["lut"]), "no-LUT:", sum(1 for x in tl if not x["lut"]))

# ============ pass 1: measure LUT'd luma/chroma ============
def measure(x):
    s = x["s"]; sid = s["shot_id"]; f = TMP/"meas"/f"{sid}.v2.json"
    if f.exists(): return sid, json.load(open(f))
    vf = "fps=2,scale=640:-2:flags=bilinear"
    if x["lut"]: vf += f",lut3d=file='{x['lut']}'"
    vf += ",signalstats,metadata=print:file=-"
    r = run(["ffmpeg","-v","error","-ss",f"{s['cut_start']:.3f}","-t",f"{s['cut_end']-s['cut_start']:.3f}","-i",str(ROOT/s["source_path"]),"-an","-vf",vf,"-f","null","-"], cwd=str(LUT_DIR))
    vals = defaultdict(list)
    for line in (r.stdout + r.stderr).splitlines():
        m_ = re.match(r"lavfi\.signalstats\.(\w+)=([\d.]+)", line)
        if m_: vals[m_.group(1)].append(float(m_.group(2)))
    # signalstats reports in the stream bit depth (10-bit sources -> 0..1023); normalise to 8-bit scale (SATAVG is unscaled)
    sc = 0.25
    res = {k: round(statistics.mean(vals[k])*(1 if k == "SATAVG" else sc), 2) for k in ("YAVG","YMIN","YMAX","UAVG","VAVG","SATAVG") if vals.get(k)}
    res["YHIGH"] = round(statistics.mean(vals["YHIGH"])*sc, 2) if vals.get("YHIGH") else None
    json.dump(res, open(f, "w")); return sid, res
t0 = time.time()
with ThreadPoolExecutor(4) as ex: meas = dict(ex.map(measure, tl))
log("measured", len(meas), f"{time.time()-t0:.0f}s")

# ============ shot matching (conservative) ============
by_sec = defaultdict(list)
for x in tl: by_sec[x["s"]["story_section"]].append(x)
adj = {}
for sec, xs in by_sec.items():
    cand = [x for x in xs if meas[x["s"]["shot_id"]]["YAVG"] >= 60 and x["s"]["provenance"].get("tone") != "blue"]
    if len(cand) < 2:
        ref = None
    else:
        ref = {k: statistics.median(meas[x["s"]["shot_id"]][k] for x in cand) for k in ("YAVG","UAVG","VAVG")}
    for x in xs:
        sid = x["s"]["shot_id"]; m = meas[sid]
        a = {"section": sec, "ref": ref, "measured": m, "brightness": 0.0, "rb_gain": 1.0, "bb_gain": 1.0, "saturation": 1.04, "notes": []}
        if ref is None or x["s"]["provenance"].get("tone") == "blue" or m["YAVG"] < 60:
            a["notes"].append("no exposure/WB matching: dark/aquarium or single-shot section — original atmosphere kept")
        else:
            dY = ref["YAVG"]-m["YAVG"]
            if abs(dY) > 10:
                a["brightness"] = round(max(-0.05, min(0.05, 0.5*dY/255)), 4); a["notes"].append(f"exposure matched halfway toward section median (dY={dY:.1f})")
            else: a["notes"].append("exposure within tolerance of section median")
            dU, dV = m["UAVG"]-ref["UAVG"], m["VAVG"]-ref["VAVG"]
            if max(abs(dU), abs(dV)) > 6 and x["s"]["provenance"].get("place") == by_sec[sec][0]["s"]["provenance"].get("place"):
                a["bb_gain"] = round(1-max(-0.03, min(0.03, 0.5*dU/128)), 4); a["rb_gain"] = round(1-max(-0.03, min(0.03, 0.5*dV/128)), 4)
                a["notes"].append(f"WB nudge toward section median (dU={dU:.1f}, dV={dV:.1f}), same place only")
            else: a["notes"].append("WB within tolerance or different place — no change")
        if m.get("YHIGH") and m["YHIGH"] > 250: a["notes"].append("highlights clipped in source (YHIGH>250) — logged, not recoverable")
        adj[sid] = a

# ============ location cards ============
cards = {}
prev_name = None
for x in tl:   # a card at EVERY place change (by user-confirmed place name), not only at section starts
    s = x["s"]; loc = events[s["event_id"]]["location"]
    name = loc.get("name") if loc.get("status") == "user_confirmed" else None
    if name and name != prev_name:
        d = meta[s["source_clip"]]["camera_local_time_from_filename"][:10].replace("-", ".")
        jp = any("ぁ" <= c <= "ヿ" for c in name)
        L = min(2.5, x["exp"]-0.5)
        cards[s["shot_id"]] = {"element_id": f"CARD_{s['shot_id']}", "section": s["story_section"], "type": "location_card", "shot_id": s["shot_id"], "text": name, "date": d,
            "font": FONT_JP if jp else FONT_CJK, "start": 0.4, "end": round(0.4+L, 2), "timeline_start": round(x["t0"]+0.4, 3), "timeline_end": round(x["t0"]+0.4+L, 3),
            "evidence": {"name_source": loc.get("name_source"), "place_id": loc.get("place_id"), "date_source": "camera_local_time_from_filename (Stage 0A)"}}
    if name: prev_name = name
log("cards", {k: v["text"] for k, v in cards.items()})

# ============ pass 2: render video shots from Original ============
def esc(sx): return sx.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
def vf_for(x):
    s = x["s"]; a = adj[s["shot_id"]]; parts = []
    if x["lut"]: parts.append(f"lut3d=file='{x['lut']}':interp=tetrahedral")
    parts.append(f"eq=brightness={a['brightness']}:saturation={a['saturation']}")
    if a["rb_gain"] != 1.0 or a["bb_gain"] != 1.0: parts.append(f"colorchannelmixer=rr={a['rb_gain']}:bb={a['bb_gain']}")
    if s["speed"] != 1.0: parts.append(f"setpts={1/s['speed']}*PTS")
    parts += [f"scale={W}:{H}:flags=lanczos", f"fps={FPS}", "setsar=1"]
    c = cards.get(s["shot_id"])
    if c:
        al = f"if(lt(t,{c['start']}),0,if(lt(t,{c['start']+0.5}),(t-{c['start']})/0.5,if(lt(t,{c['end']-0.5}),1,if(lt(t,{c['end']}),({c['end']}-t)/0.5,0))))"
        sh = "shadowcolor=black@0.7:shadowx=3:shadowy=3:borderw=2:bordercolor=black@0.75"
        parts.append(f"drawtext=fontfile='{esc(c['font'])}':text='{esc(c['text'])}':fontcolor=white:fontsize=58:x=90:y=h-210:alpha='{al}':{sh}")
        parts.append(f"drawtext=fontfile='{esc(FONT_CJK)}':text='{esc(c['date'])}':fontcolor=white@0.9:fontsize=32:x=94:y=h-140:alpha='{al}':{sh}")
    parts.append("format=yuv420p")
    return ",".join(parts)
def render_v(x):
    s = x["s"]; sid = s["shot_id"]; out = TMP/"v"/f"{sid}.mp4"; t0 = time.time()
    key = {"src": sampled_sha(ROOT/s["source_path"]), "a": s["cut_start"], "b": s["cut_end"], "speed": s["speed"],
           "lut": [LUTS[x["profile"]], sha(LUT_DIR/LUTS[x["profile"]])] if x["lut"] else None, "vf": vf_for(x), "fps": FPS, "res": [W, H], "enc": "x264 crf16 veryfast"}
    kf = TMP/"v"/f"{sid}.key.json"
    if out.exists() and out.stat().st_size and kf.exists() and json.load(open(kf)) == key: return sid, "hit", key, 0
    r = run(["ffmpeg","-y","-v","error","-ss",f"{s['cut_start']:.3f}","-i",str(ROOT/s["source_path"]),"-t",f"{s['cut_end']-s['cut_start']:.3f}","-an",
             "-map","0:v:0","-vf",vf_for(x),"-t",f"{x['exp']:.3f}","-c:v","libx264","-preset","veryfast","-crf","16","-r",str(FPS),str(out)], cwd=str(LUT_DIR))
    if r.returncode or not out.exists(): return sid, "error: "+r.stderr[-400:], key, 0
    json.dump(key, open(kf, "w")); return sid, "miss", key, time.time()-t0
t0 = time.time()
with ThreadPoolExecutor(3) as ex: vres = list(ex.map(render_v, tl))
errs = [r for r in vres if r[1].startswith("error")]
if errs: print("VIDEO RENDER ERRORS", errs[:2]); sys.exit(1)
log("video rendered", Counter(r[1] for r in vres), f"{time.time()-t0:.0f}s")

# ============ audio: per-shot cleanup + level matching ============
def lufs(path_or_args):
    r = run(path_or_args); m_ = re.findall(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", r.stderr)
    return float(m_[-1]) if m_ and m_[-1] != "-inf" else None
SPEECH_ROLES = {"dialogue"}
aud_log = {}
def render_a(x):
    s = x["s"]; sid = s["shot_id"]; out = TMP/"a"/f"{sid}.wav"
    n = int(round(x["exp"]*SR))
    if s["audio_strategy"] == "mute":
        r = run(["ffmpeg","-y","-v","error","-f","lavfi","-i",f"anullsrc=r={SR}:cl=stereo","-t",f"{x['exp']:.3f}","-c:a","pcm_f32le",str(out)])
        return sid, {"strategy": "mute", "gain_db": 0, "measured_lufs": None}
    src = ["-ss",f"{s['cut_start']:.3f}","-t",f"{s['cut_end']-s['cut_start']:.3f}","-i",str(ROOT/s["source_path"]),"-map","0:a:0"]
    L = lufs(["ffmpeg","-v","info","-nostats",*src,"-af","ebur128=framelog=quiet","-f","null","-"])
    target = -21.0 if (s["role"] in SPEECH_ROLES or s["role"] in ("reaction","payoff")) else -26.0
    g = 0.0 if L is None else max(-6.0, min(9.0, target-L))
    af = f"highpass=f=80,acompressor=threshold=-24dB:ratio=2:attack=20:release=250:makeup=1,volume={g:.2f}dB,aresample={SR},aformat=channel_layouts=stereo,apad,atrim=0:{x['exp']:.3f},afade=t=in:d=0.008,afade=t=out:st={max(0,x['exp']-0.008):.3f}:d=0.008"
    r = run(["ffmpeg","-y","-v","error",*src,"-af",af,"-c:a","pcm_f32le","-ar",str(SR),str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-300:])
    return sid, {"strategy": s["audio_strategy"], "gain_db": round(g, 2), "measured_lufs": L, "target_lufs": target, "chain": "highpass80 + gentle compressor 2:1 + level match + 8ms fades"}
with ThreadPoolExecutor(4) as ex: aud_log = dict(ex.map(render_a, tl))
lst = TMP/"a_concat.txt"; lst.write_text("".join("file '" + str(TMP/"a"/(x["s"]["shot_id"]+".wav")).replace("'", "'\\''") + "'\n" for x in tl))
voice = TMP/"voice.wav"
r = run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(voice)]); assert r.returncode == 0, r.stderr
log("voice track", dur(voice), "vs", TOTAL)

def read_pcm(path):
    r = subprocess.run(["ffmpeg","-v","error","-i",str(path),"-f","f32le","-ac","2","-ar",str(SR),"-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).copy()
V = read_pcm(voice); N = len(V)

# ============ BGM plan + ducking ============
GROUPS = [  # (name, sections, music source start sec) — same track, different source ranges; reviewed via beats.json energy (unreviewed by ear)
    ("M1 出發+透明船", ["出發", "透明船"], 0.0),
    ("M2 日常+海洋博+古宇利", ["日常", "海洋博", "古宇利"], 16.0),
    ("M3 Neo Park+海灘", ["Neo Park", "海灘"], 20.0),
    ("M4 兒童王國+尾聲", ["兒童王國", "尾聲"], 44.0)]
music_wav = read_pcm(BGM); MLEN = len(music_wav)/SR
env_t = np.arange(0, TOTAL+0.01, 0.01); gain_db = np.full(len(env_t), -80.0)
speech_wins = []   # timeline windows with speech
for x in tl:
    s = x["s"]
    for sid_ in s["source_sentence_ids"]:
        st = sentences[s["source_clip"]].get(sid_)
        if not st: continue
        a_ = max(st["start"], s["cut_start"]); b_ = min(st["end"], s["cut_end"])
        if b_ > a_: speech_wins.append((x["t0"]+(a_-s["cut_start"])/s["speed"], x["t0"]+(b_-s["cut_start"])/s["speed"], s["shot_id"]))
LAUGH_EVENTS = {"EV051", "EV052", "EV056"}   # HC001/HC022/HC045-related: laughs / shouts / animal sound kept clean
shot_level = {}
for x in tl:
    s = x["s"]
    if s["audio_strategy"] == "mute" or s.get("is_broll"): lv = 0.0
    elif s["event_id"] in LAUGH_EVENTS or s["role"] in ("reaction", "payoff"): lv = -26.0
    elif s["role"] in ("establishing", "ambient", "detail"): lv = -5.0
    else: lv = -9.0
    shot_level[s["shot_id"]] = lv
    m_ = (env_t >= x["t0"]) & (env_t < x["t1"]); gain_db[m_] = lv
for a_, b_, sid_ in speech_wins:   # duck under speech: -24 dB, hold 0.4s, then release
    m_ = (env_t >= a_-0.15) & (env_t < b_+0.4); gain_db[m_] = np.minimum(gain_db[m_], -24.0)
# smooth (attack ~0.15s / release ~0.6s) with asymmetric one-pole on the 100 Hz envelope
sm = gain_db.copy()
for i in range(1, len(sm)):
    coef = 0.15 if gain_db[i] < sm[i-1] else 0.6
    sm[i] = sm[i-1] + (gain_db[i]-sm[i-1])*(0.01/coef if coef > 0.01 else 1)
grp_env = np.full(len(env_t), -200.0); bgm = np.zeros((N, 2), np.float32)
sec_span = {sec: (xs[0]["t0"], xs[-1]["t1"]) for sec, xs in by_sec.items()}
bgm_sections = []
for name, secs, src0 in GROUPS:
    g0 = min(sec_span[s_][0] for s_ in secs); g1 = max(sec_span[s_][1] for s_ in secs)
    L = g1-g0; assert src0+L <= MLEN+0.01, (name, src0, L, MLEN)
    seg = music_wav[int(src0*SR): int((src0+L)*SR)]
    n0 = int(g0*SR); n1 = min(N, n0+len(seg)); seg = seg[:n1-n0]
    fi, fo = int(1.5*SR), int(2.0*SR); w = np.ones(len(seg), np.float32)
    w[:fi] = np.linspace(0, 1, fi); w[-fo:] = np.minimum(w[-fo:], np.linspace(1, 0, fo))
    bgm[n0:n1] += seg*w[:, None]
    ens = [e for e in beats["energy_sections"] if e["start"] < src0+L and e["end"] > src0]
    bgm_sections.append({"name": name, "sections": secs, "timeline_start": round(g0, 2), "timeline_end": round(g1, 2), "source_start": src0, "source_end": round(src0+L, 2),
                         "playback_speed": 1.0, "energy_profile_from_beats_json": Counter(e["energy"] for e in ens), "fade_in_s": 1.5, "fade_out_s": 2.0})
# natural ending: last 7 s fade of the whole bed
endfade = int(7.0*SR); bgm[-endfade:] *= np.linspace(1, 0, endfade)[:, None]
# reference music loudness: measure first group window and set ref -23 LUFS
tmpw = TMP/"bgm_probe.wav"; import wave
def write_wav(path, arr):
    pcm = np.clip(arr, -1, 1); pcm = (pcm*32767).astype("<i2")
    with wave.open(str(path), "wb") as w_: w_.setnchannels(2); w_.setsampwidth(2); w_.setframerate(SR); w_.writeframes(pcm.tobytes())
write_wav(tmpw, bgm)
Lb = lufs(["ffmpeg","-v","info","-nostats","-i",str(tmpw),"-af","ebur128=framelog=quiet","-f","null","-"]) or -20.0
ref_gain = 10**((-23.0-Lb)/20)
env_samples = np.interp(np.arange(N)/SR, env_t, sm)
bgm_final = bgm*ref_gain*(10**(env_samples/20))[:, None].astype(np.float32)
mix = V + bgm_final
mixwav = TMP/"mix_pre.wav"; write_wav(mixwav, mix)
Lm = lufs(["ffmpeg","-v","info","-nostats","-i",str(mixwav),"-af","ebur128=framelog=quiet","-f","null","-"])
trim_db = -16.0-Lm if Lm else 0.0
log("BGM raw LUFS", Lb, "mix LUFS", Lm, "trim", round(trim_db, 2))

# ============ mux final ============
vlst = TMP/"v_concat.txt"; vlst.write_text("".join("file '" + str(TMP/"v"/(x["s"]["shot_id"]+".mp4")).replace("'", "'\\''") + "'\n" for x in tl))
vcat = TMP/"video_cat.mp4"
r = run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(vlst),"-c","copy",str(vcat)]); assert r.returncode == 0, r.stderr
final = OUT/"final_vlog_1080p_master.mp4"
r = run(["ffmpeg","-y","-v","error","-i",str(vcat),"-i",str(mixwav),"-map","0:v","-map","1:a","-c:v","copy",
         "-af",f"volume={trim_db:.2f}dB,alimiter=limit=0.80:level=disabled","-c:a","aac","-b:a","256k","-ar",str(SR),"-ac","2","-t",f"{TOTAL:.3f}","-movflags","+faststart",str(final)])
assert r.returncode == 0, r.stderr
log("final written", final.stat().st_size//1e6, "MB")

# ============ Final QC measurements ============
fq = {}
fq["duration"] = round(dur(final), 3)
pv = json.loads(run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name,width,height,r_frame_rate,bit_rate,pix_fmt","-of","json",str(final)]).stdout)["streams"][0]
pa = json.loads(run(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=codec_name,sample_rate,channels,bit_rate","-of","json",str(final)]).stdout)["streams"][0]
fq["video"], fq["audio"] = pv, pa
fq["bitrate_total"] = int(float(run(["ffprobe","-v","error","-show_entries","format=bit_rate","-of","default=nw=1:nk=1",str(final)]).stdout.strip()))
dec = run(["ffmpeg","-v","error","-i",str(final),"-f","null","-"]); fq["decode_errors"] = len([l for l in dec.stderr.splitlines() if l.strip()])
bd = run(["ffmpeg","-v","info","-i",str(final),"-vf","blackdetect=d=0.3:pix_th=0.05","-an","-f","null","-"]); fq["black_segments"] = re.findall(r"black_start:([\d.]+).*?black_end:([\d.]+)", bd.stderr)
fz = run(["ffmpeg","-v","info","-i",str(final),"-vf","freezedetect=n=-60dB:d=2.5","-an","-f","null","-"]); fq["freeze_events"] = re.findall(r"freeze_start: ([\d.]+)", fz.stderr)
eb = run(["ffmpeg","-v","info","-nostats","-i",str(final),"-af","ebur128=peak=true:framelog=quiet","-f","null","-"]).stderr
fq["integrated_lufs"] = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", eb)[-1]); fq["true_peak_dbtp"] = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", eb)[-1]) if re.findall(r"Peak:\s+(-?[\d.]+) dBFS", eb) else None
fq["lra"] = float(re.findall(r"LRA:\s+([\d.]+) LU", eb)[-1])
# post-render luma / chroma per shot (3 frames) + adjacent color-jump within section
post = {}
for x in tl:
    s = x["s"]; sid = s["shot_id"]
    r = run(["ffmpeg","-v","error","-i",str(TMP/"v"/f"{sid}.mp4"),"-vf","fps=1,scale=480:-2,signalstats,metadata=print:file=-","-an","-f","null","-"])
    v_ = defaultdict(list)
    for line in r.stdout.splitlines():
        m_ = re.match(r"lavfi\.signalstats\.(\w+)=([\d.]+)", line)
        if m_: v_[m_.group(1)].append(float(m_.group(2)))
    post[sid] = {k: round(statistics.mean(v_[k]), 1) for k in ("YAVG","YMIN","YMAX","UAVG","VAVG","SATAVG") if v_.get(k)}
jumps = []
for a, b in zip(tl, tl[1:]):
    if a["s"]["story_section"] == b["s"]["story_section"]:
        pa_, pb_ = post[a["s"]["shot_id"]], post[b["s"]["shot_id"]]
        d_ = abs(pa_["YAVG"]-pb_["YAVG"])
        if d_ > 45: jumps.append((a["s"]["shot_id"], b["s"]["shot_id"], round(d_, 1)))
exp_issues = [sid for sid, p in post.items() if p.get("YMAX", 0) >= 254 and p.get("YAVG", 100) > 190 or p.get("YAVG", 100) < 25]
fq["post_render"] = post; fq["adjacent_luma_jumps_gt45"] = jumps; fq["exposure_flags"] = exp_issues
log("QC", {k: v for k, v in fq.items() if k != "post_render"})

# ============ packaging plan ============
pk_items = []
for sid, c in cards.items():
    pk_items.append({"element_id": c["element_id"], "type": "location_card", "timeline_start": c["timeline_start"], "timeline_end": c["timeline_end"],
        "content_or_asset": f"{c['text']} / {c['date']}", "evidence": c["evidence"], "purpose": "新主要 Scene 第一次出現的地點標示（2.5 秒）",
        "safe_area": "左下角，x=90px、距底 140–210px，位於手機 UI 與 1080p 動作安全區內", "subject_or_action_collision": "PENDING_VISUAL_CHECK",
        "subtitle_collision": False, "dialogue_overlap": any(a <= c["timeline_end"] and b >= c["timeline_start"] for a, b, _ in speech_wins), "preview_status": "PENDING"})
json.dump({"status": "OK" if pk_items else "NOT_APPLICABLE", "items": pk_items, "sfx": [], "captions": []}, open(OUT/"packaging_plan.json", "w"), ensure_ascii=False, indent=1)

# save intermediates for validation phase
state = {"hashes": {"edit_decisions_sha256": H_ED, "coverage_gaps_sha256": H_CG, "story_plan_sha256": H_SP}, "gate": gate, "assets": assets, "total": TOTAL,
         "tl": [{"shot_id": x["s"]["shot_id"], "t0": x["t0"], "t1": x["t1"], "exp": x["exp"], "profile": x["profile"], "profile_source": x["profile_source"],
                 "profile_conf": x["profile_conf"], "lut": x["lut"], "source": x["s"]["source_path"], "cut": [x["s"]["cut_start"], x["s"]["cut_end"]], "speed": x["s"]["speed"]} for x in tl],
         "adj": adj, "cards": cards, "aud": aud_log, "bgm_sections": bgm_sections, "bgm_sha": bgm_sha, "bgm_raw_lufs": Lb, "mix_lufs_pre": Lm, "trim_db": round(trim_db, 2),
         "speech_windows": speech_wins, "shot_level": shot_level, "qc": fq, "vres": [(r[0], r[1]) for r in vres], "video_keys": {r[0]: r[2] for r in vres}}
json.dump(state, open(TMP/"stage3_state.json", "w"), ensure_ascii=False, default=lambda o: dict(o) if isinstance(o, Counter) else str(o))
log("DONE build; run validation writer next")
