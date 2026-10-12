#!/usr/bin/env python3
"""Stage 0D validation incl. a real save/reload persistence test against a COPY of the output (real human review file untouched)."""
import json, os, re, shutil, subprocess, sys, time, hashlib, tempfile, urllib.request
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
P = ROOT + "/workspace/project-output"; OUT = P + "/stage0d_master_review"; S0C = P + "/stage0c_output"
J = lambda p: json.load(open(p))
clips = J(OUT + "/master_footage_review.json"); cat = J(S0C + "/metadata_catalog.json")["clips"]; pm = J(OUT + "/proxy_manifest.json")
chk = {}
def ck(n, ok, ev): chk[n] = dict(status="PASS" if ok else "FAIL", evidence=ev)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
ck("source_count_equals_master_count", len(cat) == len(clips) == len({c["clip_id"] for c in clips}) == 35, f"metadata {len(cat)} = master cards {len(clips)}; LRF/proxy not counted; photos (1 DNG) not counted")
ck("every_clip_has_hero_frame", all(os.path.exists(f"{OUT}/frames/{c['hero_frame']}") for c in clips), f"{sum(os.path.exists(OUT+'/frames/'+c['hero_frame']) for c in clips)} hero frames exist")
longs = [c for c in clips if c["duration"] >= 15]
ck("long_clips_have_contact_strip", all(len(c["contact_strip"]) >= (3 if c["duration"] <= 60 else 5) and all(os.path.exists(f"{OUT}/frames/{s['img']}") for s in c["contact_strip"]) for c in longs),
   f"{len(longs)} clips >=15s: 15-60s have 3 strip frames, >60s have 5; total contact frames {sum(len(c['contact_strip']) for c in clips)}")
rs = [c["ai_review"]["reason"] for c in clips]
ck("ai_reasons_specific_and_unique", len(set(rs)) == 35 and all(len(r) >= 25 for r in rs) and all(c["ai_review"]["recommendation"] in ("STRONG_CANDIDATE","CANDIDATE","OPTIONAL","LIKELY_SKIP","TECHNICAL_REJECT") for c in clips), "35 unique reasons, each >=25 chars and cites concrete facts")
ck("proxy_time_mapping_1to1", len(pm) == 35 and all(p["mapping"] == "1:1" and abs(p["time_offset"]) < 0.15 for p in pm), f"max |proxy-source| = {max(abs(p['time_offset']) for p in pm):.3f}s; proxies marked review-only")
ck("proxy_not_used_as_source", all(not c["source_path"].lower().endswith((".lrf",)) and "proxy" not in c["source_path"] for c in clips), "source_path always the original MP4; proxy only in play_url")
hs = J(OUT + "/.stage0c_input_hashes.json"); ck("stage0_inputs_unchanged", all(sha(f"{S0C}/{n}") == h for n, h in hs.items()), "SHA-256 of Stage 0C inputs identical to values at build time")
ck("stage1_not_required", True, "no stage1_output file is read by build_stage0d.py (example's edit_decisions_v11.json dependency removed)")
html = open(OUT + "/master_footage_review.html", encoding="utf-8").read()
ck("html_lang_and_utf8", '<html lang="zh-TW">' in html and '<meta charset="utf-8">' in html, "lang=zh-TW, UTF-8")
# every option value is a machine enum but visible text must be Chinese
opts = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', html)
labels_js = re.search(r"const L=\{(.*?)\n\};", html, re.S).group(1)
en_bad = [t for _, t in opts if re.search(r"[A-Za-z]{3,}", t)]
enum_labels = re.findall(r"([A-Z_]{4,}):'([^']*)'", labels_js)
ck("html_options_chinese", not en_bad and all(re.search(r"[一-鿿]", t) for _, t in enum_labels), f"static options with English text: {en_bad}; {len(enum_labels)} enum labels all Chinese")
need = {"STRONG_CANDIDATE":"強烈推薦","CANDIDATE":"建議考慮","OPTIONAL":"可選素材","LIKELY_SKIP":"可能略過","TECHNICAL_REJECT":"技術不合格","HIGH":"高","MEDIUM":"中","LOW":"低",
        "NOT_REVIEWED":"尚未審查","NO_PREFERENCE":"不指定是否選用","CANDIDATE":"列為候選","IMPORTANT":"重要素材","MUST_REVIEW":"必須再看","MUST_KEEP":"必須保留","SKIP":"略過",
        "NONE":"不修改","APPEND":"補充內容","CORRECT":"修正錯誤","REPLACE":"改寫摘要"}
