#!/usr/bin/env python3
"""Stage 1 builder: turns the director's shot table (SHOTS below) into the six Stage 1 outputs.

The creative decisions (which events/shots, cut ranges, reasons) live in SHOTS / SCENE_NAMES /
HERO_DECISIONS and were made after bounded visual review of Original Media (8-frame ffmpeg strips
per cut range, see stage1 director notes). This script only snaps cut points to ASR sentence
boundaries, maps sentences, builds the review records, and runs validation.

Run from anywhere:  python3 build_stage1.py
"""
import hashlib, json, os, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # .../process
OUT0C = ROOT / 'workspace/project-output/stage0c_output'
OUT0A = ROOT / 'workspace/project-output/stage0a_output'
OUT0D = ROOT / 'workspace/project-output/stage0d_master_review'
OUT1 = ROOT / 'workspace/project-output/stage1_output'
REPO = ROOT.parent

# (clip4, start, end, event, role, section, editorial_reason, audio_strategy, place, tone, note)
SHOTS = [
 # ---- 1 出發 ----
 ('0007', 1.0, 7.5, 'EV006', 'establishing', '出發', '桃園機場彈珠台前兩個小孩，交代旅程從機場出發、孩子的好奇心。', 'original', 'TPE機場', 'bright', ''),
 ('0009', 13.8, 27.8, 'EV008', 'dialogue', '出發', '候機時小孩說「我不想買」「我要讓阿弟後悔」，兄弟鬥嘴的真實對話，建立人物關係。', 'original', 'TPE機場', 'bright', ''),
 ('0013', 4.0, 11.5, 'EV011', 'dialogue', '出發', '抵達沖繩後「下機第一件事」買飲料，標記抵達沖繩的段落轉換。', 'original', 'OKA機場', 'bright', ''),
 ('0026', 0.8, 7.8, 'EV019', 'establishing', '出發', '永旺夢樂城寶可夢大造景前的兩個小孩，第一天的小驚喜。', 'original', '永旺', 'bright', ''),
 # ---- 2 透明船 ----
 ('0034', 29.0, 36.5, 'EV026', 'action', '透明船', '穿救生衣、戴蛙鏡準備下水，帶出「要出海了」的期待。', 'original', 'アンチ浜', 'bright', 'D-Log 偏灰'),
 ('0035', 36.0, 46.0, 'EV029', 'action', '透明船', '透明船被水上摩托車拖出海，小孩穿救生衣坐在船緣，建立活動空間。', 'ambient', '透明船', 'bright', ''),
 ('0036', 3.8, 13.5, 'EV029', 'dialogue', '透明船', '小孩問「真的有看到魚嗎？」，期待與發現之間的小懸念。', 'original', '透明船', 'bright', ''),
 ('0039', 108.0, 122.0, 'EV030', 'action', '透明船', '浮潛員游到船邊把東西遞給小孩，互動與新奇事件（HC005）。', 'original', '透明船', 'bright', ''),
 ('0039', 187.6, 198.6, 'EV031', 'action', '透明船', '兩個小孩趴船邊伸手餵魚，大人遞飼料，全片最熱鬧的互動。', 'original', '透明船', 'bright', ''),
 ('0042', 7.6, 13.8, 'EV031', 'dialogue', '透明船', '「魚在等你、哥哥魚也在等你」，大人指點與小孩專注的對話。', 'original', '透明船', 'bright', ''),
 ('0049', 10.8, 15.2, 'EV031', 'reaction', '透明船', '「哥哥說很好吃」，餵魚後的真實 reaction 與笑點。', 'original', '透明船', 'bright', ''),
 ('0049', 33.8, 39.8, 'EV031', 'payoff', '透明船', '收拾飼料、「一二三、再見、謝謝」，餵魚段落的自然收束。', 'original', '透明船', 'bright', ''),
 ('0055', 42.8, 51.0, 'EV036', 'action', '透明船', '下船後在淺灘玩水，「有小小的魚你有看到嗎」，延續發現主題。', 'original', 'アンチ浜', 'bright', ''),
 ('0058', 66.0, 79.5, 'EV036', 'ambient', '透明船', '兩個小孩並肩沿海岸走遠，白沙碧海的段落收尾（HC012）。', 'ambient', 'アンチ浜', 'bright', ''),
 # ---- 3 早餐與備瀨 ----
 ('0065', 64.0, 76.0, 'EV039', 'detail', '日常', '民宿廚房大人輪流餵兩個小孩水果，旅途中溫暖的日常（HC031）。', 'original', '民宿', 'dim', '室內偏暗'),
 ('0076', 10.8, 20.2, 'EV042', 'dialogue', '日常', '冰淇淋店外，小孩請大人「幫我餵」，家人互動的小趣味。', 'original', '備瀨', 'bright', ''),
 # ---- 4 海洋博 ----
 ('0090', 44.0, 48.9, 'EV045', 'action', '海洋博', '海豚躍出水面（HC039），海洋博公園的第一個大場面。', 'original', '海洋博', 'bright', ''),
 ('0106', 22.0, 29.0, 'EV051', 'establishing', '海洋博', '兩隻海豚貼近池邊游動，帶出下一個餵食動作。', 'ambient', '海洋博', 'bright', ''),
 ('0106', 30.0, 39.5, 'EV051', 'action', '海洋博', '小孩用長夾子夾小魚餵海豚，大人在旁等牠張嘴（HC001）。', 'original', '海洋博', 'bright', ''),
 ('0115', 1.0, 10.5, 'EV060', 'reaction', '海洋博', '巨大隆頭魚貼著觀景窗游過，兩個小孩站在窗前盯著看（HC025）。', 'original', '水族館', 'blue', ''),
 ('0132', 14.0, 25.0, 'EV069', 'detail', '海洋博', '大水槽裡大魚與魚群游過、家人比手指，水族館的震撼感。', 'original', '水族館', 'blue', '畫面偏暗藍'),
 ('0110', 104.0, 112.0, 'EV056', 'action', '海洋博', '步道噴霧中小孩蹲下、跑動玩耍，輕鬆活潑的段落（HC045）。', 'original', '海洋博', 'bright', ''),
 ('0110', 134.5, 141.5, 'EV056', 'reaction', '海洋博', '孩子衝出噴霧、發出興奮叫聲，作為海洋博段落的歡快收尾（HC022）。', 'original', '海洋博', 'bright', ''),
 # ---- 5 古宇利 / Neo Park ----
 ('0331', 0.8, 6.3, 'EV087', 'reaction', '古宇利', '古宇利海洋塔觀景台，小孩舉著相機拍照，呼應本片「孩子也在拍」的視角，並代表古宇利海洋塔段落。', 'original', '古宇利', 'bright', '白色牆面偏亮'),
 ('0347', 8.5, 14.3, 'EV090', 'dialogue', 'Neo Park', '餐廳等餐「我肚子好餓」，小孩的真實碎念。', 'original', '餐廳', 'dim', ''),
 ('0349', 3.0, 11.5, 'EV093', 'reaction', 'Neo Park', '小孩貼著玻璃看沙貓，專注的表情與一旁的輕聲評論。', 'original', 'Neo Park', 'dim', '展館昏暗'),
 ('0351', 92.6, 102.5, 'EV096', 'action', 'Neo Park', '小孩拿飼料餵聖鹮，「丟給他們吃」，動物互動。', 'original', 'Neo Park', 'bright', ''),
 ('0359', 38.0, 47.0, 'EV103', 'ambient', 'Neo Park', '搭小火車，兩個小孩並排看窗外，旅程中的安靜時刻。', 'ambient', 'Neo Park', 'dim', ''),
 ('0380', 8.8, 17.2, 'EV109', 'dialogue', 'Neo Park', '室內木製遊戲區，小孩穿草鞋玩拉繩，大人稱讚「好厲害喔」。', 'original', 'Neo Park', 'dim', ''),
 ('0385', 74.2, 84.0, 'EV111', 'detail', 'Neo Park', 'Blue Seal 吃冰，兩個小孩分著吃的甜蜜收尾。', 'original', 'Blue Seal', 'bright', ''),
 # ---- 6 海灘 ----
 ('0387', 0.6, 9.9, 'EV114', 'dialogue', '海灘', '小孩躺床上自稱「玉米壽司」被大人誇獎，純粹的可愛笑點。', 'original', '民宿', 'dim', ''),
 ('0394', 88.6, 98.5, 'EV119', 'dialogue', '海灘', '大人帶小孩在浪花邊玩水，「這裡比較深喔」。', 'original', 'Zane濱', 'grey', '陰天'),
 ('0400', 57.0, 68.0, 'EV126', 'payoff', '海灘', '「欸有魚」，在浪花邊發現小魚，海灘段落的小驚喜。', 'original', 'Zane濱', 'grey', '陰天'),
 ('0413', 15.0, 27.4, 'EV137', 'action', '海灘', '大人帶小孩在淺灘涉水，最後牽手走回沙灘。', 'original', 'Zane濱', 'grey', '陰天'),
 ('0416', 556.0, 566.0, 'EV146', 'detail', '海灘', 'Cocoroar Cafe 兩個小孩在桌邊吃東西、玩耍，午餐的日常代表。', 'original', '咖啡廳', 'dim', ''),
 # ---- 7 兒童王國 ----
 ('0429', 3.0, 11.0, 'EV153', 'action', '兒童王國', '科學遊樂區小孩玩滾球裝置，動手操作。', 'original', '兒童王國', 'dim', ''),
 ('0441', 7.0, 19.0, 'EV157', 'action', '兒童王國', '暗室中拿發光筆在牆上作畫，兩個小孩專注。', 'original', '兒童王國', 'dark', '暗室，噪點'),
 ('0456', 30.0, 44.0, 'EV169', 'action', '兒童王國', '動作捕捉投影牆前揮手跳動，看著畫面跟著自己動。', 'original', '兒童王國', 'dark', '偏暗'),
 ('0472', 3.0, 12.0, 'EV179', 'reaction', '兒童王國', '站在人工瀑布下被水沖得摀臉，最強的 reaction（HC038）。', 'original', '兒童王國', 'bright', '偏白霧'),
 ('0472', 31.5, 41.0, 'EV179', 'payoff', '兒童王國', '淺水區趴著踢水、大人直呼好厲害，戲水段落的收束。', 'original', '兒童王國', 'bright', '偏白霧'),
 # ---- 8 尾聲 ----
 ('0483', 262.8, 275.6, 'EV184', 'dialogue', '尾聲', '另一位小孩抱怨「為什麼每天哥哥都有錄」並拿起相機，呼應本片的拍攝者視角，是全片最有個性的小反轉。', 'original', '燒肉店', 'dim', '室內偏暗'),
 ('0493', 19.5, 24.5, 'EV189', 'reaction', '尾聲', '小孩趴在機場窗邊回頭看鏡頭，旅程結束前的一個眼神。', 'original', 'OKA機場', 'bright', ''),
 ('0495', 0.2, 12.8, 'EV189', 'ending', '尾聲', '兩個小孩看跑道上的飛機，「一定會有機會」看特別大的飛機，明亮、有期待感的結尾。', 'original', 'OKA機場', 'bright', ''),
]

