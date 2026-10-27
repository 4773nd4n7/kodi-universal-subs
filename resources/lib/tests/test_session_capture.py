# -*- coding: utf-8 -*-

"""Hermetic tests for the loopback receiver that captures the SubDivX browser session."""

import json
import unittest
import urllib.error
import urllib.request

from resources.lib.utils.session_capture import (CAPTURE_PATH, SCRIPT_PATH,
                                                  start_session_capture_server)

SCRIPT = "console.log('subdivx');"


class SessionCaptureServerTest(unittest.TestCase):

    def start(self, handler):
        server = start_session_capture_server(handler, port=0, script=SCRIPT)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    @staticmethod
    def url(server, path: str = CAPTURE_PATH) -> str:
        return "http://127.0.0.1:%d%s" % (server.server_address[1], path)

    def test_post_delivers_the_blob(self) -> None:
        received = []
        server = self.start(lambda blob: received.append(blob) or True)
        request = urllib.request.Request(self.url(server), data=b"c2Vzc2lvbg==",
                                         headers={"Content-Type": "text/plain"})
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(json.loads(response.read().decode("utf-8")), {"ok": True})
        self.assertEqual(received, ["c2Vzc2lvbg=="])

    def test_rejected_session_is_reported(self) -> None:
        server = self.start(lambda blob: False)
        request = urllib.request.Request(self.url(server), data=b"garbage",
                                         headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 400)

    def test_empty_body_is_rejected(self) -> None:
        server = self.start(lambda blob: True)
        request = urllib.request.Request(self.url(server), data=b"",
                                         headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 400)

    def test_unknown_post_is_not_found(self) -> None:
        server = self.start(lambda blob: True)
        request = urllib.request.Request(self.url(server, "/elsewhere"), data=b"x",
                                         headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 404)

    def test_index_page_contains_the_script_and_copy_button(self) -> None:
        server = self.start(lambda blob: True)
        with urllib.request.urlopen(self.url(server, "/"), timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers.get("Content-Type", ""))
            page = response.read().decode("utf-8")
        self.assertIn(SCRIPT, page)
        self.assertIn("Copy script", page)
        self.assertIn("subdivx.com", page)

    def test_script_endpoint_returns_the_browser_script(self) -> None:
        server = self.start(lambda blob: True)
        with urllib.request.urlopen(self.url(server, SCRIPT_PATH), timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("javascript", response.headers.get("Content-Type", ""))
            self.assertEqual(response.read().decode("utf-8"), SCRIPT)

    def test_unknown_get_is_not_found(self) -> None:
        server = self.start(lambda blob: True)
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.url(server, "/nope"), timeout=5)
        self.assertEqual(context.exception.code, 404)

    def test_browser_script_only_copies_the_needed_cookies(self) -> None:
        from resources.lib.utils.session_capture import load_browser_script
        script = load_browser_script()
        self.assertIn("cf_clearance", script)
        self.assertIn('"PHPSESSID"', script)
        self.assertIn("document.cookie", script)
        # The cookie header must be filtered, not the raw document.cookie value.
        self.assertIn(".filter((part) => wanted.includes(part.split(\"=\")[0]))", script)


    def test_options_allows_the_private_network_preflight(self) -> None:
        server = self.start(lambda blob: True)
        request = urllib.request.Request(self.url(server), method="OPTIONS")
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers.get("Access-Control-Allow-Private-Network"), "true")


if __name__ == '__main__':
    unittest.main()
