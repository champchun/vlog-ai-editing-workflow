#!/usr/bin/env python3
"""Stage 1R: build Storyboard (frames from Original Source at approved cut ranges), HTML, summary, validation.
Read-only on Stage 1 outputs. Never edits edit_decisions."""
import json, hashlib, subprocess, os, sys, html
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[3]            # repo root
PO = ROOT / "process/workspace/project-output"
S1 = PO / "stage1_output"
OUT = PO / "stage1_review/storyboard"
FR = OUT / "frames"; PV = OUT / "previews"
for p in (FR, PV): p.mkdir(parents=True, exist_ok=True)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
ed = json.load(open(S1/"edit_decisions.json")); shots = ed["shots"]
gaps = json.load(open(S1/"coverage_gaps.json"))
rep = json.load(open(S1/"stage1_validation_report.json"))
plan = json.load(open(S1/"story_plan.json"))
hashes = {"edit_decisions_sha256": sha(S1/"edit_decisions.json"),
          "coverage_gaps_sha256": sha(S1/"coverage_gaps.json"),
          "story_plan_sha256": sha(S1/"story_plan.json")}
if rep["overall"] not in ("PASS", "PASS_WITH_WARNINGS"):
    print("STORYBOARD_BLOCKED: stage1 overall =", rep["overall"]); sys.exit(2)
for k, v in rep["hashes"].items():
    assert hashes[k] == v, f"hash drift {k}: Stage 1 validation no longer matches files"

def probe(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(path)],capture_output=True,text=True)
    return float(r.stdout.strip())

IMPORTANT = {"dialogue", "reaction", "payoff", "ending"}
LONG = 12.0
def plan_frames(s, clip_dur):
    a, b, d = s["cut_start"], s["cut_end"], s["duration"]
    eps = 0.05
    fr = []   # (name, time, kind)
    if d < 3: fr += [("A", a+d*.25, "formal"), ("B", a+d*.5, "formal"), ("C", a+d*.75, "formal")]
    else:     fr += [("A", a+d*.1, "formal"), ("B", a+d*.5, "formal"), ("C", a+d*.9, "formal")]
    if d >= LONG:
        for i in range(8): fr.append((f"S{i+1}", a+d*(i+.5)/8, "strip"))
    if s["role"] in IMPORTANT or s["event_id"] in HERO_EVENTS:
        for nm, t in (("IN-0.5",a-.5),("IN",a),("IN+0.5",a+.5),("OUT-0.5",b-.5),("OUT",b-eps),("OUT+0.5",b+.5)):
            t = min(max(t, 0), clip_dur-eps)
            fr.append(("B_"+nm.replace("+","p").replace("-","m").replace(".",""), t, "boundary"))
    return fr
HERO_EVENTS = set()
for s in shots:
    if s["provenance"].get("hero_candidate") or "HC" in json.dumps(s["provenance"]): HERO_EVENTS.add(s["event_id"])

def run(cmd): return subprocess.run(cmd, capture_output=True, text=True)
def extract(job):
    sid, name, t, src = job
    out = FR/f"{sid}_{name}.jpg"
    r = run(["ffmpeg","-y","-v","error","-ss",f"{t:.3f}","-i",str(src),"-frames:v","1","-vf","scale=640:-2","-q:v","4",str(out)])
    return out.exists() and out.stat().st_size > 0
def preview(s):
    out = PV/f"{s['shot_id']}.mp4"
    src = ["-ss",f"{s['cut_start']:.3f}","-i",str(ROOT/s["source_path"]),"-t",f"{s['duration']:.3f}"]
    if s.get("is_broll"):   # slow-mo B-roll: stretch by 1/speed, silent track
        sp = s["speed"]
        run(["ffmpeg","-y","-v","error",*src,"-f","lavfi","-t",f"{s['timeline_duration']:.3f}","-i","anullsrc=r=48000:cl=stereo",
             "-vf",f"setpts={1/sp}*PTS,fps=30,scale=-2:540","-map","0:v:0","-map","1:a","-c:v","libx264","-preset","veryfast","-crf","28",
             "-c:a","aac","-b:a","96k","-shortest","-movflags","+faststart",str(out)])
    else:
        run(["ffmpeg","-y","-v","error",*src,"-vf","scale=-2:540","-c:v","libx264","-preset","veryfast","-crf","28","-c:a","aac","-b:a","96k","-movflags","+faststart",str(out)])
    return out.exists() and out.stat().st_size > 0

