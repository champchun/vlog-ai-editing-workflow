"""Stage 0D step 4: master_footage_review_validation.json (counts, hero/strip, reasons, persistence test, proxy 1:1, zh-TW, upstream untouched)."""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
PO = ROOT / 'process/workspace/project-output'
OUT = PO / 'stage0d_master_review'
L = lambda p: json.load(open(p, encoding='utf-8'))
master, man = L(OUT / 'master_footage_review.json'), L(OUT / 'proxy_manifest.json')['proxies']
cat = L(PO / 'stage0c_output/metadata_catalog.json')
checks = {}
def chk(name, ok, **ev): checks[name] = {'result': 'PASS' if ok else 'FAIL', 'evidence': ev}

# 1 counts / no clip dropped
src = {v['clip_id'] for v in cat['videos']}
ids = [m['clip_id'] for m in master]
chk('clip_count', len(ids) == len(set(ids)) == cat['summary']['source_video_clip_count'] and set(ids) == src,
    metadata=cat['summary']['source_video_clip_count'], master=len(ids), photos_excluded=cat['summary']['photo_count'])
chk('source_files_exist', all((ROOT / m['source_path']).exists() for m in master))
tot = sum(m['duration'] for m in master)
# 2 hero + strips
nofr = [m['clip_id'] for m in master if not (OUT / 'frames' / m['hero_frame']).exists()]
exp = lambda d: 0 if d < 4 else 1 if d < 15 else 3 if d < 60 else 5
badstrip = [m['clip_id'] for m in master if len(m['contact_strip']) != exp(m['duration']) or any(not (OUT / 'frames' / f['img']).exists() for f in m['contact_strip'])]
longs = [m for m in master if m['duration'] >= 60]
badseg = [m['clip_id'] for m in longs if not m['segments'] or any(not (OUT / 'frames' / s['img']).exists() for s in m['segments'])]
chk('hero_frames', not nofr, count=len(master) - len(nofr), missing=nofr[:5])
chk('contact_strips', not badstrip, bad=badstrip[:5], rule='<4s hero only; <15s hero(+mid); 15-60 hero+3; >=60 hero+5; content sample points preferred', contact_frames=sum(len(m['contact_strip']) for m in master))
chk('long_clip_segments', not badseg, long_clips=len(longs), bad=badseg[:5])
# 3 reasons
vague = [m['clip_id'] for m in master if len(m['ai_review']['reason']) < 60 or '綜合評分' not in m['ai_review']['reason']]
chk('ai_reason_specific', not vague, bad=vague[:5])
# 4 proxy
bad = [p['clip_id'] for p in man if not p.get('time_mapping_1to1')]
chk('proxy_time_mapping_1to1', len(man) == len(master) and not bad, proxies=len(man), bad=bad[:5], codecs=sorted({(p.get('vcodec'), p.get('acodec')) for p in man}, key=str))
# 5 zh-TW
html = (OUT / 'master_footage_review.html').read_text(encoding='utf-8')
fields = []
for m in master:
    fields += [m['visual_summary'], m['ai_review']['reason'], m['audio_summary'], *m['uncertainty_cues'], *m['visible_people'], *m['visible_animals'], *m['visual_objects'], *m['visual_actions']]
    fields += [e['summary'] + e['event_type_zh'] + e['location'] for e in m['events']] + [h['reason_zh'] + h['status_zh'] for h in m['hero_scenes']] + [s['activity_zh'] for s in m['segments']]
allow = re.compile(r'\b(D-Log2?|DJI|HC\d+|EV\d+|STRONG|fps|B-roll|VLM)\b')
eng = sorted({w for f in fields for w in re.findall(r'\b[a-z][A-Za-z]{2,}\b|\b(?:Agent|Hero|Scene|VLM|REJECTED|CONFIRMED)\b', allow.sub('', f or ''))})  # Capitalised/UPPER Latin = signage/brand original text, allowed
labels_ok = all(k in html for k in ['STRONG_CANDIDATE:\'強烈推薦\'', 'LIKELY_SKIP:\'可能略過\'', 'TECHNICAL_REJECT:\'技術不合格\'', 'NO_PREFERENCE:\'不指定是否選用\'', 'MUST_KEEP:\'必須保留\'', 'REPLACE:\'改寫摘要\'', 'HIGH:\'高\''])
shown_enum = re.findall(r'>\s*(STRONG_CANDIDATE|CANDIDATE|OPTIONAL|LIKELY_SKIP|TECHNICAL_REJECT|HIGH|MEDIUM|LOW|NOT_REVIEWED|NO_PREFERENCE|MUST_KEEP|MUST_REVIEW|IMPORTANT|SKIP|APPEND|CORRECT|REPLACE)\s*<', html)
chk('html_zh_TW', 'lang="zh-TW"' in html and 'charset="utf-8"' in html and labels_ok and not shown_enum and not eng,
    lang='zh-TW' in html, utf8=True, label_maps_present=labels_ok, raw_enum_shown=shown_enum, english_words_in_ai_text=eng[:30])
