#!/usr/bin/env python3
"""Natural exposure grade (colourist's call, 2026-10-14). Base = official technical LUT picture; only EXPOSURE is changed.

  * RGB' = RGB * (Y'/Y): the same gain on R, G, B -> chromaticity, saturation, white balance and skin hue are untouched.
  * Tone curve f(Y): a gamma lift that only raises what is under-exposed (never darkens), gain capped at 3x (noise),
    smooth shoulder so highlights end <= 92 IRE (hard cap 95); any channel that would pass 0.97 is scaled back (hue kept).
  * Anchors: face shots -> face ROI p90 to ~58 IRE (natural, bright skin); other shots -> scene median to a per-shot target
    chosen so neighbouring shots sit close together. Shots already bright enough (S009, S010, S012) get only the shoulder.
  * Heavily lifted shots (gain > 2.2) get a very mild hqdn3d denoise so lifted shadows stay clean.
IRE = 100 * Rec.709 luma of the post-LUT R'G'B'. Writes workspace/temp/stage3/grade.json (consumed by build_final.py).
"""
import json, hashlib, tempfile
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
src = open(HERE / "grade_per_shot.py").read().split("SKIN_TARGET =")[0]
ns = {"__file__": str(HERE / "grade_per_shot.py")}; exec(src, ns)
frame, stats, luma, ed, PLAN, TMP = ns["frame"], ns["stats"], ns["luma"], ns["ed"], ns["PLAN"], ns["TMP"]
CUBE_DIR = Path(tempfile.gettempdir()) / "stage3_grade_luts"; CUBE_DIR.mkdir(exist_ok=True)
ROI_OVERRIDE = {"S001": (.48, .30, .60, .48)}
FACE_TARGET = 58; GAIN_CAP = 3.0; SHOULDER_START = 0.70; WHITE_OUT = 0.92; HARD_CAP = 0.95; CH_LIMIT = 0.97
MID = {"S002": 30, "S004": 30, "S006": 50, "S007": 48, "S008": 44, "S010": 0, "S012": 0, "S013": 34,
       "S014": 40, "S015": 46, "S016": 42, "S017": 26}          # 0 = leave exposure alone (already bright)

def mono_cubic(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float); h = np.diff(x); d = np.diff(y) / h
    m = np.zeros(len(x)); m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(x) - 1): m[i] = 0.0 if d[i-1] * d[i] <= 0 else 2 * d[i-1] * d[i] / (d[i-1] + d[i])
    for i in range(len(d)):
        if d[i] == 0: m[i] = m[i+1] = 0
        else:
            a, b = m[i] / d[i], m[i+1] / d[i]; r = a*a + b*b
            if r > 9: t = 3 / np.sqrt(r); m[i] = t*a*d[i]; m[i+1] = t*b*d[i]
    def f(t):
        t = float(min(max(t, x[0]), x[-1])); i = max(min(int(np.searchsorted(x, t) - 1), len(h) - 1), 0); s = (t - x[i]) / h[i]
        return (2*s**3-3*s**2+1)*y[i] + (s**3-2*s**2+s)*h[i]*m[i] + (-2*s**3+3*s**2)*y[i+1] + (s**3-s**2)*h[i]*m[i+1]
    return f

def build_curve(m_in, m_out):
    """Gamma lift anchored at (m_in -> m_out) (identity if no lift needed), gain-capped, with a smooth highlight shoulder."""
    gam = 1.0
    if abs(m_out - m_in) > 1e-3: gam = np.log(m_in) / np.log(m_out)     # y**(1/gam) = m_out at y = m_in (gam>1 lifts, gam<1 darkens)
    xs = np.concatenate([np.linspace(0, 0.1, 11), np.linspace(0.12, 1.0, 45)])
    ys = []
    for v in xs:
        lift = v ** (1.0 / gam) if v > 0 else 0.0
        y = min(lift, GAIN_CAP * v) if gam > 1 else lift
        if v > SHOULDER_START:                                           # soft shoulder: ease toward WHITE_OUT at 1.0 (never above HARD_CAP)
            t = (v - SHOULDER_START) / (1.0 - SHOULDER_START)
            top = SHOULDER_START + (WHITE_OUT - SHOULDER_START) * (1 - (1 - t) ** 2)       # concave ease, ends at WHITE_OUT
            y = min(y, top)
        ys.append(y)
    ys = np.maximum.accumulate(np.array(ys)); ys = np.minimum(ys, HARD_CAP)
    for i in range(1, len(ys)):
        if ys[i] <= ys[i-1]: ys[i] = ys[i-1] + 1e-5
    return mono_cubic(xs, ys), gam

