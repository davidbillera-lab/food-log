#!/usr/bin/env python3
"""Serves the food log app, proxies Anthropic API calls, and stores food log data in memory."""
import http.server, json, urllib.request, urllib.error, os

# Load .env for local development (Render sets env vars directly in its dashboard)
def _load_dotenv():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass

_load_dotenv()
PORT = int(os.environ.get('PORT', 8080))
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

food_data = {}  # in-memory food log store; survives page reloads, cleared on server restart

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/data':
            result = json.dumps(food_data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(result)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/proxy/messages':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            # Prefer server-side key from .env / Render env vars; fall back to client header
            api_key = API_KEY or self.headers.get('x-api-key', '')
            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=body,
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                method='POST'
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    result = resp.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(result)
            except urllib.error.HTTPError as e:
                result = e.read()
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(result)
        elif self.path == '/data':
            global food_data
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                food_data = json.loads(body)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-api-key, anthropic-version')
        self.end_headers()

    def log_message(self, fmt, *args):
        print(fmt % args)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
with http.server.HTTPServer(('', PORT), Handler) as httpd:
    print(f'Serving at http://localhost:{PORT}')
    httpd.serve_forever()
