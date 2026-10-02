#!/usr/bin/env python3
"""Serve storyboard and persist Human Review to storyboard_human_review.json (bound to decision hashes)."""
import json, http.server, functools, datetime, hashlib
from pathlib import Path
OUT = Path(__file__).resolve().parents[3]/"process/workspace/project-output/stage1_review/storyboard"
HF = OUT/"storyboard_human_review.json"
class H(http.server.SimpleHTTPRequestHandler):
    def _j(self, o):
        b = json.dumps(o, ensure_ascii=False).encode(); self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/api/review": return self._j(json.load(open(HF)) if HF.exists() else {})
        if self.path == "/": self.path = "/storyboard.html"
        return super().do_GET()
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        hs = json.load(open(OUT/"storyboard_validation.json"))["hashes"]
        n = len(d["shots"]); fails = [k for k,v in d["shots"].items() if v.get("verdict")=="FAIL"]
        json.dump({"stage":"1R","reviewed_at":datetime.datetime.now().isoformat(timespec="seconds"),"hashes":hs,
                   "overall":d.get("overall",""),"shots":d["shots"],"fail_shots":fails}, open(HF,"w"), ensure_ascii=False, indent=1)
        self._j({"saved": n})
if __name__ == "__main__":
    print("http://127.0.0.1:8081")
    http.server.ThreadingHTTPServer(("127.0.0.1",8081), functools.partial(H, directory=str(OUT))).serve_forever()
