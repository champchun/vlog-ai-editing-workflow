#!/usr/bin/env python3
"""Luma-curve grade per shot (user spec 2026-10-12). Strictly monotone, no S-curve, no sharpening/clarity/local contrast.

Control points (input IRE -> output IRE), luma only (chroma kept: RGB' = Y' + (RGB - Y)), baked into a 33^3 .cube:
  black    0   -> 5        slightly lifted, never crushed
  shadows  25  -> 25       on the diagonal (dark scenes: on the black->mid chord so no groove / no S shape)
  midtones m_in -> m_out   soft arc; face shots: face-ROI p90 -> 67 IRE; others: scene median -> table below
  highs    h   -> <=91     near the diagonal
  white    100 -> 95       soft roll-off, hard cap 95 IRE
Interpolation: monotone cubic (Fritsch-Carlson); the script asserts the sampled curve is non-decreasing.
IRE = 100 * Rec.709 luma of the post-technical-LUT R'G'B' image. Writes workspace/temp/stage3/grade.json.
"""
import json, hashlib, tempfile
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
src = open(HERE / "grade_per_shot.py").read().split("SKIN_TARGET =")[0]
ns = {"__file__": str(HERE / "grade_per_shot.py")}; exec(src, ns)
frame, stats, luma, ed, PLAN, TMP = ns["frame"], ns["stats"], ns["luma"], ns["ed"], ns["PLAN"], ns["TMP"]
CUBE_DIR = Path(tempfile.gettempdir()) / "stage3_grade_luts"; CUBE_DIR.mkdir(exist_ok=True)
FACE = 67; BLACK_OUT = 5; CAP = 95
ROI_OVERRIDE = {"S001": (.48, .30, .60, .48)}
# per-shot overrides (user, 2026-10-12): under-exposed / hazy / sky-dominated shots do not use the global 65-70 IRE face rule
OVR = {
 "S001": dict(face=53.0, black_out=2.0, cg=1.1, alpha=0.85, gain_line=True),                                   # under-exposed room: face 50-55, chroma +20%, keep blacks down
 "S009": dict(face=57.5, black_float=12.0),                                         # haze: face 55-60, p1 -> ~12 IRE (blacks may float 8-12), no hard de-haze
 "S010": dict(roi=(0.0, 0.5, 0.4, 1.0), roi_stat="median", mid_out=57.5, sky_out=92.0),   # sky: p99 -> 92, ground/structure ROI -> 55-60
}
MID_OUT = {"S002": 34, "S004": 34, "S006": 54, "S007": 52, "S008": 54, "S010": 85, "S012": 50, "S013": 36,
           "S014": 46, "S015": 48, "S016": 45, "S017": 28}

def mono_cubic(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float); h = np.diff(x); d = np.diff(y) / h
    m = np.zeros(len(x)); m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(x) - 1): m[i] = 0.0 if d[i-1] * d[i] <= 0 else 2 * d[i-1] * d[i] / (d[i-1] + d[i])
    # Fritsch-Carlson limiter (guarantees monotone, no overshoot)
    for i in range(len(d)):
        if d[i] == 0: m[i] = m[i+1] = 0
        else:
            a, b = m[i] / d[i], m[i+1] / d[i]; r = a*a + b*b
            if r > 9: t = 3 / np.sqrt(r); m[i] = t*a*d[i]; m[i+1] = t*b*d[i]
    def f(t):
        t = float(min(max(t, x[0]), x[-1])); i = min(int(np.searchsorted(x, t) - 1), len(h) - 1); i = max(i, 0); s = (t - x[i]) / h[i]
        return (2*s**3-3*s**2+1)*y[i] + (s**3-2*s**2+s)*h[i]*m[i] + (-2*s**3+3*s**2)*y[i+1] + (s**3-s**2)*h[i]*m[i+1]
    return f

