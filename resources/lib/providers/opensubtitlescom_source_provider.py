# -*- coding: utf-8 -*-

"""OpenSubtitles.com source provider.

The old ``OpenSubtitles`` provider scrapes opensubtitles.org; this one talks to the REST API of
opensubtitles.com, which is a different service with its own catalogue.

The API needs an API key (free from the OpenSubtitles.com developer page) and, for downloads, a
user login: ``GET /subtitles`` returns ``file_id`` values, and ``POST /download`` exchanges one for
a link, authenticated with the token returned by ``POST /login``. Free accounts have a daily
download quota, so the token is kept for the lifetime of the provider instance and reused.
"""

from typing import Dict, List, Optional
from urllib import error as urllib_error
from urllib.parse import urlparse

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

API_URL = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "UniversalSubs Kodi add-on"

SUPPORTED_LANGUAGES: List[Language] = [
    Language(name, two_letter_code=two_letter_code,
             three_letter_code=NAME_TO_TREE_LETTER_CODE[name], standard=False)
    for name, two_letter_code in NAME_TO_TWO_LETTER_CODE.items()
    if two_letter_code and len(two_letter_code) == 2 and name in NAME_TO_TREE_LETTER_CODE
]

LANGUAGE_BY_CODE: Dict[str, Language] = {
    language.two_letter_code.lower(): language for language in SUPPORTED_LANGUAGES
}


