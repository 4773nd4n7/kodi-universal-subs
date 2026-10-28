# -*- coding: utf-8 -*-

"""Live tests for the SubDL provider.

SubDL answers through its search API, which requires an API key, so these are integration tests
against the real service: a movie search, a TV show search and downloading the first result. The
key comes from ``SUBDL_API_KEY`` and is free from https://subdl.com/panel/api; without it the tests
are skipped rather than run against a service that will refuse them.
"""

import os
import unittest

from resources.lib.common.language import Language
from resources.lib.tests import provider_testcase


@provider_testcase.requires_network
class SubDlSourceProviderTest(provider_testcase.OnlineSourceProviderTestCase):

    provider_name = "SubDL"

    movie_title = "The Matrix"
    movie_year = 1999
    movie_languages = (Language.english,)

    show_title = "The Big Bang Theory"
    show_season_number = 1
    show_episode_number = 1
    show_languages = (Language.english,)

    @classmethod
    def setUpClass(cls) -> None:
        if not os.environ.get("SUBDL_API_KEY", "").strip():
            raise unittest.SkipTest(
                "set SUBDL_API_KEY to run the live SubDL tests (free key: https://subdl.com/panel/api)")
        super().setUpClass()

    @classmethod
    def configure_settings(cls, settings) -> None:
        settings.subdl_api_key = os.environ["SUBDL_API_KEY"].strip()


if __name__ == '__main__':
    unittest.main()