def make_cube(f, path, n=33, cg=1.0, alpha=0.0):
    ax = np.linspace(0, 1, n); L = ['TITLE "luma_curve"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in ax:
        for g in ax:
            for r in ax:
                y = 0.2126*r + 0.7152*g + 0.0722*b; y2 = float(f(y))
                k = cg * (min(max(y2 / max(y, 1e-3), 1.0), 6.0) ** alpha if alpha else 1.0)     # chroma follows the luma gain (exposure-like)
                rgb = np.clip(y2 + min(k, 3.0) * (np.array([r, g, b]) - y), 0, 1)
                L.append(f"{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f}")
    path.write_text("\n".join(L) + "\n")

grade = {}
for s in ed:
    sid = s["shot_id"]; t, _, _, _, roi, why0 = PLAN[sid]; roi = ROI_OVERRIDE.get(sid, roi)
    base = frame(s, t); y = luma(base); before = stats(base, roi)
    p50 = float(np.percentile(y, 50)); ov = OVR.get(sid, {}); cg = ov.get("cg", 1.0); black_out = ov.get("black_out", float(BLACK_OUT))
    if "roi_stat" in ov:                                   # S010: anchor on a ground/structure ROI median instead of the sky
        roi = ov["roi"]; h_, w_ = y.shape
        m_in = float(np.median(y[int(roi[1]*h_):int(roi[3]*h_), int(roi[0]*w_):int(roi[2]*w_)])) * 100; m_out = ov["mid_out"]; anchor = "ground_roi_median"
    elif roi:
        h_, w_ = y.shape; r_ = y[int(roi[1]*h_):int(roi[3]*h_), int(roi[0]*w_):int(roi[2]*w_)]
        m_in = float(np.percentile(r_, 90)) * 100; m_out = float(ov.get("face", FACE)); anchor = "face_p90"
    else:
        m_in = p50 * 100; m_out = float(MID_OUT[sid]); anchor = "median"
    m_in = min(max(m_in, 6.0), 88.0)
    if not roi: m_out = min(m_out, BLACK_OUT + 3.5 * m_in)      # cap the gain on very dark shots (noise)                          # keep the midtone anchor between the end points
    chord = lambda xi: black_out + (m_out - black_out) * xi / m_in
    if m_in >= 45:  s_in = 25.0; s_out = 25.0 if chord(25.0) >= 25.0 else chord(25.0)   # on the diagonal
    else:           s_in = 0.5 * m_in; s_out = 0.95 * chord(s_in)                       # dark scene: just under the chord, no groove
    s_out = max(s_out, black_out + 0.5)
    h_in = max(85.0, m_in + 8.0); h_out = max(min(h_in, 91.0), m_out + 3.0)
    pts = [(0.0, float(black_out)), (s_in, s_out), (m_in, m_out), (h_in, h_out), (100.0, float(CAP))]
    if ov.get("gain_line"):                                # S001: plain exposure gain, blacks stay ~5, face 53, wall rolls off ~88
        p1_in = float(np.percentile(y, 1)) * 100; p99_in = float(np.percentile(y, 99)) * 100
        pts = [(0.0, 2.0), (p1_in, 5.0), (m_in, m_out), (p99_in, 88.0), (100.0, float(CAP))]
    if "black_float" in ov:                                # S009: hazy blacks stay where they are (p1 -> ~12), gentle slope, no hard de-haze
        p1_in = float(np.percentile(y, 1)) * 100
        pts = [(0.0, 3.0), (p1_in, ov["black_float"]), (m_in, m_out), (100.0, float(CAP))]
    if "sky_out" in ov:                                    # S010: protect the sky: p99 -> 92, ground/structure -> 55-60
        p99_in = float(np.percentile(y, 99)) * 100
        pts = [(0.0, float(black_out)), (m_in, m_out), (min(p99_in, 97.0), ov["sky_out"]), (100.0, float(CAP))]
    pts = [p for i, p in enumerate(pts) if i == 0 or p[0] > pts[i-1][0] + 1.0]   # drop points that crowd their neighbour
    for i in range(1, len(pts)):                                # enforce strictly increasing outputs
        if pts[i][1] <= pts[i-1][1]: pts[i] = (pts[i][0], pts[i-1][1] + 0.5)
    pts[-1] = (100.0, float(CAP)) if pts[-1][1] <= CAP else pts[-1]
    f = mono_cubic([p[0] / 100 for p in pts], [p[1] / 100 for p in pts])
    xs = np.linspace(0, 1, 2001); ys = np.array([f(v) for v in xs])
    assert np.all(np.diff(ys) >= -1e-9), f"{sid}: curve not monotone"
    assert ys.max() <= CAP / 100 + 1e-6, f"{sid}: curve exceeds cap"
    tmp = CUBE_DIR / "tmp.cube"; make_cube(f, tmp, cg=cg, alpha=ov.get('alpha', 0.0))
    hsh = hashlib.sha256(tmp.read_bytes()).hexdigest()[:12]; cube = CUBE_DIR / f"{sid}_curve_{hsh}.cube"; tmp.rename(cube)
    vf = [f"lut3d=file='{cube}':interp=tetrahedral"]
    img = frame(s, t, vf); after = stats(img, roi); ya = luma(img)
    after["white_p999"] = round(float(np.percentile(ya, 99.9)) * 100, 1)
    if roi: after["face_p90"] = round(float(np.percentile(ya[int(roi[1]*h_):int(roi[3]*h_), int(roi[0]*w_):int(roi[2]*w_)], 90)) * 100, 1)
    grade[sid] = dict(base_time_in_shot=t, base_time_source=round(s["cut_start"] + t, 3), why=why0, method="luma_curve_monotone_cube", anchor=anchor,
                      targets=dict(black_point=black_out, cap=CAP, **({"face_p90": m_out} if anchor == "face_p90" else {"anchor_median": m_out})),
                      before=before, after=after, params=dict(chroma_gain=cg, override=ov or None, points_ire=[(round(a, 1), round(b, 1)) for a, b in pts], monotone_checked=True, cube=cube.name),
                      filters=vf, skin_roi=roi, note="")
    print(sid, anchor, [(round(a), round(b)) for a, b in pts], "after", {k: v for k, v in after.items() if k != "clip_pct_over_98"}, flush=True)
json.dump(grade, open(TMP / "grade.json", "w"), ensure_ascii=False, indent=1)
