#!/usr/bin/env python3
"""YouTube-clean grade for every shot (user principle, 2026-10-12):
  black p1 -> ~2 IRE (0-5), face highlights (ROI p90) -> 65-70 IRE, highlights (p99) <= ~93 and hard cap 95 IRE,
  stronger contrast (S-curve around the midpoint). Hue-preserving: luma-only curve baked into a per-shot 33^3 .cube
  (RGB' = Y' + cg*(RGB - Y)). Writes workspace/temp/stage3/grade.json consumed by build_final.py.
IRE = 100 * Rec.709 luma of the (post technical-LUT) R'G'B' image.
"""
import json, hashlib, tempfile, importlib.util
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
src = open(HERE / "grade_per_shot.py").read().split("SKIN_TARGET =")[0]       # frame(), stats(), luma(), ed, PLAN
ns = {"__file__": str(HERE / "grade_per_shot.py")}; exec(src, ns)
frame, stats, luma, ed, PLAN, TMP = ns["frame"], ns["stats"], ns["luma"], ns["ed"], ns["PLAN"], ns["TMP"]
CUBE_DIR = Path(tempfile.gettempdir()) / "stage3_grade_luts"; CUBE_DIR.mkdir(exist_ok=True)

def mono_cubic(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float); h = np.diff(x); d = np.diff(y) / h
    m = np.zeros(len(x)); m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(x) - 1): m[i] = 0.0 if d[i-1] * d[i] <= 0 else 2 * d[i-1] * d[i] / (d[i-1] + d[i])
    def f(t):
        t = float(t)
        if t <= x[0]: return y[0] + m[0] * (t - x[0])
        if t >= x[-1]: return y[-1] + m[-1] * (t - x[-1])
        i = int(np.searchsorted(x, t) - 1); s = (t - x[i]) / h[i]
        return (2*s**3-3*s**2+1)*y[i] + (s**3-2*s**2+s)*h[i]*m[i] + (-2*s**3+3*s**2)*y[i+1] + (s**3-s**2)*h[i]*m[i+1]
    return f

def make_cube(f, cg, path, n=33):
    ax = np.linspace(0, 1, n); L = ['TITLE "youtube_luma"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in ax:
        for g in ax:
            for r in ax:
                y = 0.2126*r + 0.7152*g + 0.0722*b; y2 = min(float(f(y)), 0.95)      # hard cap 95 IRE
                c = float(np.clip(cg * (max(y2, 1e-3) / max(y, 1e-3)) ** 0.15, 0.95, 1.35))
                rgb = np.clip(y2 + c * (np.array([r, g, b]) - y), 0, 0.95 if False else 1)
                L.append(f"{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f}")
    path.write_text("\n".join(L) + "\n")

# non-face shots: median IRE target (face shots use ROI p90 -> 67 IRE). Highlights p99 -> 93, black p1 -> 2.
MID = {"S002": 28, "S004": 28, "S006": 52, "S007": 50, "S008": 52, "S010": 62, "S012": 48, "S013": 32,
       "S014": 42, "S015": 46, "S016": 42, "S017": 24}
FACE_P90 = 67
ROI_OVERRIDE = {"S001": (.48, .30, .60, .48)}   # tighter face box: the first box included the white wall
CG_OVERRIDE = {"S010": 1.45}   # sky lost its blue after stripping haze; richer chroma for this shot only
CG = 1.12                      # slightly richer chroma for the clean/airy look
grade = {}
for s in ed:
    sid = s["shot_id"]; t, _, _, _, roi, why0 = PLAN[sid]
    roi = ROI_OVERRIDE.get(sid, roi)
    base = frame(s, t); y = luma(base); before = stats(base, roi)
    p1, p50, p99 = (float(np.percentile(y, q)) for q in (1, 50, 99))
    bin_ = min(max(p1 - 0.003, 0.0), 0.40)              # allow stripping haze (S009/S010) but never past 40 IRE
    win = max(min(p99, 1.0), bin_ + 0.25)
    ob, ow = 0.02, 0.93
    if roi:
        h_, w_ = y.shape; r_ = y[int(roi[1]*h_):int(roi[3]*h_), int(roi[0]*w_):int(roi[2]*w_)]
        mid_in = float(np.percentile(r_, 90)); mid_out = FACE_P90 / 100; anchor = "face_p90"
    else:
        mid_in = p50; mid_out = MID[sid] / 100; anchor = "median"
    # keep the anchor strictly inside (black, white); cap how bright the scene median may get on face shots
    mid_in = min(max(mid_in, bin_ + 0.03), win - 0.04)
    xs = [0.0, max(bin_, 0.004), None, mid_in, None, win, 1.0]
    # S-curve: shadows slightly deeper and highlights slightly crisper than the straight line through the 3 anchors
    lo_x = bin_ + 0.5 * (mid_in - bin_); hi_x = mid_in + 0.5 * (win - mid_in)
    lo_y = ob + 0.42 * (mid_out - ob); hi_y = mid_out + 0.62 * (ow - mid_out)
    xs = [0.0, max(bin_, 0.004), lo_x, mid_in, hi_x, win, 1.0]; ys = [0.0, ob, lo_y, mid_out, hi_y, ow, 0.95]
    for i in range(1, len(xs)):
        if xs[i] <= xs[i-1] + 0.008: xs[i] = xs[i-1] + 0.008
        if ys[i] <= ys[i-1]: ys[i] = ys[i-1] + 0.004
    f = mono_cubic(xs, ys)
    tmp = CUBE_DIR / "tmp.cube"; make_cube(f, CG_OVERRIDE.get(sid, CG), tmp)
    hsh = hashlib.sha256(tmp.read_bytes()).hexdigest()[:12]; cube = CUBE_DIR / f"{sid}_yt_{hsh}.cube"; tmp.rename(cube)
    vf = [f"lut3d=file='{cube}':interp=tetrahedral"]
    after_img = frame(s, t, vf); after = stats(after_img, roi); ya = luma(after_img)
    after["white_p999"] = round(float(np.percentile(ya, 99.9)) * 100, 1)
    if roi: after["face_p90"] = round(float(np.percentile(ya[int(roi[1]*h_):int(roi[3]*h_), int(roi[0]*w_):int(roi[2]*w_)], 90)) * 100, 1)
    grade[sid] = dict(base_time_in_shot=t, base_time_source=round(s["cut_start"] + t, 3), why=why0, method="youtube_luma_cube", anchor=anchor,
                      targets=dict(black=2, white=93, cap=95, **({"face_p90": FACE_P90} if roi else {"median": MID[sid]})),
                      before=before, after=after, params=dict(points=[(round(a, 4), round(b, 4)) for a, b in zip(xs, ys)], chroma_gain=CG_OVERRIDE.get(sid, CG), cube=cube.name),
                      filters=vf, skin_roi=roi, note="")
    print(sid, anchor, "before", before, "after", after, flush=True)
json.dump(grade, open(TMP / "grade.json", "w"), ensure_ascii=False, indent=1)