def make_cube(f, path, n=33):
    ax = np.linspace(0, 1, n); L = ['TITLE "natural_exposure"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in ax:
        for g in ax:
            for r in ax:
                y = 0.2126*r + 0.7152*g + 0.0722*b
                k = float(f(y)) / y if y > 1e-4 else float(f(1e-4)) / 1e-4
                k = min(k, GAIN_CAP)
                mx = max(r, g, b) * k
                if mx > CH_LIMIT: k *= CH_LIMIT / mx                    # hue-preserving highlight protection
                L.append(f"{min(r*k,1):.6f} {min(g*k,1):.6f} {min(b*k,1):.6f}")
    path.write_text("\n".join(L) + "\n")

grade = {}
for s in ed:
    sid = s["shot_id"]; t, _, _, _, roi, why0 = PLAN[sid]; roi = ROI_OVERRIDE.get(sid, roi)
    base = frame(s, t); y = luma(base); before = stats(base, roi)
    if roi and sid != "S010":
        h_, w_ = y.shape; r_ = y[int(roi[1]*h_):int(roi[3]*h_), int(roi[0]*w_):int(roi[2]*w_)]
        m_in = float(np.percentile(r_, 90)); m_out = FACE_TARGET / 100; anchor = "face_p90"
    else:
        m_in = float(np.percentile(y, 50)); m_out = MID[sid] / 100; anchor = "median"
    m_out = max(FACE_TARGET / 100, m_in) if anchor == "face_p90" else (max(m_out, m_in) if m_out else m_in)   # never darken (whole-frame darkening was too heavy on S009)
    f, gam = build_curve(max(m_in, 0.02), m_out)
    max_gain = max(float(f(v)) / v for v in np.linspace(0.01, 0.6, 60))
    tmp = CUBE_DIR / "tmp.cube"; make_cube(f, tmp)
    hsh = hashlib.sha256(tmp.read_bytes()).hexdigest()[:12]; cube = CUBE_DIR / f"{sid}_nat_{hsh}.cube"; tmp.rename(cube)
    vf = [f"lut3d=file='{cube}':interp=tetrahedral"]
    if max_gain > 2.2: vf.append("hqdn3d=1.5:1.5:4:4")                   # mild denoise on strongly lifted shots only
    img = frame(s, t, vf[:1]); after = stats(img, roi); ya = luma(img)
    after["white_p999"] = round(float(np.percentile(ya, 99.9)) * 100, 1); after["max_channel"] = round(float(img.max()) * 100, 1)
    if roi: after["face_p90"] = round(float(np.percentile(ya[int(roi[1]*h_):int(roi[3]*h_), int(roi[0]*w_):int(roi[2]*w_)], 90)) * 100, 1)
    grade[sid] = dict(base_time_in_shot=t, base_time_source=round(s["cut_start"] + t, 3), why=why0, method="natural_exposure_rgb_gain_cube", anchor=anchor,
                      targets=dict(anchor_out=round(m_out*100, 1), cap=HARD_CAP*100), before=before, after=after,
                      params=dict(gamma=round(float(gam), 3), max_gain=round(max_gain, 2), gain_cap=GAIN_CAP, denoise=bool(max_gain > 2.2), cube=cube.name),
                      filters=vf, skin_roi=roi, note="")
    print(sid, anchor, f"gain<= {max_gain:.2f}", "med", before["median"], "->", after["median"], "p99", before["white_p99"], "->", after["white_p99"],
          "face", before.get("skin_median"), "->", after.get("face_p90"), "maxch", after["max_channel"], flush=True)
json.dump(grade, open(TMP / "grade.json", "w"), ensure_ascii=False, indent=1)
