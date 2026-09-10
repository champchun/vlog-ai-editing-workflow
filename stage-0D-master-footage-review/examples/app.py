import json
import os
from http.server import SimpleHTTPRequestHandler
import socketserver

PORT = 8080

class ReviewHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Default translation
        path = super().translate_path(path)
        # If it's a request for frames, proxy, json, html, map to stage0d_master_review
        rel_path = os.path.relpath(path, os.getcwd())
        if rel_path in ['master_footage_review.html', 'master_footage_review.json', 'human_footage_review.json'] or rel_path.startswith('frames') or rel_path.startswith('proxy'):
            return os.path.join(os.getcwd(), 'stage0d_master_review', rel_path)
        return path

    def do_GET(self):
        if self.path == '/':
            self.path = '/master_footage_review.html'
        elif self.path == '/api/data':
            master_path = 'stage0d_master_review/master_footage_review.json'
            human_path = 'stage0d_master_review/human_footage_review.json'
            
            with open(master_path, 'r') as f:
                clips = json.load(f)
                
            human_db = {}
            if os.path.exists(human_path):
                with open(human_path, 'r') as f:
                    human_db = json.load(f)
                    
            for c in clips:
                cid = c['clip_id']
                if cid in human_db:
                    c['human_review'] = human_db[cid]
                    
                    ai_rec = c['ai_review']['recommendation']
                    h_stat = human_db[cid]['status']
                    
                    if h_stat == "NOT_REVIEWED":
                        rel = "HUMAN_NOT_REVIEWED"
                    elif h_stat in ["CANDIDATE", "IMPORTANT", "MUST_KEEP"] and ai_rec in ["STRONG_CANDIDATE", "CANDIDATE", "OPTIONAL"]:
                        rel = "AGREE_KEEP"
                    elif h_stat == "SKIP" and ai_rec in ["LIKELY_SKIP", "TECHNICAL_REJECT"]:
                        rel = "AGREE_SKIP"
                    elif h_stat in ["CANDIDATE", "IMPORTANT", "MUST_KEEP"] and ai_rec in ["LIKELY_SKIP", "TECHNICAL_REJECT"]:
                        rel = "AI_SKIP_HUMAN_KEEP"
                    elif h_stat == "SKIP" and ai_rec in ["STRONG_CANDIDATE", "CANDIDATE"]:
                        rel = "AI_KEEP_HUMAN_SKIP"
                    else:
                        rel = "MIXED"
                    c['review_relationship'] = rel
                    
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(clips).encode('utf-8'))
            return
            
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            human_path = 'stage0d_master_review/human_footage_review.json'
            if os.path.exists(human_path):
                with open(human_path, 'r') as f:
                    db = json.load(f)
            else:
                db = {}
                
            cid = data['clip_id']
            db[cid] = {
                'status': data['status'],
                'reason': data['reason']
            }
            
            with open(human_path, 'w') as f:
                json.dump(db, f, indent=2)
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            return
        else:
            self.send_response(404)
            self.end_headers()

# Server runs in project root
with socketserver.TCPServer(("", PORT), ReviewHandler) as httpd:
    print(f"Server started at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    httpd.serve_forever()
