import json
import os
from http.server import SimpleHTTPRequestHandler
import socketserver

HOST = '127.0.0.1'
PORT = int(os.environ.get('STAGE0D_PORT', '8080'))

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
            
            with open(master_path, 'r', encoding='utf-8') as f:
                clips = json.load(f)
                
            human_db = {}
            if os.path.exists(human_path):
                with open(human_path, 'r', encoding='utf-8') as f:
                    human_db = json.load(f)
                    
            for c in clips:
                cid = c['clip_id']
                if cid in human_db:
                    c['human_review'] = human_db[cid]
                    
                    ai_rec = c['ai_review']['recommendation']
                    h_stat = human_db[cid].get('status', 'NOT_REVIEWED')
                    if h_stat == 'IMPORTANT/MUST_REVIEW':
                        h_stat = 'MUST_REVIEW'
                        c['human_review']['status'] = h_stat
                    
                    if h_stat == "NOT_REVIEWED":
                        rel = "HUMAN_NOT_REVIEWED"
                    elif h_stat == "NO_PREFERENCE":
                        rel = "HUMAN_NO_PREFERENCE"
                    elif h_stat in ["CANDIDATE", "IMPORTANT", "MUST_REVIEW", "MUST_KEEP"] and ai_rec in ["STRONG_CANDIDATE", "CANDIDATE", "OPTIONAL"]:
                        rel = "AGREE_KEEP"
                    elif h_stat == "SKIP" and ai_rec in ["LIKELY_SKIP", "TECHNICAL_REJECT"]:
                        rel = "AGREE_SKIP"
                    elif h_stat in ["CANDIDATE", "IMPORTANT", "MUST_REVIEW", "MUST_KEEP"] and ai_rec in ["LIKELY_SKIP", "TECHNICAL_REJECT"]:
                        rel = "AI_SKIP_HUMAN_KEEP"
                    elif h_stat == "SKIP" and ai_rec in ["STRONG_CANDIDATE", "CANDIDATE"]:
                        rel = "AI_KEEP_HUMAN_SKIP"
                    else:
                        rel = "MIXED"
                    c['review_relationship'] = rel
                    
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
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
                with open(human_path, 'r', encoding='utf-8') as f:
                    db = json.load(f)
            else:
                db = {}
                
            cid = data['clip_id']
            summary_feedback = data.get('summary_feedback', {})
            summary_action = summary_feedback.get('action', 'NONE')
            if summary_action not in ['NONE', 'APPEND', 'CORRECT', 'REPLACE']:
                summary_action = 'NONE'

            human_status = data.get('status', 'NOT_REVIEWED')
            if human_status == 'IMPORTANT/MUST_REVIEW':
                human_status = 'MUST_REVIEW'
            allowed_statuses = ['NOT_REVIEWED', 'NO_PREFERENCE', 'CANDIDATE', 'IMPORTANT', 'MUST_REVIEW', 'MUST_KEEP', 'SKIP']
            if human_status not in allowed_statuses:
                human_status = 'NOT_REVIEWED'
            if (summary_action != 'NONE' or summary_feedback.get('text', '').strip()) and human_status == 'NOT_REVIEWED':
                human_status = 'NO_PREFERENCE'

            db[cid] = {
                'status': human_status,
                'reason': data.get('reason', ''),
                'summary_feedback': {
                    'action': summary_action,
                    'text': summary_feedback.get('text', ''),
                    'target_fields': summary_feedback.get('target_fields', []),
                    'affects_selection': False,
                    'updated_at': summary_feedback.get('updated_at')
                }
            }
            
            with open(human_path, 'w', encoding='utf-8') as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            return
        else:
            self.send_response(404)
            self.end_headers()

# Server runs in project root
with socketserver.TCPServer((HOST, PORT), ReviewHandler) as httpd:
    print(f"Server started at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    httpd.serve_forever()
