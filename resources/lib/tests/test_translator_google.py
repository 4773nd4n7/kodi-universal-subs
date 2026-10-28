# -*- coding: utf-8 -*-

"""Tests for the Google translator.

Google's endpoint answers with an HTML page rather than JSON, so the coverage is the request shape
and the extraction of the translated text from ``<div class="result-container">``.
"""

import unittest

from resources.lib.common.language import Language
from resources.lib.tests import translator_testcase
from resources.lib.translation.google_translator import GoogleTranslator

GOOGLE_RESULT = '<html><div class="result-container">Hola &amp; adi&#243;s</div></html>'


class GoogleTranslatorTest(translator_testcase.TranslatorTestCase):

    def test_translates_and_builds_the_expected_request(self):
        translator = GoogleTranslator(self.settings)
        client = self.attach(translator, (200, GOOGLE_RESULT))

        self.assertEqual(["Hola & adiós"], translator.translate(
            Language.english, Language.spanish, ["Hello"]))

        self.assertEqual(1, len(client.requests))
        self.assertEqual("https://translate.google.com:443/m?sl=en&tl=es&q=Hello", client.requests[0].url)
        self.assertEqual("GET", client.requests[0].method)

    def test_url_encodes_the_text(self):
        translator = GoogleTranslator(self.settings)
        client = self.attach(translator, (200, GOOGLE_RESULT))

        translator.translate(Language.english, Language.spanish, ["Hello there"])

        self.assertIn("q=Hello%20there", client.requests[0].url)


@translator_testcase.requires_network
class GoogleTranslatorOnlineTest(translator_testcase.OnlineTranslatorTestCase):
    """Drives the real endpoint; fails when Google changes or throttles the result page."""

    translator_class = GoogleTranslator


if __name__ == '__main__':
    unittest.main()
