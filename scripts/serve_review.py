#!/usr/bin/env python3
"""Serve one episode locally, including byte ranges for audio/video seeking."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import json
import secrets
from urllib.parse import urlsplit
from feedback_store import FeedbackStore, FeedbackConflict

class Handler(SimpleHTTPRequestHandler):
    def json_response(self, status, value):
        raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def local_request(self):
        host = self.headers.get('Host', '')
        try:
            parsed = urlsplit('http://' + host)
            valid = parsed.hostname in {'localhost', '127.0.0.1'} and parsed.port == self.server.server_port
        except ValueError:
            valid = False
        if not valid:
            return False
        origin = self.headers.get('Origin')
        return (not origin or origin == 'http://' + host) and self.headers.get('Sec-Fetch-Site') != 'cross-site'

    def do_GET(self):
        if urlsplit(self.path).path == '/api/workbench/feedback':
            if not self.local_request():
                return self.json_response(403, {'error': '仅当前本机工作台可读取意见。'})
            try:
                return self.json_response(200, {'projectId': self.server.feedback.project_id,
                                               'writeToken': self.server.write_token,
                                               'snapshot': self.server.feedback.load()})
            except (ValueError, OSError) as error:
                return self.json_response(500, {'error': str(error)})
        return super().do_GET()

    def do_POST(self):
        route = urlsplit(self.path).path
        if route not in {'/api/workbench/feedback', '/api/workbench/feedback/assets'}:
            return self.json_response(404, {'error': '未知保存接口。'})
        if not self.local_request() or self.headers.get('X-Workbench-Token') != self.server.write_token:
            return self.json_response(403, {'error': '保存请求须来自当前本机工作台。'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.json_response(415, {'error': '保存请求须使用 JSON。'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 192 * 1024 * 1024:
                return self.json_response(413, {'error': '本次保存超过192MB，请拆分附件。'})
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError('请求须为对象。')
            if route.endswith('/assets'):
                return self.json_response(200, self.server.feedback.upload(value))
            saved = self.server.feedback.save(value)
            return self.json_response(200, {'revision': saved['revision'], 'savedAt': saved['savedAt'], 'path': 'feedback/latest.json'})
        except FeedbackConflict as error:
            return self.json_response(409, {'error': str(error), 'revision': error.revision, 'conflictPath': error.path})
        except (ValueError, KeyError, TypeError) as error:
            return self.json_response(400, {'error': str(error)})
        except OSError as error:
            return self.json_response(500, {'error': '项目文件保存失败：' + str(error)})

    def send_head(self):
        self.remaining = None
        path = Path(self.translate_path(self.path))
        value = self.headers.get('Range')
        if not path.is_file() or not value:
            return super().send_head()
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
        if not match or not any(match.groups()):
            self.send_error(416)
            return None
        size = path.stat().st_size
        start, end = match.groups()
        start, end = (max(0, size-int(end)), size-1) if not start else (int(start), min(size-1, int(end)) if end else size-1)
        if start >= size or end < start:
            self.send_error(416)
            return None
        stream = path.open('rb')
        stream.seek(start)
        self.remaining = end-start+1
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(self.remaining))
        self.end_headers()
        return stream

    def copyfile(self, source, output):
        try:
            if self.remaining is None:
                return super().copyfile(source, output)
            while self.remaining:
                block = source.read(min(1048576, self.remaining))
                if not block:
                    break
                output.write(block)
                self.remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_):
        pass


def create_server(episode, port):
    episode = Path(episode).resolve()
    def factory(*a, **kw):
        return Handler(*a, directory=str(episode), **kw)
    server = ThreadingHTTPServer(('127.0.0.1', port), factory)
    server.feedback = FeedbackStore(episode)
    server.write_token = secrets.token_urlsafe(32)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path)
    parser.add_argument('--port', type=int, default=8866)
    args = parser.parse_args()
    episode = args.episode.expanduser().resolve()
    if not (episode/'review/index.html').is_file():
        parser.error('先运行 build_review.py 生成 review/index.html。')
    server = create_server(episode, args.port)
    print(f'http://127.0.0.1:{server.server_port}/review/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