# 6 upstream untouched (mtime older than first Stage 0D output; hashes recorded)
t0 = min(p.stat().st_mtime for p in [OUT / 'proxy'] if p.exists())
ups = [p for d in ('stage0a_output', 'stage0b_output', 'stage0c_output') for p in (PO / d).glob('*.json') if not p.name.startswith('._')]
newer = [str(p.relative_to(PO)) for p in ups if p.stat().st_mtime > t0]
chk('stage0_untouched', not newer, files=len(ups), modified_after_0d_start=newer, sha256_sample={p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in ups if p.parent.name == 'stage0c_output'})
# 7 Stage 1 not required
chk('no_stage1_dependency', 'stage1_output' not in (ROOT / 'process/stage-0D-master-footage-review/scripts/d1_build.py').read_text(encoding='utf-8'))
# 8 persistence test on a temp copy of the console
def api(port, path, data=None):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=10))
tmp = Path(tempfile.mkdtemp(prefix='s0d_test_'))
for f in ('app.py', 'master_footage_review.json', 'master_footage_review.html'): shutil.copy(OUT / f, tmp / f)
port = 8791
def start(): 
    pr = subprocess.Popen([sys.executable, str(tmp / 'app.py')], env={**os.environ, 'STAGE0D_PORT': str(port)}, stdout=subprocess.DEVNULL)
    for _ in range(40):
        try: urllib.request.urlopen(f'http://127.0.0.1:{port}/api/cases', timeout=2); break
        except Exception: time.sleep(0.5)
    return pr
res = {}
try:
    pr = start()
    a, b, c = master[0], master[1], next(m for m in master if m['segments'])
    fb = lambda act, txt: {'action': act, 'text': txt, 'target_fields': ['visual_summary'], 'affects_selection': False, 'updated_at': 'T'}
    api(port, '/api/save', {'clip_id': a['clip_id'], 'status': 'NOT_REVIEWED', 'reason': '', 'summary_feedback': fb('APPEND', '補充：測試')})
    api(port, '/api/save', {'clip_id': b['clip_id'], 'status': 'MUST_KEEP', 'reason': '測試理由', 'summary_feedback': fb('NONE', '')})
    api(port, '/api/save', {'clip_id': c['clip_id'], 'status': 'NOT_REVIEWED', 'reason': '', 'segment_reviews': {c['segments'][0]['segment_id']: {'status': 'IMPORTANT', 'reason': '段落測試'}}, 'summary_feedback': fb('NONE', '')})
    api(port, '/api/case', {'clip_id': a['clip_id'], 'start': 1, 'end': 2, 'issue': '測試', 'expected': '測試'})
    pr.terminate(); pr.wait(); pr = start()
    d = {x['clip_id']: x for x in api(port, '/api/data')}
    res = {'summary_only_becomes_NO_PREFERENCE': d[a['clip_id']]['human_review']['status'] == 'NO_PREFERENCE' and d[a['clip_id']]['review_relationship'] == 'HUMAN_NO_PREFERENCE',
           'summary_and_status_independent': d[b['clip_id']]['human_review']['status'] == 'MUST_KEEP' and d[b['clip_id']]['human_review']['summary_feedback']['action'] == 'NONE',
           'summary_text_persisted_after_restart': d[a['clip_id']]['human_review']['summary_feedback']['text'] == '補充：測試',
           'summary_never_affects_selection': not d[a['clip_id']]['human_review']['summary_feedback']['affects_selection'],
           'ai_review_untouched': d[a['clip_id']]['ai_review'] == a['ai_review'] and 'recommendation' not in d[a['clip_id']]['human_review'],
           'segment_review_persisted': d[c['clip_id']]['human_review']['segment_reviews'][c['segments'][0]['segment_id']]['status'] == 'IMPORTANT',
           'case_saved': len(json.load(open(tmp / 'review_cases.json', encoding='utf-8'))) == 1,
           'master_json_merged_for_stage1': next(x for x in json.load(open(tmp / 'master_footage_review.json', encoding='utf-8')) if x['clip_id'] == b['clip_id'])['human_review']['status'] == 'MUST_KEEP',
           'all_clips_still_listed': len(d) == len(master)}
    r = urllib.request.Request(f'http://127.0.0.1:{port}/proxy/x', headers={'Range': 'bytes=0-9'})
    pr.terminate()
finally:
    try: pr.terminate()
    except Exception: pass
    shutil.rmtree(tmp, ignore_errors=True)
chk('human_review_persistence', bool(res) and all(res.values()), **res)
hp = OUT / 'human_footage_review.json'
real_clean = not hp.exists() or not any(t in hp.read_text(encoding='utf-8') for t in ('補充：測試', '測試理由', '段落測試'))
chk('real_human_review_not_polluted_by_test', real_clean)
# 9 seek mapping
bad = [m['clip_id'] for m in master for t in [m['hero_time']] + [f['ts'] for f in m['contact_strip']] + [s['ts'] for s in m['segments']] if not (0 <= t <= m['duration'])]
chk('frame_times_within_source_and_mapped_to_proxy', not bad, bad=bad[:5], note='frame ts is Original-Source seconds; proxy is 1:1 so player seeks to the same value')
overall = 'PASS' if all(c['result'] == 'PASS' for c in checks.values()) else 'FAIL'
rec = {}
for m in master: rec[m['ai_review']['recommendation']] = rec.get(m['ai_review']['recommendation'], 0) + 1
rep = {'stage': '0D', 'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'overall': overall,
       'headline': {'total_source_clips': len(src), 'master_review_clips': len(ids), 'total_runtime_s': round(tot, 1), 'hero_count': len(master) - len(nofr),
                    'long_clip_count': len(longs), 'contact_frames': sum(len(m['contact_strip']) for m in master), 'segment_frames': sum(len(m['segments']) for m in master),
                    'ai_recommendation': rec, 'proxy_count': len(man)},
       'checks': checks, 'example_kit': {'used': True, 'modified': ['app.py (path/Range/segment/cases/merge)', 'master_footage_review.html (player, filters, segments, cases)', 'build_stage0d.py replaced by scripts/d0-d4 (Stage 0B/0C schema; no Stage 1 input)']}}
json.dump(rep, open(OUT / 'master_footage_review_validation.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(overall, {k: v['result'] for k, v in checks.items()})
for k, v in checks.items():
    if v['result'] == 'FAIL': print(k, json.dumps(v['evidence'], ensure_ascii=False)[:400])
