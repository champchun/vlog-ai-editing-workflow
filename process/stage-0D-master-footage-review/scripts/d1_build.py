"""Stage 0D step 1: build master_footage_review.json (one card per Source Video Clip) + frame jobs.
Reads ONLY Stage 0A-0C formal outputs (Stage 1 data is never required). Does not modify upstream files."""
import json, os, sys, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PO = ROOT / 'process/workspace/project-output'
S0C, S0B, S0A = PO / 'stage0c_output', PO / 'stage0b_output', PO / 'stage0a_output'
OUT = PO / 'stage0d_master_review'
OUT.mkdir(parents=True, exist_ok=True)
L = lambda p: json.load(open(p, encoding='utf-8'))

val = L(S0C / 'stage0_validation_report.json')
assert val['overall'] in ('PASS', 'PASS_WITH_WARNINGS'), 'Stage 0 overall must PASS'
cat = L(S0C / 'metadata_catalog.json')['videos']
vis = {c['clip_id']: c for c in L(S0C / 'visual_summary.json')['clips']}
events = L(S0C / 'event_candidates.json')['events']
hero = L(S0C / 'hero_scene_candidates.json')
regions = L(S0B / 'ai_visual_review.json')
intra = {x['clip_id']: x for x in regions['intra_clip_segments']}
regs = defaultdict(list)
for r in regions['regions']:
    regs[r['clip_id']].append(r)
tr = L(S0A / 'transcript_sentences.json')
sent, sev = defaultdict(list), defaultdict(list)
for s in tr['sentences']:
    sent[s['clip_id']].append(s)
for s in tr['sound_events']:
    sev[s['clip_id']].append(s)

EVT_ZH = {'transition_or_incidental': '過場／零碎畫面', 'animal_observation': '觀察動物', 'play': '玩耍', 'transit': '移動／交通',
          'family_meal': '家人用餐', 'water_play': '玩水', 'exhibit_visit': '參觀展覽', 'sand_play': '玩沙', 'interactive_exhibit_play': '互動展品體驗',
          'family_interaction': '家人互動', 'scenery': '風景', 'shopping': '購物', 'animal_feeding': '餵食動物', 'boat_ride': '搭船', 'walk': '散步',
          'animal_show': '動物表演', 'snack_break': '點心休息', 'animal_interaction': '與動物互動', 'activity_preparation': '活動準備',
          'snorkel_guide_interaction': '浮潛教練互動', 'kid_portrait': '孩子特寫', 'airplane_watching': '看飛機'}
SIG_ZH = {'activity_cue': '活動跡象', 'animal': '動物', 'camera_turn': '鏡頭轉向', 'kids': '小孩', 'multi_person': '多人', 'scenic': '風景',
          'untranscribed_vocal_activity': '有未轉錄人聲'}
HS_ZH = {'CONFIRMED': '已複核確認（Stage 0B 候選，尚非 Stage 1 選用）', 'REJECTED': '已複核，未確認為精彩場景',
         'NEEDS_MORE_REVIEW': '仍待複核（需原音）', 'NOT_REVIEWED': '未複核（預算限制，僅有程式訊號提名）'}

# ---------- display normalisation (faithful zh-TW display; upstream files untouched) ----------
TERMS = [('Agent 複核', 'AI 助理複核'), ('Hero Scene', '精彩場景'), ('hero scene', '精彩場景'), ('B-roll', '輔助畫面'), ('B-Roll', '輔助畫面'),
         ('VLM', '視覺模型'), ('REJECTED', '未確認'), ('CONFIRMED', '已確認'), ('scenic', '風景'), ('Hero', '精彩場景')]
def zh(t):
    for a, b in TERMS: t = t.replace(a, b)
    return t
OBJ_ZH = {'aquarium': '水族箱', 'backpack': '背包', 'bedding': '寢具', 'bedroom': '臥室', 'bench': '長椅', 'bottle': '瓶子', 'cage': '籠子', 'camera': '相機',
          'container': '容器', 'conveyance': '交通工具', 'cord': '繩索', 'equp': '設備', 'eyeglasses': '眼鏡', 'fence': '圍欄', 'figurine': '人偶', 'fishtank': '魚缸',
          'furniture': '家具', 'helicopter': '直升機', 'housewares': '家用品', 'liquid': '液體', 'luggage': '行李', 'optical': '光學器材', 'outdoor': '戶外',
          'people': '人', 'pillow': '枕頭', 'plant': '植物', 'plate': '盤子', 'portal': '門口', 'rocks': '岩石', 'structure': '建築結構', 'table': '桌子',
          'tableware': '餐具', 'toy': '玩具', 'umbrella': '雨傘', 'use': '用品', 'utensil': '餐具', 'wood': '木頭', 'sunglasses': '太陽眼鏡', 'clownfish': '小丑魚',
          'cat': '貓', 'dog': '狗', 'bird': '鳥', 'fish': '魚', 'seal': '海豹', 'dolphin': '海豚'}