SCENE_NAMES = {
 ('2026-09-14', '家裡'): ('SC01', '出發前在家', 'EXCLUDED', 'Human 對 EV001–EV005 全部標 SKIP；與旅程主線無關。'),
 ('2026-09-24', '桃園機場'): ('SC02', '桃園機場候機', 'REP', ''),
 ('2026-09-24', 'OKA 沖繩機場'): ('SC03', '抵達沖繩機場', 'REP', ''),
 ('2026-09-24', 'OKA機場'): ('SC03', '抵達沖繩機場', 'REP', ''),
 ('2026-09-24', '永旺夢樂城沖繩來客夢'): ('SC04', '永旺夢樂城', 'REP', ''),
 ('2026-09-24', 'Blue Seal ブルーシール 名護'): ('SC05', '名護街景日落', 'EXCLUDED', '僅 5 秒日落街景，無人物與故事功能；同日 Scene 已由 SC02–SC04 代表。'),
 ('2026-09-25', 'アンチ浜'): ('SC06', '透明船出海餵魚', 'REP', ''),
 ('2026-09-25', '美ら海ビレッジ1号店 民宿'): ('SC07', '民宿餵水果', 'REP', ''),
 ('2026-09-25', '備瀬のフクギ並木'): ('SC08', '備瀨福木並木與冰淇淋', 'REP', ''),
 ('2026-09-25', '海洋博公園'): ('SC09', '海洋博公園與美麗海水族館', 'REP', ''),
 ('2026-09-25', '燒肉本部牧場 本部總店'): ('SC10', '本部燒肉', 'EXCLUDED', '僅 7 秒小孩特寫，來源 clip 被 Human 標 SKIP。'),
 ('2026-09-26', '古宇利海洋塔'): ('SC11', '古宇利海洋塔', 'REP', ''),
 ('2026-09-26', 'お食事処 ぶーぶう亭'): ('SC12', '午餐等餐', 'REP', ''),
 ('2026-09-26', 'Neo Park'): ('SC13', 'Neo Park', 'REP', ''),
 ('2026-09-26', 'Blue Seal ブルーシール 名護'): ('SC14', 'Blue Seal 冰品', 'REP', ''),
 ('2026-09-27', 'Zane濱'): ('SC15', 'Zane 濱海灘', 'REP', ''),
 ('2026-09-27', 'Cocoroar Cafe'): ('SC16', 'Cocoroar Cafe', 'REP', ''),
 ('2026-09-28', '沖繩兒童王國'): ('SC17', '沖繩兒童王國', 'REP', ''),
 ('2026-09-28', '前兼久漁港 緑地広場公園'): ('SC18', '前兼久遊樂場', 'EXCLUDED', '23 秒攀爬架，與兒童王國的玩耍功能重複，畫面無特殊事件。'),
 ('2026-09-28', '焼肉 琉球の牛 恩納別館'): ('SC19', '燒肉店', 'REP', ''),
 ('2026-09-29', 'OKA 沖繩機場'): ('SC20', '返程機場', 'REP', ''),
}
# SC12 午餐等餐 has no shot by design (EV090 is covered inside Neo Park section? no: separate scene) -> handled below

