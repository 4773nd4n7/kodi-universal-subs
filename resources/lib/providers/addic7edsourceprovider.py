# -*- coding: utf-8 -*-

import math
import re
import time
from datetime import timedelta
from typing import List, Set, Tuple
from urllib.parse import quote

from bs4 import BeautifulSoup

from resources.lib.httpclient import HttpRequest
from resources.lib.language import Language
from resources.lib.providers.getrequest import GetRequest
from resources.lib.providers.getresult import GetResult
from resources.lib.providers.searchrequest import SearchRequest
from resources.lib.providers.searchresult import SearchResult
from resources.lib.providers.sourceprovider import (SourceProvider,
                                                    find_text_between,
                                                    unescape_html)
from resources.lib.settings import Settings

MAX_TITLES_COUNT = 5


SUPPORTED_LANGUAGES = [
    "Albanian",
    "Arabic",
    "Armenian",
    "Azerbaijani",
    "Bengali",
    "Bosnian",
    "Bulgarian",
    "Cantonese",
    "Catalan",
    "Chinese",
    "Croatian",
    "Czech",
    "Danish",
    "Dutch",
    "English",
    "Estonian",
    "Euskera",
    "Finnish",
    "French",
    "Galego",
    "German",
    "Greek",
    "Hebrew",
    "Hindi",
    "Hungarian",
    "Icelandic",
    "Indonesian",
    "Italian",
    "Japanese",
    "Kannada",
    "Klingon",
    "Korean",
    "Latvian",
    "Lithuanian",
    "Macedonian",
    "Malay",
    "Malayalam",
    "Marathi",
    "Norwegian",
    "Persian",
    "Polish",
    "Portuguese",
    "Romanian",
    "Russian",
    "Serbian",
    "Sinhala",
    "Slovak",
    "Slovenian",
    "Spanish",
    "Swedish",
    "Tagalog",
    "Tamil",
    "Telugu",
    "Thai",
    "Turkish",
    "Ukrainian",
    "Vietnamese",
    "Welsh",
]


class Addic7edSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._supported_languages = Language.build_languages_set(SUPPORTED_LANGUAGES)
        self._http_client.base_url = "https://www.addic7ed.com"
        self._http_client.default_headers["Host"] = "www.addic7ed.com"
        self._http_client.default_headers["Referer"] = "https://www.addic7ed.com"
        self._http_client.default_headers["Accept"] = "text/html,application/xhtml+xml,application/xml"
        self._http_client.default_headers["Accept-Language"] = "en-US,en"

    @property
    def name(self) -> str:
        return "Addic7ed"

    @property
    def short_name(self) -> str:
        return "AD7"

    @property
    def supported_languages(self) -> Set[Language]:
        return self._supported_languages

    @property
    def overrides_ratings_from_downloads(self) -> bool:
        return True

    def __fetch_search_title_urls(self, request: SearchRequest, supported_request_languages: List[Language]) -> List[Tuple[str, str]]:
        http_request = HttpRequest("/search.php", follow_redirects=False)
        http_request.add_url_query_params({"search": self._build_search_term(request), "Submit": "Search"})
        http_response = self._http_client.exchange(http_request)
        titles: List[Tuple[str, str]] = []
        if 300 <= http_response.status_code < 400:
            title_name = self._build_search_term(request)
            title_url = http_response.get_header_value("Location")
            titles.append((title_name, title_url))
        else:
            titles_html = http_response.get_data_as_html()
            title_anchors = titles_html.select('table.tabel[align="center"][width="80%"][border="0"] tr a')
            for title_anchor in title_anchors:
                # title_tr.select_one('img[src$="/film.png"]') # movie result
                # title_tr.select_one('img[src$="/television.png"]') # tv show result
                title_name = title_anchor.get_text(strip=True)
                title_url = title_anchor.attrs["href"]
                titles.append((title_name, title_url))
        return titles

    def _fetch_search_results(self, request: SearchRequest, supported_request_languages: List[Language]) -> List[SearchResult]:
        results: List[SearchResult] = []
        titles = self.__fetch_search_title_urls(request, supported_request_languages)
        for title_index, (title_name, title_url) in enumerate(titles[:MAX_TITLES_COUNT]):
            self._logger.info("Processing search results for title %s" % title_name)
            http_request = HttpRequest(title_url)
            http_request.sleep_before = timedelta(seconds=1) if title_index > 0 else None
            http_response = self._http_client.exchange(http_request)
            results_html = http_response.get_data_as_html()
            results_img = results_html.select('img[src$="images/folder_page.png"]')
            for result_img in results_img:
                result_tbody = result_img.find_parent("tbody")
                result = SearchResult()
                result.language = Language(result_tbody.select_one("td.language").get_text(strip=True))
                if not result.language in supported_request_languages:
                    continue
                result.id = result_tbody.select_one('a.buttonDownload[href^="/original/"]').attrs["href"]
                result.title = title_name
                result.release_info = result_img.parent.get_text(strip=True)
                result.release_info = re.sub(
                    r"^Version (.*), Duration: [\d.]+", r"\1",
                    result.release_info)
                result.author = result_tbody.select_with('a[href^="/user/"]', lambda t: t.get_text(strip=True))
                result.downloads = int(re.sub(
                    r"^\d+ times edited · (\d+) Downloads · \d+ sequences", r"\1",
                    result_tbody.select_one('td.newsDate[colspan="2"]').get_text(strip=True)))
                result.is_hearing_impaired = False  # no way to detect if match has information for  HI
                results.append(result)
                if request.max_results and len(results) >= request.max_results:
                    return results
        return results

    def _get(self, request: GetRequest) -> List[GetResult]:
        http_request = HttpRequest(request.search_result_id)
        http_response = self._http_client.exchange(http_request)
        results = self._process_subtitles_data(http_response.file_name, http_response.data)
        return results
