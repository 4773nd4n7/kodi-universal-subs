# -*- coding: utf-8 -*-

"""Tests for ``SubtitleTranslator``, the glue between the subtitle formats and a translator.

The translator is a stub that upper-cases each line, so the assertions are about the SRT round
trip: which lines reach the translator, that the cue timings survive, and how the file is renamed.
"""

import logging
import unittest

from resources.lib.common.language import Language
from resources.lib.providers.get_result import GetResult
from resources.lib.tests.provider_fixtures import ENGLISH_SUBTITLE_TEXT
from resources.lib.translation.subtitle_translator import SubtitleTranslator
from resources.lib.translation.translator import Translator


class UpperCaseTranslator(Translator):
    """Translator that upper-cases each line; bypasses the cache and the network entirely."""

    def __init__(self):
        self._logger = logging.getLogger("UniversalSubs.Tests.UpperCaseTranslator")

    @property
    def name(self):
        return "Upper"

    def supports_translation(self, from_language, to_language):
        return True

    def _translate(self, internal_from_language, internal_to_language, texts):
        return [text.upper() for text in texts]

    def translate(self, from_language, to_language, texts):
        return [text.upper() for text in texts]


class SubtitleTranslatorTest(unittest.TestCase):

    def build_result(self, file_name="movie.srt", text=ENGLISH_SUBTITLE_TEXT):
        result = GetResult()
        result.file_name = file_name
        result.content = text.encode("utf-8")
        result.provider_name = "Tests"
        return result

    def test_translates_every_line_and_renames_the_file(self):
        result = self.build_result()
        translator = SubtitleTranslator(UpperCaseTranslator())

        translated = translator.translate(result, Language.english, Language.spanish)

        self.assertEqual("movie.es.srt", translated.file_name)
        content = translated.content.decode("utf-8")
        self.assertIn("WAKE UP, NEO.", content)
        self.assertIn("THE MATRIX HAS YOU.", content)
        self.assertNotIn("Wake up, Neo.", content)

    def test_keeps_the_cue_timings(self):
        result = self.build_result()
        translated = SubtitleTranslator(UpperCaseTranslator()).translate(
            result, Language.english, Language.spanish)

        content = translated.content.decode("utf-8")
        self.assertIn("00:00:01,000 --> 00:00:03,000", content)
        self.assertIn("00:00:03,500 --> 00:00:06,000", content)

    def test_does_not_modify_the_source_result(self):
        result = self.build_result()
        SubtitleTranslator(UpperCaseTranslator()).translate(result, Language.english, Language.spanish)
        self.assertEqual(ENGLISH_SUBTITLE_TEXT, result.content.decode("utf-8"))

    def test_supports_only_known_subtitle_formats(self):
        translator = SubtitleTranslator(UpperCaseTranslator())
        self.assertTrue(translator.supports_subtitle(self.build_result()))
        # .txt is claimed by the MPlayer2 format; .mkv is not a subtitle format at all.
        self.assertTrue(translator.supports_subtitle(self.build_result(file_name="movie.txt")))
        self.assertFalse(translator.supports_subtitle(self.build_result(file_name="movie.mkv")))


if __name__ == '__main__':
    unittest.main()