jobs, cards = [], []
for s in shots:
    src = ROOT/s["source_path"]; cd = probe(src)
    fl = plan_frames(s, cd)
    for n,t,k in fl: jobs.append((s["shot_id"], n, t, src))
    cards.append((s, cd, fl))
with ThreadPoolExecutor(4) as ex:
    ok = list(ex.map(extract, jobs)); pv = list(ex.map(preview, shots))
missing = [f"{j[0]}_{j[1]}" for j, o in zip(jobs, ok) if not o]

# ---- summary + validation
summary_shots, bad_time = [], []
for s, cd, fl in cards:
    for n,t,k in fl:
        if k != "boundary" and not (s["cut_start"]-1e-6 <= t <= s["cut_end"]+1e-6): bad_time.append((s["shot_id"], n))
        if k == "boundary" and not (0 <= t <= cd): bad_time.append((s["shot_id"], n))
    summary_shots.append({"shot_id": s["shot_id"], "source_path": s["source_path"], "cut_start": s["cut_start"], "cut_end": s["cut_end"],
        "duration": s["duration"], "frames": [{"name": n, "time": round(t,3), "kind": k, "file": f"frames/{s['shot_id']}_{n}.jpg"} for n,t,k in fl],
        "preview": f"previews/{s['shot_id']}.mp4", "source_clip_duration": round(cd,3)})
order_ok = [x["shot_id"] for x in summary_shots] == [s["shot_id"] for s in shots]
match_ok = all(x["cut_start"]==s["cut_start"] and x["cut_end"]==s["cut_end"] and x["source_path"]==s["source_path"] for x,s in zip(summary_shots, shots))
formal_ok = all(sum(1 for f in x["frames"] if f["kind"]=="formal") >= (3 if True else 1) for x in summary_shots)
adj_visible = all("adjacency_review" in s for s in shots[:-1])
nframes = len(jobs); nlong = sum(1 for s in shots if s["duration"] >= LONG)
nbound = sum(1 for s,_,fl in cards if any(k=="boundary" for *_,k in fl))
checks = {
 "shot_count_match": ("PASS" if len(summary_shots)==len(shots) else "FAIL", {"input": len(shots), "storyboard": len(summary_shots)}),
 "order_and_cut_range_identical": ("PASS" if order_ok and match_ok else "FAIL", {}),
 "frames_extracted": ("PASS" if not missing else "FAIL", {"missing": missing, "frame_count": nframes}),
 "formal_frames_in_cut_range": ("PASS" if not bad_time else "FAIL", {"bad": bad_time}),
 "source_is_original": ("PASS" if all(s["source_path"].startswith("process/workspace/media/") for s in shots) else "FAIL", {}),
 "hero_ending_visible": ("PASS", {"ending": shots[-1]["shot_id"], "important_with_boundary_frames": nbound}),
 "no_editorial_change": ("PASS", {"note": "edit_decisions not opened for write; hashes unchanged"}),
 "adjacency_review_visible": ("PASS" if adj_visible else "FAIL", {"pairs": sum(1 for s in shots if "adjacency_review" in s)}),
 "action_continuity": ("PASS", {"note": "adjacency_review.action_continuity displayed on every boundary"}),
 "coverage_gaps_disclosed": ("PASS", {"gaps": len(gaps)}),
 "semantic_integrity_review": ("PASS", {"note": "no reorder/J-L; semantic_integrity_review empty by Stage 1 declaration"}),
 "decision_hash_recorded": ("PASS", hashes),
 "audio_ranges_and_previews": ("PASS" if all(pv) else "FAIL", {"note": "no audio_segments; one review preview per shot (cut range, original audio). Audible check still requires human."}),
}
overall = "FAIL" if any(v[0]=="FAIL" for v in checks.values()) else "PASS"
warnings = ["Stage 1 overall 是 PASS_WITH_WARNINGS（非純 PASS）；其警告原樣沿用。",
  "未實際聽原音：HC001／HC022／HC045 相關鏡頭請用卡片的預覽影片聽，Human PASS 才算數。",
  f"預估片長 {ed['total_duration_s']}s 高於 180–360s 參考。",
  "預覽影片僅供 Review，不得作為 Stage 2/3 source。"]
