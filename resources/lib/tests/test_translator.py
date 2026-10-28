# -*- coding: utf-8 -*-

"""Tests for the behaviour ``Translator`` provides to every translator.

Block building, block translation and the caching/normalisation in ``translate`` are provider
independent, so they run against ``StubTranslator``: a translator whose network layer is a plain
function that records the texts it was asked to translate.
"""

import logging
import unittest
from datetime import timedelta

from resources.lib.common.language import Language
from resources.lib.tests import translator_testcase
from resources.lib.tests.translator_testcase import FakeCache
from resources.lib.translation.google_translator import GoogleTranslator
from resources.lib.translation.translator import TranslateException, Translator, \
    UnsupportedTranslationException


class PassthroughLanguages:
    """``MappedLanguages`` stand-in for the stub, which does no language mapping of its own."""

    def has_any_external(self, language):
        return True

    def to_internal_first(self, language, default=None):
        return language


class StubTranslator(Translator):
    """Translator whose network layer is a plain function, used to exercise the base class."""

    def __init__(self, translate_function=None, supported=True):
        self._logger = logging.getLogger("UniversalSubs.Tests.StubTranslator")
        self._cache = FakeCache()
        self._supported = supported
        self._translate_function = translate_function or (lambda texts: [text.upper() for text in texts])
        self.translated_blocks = []
        # Same name mangling the base class uses for its private attribute.
        self._Translator__languages = PassthroughLanguages()

    @property
    def name(self):
        return "Stub"

    @property
    def short_name(self):
        return "ST"

    def supports_translation(self, from_language, to_language):
        return self._supported

    def _translate(self, internal_from_language, internal_to_language, texts):
        self.translated_blocks.append(list(texts))
        return self._translate_function(texts)


class TextBlockBuildingTest(translator_testcase.TranslatorTestCase):

    def setUp(self):
        self.translator = StubTranslator()

    def test_keeps_texts_together_while_they_fit(self):
        self.assertEqual(["one|two"], self.translator._build_text_blocks(["one", "two"], 100, "|"))

    def test_starts_a_new_block_when_the_size_is_exceeded(self):
        self.assertEqual(["aaa|bbb", "ccc"], self.translator._build_text_blocks(["aaa", "bbb", "ccc"], 10, "|"))

    def test_keeps_a_text_larger_than_the_block_size_whole(self):
        self.assertEqual(["0123456789"], self.translator._build_text_blocks(["0123456789"], 5, "|"))

    def test_returns_nothing_for_no_texts(self):
        self.assertEqual([], self.translator._build_text_blocks([], 10, "|"))


class TranslateInBlocksTest(translator_testcase.TranslatorTestCase):

    def setUp(self):
        self.translator = StubTranslator()

    def test_joins_blocks_then_splits_the_translation_back(self):
        texts = ["one", "two"]
        translations = self.translator._translate_in_blocks(
            texts, 100, "|", lambda block: block.upper(), delay=timedelta())
        self.assertEqual(["ONE", "TWO"], translations)

    def test_carries_extra_parameters_over_to_the_next_block(self):
        calls = []

        def translate(block, token):
            calls.append((block, token))
            return ["%s@%s" % (block, token), "token-%d" % len(calls)]

        translations = self.translator._translate_in_blocks(
            ["a", "b", "c"], 3, "|", translate, ["token-0"], delay=timedelta())

        # "a|b" becomes "a|b@token-0", so the separator splits inside the translated block.
        self.assertEqual(["a", "b@token-0", "c@token-1"], translations)
        self.assertEqual([("a|b", "token-0"), ("c", "token-1")], calls)

    def test_a_missing_translation_raises(self):
        with self.assertRaises(TranslateException):
            self.translator._translate_in_blocks(["x"], 100, "|", lambda block: [None, "unused"], delay=timedelta())


class TranslatorTranslateTest(translator_testcase.TranslatorTestCase):

    def test_normalizes_whitespace_before_translating(self):
        translator = StubTranslator()
        self.assertEqual(["HELLO WORLD"], translator.translate(
            Language.english, Language.spanish, ["  hello   world  "]))
        self.assertEqual([["hello world"]], translator.translated_blocks)

    def test_serves_a_repeated_line_from_the_cache(self):
        translator = StubTranslator()
        translator.translate(Language.english, Language.spanish, ["Hello"])
        translator.translate(Language.english, Language.spanish, ["Hello"])
        self.assertEqual(1, len(translator.translated_blocks))

    def test_translates_only_the_lines_missing_from_the_cache(self):
        translator = StubTranslator()
        translator._cache.set("en:es:Hello", "Hola")

        self.assertEqual(["Hola", "BYE"], translator.translate(
            Language.english, Language.spanish, ["Hello", "Bye"]))
        self.assertEqual([["Bye"]], translator.translated_blocks)

    def test_unsupported_language_pair_raises(self):
        translator = StubTranslator(supported=False)
        with self.assertRaises(UnsupportedTranslationException):
            translator.translate(Language.english, Language.spanish, ["Hello"])

    def test_id_is_derived_from_the_provider_name(self):
        self.assertEqual("UniversalSubs.Translator.Google", GoogleTranslator(self.settings).id)


if __name__ == '__main__':
    unittest.main()