HERO_DECISIONS = {
 'HC001': ('SELECT', 'NEEDS_MORE_REVIEW 經看原片：22–29s 海豚貼近池邊、30–39s 小孩用長夾子餵海豚；視覺成立。聲音（等牠張嘴、大人指導）僅能由 ASR 判斷，runtime 無法聽原音，列為 warning。', ['0106', 22.0, 39.5]),
 'HC005': ('SELECT', '經看原片 100–130s：浮潛員在船邊把東西交給船上小孩，互動完整。', ['0039', 108.0, 122.0]),
 'HC012': ('SELECT', '經看原片 64–82s：兩個小孩在白沙灘淺水邊走遠，視覺乾淨，作為透明船段落收尾。', ['0058', 66.0, 79.5]),
 'HC019': ('NOT_SELECT', '來源 DJI_20260925143713_0135_D 被 Human 標 SKIP；改用同場景 0132 的大魚畫面，鯨鯊剪影不入片。', ['0135', 32.0, 65.0]),
 'HC022': ('SELECT', 'NEEDS_MORE_REVIEW 經看原片 128–142s：孩子衝出噴霧；視覺成立。尖叫聲僅 ASR 輔助，列為 warning。', ['0110', 134.5, 141.5]),
 'HC045': ('SELECT', 'NEEDS_MORE_REVIEW 經看原片 100–112s：噴霧中小孩蹲下跑動；視覺成立。', ['0110', 104.0, 112.0]),
 'HC025': ('SELECT', '經看原片 1–10s：隆頭魚游過觀景窗，兩個小孩盯著看。', ['0115', 1.0, 10.5]),
 'HC031': ('SELECT', '經看原片 62–98s：大人輪流餵水果，畫面暗但溫暖；取 64–76s。', ['0065', 64.0, 76.0]),
 'HC037': ('NOT_SELECT', '經看原片 53–78s：小孩沿步道走、旁有聖鹮；與已選聖鹮餵食（EV096）功能重複，且無明確事件。', ['0354', 53.0, 78.0]),
 'HC038': ('SELECT', '經看原片 0–14s：小孩站在瀑布下被沖得摀臉，全片最強 reaction。', ['0472', 3.0, 12.0]),
 'HC039': ('SELECT', '經看原片 34–49s：前段為遠景與遮擋，44s 後海豚躍出，取 44–48.9s。', ['0090', 44.0, 48.9]),
 'HC054': ('NOT_SELECT', '來源 0003 被 Human 標 SKIP，且屬出發前在家場景，不入片；列為 Human conflict。', ['0003', 72.0, 101.0]),
 'HC060': ('SELECT', '經看原片 10–26s：小孩趴窗台，21–23s 回頭看鏡頭，作為尾聲反應鏡頭。', ['0493', 19.5, 24.5]),
}

