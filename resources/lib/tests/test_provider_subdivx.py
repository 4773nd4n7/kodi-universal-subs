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
                                                            encode_browser_session,
                                                            explain_browser_session,
                                                            parse_browser_session,
                                                            parse_csrf_token,
                                                            parse_search_field)

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

    def test_copied_curl_request_yields_cookie_and_user_agent(self) -> None:
        # cf_clearance is HttpOnly, so "Copy as cURL" from the Network tab is the supported capture.
        pasted = (
            "curl 'https://www.subdivx.com/' \\\n"
            "  -H 'accept: text/html,application/xhtml+xml' \\\n"
            "  -H 'cookie: cf_clearance=token; PHPSESSID=session' \\\n"
            "  -H 'user-agent: Mozilla/5.0 Test' \\\n"
            "  --compressed\n"
        )
        self.assertEqual(parse_browser_session(pasted),
                         {"cookie": "cf_clearance=token; PHPSESSID=session", "ua": "Mozilla/5.0 Test"})

    def test_copied_cmd_request_yields_cookie_and_user_agent(self) -> None:
        pasted = (
            'curl "https://www.subdivx.com/" ^\n'
            '  -H "accept: text/html" ^\n'
            '  -H "cookie: cf_clearance=token; PHPSESSID=session" ^\n'
            '  -H "user-agent: Mozilla/5.0 Test" ^\n'
        )
        self.assertEqual(parse_browser_session(pasted),
                         {"cookie": "cf_clearance=token; PHPSESSID=session", "ua": "Mozilla/5.0 Test"})

    def test_copied_powershell_request_yields_cookie_and_user_agent(self) -> None:
        pasted = (
            "Invoke-WebRequest -Uri 'https://www.subdivx.com/' -Headers @{\n"
            "  'accept'='text/html'\n"
            "  'cookie'='cf_clearance=token; PHPSESSID=session'\n"
            "  'user-agent'='Mozilla/5.0 Test'\n"
            "}\n"
        )
        self.assertEqual(parse_browser_session(pasted),
                         {"cookie": "cf_clearance=token; PHPSESSID=session", "ua": "Mozilla/5.0 Test"})

    def test_pasted_header_block_yields_cookie_and_user_agent(self) -> None:
        pasted = ("Cookie: cf_clearance=token; PHPSESSID=session\n"
                  "User-Agent: Mozilla/5.0 Test\n")
        self.assertEqual(parse_browser_session(pasted),
                         {"cookie": "cf_clearance=token; PHPSESSID=session", "ua": "Mozilla/5.0 Test"})

    def test_bare_cookie_header_is_accepted(self) -> None:
        self.assertEqual(parse_browser_session("cf_clearance=token; PHPSESSID=session"),
                         {"cookie": "cf_clearance=token; PHPSESSID=session"})

    def test_a_lone_clearance_value_is_taken_as_the_cookie(self) -> None:
        # Copying the value out of Application -> Cookies is a common shortcut, so accept it. It
        # carries no user agent, which is why the page recommends copying the whole request.
        value = "ChXpYt3ToRDKMxVv1yLtQ3aX1jqvfpG6Poyc24LcvarpvRu0Vqup7Z7eGnwPMhf__eweyL4IRmNkm8WfnpD9"
        self.assertEqual(parse_browser_session(value),
                         {"cookie": "cf_clearance=" + value})
        self.assertEqual(parse_browser_session("cf_clearance=" + value),
                         {"cookie": "cf_clearance=" + value})

    def test_the_site_version_names_the_search_field(self) -> None:
        # The site posts "buscar" + $("#vs").text().replace(/[v.]/g, ""); a hardcoded "buscar" is
        # unknown to the endpoint, which then returns an empty body.
        self.assertEqual(parse_search_field('<span id="vs">v4.61</span>'), "buscar461")
        self.assertEqual(parse_search_field('<div id="vs" class="x">v1.2</div>'), "buscar12")
        self.assertEqual(parse_search_field("<html></html>"), "buscar")

    def test_the_csrf_token_is_read_from_the_meta_tag(self) -> None:
        self.assertEqual(parse_csrf_token('<meta name="csrf-token" content="abc123">'), "abc123")
        self.assertEqual(parse_csrf_token("<html></html>"), "")

    def test_the_page_supplied_user_agent_completes_a_value_only_paste(self) -> None:
        # The simplest capture is copying cf_clearance from Application -> Cookies; the page adds
        # the user agent, so the pair Cloudflare checks is complete.
        value = "ChXpYt3ToRDKMxVv1yLtQ3aX1jqvfpG6Poyc24LcvarpvRu0Vqup7Z7eGnwPMhf__eweyL4IRmNkm8WfnpD9"
        session, reason = explain_browser_session(value, "Mozilla/5.0 Test")
        self.assertEqual(session, {"cookie": "cf_clearance=" + value, "ua": "Mozilla/5.0 Test"})
        self.assertEqual(reason, "")

    def test_a_user_agent_from_the_request_wins_over_the_page_one(self) -> None:
        session, _ = explain_browser_session(
            "cookie: cf_clearance=token\nuser-agent: FromRequest/1", "FromPage/2")
        self.assertEqual(session["ua"], "FromRequest/1")

    def test_a_short_token_is_not_mistaken_for_a_clearance(self) -> None:
        session, reason = explain_browser_session("abc123")
        self.assertEqual(session, {})
        self.assertIn("cookie value without its name", reason)

    def test_a_curl_without_a_cookie_header_is_reported_as_such(self) -> None:
        session, reason = explain_browser_session("curl 'https://www.subdivx.com/' -H 'accept: text/html'")
        self.assertEqual(session, {})
        self.assertIn("no cookie header", reason)

    def test_text_without_a_session_cookie_is_rejected(self) -> None:
        self.assertEqual(parse_browser_session("hello world"), {})
        self.assertEqual(parse_browser_session("cookie: other=1"), {})
        # A user agent alone cannot authenticate anything.
        self.assertEqual(parse_browser_session("user-agent: Mozilla/5.0 Test"), {})

    def test_encoded_session_round_trips_through_the_setting(self) -> None:
        session = {"cookie": "cf_clearance=token; PHPSESSID=session", "ua": "Mozilla/5.0 Test"}
        self.assertEqual(parse_browser_session(encode_browser_session(session)), session)

    def test_a_good_session_explains_nothing(self) -> None:
        session, reason = explain_browser_session("cf_clearance=token; PHPSESSID=session")
        self.assertEqual(session, {"cookie": "cf_clearance=token; PHPSESSID=session"})
        self.assertEqual(reason, "")

    def test_rejections_say_what_the_user_has_to_do(self) -> None:
        self.assertEqual(explain_browser_session("")[1], "nothing was pasted")
        # The common mistake: the pasted request is the one Cloudflare answered with the challenge.
        no_cookie = explain_browser_session("curl 'https://www.subdivx.com/' -H 'accept: text/html'")[1]
        self.assertIn("no cookie header", no_cookie)
        self.assertIn("after the page finished loading", no_cookie)
        self.assertIn("no SubDivX cookie", explain_browser_session("cookie: other=1")[1])

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
