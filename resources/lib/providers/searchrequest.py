# -*- coding: utf-8 -*-

import os
from pathlib import Path
from re import IGNORECASE, UNICODE, compile
from typing import List
from urllib.parse import ParseResult, unquote, urlparse
from urllib.request import url2pathname

from resources.lib.common.language import Language

URL_REGEX = compile(r'[A-z]+://.*', IGNORECASE | UNICODE)


def is_file_path(file_path_or_url: str) -> bool:
    return not URL_REGEX.search(file_path_or_url)


class SearchRequest:

    year: int = None
    show_season_number: int = None
    show_episode_number: int = None
    show_title: str = None
    title: str = None
    languages: List[Language] = []
    manual_search_text: str = None
    file_url: str
    file_languages: List[Language] = []
    max_results: int = 50

    @property
    def is_show_search(self) -> bool:
        return True if self.show_title else False

    @property
    def is_manual_search(self) -> bool:
        return self.manual_search_text

    @property
    def is_file(self) -> bool:
        return self.file_url.startswith("file://")

    @property
    def file_parsed_url(self) -> ParseResult:
        return urlparse(self.file_url) if self.file_url else None

    @property
    def file_path(self) -> Path:
        if not self.is_file:
            return None
        file_parsed_url = self.file_parsed_url
        host = "{0}{0}{mnt}{0}".format(os.path.sep, mnt=file_parsed_url.netloc)
        return Path(os.path.normpath(os.path.join(host, url2pathname(unquote(file_parsed_url.path)))))

    def get_file_name(self, include_extension: bool = True) -> str:
        (file_directory, file_name) = os.path.split(unquote(self.file_parsed_url.path))
        if include_extension:
            return file_name
        (file_base_name, file_ext) = os.path.splitext(file_name)
        return file_base_name

    def set_file_url_or_path(self, file_path_or_url: str) -> None:
        url = Path(file_path_or_url).as_uri() if is_file_path(file_path_or_url) else file_path_or_url
        self.file_url = url
