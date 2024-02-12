# -*- coding: utf-8 -*-

import html
import re
from typing import Dict, List, Set
from urllib.parse import quote

from resources.lib.httpclient import HttpRequest
from resources.lib.language import Language
from resources.lib.settings import Settings
from resources.lib.translation.translator import Translator

SUPPORTED_LANGUAGES: Dict[str, str] = {
    "Afrikaans": "af",
    "Albanian": "sq",
    "Amharic": "am",
    "Arabic": "ar",
    "Armenian": "hy",
    "Assamese": "as",
    "Aymara": "ay",
    "Azerbaijani": "az",
    "Bambara": "bm",
    "Basque": "eu",
    "Belarusian": "be",
    "Bengali": "bn",
    "Bhojpuri": "bho",
    "Bosnian": "bs",
    "Bulgarian": "bg",
    "Catalan": "ca",
    "Cebuano": "ceb",
    "Chinese": "zh",
    "Corsican": "co",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dhivehi": "dv",
    "Dogri": "doi",
    "Dutch": "nl",
    "English": "en",
    "Esperanto": "eo",
    "Estonian": "et",
    "Ewe": "ee",
    "Filipino": "fil",
    "Finnish": "fi",
    "French": "fr",
    "Frisian": "fy",
    "Galician": "gl",
    "Georgian": "ka",
    "German": "de",
    "Greek": "el",
    "Guarani": "gn",
    "Gujarati": "gu",
    "Haitian Creole": "ht",
    "Hausa": "ha",
    "Hawaiian": "haw",
    "Hebrew": "he or iw",
    "Hindi": "hi",
    "Hmong": "hmn",
    "Hungarian": "hu",
    "Icelandic": "is",
    "Igbo": "ig",
    "Ilocano": "ilo",
    "Indonesian": "id",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Javanese": "jv",
    "Kannada": "kn",
    "Kazakh": "kk",
    "Khmer": "km",
    "Kinyarwanda": "rw",
    "Konkani": "gom",
    "Korean": "ko",
    "Krio": "kri",
    "Sorani": "ckb",
    "Kurdish": "ku",
    "Kyrgyz": "ky",
    "Lao": "lo",
    "Latin": "la",
    "Latvian": "lv",
    "Lingala": "ln",
    "Lithuanian": "lt",
    "Luganda": "lg",
    "Luxembourgish": "lb",
    "Macedonian": "mk",
    "Maithili": "mai",
    "Malagasy": "mg",
    "Malay": "ms",
    "Malayalam": "ml",
    "Maltese": "mt",
    "Maori": "mi",
    "Marathi": "mr",
    "Manipuri": "mni",
    "Mizo": "lus",
    "Mongolian": "mn",
    "Burmese": "my",
    "Nepali": "ne",
    "Norwegian": "no",
    "Chichewa": "ny",
    "Oriya": "or",
    "Oromo": "om",
    "Pashto": "ps",
    "Persian": "fa",
    "Polish": "pl",
    "Portuguese": "pt",
    "Punjabi": "pa",
    "Quechua": "qu",
    "Romanian": "ro",
    "Russian": "ru",
    "Samoan": "sm",
    "Sanskrit": "sa",
    "Scots Gaelic": "gd",
    "Sepedi": "nso",
    "Serbian": "sr",
    "Sesotho": "st",
    "Shona": "sn",
    "Sindhi": "sd",
    "Sinhala": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Somali": "so",
    "Spanish": "es",
    "Sundanese": "su",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tagalog": "tl",
    "Tajik": "tg",
    "Tamil": "ta",
    "Tatar": "tt",
    "Telugu": "te",
    "Thai": "th",
    "Tigrinya": "ti",
    "Tsonga": "ts",
    "Turkish": "tr",
    "Turkmen": "tk",
    "Akan": "ak",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Uyghur": "ug",
    "Uzbek": "uz",
    "Vietnamese": "vi",
    "Welsh": "cy",
    "Xhosa": "xh",
    "Yiddish": "yi",
    "Yoruba": "yo",
    "Zulu": "zu",
}

RESULT_RE = re.compile(
    r'<div class="result-container">(?P<result>[^<]+)</div>',
    re.IGNORECASE | re.DOTALL
)


class GoogleTranslator(Translator):

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.supported_languages: Set[Language] = Language.build_languages_set(SUPPORTED_LANGUAGES)

    @property
    def name(self) -> str:
        return "Google"

    @property
    def short_name(self) -> str:
        return "GG"

    def supports_translation(self, from_language: Language, to_language: Language) -> bool:
        return from_language in self.supported_languages and to_language in self.supported_languages

    def __fetch_translation(self, from_language: Language, to_language: Language, text: str) -> str:
        request = HttpRequest("https://translate.google.com:443/m?sl=%s&tl=%s&q=%s" %
                              (from_language.two_letter_code, to_language.two_letter_code, quote(text)))
        response = self._http_client.exchange(request)
        result_match = RESULT_RE.search(response.get_data_as_text())
        assert result_match
        return html.unescape(result_match["result"])

    def _translate(self, from_language: Language, to_language: Language, texts: List[str]) -> List[str]:
        return self._translate_in_blocks(texts, 2000, "\n\n", lambda text: self.__fetch_translation(from_language, to_language, text))
