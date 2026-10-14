#!/usr/bin/env python3
"""LUT-only reference render: same shots/cuts/audio as the Final, technical LUT only (rotation fix for S004), no grading."""
import json, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
PRJ = Path(__file__).resolve().parents[2]; PO = PRJ / "workspace/project-output"
OUT = PO / "stage3_output"; TMP = PRJ / "workspace/temp/stage3/lut_only"; TMP.mkdir(parents=True, exist_ok=True)
LUT_DIR = PRJ / "stage-3-final-color-mix/assets/lut"
LUTS = {"D-Log": "DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube", "D-Log2": "DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube"}
ed = json.load(open(PO / "stage1_output/edit_decisions.json"))["shots"]
def render(s):
    out = TMP / f"{s['shot_id']}.mp4"
    vf = (["hflip,vflip"] if s.get("rotation") == 180 else []) + [f"lut3d=file='{LUTS[s['color_profile']]}':interp=tetrahedral", "scale=1920:1080:flags=bicubic", "fps=30", "setsar=1", "format=yuv420p"]
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s['cut_start']:.3f}", "-i", str(PRJ / s["source_path"]), "-t", f"{s['cut_end']-s['cut_start']:.3f}",
                        "-an", "-map", "0:v:0", "-vf", ",".join(vf), "-t", f"{(s['cut_end']-s['cut_start'])/s['speed']:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-r", "30", str(out)],
                       capture_output=True, text=True, cwd=str(LUT_DIR))
    if r.returncode: sys.exit(f"{s['shot_id']} {r.stderr[-300:]}")
    return out
with ThreadPoolExecutor(3) as ex: parts = list(ex.map(render, ed))
lst = TMP / "concat.txt"; lst.write_text("".join("file '" + str(p).replace("'", "'\\''") + "'\n" for p in parts))
cat = TMP / "cat.mp4"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(cat)], check=True)
final = OUT / "final_vlog_1080p_LUT_only.mp4"      # audio copied from the current master so only the picture differs
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(cat), "-i", str(OUT / "final_vlog_1080p_master.mp4"), "-map", "0:v", "-map", "1:a", "-c", "copy", "-shortest", str(final)], check=True)
FONT = "/System/Library/Fonts/Helvetica.ttc"; dts = []
for s in ed:
    a = s["timeline_start"]; b = a + s["duration"]
    txt = f"{s['shot_id']}  {s['source_clip']}  LUT only".replace(":", "\\:")
    dts.append(f"drawtext=fontfile={FONT}:text='{txt}':x=24:y=24:fontsize=40:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=10:enable='between(t,{a:.3f},{b-0.001:.3f})'")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-vf", ",".join(dts), "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-c:a", "copy", str(OUT / "final_vlog_1080p_LUT_only_labeled.mp4")], check=True)
print("done")
