# -*- coding: utf-8 -*-

"""Live tests for the SubDivX provider.

SubDivX is a Spanish-only site, so the movie search runs in Spanish and there is no TV show
coverage: this provider turns an episode request into the literal text ``"<show> S01E01"``, which
the site does not understand. The assertions live in ``OnlineSourceProviderTestCase``.

The tests reach the public internet, so they are skipped unless explicitly enabled::

    $env:UNIVERSAL_SUBS_NETWORK_TESTS='0'
    python -m resources.lib.tests.test_provider_subdivx -v

See ``provider_testcase`` for the dependencies these tests need outside Kodi.
"""

import base64
import json
import tempfile
import unittest
from pathlib import Path

from resources.lib.common.language import Language
from resources.lib.common.settings import Settings
from resources.lib.providers.subdivx_source_provider import (SubDivXSourceProvider,
                                                            parse_browser_session)

# Imported as a module (not as a bare class name) so that the shared base test case, which is
# abstract, is not collected by unittest discovery as a test case of its own.
from . import provider_testcase


@provider_testcase.requires_network
class SubDivXSourceProviderTest(provider_testcase.OnlineSourceProviderTestCase):

    provider_name = "SubDivX"
    # SubDivX is a Spanish site and only supports Spanish subtitles.
    movie_title = "Matrix"
    movie_year = 1999
    movie_languages = [Language.spanish]
    # A show search would be sent as the literal text "<show> S01E01", which the site does not
    # understand, so only the movie operations apply here.
    supports_tv_shows = False


class SubDivXBrowserSessionTest(unittest.TestCase):
    """The browser-session blob is the only way past Cloudflare; its wiring is covered here."""

    @staticmethod
    def build_blob(cookie: str, ua: str = None) -> str:
        data = {"cookie": cookie}
        if ua is not None:
            data["ua"] = ua
        return base64.b64encode(json.dumps(data).encode("utf-8")).decode("ascii")

    def test_blob_is_decoded_into_cookie_and_user_agent(self) -> None:
        blob = self.build_blob("cf_clearance=token; PHPSESSID=session", "Mozilla/5.0 Test")
        self.assertEqual(parse_browser_session(blob),
                         {"cookie": "cf_clearance=token; PHPSESSID=session", "ua": "Mozilla/5.0 Test"})

    def test_empty_or_invalid_blobs_keep_the_anonymous_path(self) -> None:
        self.assertEqual(parse_browser_session(""), {})
        self.assertEqual(parse_browser_session("not-base64!"), {})
        self.assertEqual(parse_browser_session(self.build_blob("")), {})
        missing_cookie = base64.b64encode(b'{"ua": "Mozilla/5.0 Test"}').decode("ascii")
        self.assertEqual(parse_browser_session(missing_cookie), {})

    def test_provider_replays_the_session_on_its_requests(self) -> None:
        settings = Settings()
        settings.addon_user_path = Path(tempfile.mkdtemp(prefix="subdivx-session-test-"))
        settings.subdivx_session = self.build_blob("cf_clearance=token; PHPSESSID=session", "UA-test/1")
        provider = SubDivXSourceProvider(settings)
        self.assertEqual(provider._http_client.default_headers["Cookie"], "cf_clearance=token; PHPSESSID=session")
        self.assertEqual(provider._http_client.default_headers["User-Agent"], "UA-test/1")

    def test_provider_without_session_sends_no_cookie(self) -> None:
        settings = Settings()
        settings.addon_user_path = Path(tempfile.mkdtemp(prefix="subdivx-session-test-"))
        provider = SubDivXSourceProvider(settings)
        self.assertNotIn("Cookie", provider._http_client.default_headers)


if __name__ == '__main__':
    unittest.main()
