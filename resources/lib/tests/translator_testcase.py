# -*- coding: utf-8 -*-

"""Shared helpers for the translator test cases.

The translators reach their services only through ``HttpClient.exchange``, so ``FakeHttpClient``
replays a queue of canned responses and records the requests: the tests assert both on the
translation and on what the translator asked the service for, without touching the network.

``TranslatorTestCase`` gives each test case the ``Settings`` a translator needs, isolated in a
temporary directory, plus the ``attach`` helper that swaps in the fake client.
"""

import shutil
import socket
import tempfile
import unittest
from pathlib import Path

from resources.lib.common.language import Language
from resources.lib.tests import provider_testcase
from resources.lib.utils.http_client import HttpResponse

#: Live translator tests run by default, like the live provider tests; set the variable to 0 to skip.
NETWORK_TESTS_ENVIRONMENT_VARIABLE = provider_testcase.NETWORK_TESTS_ENVIRONMENT_VARIABLE

#: ``urllib`` has no timeout of its own; without this a dead service would hang the run.
NETWORK_TIMEOUT_SECONDS = provider_testcase.NETWORK_TIMEOUT_SECONDS

requires_network = unittest.skipUnless(
    provider_testcase.network_tests_enabled(),
    "Live translator tests are disabled by %s=0; unset it to run them against the real services."
    % NETWORK_TESTS_ENVIRONMENT_VARIABLE)


class FakeHttpClient:
    """Stands in for ``HttpClient``, replaying a queue of responses and recording requests."""

    def __init__(self, responses):
        self.requests = []
        self._responses = list(responses)

    def exchange(self, request):
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("unexpected request to %s" % request.url)
        status_code, body = self._responses.pop(0)
        if isinstance(body, str):
            body = body.encode("utf-8")
        return HttpResponse(request, status_code, {}, lambda: body)


class FakeCache:
    """Minimal stand-in for ``resources.lib.utils.cache.Cache``."""

    def __init__(self):
        self.values = {}

    @property
    def is_enabled(self):
        return True

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class TranslatorTestCase(unittest.TestCase):

    work_directory: Path = None
    settings = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.work_directory = Path(tempfile.mkdtemp(prefix="universal-subs-translator-tests-"))
        cls.settings = provider_testcase.build_settings(cls.work_directory)
        cls.addClassCleanup(shutil.rmtree, cls.work_directory, True)

    def attach(self, translator, *responses):
        """Point the translator at a fake client, with one queued response per exchange."""
        client = FakeHttpClient(responses)
        translator._http_client = client
        return client


class OnlineTranslatorTestCase(TranslatorTestCase):
    """Integration tests: drive a translator against the service it really talks to.

    The settings disable the translation cache, so every assertion reaches the network; a failure
    here means the service is down, changed shape, or is refusing this client - which is exactly
    what these tests exist to notice.
    """

    #: The translator class under test.
    translator_class = None

    #: Short, uncontroversial sentences; every service translates these the same way.
    SENTENCES = ["Hello", "Goodbye", "Thank you"]

    translator = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        socket.setdefaulttimeout(NETWORK_TIMEOUT_SECONDS)

    def setUp(self):
        super().setUp()
        self.translator = self.translator_class(self.settings)

    def translate(self, texts):
        try:
            return self.translator.translate(Language.english, Language.spanish, texts)
        except Exception as error:
            self.fail("%s could not translate against the live service: %s: %s" % (
                self.translator_class.__name__, type(error).__name__, error))

    def test_translates_a_single_line(self):
        translations = self.translate(["Hello"])

        self.assertEqual(1, len(translations))
        self.assertTrue(translations[0].strip())
        self.assertNotEqual("Hello", translations[0].strip())

    def test_translates_every_line_of_a_batch(self):
        translations = self.translate(self.SENTENCES)

        self.assertEqual(len(self.SENTENCES), len(translations))
        for source, translation in zip(self.SENTENCES, translations):
            self.assertTrue(translation.strip(), "empty translation for %r" % source)
            self.assertNotEqual(source, translation.strip(), "untranslated text returned for %r" % source)

    def test_translates_hello_to_spanish(self):
        translations = self.translate(["Hello"])

        self.assertIn("hola", translations[0].lower())
