#!/usr/bin/python

import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

if __name__ == '__main__' and not __package__:
    __package__ = 'resources.lib.tests'
    sys.path.append(str(Path(__file__).resolve().parents[len(__package__.split("."))]))
    try:
        sys.path.remove(str(Path(__file__).resolve().parent))
    except ValueError:
        pass

from ..common.language import Language
from ..common.settings import Settings
from ..providers.addic7edsourceprovider import Addic7edSourceProvider
from ..providers.filesystemsourceprovider import FileSystemSourceProvider
from ..providers.getrequest import GetRequest
from ..providers.opensubtitlessourceprovider import OpenSubtitlesSourceProvider
from ..providers.podnapisisourceprovider import PodnapisiSourceProvider
from ..providers.providersregistry import ProvidersRegistry
from ..providers.searchrequest import SearchRequest
from ..providers.subdivxsourceprovider import SubDivXSourceProvider
from ..providers.subscenesourceprovider import SubsceneSourceProvider
from ..utils.compression import Compression
from ..utils.logging import init_logging_from_yaml
from ..utils.yaml import to_yaml

Compression.seven_zip_exec_path = Path("C:/Program Files/7-Zip/7z.exe")

settings = Settings()
settings.addon_id = "service.subtitles.universalsubs"
settings.addon_path = Path(__file__).joinpath("..", "..", "..", "..").resolve()
settings.addon_user_path = Path(os.environ["UNIVERSAL_SUBS_USER_PATH"]).resolve()
settings.include_author_on_results = False
settings.providers = ["OpenSubtitles", "Subscene", "PodnapisiNET", "SubDivX", "Addic7ed", "FileSystem"]
settings.providers = ["OpenSubtitles"]
settings.file_system_provider_path = Path("G:/Subtitulos")
settings.search_cache_ttl = timedelta(days=7)
settings.translation_cache_ttl = timedelta(days=30)
settings.translators = ["Google", "Libre", "Bing"]
# settings.translators = ["Google"]
settings.translators = []
settings.cache_whole_requests = True


init_logging_from_yaml(settings.addon_path.joinpath('logging.test.yaml'))
logger = logging.getLogger('UniversalSubs')
logger.info("Settings: %s", to_yaml(settings))


# provider = Addic7edSourceProvider(settings)
# provider = FileSystemSourceProvider(settings)
# provider = OpenSubtitlesSourceProvider(settings)
# provider = PodnapisiSourceProvider(settings)
# provider = SubDivXSourceProvider(settings)
# provider = SubsceneSourceProvider(settings)
provider = ProvidersRegistry.build_from_settings(settings)

search_request = SearchRequest()
search_request.max_results = 100
search_request.languages = [
    # Language.english,
    Language.spanish,
]
# search_request.manual_search_text = "Aquaman"
search_request.title = "My Sassy Girl"
search_request.year = 2001
# search_request.show_title = "Breaking Bad"
# search_request.show_season_number = 1
# search_request.show_episode_number = 2
# search_request.year = 2008
# search_request.show_title = "Pluto"
# search_request.show_season_number = 1
# search_request.show_episode_number = 3
# search_request.year = 2023
search_request.set_file_url_or_path("C:/Example/TestFile.mkv")
search_request.file_languages = [Language.unknown]
search_results = provider.search(search_request)


if len(search_results) > 0:  # and not settings.translators:
    search_result = search_results[len(search_results) - 1]
    get_request = GetRequest()
    get_request.language = search_result.language
    get_request.search_result_id = search_result.id
    get_request.file_url = search_request.file_url
    get_results = provider.get(get_request)
    for get_result in get_results:
        get_result.write_into(settings.addon_user_path)
