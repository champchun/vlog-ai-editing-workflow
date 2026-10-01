"""Stage 0D Review Console server (adapted from the Reusable Kit prototype).
Run from anywhere:  python3 app.py     -> http://127.0.0.1:8080
Serves the folder this file lives in (stage0d_master_review/), with HTTP Range support for <video>.
Human Review is autosaved to human_footage_review.json and merged into master_footage_review.json
(AI review and Human review stay separate fields; nothing upstream is touched)."""
import json, os, re, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
HOST, PORT = '127.0.0.1', int(os.environ.get('STAGE0D_PORT', '8080'))
MASTER, HUMAN, CASES = BASE / 'master_footage_review.json', BASE / 'human_footage_review.json', BASE / 'review_cases.json'
LOCK = threading.Lock()
STATUSES = ['NOT_REVIEWED', 'NO_PREFERENCE', 'CANDIDATE', 'IMPORTANT', 'MUST_REVIEW', 'MUST_KEEP', 'SKIP']
ACTIONS = ['NONE', 'APPEND', 'CORRECT', 'REPLACE']
KEEP = ['CANDIDATE', 'IMPORTANT', 'MUST_REVIEW', 'MUST_KEEP']


def relationship(ai_rec, status):
    if status == 'NOT_REVIEWED': return 'HUMAN_NOT_REVIEWED'
    if status == 'NO_PREFERENCE': return 'HUMAN_NO_PREFERENCE'
    ai_keep = ai_rec in ('STRONG_CANDIDATE', 'CANDIDATE', 'OPTIONAL')
    if status in KEEP: return 'AGREE_KEEP' if ai_keep else 'AI_SKIP_HUMAN_KEEP'
    return 'AI_KEEP_HUMAN_SKIP' if ai_rec in ('STRONG_CANDIDATE', 'CANDIDATE') else 'AGREE_SKIP'


def read_json(path, default):
    return json.load(open(path, encoding='utf-8')) if path.exists() else default


def write_json(path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def merged(clips, db):
    for c in clips:
        h = db.get(c['clip_id'])
        if not h: continue
        h = dict(h)
        if h.get('status') == 'IMPORTANT/MUST_REVIEW': h['status'] = 'MUST_REVIEW'
        h.setdefault('segment_reviews', {})
        c['human_review'] = h
        rec = c['ai_review']['recommendation']
        c['review_relationship'] = relationship(rec, h['status'])
        c['segment_relationships'] = {sid: relationship(rec, s.get('status', 'NOT_REVIEWED')) for sid, s in h['segment_reviews'].items()}
    return clips


def merge_master():
    """Rewrite master_footage_review.json with the current Human Review (Stage 1 reads this file)."""
    with LOCK:
        write_json(MASTER, merged(read_json(MASTER, []), read_json(HUMAN, {})))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(BASE), **k)

    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/': self.path = '/master_footage_review.html'
        elif path == '/api/data':
            with LOCK:
                return self._json(merged(read_json(MASTER, []), read_json(HUMAN, {})))
        elif path == '/api/cases':
            return self._json(read_json(CASES, []))
        elif path.startswith('/proxy/') and 'Range' in self.headers:
            return self._range(BASE / path.lstrip('/').replace('%20', ' '))
        return super().do_GET()

    def _range(self, f):
        m = re.match(r'bytes=(\d*)-(\d*)', self.headers['Range'])
        if not f.is_file() or not m: self.send_error(404); return
        size = f.stat().st_size
        a = int(m.group(1)) if m.group(1) else max(size - int(m.group(2)), 0)
        b = min(int(m.group(2)), size - 1) if m.group(1) and m.group(2) else size - 1
        self.send_response(206)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Range', f'bytes {a}-{b}/{size}')
        self.send_header('Content-Length', str(b - a + 1))
        self.end_headers()
        with open(f, 'rb') as fh:
            fh.seek(a); left = b - a + 1
            try:
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if self.path == '/api/save':
            cid = data['clip_id']
            fb = data.get('summary_feedback') or {}
            action = fb.get('action', 'NONE')
            if action not in ACTIONS: action = 'NONE'
            status = data.get('status', 'NOT_REVIEWED')
            if status == 'IMPORTANT/MUST_REVIEW': status = 'MUST_REVIEW'
            if status not in STATUSES: status = 'NOT_REVIEWED'
            if (action != 'NONE' or fb.get('text', '').strip()) and status == 'NOT_REVIEWED': status = 'NO_PREFERENCE'
            segs = {}
            for sid, s in (data.get('segment_reviews') or {}).items():
                st = s.get('status', 'NOT_REVIEWED')
                if st not in STATUSES: st = 'NOT_REVIEWED'
                if st != 'NOT_REVIEWED' or s.get('reason', '').strip():
                    segs[sid] = {'status': st, 'reason': s.get('reason', ''), 'updated_at': s.get('updated_at')}
            with LOCK:
                db = read_json(HUMAN, {})
                db[cid] = {'status': status, 'reason': data.get('reason', ''), 'segment_reviews': segs,
                           'summary_feedback': {'action': action, 'text': fb.get('text', ''), 'target_fields': fb.get('target_fields', []),
                                                'affects_selection': False, 'updated_at': fb.get('updated_at')}}
                write_json(HUMAN, db)
            merge_master()
            return self._json({'status': 'ok', 'saved_status': status})
        if self.path == '/api/case':
            with LOCK:
                cases = read_json(CASES, [])
                cases.append({'case_id': f'RC{len(cases) + 1:04d}', 'clip_id': data['clip_id'], 'start': data.get('start'), 'end': data.get('end'),
                              'issue': data.get('issue', ''), 'expected': data.get('expected', ''),
                              'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'rewrites_stage0_facts': False})
                write_json(CASES, cases)
            return self._json({'status': 'ok', 'cases': len(cases)})
        self.send_error(404)


if __name__ == '__main__':
    merge_master()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Stage 0D 審片主控台：http://{HOST}:{PORT}   （Ctrl+C 結束）')
    srv.serve_forever()
