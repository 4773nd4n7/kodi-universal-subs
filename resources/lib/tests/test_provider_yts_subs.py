# -*- coding: utf-8 -*-

"""Live tests for the YTS Subs provider.

The site serves plain HTML, so these tests run by default like the other live provider tests. It
indexes YIFY movies only, which is why the TV show test is disabled here.
"""

import unittest

from resources.lib.common.language import Language
from resources.lib.tests import provider_testcase


@provider_testcase.requires_network
class YtsSubsSourceProviderTest(provider_testcase.OnlineSourceProviderTestCase):

    provider_name = "YTS Subs"

    movie_title = "The Matrix"
    movie_year = 1999
    movie_languages = (Language.english,)

    #: The site only lists subtitles for movies.
    supports_tv_shows = False


if __name__ == '__main__':
    unittest.main()
