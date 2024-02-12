# -*- coding: utf-8 -*-

import re
import time
from codecs import encode
from typing import Dict, List, Set, Tuple

from resources.lib.httpclient import HttpRequest
from resources.lib.json import from_json
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
    "Azerbaijani": "az",
    "Bangla": "bn",
    "Bashkir": "ba",
    "Basque": "eu",
    "Bhojpuri": "bho",
    "Bodo": "brx",
    "Bosnian": "bs",
    "Bulgarian": "bg",
    "Cantonese (Traditional)": "yue",
    "Catalan": "ca",
    "Chhattisgarhi": "hne",
    "Chinese (Literary)": "lzh",
    "Chinese Simplified": "zh-Hans",
    "Chinese Traditional": "zh-Hant",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dari": "prs",
    "Divehi": "dv",
    "Dogri": "doi",
    "Dutch": "nl",
    "English": "en",
    "Estonian": "et",
    "Faroese": "fo",
    "Fijian": "fj",
    "Filipino": "fil",
    "Finnish": "fi",
    "French (Canada)": "fr-CA",
    "French": "fr",
    "Galician": "gl",
    "Ganda": "lug",
    "Georgian": "ka",
    "German": "de",
    "Greek": "el",
    "Gujarati": "gu",
    "Haitian Creole": "ht",
    "Hausa": "ha",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hmong Daw": "mww",
    "Hungarian": "hu",
    "Icelandic": "is",
    "Igbo": "ig",
    "Indonesian": "id",
    "Inuinnaqtun": "ikt",
    "Inuktitut": "iu",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Kannada": "kn",
    "Kashmiri": "ks",
    "Kazakh": "kk",
    "Khmer": "km",
    "Kinyarwanda": "rw",
    "Konkani": "gom",
    "Korean": "ko",
    "Kurdish (Central)": "ku",
    "Kurdish (Northern)": "kmr",
    "Kyrgyz": "ky",
    "Lao": "lo",
    "Latvian": "lv",
    "Lingala": "ln",
    "Lithuanian": "lt",
    "Lower Sorbian": "dsb",
    "Macedonian": "mk",
    "Maithili": "mai",
    "Malagasy": "mg",
    "Malay": "ms",
    "Malayalam": "ml",
    "Maltese": "mt",
    "Māori": "mi",
    "Marathi": "mr",
    "Mongolian (Cyrillic)": "mn-Cyrl",
    "Mongolian (Traditional)": "mn-Mong",
    "Myanmar (Burmese)": "my",
    "Nepali": "ne",
    "Norwegian": "nb",
    "Nyanja": "nya",
    "Odia": "or",
    "Pashto": "ps",
    "Persian": "fa",
    "Polish": "pl",
    "Portuguese": "pt",
    "Punjabi": "pa",
    "Querétaro Otomi": "otq",
    "Romanian": "ro",
    "Rundi": "run",
    "Russian": "ru",
    "Samoan": "sm",
    "Serbian (Cyrillic)": "sr-Cyrl",
    "Serbian (Latin)": "sr-Latn",
    "Sesotho sa Leboa": "nso",
    "Sesotho": "st",
    "Setswana": "tn",
    "Shona": "sn",
    "Sindhi": "sd",
    "Sinhala": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Somali": "so",
    "Spanish": "es",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tahitian": "ty",
    "Tamil": "ta",
    "Tatar": "tt",
    "Telugu": "te",
    "Thai": "th",
    "Tibetan": "bo",
    "Tigrinya": "ti",
    "Tongan": "to",
    "Turkish": "tr",
    "Turkmen": "tk",
    "Ukrainian": "uk",
    "Upper Sorbian": "hsb",
    "Urdu": "ur",
    "Uyghur": "ug",
    "Uzbek (Latin)": "uz",
    "Vietnamese": "vi",
    "Welsh": "cy",
    "Xhosa": "xh",
    "Yoruba": "yo",
    "Yucatec Maya": "yua",
    "Zulu": "zu",
}

# AbusePreventionHelper.init.apply(this, params_AbusePreventionHelper);
# //rrer":""}}); var params_AbusePreventionHelper = [1707070300340,"MI8IZijShjyAdautxddTdsW1cMBEDWUa",3600000]; var pa
KEY_AND_TOKEN_RE = re.compile(
    r'var params_AbusePreventionHelper\s*=\s*\[(?P<key>\d+)\s*,\s*"(?P<token>[^"]+)"',
    re.IGNORECASE | re.DOTALL
)


class BingTranslator(Translator):

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.supported_languages: Set[Language] = Language.build_languages_set(SUPPORTED_LANGUAGES)

    @property
    def name(self) -> str:
        return "Bing"

    @property
    def short_name(self) -> str:
        return "BG"

    def supports_translation(self, from_language: Language, to_language: Language) -> bool:
        return from_language in self.supported_languages and to_language in self.supported_languages

    def __fetch_key_and_token(self) -> Tuple[str, str]:
        request = HttpRequest("https://www.bing.com/Translator")
        text = self._http_client.exchange(request).get_data_as_text()
        match = KEY_AND_TOKEN_RE.search(text)
        assert match
        return match["key"], match["token"]

    def __fetch_translation(self, from_language: Language, to_language: Language, text: str, key: str, token: str) -> str:
        request = HttpRequest("https://www.bing.com/ttranslatev3?IG=1&IID=1", "POST")
        request.headers = {'Origin': 'https://www.bing.com'}
        request.set_urlencoded_form_data({
            "fromLang": from_language.two_letter_code,
            "to": to_language.two_letter_code,
            "text":  text,
            "key": key,
            "token": token,
        })
        response = self._http_client.exchange(request)
        try:
            response_json = response.get_data_as_json()
            return response_json[0]["translations"][0]["text"]
        except:
            self._logger.warn("Error parsing translation result: " + response.get_data_as_text())
            time.sleep(10)  # cooldown after error
            return None

    def fetch_translation_key_and_token(self, from_language: Language, to_language: Language, text: str, key: str, token: str) -> List[str]:
        translation = self.__fetch_translation(from_language, to_language, text, key, token)
        if translation is None:
            key, token = self.__fetch_key_and_token()
            translation = self.__fetch_translation(from_language, to_language, text, key, token)
        return [translation, key, token]

    def _translate(self, from_language: Language, to_language: Language, texts: List[str]) -> List[str]:
        return self._translate_in_blocks(
            texts,
            500,
            "\n\n",
            lambda text, key, token: self.fetch_translation_key_and_token(from_language, to_language, text, key, token),
            self.__fetch_key_and_token())
