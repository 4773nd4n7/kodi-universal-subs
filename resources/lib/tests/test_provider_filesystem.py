# -*- coding: utf-8 -*-

"""Tests for the ``FileSystem`` provider: subtitles anywhere below a configured library folder.

The provider is driven through the same ``search`` and ``get`` operations as the remote providers,
against a temporary library instead of a provider site, so these tests are hermetic and always run.

Run it from the repository root, without installing the add-on into Kodi:

    python -m resources.lib.tests.test_provider_filesystem -v
"""

import unittest
from pathlib import Path

from resources.lib.common.language import Language
from resources.lib.common.settings import Settings

from .provider_fixtures import (ENGLISH_SUBTITLE_TEXT, MOVIE_TITLE, MOVIE_YEAR,
                                SPANISH_SUBTITLE_TEXT, write_text_file)
from .provider_testcase import ProviderTestCase


class FileSystemSourceProviderTest(ProviderTestCase):
    """``FileSystem``: subtitles anywhere below the configured library folder."""

    provider_name = "FileSystem"

    library_directory: Path = None

    @classmethod
    def configure_settings(cls, settings: Settings) -> None:
        cls.library_directory = cls.work_directory.joinpath("library")
        cls.library_directory.mkdir(parents=True, exist_ok=True)
        settings.file_system_provider_path = cls.library_directory

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        write_text_file(cls.library_directory.joinpath("movies", "%s (%s).en.srt" % (MOVIE_TITLE, MOVIE_YEAR)),
                        ENGLISH_SUBTITLE_TEXT)
        write_text_file(cls.library_directory.joinpath("movies", "%s (%s).es.srt" % (MOVIE_TITLE, MOVIE_YEAR)),
                        SPANISH_SUBTITLE_TEXT)
        write_text_file(cls.library_directory.joinpath("series", "Some Other Show (2005).en.srt"),
                        ENGLISH_SUBTITLE_TEXT)

    def test_search_finds_subtitles_below_the_library_root(self) -> None:
        search_results = self.provider().search(self.build_movie_search_request(MOVIE_TITLE, MOVIE_YEAR, []))
        expected_ids = {
            str(self.library_directory.joinpath("movies", "%s (%s).en.srt" % (MOVIE_TITLE, MOVIE_YEAR))),
            str(self.library_directory.joinpath("movies", "%s (%s).es.srt" % (MOVIE_TITLE, MOVIE_YEAR))),
        }
        self.assertEqual(expected_ids, {search_result.id for search_result in search_results})
        for search_result in search_results:
            self.assertEqual("FileSystem", search_result.provider_name)
            # The file name is part of the release info here, so the derived sync flag is a real bool.
            self.assertIsInstance(search_result.is_sync, bool)

    def test_search_filters_results_by_language(self) -> None:
        search_results = self.provider().search(self.build_movie_search_request(MOVIE_TITLE, MOVIE_YEAR, [Language.spanish]))
        self.assertEqual(1, len(search_results))
        self.assertEqual(Language.spanish, search_results[0].language)
        self.assertTrue(search_results[0].id.endswith(".es.srt"))

    def test_search_returns_nothing_for_an_unknown_title(self) -> None:
        self.assertEqual([], self.provider().search(self.build_movie_search_request("An Unknown Movie", 2024, [])))

    def test_get_returns_the_subtitle_file(self) -> None:
        search_results = self.provider().search(self.build_movie_search_request(MOVIE_TITLE, MOVIE_YEAR, [Language.english]))
        self.assertEqual(1, len(search_results))
        get_results = self.download(search_results[0])
        self.assert_valid_subtitle_results(get_results)
        self.assertEqual(ENGLISH_SUBTITLE_TEXT, get_results[0].content.decode("utf-8"))
        self.assert_result_can_be_saved(get_results[0])


if __name__ == '__main__':
    unittest.main()