import re as _re
def split_objs(items):
    """generic labels -> zh; Capitalised/UPPERCASE Latin text = signage/brand original text kept apart (never translated or guessed)."""
    gen, sign = [], []
    for o in items:
        o = o.strip()
        if _re.fullmatch(r'[a-z ]+', o): gen.append(OBJ_ZH.get(o, o))
        elif _re.search(r'[A-Za-z]', o) and not _re.search(r'[\u4e00-\u9fff]', o): sign.append(o)
        else: gen.append(o)
    return gen, sign

# ---------- hero scene candidates per clip ----------
hs_by_clip = defaultdict(list)
for c in hero['candidates']:
    ar = c.get('agent_review') or {}
    st = ar.get('status', 'NOT_REVIEWED')
    s0, e0 = (ar.get('refined_start'), ar.get('refined_end')) if st == 'CONFIRMED' and ar.get('refined_start') is not None else (c['candidate_start'], c['candidate_end'])
    hs_by_clip[c['clip_id']].append({'candidate_id': c['candidate_id'], 'status': st, 'status_zh': HS_ZH.get(st, st), 'start': s0, 'end': e0,
        'reason_zh': zh((ar.get('decision_reason') or ar.get('visual_findings') or '、'.join(c.get('visual_evidence', [])[:2]))[:160]),
        'event_ids': c.get('event_ids', []), 'selected_in_stage1': False})
for c in hero['candidates_not_reviewed_budget']:
    hs_by_clip[c['clip_id']].append({'candidate_id': None, 'status': 'NOT_REVIEWED', 'status_zh': HS_ZH['NOT_REVIEWED'], 'start': c['start'], 'end': c['end'],
        'reason_zh': '程式訊號：' + '、'.join(SIG_ZH.get(x, x) for x in c.get('signals', [])), 'event_ids': [], 'selected_in_stage1': False})

# ---------- events per clip ----------
ev_by_clip = defaultdict(list)
for e in events:
    for sr in e['source_ranges']:
        ev_by_clip[sr['clip_id']].append((e, sr))
ev_nclips = {e['event_id']: len({sr['clip_id'] for sr in e['source_ranges']}) for e in events}

def ev_score(e):
    return (0.30 * e['story_value'] + 0.20 * e['emotional_value'] + 0.20 * e['interaction_value'] + 0.15 * e['visual_value'] + 0.15 * e['novelty'])

def fmt_t(s):
    s = float(s); return f'{int(s // 60)}:{s % 60:04.1f}' if s >= 60 else f'{s:.1f}秒'

def people_zh(vp):
    a, k = vp.get('max_adults', 0), vp.get('max_kids', 0)
    return [] if not (a or k) else [x for x in (f'最多同時 {a} 位大人' if a else '', f'最多同時 {k} 位小孩' if k else '') if x]

