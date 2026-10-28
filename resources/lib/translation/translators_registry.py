# -*- coding: utf-8 -*-

import logging
from typing import Dict, List, Optional

from resources.lib.common.settings import Settings
from resources.lib.translation.bing_translator import BingTranslator
from resources.lib.translation.google_translator import GoogleTranslator
from resources.lib.translation.translator import Translator


class TranslatorsRegistry:

    def __init__(self, settings: Settings):
        self._logger: logging.Logger = logging.getLogger("UniversalSubs.TranslatorsRegistry")
        self._translators: Dict[str, Translator] = {
            translator.name: translator
            for translator in [
                BingTranslator(settings),
                GoogleTranslator(settings)
            ]
        }

    def get_translator(self, name: str) -> Optional[Translator]:
        """The translator registered under that name, or None when it is unknown.

        A name can be unknown because the Kodi setting still holds a translator removed from this
        version, so callers get None instead of a KeyError and can skip it.
        """
        translator = self._translators.get(name)
        if translator is None:
            self._logger.warning("Ignoring unknown translator name '%s'; known translators: %s",
                                 name, ", ".join(sorted(self._translators)))
        return translator

    def get_translators(self, names: List[str] = None) -> List[Translator]:
        """The registered translators among those names, preserving their order and skipping unknown ones."""
        return [translator for translator in (self.get_translator(name) for name in names or [])
                if translator is not None]
