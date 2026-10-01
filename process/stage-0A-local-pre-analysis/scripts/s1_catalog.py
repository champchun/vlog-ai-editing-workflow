#!/usr/bin/env python3
"""Stage 0A step 1: media scan, ffprobe/exiftool metadata, color evidence,
GPS provenance, duplicate candidates, LRF proxy pairing (metadata level).

Output (intermediate): temp/stage0a/catalog.json
"""
from __future__ import annotations

import csv
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import (MEDIA, PHOTO_EXTS, PROXY_EXTS, SIDECAR_EXTS, TEMP, VIDEO_EXTS,
                    ffprobe, full_hash, iter_media, read_json, rel, run_json,
                    sampled_hash, write_json)

NAME_TIME_RE = re.compile(r"DJI_(20\d{12})_")
EXIFTOOL_VER = subprocess.run(["exiftool", "-ver"], capture_output=True, text=True).stdout.strip()
FFPROBE_VER = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True).stdout.split("\n")[0]

# Exact DJI ColorGammaSxS strings we map. Anything else stays unknown with raw value preserved.
DJI_GAMMA_MAP = {"D-Log": "D-Log", "D-Log M": "D-Log M", "D-Log2": "D-Log2", "HLG": "HLG"}


def fr(s):
    try:
        a, b = s.split("/")
        return round(int(a) / int(b), 4) if int(b) else None
    except Exception:
        return None


