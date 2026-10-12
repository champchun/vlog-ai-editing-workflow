#!/usr/bin/env python3
"""Match clip capture time (from DJI filename, local +08:00) to Google Timeline
and write GPS into the MP4. Default is dry-run; --apply writes in place.
Usage: gps_tag_videos.py MEDIA_DIR TIMELINE_JSON OUT_DIR [--apply]"""
import json, re, sys, glob, subprocess, hashlib, os
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
media, tl, out = sys.argv[1:4]
apply = "--apply" in sys.argv
os.makedirs(out, exist_ok=True)

def geo(s):
    a, b = s.replace("geo:", "").split(",")[:2]
    return float(a), float(b)

segs = []
for x in json.load(open(tl)):
    k = next((k for k in ("visit", "activity") if k in x), None)
    if not k: continue
    s = datetime.fromisoformat(x["startTime"]); e = datetime.fromisoformat(x["endTime"])
    v = x[k]
    if k == "visit":
        segs.append((s, e, "visit", geo(v["topCandidate"]["placeLocation"]), None,
                     v["topCandidate"].get("semanticType"), float(v.get("probability", 0))))
    else:
        segs.append((s, e, "activity", geo(v["start"]), geo(v["end"]),
                     v["topCandidate"]["type"], float(v.get("probability", 0))))

def locate(t):
    for s, e, kind, p0, p1, label, prob in segs:
        if s <= t < e:
            if kind == "visit":
                return p0, "visit", label, prob, s.tzinfo
            f = (t - s) / (e - s)
            p = (p0[0] + (p1[0]-p0[0])*f, p0[1] + (p1[1]-p0[1])*f)
            return p, "activity_interpolated", label, prob, s.tzinfo
    return None, "no_coverage", None, 0, None

rows = []
for f in sorted(glob.glob(os.path.join(media, "**", "*.MP4"), recursive=True)):
    m = re.search(r"_(\d{14})_", f)
    if not m: continue
    fname_start = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=TZ)
    ct = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_tags=creation_time", "-of", "csv=p=0", f]).decode().strip().split(",")[0]
    # creation_time (UTC) is authoritative; filename time is off by 1h on some clips (verified by content)
    start = datetime.fromisoformat(ct.replace("Z", "+00:00")).astimezone(TZ) if ct else fname_start
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))
    mid = start + timedelta(seconds=dur/2)
    p, how, label, prob, loc_tz = locate(mid)
    local = mid.astimezone(loc_tz) if loc_tz else None   # clock time at the GPS location (Timeline offset)
    before = json.loads(subprocess.check_output(["exiftool", "-json", "-n", "-Keys:GPSCoordinates", "-XMP:GPSLatitude", "-XMP:GPSLongitude", f]))[0]
    rows.append(dict(path=f, start=start.isoformat(), filename_start=fname_start.isoformat(), time_basis="creation_time_utc" if ct else "filename", duration_s=round(dur, 2), capture_time_utc=mid.astimezone(timezone.utc).isoformat(), local_time_at_gps_location=local and local.isoformat(), gps_location_utc_offset=local and local.strftime("%z"), lat=p and round(p[0], 6), lon=p and round(p[1], 6),
                     method=how, context=label, probability=prob, previous_gps=before))

json.dump(rows, open(os.path.join(out, "gps_match.json"), "w"), ensure_ascii=False, indent=1)
for r in rows:
    print(os.path.basename(r["path"])[4:19], r["method"], r["context"], r["lat"], r["lon"])

if apply:
    for r in rows:
        if r["lat"] is None: continue
        c = f'{r["lat"]:+.6f}{r["lon"]:+.6f}/'
        subprocess.check_call(["exiftool", "-overwrite_original_in_place", "-q",
            f'-Keys:GPSCoordinates={r["lat"]}, {r["lon"]}',
            f'-XMP:GPSLatitude={r["lat"]}', f'-XMP:GPSLongitude={r["lon"]}', r["path"]])
    print("applied", sum(r["lat"] is not None for r in rows))
