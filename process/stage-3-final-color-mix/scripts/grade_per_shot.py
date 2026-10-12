#!/usr/bin/env python3
"""Per-shot grade from a director-chosen 'best looking' base frame, guided by IRE.

For each shot: decode the base frame from the Original (rotation + technical LUT only), measure luma IRE
percentiles (IRE = 100 * luma of Rec.709 R'G'B', i.e. limited-range Y 16-235 -> 0-100), then compute a
levels+gamma grade that maps black/median/white to the targets chosen for that shot. Writes
workspace/temp/stage3/grade.json, which build_final.py applies. Also writes before/after numbers.
"""
import json, subprocess, sys, io
from pathlib import Path
import numpy as np
from PIL import Image

PRJ = Path(__file__).resolve().parents[2]
PO = PRJ / "workspace/project-output"
TMP = PRJ / "workspace/temp/stage3"
LUT_DIR = PRJ / "stage-3-final-color-mix/assets/lut"
LUTS = {"D-Log": "DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube",
        "D-Log2": "DJI OSMO Pocket 4P D-Log2 to Rec.709 V1.0 size65.cube"}
ed = json.load(open(PO / "stage1_output/edit_decisions.json"))["shots"]
master = {c["clip_id"]: c for c in json.load(open(PO / "stage0d_master_review/master_footage_review.json"))}

# shot: (base_time_in_shot_s, target_median_IRE, target_black_IRE, target_white_IRE, skin_roi or None, why)
PLAN = {
 "S001": (2.62, 36, 3, 90, (.42, .17, .64, .50), "臉在陰影，抬到可辨識；地鐵站偏暗，不拉成白天"),
 "S002": (5.25, 26, 2, 88, None, "車廂偏暗，只提到看得見主體；保留車廂氣氛"),
 "S003": (3.33, 42, 3, 92, (.30, .15, .70, .35), "自拍臉部特寫，以額頭膚色為準"),
 "S004": (1.98, 24, 2, 85, None, "展場暗處的貓，提到看清臉；仍是暗場"),
 "S005": (1.25, 45, 3, 92, (.22, .22, .47, .60), "展場室內，孩子側臉為準"),
 "S006": (2.92, 48, 3, 94, None, "貓牆明亮背景，避免白牆過曝"),
 "S007": (5.19, 46, 3, 94, None, "舞台玩耍，人物偏小，以整體清爽為準"),
 "S008": (1.95, 48, 3, 94, None, "大廳逆光玻璃，壓住高光"),
 "S009": (5.62, 52, 3, 94, (.50, .45, .60, .72), "烈日戶外，原片偏白霧，增加對比、臉為準"),
 "S010": (7.5, 58, 4, 94, None, "天空偏白無主體，以有樹與高架橋的畫面為準，壓住高光"),
 "S011": (2.5, 48, 3, 93, (.23, .30, .35, .50), "車頭窗，回頭笑的臉為準"),
 "S012": (4.78, 48, 3, 93, None, "車頭窗，兩人側背，場景延續 S011"),
 "S013": (4.5, 28, 2, 85, None, "暗色展區，保留氣氛，只提到甲蟲看得清"),
 "S014": (2.1, 38, 2, 88, None, "鬣蜥，色偏灰，提亮並保留岩壁暗部"),
 "S015": (1.63, 42, 3, 90, None, "鬃獅蜥箱，暖光明亮，略壓高光"),
 "S016": (1.25, 38, 2, 88, None, "陸龜熱燈箱，保留暖色"),
 "S017": (2.57, 30, 2, 90, None, "結尾鬃獅蜥，黑背景保持黑，主體亮度優先"),
}

