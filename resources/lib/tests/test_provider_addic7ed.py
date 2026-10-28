# -*- coding: utf-8 -*-

"""Live tests for the Addic7ed provider.

Addic7ed indexes TV episodes first and movies second, so both search shapes are covered: a movie
search with a year and a TV show search with season and episode. The assertions live in
``OnlineSourceProviderTestCase``.

The tests reach the public internet, so they are skipped unless explicitly enabled::

    $env:UNIVERSAL_SUBS_NETWORK_TESTS='0'
    python -m resources.lib.tests.test_provider_addic7ed -v

See ``provider_testcase`` for the dependencies these tests need outside Kodi.
"""

import unittest

from resources.lib.common.language import Language

# Imported as a module (not as a bare class name) so that the shared base test case, which is
# abstract, is not collected by unittest discovery as a test case of its own.
from . import provider_testcase


@provider_testcase.requires_network
class Addic7edSourceProviderTest(provider_testcase.OnlineSourceProviderTestCase):

    provider_name = "Addic7ed"
    movie_title = "The Matrix"
    movie_year = 1999
    movie_languages = [Language.english]
    show_title = "The Big Bang Theory"
    show_season_number = 1
    show_episode_number = 1
    show_languages = [Language.english]


if __name__ == '__main__':
    unittest.main()
