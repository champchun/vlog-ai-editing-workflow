"""Stage 0A shared paths and helpers."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

PROCESS = Path(__file__).resolve().parents[2]
WORKSPACE = PROCESS / "workspace"
MEDIA = WORKSPACE / "media"
GPS_DIR = WORKSPACE / "gps"
OUT = WORKSPACE / "project-output" / "stage0a_output"
TEMP = WORKSPACE / "temp" / "stage0a"

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
PHOTO_EXTS = {".jpg", ".jpeg", ".dng", ".heic", ".arw", ".png", ".tif", ".tiff"}
PROXY_EXTS = {".lrf"}
SIDECAR_EXTS = {".pp3", ".csv", ".md", ".xmp", ".srt"}


def rel(p: Path) -> str:
    """Path relative to the process/ directory (repository-stable)."""
    return str(Path(p).resolve().relative_to(PROCESS.parent))


def sampled_hash(p: Path, chunk: int = 4 * 1024 * 1024) -> str:
    """sha256 over size + first/middle/last chunk. Candidate-only duplicate key."""
    size = p.stat().st_size
    h = hashlib.sha256(str(size).encode())
    with open(p, "rb") as f:
        for off in (0, max(0, size // 2 - chunk // 2), max(0, size - chunk)):
            f.seek(off)
            h.update(f.read(chunk))
    return "sampled-sha256:" + h.hexdigest()


def full_hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b""):
            h.update(b)
    return "sha256:" + h.hexdigest()


def run_json(cmd: list[str]):
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def ffprobe(p: Path) -> dict:
    return run_json(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(p)])


def iter_media():
    for root, dirs, files in os.walk(MEDIA):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for n in sorted(files):
            if n.startswith("._") or n.startswith("."):
                continue
            yield Path(root) / n


def _np_default(o):
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(type(o))


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_np_default), encoding="utf-8")
    tmp.replace(p)


def read_json(p: Path, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def cache_key(p: Path, params: dict) -> str:
    st = p.stat()
    return hashlib.sha1(json.dumps([str(p), st.st_size, int(st.st_mtime), params], sort_keys=True).encode()).hexdigest()[:16]
