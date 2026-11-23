# -*- coding: utf-8 -*-

"""Live tests for the OpenSubtitles.com provider.

The API needs an API key and, for downloads, a user login. Point these environment variables at a
real account to run them; without them the tests are skipped:

    OPENSUBTITLES_COM_API_KEY, OPENSUBTITLES_COM_USERNAME, OPENSUBTITLES_COM_PASSWORD
"""

import os
import unittest

from resources.lib.common.language import Language
from resources.lib.tests import provider_testcase

ENVIRONMENT_VARIABLES = ("OPENSUBTITLES_COM_API_KEY", "OPENSUBTITLES_COM_USERNAME",
                         "OPENSUBTITLES_COM_PASSWORD")


@provider_testcase.requires_network
class OpenSubtitlesComSourceProviderTest(provider_testcase.OnlineSourceProviderTestCase):

    provider_name = "OpenSubtitles.com"

    movie_title = "The Matrix"
    movie_year = 1999
    movie_languages = (Language.english,)

    show_title = "The Big Bang Theory"
    show_season_number = 1
    show_episode_number = 1
    show_languages = (Language.english,)

    @classmethod
    def setUpClass(cls) -> None:
        missing = [name for name in ENVIRONMENT_VARIABLES if not os.environ.get(name, "").strip()]
        if missing:
            raise unittest.SkipTest("set %s to run the live OpenSubtitles.com tests" % ", ".join(missing))
        super().setUpClass()

    @classmethod
    def configure_settings(cls, settings) -> None:
        settings.opensubtitles_com_api_key = os.environ["OPENSUBTITLES_COM_API_KEY"].strip()
        settings.opensubtitles_com_username = os.environ["OPENSUBTITLES_COM_USERNAME"].strip()
        settings.opensubtitles_com_password = os.environ["OPENSUBTITLES_COM_PASSWORD"]


if __name__ == '__main__':
    unittest.main()