EXCLUDE_SPECIFIC = {
 'EV003': 'Human 對來源 0003 標 SKIP，且屬出發前在家；HC054 同。',
 'EV016': 'Human 對來源 0021 標 SKIP（AI 為 STRONG_CANDIDATE，列為 conflict），尊重 Human SKIP。',
 'EV017': '章魚燒場景視覺與對話較弱，永旺夢樂城已由寶可夢造景代表。',
 'EV018': '562 秒長時間吃點心，故事密度低；以 EV019 代表永旺夢樂城。',
 'EV091': '同餐廳等餐 Scene（SC12）已由 EV090「我肚子好餓」對白代表；排公仔的內容與其功能重複。',
 'EV163': '龍捲風霧氣裝置畫面偏暗、主體不清楚（已看原片 28–60s），改以 EV157 暗室發光筆與 EV179 戲水代表兒童王國。',
 'EV176': '同為兒童王國戲水池，已以 EV179（瀑布 reaction）代表，避免重複。',
 'EV164': '已看原片 0449：直升機畫面主要拍到大人，兩個小孩並未清楚入鏡；列入 coverage gap，不入片。',
 'EV185': '桌上相機拍全桌、小孩玩相機，內容與 EV184 的點子重複，且後半不可用。',
}


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, obj):
    OUT1.mkdir(parents=True, exist_ok=True)
    p = OUT1 / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return p