def frame(shot, t_in_shot, with_grade=None):
    s = shot
    m = master[s["source_clip"]]; prof = m["color_profile"]
    vf = []
    if s.get("rotation") == 180: vf.append("hflip,vflip")
    vf += [f"lut3d=file='{LUTS[prof]}':interp=tetrahedral"]
    if with_grade: vf += with_grade
    vf += ["scale=960:540:flags=bilinear", "format=rgb24"]
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s['cut_start']+t_in_shot:.3f}", "-i", str(PRJ / s["source_path"]),
                        "-frames:v", "1", "-vf", ",".join(vf), "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, cwd=str(LUT_DIR))
    if r.returncode or not r.stdout: sys.exit(f"decode fail {s['shot_id']} {r.stderr[-300:]}")
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB"), dtype=np.float32) / 255.0

def luma(a): return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
def stats(a, roi=None):
    y = luma(a)
    o = {"black_p1": round(float(np.percentile(y, 1)) * 100, 1), "median": round(float(np.percentile(y, 50)) * 100, 1),
         "white_p99": round(float(np.percentile(y, 99)) * 100, 1), "clip_pct_over_98": round(float((y > 0.98).mean()) * 100, 2)}
    if roi:
        h, w = y.shape; x0, y0, x1, y1 = roi
        o["skin_median"] = round(float(np.median(y[int(y0*h):int(y1*h), int(x0*w):int(x1*w)])) * 100, 1)
    return o

SKIN_TARGET = {"S001": 50, "S003": 52, "S005": 52, "S009": 58, "S011": 50}
grade = {}
for s in ed:
    sid = s["shot_id"]; t, tm, tb, tw, roi, why = PLAN[sid]
    base = frame(s, t); b = stats(base, roi)
    y = luma(base)
    p1, p50, p99 = (float(np.percentile(y, q)) for q in (1, 50, 99))
    ob, ow, tmid = tb / 100, tw / 100, tm / 100
    bin_ = min(max(p1 - 0.005, 0.0), 0.12)           # input black point (never crush more than 12 IRE)
    win = max(min(p99 + 0.01, 1.0), 0.6)              # input white point
    if roi is not None and SKIN_TARGET.get(sid):      # face shots: the face drives the grade (skin ~50-75 IRE)
        sk = float(np.median(y[int(roi[1]*y.shape[0]):int(roi[3]*y.shape[0]), int(roi[0]*y.shape[1]):int(roi[2]*y.shape[1])]))
        mid_in, mid_out = sk, SKIN_TARGET[sid] / 100
    else:
        mid_in, mid_out = p50, tmid
    def build(mid_out_):
        pts_ = [(max(bin_, 0.004), ob), (min(max(mid_in, bin_ + 0.03), win - 0.03), mid_out_), (win, ow), (1.0, 1.0)]
        for i in range(1, len(pts_)):                  # keep strictly increasing x and monotonic y
            if pts_[i][0] <= pts_[i - 1][0] + 0.01: pts_[i] = (pts_[i - 1][0] + 0.01, max(pts_[i][1], pts_[i - 1][1] + 0.005))
            if pts_[i][1] <= pts_[i - 1][1]: pts_[i] = (pts_[i][0], pts_[i - 1][1] + 0.005)
        p_ = dict(points=[(round(x, 4), round(y_, 4)) for x, y_ in pts_])
        return p_, ["curves=all='" + " ".join(f"{x:.4f}/{y_:.4f}" for x, y_ in p_["points"]) + "'"]
    note = ""
    while True:
        params, vf = build(mid_out)
        st_ = stats(frame(s, t, vf), roi)
        if roi is None or not SKIN_TARGET.get(sid) or (st_["median"] <= 65 and st_["clip_pct_over_98"] <= 1.0) or mid_out <= 0.30: break
        mid_out -= 0.03; note = f"skin target lowered to {mid_out*100:.0f} IRE to keep scene median<=65 and clipping<=1%"
    after = stats(frame(s, t, vf), roi)
    grade[sid] = dict(base_time_in_shot=t, base_time_source=round(s["cut_start"] + t, 3), why=why, targets=dict(median=tm, black=tb, white=tw),
                      before=b, after=after, params=params, filters=vf, skin_roi=roi, note=note)
    print(sid, "before", b, "after", after, flush=True)
json.dump(grade, open(TMP / "grade.json", "w"), ensure_ascii=False, indent=1)