class OpenSubtitlesComSourceProvider(SourceProvider):

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, MappedLanguages(SUPPORTED_LANGUAGES, {}))
        self.__token: Optional[str] = None

    @property
    def name(self) -> str:
        return "OpenSubtitles.com"

    @property
    def short_name(self) -> str:
        return "OSC"

    @property
    def _api_key(self) -> str:
        return (self._settings.opensubtitles_com_api_key or "").strip()

    def missing_credentials(self) -> str:
        if not self._api_key:
            return "OpenSubtitles.com needs an API key"
        if not (self._settings.opensubtitles_com_username or "").strip() \
                or not self._settings.opensubtitles_com_password:
            return "OpenSubtitles.com needs a username and password to download subtitles"
        return ""

    def __build_headers(self, authenticated: bool = False) -> Dict[str, str]:
        headers = {
            "Api-Key": self._api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if authenticated and self.__token:
            headers["Authorization"] = "Bearer " + self.__token
        return headers

    def __login(self) -> Optional[str]:
        """Exchange the configured credentials for a token, once per provider instance."""
        if self.__token:
            return self.__token
        username = (self._settings.opensubtitles_com_username or "").strip()
        password = self._settings.opensubtitles_com_password or ""
        if not username or not password:
            self._logger.warning("OpenSubtitles.com username and password are required to download subtitles")
            return None
        request = HttpRequest(API_URL + "/login", "POST")
        request.headers = self.__build_headers()
        request.set_json_data({"username": username, "password": password})
        try:
            response = self._http_client.exchange(request)
        except urllib_error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            raise RuntimeError(
                "OpenSubtitles.com login failed for %s (%s): %s" % (
                    username, error.code, body[:400])) from None
        payload = response.get_data_as_json()
        self.__token = payload.get("token") if isinstance(payload, dict) else None
        if not self.__token:
            self._logger.warning("OpenSubtitles.com login failed: %s", payload)
        return self.__token

    def __build_api_params(self, request: SearchRequest, request_internal_languages: List[Language]) -> Dict[str, object]:
        params: Dict[str, object] = {"type": "episode" if request.is_show_search else "movie"}
        if request.is_manual_search:
            params["query"] = request.manual_search_text
        elif request.is_show_search:
            params["query"] = request.show_title
            if request.show_season_number is not None:
                params["season_number"] = request.show_season_number
            if request.show_episode_number is not None:
                params["episode_number"] = request.show_episode_number
        else:
            params["query"] = request.title
            if request.year:
                params["year"] = request.year
        language_codes = [language.two_letter_code.lower() for language in request_internal_languages
                          if language.two_letter_code]
        if language_codes:
            params["languages"] = ",".join(language_codes)
        return params

    def __parse_result(self,
                       request_internal_languages: List[Language],
                       title: str,
                       entry: dict) -> Optional[SearchResult]:
        attributes = entry.get("attributes") or {}
        files = attributes.get("files") or []
        if not files or not files[0].get("file_id"):
            return None
        file = files[0]
        language = LANGUAGE_BY_CODE.get((attributes.get("language") or "").lower())
        if language is None:
            language = request_internal_languages[0] if len(request_internal_languages) == 1 else Language.unknown
        if request_internal_languages and language not in request_internal_languages:
            return None
        result = SearchResult()
        # The download endpoint needs the file id; the file name is kept so the unpacked subtitle
        # can be named after it instead of after the id.
        result.id = "%s|%s" % (file["file_id"], file.get("file_name") or "")
        # For episodes ``title`` is the episode name ("Pilot") and ``parent_title`` is the show.
        details = attributes.get("feature_details") or {}
        result.title = details.get("parent_title") or details.get("title") \
            or attributes.get("movie_name") or title
        result.release_info = normalize_white_space(attributes.get("release") or file.get("file_name") or "")
        result.language = language
        result.is_hearing_impaired = bool(attributes.get("hearing_impaired"))
        result.downloads = attributes.get("download_count") if attributes.get("download_count") is not None else -1
        # The API rates subtitles from 0 to 10; SearchResult documents 0.0 to 5.0.
        rating = attributes.get("ratings")
        result.rating = min(5.0, float(rating) / 2) if rating else 0.0
        return result

    def _fetch_search_results(self, request: SearchRequest, request_internal_languages: List[Language]) -> List[SearchResult]:
        if not self._api_key:
            self._logger.warning("OpenSubtitles.com API key is not configured; skipping the search")
            return []

        http_request = HttpRequest(API_URL + "/subtitles")
        http_request.headers = self.__build_headers()
        http_request.add_url_query_params(self.__build_api_params(request, request_internal_languages))
        payload = self._http_client.exchange(http_request).get_data_as_json()
        if not isinstance(payload, dict) or "data" not in payload:
            self._logger.warning("OpenSubtitles.com returned an unexpected response: %s", payload)
            return []

        results: List[SearchResult] = []
        seen_ids = set()
        for entry in payload.get("data") or []:
            result = self.__parse_result(request_internal_languages, self._build_search_term(request), entry)
            if result is None or result.id in seen_ids:
                continue
            seen_ids.add(result.id)
            results.append(result)
            if request.max_results and len(results) >= request.max_results:
                break
        return results

    def _get(self, request: GetRequest) -> List[GetResult]:
        if not self.__login():
            return []
        file_id, _, file_name = request.search_result_id.partition("|")
        http_request = HttpRequest(API_URL + "/download", "POST")
        http_request.headers = self.__build_headers(authenticated=True)
        http_request.set_json_data({"file_id": int(file_id)})
        try:
            http_response = self._http_client.exchange(http_request)
        except urllib_error.HTTPError as error:
            # The API explains what it disliked in the body; losing it turns a fixable problem into
            # "HTTP Error 400" in the logs.
            body = error.read().decode("utf-8", "replace")
            raise RuntimeError(
                "OpenSubtitles.com rejected the download of file_id %s (%s): %s" % (
                    file_id, error.code, body[:400])) from None
        payload = http_response.get_data_as_json()
        link = payload.get("link") if isinstance(payload, dict) else None
        if not link:
            self._logger.warning("OpenSubtitles.com did not return a download link: %s", payload)
            return []
        download_request = HttpRequest(link)
        download_request.headers = {"User-Agent": USER_AGENT}
        http_response = self._http_client.exchange(download_request)
        download_file_name = payload.get("file_name") or file_name \
            or urlparse(link).path.rsplit("/", 1)[-1] or "subtitle.zip"
        return self._process_get_subtitles_data(download_file_name, http_response.data)
