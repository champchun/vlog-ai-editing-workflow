#!/usr/bin/env python3
"""Stage 0C step 4: match events to Google Timeline visits and build a place-naming sheet.

For each event (UTC window) find Timeline visits that overlap in time. The event's place key is the
Timeline placeID of the best overlapping visit (largest overlap); events with no overlapping visit fall
back to ~400 m coordinate clustering of their EXIF coordinates and are marked as such. No names are
invented: the user names each place in the generated HTML (download place_names.json -> workspace/gps/).

Outputs: temp/stage0c/places.json, process/workspace/gps/place_naming.html
"""
from __future__ import annotations

import base64
import html
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2

PROCESS = Path(__file__).resolve().parents[2]
REPO = PROCESS.parent
sys.path.insert(0, str(PROCESS / "stage-0A-local-pre-analysis" / "scripts"))
from common import read_json, write_json  # noqa: E402

W = PROCESS / "workspace"
OUT = W / "project-output/stage0c_output"
TEMP = W / "temp/stage0c"
GPS = W / "gps"
CLUSTER_M = 400


def hav(a, b):
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def geo(s):
    lat, lon = s.removeprefix("geo:").split(",")
    return float(lat), float(lon)


def main():
    ev = read_json(OUT / "event_candidates.json")["events"]
    tl = json.loads((GPS / "Timeline 3.json").read_text(encoding="utf-8"))
    t_lo = min(datetime.fromisoformat(e["start"]) for e in ev).timestamp() - 86400
    t_hi = max(datetime.fromisoformat(e["end"]) for e in ev).timestamp() + 86400
    visits = []
    for e in tl:
        if "visit" not in e:
            continue
        a, b = datetime.fromisoformat(e["startTime"]).timestamp(), datetime.fromisoformat(e["endTime"]).timestamp()
        if b < t_lo or a > t_hi:
            continue
        tc = e["visit"]["topCandidate"]
        visits.append({"a": a, "b": b, "placeID": tc["placeID"], "type": tc.get("semanticType"), "loc": geo(tc["placeLocation"]),
                       "prob": float(e["visit"].get("probability", 0)), "start": e["startTime"], "end": e["endTime"]})
    assign = {}
    for e in ev:
        a, b = datetime.fromisoformat(e["start"]).timestamp(), datetime.fromisoformat(e["end"]).timestamp()
        best, ov_best = None, 0.0
        for v in visits:
            ov = min(b, v["b"]) - max(a, v["a"])
            if ov > ov_best:
                best, ov_best = v, ov
        g = e["location"]["gps_auxiliary"]
        exif = (g["lat"], g["lon"]) if g else None
        if best and (exif is None or hav(exif, best["loc"]) <= 1500):
            assign[e["event_id"]] = {"key": best["placeID"], "basis": "timeline_visit_overlap", "type": best["type"],
                                     "visit": [best["start"], best["end"]], "visit_loc": best["loc"],
                                     "exif_to_visit_m": round(hav(exif, best["loc"])) if exif else None, "overlap_s": round(ov_best)}
        else:
            assign[e["event_id"]] = {"key": None, "basis": "exif_coordinate_cluster", "type": None, "exif": exif,
                                     "note": "no overlapping Timeline visit within 1.5 km (travelling / path-only period)"}
    # cluster the fallback events by coordinate
    cl = []
    for eid, a in assign.items():
        if a["key"] is None and a["exif"]:
            for c in cl:
                if hav(c["center"], a["exif"]) <= CLUSTER_M:
                    c["members"].append(eid)
                    break
            else:
                cl.append({"center": a["exif"], "members": [eid]})
    for i, c in enumerate(cl, 1):
        for eid in c["members"]:
            assign[eid]["key"] = f"cluster{i:02d}"
    # places
    by_key = defaultdict(list)
    for e in ev:
        by_key[assign[e["event_id"]]["key"]].append(e)
    places = []
    for k, es in sorted(by_key.items(), key=lambda kv: min(e["start"] for e in kv[1])):
        lat = sum(e["location"]["gps_auxiliary"]["lat"] for e in es) / len(es)
        lon = sum(e["location"]["gps_auxiliary"]["lon"] for e in es) / len(es)
        types = Counter(assign[e["event_id"]]["type"] for e in es if assign[e["event_id"]]["type"])
        places.append({"place_id": None, "timeline_key": k, "basis": assign[es[0]["event_id"]]["basis"],
                       "timeline_semantic_type": types.most_common(1)[0][0] if types else None,
                       "lat": round(lat, 5), "lon": round(lon, 5),
                       "dates": sorted({e["date"] for e in es}), "event_ids": [e["event_id"] for e in es],
                       "footage_s": round(sum(r["end"] - r["start"] for e in es for r in e["source_ranges"]))})
    for i, p in enumerate(places, 1):
        p["place_id"] = f"P{i:02d}"
    key2pid = {p["timeline_key"]: p["place_id"] for p in places}
    ev_by = {e["event_id"]: e for e in ev}
    for eid, a in assign.items():
        a["place_id"] = key2pid[a["key"]]
    write_json(TEMP / "places.json", {"method": __doc__, "events_total": len(ev), "visits_considered": len(visits),
                                      "places": places, "event_place": assign})

    # thumbnails: nearest existing 0B review frame to each event's first-unit midpoint
    fman = defaultdict(list)
    for f in read_json(W / "temp/stage0b/frames_manifest.json")["frames"]:
        fman[f["clip_id"]].append(f)

    def thumbs(p, n=4):
        out, seen = [], set()
        es = sorted((ev_by[i] for i in p["event_ids"]), key=lambda e: -(e["story_value"] + e["visual_value"]))
        for e in es:
            r = e["source_ranges"][0]
            cand = [f for f in fman.get(r["clip_id"], []) if r["start"] <= f["t"] <= r["end"]] or fman.get(r["clip_id"], [])
            if not cand:
                continue
            mid = (r["start"] + r["end"]) / 2
            f = min(cand, key=lambda f: abs(f["t"] - mid))
            if f["path"] in seen:
                continue
            seen.add(f["path"])
            img = cv2.resize(cv2.imread(str(REPO / f["path"])), (320, 180), interpolation=cv2.INTER_AREA)
            out.append((e, base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()).decode()))
            if len(out) >= n:
                break
        return out

    rows = []
    for p in places:
        es = [ev_by[i] for i in p["event_ids"]]
        ts = thumbs(p)
        top = sorted(es, key=lambda e: -(e["story_value"] + e["visual_value"]))[:3]
        pre = {"Home": "住家（Timeline 標註 Home）", "Work": "工作地（Timeline 標註 Work）"}.get(p["timeline_semantic_type"], "")
        rows.append(f"""<section class="place" data-pid="{p['place_id']}">
<h3>{p['place_id']} <small>{', '.join(p['dates'])} · {len(es)} 個事件 · 素材 {p['footage_s']//60} 分 {p['footage_s']%60} 秒 · Timeline 類型：{p['timeline_semantic_type'] or '無'}</small></h3>
<div class="thumbs">{''.join(f'<figure><img src="data:image/jpeg;base64,{b}"><figcaption>{html.escape(e["event_id"])} {html.escape(e["summary"][:34])}</figcaption></figure>' for e, b in ts)}</div>
<p class="meta">座標 {p['lat']}, {p['lon']} · <a href="https://www.google.com/maps?q={p['lat']},{p['lon']}" target="_blank" rel="noopener">在地圖上開啟</a>
 · 依據：{'Timeline 停留紀錄' if p['basis']=='timeline_visit_overlap' else '座標群集（Timeline 無對應停留）'}</p>
<p class="meta">代表事件：{html.escape('；'.join(e['summary'][:30] for e in top))}</p>
<label>地名：<input class="name" placeholder="{html.escape(pre) or '例如：○○海洋公園'}" value=""></label>
<label>備註：<input class="note" placeholder="選填"></label>
</section>""")
    page = f"""<!doctype html><html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>地點命名表</title><style>
body{{font-family:-apple-system,"PingFang TC",sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#222;background:#fafafa}}
.place{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:14px 0}}
h3{{margin:0 0 6px}} small{{font-weight:400;color:#666;font-size:13px}}
.thumbs{{display:flex;gap:8px;flex-wrap:wrap}} figure{{margin:0;width:200px}} figure img{{width:200px;border-radius:4px}}
figcaption{{font-size:12px;color:#555}} .meta{{font-size:13px;color:#444;margin:6px 0}}
label{{display:inline-block;margin:6px 12px 0 0;font-size:14px}} input{{padding:5px 8px;width:280px;font-size:14px}}
#bar{{position:sticky;top:0;background:#fffbe6;border:1px solid #ecd;padding:10px;border-radius:6px;z-index:2}}
button{{padding:7px 14px;font-size:14px;cursor:pointer}}</style></head><body>
<div id="bar"><b>地點命名表</b>：共 {len(places)} 個地點、{len(ev)} 個事件。只填你確定的地名，不確定的留白（會維持「未知」）。
地圖連結是你自行點開的，這個頁面不會傳送任何資料。填完按下載，把 <code>place_names.json</code> 放進 <code>process/workspace/gps/</code>。
<button id="dl">下載 place_names.json</button> <span id="cnt"></span></div>
{''.join(rows)}
<script>
const ST='place_names_draft';
function load(){{try{{const d=JSON.parse(localStorage.getItem(ST)||'{{}}');document.querySelectorAll('.place').forEach(s=>{{const x=d[s.dataset.pid];if(x){{s.querySelector('.name').value=x.name||'';s.querySelector('.note').value=x.note||''}}}})}}catch(e){{}}}}
function collect(){{const o={{}};document.querySelectorAll('.place').forEach(s=>{{o[s.dataset.pid]={{name:s.querySelector('.name').value.trim(),note:s.querySelector('.note').value.trim()}}}});return o}}
function upd(){{const o=collect();try{{localStorage.setItem(ST,JSON.stringify(o))}}catch(e){{}};document.getElementById('cnt').textContent='已填 '+Object.values(o).filter(v=>v.name).length+'/{len(places)}'}}
document.addEventListener('input',upd);load();upd();
document.getElementById('dl').onclick=()=>{{const o=collect();const out={{source:'user_confirmed',created:new Date().toISOString(),places:o}};
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{{type:'application/json'}}));a.download='place_names.json';a.click()}};
</script></body></html>"""
    (GPS / "place_naming.html").write_text(page, encoding="utf-8")
    print(f"visits considered {len(visits)}; events {len(ev)}; places {len(places)}")
    print("basis", dict(Counter(p["basis"] for p in places)), "types", dict(Counter(p["timeline_semantic_type"] for p in places)))
    print("events per place", sorted((len(p["event_ids"]) for p in places), reverse=True))
    print("exif→visit distance m (median/max)", sorted(a["exif_to_visit_m"] for a in assign.values() if a.get("exif_to_visit_m") is not None)[len(assign) // 2],
          max(a.get("exif_to_visit_m") or 0 for a in assign.values()))


if __name__ == "__main__":
    main()