def load_geotag_reports():
    """geotag_report.csv written by geotag_engine.py (earlier runs: shared-resources/geotag_from_timeline.py)."""
    rep = {}
    for p in MEDIA.rglob("geotag_report.csv"):
        if p.name.startswith("._"):
            continue
        with open(p, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rep[(p.parent.resolve(), row["file"])] = {**row, "report_path": rel(p)}
    return rep


def exif_batch(paths):
    out = {}
    paths = list(paths)
    for i in range(0, len(paths), 60):
        chunk = paths[i:i + 60]
        data = run_json(["exiftool", "-json", "-G1", "-n", "-api", "LargeFileSupport=1", *map(str, chunk)])
        for d in data:
            out[str(Path(d["SourceFile"]).resolve())] = d
    return out


def pick(d, *keys):
    for k in keys:
        if k in d and d[k] not in (None, "", " "):
            return d[k]
    return None


def video_record(p: Path, ex: dict, geo: dict | None):
    pr = ffprobe(p)
    fmt = pr["format"]
    tags = fmt.get("tags", {})
    vids = [s for s in pr["streams"] if s["codec_type"] == "video" and s.get("codec_name") != "mjpeg"]
    auds = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    datas = [s for s in pr["streams"] if s["codec_type"] == "data"]
    v = vids[0] if vids else {}
    rotation = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    rotation = int(pick(ex, "Composite:Rotation") or rotation or 0)

    creation_utc = tags.get("creation_time")
    m = NAME_TIME_RE.search(p.name)
    name_local = datetime.strptime(m.group(1), "%Y%m%d%H%M%S") if m else None
    tz_offset = None
    if name_local and creation_utc:
        cu = datetime.fromisoformat(creation_utc.replace("Z", "+00:00")).replace(tzinfo=None)
        mins = round((name_local - cu).total_seconds() / 900) * 15
        if abs(mins) <= 14 * 60:
            tz_offset = f"{'+' if mins >= 0 else '-'}{abs(mins)//60:02d}:{abs(mins)%60:02d}"

    # ---- color evidence
    raw_gamma = tags.get("com.dji.camera.ColorGammaSxS") or pick(ex, "Keys:DjiCameraColorGammaSxS")
    model = tags.get("com.dji.camera.CameraModel") or pick(ex, "Keys:DjiCameraCameraModel")
    detected = {k: v.get(k) for k in ("pix_fmt", "color_space", "color_transfer", "color_primaries", "color_range")}
    detected["bits_per_raw_sample"] = v.get("bits_per_raw_sample")
    conflicts = []
    if raw_gamma and raw_gamma.strip() in DJI_GAMMA_MAP:
        profile = DJI_GAMMA_MAP[raw_gamma.strip()]
        src = "camera_metadata:Keys/com.dji.camera.ColorGammaSxS"
        conf = "high"
        if profile.startswith("D-Log") and "10" not in (v.get("pix_fmt") or ""):
            conflicts.append("log gamma declared but stream is not 10-bit")
            profile, conf = "unknown", "conflict"
    else:
        profile, src, conf = "unknown", None, "none"
        if raw_gamma:
            conflicts.append(f"unmapped ColorGammaSxS value {raw_gamma!r}; not guessed")

    # ---- GPS provenance
    gps = None
    lat, lon = pick(ex, "Composite:GPSLatitude"), pick(ex, "Composite:GPSLongitude")
    if lat is not None and lon is not None:
        gps = {"lat": lat, "lon": lon, "written_by": None, "method": None,
               "evidence_level": "auxiliary", "note": None}
        if geo:
            gps.update(written_by="stage-0A geotag_engine.py (Google Maps Timeline; earlier runs: shared-resources/geotag_from_timeline.py)",
                       method=geo.get("source"), report=geo.get("report_path"),
                       report_status=geo.get("status"))
            gps["note"] = ("Coordinates were written into the file from Google Timeline, not recorded by the camera. "
                           "Auxiliary evidence only; named places need further confirmation.")
        else:
            gps["note"] = "GPS source not established (no geotag report entry). Treat as unverified auxiliary data."

    return {
        "media_type": "video",
        "clip_id": p.stem,
        "filename": p.name,
        "source_path": rel(p),
        "source_id": {"camera_model": model, "encoder": tags.get("encoder"),
                      "camera_serial_suffix": (tags.get("com.dji.camera.CameraSerialNumber") or "")[-4:] or None,
                      "original_file_path": pick(ex, "UserData:OriginalFilePath")},
        "file_size_bytes": int(fmt["size"]),
        "file_mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
        "sampled_hash": sampled_hash(p),
        "creation_time_utc": creation_utc,
        "camera_local_time_from_filename": name_local.isoformat() if name_local else None,
        "derived_tz_offset": tz_offset,
        "timecode": tags.get("timecode"),
        "duration": round(float(fmt["duration"]), 4),
        "video_duration": round(float(v.get("duration", fmt["duration"])), 4),
        "fps": fr(v.get("avg_frame_rate")),
        "fps_rational": v.get("avg_frame_rate"),
        "codec": v.get("codec_name"),
        "codec_tag": v.get("codec_tag_string"),
        "resolution": {"width": v.get("width"), "height": v.get("height")},
        "rotation": rotation,
        "bitrate_bps": int(fmt.get("bit_rate", 0)) or None,
        "audio": {
            "track_count": len(auds),
            "tracks": [{"index": a["index"], "codec": a.get("codec_name"), "sample_rate": a.get("sample_rate"),
                        "channels": a.get("channels"), "duration": a.get("duration")} for a in auds],
            "asr_track": auds[0]["index"] if auds else None,
        },
        "data_streams": [s.get("codec_tag_string") for s in datas],
        "stream_start_times": {"video": float(v.get("start_time", 0) or 0),
                               "audio": [float(a.get("start_time", 0) or 0) for a in auds]},
        "detected_color_metadata": detected,
        "color_profile": profile,
        "color_profile_source": src,
        "color_profile_confidence": conf,
        "color_evidence": {"raw_ColorGammaSxS": raw_gamma, "camera_model": model,
                           "white_balance_kelvin": tags.get("com.dji.camera.WhiteBalanceKelvin"),
                           "lens": tags.get("com.dji.camera.LensType"),
                           "firmware": tags.get("com.dji.camera.SupVersion"),
                           "tools": [EXIFTOOL_VER and f"exiftool {EXIFTOOL_VER}", FFPROBE_VER],
                           "mapping_basis": "Exact string match of the DJI camera Keys atom ColorGammaSxS; "
                                            "ffprobe bt709 tags are recorded separately and not used as profile evidence.",
                           "conflicts": conflicts},
        "gps": gps,
        "proxy": None,
        "duplicate_of": None,
        "warnings": [],
    }


def photo_record(p: Path, ex: dict, geo: dict | None):
    dto = pick(ex, "ExifIFD:DateTimeOriginal", "IFD0:DateTimeOriginal", "XMP-exif:DateTimeOriginal")
    off = pick(ex, "ExifIFD:OffsetTimeOriginal")
    gps = None
    lat, lon = pick(ex, "Composite:GPSLatitude"), pick(ex, "Composite:GPSLongitude")
    if lat is not None and lon is not None:
        marker = str(pick(ex, "GPS:GPSProcessingMethod") or "")
        if "timeline" in marker.lower() and not geo:
            geo = {"source": "timeline(in-file GPSProcessingMethod)", "report_path": None}
        cam_fix = pick(ex, "GPS:GPSStatus") == "A" and pick(ex, "Composite:GPSDateTime") and not geo
        gps = {"lat": lat, "lon": lon, "evidence_level": "auxiliary",
               "written_by": "stage-0A geotag_engine.py (Google Maps Timeline; earlier runs: shared-resources/geotag_from_timeline.py)" if geo
               else ("camera EXIF GPS (GPSStatus=A)" if cam_fix else None),
               "method": geo.get("source") if geo else ("camera_exif" if cam_fix else None),
               "gps_datetime_utc": pick(ex, "Composite:GPSDateTime"),
               "note": "Timeline-derived, auxiliary only" if geo
               else ("Camera-recorded fix; auxiliary for named places" if cam_fix else "GPS source not established")}
    return {
        "media_type": "photo",
        "photo_id": p.stem + p.suffix.lower().replace(".", "_"),
        "filename": p.name,
        "source_path": rel(p),
        "format": (ex.get("File:FileType") or p.suffix[1:]).upper(),
        "source_id": {"make": pick(ex, "IFD0:Make"), "camera_model": pick(ex, "IFD0:Model")},
        "file_size_bytes": p.stat().st_size,
        "sampled_hash": sampled_hash(p),
        "datetime_original": dto,
        "offset_time_original": off,
        "resolution": {"width": pick(ex, "Composite:ImageSize") and int(str(ex["Composite:ImageSize"]).split()[0].split("x")[0]),
                       "height": pick(ex, "Composite:ImageSize") and int(str(ex["Composite:ImageSize"]).split()[-1].split("x")[-1])},
        "orientation": pick(ex, "IFD0:Orientation"),
        "gps": gps,
        "sidecars": [rel(s) for s in [p.with_name(p.name + ".pp3"), p.with_suffix(".xmp")] if s.exists()],
        "not_applicable": ["transcript", "vad", "fps", "cut_range"],
        "duplicate_of": None,
        "warnings": ([] if dto else ["no DateTimeOriginal"]) + ([] if lat is not None else
                    [f"no GPS coordinates (GPSStatus={pick(ex, 'GPS:GPSStatus')})"]),
    }


def main():
    TEMP.mkdir(parents=True, exist_ok=True)
    files = list(iter_media())
    geo = load_geotag_reports()
    videos, photos, proxies, sidecars, unknown = [], [], [], [], []
    for p in files:
        e = p.suffix.lower()
        (videos if e in VIDEO_EXTS else photos if e in PHOTO_EXTS else proxies if e in PROXY_EXTS
         else sidecars if e in SIDECAR_EXTS else unknown).append(p)

    ex = exif_batch(videos + photos)
    # Confirm type by probing, not by extension/folder.
    with ThreadPoolExecutor(6) as pool:
        vrecs = list(pool.map(lambda p: video_record(p, ex.get(str(p.resolve()), {}), geo.get((p.parent.resolve(), p.name))), videos))
    prec = []
    for p in photos:
        d = ex.get(str(p.resolve()), {})
        mime = d.get("File:MIMEType", "")
        if not mime.startswith("image/"):
            unknown.append(p)
            continue
        prec.append(photo_record(p, d, geo.get((p.parent.resolve(), p.name))))
    for r in vrecs:
        if not r["codec"] or not r["duration"]:
            r["warnings"].append("no decodable video stream")

    # ---- LRF proxy pairing (metadata level; content spot check in s2)
    by_stem = {Path(r["source_path"]).with_suffix("").name: r for r in vrecs}
    proxy_entries, unpaired = [], []
    for lp in proxies:
        pr = ffprobe(lp)
        v = next((s for s in pr["streams"] if s["codec_type"] == "video" and s.get("codec_name") != "mjpeg"), {})
        d = float(pr["format"]["duration"])
        ct = pr["format"].get("tags", {}).get("creation_time")
        src = by_stem.get(lp.stem)
        ent = {"proxy_path": rel(lp), "proxy_duration": round(d, 4),
               "proxy_resolution": f'{v.get("width")}x{v.get("height")}', "proxy_fps": fr(v.get("avg_frame_rate")),
               "proxy_creation_time_utc": ct}
        if src:
            dd = round(d - src["duration"], 4)
            def _t(x):
                return datetime.fromisoformat(x.replace("Z", "+00:00"))
            ct_delta = round((_t(ct) - _t(src["creation_time_utc"])).total_seconds(), 3) if ct and src["creation_time_utc"] else None
            same_time = ct_delta is not None and abs(ct_delta) <= 2.0
            ent.update(source_path=src["source_path"], source_duration=src["duration"], duration_delta=dd,
                       creation_time_match=same_time, creation_time_delta_seconds=ct_delta,
                       time_offset_seconds=0.0,
                       metadata_match=bool(abs(dd) <= 0.1 and same_time),
                       content_check=None, pairing_status="metadata_matched_pending_content_check"
                       if abs(dd) <= 0.1 and same_time else "metadata_mismatch")
        else:
            ent.update(source_path=None, pairing_status="unpaired")
            unpaired.append(rel(lp))
        proxy_entries.append(ent)

    # ---- duplicate candidates: sampled hash collision -> full hash verification
    groups = defaultdict(list)
    for r in vrecs + prec:
        groups[r["sampled_hash"]].append(r)
    dup_groups = []
    for h, rs in groups.items():
        if len(rs) < 2:
            continue
        fh = defaultdict(list)
        for r in rs:
            fh[full_hash(Path(__file__).resolve().parents[3] / r["source_path"])].append(r)
        for k, same in fh.items():
            if len(same) > 1:
                keep = same[0]
                for r in same[1:]:
                    r["duplicate_of"] = keep["source_path"]
                dup_groups.append({"full_hash": k, "files": [r["source_path"] for r in same], "verified": True})

    write_json(TEMP / "catalog.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tools": {"exiftool": EXIFTOOL_VER, "ffprobe": FFPROBE_VER},
        "videos": vrecs, "photos": prec, "proxies": proxy_entries,
        "unpaired_proxies": unpaired,
        "sidecars": [rel(p) for p in sidecars],
        "unknown_files": [rel(p) for p in unknown],
        "duplicate_groups": dup_groups,
    })
    from collections import Counter
    print("videos", len(vrecs), "photos", len(prec), "proxies", len(proxy_entries), "unpaired", len(unpaired),
          "unknown", len(unknown), "dups", len(dup_groups))
    print("color", Counter((r["color_evidence"]["raw_ColorGammaSxS"], r["color_profile"]) for r in vrecs))
    print("fps", Counter((r["resolution"]["width"], r["resolution"]["height"], r["fps"]) for r in vrecs))
    print("tz", Counter(r["derived_tz_offset"] for r in vrecs))
    print("proxy status", Counter(e["pairing_status"] for e in proxy_entries))
    print("gps", Counter((r["gps"] or {}).get("method") for r in vrecs + prec))


if __name__ == "__main__":
    main()
