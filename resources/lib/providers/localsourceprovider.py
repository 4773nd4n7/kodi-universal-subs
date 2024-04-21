# -*- coding: utf-8 -*-

import os
from pathlib import Path
from typing import List

from resources.lib.common.language import Language
from resources.lib.common.mappedlanguages import MappedLanguages
from resources.lib.common.settings import Settings
from resources.lib.providers.getrequest import GetRequest
from resources.lib.providers.getresult import GetResult
from resources.lib.providers.searchrequest import SearchRequest
from resources.lib.providers.searchresult import SearchResult
from resources.lib.providers.sourceprovider import SourceProvider
from resources.lib.utils.text import normalize_text


class LocalSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings, MappedLanguages([]))

    @property
    def name(self) -> str:
        return "Local"

    @property
    def short_name(self) -> str:
        return "LO"

    def _fetch_search_results(self, request: SearchRequest, request_internal_languages: List[Language]) -> List[SearchResult]:
        results: List[SearchResult] = []
        if not request.is_file:
            return results
        request_base_file_path = os.path.splitext(str(request.file_path))[0]
        for root_name, _, file_names in os.walk(request.file_path.parent):
            root_path = Path(root_name)
            for file_name in file_names:
                if not (self._is_subtitle_file_name(file_name) or self._is_compressed_file_name(file_name)):
                    continue
                file_path = root_path.joinpath(file_name)
                if not str(file_path).startswith(request_base_file_path):
                    continue
                result = SearchResult()
                file_language_code = os.path.splitext(os.path.splitext(file_name)[0])[1][1:].split(" ")[0]
                result.language = Language.from_two_letter_code(file_language_code) \
                    if file_language_code \
                    else Language.unknown
                if result.language != Language.unknown and request.languages and not result.language in request.languages:
                    continue
                result.id = str(file_path)
                result.title = file_name
                result.release_info = result.id
                results.append(result)
                if request.max_results and len(results) >= request.max_results:
                    return results
        return results

    def _get(self, request: GetRequest) -> List[GetResult]:
        results: List[GetResult] = []
        file_path = Path(request.search_result_id)
        if not file_path.exists():
            self._logger.fatal("File not found: %s", file_path)
        else:
            with open(file_path, 'rb') as file:
                file_content: bytes = file.read()
            results = self._process_get_subtitles_data(file_path.name, file_content)
        return results
