#!/usr/bin/env python3
"""Concatenate per-shot review previews into one labeled review video (review proxy only, never a Stage 2 source).
Usage: make_review_cut.py vN   -> storyboard/review_cut_vN.mp4"""
import json, subprocess, sys
from pathlib import Path
SB = Path(__file__).resolve().parents[3]/"process/workspace/project-output/stage1_review/storyboard"
ed = json.load(open(SB.parent.parent/"stage1_output/edit_decisions.json"))["shots"]
F = "fontfile=/System/Library/Fonts/Supplemental/Arial.ttf"
BROLL_ROLES = {"establishing", "ambient", "detail"}
ins, fc, cat = [], [], ""
for i, s in enumerate(ed):
    ins += ["-i", str(SB/"previews"/f"{s['shot_id']}.mp4")]
    extra = ""
    if s.get("is_broll"):
        extra = f",drawtext={F}:text='BROLL  0.5x slow-mo':x=w-tw-14:y=12:fontsize=30:fontcolor=white:box=1:boxcolor=0xDD5500@0.85"
    elif s["role"] in BROLL_ROLES:
        extra = f",drawtext={F}:text='BROLL':x=w-tw-14:y=12:fontsize=30:fontcolor=white:box=1:boxcolor=0x1A8A8A@0.85"
    fc.append(f"[{i}:v]fps=30,scale=960:540,setsar=1,drawtext={F}:text='{s['shot_id']}  {s['event_id']}  {s['role']}':x=12:y=12:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.55{extra}[v{i}];[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
    cat += f"[v{i}][a{i}]"
fc.append(f"{cat}concat=n={len(ed)}:v=1:a=1[v][a]")
out = SB/f"review_cut_{sys.argv[1]}.mp4"
r = subprocess.run(["ffmpeg","-y","-v","error",*ins,"-filter_complex",";".join(fc),"-map","[v]","-map","[a]","-c:v","libx264","-preset","veryfast","-crf","27","-c:a","aac","-b:a","128k","-movflags","+faststart",str(out)],capture_output=True,text=True)
print(r.stderr[-300:] or out)
print("slowmo B-roll:", [s["shot_id"] for s in ed if s.get("is_broll")])
print("labeled B-roll (role):", [s["shot_id"] for s in ed if not s.get("is_broll") and s["role"] in BROLL_ROLES])
