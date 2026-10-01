"""Stage 0D step 3: install Console (app.py + html from examples/), write proxy_manifest.json,
re-merge any existing Human Review into master_footage_review.json."""
import json, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / 'process/stage-0D-master-footage-review/examples'
OUT = ROOT / 'process/workspace/project-output/stage0d_master_review'
for f in ('app.py', 'master_footage_review.html', 'quick_review.html'):
    shutil.copy(KIT / f, OUT / f)
master = json.load(open(OUT / 'master_footage_review.json', encoding='utf-8'))

def probe(p):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,duration',
                                   '-of', 'json', str(p)], capture_output=True, text=True).stdout)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), {})
    a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), {})
    return {'format_duration': float(j['format']['duration']), 'video_duration': float(v.get('duration', 0)), 'vcodec': v.get('codec_name'),
            'acodec': a.get('codec_name'), 'size': f"{v.get('width')}x{v.get('height')}", 'fps': v.get('r_frame_rate')}

cat = {v['clip_id']: v for v in json.load(open(ROOT / 'process/workspace/project-output/stage0c_output/metadata_catalog.json'))['videos']}
items = []
for m in master:
    p = OUT / m['play_url']
    if not p.exists():
        items.append({'clip_id': m['clip_id'], 'exists': False}); continue
    pr, src = probe(p), cat[m['clip_id']]
    d = abs(pr['video_duration'] - src['video_duration'])
    items.append({'clip_id': m['clip_id'], 'proxy': m['play_url'], 'source_path': m['source_path'], 'exists': True, **pr,
                  'source_duration': src['video_duration'], 'source_fps': src['fps_rational'], 'duration_delta_s': round(d, 4),
                  'time_mapping_1to1': d <= 0.1, 'fps_note': 'proxy frame rate differs from source (LRF is 30fps); time axis/duration unchanged' if pr['fps'] != src['fps_rational'] else None,
                  'transcoded_from': 'upstream_verified_LRF_pair' if src.get('proxy') else 'original', 'review_only': True})
json.dump({'note': 'Review proxies for Stage 0D only. NEVER a Stage 1/2/3 source; time axis is 1:1 with the original (no trim, no fps change).',
           'proxies': items}, open(OUT / 'proxy_manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
sys.path.insert(0, str(OUT)); import app; app.merge_master()
print('manifest', len(items), 'ok', sum(i.get('time_mapping_1to1', False) for i in items))