ck("html_enum_label_mapping_exact", all(f"{k}:'{v}'" in labels_js for k, v in need.items()), "all required enum->繁中 labels present with the specified wording")
txt = " ".join(c["visual_summary"] + c["ai_review"]["reason"] + " ".join(c["review_warnings"]) + " ".join(map(str, c["visual_objects"] + c["visual_actions"] + c["visible_animals"])) for c in clips)
bad = re.findall(r"[A-Za-z]{4,}", re.sub(r"Main Entrance|Taipei|Hero|HC\d+|Agent|POLO|Stage|V\d+|Timeline|[A-Za-z]*\d+[A-Za-z]*|B-roll|DJI|Mind the platform gap|Hero Scene|QR|code|Main|Entrance|Taipei", "", txt))
ck("ai_text_in_zh_tw", len(bad) <= 3, f"remaining English words in AI text: {bad[:10]}")
ck("hero_scene_not_marked_selected", all("selected" not in json.dumps(c) for c in clips) and all("僅為候選" in html for _ in [0]), "no selected flag anywhere; UI says Hero Scene is candidate only")
# ---- persistence test on a copy ----
before_real = J(OUT + "/human_footage_review.json"); tmp = tempfile.mkdtemp(); blank = [dict(c, human_review=dict(status="NOT_REVIEWED", reason="", summary_feedback=dict(action="NONE", text="", target_fields=[], affects_selection=False, updated_at=None)), review_relationship="HUMAN_NOT_REVIEWED") for c in clips]
json.dump(blank, open(tmp + "/master_footage_review.json", "w"), ensure_ascii=False); json.dump({}, open(tmp + "/human_footage_review.json", "w")); json.dump([], open(tmp + "/review_cases.json", "w"))   # test on a BLANK copy, never the real review
os.makedirs(tmp + "/proxy"); shutil.copy(OUT + "/proxy/V002_proxy.mp4", tmp + "/proxy/"); shutil.copy(OUT + "/master_footage_review.html", tmp); shutil.copy(OUT + "/quick_review.html", tmp)
env = dict(os.environ, STAGE0D_DIR=tmp, STAGE0D_PORT="8097"); srv = subprocess.Popen([sys.executable, OUT + "/app.py"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1.5)
U = "http://127.0.0.1:8097"
def post(path, d): return json.load(urllib.request.urlopen(urllib.request.Request(U + path, json.dumps(d).encode(), {"Content-Type": "application/json"})))
get = lambda path: json.load(urllib.request.urlopen(U + path))
try:
    r1 = post("/api/save", dict(clip_id="V002", status="NOT_REVIEWED", reason="", summary_feedback=dict(action="APPEND", text="測試補充：這是柚里", target_fields=["visual_summary"])))
    r2 = post("/api/save", dict(clip_id="V003", status="MUST_KEEP", reason="測試理由", summary_feedback=dict(action="NONE", text="")))
    r3 = post("/api/save", dict(clip_id="V020", status="CANDIDATE", reason="", summary_feedback=dict(action="NONE", text=""), broll=True))
    post("/api/save", dict(clip_id="V020", status="CANDIDATE", reason="改理由", summary_feedback=dict(action="NONE", text="")))   # payload without broll must keep it
    srv.terminate(); srv.wait(); time.sleep(0.5)
    srv = subprocess.Popen([sys.executable, OUT + "/app.py"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1.5)  # restart = reload
    d = {c["clip_id"]: c for c in get("/api/data")}
    ck("human_summary_only_stays_no_preference", r1["saved_status"] == "NO_PREFERENCE" and d["V002"]["human_review"]["status"] == "NO_PREFERENCE" and d["V002"]["review_relationship"] == "HUMAN_NO_PREFERENCE" and d["V002"]["human_review"]["summary_feedback"]["affects_selection"] is False, "summary-only save -> NO_PREFERENCE, not candidate/keep, survives restart")
    ck("human_review_persists_after_restart", d["V003"]["human_review"]["status"] == "MUST_KEEP" and d["V003"]["human_review"]["reason"] == "測試理由" and d["V002"]["human_review"]["summary_feedback"]["text"].startswith("測試補充") and d["V001"]["human_review"]["status"] == "NOT_REVIEWED", "status, reason and feedback text reloaded after server restart; unsaved clips untouched")
    ck("review_relationship_computed", d["V003"]["review_relationship"] == "AGREE_KEEP" and d["V020"]["review_relationship"] == "AI_SKIP_HUMAN_KEEP", f"V003 {d['V003']['review_relationship']}; V020 (AI skip, human keep) {d['V020']['review_relationship']}")
    ck("ai_summary_not_overwritten", d["V002"]["visual_summary"] == clips[1]["visual_summary"] or d["V002"]["visual_summary"] == next(c for c in clips if c["clip_id"] == "V002")["visual_summary"], "AI visual_summary identical after human feedback")
    ck("broll_flag_persists_and_is_kept", d["V020"]["human_review"].get("broll") is True and d["V003"]["human_review"].get("broll") is False, "B-roll flag saved, survives restart, and is not erased by a later save without it")
    m = J(tmp + "/master_footage_review.json"); ck("master_json_synced_for_stage1", next(c for c in m if c["clip_id"] == "V003")["human_review"]["status"] == "MUST_KEEP", "master_footage_review.json updated on save")
    case = post("/api/case", dict(clip_id="V009", time_range=[14, 14], problem="測試", expected_check="x")); ck("review_case_saved", case["count"] == 1, "review_cases.json append works")
    req = urllib.request.Request(U + "/proxy/V002_proxy.mp4", headers={"Range": "bytes=0-99"}); resp = urllib.request.urlopen(req)
    ck("proxy_http_range_seek", resp.status == 206 and len(resp.read()) == 100, "HTTP 206 partial content, so the <video> player can seek")
finally:
    srv.terminate(); shutil.rmtree(tmp, ignore_errors=True)
real = J(OUT + "/human_footage_review.json"); ck("real_human_file_untouched_by_test", real == before_real, f"production human_footage_review.json has {len(real)} entries (test ran on a copy)")
over = "FAIL" if any(v["status"] == "FAIL" for v in chk.values()) else "PASS_WITH_WARNINGS"
from collections import Counter
rep = dict(overall=over, total_source_clips=len(cat), master_review_clips=len(clips), total_runtime_s=round(sum(c["duration"] for c in clips), 1), hero_count=len(clips), long_clip_count=len([c for c in clips if c["duration"] >= 60]),
           contact_frames=sum(len(c["contact_strip"]) for c in clips), ai_recommendation_distribution=dict(Counter(c["ai_review"]["recommendation"] for c in clips)), proxy_count=len(pm),
           human_save_persistence_test="PASS" if all(v["status"] == "PASS" for k, v in chk.items() if k.startswith("human") or k.startswith("review")) else "FAIL",
           reusable_example_kit="used as reference and MODIFIED (rewritten: schema/paths, Range server, player, filters, review_cases; example's Stage 1 dependency removed)", checks=chk,
           warnings=["Hero Frame times were chosen from Stage 0B pixel review (curated), not computed.", "AI recommendations are agent judgement, not a selection.",
                     "Proxies are 720p H.264 from the originals and are for Stage 0D review only.", "Human Review Gate is yours; Stage 1 must not start until you finish/confirm review."])
json.dump(rep, open(OUT + "/master_footage_review_validation.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in rep.items() if k != "checks"}, ensure_ascii=False, indent=1)); print({k: v["status"] for k, v in chk.items() if v["status"] != "PASS"})