master, frame_jobs = [], []
for v in cat:
    cid, dur = v['clip_id'], v['duration']
    vc, rg = vis[cid], sorted(regs.get(cid, []), key=lambda r: r['start'])
    evs = ev_by_clip.get(cid, [])
    best = max(evs, key=lambda x: ev_score(x[0])) if evs else None
    hs = hs_by_clip.get(cid, [])
    conf = [h for h in hs if h['status'] == 'CONFIRMED']
    tech = v.get('technical_summary', {}) or {}
    usable = tech.get('usable_ratio')
    ss, ses = sent.get(cid, []), sev.get(cid, [])
    rel = [s for s in ss if s['transcript_status'] == 'reliable']
    unc = [s for s in ss if s['transcript_status'] != 'reliable']

    # ---- AI recommendation ----
    score = ev_score(best[0]) if best else 1.0
    notes_up, notes_down = [], []
    if conf:
        score += 1.0; notes_up.append(f"含已複核確認的精彩場景候選 {', '.join(h['candidate_id'] for h in conf)}（{fmt_t(conf[0]['start'])}–{fmt_t(conf[0]['end'])}）")
    if best and best[0]['event_type'] == 'transition_or_incidental':
        score -= 0.7; notes_down.append('事件類型屬過場／零碎畫面')
    if best and ev_nclips[best[0]['event_id']] >= 4:
        score -= 0.3; notes_down.append(f"同一事件共有 {ev_nclips[best[0]['event_id']]} 支素材，內容可能重複")
    if usable is not None and usable < 0.5:
        score -= 0.5; notes_down.append(f'技術可用比例僅 {usable:.0%}（晃動／模糊偏多）')
    if dur < 4:
        score -= 0.3; notes_down.append(f'片長僅 {dur:.1f} 秒')
    if rel:
        score += 0.2
    if v['hard_unusable']:
        rec, pri = 'TECHNICAL_REJECT', 'LOW'
    elif score >= 3.0:
        rec, pri = 'STRONG_CANDIDATE', 'HIGH'
    elif score >= 2.4:
        rec, pri = 'CANDIDATE', 'MEDIUM'
    elif score >= 1.8:
        rec, pri = 'OPTIONAL', 'LOW'
    else:
        rec, pri = 'LIKELY_SKIP', 'LOW'

    ev_txt = ''
    if best:
        e = best[0]
        ev_txt = (f"歸屬事件 {e['event_id']}（{EVT_ZH.get(e['event_type'], e['event_type'])}，{e['location']['name']}）：{zh(e['summary'])}"
                  f"［故事{e['story_value']}／情感{e['emotional_value']}／互動{e['interaction_value']}／畫面{e['visual_value']}／新鮮{e['novelty']}，滿分5］")
    else:
        ev_txt = '未歸入任何事件'
    cov = []
    if rel: cov.append(f'有 {len(rel)} 句可靠逐字稿')
    if ses: cov.append(f'{len(ses)} 段未轉錄人聲／環境聲需聆聽')
    if not cov: cov.append('幾乎無對話')
    tail = ('；加分：' + '；'.join(notes_up)) if notes_up else ''
    tail += ('；扣分：' + '；'.join(notes_down)) if notes_down else ''
    verdict = {'STRONG_CANDIDATE': '建議優先檢視', 'CANDIDATE': '建議認真考慮', 'OPTIONAL': '可作補充或 B-roll', 'LIKELY_SKIP': '建議可略過，但仍請人工確認', 'TECHNICAL_REJECT': '技術不合格'}[rec]
    reason = f"{verdict}。{ev_txt}。聲音：{'，'.join(cov)}{tail}。綜合評分 {score:.2f}。"

    # ---- visible info ----
    objs = []
    for r in rg:
        for o in (r.get('visual_objects') or {}).get('objects', []):
            if o not in objs: objs.append(o)
    acts = []
    for r in rg:
        for a in (r.get('visual_actions') or {}).get('subject_activities', []):
            if a not in acts and a != '無人': acts.append(a)
    animals = [OBJ_ZH.get(a.lower(), a) for a in ((vc.get('visual_animals') or {}).get('final_visual_label') or [])]
    objs, signage = split_objs(objs)
    acts = [zh(a) for a in acts]
    aud = f"可靠逐字稿 {len(rel)} 句、不確定 {len(unc)} 句、未轉錄人聲／環境聲 {len(ses)} 段"
    quotes = [f"[{fmt_t(s['start'])}] {s['text']}" for s in rel[:4]]
    cues = []
    if unc: cues.append(f'語音不確定：{len(unc)} 句辨識信心偏低，內容僅供參考')
    if ses: cues.append(f'有 {len(ses)} 段人聲／環境聲未轉錄，需實際聆聽')
    if any((r.get('action_coverage') or {}).get('action_process_seen') is None for r in rg) and dur >= 15:
        cues.append('視覺覆蓋缺口：僅單格抽樣，動作過程與結果未連續確認')
    if vc['visual_people'].get('max_adults') or vc['visual_people'].get('max_kids'):
        cues.append('人物身分未確認（僅有人數，未指認是誰）')
    if any('noise' in r['quality'].get('vlm_issues', {}) for r in rg): cues.append('畫質警告：疑似有雜訊')
    if any('overexposed' in r['quality'].get('vlm_issues', {}) for r in rg): cues.append('畫質警告：疑似過曝')
    if usable is not None and usable < 0.7: cues.append(f'畫質警告：技術可用比例 {usable:.0%}')

    # ---- hero frame + contact strip (content-based, Original Source) ----
    cand = sorted({round(t, 2) for r in rg for t in r.get('sample_times', []) if 0 <= t <= dur})
    if conf: hero_t = (conf[0]['start'] + conf[0]['end']) / 2
    elif best: hero_t = (best[1]['start'] + best[1]['end']) / 2
    else: hero_t = dur / 2
    if cand: hero_t = min(cand, key=lambda t: abs(t - hero_t)) if not conf else hero_t
    hero_t = 0.0 if dur < 0.5 else min(max(hero_t, 0.1), max(dur - 0.2, 0.1))
    n = 1 if dur < 15 else 3 if dur < 60 else 5
    pcts = {1: [0.5], 3: [0.25, 0.5, 0.75], 5: [0.1, 0.3, 0.5, 0.7, 0.9]}[n]
    if len(cand) >= n and dur >= 15:
        idx = [round(i * (len(cand) - 1) / (n - 1)) for i in range(n)] if n > 1 else [0]
        times, basis = [cand[i] for i in idx], 'content_sample_points'
    else:
        times, basis = [dur * p for p in pcts], 'percentage_fallback'
    if dur < 15: times = [] if dur < 4 else [dur * 0.5]; basis = 'short_clip'
    strip = [{'img': f'{cid}_c{i}.jpg', 'ts': round(t, 2)} for i, t in enumerate(times)]
    frame_jobs.append({'clip_id': cid, 'src': v['source_path'], 'ts': round(hero_t, 3), 'out': f'{cid}_hero.jpg'})
    frame_jobs += [{'clip_id': cid, 'src': v['source_path'], 'ts': s['ts'], 'out': s['img']} for s in strip]

    segs = []
    if dur >= 60:
        for i, sg in enumerate((intra.get(cid) or {}).get('segments') or [{'segment_id': f'{cid}#S01', 'start': 0, 'end': dur, 'activity_zh': '整支（未分段）'}]):
            mid = min(max((sg['start'] + sg['end']) / 2, 0.1), dur - 0.2)
            segs.append({'segment_id': sg['segment_id'], 'start': sg['start'], 'end': sg['end'], 'activity_zh': sg.get('activity_zh', ''), 'img': f'{cid}_s{i}.jpg', 'ts': round(mid, 2)})
            frame_jobs.append({'clip_id': cid, 'src': v['source_path'], 'ts': round(mid, 3), 'out': f'{cid}_s{i}.jpg'})

    master.append({
        'clip_id': cid, 'filename': v['filename'], 'source_path': v['source_path'], 'media_type': 'video',
        'creation_time_utc': v['creation_time_utc'], 'local_time': v['camera_local_time_from_filename'], 'tz_offset': v['derived_tz_offset'],
        'duration': dur, 'resolution': f"{v['resolution']['width']}x{v['resolution']['height']}", 'fps': v['fps'], 'codec': v['codec'], 'color_profile': v['color_profile'],
        'hero_frame': f'{cid}_hero.jpg', 'hero_time': round(hero_t, 2), 'contact_strip': strip, 'contact_basis': basis, 'segments': segs,
        'play_url': f'proxy/{cid}.mp4',
        'visual_summary': zh(vc['visual_summary']), 'visible_people': people_zh(vc['visual_people']) + [a for a in vc['visual_people'].get('activities', []) if a != '無人'],
        'visible_animals': animals, 'visual_objects': objs, 'signage_text_original': signage, 'visual_actions': acts,
        'audio_summary': aud, 'transcript_quotes': quotes, 'uncertainty_cues': cues,
        'events': [{'event_id': e['event_id'], 'event_type': e['event_type'], 'event_type_zh': EVT_ZH.get(e['event_type'], e['event_type']), 'summary': zh(e['summary']),
                    'location': e['location']['name'], 'reaction': e.get('reaction', ''), 'start': sr['start'], 'end': sr['end']} for e, sr in evs],
        'event_ids': [e['event_id'] for e, _ in evs], 'has_reaction': any((e.get('reaction') or '未見') not in ('未見', '無', '') for e, _ in evs), 'hero_scenes': hs,
        'ai_suggested_regions': [{'start': s['start'], 'end': s['end'], 'label': s['activity_zh']} for s in segs],
        'technical': {'usable_ratio': usable, 'issue_ratios': tech.get('issue_ratios'), 'hard_unusable': v['hard_unusable']},
        'ai_review': {'recommendation': rec, 'priority': pri, 'reason': reason, 'score': round(score, 2)},
        'human_review': {'status': 'NOT_REVIEWED', 'reason': '', 'segment_reviews': {},
                         'summary_feedback': {'action': 'NONE', 'text': '', 'target_fields': [], 'affects_selection': False, 'updated_at': None}},
        'review_relationship': 'HUMAN_NOT_REVIEWED'})

json.dump(master, open(OUT / 'master_footage_review.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(frame_jobs, open(OUT / 'frame_jobs.json', 'w'), ensure_ascii=False)
from collections import Counter
print(len(master), 'clips;', len(frame_jobs), 'frames;', Counter(m['ai_review']['recommendation'] for m in master))
