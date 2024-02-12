# -*- coding: utf-8 -*-

import re
from typing import Any, Dict, List, Set

from resources.lib.httpclient import HttpRequest
from resources.lib.language import Language
from resources.lib.providers.getrequest import GetRequest
from resources.lib.providers.getresult import GetResult
from resources.lib.providers.searchrequest import SearchRequest
from resources.lib.providers.searchresult import SearchResult
from resources.lib.providers.sourceprovider import (SourceProvider,
                                                    unescape_html)
from resources.lib.settings import Settings

START_HTML = '<i class="fa fa-star rating-color">'

RE_FORCED_SUBTITLE_FILE_NAME = re.compile(r"\b(forced|forzado)\b", re.IGNORECASE)


class SubDivXSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._supported_languages = set([Language.spanish])
        self._http_client.base_url = "https://www.subdivx.com/"

    @property
    def name(self) -> str:
        return "SubDivX"

    @property
    def short_name(self) -> str:
        return "SDX"

    @property
    def supported_languages(self) -> Set[Language]:
        return self._supported_languages

    @property
    def overrides_ratings_from_downloads(self) -> bool:
        return True

    def _fetch_search_results(self, request: SearchRequest, supported_request_languages: List[Language]) -> List[SearchResult]:
        http_request = HttpRequest("/inc/ajax.php", "POST")
        http_request.set_urlencoded_form_data(
            {"tabla": "resultados", "buscar": self._build_search_term(request)})
        http_response = self._http_client.exchange(http_request)
        results_data: Dict[str, Any] = http_response.get_data_as_json()
        results: List[SearchResult] = []
        for result_data in results_data["aaData"]:
            if self._settings.exclude_splitted_subtitles and result_data.get("cds", 1) > 1:
                continue
            result = SearchResult()
            result.id = result_data["id"]
            result.title = unescape_html(result_data["titulo"])
            result.release_info = unescape_html(re.sub(r"</?[^>]+>", "", result_data["descripcion"]))
            result.author = re.sub(r".*/>\s*([^<]+)\s*</a>\s*</div>.*", r"\1", result_data.get("nick", ""))
            result.downloads = result_data["descargas"]
            result.rating = float(str(result_data.get("calificacion", "")).count(START_HTML))
            result.language = Language.spanish
            results.append(result)
            if request.max_results and len(results) >= request.max_results:
                return results
        return results

    def _is_forced_subtitle_file_name(self, file_name: str) -> bool:
        return bool(RE_FORCED_SUBTITLE_FILE_NAME.search(file_name))

    def _get(self, request: GetRequest) -> List[GetResult]:
        http_request = HttpRequest("/descargar.php")
        http_request.add_url_query_params({"id": request.search_result_id})
        http_response = self._http_client.exchange(http_request)
        results = self._process_subtitles_data(http_response.file_name, http_response.data)
        return results