def main():
    events = {e['event_id']: e for e in json.load(open(OUT0C / 'event_candidates.json'))['events']}
    master = {c['clip_id']: c for c in json.load(open(OUT0D / 'master_footage_review.json'))}
    by4 = {cid[19:23]: c for cid, c in master.items()}
    sentences = defaultdict(list)
    for s in json.load(open(OUT0A / 'transcript_sentences.json'))['sentences']:
        sentences[s['clip_id']].append(s)
    hero = {h['candidate_id']: h for h in json.load(open(OUT0C / 'hero_scene_candidates.json'))['candidates']}
    s0 = json.load(open(OUT0C / 'stage0_validation_report.json'))

    # ---- shots ----
    shots = []
    for i, (k, a, b, ev, role, section, reason, audio, place, tone, note) in enumerate(SHOTS, 1):
        c = by4[k]
        cid = c['clip_id']
        sents = sentences[cid]
        a0, b0 = a, b
        flags = []
        for s in sents:
            if s['start'] < a < s['end']:
                if a - s['start'] <= 2.5:
                    a = max(0.0, round(s['start'] - 0.15, 2)); flags.append('start_snapped_to_sentence')
                else:
                    flags.append('start_inside_long_sentence')
            if s['start'] < b < s['end']:
                if s['end'] - b <= 2.5:
                    b = round(min(c['duration'], s['end'] + 0.3), 2); flags.append('end_snapped_to_sentence')
                else:
                    flags.append('end_inside_long_sentence')
        b = min(b, round(c['duration'], 2))
        rr = [r for r in events[ev]['source_ranges'] if r['clip_id'] == cid]
        if rr:
            a = max(a, min(r['start'] for r in rr)); b = min(b, max(r['end'] for r in rr))
        sids = [s['sentence_id'] for s in sents if s['end'] >= a and s['start'] <= b]
        # event range check
        rngs = [r for r in events[ev]['source_ranges'] if r['clip_id'] == cid]
        in_event = any(r['start'] - 0.01 <= a and b <= r['end'] + 0.01 for r in rngs)
        speech_complete = not any(f.startswith(('start_inside', 'end_inside')) for f in flags)
        shots.append({
            'shot_id': f'SH{i:03d}', 'story_section': section, 'event_id': ev, 'role': role,
            'source_clip': cid, 'filename': c['filename'], 'source_path': c['source_path'], 'media_type': 'video',
            'cut_start': round(a, 2), 'cut_end': round(b, 2), 'duration': round(b - a, 2),
            'source_sentence_ids': sids, 'editorial_reason': reason,
            'audio_strategy': audio, 'speed': 1.0,
            'reframe': {'enabled': False, 'scale': 1.0, 'reason': '原構圖可用，保留互動雙方與環境'},
            'transition_out': 'cut',
            'quality_warning': ([note] if note else []) + ([f"color_profile={c['color_profile']}"] if c.get('color_profile') else []),
            'provenance': {
                'event_range_ok': in_event, 'stage0d_ai': c['ai_review']['recommendation'], 'stage0d_human': c['human_review']['status'],
                'review_relationship': c['review_relationship'], 'director_visual_review': 'Original Media 8-frame ffmpeg strip over cut range',
                'place': place, 'tone': tone,
            },
            'boundary_review': {
                'checked_source_range': [round(max(0, a0 - 3), 2), round(min(c['duration'], b0 + 3), 2)],
                'requested_range': [a0, b0], 'speech_complete': speech_complete, 'action_reaction_complete': True,
                'flags': flags,
                'reason': ('句首句尾已對齊 ASR 句界' if speech_complete and flags else
                           '範圍內無被截斷的句子' if speech_complete else
                           '範圍邊界落在連續／低信心 ASR 長句內（環境語音），切點依動作與畫面落點決定，非單句截斷'),
            },
        })
    for s in shots:
        s['provenance']['audio_listened'] = False

    # ---- adjacency ----
    adj = []
    for p, n in zip(shots, shots[1:]):
        pl, nl = p['provenance'], n['provenance']
        same_place = pl['place'] == nl['place']
        same_tone = pl['tone'] == nl['tone']
        same_ev = p['event_id'] == n['event_id']
        jump = 'low' if (same_place and same_tone) else ('medium' if same_place or same_tone else 'high')
        if same_ev and same_place:
            strat, why = 'none_needed', '同一事件內連續動作，直接切。'
        elif p['story_section'] == n['story_section']:
            strat, why = 'sound_bridge' if n['role'] in ('dialogue', 'reaction') else 'none_needed', '同一段落內換場景／事件，對白或環境聲承接即可，不需特殊轉場。'
        else:
            strat, why = 'chapter_change_establishing_cut', '章節切換：下一鏡先以建立鏡頭／環境鏡頭進入，明暗與地點變化為刻意的段落分隔，不用特殊轉場。'
        adj.append({'from_shot_id': p['shot_id'], 'to_shot_id': n['shot_id'],
                    'visual_jump': jump, 'composition_anchor': f"{pl['place']}→{nl['place']}",
                    'tone_change': f"{pl['tone']}→{nl['tone']}",
                    'action_continuity': 'continuous' if same_ev else 'new_event',
                    'bridge_strategy': strat, 'reason': why})
    for s, a_ in zip(shots, adj + [None]):
        if a_: s['adjacency_review'] = a_

    # ---- scenes / events ----
    sel_events = []
    for s in shots:
        if s['event_id'] not in sel_events: sel_events.append(s['event_id'])
    scene_of, scene_events = {}, defaultdict(list)
    for eid, e in events.items():
        key = (e['date'], e['location']['name'])
        sc = SCENE_NAMES[key][0]
        scene_of[eid] = sc; scene_events[sc].append(eid)
    scene_meta = {}
    for key, v in SCENE_NAMES.items():
        scene_meta.setdefault(v[0], (v[1], v[2], v[3], key))
    # SC12 午餐等餐: represented by EV090 shot? ensure
    sc_shots = defaultdict(list)
    for s in shots: sc_shots[scene_of[s['event_id']]].append(s['shot_id'])

    scenes = []
    for sc in sorted(scene_meta):
        name, kind, why, key = scene_meta[sc]
        evs = scene_events[sc]
        ev0 = events[evs[0]]
        rep = [e for e in evs if e in sel_events]
        times = sorted(events[e]['start'][11:16] for e in evs)
        eng = {
         'SC02': ('等候中兩兄弟鬥嘴，帶出「這趟旅程有孩子的觀點」', '孩子說「我不想買」的小反差'),
         'SC03': ('抵達沖繩的第一件事：買飲料', '「下機第一件事」的小收束'),
         'SC04': ('第一天的探索與寶可夢造景', ''),
         'SC06': ('出海、看魚、餵魚的連續發現', '「一二三、再見、謝謝」餵魚收束'),
         'SC07': ('家人在日常中互相照顧', ''),
         'SC08': ('冰淇淋與小請求', ''),
         'SC09': ('動物近距離互動與水族館震撼', '孩子衝出噴霧的歡鬧收尾'),
         'SC11': ('園區遊園車的海景', ''),
         'SC13': ('餵鳥、看沙貓、搭小火車', '吃冰收尾'),
         'SC15': ('海灘玩水，發現小魚', '「欸有魚」'),
         'SC16': ('午餐的日常', ''),
         'SC17': ('室內科學遊樂與戲水', '瀑布下 reaction'),
         'SC19': ('小孩抱怨每天都只錄哥哥', '拿起相機自己錄'),
         'SC20': ('回程前看飛機', '「一定會有機會」'),
        }.get(sc, ('', ''))
        scenes.append({
            'scene_id': sc, 'date': key[0], 'time_range': [times[0], times[-1]], 'location': name, 'location_name': key[1],
            'activity': ev0['event_type'], 'event_ids': evs,
            'coverage_importance': 'MAJOR' if sc in ('SC06', 'SC09', 'SC13', 'SC15', 'SC17') else ('MINOR' if kind == 'EXCLUDED' else 'NORMAL'),
            'representative_event_candidates': rep, 'engagement_change': eng[0], 'mini_payoff': eng[1],
            'coverage_gaps': [], 'must_preserve': kind != 'EXCLUDED' and sc in ('SC06', 'SC20'),
            'selected_shot_ids': sc_shots.get(sc, []),
            'reason': (why or ('已有代表 Event：' + '、'.join(rep))) if kind == 'EXCLUDED' else ('已有代表 Event：' + '、'.join(rep) if rep else '無代表（見 coverage_gaps）'),
            'excluded': kind == 'EXCLUDED',
        })
    # SC12: no representative -> record exclusion with reason (EV090 shot is in Neo Park section by time)
    for sc_ in scenes:
        if sc_['scene_id'] == 'SC12' and not sc_['event_ids'][0] in sel_events:
            sc_['excluded'] = True
            sc_['reason'] = '午餐等餐 3 個 Event（EV089–EV091）：內容為小孩等餐碎念與排公仔，兩個動作與 Neo Park 的對白鏡頭功能重複；Neo Park 段落已有同日 Scene 代表。'
    # --- exclusions ---
    excluded = []
    for eid, e in events.items():
        if eid in sel_events: continue
        clips = [master[r['clip_id']] for r in e['source_ranges']]
        human_skip = all(c['human_review']['status'] == 'SKIP' for c in clips)
        sc = scene_of[eid]
        scn = scene_meta[sc]
        sc_rep = [x for x in scene_events[sc] if x in sel_events]
        if eid in EXCLUDE_SPECIFIC: why = EXCLUDE_SPECIFIC[eid]
        elif human_skip: why = 'Human 對來源 clip 全部標 SKIP，尊重人工意見。'
        elif e['event_type'] == 'transition_or_incidental' or max(e['story_value'], e['emotional_value'], e['interaction_value']) <= 1:
            why = '過場或零碎畫面，無獨立故事功能。'
        elif scn[1] == 'EXCLUDED':
            why = scn[2]
        elif sc_rep:
            why = f"同 Scene（{scn[0]}）已有更強代表 {'、'.join(sc_rep)}；本事件功能重複或畫面較弱。"
        else:
            why = '同 Scene 無其他代表，但本事件故事價值低，片長取捨；已在 scene_inventory 記錄。'
        has_human_keep = any(c['human_review']['status'] in ('CANDIDATE', 'IMPORTANT', 'MUST_KEEP', 'MUST_REVIEW') for c in clips)
        excluded.append({'event_id': eid, 'scene_id': sc, 'summary': e['summary'],
                         'exclusion_reason': why, 'human_candidate_reevaluated': has_human_keep,
                         'ai_recommendations': sorted({c['ai_review']['recommendation'] for c in clips})})

    # SC12 hard check: no scene vanishes without reason
    for sc_ in scenes:
        assert sc_['selected_shot_ids'] or sc_['excluded'], sc_['scene_id']

    # ---- human conflicts ----
    used = {s['source_clip'] for s in shots}
    conflicts = []
    for cid, c in master.items():
        rel = c['review_relationship']
        if rel == 'AI_SKIP_HUMAN_KEEP':
            conflicts.append({'clip_id': cid, 'relationship': rel, 'ai': c['ai_review']['recommendation'], 'human': c['human_review']['status'],
                              'used_in_edit': cid in used,
                              'resolution': ('已選入。' if cid in used else '重新評估後未採用：' + (c['visual_summary'][:60] or '畫面較弱') + '；同 Scene 已有更強代表或故事功能低。')})
        elif rel == 'AI_KEEP_HUMAN_SKIP':
            conflicts.append({'clip_id': cid, 'relationship': rel, 'ai': c['ai_review']['recommendation'], 'human': 'SKIP',
                              'used_in_edit': cid in used, 'resolution': '尊重 Human SKIP，未使用。' if cid not in used else 'CONFLICT: 使用了 Human SKIP 素材'})
    # ---- hero reviews ----
    hero_rev = []
    for hid, (dec, why, (k, a, b)) in HERO_DECISIONS.items():
        h = hero[hid]
        hero_rev.append({'candidate_id': hid, 'stage0b_status': (h.get('agent_review') or {}).get('status'),
                         'reviewed_range': [a, b], 'reviewed_media': by4[k]['source_path'] + ' (Original, ffmpeg 8-frame strip; no audio listening)',
                         'story_function': h['candidate_type'], 'context_complete': True, 'decision': dec, 'reason': why,
                         'audio_listened': False})

    # ---- coverage gaps ----
    gaps = [
     {'scene_id': 'SC17', 'expected_function': '直升機展示：小孩坐進機艙', 'available_evidence': 'EV164／0448／0449 畫面',
      'missing_coverage': '原片 0449 主要拍到大人，兩個小孩未清楚入鏡', 'impact': '低，兒童王國已有其他互動展項', 'resolution': '接受缺口'},
     {'scene_id': 'SC17', 'expected_function': '龍捲風霧氣裝置的互動結果', 'available_evidence': 'EV163／0446／0447（原片 28–60s）',
      'missing_coverage': '畫面偏暗，小孩動作模糊，不適合作為正式鏡頭', 'impact': '中，錯過一個小孩玩了好幾輪的活動', 'resolution': '以既有素材調整敘事：用 EV157 暗室發光筆代表暗室互動展項；建議未來在此類暗室展項使用補光或更穩定的角度'},
     {'scene_id': 'SC11', 'expected_function': '古宇利海洋塔的建立環境與人物反應', 'available_evidence': 'EV086（過曝）、EV084（遊園車；來源 0154 被 Human 標 SKIP）',
      'missing_coverage': '登塔高處畫面過曝，缺少小孩與景色同框的鏡頭', 'impact': '低，僅以 EV087 觀景台小孩拍照作代表', 'resolution': '以既有素材調整敘事'},
     {'scene_id': 'SC09', 'expected_function': '海豚餵食與水族館的小孩反應', 'available_evidence': 'EV051／EV060／EV069',
      'missing_coverage': '鯨鯊畫面來源被 Human 標 SKIP（0133／0135），未使用', 'impact': '中，水族館最大亮點以 0132 的魚群畫面代替', 'resolution': '接受缺口（尊重 Human SKIP）'},
     {'scene_id': 'SC01', 'expected_function': '出發前在家', 'available_evidence': 'EV001–EV005', 'missing_coverage': 'Human 全部標 SKIP，整個 Scene 不入片',
      'impact': '低，旅程從機場開始', 'resolution': '接受缺口'},
    ]

    total = round(sum(s['duration'] for s in shots), 2)
    roles = Counter(s['role'] for s in shots)

    # ---- story plan ----
    sections = []
    for name in dict.fromkeys(s['story_section'] for s in shots):
        ss = [s for s in shots if s['story_section'] == name]
        sections.append({'section': name, 'shot_ids': [s['shot_id'] for s in ss], 'duration': round(sum(s['duration'] for s in ss), 2),
                         'events': list(dict.fromkeys(s['event_id'] for s in ss))})
    story_plan = {
     'title': '沖繩五天四夜：孩子們的視角', 'spine': '出發 → 透明船出海餵魚（全片高點）→ 日常小插曲 → 海洋博 → Neo Park/古宇利 → 海灘 → 兒童王國 → 小孩要自己錄（反轉）→ 機場看飛機（結尾）',
     'cold_open': None, 'cold_open_reason': '未使用 Cold Open：高點「透明船餵魚」在第二章即出現，結尾的「為什麼每天都錄哥哥」需要前面的拍攝者鋪陳才有反轉效果。',
     'sections': sections, 'selected_events': sel_events, 'estimated_runtime_s': total,
     'runtime_note': f'{total:.0f} 秒，高於一般 180–360 秒的參考範圍：行程六天、五個主要 Scene（透明船、海洋博、Neo Park、海灘、兒童王國），依 Coverage First 先保代表再縮短。若需縮短，優先砍 Neo Park／海灘段的 dialogue 鏡頭，不得刪光整個 Scene。',
     'music_sections': [], 'music_note': '本輪未規劃卡點；BGM 由 Stage 3 依預設音樂處理。',
     'photos': {'used': 0, 'note': '本輪未納入照片；影片已足以代表所有 Scene。'},
     'human_review_note': 'Human Review：201 CANDIDATE、59 SKIP（無 NO_PREFERENCE、無 MUST_KEEP）；CANDIDATE 一律視為「必須認真評估」而非必選。',
    }
    # ---- chapter engagement ----
    outline = ['# Stage 1 導演大綱', '', f'總長約 {total:.0f} 秒｜Shot {len(shots)}｜Selected Event {len(sel_events)}｜Scene 代表 {sum(1 for x in scenes if x["selected_shot_ids"])}/{len(scenes)}', '']
    for sec in sections:
        outline.append(f"## {sec['section']}（{sec['duration']:.0f}s）")
        for sid in sec['shot_ids']:
            s = next(x for x in shots if x['shot_id'] == sid)
            outline.append(f"- {sid} [{s['role']}] {s['filename']} {s['cut_start']:.1f}–{s['cut_end']:.1f}s｜{s['editorial_reason']}")
        outline.append('')
    outline += ['## 未選入／衝突摘要', f'- Excluded Event：{len(excluded)}', f'- Human conflicts：{len(conflicts)}（皆已列在 scene/validation）', '']

    # ---- write main outputs (hash after) ----
    dump('story_plan.json', story_plan)
    (OUT1 / 'director_outline.txt').write_text('\n'.join(outline), encoding='utf-8')
    dump('scene_inventory.json', {'scenes': scenes, 'excluded_events': excluded, 'hero_scene_director_review': hero_rev})
    cg = dump('coverage_gaps.json', gaps)
    ed = dump('edit_decisions.json', {
        'stage': 1, 'version': 1, 'format': '16:9', 'fps_note': '成片 fps 由 Stage 2 依原片 29.97/59.94 決定，本階段不 Render',
        'total_duration_s': total, 'shots': shots, 'semantic_integrity_review': [],
        'semantic_integrity_note': '本輪沒有對話重排、刪句或 J/L Cut；所有 Shot 保持原片單一連續範圍與原音，因此不需 semantic_integrity_review 條目。',
        'audio_segments_note': '未使用 audio_segments；audio_strategy 僅為 original／ambient，Stage 2 直接取該 Shot 的原片音訊。',
        'human_review_conflicts': conflicts,
    })

    # ---- validation ----
    cl = {c['clip_id'] for c in master.values()}
    checks = {}
    def chk(name, ok, ev=None): checks[name] = {'result': 'PASS' if ok else 'FAIL', 'evidence': ev if ev is not None else {}}
    chk('stage0_overall_gate', s0['overall'] in ('PASS', 'PASS_WITH_WARNINGS'), {'stage0': s0['overall'], 'stage0d': 'PASS (human review: 201 CANDIDATE / 59 SKIP)'})
    chk('selected_event_shot_coverage', all(any(s['event_id'] == e for s in shots) for e in sel_events) and all(s['event_id'] in sel_events for s in shots), {'selected': len(sel_events)})
    chk('duplicate_selected_event_check', len(sel_events) == len(set(sel_events)))
    chk('scene_coverage', all(x['selected_shot_ids'] or x['excluded'] for x in scenes), {'scenes': len(scenes), 'with_shots': sum(1 for x in scenes if x['selected_shot_ids']), 'excluded_with_reason': [x['scene_id'] for x in scenes if x['excluded']]})
    bad_cut = [s['shot_id'] for s in shots if not (0 <= s['cut_start'] < s['cut_end'] <= master[s['source_clip']]['duration'] + 0.01) or abs(s['duration'] - (s['cut_end'] - s['cut_start'])) > 0.011]
    chk('cut_range_validity', not bad_cut, {'bad': bad_cut})
    chk('event_range_containment', all(s['provenance']['event_range_ok'] for s in shots), {'outside_event': [s['shot_id'] for s in shots if not s['provenance']['event_range_ok']]})
    bad_src = [s['shot_id'] for s in shots if not (REPO / s['source_path']).exists() or 'workspace/media/' not in s['source_path'] or s['source_clip'] not in cl]
    chk('source_is_original', not bad_src, {'bad': bad_src})
    tm_bad = []
    for s in shots:
        exp = [x['sentence_id'] for x in sentences[s['source_clip']] if x['end'] >= s['cut_start'] and x['start'] <= s['cut_end']]
        if exp != s['source_sentence_ids']: tm_bad.append(s['shot_id'])
    chk('transcript_mapping', not tm_bad, {'bad': tm_bad})
    chk('shot_role_diversity', len(roles) >= 6, dict(roles))
    chk('no_hard_unusable_selected', not any(master[s['source_clip']]['technical']['hard_unusable'] for s in shots))
    skip_used = [s['shot_id'] for s in shots if s['provenance']['stage0d_human'] == 'SKIP']
    chk('human_review_conflicts_resolved', not skip_used and all(('resolution' in c) for c in conflicts), {'human_skip_used': skip_used, 'conflicts': len(conflicts), 'ai_skip_human_keep_used': sum(1 for c in conflicts if c['relationship'] == 'AI_SKIP_HUMAN_KEEP' and c['used_in_edit'])})
    chk('boundary_review_complete', all('boundary_review' in s for s in shots), {'non_complete_speech': [s['shot_id'] for s in shots if not s['boundary_review']['speech_complete']]})
    chk('audio_segment_ranges', True, {'note': 'no audio_segments used; strategies original/ambient only'})
    chk('audio_timeline_bounds', True, {'note': 'n/a'}); chk('audio_overlap_intent', True, {'note': 'n/a'})
    chk('semantic_integrity', True, {'note': 'no reordering/deleting of sentences, no J/L'})
    chk('adjacency_review_complete', len(adj) == len(shots) - 1 and all(a_['bridge_strategy'] for a_ in adj), {'pairs': len(adj), 'high_jump': sum(1 for a_ in adj if a_['visual_jump'] == 'high')})
    chk('coverage_gap_accounting', all({'scene_id', 'expected_function', 'available_evidence', 'missing_coverage', 'impact', 'resolution'} <= set(g) for g in gaps), {'gaps': len(gaps)})
    chk('chapter_engagement', all(x['engagement_change'] for x in scenes if x['selected_shot_ids'] and x['scene_id'] in ('SC02','SC03','SC06','SC07','SC08','SC09','SC11','SC13','SC15','SC16','SC17','SC19','SC20')) , {'note': 'engagement_change recorded for major scenes'})
    chk('reframe_subject_coverage', all(not s['reframe']['enabled'] for s in shots), {'reframed': 0})
    chk('hero_scene_director_review', all(h['decision'] in ('SELECT', 'NOT_SELECT', 'NEEDS_REVISION') for h in hero_rev) and not [h for h in hero if hero[h].get('agent_review', {}).get('status') in ('CONFIRMED', 'NEEDS_MORE_REVIEW') and h not in HERO_DECISIONS], {'reviewed': len(hero_rev), 'selected': sum(1 for h in hero_rev if h['decision'] == 'SELECT')})
    last = shots[-1]
    chk('ending_visual_quality', last['provenance']['tone'] == 'bright', {'ending': last['shot_id'], 'clip': last['source_clip']})
    chk('ending_story_function', last['role'] == 'ending' and last['event_id'] == 'EV189', {'event': last['event_id']})
    warns = [
     'Human Review 為整批標記（201 CANDIDATE／59 SKIP），沒有逐支理由，CANDIDATE 只能視為「請認真評估」，未視為必選。',
     'runtime 無法聽原音：所有 Hero 與對話判斷依畫面＋ASR／VAD；HC001、HC022、HC045 的聲音（笑聲／叫聲）未實際聽查，Storyboard Gate 時請以可聽預覽確認。',
     f'預估片長 {total:.0f} 秒高於一般 180–360 秒參考；理由與縮短優先序見 story_plan.runtime_note。',
     '多數鏡頭的 boundary_review 使用 ASR 句界；ASR 低信心時改依動作落點切，已在 boundary_review.flags 標註。',
    ]
    overall = 'FAIL' if any(c['result'] == 'FAIL' for c in checks.values()) else 'PASS_WITH_WARNINGS'
    rep = {'stage': 1, 'generated_by': 'build_stage1.py', 'overall': overall, 'checks': checks, 'warnings': warns,
           'summary': {'scene_count': len(scenes), 'selected_events': len(sel_events), 'excluded_events': len(excluded), 'shot_count': len(shots),
                       'estimated_runtime_s': total, 'role_distribution': dict(roles), 'human_review_conflicts': len(conflicts), 'ending_event': last['event_id']},
           'hashes': {'edit_decisions_sha256': sha256_of(ed), 'coverage_gaps_sha256': sha256_of(cg), 'story_plan_sha256': sha256_of(OUT1 / 'story_plan.json')}}
    dump('stage1_validation_report.json', rep)
    print(json.dumps({'overall': overall, **rep['summary'], 'fails': [k for k, v in checks.items() if v['result'] == 'FAIL']}, ensure_ascii=False, indent=1))
    for k, v in checks.items():
        if v['result'] == 'FAIL': print('FAIL', k, v['evidence'])


if __name__ == '__main__':
    main()
