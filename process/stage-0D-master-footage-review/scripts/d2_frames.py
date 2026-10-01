"""Stage 0D step 2: extract Hero / Contact / Segment frames from the ORIGINAL clips (640px JPG)."""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'process/workspace/project-output/stage0d_master_review'
FR = OUT / 'frames'; FR.mkdir(exist_ok=True)
jobs = json.load(open(OUT / 'frame_jobs.json'))

def run(j):
    dst = FR / j['out']
    if dst.exists() and dst.stat().st_size > 0: return j['out'], True
    r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(j['ts']), '-i', str(ROOT / j['src']), '-frames:v', '1',
                        '-vf', 'scale=640:-2,format=yuvj420p', '-q:v', '4', str(dst)], capture_output=True)
    return j['out'], dst.exists() and dst.stat().st_size > 0

if __name__ == '__main__':
    bad = [o for o, ok in ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 3).map(run, jobs) if not ok]
    print('frames', len(jobs), 'failed', len(bad), bad[:10])
