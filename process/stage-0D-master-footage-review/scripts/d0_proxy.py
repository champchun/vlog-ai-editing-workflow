"""Stage 0D: build 720p H.264/AAC review proxies from the ORIGINAL clips (browser-safe).
Source of the transcode is the upstream-verified 720p LRF pair when it exists (Stage 0A
source_proxy_manifest: duration/creation_time matched 1:1), else the original; much cheaper to decode.
Proxy is review-only (never a Stage 1/2/3 source); timeline is 1:1 (no trim, no fps change)."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]            # repo root
OUT = ROOT / 'process/workspace/project-output/stage0d_master_review'
PROXY = OUT / 'proxy'
PROXY.mkdir(parents=True, exist_ok=True)
cat = json.load(open(ROOT / 'process/workspace/project-output/stage0c_output/metadata_catalog.json'))['videos']

def run(v):
    dst = PROXY / f"{v['clip_id']}.mp4"
    if dst.exists() and dst.stat().st_size > 0:
        return v['clip_id'], 'skip'
    tmp = dst.with_suffix('.part.mp4')
    cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(ROOT / (v.get('proxy') or v['source_path'])),
           '-map', '0:v:0', '-map', '0:a:0?', '-vf', 'scale=1280:720,format=yuv420p',
           '-fps_mode', 'passthrough', '-c:v', 'h264_videotoolbox', '-b:v', '3M', '-allow_sw', '1',
           '-tag:v', 'avc1', '-c:a', 'aac', '-b:a', '128k', '-ac', '2', '-movflags', '+faststart', str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not tmp.exists():
        return v['clip_id'], 'FAIL ' + r.stderr[-200:]
    tmp.rename(dst)
    return v['clip_id'], 'ok'

if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    done = 0
    with ThreadPoolExecutor(n) as ex:
        for cid, st in ex.map(run, cat):
            done += 1
            if st.startswith('FAIL') or done % 20 == 0:
                print(done, cid, st, flush=True)
    print('proxy done', done, flush=True)
