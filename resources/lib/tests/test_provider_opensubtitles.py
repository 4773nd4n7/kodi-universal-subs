# -*- coding: utf-8 -*-

"""Live tests for the OpenSubtitles provider.

Covers the operations the addon performs for a user: a movie search with a year, a TV show search
with season and episode, and downloading the first result. The assertions live in
``OnlineSourceProviderTestCase``; this module only supplies the titles and languages.

The tests reach the public internet, so they are skipped unless explicitly enabled::

    $env:UNIVERSAL_SUBS_NETWORK_TESTS='1'
    python -m resources.lib.tests.test_provider_opensubtitles -v

See ``provider_testcase`` for the dependencies these tests need outside Kodi.
"""

import unittest

from resources.lib.common.language import Language

# Imported as a module (not as a bare class name) so that the shared base test case, which is
# abstract, is not collected by unittest discovery as a test case of its own.
from . import provider_testcase


@provider_testcase.requires_network
class OpenSubtitlesProviderTest(provider_testcase.OnlineSourceProviderTestCase):

    provider_name = "OpenSubtitles"
    movie_title = "The Matrix"
    movie_year = 1999
    movie_languages = [Language.english]
    show_title = "The Big Bang Theory"
    show_season_number = 1
    show_episode_number = 1
    show_languages = [Language.english]


if __name__ == '__main__':
    unittest.main()
