# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path
from typing import List, Set

from resources.lib.language import Language
from resources.lib.providers.getrequest import GetRequest
from resources.lib.providers.getresult import GetResult
from resources.lib.providers.searchrequest import SearchRequest
from resources.lib.providers.searchresult import SearchResult
from resources.lib.providers.sourceprovider import (SourceProvider,
                                                    normalize_text)
from resources.lib.settings import Settings


class FileSystemSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.root_path = settings.file_system_provider_path

    @property
    def name(self) -> str:
        return "FileSystem"

    @property
    def short_name(self) -> str:
        return "FS"

    @property
    def supported_languages(self) -> Set[Language]:
        return None

    def _fetch_search_results(self, request: SearchRequest, supported_request_languages: List[Language]) -> List[SearchResult]:
        results: List[SearchResult] = []
        normalized_search_term = normalize_text(self._build_search_term(request), True)
        if not normalized_search_term:
            return results
        for root_name, _, file_names in os.walk(self.root_path):
            root_path = Path(root_name)
            normalized_root_name = normalize_text(root_name, True)
            for file_name in file_names:
                if not (self._is_subtitle_file_name(file_name) or self._is_compressed_file_name(file_name)):
                    continue
                if not (normalized_search_term in normalize_text(file_name, True) or normalized_search_term in normalized_root_name):
                    continue
                result = SearchResult()
                result.id = str(root_path.joinpath(file_name).resolve())
                result.title = file_name
                result.release_info = result.id
                result.language = Language.unknown
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
            results = self._process_subtitles_data(file_path.name, file_content)
        return results
