# -*- coding: utf-8 -*-

import re
from typing import Dict, List, Set

from resources.lib.httpclient import HttpRequest
from resources.lib.json import from_json
from resources.lib.language import Language
from resources.lib.settings import Settings
from resources.lib.translation.translator import Translator

SUPPORTED_LANGUAGES: Dict[str, str] = {
    "Albanian": "sq",
    "Arabic": "ar",
    "Azerbaijani": "az",
    "Bengali": "bn",
    "Bulgarian": "bg",
    "Catalan": "ca",
    "Chinese (Traditional)": "zt",
    "Chinese": "zh",
    "Czech": "cs",
    "Danish": "da",
    "Dutch": "nl",
    "English": "en",
    "Esperanto": "eo",
    "Estonian": "et",
    "Finnish": "fi",
    "French": "fr",
    "German": "de",
    "Greek": "el",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hungarian": "hu",
    "Indonesian": "id",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Malay": "ms",
    "Norwegian": "nb",
    "Persian": "fa",
    "Polish": "pl",
    "Portuguese": "pt",
    "Romanian": "ro",
    "Russian": "ru",
    "Serbian": "sr",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Spanish": "es",
    "Swedish": "sv",
    "Tagalog": "tl",
    "Thai": "th",
    "Turkish": "tr",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Vietnamese": "vi",
}

SECRET_RE = re.compile(r'\sapiSecret: "(?P<secret>[^"]+)"', re.IGNORECASE | re.DOTALL)


class LibreTranslator(Translator):

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.supported_languages: Set[Language] = Language.build_languages_set(SUPPORTED_LANGUAGES)

    @property
    def name(self) -> str:
        return "Libre"

    @property
    def short_name(self) -> str:
        return "LB"

    def supports_translation(self, from_language: Language, to_language: Language) -> bool:
        return from_language in self.supported_languages and to_language in self.supported_languages

    def __fetch_secret(self) -> str:
        request = HttpRequest("https://libretranslate.com/js/app.js?v=1.5.5")
        text = self._http_client.exchange(request).get_data_as_text()
        match = SECRET_RE.search(text)
        assert match
        return match["secret"]

    def __fetch_translation(self, from_language: Language, to_language: Language, text: str, secret: str) -> str:
        # request = HttpRequest("https://libretranslate.com/translate", "POST")
        # request.set_json_data({
        #     "q": text_chunk,
        #     "source": from_language.two_letter_code,
        #     "target": to_language.two_letter_code,
        #     "format": "text",
        #     "api_key": ""
        # })
        request = HttpRequest("https://libretranslate.com/translate", "POST")
        request.throw_on_error_codes = False
        request.headers = {'Origin': 'https://libretranslate.com'}
        request.set_urlencoded_form_data({
            "q": text,
            "source": from_language.two_letter_code,
            "target": to_language.two_letter_code,
            "format": "text",
            "secret": secret,
        })
        response = self._http_client.exchange(request)
        if response.status_code == 400:
            return None
        response_json = response.get_data_as_json()
        return response_json["translatedText"]

    def fetch_translation_and_secret(self, from_language: Language, to_language: Language, text: str, secret: str) -> List[str]:
        translation = self.__fetch_translation(from_language, to_language, text, secret)
        if translation is None:
            secret = self.__fetch_secret()
            translation = self.__fetch_translation(from_language, to_language, text, secret)
        return [translation, secret]

    def _translate(self, from_language: Language, to_language: Language, texts: List[str]) -> List[str]:
        return self._translate_in_blocks(
            texts,
            2000,
            "\n\n",
            lambda text, s: self.fetch_translation_and_secret(from_language, to_language, text, s),
            [self.__fetch_secret()])
