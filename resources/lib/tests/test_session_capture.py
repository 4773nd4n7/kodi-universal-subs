# -*- coding: utf-8 -*-

"""Offline tests for the loopback receiver that captures the SubDivX browser session."""

import json
import unittest
import urllib.error
import urllib.request

from resources.lib.utils.session_capture import (CAPTURE_PATH,
                                                  start_session_capture_server)


def accept(sink=None):
    """A session handler that accepts everything and optionally records (text, user agent)."""
    def handler(blob, browser_user_agent=""):
        if sink is not None:
            sink.append((blob, browser_user_agent))
        return ""
    return handler


def reject(reason: str):
    """A session handler that refuses with that reason, the way the Kodi service does."""
    return lambda blob, browser_user_agent="": reason


class SessionCaptureServerTest(unittest.TestCase):

    def start(self, handler):
        server = start_session_capture_server(handler, port=0)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    @staticmethod
    def url(server, path: str = CAPTURE_PATH) -> str:
        return "http://127.0.0.1:%d%s" % (server.server_address[1], path)

    def test_post_delivers_the_pasted_request(self) -> None:
        received = []
        server = self.start(accept(received))
        pasted = "curl 'https://www.subdivx.com/' -H 'cookie: cf_clearance=token'"
        request = urllib.request.Request(self.url(server), data=pasted.encode("utf-8"),
                                         headers={"Content-Type": "text/plain"})
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(json.loads(response.read().decode("utf-8")), {"ok": True})
        self.assertEqual(received, [(pasted, "")])

    def test_the_page_supplies_the_browser_user_agent(self) -> None:
        # A lone cf_clearance value is useless without the user agent it was issued to, and the page
        # runs in that same browser, so it reports its own.
        received = []
        server = self.start(accept(received))
        payload = json.dumps({"text": "ChXpYt3T", "ua": "Mozilla/5.0 Test"})
        request = urllib.request.Request(self.url(server), data=payload.encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(json.loads(response.read().decode("utf-8")), {"ok": True})
        self.assertEqual(received, [("ChXpYt3T", "Mozilla/5.0 Test")])

    def test_rejection_reason_reaches_the_page(self) -> None:
        # "session rejected" told the user nothing; the page now shows the actual reason.
        reason = "the pasted cookie header has no SubDivX cookie in it"
        server = self.start(reject(reason))
        request = urllib.request.Request(self.url(server), data=b"x",
                                         headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 400)
        payload = json.loads(context.exception.read().decode("utf-8"))
        self.assertEqual(payload, {"ok": False, "error": reason})

    def test_empty_body_is_rejected(self) -> None:
        server = self.start(accept())
        request = urllib.request.Request(self.url(server), data=b"",
                                         headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 400)

    def test_unknown_post_is_not_found(self) -> None:
        server = self.start(accept())
        request = urllib.request.Request(self.url(server, "/elsewhere"), data=b"x",
                                         headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 404)

    def test_index_page_is_never_cached(self) -> None:
        # Otherwise a browser keeps showing the capture steps of a previous add-on version.
        server = self.start(accept())
        with urllib.request.urlopen(self.url(server, "/"), timeout=5) as response:
            self.assertIn("no-store", response.headers.get("Cache-Control", ""))

    def test_index_page_explains_the_devtools_capture(self) -> None:
        server = self.start(accept())
        with urllib.request.urlopen(self.url(server, "/"), timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers.get("Content-Type", ""))
            page = response.read().decode("utf-8")
        # The simplest route leads: copy the value from Application -> Cookies; the page adds the UA.
        self.assertIn("Application", page)
        self.assertIn("cf_clearance", page)
        self.assertIn("Send to Kodi", page)
        self.assertIn("HttpOnly", page)
        self.assertIn("subdivx.com", page)
        self.assertIn("navigator.userAgent", page)
        # The whole-request copy stays documented as the alternative.
        self.assertIn("Network", page)

    def test_the_page_script_endpoint_is_gone(self) -> None:
        # A page script cannot read an HttpOnly clearance, so the old endpoint must not come back.
        server = self.start(accept())
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.url(server, "/subdivx-session.js"), timeout=5)
        self.assertEqual(context.exception.code, 404)

    def test_unknown_get_is_not_found(self) -> None:
        server = self.start(accept())
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.url(server, "/nope"), timeout=5)
        self.assertEqual(context.exception.code, 404)

    def test_options_allows_the_private_network_preflight(self) -> None:
        server = self.start(accept())
        request = urllib.request.Request(self.url(server), method="OPTIONS")
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers.get("Access-Control-Allow-Private-Network"), "true")


if __name__ == '__main__':
    unittest.main()
