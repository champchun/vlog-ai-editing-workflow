#!/usr/bin/env python3
"""Re-grade selected shots with a hue-preserving LUMA-ONLY curve (baked into a per-shot 33^3 .cube).

Why: per-channel RGB curves (curves=all=...) amplify chroma when lifting/pulling hard, which showed up as colour
shifts on S003/S010/S012/S017. Here Y' = f(Y) and RGB' = Y' + cg*(RGB - Y) with a mild chroma gain, then clip.
Updates workspace/temp/stage3/grade.json for only the listed shots; the others are left untouched.
"""
import json, hashlib, sys, tempfile
from pathlib import Path
import numpy as np

def PchipInterpolator(x, y, extrapolate=True):
    """Monotone cubic (Fritsch-Carlson) interpolation, linear extrapolation outside the knots."""
    x = np.asarray(x, float); y = np.asarray(y, float); h = np.diff(x); d = np.diff(y) / h
    m = np.zeros(len(x)); m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(x) - 1):
        m[i] = 0.0 if d[i - 1] * d[i] <= 0 else 2 * d[i - 1] * d[i] / (d[i - 1] + d[i])
    def f(t):
        t = float(t)
        if t <= x[0]: return y[0] + m[0] * (t - x[0])
        if t >= x[-1]: return y[-1] + m[-1] * (t - x[-1])
        i = int(np.searchsorted(x, t) - 1); s_ = (t - x[i]) / h[i]
        h00 = 2*s_**3 - 3*s_**2 + 1; h10 = s_**3 - 2*s_**2 + s_; h01 = -2*s_**3 + 3*s_**2; h11 = s_**3 - s_**2
        return h00*y[i] + h10*h[i]*m[i] + h01*y[i+1] + h11*h[i]*m[i+1]
    return f
sys.path.insert(0, str(Path(__file__).parent))
PRJ = Path(__file__).resolve().parents[2]
TMP = PRJ / "workspace/temp/stage3"
import importlib.util
spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "grade_per_shot.py")
src = open(Path(__file__).parent / "grade_per_shot.py").read().split("SKIN_TARGET =")[0]   # reuse frame()/stats()/PLAN only
ns = {"__file__": str(Path(__file__).parent / "grade_per_shot.py")}
exec(src, ns)
frame, stats, luma, ed, PLAN = ns["frame"], ns["stats"], ns["luma"], ns["ed"], ns["PLAN"]
CUBE_DIR = Path(tempfile.gettempdir()) / "stage3_grade_luts"; CUBE_DIR.mkdir(exist_ok=True)

# shot: (base_time, median IRE, black IRE, white IRE, skin_roi, skin target or None, note)
REDO = {
 "S003": (3.33, 42, 3, 92, (.30, .15, .70, .35), 48, "自拍特寫：只動亮度、保留膚色色相；膚色目標 48 IRE"),
 "S010": (7.5, 66, 4, 95, None, None, "天空：不再壓暗到 58，保留明亮通透；色相不變"),
 "S012": (4.78, 46, 3, 92, None, None, "車頭窗：只動亮度，保留原本暖色車廂"),
 "S017": (2.57, 20, 2, 80, None, None, "結尾：主體亮度與高光降低，黑背景保持黑"),
}
CG_FIXED = {"S003": 1.30, "S010": 1.35}   # chroma gain overrides after eyeballing: default (Y'/Y)^0.25 looked grey on S003 and hazy on S010
grade = json.load(open(TMP / "grade.json"))

def make_cube(f, cg_fn, path, n=33):
    ax = np.linspace(0, 1, n)
    lines = [f"TITLE \"luma_only\"", f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in ax:
        for g in ax:
            for r in ax:
                y = 0.2126 * r + 0.7152 * g + 0.0722 * b
                y2 = float(f(y)) if y > 1e-6 else float(f(0.0))
                cg = cg_fn(y2 / max(y, 1e-3))
                rgb = np.clip(y2 + cg * (np.array([r, g, b]) - y), 0, 1)
                lines.append(f"{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f}")
    path.write_text("\n".join(lines) + "\n")

for sid, (t, tm, tb, tw, roi, skin_t, why) in REDO.items():
    s = next(x for x in ed if x["shot_id"] == sid)
    base = frame(s, t); y = luma(base); before = stats(base, roi)
    p1, p50, p99 = (float(np.percentile(y, q)) for q in (1, 50, 99))
    ob, ow = tb / 100, tw / 100
    bin_ = min(max(p1 - 0.005, 0.0), 0.12); win = max(min(p99 + 0.01, 1.0), 0.6)
    mid_in = p50; mid_out = tm / 100
    if roi is not None and skin_t:
        h, w = y.shape; mid_in = float(np.median(y[int(roi[1]*h):int(roi[3]*h), int(roi[0]*w):int(roi[2]*w)])); mid_out = skin_t / 100
    xs = [0.0, max(bin_, 0.004), min(max(mid_in, bin_ + 0.03), win - 0.03), win, 1.0]
    ys = [0.0, ob, mid_out, ow, 1.0]
    for i in range(1, len(xs)):
        if xs[i] <= xs[i - 1] + 0.01: xs[i] = xs[i - 1] + 0.01
        if ys[i] <= ys[i - 1]: ys[i] = ys[i - 1] + 0.005
    f = PchipInterpolator(xs, ys, extrapolate=True)
    cg_fn = (lambda ratio, c=CG_FIXED[sid]: c) if sid in CG_FIXED else (lambda ratio: float(np.clip(ratio ** 0.25, 0.9, 1.25)))
    tmp = CUBE_DIR / "tmp.cube"; make_cube(f, cg_fn, tmp)
    h = hashlib.sha256(tmp.read_bytes()).hexdigest()[:12]; cube = CUBE_DIR / f"{sid}_{h}.cube"; tmp.rename(cube)
    vf = [f"lut3d=file='{cube}':interp=tetrahedral"]
    after = stats(frame(s, t, vf), roi)
    grade[sid] = dict(base_time_in_shot=t, base_time_source=round(s["cut_start"] + t, 3), why=why, method="luma_only_cube",
                      targets=dict(median=tm, black=tb, white=tw), before=before, after=after,
                      params=dict(points=[(round(a, 4), round(b, 4)) for a, b in zip(xs, ys)], chroma_gain=(CG_FIXED.get(sid) or "clip((Y'/Y)^0.25, 0.9, 1.25)"), cube=cube.name, cube_sha256_12=h),
                      filters=vf, skin_roi=roi, note="")
    print(sid, "before", before, "after", after, flush=True)
json.dump(grade, open(TMP / "grade.json", "w"), ensure_ascii=False, indent=1)