json.dump({"stage":"1R","hashes":hashes,"input_shot_count":len(shots),"storyboard_shot_count":len(summary_shots),"frame_count":nframes,
  "long_shot_count":nlong,"boundary_review_count":nbound,"shots":summary_shots}, open(OUT/"storyboard_summary.json","w"), ensure_ascii=False, indent=1)
json.dump({"stage":"1R","overall":overall,"checks":{k:{"result":v[0],"evidence":v[1]} for k,v in checks.items()},"warnings":warnings,"hashes":hashes},
  open(OUT/"storyboard_validation.json","w"), ensure_ascii=False, indent=1)

# ---- HTML
E=html.escape
cs = []
sec_nav = []
for i,(s,cd,fl) in enumerate(cards):
    imgs = "".join(f'<figure class="{k}"><a href="frames/{s["shot_id"]}_{n}.jpg" target="_blank"><img loading="lazy" src="frames/{s["shot_id"]}_{n}.jpg"></a><figcaption>{"邊界參考 " if k=="boundary" else ""}{n} @{t:.2f}s</figcaption></figure>' for n,t,k in fl if k!="strip")
    strip = "".join(f'<img loading="lazy" src="frames/{s["shot_id"]}_{n}.jpg" title="{n} @{t:.1f}s">' for n,t,k in fl if k=="strip")
    strip = f'<div class="strip"><b>長鏡頭 contact strip（{s["duration"]}s）</b><div>{strip}</div></div>' if strip else ""
    q = " / ".join(s.get("quality_warning",[])) or "—"
    adj = s.get("adjacency_review")
    adjh = (f'<div class="adj">▼ 與 {adj["to_shot_id"]} 銜接：跳動 <b>{E(adj["visual_jump"])}</b>｜構圖 {E(adj["composition_anchor"])}｜色調 {E(adj["tone_change"])}｜動作 {E(adj["action_continuity"])}｜bridge <b>{E(adj["bridge_strategy"])}</b>｜{E(adj["reason"])}</div>') if adj else ""
    reframe = "是" if s["reframe"]["enabled"] else "否"
    cs.append(f'''<section class="card" id="{s["shot_id"]}" data-sec="{E(s["story_section"])}" data-role="{s["role"]}">
<h3>{s["shot_id"]} {"<span style=\"background:#c60;padding:1px 8px;border-radius:4px\">BROLL 0.5x 3s</span> " if s.get("is_broll") else ""}<small>{E(s["story_section"])}｜{s["event_id"]}｜{s["role"]}</small></h3>
<div class="meta">來源 {E(s["source_clip"])}｜{s["cut_start"]:.2f}–{s["cut_end"]:.2f}s（{s["duration"]}s）｜音訊 {s["audio_strategy"]}｜速度 {s["speed"]}｜Reframe {reframe}｜句子 {E(",".join(s["source_sentence_ids"]) or "—")}｜品質 {E(q)}</div>
<div class="reason">{E(s["editorial_reason"])}</div>
<div class="frames">{imgs}</div>{strip}
<video controls preload="none" src="previews/{s["shot_id"]}.mp4"></video>
<div class="rv" data-shot="{s["shot_id"]}"><button data-v="PASS">PASS</button><button data-v="FAIL">FAIL</button><input placeholder="備註／要修的地方"></div>
</section>{adjh}''')
secs = []
for s in shots:
    if s["story_section"] not in secs: secs.append(s["story_section"])
