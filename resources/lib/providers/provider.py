# -*- coding: utf-8 -*-

import logging
from abc import abstractmethod
from typing import List

from resources.lib.providers.get_request import GetRequest
from resources.lib.providers.get_result import GetResult
from resources.lib.providers.search_request import SearchRequest
from resources.lib.providers.search_result import SearchResult


class Provider:

    def __init__(self):
        self._logger: logging.Logger = logging.getLogger(self.id)

    @property
    def id(self) -> str:
        return 'UniversalSubs.Provider.' + self.name

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def short_name(self) -> str:
        return self.name

    def missing_credentials(self) -> str:
        """The credentials this provider still needs, empty when it has everything.

        A provider that returns an empty list because it is not configured looks like "no subtitles
        found", so the add-on asks this to tell the user *why* instead.
        """
        return ""

    @abstractmethod
    def search(self, request: SearchRequest) -> List[SearchResult]:
        pass

    @abstractmethod
    def get(self, request: GetRequest) -> List[GetResult]:
        pass
