# -*- coding: utf-8 -*-

"""SubDL (subdl.com) source provider.

SubDL exposes a documented search API (https://subdl.com/api-doc) that needs an API key from the
user's account; free keys allow 2,000 requests a day. The API answers with JSON, and its download
links are ZIP archives served from dl.subdl.com, which ``SourceProvider`` already knows how to
unpack. The key is a setting, so a user without one simply gets no results from this provider.
"""

from typing import Dict, List, Optional
from urllib.parse import quote

from resources.lib.common.language import Language, NAME_TO_TREE_LETTER_CODE, \
    NAME_TO_TWO_LETTER_CODE
from resources.lib.common.mapped_languages import MappedLanguages
from resources.lib.common.settings import Settings
from resources.lib.providers.get_request import GetRequest
from resources.lib.providers.get_result import GetResult
from resources.lib.providers.search_request import SearchRequest
from resources.lib.providers.search_result import SearchResult
from resources.lib.providers.source_provider import SourceProvider
from resources.lib.utils.http_client import HttpRequest
from resources.lib.utils.text import normalize_white_space

API_URL = "https://api.subdl.com/api/v1/subtitles"
DOWNLOAD_URL = "https://dl.subdl.com"
CLIENT_NAME = "kodi"
SUBS_PER_PAGE = 30

#: SubDL identifies languages with upper-case ISO 639-1 codes ("EN", "FR"). Build the supported
#: set from the codes the add-on already knows, so the two can never drift apart; the names that
#: have no three-letter code are left out because Language equality compares both codes.
SUPPORTED_LANGUAGES: List[Language] = [
    Language(name, two_letter_code=two_letter_code,
             three_letter_code=NAME_TO_TREE_LETTER_CODE[name], standard=False)
    for name, two_letter_code in NAME_TO_TWO_LETTER_CODE.items()
    if two_letter_code and len(two_letter_code) == 2 and name in NAME_TO_TREE_LETTER_CODE
]

LANGUAGE_BY_CODE: Dict[str, Language] = {
    language.two_letter_code.upper(): language for language in SUPPORTED_LANGUAGES
}


def download_url_from_api_url(url: str) -> str:
    """The download path without the API key SubDL appends to it.

    The API answers with ``/subtitle/<id>.zip?api_key=…``, but ``dl.subdl.com`` serves that path
    without any credential. Keeping the query would put the key into the search result id, the Kodi
    log, and the plugin URL Kodi calls, for no benefit.
    """
    return (url or "").split("?", 1)[0]


class SubDlSourceProvider(SourceProvider):

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, MappedLanguages(SUPPORTED_LANGUAGES, {}))

    @property
    def name(self) -> str:
        return "SubDL"

    @property
    def short_name(self) -> str:
        return "SD"

    def missing_credentials(self) -> str:
        if not (self._settings.subdl_api_key or "").strip():
            return "SubDL needs an API key"
        return ""

    def __build_api_params(self, request: SearchRequest, request_internal_languages: List[Language]) -> Dict[str, object]:
        params: Dict[str, object] = {
            "api_key": (self._settings.subdl_api_key or "").strip(),
            "subs_per_page": SUBS_PER_PAGE,
            "releases": 1,
            "client": CLIENT_NAME,
        }
        if request.is_manual_search:
            params["film_name"] = request.manual_search_text
        elif request.is_show_search:
            params["film_name"] = request.show_title
            params["type"] = "tv"
            if request.show_season_number is not None:
                params["season_number"] = request.show_season_number
            if request.show_episode_number is not None:
                params["episode_number"] = request.show_episode_number
        else:
            params["film_name"] = request.title
            params["type"] = "movie"
            if request.year:
                params["year"] = request.year
        language_codes = [language.two_letter_code.upper() for language in request_internal_languages
                          if language.two_letter_code]
        if language_codes:
            params["languages"] = ",".join(language_codes)
        return params

    def __parse_result(self,
                       request_internal_languages: List[Language],
                       title: str,
                       entry: dict) -> Optional[SearchResult]:
        url = download_url_from_api_url(entry.get("url") or "")
        if not url:
            return None
        result = SearchResult()
        result.id = url
        result.title = title
        result.release_info = normalize_white_space(entry.get("release_name") or entry.get("name") or "")
        language = LANGUAGE_BY_CODE.get((entry.get("language") or "").upper())
        if language is None:
            # The API documents the field but older payloads omit it; when the request asked for a
            # single language there is no ambiguity left to resolve.
            language = request_internal_languages[0] if len(request_internal_languages) == 1 else Language.unknown
        if request_internal_languages and language not in request_internal_languages:
            return None
        result.language = language
        result.is_hearing_impaired = bool(entry.get("hi"))
        return result

    def _fetch_search_results(self, request: SearchRequest, request_internal_languages: List[Language]) -> List[SearchResult]:
        if not (self._settings.subdl_api_key or "").strip():
            self._logger.warning("SubDL API key is not configured; skipping the search")
            return []

        http_request = HttpRequest(API_URL)
        http_request.add_url_query_params(self.__build_api_params(request, request_internal_languages))
        payload = self._http_client.exchange(http_request).get_data_as_json()
        if not isinstance(payload, dict) or not payload.get("status"):
            self._logger.warning("SubDL returned an error response: %s",
                                 payload if not isinstance(payload, dict) else payload.get("error"))
            return []

        titles = payload.get("results") or []
        title = (titles[0].get("name") if titles else None) or self._build_search_term(request)
        results: List[SearchResult] = []
        seen_ids = set()
        for entry in payload.get("subtitles") or []:
            result = self.__parse_result(request_internal_languages, title, entry)
            if result is None or result.id in seen_ids:
                continue
            seen_ids.add(result.id)
            results.append(result)
            if request.max_results and len(results) >= request.max_results:
                break
        return results

    def _get(self, request: GetRequest) -> List[GetResult]:
        url = download_url_from_api_url(request.search_result_id)
        if not url.startswith("http"):
            url = DOWNLOAD_URL + url
        api_key = (self._settings.subdl_api_key or "").strip()
        if api_key:
            # dl.subdl.com only authorises through the query parameter (it ignores the key as a
            # header), so the key is attached here instead of travelling in the search result id
            # that Kodi stores, logs and passes back.
            url += ("&" if "?" in url else "?") + "api_key=" + quote(api_key, safe="")
        http_response = self._http_client.exchange(HttpRequest(url))
        file_name = http_response.file_name or url.rsplit("/", 1)[-1] or "subtitle.zip"
        return self._process_get_subtitles_data(file_name, http_response.data)
