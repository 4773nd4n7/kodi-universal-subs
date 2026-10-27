# -*- coding: utf-8 -*-

"""Tests for the ``Local`` provider: subtitles stored next to the media file being played.

The provider is driven through the same ``search`` and ``get`` operations as the remote providers,
against a temporary directory instead of a provider site, so these tests are hermetic and always
run.

Run it from the repository root, without installing the add-on into Kodi:

    python -m resources.lib.tests.test_provider_local -v
"""

import unittest
import zipfile
from pathlib import Path

from resources.lib.common.language import Language
from resources.lib.providers.searchrequest import SearchRequest

from .provider_fixtures import (ENGLISH_SUBTITLE_TEXT, MOVIE_TITLE, MOVIE_YEAR,
                                SPANISH_SUBTITLE_TEXT, find_result_by_id,
                                write_text_file)
from .provider_testcase import ProviderTestCase


class LocalSourceProviderTest(ProviderTestCase):
    """``Local``: subtitles stored next to the media file that is being played."""

    provider_name = "Local"

    media_file_path: Path = None
    media_directory: Path = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.media_directory = cls.work_directory.joinpath("media")
        cls.media_directory.mkdir(parents=True, exist_ok=True)
        cls.media_file_path = cls.media_directory.joinpath("%s (%s).mp4" % (MOVIE_TITLE, MOVIE_YEAR))
        cls.media_file_path.write_bytes(b"")
        base_path = cls.media_directory.joinpath("%s (%s)" % (MOVIE_TITLE, MOVIE_YEAR))
        write_text_file(base_path.with_name(base_path.name + ".en.srt"), ENGLISH_SUBTITLE_TEXT)
        write_text_file(base_path.with_name(base_path.name + ".es.srt"), SPANISH_SUBTITLE_TEXT)
        write_text_file(base_path.with_name(base_path.name + ".srt"), ENGLISH_SUBTITLE_TEXT)
        write_text_file(base_path.with_name(base_path.name + ".en.forced.srt"), ENGLISH_SUBTITLE_TEXT)
        with zipfile.ZipFile(base_path.with_name(base_path.name + ".es.zip"), "w") as archive:
            archive.writestr("%s (%s).es.srt" % (MOVIE_TITLE, MOVIE_YEAR), SPANISH_SUBTITLE_TEXT)

    @classmethod
    def build_request(cls, languages=(Language.english,)) -> SearchRequest:
        request = SearchRequest()
        request.languages = list(languages)
        request.max_results = cls.max_results
        request.set_file_url_or_path(str(cls.media_file_path))
        return request

    @classmethod
    def subtitle_path(cls, suffix: str) -> Path:
        return cls.media_directory.joinpath("%s (%s)%s" % (MOVIE_TITLE, MOVIE_YEAR, suffix))

    def test_search_finds_every_sidecar_subtitle(self) -> None:
        search_results = self.provider().search(self.build_request(languages=[]))
        expected_ids = {
            str(self.subtitle_path(".en.srt")),
            str(self.subtitle_path(".es.srt")),
            str(self.subtitle_path(".srt")),
            str(self.subtitle_path(".en.forced.srt")),
            str(self.subtitle_path(".es.zip")),
        }
        self.assertEqual(expected_ids, {search_result.id for search_result in search_results})
        for search_result in search_results:
            self.assertEqual("Local", search_result.provider_name)
            # Sidecar subtitles belong to the file being played, so they are always in sync; the
            # base provider must not replace that with "unknown" when there is no release name.
            self.assertIs(True, search_result.is_sync,
                          "Sidecar result '%s' lost its sync flag" % Path(search_result.id).name)

    def test_search_maps_the_language_suffix_of_each_file(self) -> None:
        search_results = self.provider().search(self.build_request(languages=[]))
        expected_languages = {
            str(self.subtitle_path(".en.srt")): Language.english,
            str(self.subtitle_path(".es.srt")): Language.spanish,
            str(self.subtitle_path(".srt")): Language.unknown,
            str(self.subtitle_path(".en.forced.srt")): Language.english,
            str(self.subtitle_path(".es.zip")): Language.spanish,
        }
        for expected_id, expected_language in expected_languages.items():
            with self.subTest(file=Path(expected_id).name):
                search_result = find_result_by_id(search_results, expected_id)
                self.assertIsNotNone(search_result, "Missing search result for '%s'" % expected_id)
                self.assertEqual(expected_language, search_result.language)

    def test_search_filters_results_by_language(self) -> None:
        # Files with no language suffix cannot be attributed a language, so this provider keeps them
        # for every language filter instead of hiding them; the user still gets to pick them.
        english_results = self.provider().search(self.build_request([Language.english]))
        self.assertEqual(
            {str(self.subtitle_path(".en.srt")), str(self.subtitle_path(".en.forced.srt")),
             str(self.subtitle_path(".srt"))},
            {search_result.id for search_result in english_results})
        italian_results = self.provider().search(self.build_request([Language.italian]))
        self.assertEqual(
            {str(self.subtitle_path(".srt"))},
            {search_result.id for search_result in italian_results})

    def test_get_returns_the_subtitle_file(self) -> None:
        search_result = next(search_result for search_result in self.provider().search(self.build_request([Language.english]))
                             if search_result.id == str(self.subtitle_path(".en.srt")))
        get_results = self.download(search_result)
        self.assert_valid_subtitle_results(get_results)
        self.assertEqual("%s (%s).en.srt" % (MOVIE_TITLE, MOVIE_YEAR), get_results[0].file_name)
        self.assertEqual(ENGLISH_SUBTITLE_TEXT, get_results[0].content.decode("utf-8"))
        self.assertFalse(get_results[0].is_forced)
        written_file_path = self.assert_result_can_be_saved(get_results[0])
        self.assertEqual(ENGLISH_SUBTITLE_TEXT, written_file_path.read_text(encoding="utf-8"))

    def test_get_marks_forced_subtitles(self) -> None:
        search_result = next(search_result for search_result in self.provider().search(self.build_request([Language.english]))
                             if search_result.id == str(self.subtitle_path(".en.forced.srt")))
        get_results = self.download(search_result)
        self.assert_valid_subtitle_results(get_results)
        self.assertTrue(get_results[0].is_forced, "The 'forced' marker in the file name must be detected")

    def test_get_unpacks_archived_subtitles(self) -> None:
        search_results = self.provider().search(self.build_request([Language.spanish]))
        search_result = find_result_by_id(search_results, str(self.subtitle_path(".es.zip")))
        self.assertIsNotNone(search_result, "The archived subtitle was not found")
        get_results = self.download(search_result)
        self.assert_valid_subtitle_results(get_results)
        self.assertEqual("%s (%s).es.srt" % (MOVIE_TITLE, MOVIE_YEAR), get_results[0].file_name)
        self.assertEqual(SPANISH_SUBTITLE_TEXT, get_results[0].content.decode("utf-8"))


if __name__ == '__main__':
    unittest.main()
