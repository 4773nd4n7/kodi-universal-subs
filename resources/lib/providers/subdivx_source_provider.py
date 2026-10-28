# -*- coding: utf-8 -*-

import base64
import json
import re
from typing import Any, Dict, List

from resources.lib.common.language import Language
from resources.lib.common.mapped_languages import MappedLanguages
from resources.lib.common.settings import Settings
from resources.lib.providers.get_request import GetRequest
from resources.lib.providers.get_result import GetResult
from resources.lib.providers.search_request import (SearchRequest,
                                                   SearchResultsCounter)
from resources.lib.providers.search_result import SearchResult
from resources.lib.providers.source_provider import SourceProvider
from resources.lib.utils.http_client import HttpRequest
from resources.lib.utils.text import unescape_html

STAR_HTML = '<i class="fa fa-star rating-color">'


def parse_browser_session(raw: str) -> Dict[str, str]:
    """Decode the blob that ``resources/subdivx-session.js`` copies to the clipboard.

    The blob is base64-encoded JSON with the browser's ``cookie`` header value and its ``ua``:
    Cloudflare binds ``cf_clearance`` to that user agent, so both have to travel together.
    Empty, truncated or unrecognised input yields an empty mapping, which keeps the anonymous
    request path.
    """
    value = (raw or "").strip()
    if not value:
        return {}
    try:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4)).decode("utf-8")
        data = json.loads(decoded)
    except (ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("cookie"), str) or not data["cookie"]:
        return {}
    session = {"cookie": data["cookie"]}
    if isinstance(data.get("ua"), str) and data["ua"]:
        session["ua"] = data["ua"]
    return session


RE_FORCED_SUBTITLE_FILE_NAME = re.compile(r"\b(forced|forzado)\b", re.IGNORECASE)


class SubDivXSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings, MappedLanguages([Language.spanish]))
        self._http_client.base_url = "https://www.subdivx.com/"
        self._http_client.default_headers["Referer"] = "https://www.subdivx.com/index.php"
        browser_session = parse_browser_session(settings.subdivx_session)
        if browser_session:
            self._http_client.default_headers["Cookie"] = browser_session["cookie"]
            if browser_session.get("ua"):
                # cf_clearance is bound to the user agent that obtained it.
                self._http_client.default_headers["User-Agent"] = browser_session["ua"]

    @property
    def name(self) -> str:
        return "SubDivX"

    @property
    def short_name(self) -> str:
        return "SDX"

    @property
    def _overrides_ratings_from_downloads(self) -> bool:
        return True

    def _fetch_search_results(self, request: SearchRequest, request_internal_languages: List[Language]) -> List[SearchResult]:
        http_request = HttpRequest("/inc/ajax.php", "POST")
        http_request.set_urlencoded_form_data(
            {"tabla": "resultados", "buscar": self._build_search_term(request)})
        http_response = self._http_client.exchange(http_request)
        results_data: Dict[str, Any] = http_response.get_data_as_json()
        results: List[SearchResult] = []
        results_counter: SearchResultsCounter = request.build_counter()
        for result_data in results_data["aaData"]:
            if self._settings.exclude_splitted_subtitles and result_data.get("cds", 1) > 1:
                continue
            result = SearchResult()
            result.id = result_data["id"]
            result.title = unescape_html(result_data["titulo"])
            result.release_info = unescape_html(re.sub(r"</?[^>]+>", "", result_data["descripcion"]))
            result.author = re.sub(r".*/>\s*([^<]+)\s*</a>\s*</div>.*", r"\1", result_data.get("nick", ""))
            result.downloads = result_data["descargas"]
            result.rating = float(str(result_data.get("calificacion", "")).count(STAR_HTML))  # count number of stars
            result.language = Language.spanish
            results.append(result)
            results_counter.try_accept_result(result)
            if results_counter.reached_max_results:
                return results
        return results

    def _is_forced_subtitle_file_name(self, file_name: str) -> bool:
        return bool(RE_FORCED_SUBTITLE_FILE_NAME.search(file_name))

    def _get(self, request: GetRequest) -> List[GetResult]:
        http_request = HttpRequest("/descargar.php")
        http_request.add_url_query_params({"id": request.search_result_id})
        http_response = self._http_client.exchange(http_request)
        results = self._process_get_subtitles_data(http_response.file_name, http_response.data)
        return results
