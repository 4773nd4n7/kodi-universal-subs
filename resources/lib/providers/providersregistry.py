# -*- coding: utf-8 -*-

import logging
from typing import Dict, List

from resources.lib.providers.addic7edsourceprovider import \
    Addic7edSourceProvider
from resources.lib.providers.compositeprovider import CompositeProvider
from resources.lib.providers.filesystemsourceprovider import \
    FileSystemSourceProvider
from resources.lib.providers.opensubtitlessourceprovider import \
    OpenSubtitlesSourceProvider
from resources.lib.providers.podnapisisourceprovider import \
    PodnapisiSourceProvider
from resources.lib.providers.provider import Provider
from resources.lib.providers.subdivxsourceprovider import SubDivXSourceProvider
from resources.lib.providers.translationsdecoratorprovider import \
    TranslationsDecoratorProvider
from resources.lib.settings import Settings
from resources.lib.translation.translatorsregistry import TranslatorsRegistry


class ProvidersRegistry:

    def __init__(self, settings: Settings):
        self._logger: logging.Logger = logging.getLogger("UniversalSubs.ProvidersRegistry")
        self._providers: Dict[str, Provider] = {
            provider.name: provider
            for provider in [
                PodnapisiSourceProvider(settings),
                SubDivXSourceProvider(settings),
                OpenSubtitlesSourceProvider(settings),
                FileSystemSourceProvider(settings),
                Addic7edSourceProvider(settings)
            ]
        }

    def get_providers(self, names: List[str]) -> List[Provider]:
        return [self._providers[name] for name in names]

    @staticmethod
    def build_from_settings(settings: Settings) -> Provider:
        providersRegistry = ProvidersRegistry(settings)
        provider = CompositeProvider(providersRegistry.get_providers(settings.providers))
        if settings.translators:
            translators_registry = TranslatorsRegistry(settings)
            translators = translators_registry.get_translators(settings.translators)
            return TranslationsDecoratorProvider(provider, translators, settings.translation_extra_languages)
        else:
            return provider
