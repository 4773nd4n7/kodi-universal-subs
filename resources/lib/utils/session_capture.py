# -*- coding: utf-8 -*-
"""Loopback HTTP receiver and instruction page for the SubDivX browser-session capture.

The add-on service listens on 127.0.0.1 and serves:

* ``GET /`` - instructions with the browser script and a copy button;
* ``GET /subdivx-session.js`` - the browser script itself;
* ``POST /subdivx-session`` - the captured session blob.

The page is the only thing the user needs to know about: it contains the script to run.
"""

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CAPTURE_PATH = "/subdivx-session"
SCRIPT_PATH = "/subdivx-session.js"
DEFAULT_PORT = 39517
MAX_BODY_BYTES = 16 * 1024

INSTRUCTIONS_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Universal Subs - SubDivX session capture</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 46rem; line-height: 1.5; }}
 textarea {{ width: 100%; height: 18rem; font: 12px/1.4 ui-monospace, monospace; }}
 button {{ padding: .4rem 1rem; font-size: 1rem; }}
 code {{ background: #eee; padding: 0 .25rem; border-radius: 3px; }}
</style>
</head>
<body>
<h1>SubDivX browser session</h1>
<p>SubDivX is protected by Cloudflare, so Kodi cannot reach it on its own. Your browser can.</p>
<ol>
 <li>Copy the script below (use the button, or select the text).</li>
 <li>Open <a href="https://www.subdivx.com/" target="_blank" rel="noreferrer">subdivx.com</a> in
     another tab and wait until the page has loaded (the Cloudflare check must have passed).</li>
 <li>In the <strong>subdivx.com tab</strong> (cookies belong to that page, so this page cannot read
     them), open the developer tools (<code>F12</code>), switch to the <strong>Console</strong>,
     paste the script and press Enter.</li>
</ol>
<p><button id="copy" type="button">Copy script</button> <span id="status"></span></p>
<textarea id="script" readonly>{script}</textarea>
<p>Kodi shows a notification when the session arrives. If it does not, the script prints the blob:
paste it into <strong>Settings &rarr; Advanced &rarr; SubDivX browser session</strong>. The session
expires, so repeat these steps when SubDivX stops returning results.</p>
<script>
document.getElementById("copy").addEventListener("click", async () => {{
  const script = document.getElementById("script");
  try {{
    await navigator.clipboard.writeText(script.value);
    document.getElementById("status").textContent = "Copied.";
  }} catch (error) {{
    script.select();
    document.getElementById("status").textContent = "Press Ctrl+C to copy.";
  }}
}});
</script>
</body>
</html>
"""


def load_browser_script() -> str:
    path = Path(__file__).resolve().parents[2] / "subdivx-session.js"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "// resources/subdivx-session.js is missing from this installation."


class SessionCaptureHandler(BaseHTTPRequestHandler):
    """Serve the capture page and accept one base64 session blob from the browser."""

    server_version = "UniversalSubsSession/1.0"

    def log_message(self, format: str, *args) -> None:
        pass  # Kodi owns the log; a silent receiver is fine.

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send_text(200, self.server.page, "text/html; charset=utf-8")
        elif path == SCRIPT_PATH:
            self._send_text(200, self.server.script, "text/javascript; charset=utf-8")
        else:
            self._send_text(404, "Not found", "text/plain; charset=utf-8")

    def do_OPTIONS(self) -> None:
        # Chrome's Private Network Access preflight: an https page posting to loopback.
        self.send_response(204)
        self._write_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != CAPTURE_PATH:
            self._send_json(404, {"ok": False, "error": "unknown path"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"ok": False, "error": "invalid body size"})
            return
        try:
            blob = self.rfile.read(length).decode("utf-8").strip()
        except UnicodeDecodeError:
            self._send_json(400, {"ok": False, "error": "body is not UTF-8"})
            return
        handler = getattr(self.server, "on_session", None)
        if handler is None or not handler(blob):
            self._send_json(400, {"ok": False, "error": "session rejected"})
            return
        self._send_json(200, {"ok": True})

    def _write_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")

    def _send_text(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._write_cors_headers()
        self.end_headers()
        self.wfile.write(data)


class SessionCaptureServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, on_session, script: str):
        self.on_session = on_session
        self.script = script
        self.page = INSTRUCTIONS_TEMPLATE.format(script=html.escape(script, quote=False))
        super().__init__(address, SessionCaptureHandler)


def start_session_capture_server(on_session, port: int = DEFAULT_PORT, host: str = "127.0.0.1",
                                 script: str = None) -> SessionCaptureServer:
    """Start the receiver in a daemon thread; raises OSError when the port is unavailable."""
    server = SessionCaptureServer((host, port), on_session,
                                  load_browser_script() if script is None else script)
    thread = threading.Thread(target=server.serve_forever, name="subdivx-session-capture", daemon=True)
    thread.start()
    return server
