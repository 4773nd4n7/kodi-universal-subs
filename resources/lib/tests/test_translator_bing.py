# -*- coding: utf-8 -*-

"""Tests for the Bing translator.

Bing needs a key and a token scraped from the translator page before it accepts a translation
request, and those expire: the translator scrapes a fresh pair when a response cannot be parsed.
"""

import unittest
from unittest import mock
from urllib.parse import parse_qs

from resources.lib.common.language import Language
from resources.lib.tests import translator_testcase
from resources.lib.translation import bing_translator
from resources.lib.translation.bing_translator import BingTranslator

BING_PAGE = '<script>var params_AbusePreventionHelper = [1707070300340,"TOKEN-1",3600000];</script>'
BING_PAGE_REFRESHED = '<script>var params_AbusePreventionHelper = [1707070399999,"TOKEN-2",3600000];</script>'
BING_RESULT = '[{"translations":[{"text":"Hola"}]}]'


class BingTranslatorTest(translator_testcase.TranslatorTestCase):

    def test_translates_with_the_key_and_token_scraped_from_the_page(self):
        translator = BingTranslator(self.settings)
        client = self.attach(translator, (200, BING_PAGE), (200, BING_RESULT))

        self.assertEqual(["Hola"], translator.translate(
            Language.english, Language.spanish, ["Hello"]))

        self.assertEqual(2, len(client.requests))
        self.assertEqual("POST", client.requests[1].method)
        form_data = parse_qs(client.requests[1].data.decode())
        self.assertEqual(["Hello"], form_data["text"])
        self.assertEqual(["en"], form_data["fromLang"])
        self.assertEqual(["es"], form_data["to"])
        self.assertEqual(["1707070300340"], form_data["key"])
        self.assertEqual(["TOKEN-1"], form_data["token"])

    def test_refreshes_the_token_when_the_translation_cannot_be_parsed(self):
        translator = BingTranslator(self.settings)
        client = self.attach(translator, (200, BING_PAGE), (200, "not json"),
                             (200, BING_PAGE_REFRESHED), (200, BING_RESULT))

        # The error path waits ten seconds before retrying; the tests do not.
        with mock.patch.object(bing_translator.time, "sleep"):
            self.assertEqual(["Hola"], translator.translate(
                Language.english, Language.spanish, ["Hello"]))

        self.assertEqual(4, len(client.requests))
        retried_form_data = parse_qs(client.requests[3].data.decode())
        self.assertEqual(["TOKEN-2"], retried_form_data["token"])
        self.assertEqual(["1707070399999"], retried_form_data["key"])


@translator_testcase.requires_network
class BingTranslatorOnlineTest(translator_testcase.OnlineTranslatorTestCase):
    """Drives the real endpoint; fails when the token page changes shape."""

    translator_class = BingTranslator


if __name__ == '__main__':
    unittest.main()
