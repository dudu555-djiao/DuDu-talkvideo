#!/usr/bin/env python3
"""Serve one episode locally, including byte ranges for audio/video seeking."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re

class Handler(SimpleHTTPRequestHandler):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path)
    parser.add_argument('--port', type=int, default=8866)
    args = parser.parse_args()
    episode = args.episode.expanduser().resolve()
    if not (episode/'review/index.html').is_file():
        parser.error('先运行 build_review.py 生成 review/index.html。')
    def factory(*a, **kw):
        return Handler(*a, directory=str(episode), **kw)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), factory)
    print(f'http://127.0.0.1:{server.server_port}/review/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
