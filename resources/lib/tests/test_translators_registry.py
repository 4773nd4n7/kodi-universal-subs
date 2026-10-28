# -*- coding: utf-8 -*-

"""Tests for ``TranslatorsRegistry``: the translators it builds and how they are looked up."""

import unittest

from resources.lib.tests import translator_testcase
from resources.lib.translation.google_translator import GoogleTranslator
from resources.lib.translation.translators_registry import TranslatorsRegistry


class TranslatorsRegistryTest(translator_testcase.TranslatorTestCase):

    def test_exposes_the_registered_translators_by_name(self):
        registry = TranslatorsRegistry(self.settings)
        translators = registry.get_translators(["Bing", "Google"])
        self.assertEqual(["Bing", "Google"], [translator.name for translator in translators])

    def test_returns_the_registered_instance(self):
        registry = TranslatorsRegistry(self.settings)
        self.assertIsInstance(registry.get_translators(["Google"])[0], GoogleTranslator)

    def test_skips_unknown_names(self):
        # A Kodi setting can still name a translator that a later version removed.
        registry = TranslatorsRegistry(self.settings)
        self.assertEqual(["Google"], [translator.name for translator in
                                      registry.get_translators(["Removed", "Google"])])

    def test_returns_nothing_for_no_names(self):
        registry = TranslatorsRegistry(self.settings)
        self.assertEqual([], registry.get_translators())


if __name__ == '__main__':
    unittest.main()
