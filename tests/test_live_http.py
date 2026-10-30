"""Real loopback HTTP traffic; no production server or external network."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from app import loadtest


def test_real_http_load_and_error_accounting():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == '/health' else 503)
            self.end_headers()
            self.wfile.write(b'ok')

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for path, expected in [('/health', 'passed'), ('/failure', 'failed')]:
            job = loadtest.start(f'http://127.0.0.1:{server.server_port}{path}', 20, 4, True)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                result = next(j for j in loadtest.jobs() if j['id'] == job['id'])
                if result['state'] not in {'queued', 'running'}:
                    break
                time.sleep(.02)
            assert result['state'] == expected
            assert result['completed'] == 20
            assert result['errors'] == (0 if expected == 'passed' else 20)
            assert result['p95_ms'] is not None
    finally:
        server.shutdown()
        server.server_close()
