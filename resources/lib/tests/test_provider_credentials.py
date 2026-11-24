# -*- coding: utf-8 -*-

"""Providers that cannot work without credentials must say so instead of returning no results."""

import tempfile
import unittest
from pathlib import Path

from resources.lib.common.settings import Settings
from resources.lib.providers.opensubtitlescom_source_provider import OpenSubtitlesComSourceProvider
from resources.lib.providers.provider import Provider  # noqa: F401  (kept for the docs below)
from resources.lib.providers.subdivx_source_provider import (SubDivXSourceProvider,
                                                             encode_browser_session)
from resources.lib.providers.subdl_source_provider import SubDlSourceProvider


class MissingCredentialsTest(unittest.TestCase):

    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.settings = Settings()
        self.settings.addon_user_path = Path(self._temporary_directory.name)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_subdl_reports_its_missing_key(self) -> None:
        self.assertIn("API key", SubDlSourceProvider(self.settings).missing_credentials())
        self.settings.subdl_api_key = "a-key"
        self.assertEqual(SubDlSourceProvider(self.settings).missing_credentials(), "")

    def test_opensubtitles_com_reports_key_then_login(self) -> None:
        self.assertIn("API key", OpenSubtitlesComSourceProvider(self.settings).missing_credentials())

        self.settings.opensubtitles_com_api_key = "a-key"
        self.assertIn("username and password",
                      OpenSubtitlesComSourceProvider(self.settings).missing_credentials())

        self.settings.opensubtitles_com_username = "someone"
        self.assertIn("username and password",
                      OpenSubtitlesComSourceProvider(self.settings).missing_credentials())

        self.settings.opensubtitles_com_password = "secret"
        self.assertEqual(OpenSubtitlesComSourceProvider(self.settings).missing_credentials(), "")

    def test_subdivx_reports_its_missing_session(self) -> None:
        # Cloudflare challenges every non-browser client, so the session is required, not optional.
        self.assertIn("browser session", SubDivXSourceProvider(self.settings).missing_credentials())

        self.settings.subdivx_session = encode_browser_session(
            {"cookie": "cf_clearance=abc", "ua": "Mozilla/5.0"})
        self.assertEqual(SubDivXSourceProvider(self.settings).missing_credentials(), "")

    def test_a_provider_without_credentials_stays_quiet(self) -> None:
        # Providers that need none (local, filesystem, addic7ed, …) inherit the empty answer.
        from resources.lib.providers.addic7ed_source_provider import Addic7edSourceProvider

        self.assertEqual(Addic7edSourceProvider(self.settings).missing_credentials(), "")

    def test_subdl_download_url_drops_the_key_it_was_given(self) -> None:
        # The API embeds the key in the download URL it returns; dl.subdl.com does not need it, and
        # keeping it would leak the key into Kodi's log and into the plugin call Kodi builds.
        from resources.lib.providers.subdl_source_provider import download_url_from_api_url

        self.assertEqual("/subtitle/3495158-8417477.zip",
                         download_url_from_api_url("/subtitle/3495158-8417477.zip?api_key=secret"))
        self.assertEqual("/subtitle/3495158-8417477.zip",
                         download_url_from_api_url("/subtitle/3495158-8417477.zip"))
        self.assertEqual("", download_url_from_api_url(None))


if __name__ == "__main__":
    unittest.main()
