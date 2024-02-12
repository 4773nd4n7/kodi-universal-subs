# -*- coding: utf-8 -*-

from typing import List, Set, Tuple
from urllib.parse import parse_qs, urlparse

from bs4 import ResultSet, Tag

from resources.lib.httpclient import HttpRequest
from resources.lib.language import Language
from resources.lib.providers.getrequest import GetRequest
from resources.lib.providers.getresult import GetResult
from resources.lib.providers.searchrequest import SearchRequest
from resources.lib.providers.searchresult import SearchResult
from resources.lib.providers.sourceprovider import SourceProvider
from resources.lib.settings import Settings
from resources.lib.xml import from_xml

SUPPORTED_LANGUAGES = {
    "Afrikaans": "af",
    "Albanian": "sq",
    "Amharic": "am",
    "Arabic": "ar",
    "Aragonese": "an",
    "Argentino": "es-ar",
    "Assamese": "as",
    "Azerbaijani": "az",
    "Basque": "eu",
    "Belarus": "be",
    "Bengali": "bn",
    "Bosnian": "bs",
    "Brazilian": "pt-br",
    "Bulgarian": "bg",
    "Cantonese": "yyef",
    "Catalan": "ca",
    "Chinese": "zh",
    "cmn": "Mandarin",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dutch": "nl",
    "Dzongkha": "dz",
    "English": "en",
    "Esperanto": "eo",
    "Estonian": "et",
    "Faroese": "fo",
    "Farsi": "fa",
    "Finnish": "fi",
    "French": "fr",
    "Georgian": "ka",
    "German": "de",
    "Greek": "el",
    "Greenlandic": "kl",
    "Gujarati": "gu",
    "Haitian": "ht",
    "haw": "Hawaiian",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hungarian": "hu",
    "Icelandic": "is",
    "Indonesian": "id",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Javanese": "jv",
    "Kannada": "kn",
    "Kazakh": "kk",
    "Khmer": "km",
    "Kinyarwanda": "rw",
    "Korean": "ko",
    "Kurdish": "ku",
    "Kyrgyz": "ky",
    "Lao": "lo",
    "Latin": "la",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Luxembourgish": "lb",
    "Macedonian": "mk",
    "Malay": "ms",
    "Malayalam": "ml",
    "Maltese": "mt",
    "Marathi": "mr",
    "Mongolian": "mn",
    "Ndonga": "nb",
    "Nepali": "ne",
    "Northern Sami": "se",
    "Norwegian Nynorsk": "nn",
    "Norwegian": "no",
    "Occitan": "oc",
    "Oriya": "or",
    "Panjabi": "pa",
    "Pashto": "ps",
    "Polish": "pl",
    "Portuguese": "pt",
    "Quechua": "qu",
    "Romanian": "ro",
    "Russian": "ru",
    "Serbian (Latin)": "sr-latn",
    "Serbian": "sr",
    "Sinhala": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Spanish": "es",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tagalog": "tl",
    "Tamil": "ta",
    "Telugu": "te",
    "Thai": "th",
    "Turkish": "tr",
    "Turkmen": "tk",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Uyghur": "ug",
    "Vietnamese": "vi",
    "Volapük": "vo",
    "Walloon": "wa",
    "Welsh": "cy",
    "Xhosa": "xh",
    "Zulu": "zu",
}


class PodnapisiSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._supported_languages = Language.build_languages_set(SUPPORTED_LANGUAGES)
        self._http_client.base_url = "https://www.podnapisi.net"
        self._http_client.default_headers["Host"] = "www.podnapisi.net"
        self._http_client.default_headers["Referer"] = "https://www.podnapisi.net"
        self._http_client.default_headers["Accept"] = "text/html,application/xhtml+xml,application/xml"
        self._http_client.default_headers["Accept-Language"] = "en-US,en"

    @property
    def name(self) -> str:
        return "PodnapisiNET"

    @property
    def short_name(self) -> str:
        return "PN"

    @property
    def supported_languages(self) -> Set[Language]:
        return self._supported_languages

    def __fetch_search_results_page(self, request: SearchRequest, supported_request_languages: List[Language], page: int) -> Tuple[ResultSet, int]:
        http_request = HttpRequest("/en/subtitles/search/")
        http_request.add_url_query_params({
            "language": sorted([l.two_letter_code for l in supported_request_languages]),
            "movie_type": ["tv-series", "mini-series"] if request.is_show_search else "movie",
            "type": "episode" if request.is_show_search else None,
            "seasons": request.show_season_number if request.is_show_search else None,
            "episodes": request.show_episode_number if request.is_show_search else None,
            "keywords": request.show_title if request.is_show_search else self._build_search_term(request),
            "page": page
        })
        http_request.headers["Accept-Language"] = ";".join([l.two_letter_code for l in supported_request_languages])
        http_response = self._http_client.exchange(http_request)
        results_html = http_response.get_data_as_html()
        results_tbody = results_html.find('tbody')
        if not results_tbody:
            return [], None
        pagination_ul = results_html.select_one("ul.pagination")
        next_page = None
        if pagination_ul:
            next_page_url = urlparse(pagination_ul.select_one("a.page-link").attrs["href"])
            next_page = next((next_page for next_page in parse_qs(next_page_url.query).get("page", [])), None)
        return results_tbody.find_all("tr", recursive=False), next_page

    def _fetch_search_results(self, request: SearchRequest, supported_request_languages: List[Language]) -> List[SearchResult]:
        results: List[SearchResult] = []
        page = 1
        while page:
            row_tags, page = self.__fetch_search_results_page(request, supported_request_languages, page)
            for row_tag in row_tags:
                # fps = float(row.select_one("td:nth-child(2)").get_text(strip=True))
                cds = int(row_tag.select_one("td:nth-child(3)").get_text(strip=True))
                if self._settings.exclude_splitted_subtitles and cds > 1:
                    continue
                result = SearchResult()
                result.id = row_tag.select_one('a[title="Download subtitles."]').attrs["href"]
                result.title = row_tag.select_one('a[alt="Subtitles\' page"]').get_text(strip=True)
                description_tag = row_tag.select_one("td:nth-child(1) > span:nth-child(2)")
                result.release_info = description_tag.get_text(strip=True) if description_tag else None
                result.is_hearing_impaired = row_tag.select_one('i.text-cc') is not None
                result.language = Language.from_2_or_3_letter_code(
                    row_tag.select_one("abbr.language").get_text(strip=True))
                author_tag = row_tag.select_one(
                    'a[title^="Add "][title$=" to active filters."][href*="&contributors="]')
                result.author = author_tag.get_text(strip=True) if author_tag else None
                rating_tag = row_tag.select_one("div.rating")
                rating_td_tag: Tag = next(p for p in rating_tag.parents if p.name == "td")
                result.rating = float(rating_tag.attrs["data-title"].split("%")[0])/20
                downloads_tag = rating_td_tag.find_previous("td").find_previous("td")
                result.downloads = int(downloads_tag.get_text(strip=True))
                results.append(result)
                if request.max_results and len(results) >= request.max_results:
                    return results
        return results

    def _get(self, request: GetRequest) -> List[GetResult]:
        http_request = HttpRequest(request.search_result_id)
        http_response = self._http_client.exchange(http_request)
        results = self._process_subtitles_data(http_response.file_name, http_response.data)
        return results
