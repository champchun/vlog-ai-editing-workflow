#!/usr/bin/env python3
"""依照 Google 地圖時間軸（Timeline.json）替 MP4 / DNG / JPG 寫入 GPS 位置（只補沒有 GPS 的檔案）。

本檔屬於 Stage 0A 的前置步驟，由使用者在 0A 之前自行執行（見 README）。

用法：
    # 不指定 --timeline：自動使用 workspace/gps/ 內檔名含 timeline 的 .json
    python3 geotag_engine.py --media ./DJI_001

    # 先預覽（不改檔，只輸出 CSV）
    python3 geotag_engine.py --timeline "Timeline 3.json" --media ./DJI_001

    # 確認沒問題後寫入
    python3 geotag_engine.py --timeline "Timeline 3.json" --media ./DJI_001 --write

時間來源：
    MP4：QuickTime CreateDate（UTC）
    DNG：EXIF DateTimeOriginal（相機本地時間，沒有時區）
         → 時區預設由同資料夾 MP4 推算（檔名時間 − UTC CreateDate），
           也可以用 --dng-tz +09:00 直接指定。

需要 exiftool（brew install exiftool）。
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov"}
PHOTO_EXTS = {".dng", ".jpg", ".jpeg", ".heic", ".arw", ".cr3", ".nef"}
NAME_TIME_RE = re.compile(r"(20\d{12})")  # DJI_20260925090846_0043_D → 20260925090846


# ---------------------------------------------------------------- timeline

@dataclass
class Visit:
    start: datetime
    end: datetime
    lat: float
    lon: float


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_geo(s: str) -> tuple[float, float]:
    lat, lon = s.removeprefix("geo:").split(",")
    return float(lat), float(lon)


class Timeline:
    def __init__(self, path: Path):
        entries = json.loads(path.read_text(encoding="utf-8"))
        self.visits: list[Visit] = []
        points: list[tuple[datetime, float, float]] = []

        for e in entries:
            try:
                start, end = parse_time(e["startTime"]), parse_time(e["endTime"])
                if "visit" in e:
                    lat, lon = parse_geo(e["visit"]["topCandidate"]["placeLocation"])
                    self.visits.append(Visit(start, end, lat, lon))
                    points += [(start, lat, lon), (end, lat, lon)]
                elif "activity" in e:
                    a = e["activity"]
                    if "start" in a:
                        points.append((start, *parse_geo(a["start"])))
                    if "end" in a:
                        points.append((end, *parse_geo(a["end"])))
                elif "timelinePath" in e:
                    for p in e["timelinePath"]:
                        t = start + timedelta(minutes=float(p["durationMinutesOffsetFromStartTime"]))
                        points.append((t, *parse_geo(p["point"])))
            except (KeyError, ValueError):
                continue

        self.visits.sort(key=lambda v: v.start)
        self.visit_starts = [v.start for v in self.visits]
        points.sort(key=lambda p: p[0])
        self.points = points
        self.point_times = [p[0] for p in points]

    def locate(self, t: datetime, max_gap: timedelta) -> tuple[float, float, str] | None:
        # 1) 停留點（visit）優先
        i = bisect.bisect_right(self.visit_starts, t) - 1
        if i >= 0 and self.visits[i].start <= t <= self.visits[i].end:
            v = self.visits[i]
            return v.lat, v.lon, "visit"

        # 2) 移動中：前後兩點線性內插
        j = bisect.bisect_left(self.point_times, t)
        before = self.points[j - 1] if j > 0 else None
        after = self.points[j] if j < len(self.points) else None
        if before and after and (after[0] - before[0]) <= max_gap * 2:
            span = (after[0] - before[0]).total_seconds()
            r = 0.0 if span == 0 else (t - before[0]).total_seconds() / span
            lat = before[1] + (after[1] - before[1]) * r
            lon = before[2] + (after[2] - before[2]) * r
            return lat, lon, "interpolated"

        # 3) 最近的一點（在 max_gap 內）
        near = [p for p in (before, after) if p and abs(p[0] - t) <= max_gap]
        if near:
            p = min(near, key=lambda p: abs(p[0] - t))
            return p[1], p[2], "nearest"
        return None


# ---------------------------------------------------------------- media

def parse_tz(s: str) -> timezone:
    m = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})?", s.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"時區格式錯誤：{s}（例：+09:00）")
    sign = 1 if m.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)))


def exif_dt(s: str | None) -> datetime | None:
    if not s or s.startswith("0000"):
        return None
    try:
        return datetime.strptime(s[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def name_dt(name: str) -> datetime | None:
    m = NAME_TIME_RE.search(name)
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S") if m else None


def has_real_gps(meta: dict) -> bool:
    lat, lon = meta.get("GPSLatitude"), meta.get("GPSLongitude")
    try:
        return lat is not None and lon is not None and not (float(lat) == 0 and float(lon) == 0)
    except (TypeError, ValueError):
        return False


def read_metadata(files: list[Path]) -> dict[Path, dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(str(p) for p in files))
        argfile = f.name
    out = subprocess.run(
        ["exiftool", "-json", "-n", "-api", "QuickTimeUTC=0",
         "-QuickTime:CreateDate", "-DateTimeOriginal", "-OffsetTimeOriginal",
         "-GPSLatitude", "-GPSLongitude", "-@", argfile],
        capture_output=True, text=True,
    )
    Path(argfile).unlink(missing_ok=True)
    return {Path(m["SourceFile"]): m for m in json.loads(out.stdout or "[]")}


def camera_tz_samples(videos: list[tuple[Path, dict]]) -> list[tuple[datetime, timedelta]]:
    """從 MP4 推相機時區：檔名（相機本地時間）− CreateDate（UTC）。"""
    samples = []
    for path, meta in videos:
        local, utc = name_dt(path.name), exif_dt(meta.get("CreateDate"))
        if local and utc:
            offset = timedelta(minutes=round((local - utc).total_seconds() / 900) * 15)
            if timedelta(hours=-12) <= offset <= timedelta(hours=14):
                samples.append((local, offset))
    return sorted(samples)


def guess_offset(local: datetime, samples: list[tuple[datetime, timedelta]]) -> timedelta | None:
    if not samples:
        return None
    return min(samples, key=lambda s: abs(s[0] - local))[1]


def fmt_offset(td: timedelta) -> str:
    mins = int(td.total_seconds() // 60)
    sign = "+" if mins >= 0 else "-"
    return f"{sign}{abs(mins) // 60:02d}:{abs(mins) % 60:02d}"


# ---------------------------------------------------------------- timeline discovery

GPS_DIR = Path(__file__).resolve().parents[2] / "workspace" / "gps"


def find_timeline(gps_dir: Path = GPS_DIR) -> Path:
    """The single *.json in the GPS folder whose name contains 'timeline' (case-insensitive)."""
    found = sorted(p for p in gps_dir.iterdir()
                   if p.is_file() and p.suffix.lower() == ".json"          # .JSON counts too (glob is case-sensitive)
                   and "timeline" in p.name.lower() and not p.name.startswith("."))
    if not found:
        sys.exit(f"沒有指定 --timeline，而且在 {gps_dir} 找不到檔名含 timeline 的 .json")
    if len(found) > 1:
        sys.exit(f"在 {gps_dir} 找到多個 timeline 檔，請用 --timeline 指定其中一個：\n  " + "\n  ".join(p.name for p in found))
    return found[0]


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="依 Google Timeline 替 MP4/DNG 寫入 GPS 位置")
    ap.add_argument("--timeline", type=Path, help="Timeline JSON 路徑（不指定時，自動到 workspace/gps/ 找檔名含 timeline 的 .json）")
    ap.add_argument("--media", required=True, type=Path, help="素材資料夾（MP4/DNG）")
    ap.add_argument("--recursive", action="store_true", help="包含子資料夾")
    ap.add_argument("--dng-tz", type=parse_tz, help="照片的相機時區（例 +09:00）；不填則由 MP4 自動推算")
    ap.add_argument("--max-gap", type=float, default=30, help="與時間軸最近點最多相差幾分鐘（預設 30）")
    ap.add_argument("--time-shift", type=float, default=0, help="所有素材時間額外偏移秒數（校正相機時鐘）")
    ap.add_argument("--force", action="store_true", help="已有 GPS 的檔案也覆寫")
    ap.add_argument("--write", action="store_true", help="實際寫入（未加此參數只做預覽）")
    ap.add_argument("--keep-original", action="store_true", help="寫入時保留 exiftool 的 _original 備份")
    ap.add_argument("--report", type=Path, help="預覽 CSV 輸出路徑（預設 <media>/geotag_report.csv）")
    args = ap.parse_args()

    if args.timeline is None:
        args.timeline = find_timeline()
        print(f"未指定 --timeline，自動使用：{args.timeline}")
    if not args.timeline.is_file():
        sys.exit(f"找不到時間軸：{args.timeline}")
    if not args.media.is_dir():
        sys.exit(f"找不到素材資料夾：{args.media}")

    print(f"讀取時間軸：{args.timeline}")
    tl = Timeline(args.timeline)
    print(f"  停留點 {len(tl.visits)} 筆，軌跡點 {len(tl.points)} 筆")

    pattern = "**/*" if args.recursive else "*"
    files = sorted(p for p in args.media.glob(pattern)
                   if p.is_file() and not p.name.startswith("._")
                   and p.suffix.lower() in VIDEO_EXTS | PHOTO_EXTS)
    if not files:
        sys.exit("資料夾內沒有 MP4 / DNG")
    print(f"讀取 {len(files)} 個檔案的 metadata…")
    meta = read_metadata(files)

    videos = [(p, meta.get(p, {})) for p in files if p.suffix.lower() in VIDEO_EXTS]
    tz_samples = camera_tz_samples(videos)
    shift = timedelta(seconds=args.time_shift)
    max_gap = timedelta(minutes=args.max_gap)

    rows, to_write = [], []
    for p in files:
        m = meta.get(p, {})
        row = {"file": p.name, "shot_utc": "", "camera_tz": "", "lat": "", "lon": "", "source": "", "status": ""}

        if p.suffix.lower() in VIDEO_EXTS:
            utc = exif_dt(m.get("CreateDate"))
            if utc:
                utc = utc.replace(tzinfo=timezone.utc)
                row["camera_tz"] = "UTC"
        else:
            local = exif_dt(m.get("DateTimeOriginal")) or name_dt(p.name)
            utc = None
            if local:
                if m.get("OffsetTimeOriginal"):
                    tz = parse_tz(m["OffsetTimeOriginal"])
                elif args.dng_tz:
                    tz = args.dng_tz
                else:
                    off = guess_offset(local, tz_samples)
                    tz = timezone(off) if off is not None else None
                if tz:
                    utc = local.replace(tzinfo=tz).astimezone(timezone.utc)
                    row["camera_tz"] = fmt_offset(tz.utcoffset(None))

        if not utc:
            row["status"] = "無拍攝時間／無法判斷時區"
            rows.append(row)
            continue

        utc += shift
        row["shot_utc"] = utc.strftime("%Y-%m-%d %H:%M:%S")

        if has_real_gps(m) and not args.force:
            row["status"] = "已有 GPS，略過"
            rows.append(row)
            continue

        loc = tl.locate(utc, max_gap)
        if not loc:
            row["status"] = "時間軸沒有對應位置"
            rows.append(row)
            continue

        lat, lon, source = loc
        row.update(lat=f"{lat:.6f}", lon=f"{lon:.6f}", source=source, status="待寫入")
        rows.append(row)
        to_write.append((p, lat, lon))

    report = args.report or args.media / "geotag_report.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("結果：" + "、".join(f"{k} {v}" for k, v in counts.items()))
    print(f"報表：{report}")

    if not args.write:
        print("（預覽模式，未改檔。確認報表後加上 --write 寫入）")
        return 0
    if not to_write:
        return 0

    print(f"寫入 {len(to_write)} 個檔案…")
    lines = []
    for p, lat, lon in to_write:
        lat_ref, lon_ref = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
        if p.suffix.lower() in VIDEO_EXTS:
            iso6709 = f"{lat:+.6f}{lon:+.6f}/"
            tags = [f"-Keys:GPSCoordinates={lat}, {lon}",
                    f"-UserData:GPSCoordinates={lat}, {lon}",
                    f"-XMP:GPSLatitude={lat}", f"-XMP:GPSLongitude={lon}",
                    f"-ItemList:GPSCoordinates={iso6709}"]
        else:
            tags = [f"-GPSLatitude={abs(lat)}", f"-GPSLatitudeRef={lat_ref}",
                    f"-GPSLongitude={abs(lon)}", f"-GPSLongitudeRef={lon_ref}",
                    "-GPSMapDatum=WGS-84", "-GPSProcessingMethod=Google Timeline",
                    "-GPSAltitude=", "-GPSAltitudeRef="]   # no GPSStatus=A: keep Timeline-derived coords distinguishable from a camera fix
        lines += tags + [str(p), "-execute"]

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
        argfile = f.name
    common = ["-m", "-q"] + ([] if args.keep_original else ["-overwrite_original"])
    proc = subprocess.run(["exiftool", "-@", argfile, "-common_args", *common], text=True)
    Path(argfile).unlink(missing_ok=True)
    print("完成" if proc.returncode == 0 else f"exiftool 回傳 {proc.returncode}，請檢查上方訊息")
    if proc.returncode == 0:   # report must reflect reality after a write
        for r in rows:
            if r["status"] == "待寫入":
                r["status"] = "已寫入"
        with report.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
