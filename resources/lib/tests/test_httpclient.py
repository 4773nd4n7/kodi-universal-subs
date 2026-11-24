# -*- coding: utf-8 -*-

"""Tests for the HTTP response helpers the providers depend on.

The redirect handling of several providers reads the ``Location`` header, and servers are free to
send it in any casing (OpenSubtitles sends ``location``), so the lookup rules are covered here
without touching the network.

Run it from the repository root, without installing the add-on into Kodi::

    python -m resources.lib.tests.test_httpclient -v
"""

import unittest

from resources.lib.utils.http_client import HttpRequest, HttpResponse


def build_response(headers, status_code=200, final_request_url=None) -> HttpResponse:
    request = HttpRequest("https://example.com/subtitles/the-matrix")
    return HttpResponse(request, status_code, headers, lambda: b"", final_request_url)


class HttpResponseHeadersTest(unittest.TestCase):

    def test_header_lookup_ignores_name_casing(self) -> None:
        response = build_response({"location": ["/moved"]}, status_code=307)
        for header_name in ("Location", "location", "LOCATION"):
            with self.subTest(header=header_name):
                self.assertEqual("/moved", response.get_header_value(header_name))
                self.assertEqual(["/moved"], response.get_header_values(header_name))

    def test_missing_header_returns_no_values(self) -> None:
        response = build_response({"content-type": ["text/html"]})
        self.assertIsNone(response.get_header_value("Location"))
        self.assertEqual([], response.get_header_values("Location"))

    def test_casing_variants_of_one_header_are_merged(self) -> None:
        response = build_response({"Set-Cookie": ["a=1"], "set-cookie": ["b=2"]})
        self.assertEqual(["a=1", "b=2"], response.get_header_values("set-cookie"))

    def test_reading_one_header_that_has_many_values_can_be_refused(self) -> None:
        response = build_response({"set-cookie": ["a=1", "b=2"]})
        self.assertEqual("a=1", response.get_header_value("Set-Cookie"))
        with self.assertRaises(Exception):
            response.get_header_value("set-cookie", throw_if_many=True)

    def test_header_names_keep_the_casing_the_server_sent(self) -> None:
        response = build_response({"location": ["/moved"]}, status_code=307)
        self.assertIn("location", response.get_header_names())

    def test_file_name_falls_back_to_the_request_path(self) -> None:
        response = build_response({}, final_request_url="https://example.com/subtitles/movie.zip")
        self.assertEqual("movie.zip", response.file_name)

    def test_file_name_prefers_content_disposition(self) -> None:
        response = build_response({"Content-Disposition": ['attachment; filename="The Matrix.srt"']})
        self.assertEqual("The Matrix.srt", response.file_name)

    def test_file_name_reads_the_extended_utf8_form(self) -> None:
        # RFC 5987 form; SubDL sends this, and it used to crash with "'str' object has no attribute
        # 'decode'" because unquote already returns text under Python 3.
        response = build_response(
            {"Content-Disposition": ["attachment; filename*=UTF-8''The%20Matrix.srt"]})
        self.assertEqual("The Matrix.srt", response.file_name)

    def test_file_name_reads_the_extended_latin1_form(self) -> None:
        response = build_response(
            {"Content-Disposition": ["attachment; filename*=ISO-8859-1''caf%E9.srt"]})
        self.assertEqual("café.srt", response.file_name)

    def test_credential_query_values_are_masked_for_logs(self) -> None:
        # SubDL only accepts its key as a query parameter, so it has to travel in the URL; the log
        # must not carry it.
        from resources.lib.utils.http_client import redact_url

        self.assertEqual("https://api.example/x?api_key=***&page=2",
                         redact_url("https://api.example/x?api_key=subdl_secret&page=2"))
        self.assertEqual("https://api.example/x?token=***&sig=***",
                         redact_url("https://api.example/x?token=abc&sig=def"))
        self.assertEqual("https://api.example/x?page=2",
                         redact_url("https://api.example/x?page=2"))


if __name__ == '__main__':
    unittest.main()
