# -*- coding: utf-8 -*-

import logging
from typing import Dict, List

from resources.lib.common.settings import Settings
from resources.lib.providers.addic7edsourceprovider import \
    Addic7edSourceProvider
from resources.lib.providers.cleanupdecoratorprovider import \
    CleanupDecoratorProvider
from resources.lib.providers.compositeprovider import CompositeProvider
from resources.lib.providers.filesystemsourceprovider import \
    FileSystemSourceProvider
from resources.lib.providers.localsourceprovider import LocalSourceProvider
from resources.lib.providers.opensubtitlessourceprovider import \
    OpenSubtitlesSourceProvider
from resources.lib.providers.provider import Provider
from resources.lib.providers.subdivxsourceprovider import SubDivXSourceProvider
from resources.lib.providers.subscenesourceprovider import \
    SubsceneSourceProvider
from resources.lib.providers.translationsdecoratorprovider import \
    TranslationsDecoratorProvider
from resources.lib.translation.translatorsregistry import TranslatorsRegistry


class ProvidersRegistry:

    _logger: logging.Logger = logging.getLogger("UniversalSubs.ProvidersRegistry")

    def __init__(self, settings: Settings):
        self._providers: Dict[str, Provider] = {
            provider.name: provider
            for provider in [
                SubsceneSourceProvider(settings),
                SubDivXSourceProvider(settings),
                OpenSubtitlesSourceProvider(settings),
                Addic7edSourceProvider(settings),
                LocalSourceProvider(settings),
                FileSystemSourceProvider(settings),
            ]
        }

    def get_provider(self, name: str) -> Provider | None:
        """The registered provider with that name, or None when the name is not registered.

        A name can be unknown because the Kodi setting still holds a provider removed from this
        version, so callers get None instead of a KeyError and can skip it.
        """
        provider = self._providers.get(name)
        if provider is None:
            self._logger.warning("Ignoring unknown provider name '%s'; known providers: %s",
                                 name, ", ".join(sorted(self._providers)))
        return provider

    def get_providers(self, names: List[str]) -> List[Provider]:
        """The registered providers among those names, preserving their order and skipping unknown ones."""
        return [provider for provider in (self.get_provider(name) for name in names) if provider is not None]

    @staticmethod
    def __build_from_source_providers(settings: Settings) -> Provider:
        providersRegistry = ProvidersRegistry(settings)
        providers = providersRegistry.get_providers(settings.providers)
        if not providers:
            # Every configured name was unknown (a stale setting after a provider removal); searching
            # nothing is better than crashing, and the warning above names the offending value.
            ProvidersRegistry._logger.error(
                "No registered provider was configured (configured: %s); searches will return no results",
                settings.providers)
        elif len(providers) == 1:
            return providers[0]
        return CompositeProvider(providers)

    @staticmethod
    def __build_from_translators(provider: Provider, settings: Settings) -> Provider:
        if not settings.translators:
            return provider
        translators_registry = TranslatorsRegistry(settings)
        translators = translators_registry.get_translators(settings.translators)
        return TranslationsDecoratorProvider(provider, translators, settings.translation_extra_languages)

    @staticmethod
    def __build_from_cleanup(provider: Provider, settings: Settings) -> Provider:
        if not settings.clean_up_subtitles:  # not settings.clean_up_ads and not settings.clean_up_hi_markers:
            return provider
        return CleanupDecoratorProvider(provider, settings)

    @staticmethod
    def build_from_settings(settings: Settings) -> Provider:
        provider = ProvidersRegistry.__build_from_source_providers(settings)
        provider = ProvidersRegistry.__build_from_translators(provider, settings)
        provider = ProvidersRegistry.__build_from_cleanup(provider, settings)
        return provider
