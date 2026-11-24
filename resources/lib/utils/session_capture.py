# -*- coding: utf-8 -*-
"""Loopback HTTP receiver and instruction page for the SubDivX browser-session capture.

The add-on service listens on 127.0.0.1 and serves:

* ``GET /`` - instructions plus the paste box that sends a copied request back;
* ``POST /subdivx-session`` - a request copied from the browser's developer tools, or a stored
  session blob.

A page script cannot do the capture itself: Cloudflare marks ``cf_clearance`` as HttpOnly, so
``document.cookie`` never contains it. The request headers that the Network tab can copy are the
only browser-side source of that cookie.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

CAPTURE_PATH = "/subdivx-session"
DEFAULT_PORT = 39517
MAX_BODY_BYTES = 16 * 1024

INSTRUCTIONS_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Universal Subs - SubDivX session capture</title>
<style>
 body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 46rem; line-height: 1.5; }
 textarea { width: 100%; height: 12rem; font: 12px/1.4 ui-monospace, monospace; }
 button { padding: .4rem 1rem; font-size: 1rem; }
 code { background: #eee; padding: 0 .25rem; border-radius: 3px; }
</style>
</head>
<body>
<h1>SubDivX browser session</h1>
<p>SubDivX is protected by Cloudflare, so Kodi cannot reach it on its own. Your browser can: it
solves the challenge and keeps the clearance cookie, but Cloudflare marks that cookie
<code>HttpOnly</code>, so no script running in the page can read it. Copy the value out by hand:</p>
<ol>
 <li>Open <a href="https://www.subdivx.com/" target="_blank" rel="noreferrer">subdivx.com</a> in
     another tab and wait until it has loaded (the Cloudflare check must have passed).</li>
 <li>Press <code>F12</code>, open <strong>Application &rarr; Cookies &rarr;
     https://www.subdivx.com</strong>, select the <code>cf_clearance</code> row and copy its
     <strong>value</strong>.</li>
 <li>Paste that value below and press <strong>Send to Kodi</strong>. This page attaches your
     browser's user agent, which Cloudflare requires next to the clearance.</li>
</ol>
<textarea id="paste" spellcheck="false" placeholder="Paste the cf_clearance value here"></textarea>
<p><button id="send" type="button">Send to Kodi</button> <span id="status"></span></p>
<p>Only need the clearance to work? That is all. If you also want SubDivX's own login session, or
you are capturing from a browser other than the one this page is open in, use <strong>Network</strong>
instead: pick a request made after the page loaded, right-click it, <strong>Copy &rarr; Copy as
cURL</strong>, and paste that here &mdash; a copied request carries the cookie header and the user
agent together.</p>
<p>Kodi shows a notification when the session arrives. If Kodi is not running, paste the same text
into <strong>Settings &rarr; Advanced &rarr; SubDivX browser session</strong>. The session expires, so
repeat these steps when SubDivX stops returning results. Anyone holding it can act as this browser
session, so do not share it.</p>
<script>
const status = document.getElementById("status");
document.getElementById("send").addEventListener("click", async () => {
  const text = document.getElementById("paste").value.trim();
  if (!text) {
    status.textContent = "Paste the cf_clearance value first.";
    return;
  }
  status.textContent = "Sending...";
  try {
    const response = await fetch("/subdivx-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, ua: navigator.userAgent }),
    });
    const result = await response.json();
    status.textContent = result.ok
      ? "Session sent to Kodi."
      : "Kodi rejected it: " + (result.error || "unknown reason");
  } catch (error) {
    status.textContent = "Could not reach Kodi: " + error;
  }
});
</script>
</body>
</html>
"""


def split_capture_payload(body: str) -> Tuple[str, str]:
    """The pasted text and the user agent the page reported.

    The page posts JSON so the browser can attach ``navigator.userAgent``: a lone ``cf_clearance``
    value is useless to Cloudflare without it. A raw text body (a plain POST from a script or curl)
    is still accepted, in which case no user agent is known.
    """
    if body.startswith("{"):
        try:
            data = json.loads(body)
        except ValueError:
            return body, ""
        if isinstance(data, dict) and isinstance(data.get("text"), str):
            user_agent = data.get("ua")
            return data["text"], user_agent if isinstance(user_agent, str) else ""
    return body, ""


class SessionCaptureHandler(BaseHTTPRequestHandler):
    """Serve the capture page and accept one pasted session from the browser."""

    server_version = "UniversalSubsSession/1.0"

    def log_message(self, format: str, *args) -> None:
        pass  # Kodi owns the log; a silent receiver is fine.

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send_text(200, self.server.page, "text/html; charset=utf-8")
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
            body = self.rfile.read(length).decode("utf-8").strip()
        except UnicodeDecodeError:
            self._send_json(400, {"ok": False, "error": "body is not UTF-8"})
            return
        blob, browser_user_agent = split_capture_payload(body)
        handler = getattr(self.server, "on_session", None)
        if handler is None:
            self._send_json(400, {"ok": False, "error": "no session handler"})
            return
        error = handler(blob, browser_user_agent)
        if error:
            self._send_json(400, {"ok": False, "error": error})
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
        # The page changes with every add-on upgrade; a cached copy would keep showing old steps.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self._write_cors_headers()
        self.end_headers()
        self.wfile.write(data)


class SessionCaptureServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, on_session):
        self.on_session = on_session
        self.page = INSTRUCTIONS_PAGE
        super().__init__(address, SessionCaptureHandler)


def start_session_capture_server(on_session, port: int = DEFAULT_PORT,
                                 host: str = "127.0.0.1") -> SessionCaptureServer:
    """Start the receiver in a daemon thread; raises OSError when the port is unavailable."""
    server = SessionCaptureServer((host, port), on_session)
    thread = threading.Thread(target=server.serve_forever, name="subdivx-session-capture", daemon=True)
    thread.start()
    return server
