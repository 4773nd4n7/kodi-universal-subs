# -*- coding: utf-8 -*-

"""Tests for the Subscene provider: live searches plus the results parser.

Two kinds of coverage live here because both belong to one provider:

* ``SubsceneSourceProviderTest`` performs the live movie and TV show searches and downloads the
  first result, using the assertions of ``OnlineSourceProviderTestCase``. It reaches the public
  internet and runs by default; ``UNIVERSAL_SUBS_NETWORK_TESTS=0`` skips it.
* ``SubsceneResultParsingTest`` parses a recorded results table, which covers the mapping onto
  ``SearchResult`` (including the documented 0.0-5.0 rating range) without the network, so it
  always runs.

Run it from the repository root; set the variable to keep a run offline::

    python -m resources.lib.tests.test_provider_subscene -v
    $env:UNIVERSAL_SUBS_NETWORK_TESTS='0'

See ``provider_testcase`` for the dependencies these tests need outside Kodi.
"""

import unittest

from bs4 import BeautifulSoup

from resources.lib.common.language import Language
from resources.lib.providers.search_request import SearchRequest

# Imported as a module (not as a bare class name) so that the shared base test case, which is
# abstract, is not collected by unittest discovery as a test case of its own.
from . import provider_testcase
from .provider_fixtures import MOVIE_TITLE, MOVIE_YEAR
from .provider_testcase import ProviderTestCase


@provider_testcase.requires_network
class SubsceneSourceProviderTest(provider_testcase.OnlineSourceProviderTestCase):

    provider_name = "Subscene"
    movie_title = "The Matrix"
    movie_year = 1999
    movie_languages = [Language.english]
    show_title = "The Big Bang Theory"
    show_season_number = 1
    show_episode_number = 1
    show_languages = [Language.english]


class SubsceneResultParsingTest(ProviderTestCase):
    """The Subscene results table maps onto ``SearchResult`` correctly, without the live site."""

    provider_name = "Subscene"

    SEARCH_RESULTS_HTML = """
    <div class="content">
      <table>
        <tbody>
          <tr>
            <td>Language</td><td>Title</td><td>Uploader</td><td>Rating</td><td>Downloads</td>
          </tr>
          <tr>
            <td>
              <a href="/subtitles/the-matrix-positive">
                <span>English</span><span>The.Matrix.1999.1080p.BluRay</span>
                <i class="positive-icon"></i>
              </a>
            </td>
            <td>1</td><td>2</td><td>3</td>
            <td><a href="/u/uploader-one">uploader one</a></td>
          </tr>
          <tr>
            <td>
              <a href="/subtitles/the-matrix-neutral">
                <span>English</span><span>The.Matrix.1999.720p.WEB</span>
                <i class="neutral-icon"></i>
              </a>
            </td>
            <td>1</td><td>2</td><td>3</td>
            <td><a href="/u/uploader-two">uploader two</a></td>
          </tr>
          <tr>
            <td>
              <a href="/subtitles/the-matrix-plain">
                <span>English</span><span>The.Matrix.1999.DVDRip</span>
              </a>
            </td>
            <td>1</td><td>2</td><td>3</td>
            <td><a href="/u/uploader-three">uploader three</a></td>
          </tr>
        </tbody>
      </table>
    </div>
    """

    @classmethod
    def parse_results(cls):
        provider = cls.provider()
        request = SearchRequest()
        request.languages = [Language.english]
        request.set_file_url_or_path(str(cls.work_directory.joinpath("%s (%s).mkv" % (MOVIE_TITLE, MOVIE_YEAR))))
        internal_english = provider._supported_languages.get_internal_by_name("English")
        # The results parser is name-mangled inside the provider; this is the only way to cover it
        # without a network round trip, and it is the place the rating is produced.
        return provider._SubsceneSourceProvider__parse_many_search_results(
            request, [internal_english], MOVIE_TITLE, BeautifulSoup(cls.SEARCH_RESULTS_HTML, "html5lib"))

    def test_search_results_are_parsed(self) -> None:
        search_results = self.parse_results()
        self.assertEqual(3, len(search_results))
        self.assertEqual(["||/subtitles/the-matrix-positive", "||/subtitles/the-matrix-neutral",
                          "||/subtitles/the-matrix-plain"],
                         [search_result.id for search_result in search_results])
        self.assertEqual(["uploader one", "uploader two", "uploader three"],
                         [search_result.author for search_result in search_results])

    def test_ratings_stay_within_the_documented_range(self) -> None:
        # SearchResult.rating is documented as 0.0-5.0; the three site states must map inside it.
        search_results = self.parse_results()
        self.assertEqual([5.0, 2.5, 0.0], [search_result.rating for search_result in search_results])
        for search_result in search_results:
            with self.subTest(result=search_result.id):
                self.assertGreaterEqual(search_result.rating, 0.0)
                self.assertLessEqual(search_result.rating, 5.0)


if __name__ == '__main__':
    unittest.main()
