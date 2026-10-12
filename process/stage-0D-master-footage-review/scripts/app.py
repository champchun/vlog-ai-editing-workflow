#!/usr/bin/env python3
"""Stage 0D review server. Run from anywhere: python3 app.py  -> http://127.0.0.1:8080
Serves this folder (HTML/frames/proxy with HTTP Range for video seeking), autosaves human review to human_footage_review.json
and merges it into master_footage_review.json (AI and human stay separate; no selected flag)."""
import json, os, re, tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

DIR = os.environ.get("STAGE0D_DIR", os.path.dirname(os.path.abspath(__file__)))
HOST, PORT = "127.0.0.1", int(os.environ.get("STAGE0D_PORT", "8080"))
MASTER, HUMAN, CASES = (os.path.join(DIR, n) for n in ("master_footage_review.json", "human_footage_review.json", "review_cases.json"))
STATUSES = ["NOT_REVIEWED", "NO_PREFERENCE", "CANDIDATE", "IMPORTANT", "MUST_REVIEW", "MUST_KEEP", "SKIP"]
ACTIONS = ["NONE", "APPEND", "CORRECT", "REPLACE"]
AI_KEEP, AI_SKIP, H_KEEP = {"STRONG_CANDIDATE", "CANDIDATE", "OPTIONAL"}, {"LIKELY_SKIP", "TECHNICAL_REJECT"}, {"CANDIDATE", "IMPORTANT", "MUST_REVIEW", "MUST_KEEP"}

def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return default

def atomic(p, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

def relation(ai, h):
    if h == "NOT_REVIEWED": return "HUMAN_NOT_REVIEWED"
    if h == "NO_PREFERENCE": return "HUMAN_NO_PREFERENCE"
    if h in H_KEEP: return "AGREE_KEEP" if ai in AI_KEEP else "AI_SKIP_HUMAN_KEEP"
    if h == "SKIP": return "AGREE_SKIP" if ai in AI_SKIP else "AI_KEEP_HUMAN_SKIP"
    return "HUMAN_NOT_REVIEWED"

def merged():
    clips, db = load(MASTER, []), load(HUMAN, {})
    for c in clips:
        if c["clip_id"] in db: c["human_review"] = db[c["clip_id"]]
        c["review_relationship"] = relation(c["ai_review"]["recommendation"], c["human_review"].get("status", "NOT_REVIEWED"))
    return clips

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=DIR, **k)
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()
    def js(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/": self.path = "/master_footage_review.html"
        if path == "/api/data": return self.js(merged())
        if path == "/api/cases": return self.js(load(CASES, []))
        if path.startswith("/proxy/") and self.headers.get("Range"): return self.ranged(path)
        return super().do_GET()
    def ranged(self, path):   # HTTP Range so <video> can seek
        f = os.path.join(DIR, os.path.normpath(path.lstrip("/")))
        if not f.startswith(DIR) or not os.path.isfile(f): self.send_error(404); return
        size = os.path.getsize(f); m = re.match(r"bytes=(\d*)-(\d*)", self.headers["Range"])
        a = int(m.group(1)) if m and m.group(1) else 0; b = int(m.group(2)) if m and m.group(2) else size - 1; b = min(b, size - 1)
        self.send_response(206); self.send_header("Content-Type", "video/mp4"); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {a}-{b}/{size}"); self.send_header("Content-Length", str(b - a + 1)); self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(a); left = b - a + 1
            while left > 0:
                d = fh.read(min(1 << 20, left))
                if not d: break
                try: self.wfile.write(d)
                except (BrokenPipeError, ConnectionResetError): break
                left -= len(d)
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); data = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/save":
            cid = data.get("clip_id")
            if cid not in {c["clip_id"] for c in load(MASTER, [])}: return self.js({"error": "unknown clip_id"}, 400)
            db = load(HUMAN, {}); old = db.get(cid) or {}
            fb = data.get("summary_feedback") or old.get("summary_feedback") or {}; act = fb.get("action", "NONE"); act = act if act in ACTIONS else "NONE"
            status = data["status"] if "status" in data else old.get("status", "NOT_REVIEWED"); status = status if status in STATUSES else "NOT_REVIEWED"
            broll = bool(data["broll"]) if "broll" in data else bool(old.get("broll", False))   # keep existing flag when a payload omits it
            if (act != "NONE" or (fb.get("text") or "").strip() or broll) and status == "NOT_REVIEWED": status = "NO_PREFERENCE"   # summary-only / B-roll flag never implies a keep
            # per-segment marks (merged into existing ones, never wiping other segments)
            valid = {s["segment_id"] for c in load(MASTER, []) if c["clip_id"] == cid for s in c.get("segments", [])}
            segs = dict(old.get("segment_reviews") or {})
            for sid, s in (data.get("segment_reviews") or {}).items():
                if sid in valid:
                    st = s.get("status", "NOT_REVIEWED"); st = st if st in STATUSES else "NOT_REVIEWED"
                    segs[sid] = dict(status=st, broll=bool(s.get("broll", False)), updated_at=datetime.now(timezone.utc).isoformat())
            source = old.get("status_source") or ("manual" if old.get("status", "NOT_REVIEWED") != "NOT_REVIEWED" else "none")
            if "status" in data and status != "NOT_REVIEWED": source = "manual"
            if "status" in data and status == "NOT_REVIEWED" and not data.get("segment_reviews"): source = "none"
            if data.get("segment_reviews") and source != "manual":      # derive the clip-level status from its segments until the user sets one by hand
                marked = [v for v in segs.values() if v["status"] != "NOT_REVIEWED"]
                if any(v["status"] == "CANDIDATE" for v in marked): status, broll, source = "CANDIDATE", False, "derived_from_segments"
                elif any(v["status"] == "NO_PREFERENCE" and v["broll"] for v in marked): status, broll, source = "NO_PREFERENCE", True, "derived_from_segments"
                elif len(marked) == len(valid) and marked and all(v["status"] == "SKIP" for v in marked): status, broll, source = "SKIP", False, "derived_from_segments"
            db[cid] = dict(status=status, broll=broll, status_source=source, reason=data.get("reason", old.get("reason", "")), segment_reviews=segs,
                           summary_feedback=dict(action=act, text=fb.get("text", ""), target_fields=fb.get("target_fields", ["visual_summary"]),
                           affects_selection=False, updated_at=fb.get("updated_at") or datetime.now(timezone.utc).isoformat()))
            atomic(HUMAN, db); atomic(MASTER, merged())      # keep master_footage_review.json (Stage 1 handoff) in sync
            return self.js({"status": "ok", "saved_status": status})
        if self.path == "/api/case":
            cases = load(CASES, []); cases.append(dict(clip_id=data.get("clip_id"), time_range=data.get("time_range"), problem=data.get("problem"), expected_check=data.get("expected_check"),
                                                       created_at=datetime.now(timezone.utc).isoformat(), note="regression case only; does not rewrite Stage 0 facts"))
            atomic(CASES, cases); return self.js({"status": "ok", "count": len(cases)})
        self.send_error(404)

if __name__ == "__main__":
    print(f"Stage 0D 審片主控台：http://{HOST}:{PORT}  （Ctrl+C 結束）")
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