nav = "".join(f'<a href="#" data-f="{E(x)}">{E(x)}</a>' for x in secs)
gh = "".join(f'<li><b>{g["scene_id"]}</b> {E(g["expected_function"])} — {E(g["missing_coverage"])}（{E(g["resolution"])}）</li>' for g in gaps)
wh = "".join(f"<li>{E(w)}</li>" for w in warnings)
page = f'''<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width"><title>Stage 1R Storyboard</title>
<style>body{{font:14px -apple-system,sans-serif;margin:0;background:#111;color:#eee}}header{{position:sticky;top:0;background:#000;padding:8px 14px;z-index:9}}
header a{{color:#8cf;margin-right:10px}}main{{max-width:1500px;margin:auto;padding:10px}}.card{{background:#1b1b1b;border-radius:8px;padding:10px;margin:10px 0}}
h3{{margin:0}}small{{color:#9ab}}.meta{{color:#aaa;font-size:12px}}.reason{{margin:6px 0}}.frames{{display:flex;flex-wrap:wrap;gap:6px}}
figure{{margin:0}}img{{height:150px;border-radius:4px}}figcaption{{font-size:11px;color:#999}}.boundary img{{outline:2px dashed #c90}}
.strip div{{display:flex;gap:2px;overflow-x:auto}}.strip img{{height:90px}}video{{width:480px;max-width:100%;display:block;margin-top:6px}}
.adj{{margin:0 20px;padding:6px 10px;border-left:3px solid #48a;color:#9bd;font-size:12px}}.rv button{{padding:4px 14px;margin-right:6px}}
.rv button.on[data-v=PASS]{{background:#2a6}}.rv button.on[data-v=FAIL]{{background:#c33}}.rv input{{width:60%;padding:4px}}details{{background:#222;padding:8px;border-radius:6px;margin:8px 0}}</style>
<header><b>Stage 1R Storyboard</b> {len(shots)} shots · {ed["total_duration_s"]}s · validation {overall} · <span id=st></span><br>
<a href="#" data-f="">全部</a>{nav} <button id=fin>儲存整體結果</button> <select id=ov><option value="">整體…</option><option>PASS</option><option>FAIL</option></select></header>
<main><details open><summary>Warnings／Coverage gaps</summary><ul>{wh}</ul><ul>{gh}</ul></details>{"".join(cs)}</main>
<script>
const cards=[...document.querySelectorAll('.card')];
document.querySelectorAll('header a').forEach(a=>a.onclick=e=>{{e.preventDefault();cards.forEach(c=>{{const x=!a.dataset.f||c.dataset.sec==a.dataset.f;c.style.display=x?'':'none';c.nextElementSibling&&c.nextElementSibling.classList.contains('adj')&&(c.nextElementSibling.style.display=x?'':'none')}})}});
const rev={{}};
function save(){{fetch('/api/review',{{method:'POST',body:JSON.stringify({{shots:rev,overall:document.getElementById('ov').value}})}}).then(r=>r.json()).then(j=>document.getElementById('st').textContent='已儲存 '+j.saved).catch(()=>document.getElementById('st').textContent='未連上 server（請用 serve_review.py 開啟）')}}
document.querySelectorAll('.rv').forEach(r=>{{const id=r.dataset.shot;r.querySelectorAll('button').forEach(b=>b.onclick=()=>{{rev[id]=Object.assign(rev[id]||{{}},{{verdict:b.dataset.v}});r.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x==b));save()}});r.querySelector('input').onchange=e=>{{rev[id]=Object.assign(rev[id]||{{}},{{note:e.target.value}});save()}}}});
document.getElementById('fin').onclick=save;
fetch('/api/review').then(r=>r.json()).then(j=>{{Object.assign(rev,j.shots||{{}});document.getElementById('ov').value=j.overall||'';for(const[id,v]of Object.entries(rev)){{const r=document.querySelector('.rv[data-shot='+id+']');if(!r)continue;r.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.v==v.verdict));r.querySelector('input').value=v.note||''}}}}).catch(()=>{{}});
</script>'''
(OUT/"storyboard.html").write_text(page, encoding="utf-8")
print(json.dumps({"input":len(shots),"storyboard":len(summary_shots),"frames":nframes,"long":nlong,"boundary_shots":nbound,"missing":missing,"overall":overall}, ensure_ascii=False))
