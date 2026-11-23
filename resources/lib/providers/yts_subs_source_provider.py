# -*- coding: utf-8 -*-

"""YTS Subs (yts-subs.com) source provider.

The site lists subtitles per YIFY movie, addressed by IMDb id (``/movie-imdb/tt0133093``). Its
search box is a typeahead over ``/search/ajax/<text>``, which is what this provider uses to turn a
title into an IMDb id; a keyword search on the site itself does not exist. Each row's download
button opens a detail page whose ``data-link`` attribute is a base64-encoded ZIP URL, so the
download is a plain file fetch that ``SourceProvider`` already knows how to unpack.

The site only indexes movies, so TV show searches return nothing.
"""

import base64
import re
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from resources.lib.common.language import Language
from resources.lib.common.mapped_languages import MappedLanguages
from resources.lib.common.settings import Settings
from resources.lib.providers.get_request import GetRequest
from resources.lib.providers.get_result import GetResult
from resources.lib.providers.search_request import SearchRequest
from resources.lib.providers.search_result import SearchResult
from resources.lib.providers.source_provider import SourceProvider
from resources.lib.utils.http_client import HttpRequest
from resources.lib.utils.text import normalize_text, normalize_white_space

BASE_URL = "https://yts-subs.com"
DOWNLOAD_DATA_LINK_RE = re.compile(r'data-link="(?P<link>[A-Za-z0-9+/=]+)"')

#: Language names the site prints in its "Language" column.
SITE_LANGUAGE_NAMES = [
    "Arabic", "Azerbaijani", "Bengali", "Bulgarian", "Burmese", "Chinese", "Croatian",
    "Czech", "Danish", "Dutch", "English", "Estonian", "Finnish", "French", "German",
    "Greek", "Hebrew", "Hungarian", "Indonesian", "Italian", "Japanese", "Korean", "Malay",
    "Macedonian", "Norwegian", "Persian", "Polish", "Portuguese", "Romanian", "Russian",
    "Serbian", "Slovenian", "Spanish", "Swedish", "Thai", "Turkish", "Urdu", "Vietnamese",
]

#: The site's own labels for those two, mapped onto the canonical languages.
LANGUAGE_MAPPINGS: Dict[Language, List[Language]] = {
    Language.portuguese: [Language("Brazilian Portuguese", standard=False)],
    Language("Persian"): [Language("Farsi/Persian", standard=False)],
}

SUPPORTED_LANGUAGES: List[Language] = [Language(name) for name in SITE_LANGUAGE_NAMES]


class YtsSubsSourceProvider(SourceProvider):

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, MappedLanguages(SUPPORTED_LANGUAGES, LANGUAGE_MAPPINGS))

    @property
    def name(self) -> str:
        return "YTS Subs"

    @property
    def short_name(self) -> str:
        return "YTS"

    def __search_movies(self, term: str) -> List[dict]:
        request = HttpRequest("%s/search/ajax/%s" % (BASE_URL, quote(term, safe="")))
        payload = self._http_client.exchange(request).get_data_as_json()
        return payload if isinstance(payload, list) else []

    def __pick_movie(self, request: SearchRequest, candidates: List[dict]) -> Optional[dict]:
        """The typeahead is a substring match, so pick the entry that is really the requested film."""
        wanted_title = normalize_text(request.manual_search_text if request.is_manual_search else request.title)
        best_candidate = None
        best_score = -1
        for candidate in candidates:
            candidate_title = normalize_text(candidate.get("mov_title") or "")
            score = 0
            if candidate_title == wanted_title:
                score += 2
            elif wanted_title and wanted_title in candidate_title:
                score += 1
            if request.year and str(candidate.get("mov_year")) == str(request.year):
                score += 2
            if score > best_score:
                best_candidate, best_score = candidate, score
        return best_candidate

    def __resolve_language(self, language_name: str) -> Language:
        external = self._supported_languages.get_external_by_name(language_name)
        return self._supported_languages.to_internal_first(external)

    def __parse_subtitle_rows(self,
                              request_internal_languages: List[Language],
                              title: str,
                              page_html: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        soup = BeautifulSoup(page_html, "html.parser")
        for row in soup.select("table.other-subs tbody tr"):
            download_anchor = row.select_one("a.subtitle-download")
            language_span = row.select_one("span.sub-lang")
            if download_anchor is None or language_span is None:
                continue
            language = self.__resolve_language(language_span.get_text(strip=True))
            if language == Language.unknown:
                continue
            if request_internal_languages and language not in request_internal_languages:
                continue
            release_anchor = row.select("td")[2].select_one("a")
            result = SearchResult()
            result.id = download_anchor.get("href")
            result.title = title
            result.release_info = normalize_white_space(
                re.sub(r"^\s*subtitle\s*", "", release_anchor.get_text(" ", strip=True))) if release_anchor else None
            result.language = language
            result.author = normalize_white_space(row.select_one("td.uploader-cell").get_text(strip=True)) \
                if row.select_one("td.uploader-cell") else None
            rating_text = row.select_one("td.rating-cell span")
            try:
                # The column runs from negative numbers upwards; SearchResult allows 0.0 to 5.0.
                result.rating = max(0.0, min(5.0, float(rating_text.get_text(strip=True) if rating_text else 0)))
            except ValueError:
                result.rating = 0.0
            results.append(result)
        return results

    def _fetch_search_results(self, request: SearchRequest, request_internal_languages: List[Language]) -> List[SearchResult]:
        if request.is_show_search:
            self._logger.info("YTS Subs only indexes movies, skipping the show search")
            return []
        term = request.manual_search_text if request.is_manual_search else request.title
        movie = self.__pick_movie(request, self.__search_movies(term))
        if movie is None:
            self._logger.info("YTS Subs has no movie matching '%s'", term)
            return []

        title = movie.get("mov_title") or term
        movie_url = "%s/movie-imdb/%s" % (BASE_URL, quote(movie["mov_imdb_code"]))
        page_html = self._http_client.exchange(HttpRequest(movie_url)).get_data_as_text()
        results: List[SearchResult] = []
        seen_ids = set()
        for result in self.__parse_subtitle_rows(request_internal_languages, title, page_html):
            if result.id in seen_ids:
                continue
            seen_ids.add(result.id)
            results.append(result)
            if request.max_results and len(results) >= request.max_results:
                break
        return results

    def _get(self, request: GetRequest) -> List[GetResult]:
        page_html = self._http_client.exchange(
            HttpRequest("%s%s" % (BASE_URL, request.search_result_id))).get_data_as_text()
        match = DOWNLOAD_DATA_LINK_RE.search(page_html)
        if not match:
            self._logger.warning("YTS Subs did not expose a download link for %s", request.search_result_id)
            return []
        download_url = base64.b64decode(match.group("link")).decode("utf-8")
        http_response = self._http_client.exchange(HttpRequest(download_url))
        file_name = urlparse(download_url).path.rsplit("/", 1)[-1] or "subtitle.zip"
        return self._process_get_subtitles_data(file_name, http_response.data)
