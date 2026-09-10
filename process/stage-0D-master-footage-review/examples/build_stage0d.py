import json
import os
import subprocess
import shutil

out_dir = 'stage0d_master_review'
frames_dir = os.path.join(out_dir, 'frames')
proxy_dir = os.path.join(out_dir, 'proxy')
kit_dir = os.path.dirname(os.path.abspath(__file__))

os.makedirs(frames_dir, exist_ok=True)
os.makedirs(proxy_dir, exist_ok=True)

# 1. Load Data
try:
    with open('stage0c_output/metadata_catalog.json', 'r') as f:
        catalog = json.load(f)
    with open('stage0c_output/visual_summary.json', 'r') as f:
        vis_data = json.load(f)
    with open('stage0c_output/event_candidates.json', 'r') as f:
        events_data = json.load(f)
except FileNotFoundError as e:
    print(f"Error: 找不到 Stage 0 輸出檔案。請確保已完成 Stage 0A~0C。({e})")
    exit(1)
    
try:
    with open('stage1_output/edit_decisions_v11.json', 'r') as f:
        stage1_decisions = json.load(f)
        stage1_clips = set(s['filename'] for s in stage1_decisions)
except:
    stage1_clips = set() # Optional fallback if stage1 not done yet

# Map vis_data to clips
vis_by_clip = {}
for v in vis_data:
    cid = v['clip_id']
    if cid not in vis_by_clip:
        vis_by_clip[cid] = []
    vis_by_clip[cid].append(v)

# Map events to clips
events_by_clip = {}
for e in events_data:
    for cid in e['source_clips']:
        if cid not in events_by_clip:
            events_by_clip[cid] = []
        events_by_clip[cid].append(e['event_id'])

# 2. Build Master Clips
master_clips = []
extract_jobs = []
proxy_jobs = []

for c in catalog:
    cid = c['clip_id']
    dur = c['duration']
    fname = c['filename']
    src = c['absolute_path']
    
    mc = {
        "clip_id": cid,
        "filename": fname,
        "source_path": src,
        "duration": dur,
        "hero_frame": f"{cid}_hero.jpg",
        "contact_strip": [],
        "visual_summary": "",
        "audio_summary": "",
        "event_ids": events_by_clip.get(cid, []),
        "ai_suggested_regions": [],
        "visible_people": [],
        "visible_animals": [],
        "visual_objects": [],
        "visual_actions": []
    }
    
    vis_segments = vis_by_clip.get(cid, [])
    
    ai_score = 0
    if vis_segments:
        mc['visual_summary'] = vis_segments[0].get('visual_summary', '')
        
        for vs in vis_segments:
            mc['visible_people'].extend(vs.get('visible_people', []))
            mc['visible_animals'].extend(vs.get('visual_animals', []))
            mc['visual_objects'].extend(vs.get('visual_objects', []))
            mc['visual_actions'].extend(vs.get('visual_actions', []))
            if vs.get('aligned_transcript_sentences'):
                mc['audio_summary'] += " ".join(vs['aligned_transcript_sentences']) + " "
                
            m_score = max(vs.get('visual_value', 0), vs.get('interaction_value', 0), vs.get('reaction_value', 0), vs.get('novelty_value', 0))
            ai_score = max(ai_score, m_score)
            
            if len(vis_segments) > 1:
                mc['ai_suggested_regions'].append({
                    "start": vs['segment_start'],
                    "end": vs['segment_end'],
                    "label": (vs.get('visual_actions') or ['segment'])[0]
                })

    mc['visible_people'] = list(set(mc['visible_people']))
    mc['visible_animals'] = list(set(mc['visible_animals']))
    mc['visual_objects'] = list(set(mc['visual_objects']))
    mc['visual_actions'] = list(set(mc['visual_actions']))
    
    rec = "LIKELY_SKIP"
    pri = "LOW"
    reason = "Low interaction/visual values. No strong events detected."
    if ai_score > 0.8 or mc['event_ids']:
        rec = "STRONG_CANDIDATE"
        pri = "HIGH"
        reason = "High visual/reaction value or part of a major event. Strong candidate for selection."
    elif ai_score > 0.6:
        rec = "CANDIDATE"
        pri = "MEDIUM"
        reason = "Good visual elements detected. Could serve as coverage."
    elif ai_score > 0.4:
        rec = "OPTIONAL"
        pri = "LOW"
        reason = "Average visual value. Might be useful as B-roll if needed."
        
    mc['ai_review'] = {
        "recommendation": rec,
        "priority": pri,
        "reason": reason
    }
    
    mc['human_review'] = {
        "status": "NOT_REVIEWED",
        "reason": ""
    }
    mc['review_relationship'] = "HUMAN_NOT_REVIEWED"
    
    extract_jobs.append({'src': src, 'ts': dur*0.5, 'out': mc['hero_frame']})
    
    if dur >= 60:
        pcts = [0.1, 0.3, 0.5, 0.7, 0.9]
    elif dur >= 15:
        pcts = [0.25, 0.5, 0.75]
    else:
        pcts = []
        
    for i, p in enumerate(pcts):
        strip_name = f"{cid}_{int(p*100)}.jpg"
        mc['contact_strip'].append({"img": strip_name, "ts": dur*p})
        extract_jobs.append({'src': src, 'ts': dur*p, 'out': strip_name})
        
    if fname in stage1_clips:
        proxy_name = f"{cid}_proxy.mp4"
        proxy_path = os.path.join(proxy_dir, proxy_name)
        mc['play_url'] = f"proxy/{proxy_name}"
        if not os.path.exists(proxy_path):
            proxy_jobs.append({'src': src, 'dur': dur, 'out': proxy_path})
    else:
        mc['play_url'] = "original" 
        
    master_clips.append(mc)

# 3. Execution FFmpeg
print(f"Extracting {len(extract_jobs)} frames (this will take a few minutes)...")
for job in extract_jobs:
    out_p = os.path.join(frames_dir, job['out'])
    if not os.path.exists(out_p):
        cmd = ['ffmpeg', '-y', '-ss', str(job['ts']), '-i', job['src'], '-vframes', '1', '-q:v', '5', '-vf', 'scale=640:-1', out_p]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print(f"Generating {len(proxy_jobs)} proxies...")
for job in proxy_jobs:
    cmd = [
        'ffmpeg', '-y', '-i', job['src'],
        '-vf', 'scale=1280:720,format=yuv420p', '-c:v', 'h264_videotoolbox', '-b:v', '2M',
        '-c:a', 'aac', '-b:a', '128k', job['out']
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 4. Generate master JSON
with open(os.path.join(out_dir, 'master_footage_review.json'), 'w') as f:
    json.dump(master_clips, f, indent=2, ensure_ascii=False)

# 5. Copy HTML (Do NOT copy app.py since it should run from the root/kit location)
shutil.copy(os.path.join(kit_dir, 'master_footage_review.html'), os.path.join(out_dir, 'master_footage_review.html'))

print("Stage 0D Backend Processing Complete!")
