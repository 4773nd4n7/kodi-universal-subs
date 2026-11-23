# -*- coding: utf-8 -*-

"""Contract tests for the provider registry.

These checks apply to every provider regardless of where it gets its data from, and they run
without touching the network: a provider that cannot serve a request is skipped, unknown names (a
provider removed from the add-on but still stored in the user's Kodi settings) are ignored instead
of breaking every search, and the composition built from the settings matches the configuration.

Run it from the repository root, without installing the add-on into Kodi::

    python -m resources.lib.tests.test_provider_registry -v
"""

import unittest

from resources.lib.common.language import Language
from resources.lib.providers.composite_provider import CompositeProvider
from resources.lib.providers.local_source_provider import LocalSourceProvider
from resources.lib.providers.providers_registry import ProvidersRegistry

from .provider_fixtures import MOVIE_TITLE, MOVIE_YEAR
from .provider_testcase import ProviderTestCase, build_settings

EXPECTED_PROVIDER_NAMES = [
    "Addic7ed",
    "FileSystem",
    "Local",
    "OpenSubtitles",
    "OpenSubtitles.com",
    "SubDivX",
    "SubDL",
    "Subscene",
    "YTS Subs",
]


class ProviderRegistryTest(ProviderTestCase):
    """Checks that apply to every provider, whatever its data source is."""

    def test_registry_exposes_every_provider(self) -> None:
        for provider_name in EXPECTED_PROVIDER_NAMES:
            with self.subTest(provider=provider_name):
                provider = self.registry.get_provider(provider_name)
                self.assertIsNotNone(provider, "Provider %s is not registered" % provider_name)
                self.assertEqual(provider_name, provider.name)
                self.assertEqual("UniversalSubs.Provider." + provider_name, provider.id)
                self.assertTrue(provider.short_name, "Provider %s has no short name" % provider_name)

    def test_get_providers_preserves_the_requested_order(self) -> None:
        provider_names = ["SubDivX", "Local", "OpenSubtitles"]
        self.assertEqual(provider_names, [provider.name for provider in self.registry.get_providers(provider_names)])

    def test_unknown_provider_name_is_ignored(self) -> None:
        # A provider removed from the add-on can still be stored in the user's Kodi settings.
        self.assertIsNone(self.registry.get_provider("PodnapisiNET"))

    def test_get_providers_skips_unknown_names_and_keeps_the_order(self) -> None:
        provider_names = ["Local", "PodnapisiNET", "FileSystem", "NoSuchProvider"]
        self.assertEqual(["Local", "FileSystem"],
                         [provider.name for provider in self.registry.get_providers(provider_names)])

    def test_search_is_skipped_when_the_requested_language_is_not_supported(self) -> None:
        # SubDivX only serves Spanish, so an English search must not reach the network at all.
        provider = self.registry.get_provider("SubDivX")

        def fail_if_called(http_request):
            self.fail("Provider reached the network for a request it cannot serve: %s" % http_request.url)

        provider._http_client.exchange = fail_if_called
        search_request = self.build_movie_search_request(MOVIE_TITLE, MOVIE_YEAR, [Language.english])
        self.assertEqual([], provider.search(search_request))

    def test_build_from_settings_returns_the_single_configured_provider(self) -> None:
        settings = build_settings(self.work_directory.joinpath("single-provider"))
        settings.providers = ["Local"]
        self.assertIsInstance(ProvidersRegistry.build_from_settings(settings), LocalSourceProvider)

    def test_build_from_settings_composes_the_configured_providers(self) -> None:
        settings = build_settings(self.work_directory.joinpath("composed-providers"))
        settings.providers = ["Local", "FileSystem"]
        self.assertIsInstance(ProvidersRegistry.build_from_settings(settings), CompositeProvider)

    def test_build_from_settings_survives_a_configuration_of_only_unknown_names(self) -> None:
        # Kodi keeps a stale provider name in the user's settings after an upgrade; that must not
        # break every search, it should just leave nothing to search.
        settings = build_settings(self.work_directory.joinpath("stale-providers"))
        settings.providers = ["PodnapisiNET"]
        provider = ProvidersRegistry.build_from_settings(settings)
        self.assertIsInstance(provider, CompositeProvider)
        self.assertEqual([], provider.search(self.build_movie_search_request(MOVIE_TITLE, MOVIE_YEAR, [])))

    def test_build_from_settings_ignores_a_removed_translator(self) -> None:
        # "Libre" was removed; a stale settings value naming it must not wrap the provider in a
        # translation layer that has nothing to translate with.
        settings = build_settings(self.work_directory.joinpath("stale-translator"))
        settings.providers = ["Local"]
        settings.translators = ["Libre"]
        self.assertIsInstance(ProvidersRegistry.build_from_settings(settings), LocalSourceProvider)


if __name__ == '__main__':
    unittest.main()
