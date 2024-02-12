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

from ..compression import Compression
from ..language import Language
from ..logging import init_logging
from ..providers.addic7edsourceprovider import Addic7edSourceProvider
from ..providers.filesystemsourceprovider import FileSystemSourceProvider
from ..providers.getrequest import GetRequest
from ..providers.opensubtitlessourceprovider import OpenSubtitlesSourceProvider
from ..providers.podnapisisourceprovider import PodnapisiSourceProvider
from ..providers.providersregistry import ProvidersRegistry
from ..providers.searchrequest import SearchRequest
from ..providers.subdivxsourceprovider import SubDivXSourceProvider
from ..providers.translationsdecoratorprovider import \
    TranslationsDecoratorProvider
from ..settings import Settings
from ..yaml import to_yaml

Compression.seven_zip_exec_path = Path("C:/Program Files/7-Zip/7z.exe")


settings: Settings = Settings()
settings.addon_id = "service.subtitles.universalsubs"
settings.addon_version = "0.0.1"
settings.addon_path = Path(os.environ["UNIVERSAL_SUBS_PATH"]).resolve()
settings.addon_user_path = Path(os.environ["UNIVERSAL_SUBS_USER_PATH"]).resolve()
settings.include_author_on_results = False
settings.providers = ["FileSystem", "OpenSubtitles", "PodnapisiNET", "SubDivX", "Addic7ed"]
settings.providers = ["OpenSubtitles"]
settings.file_system_provider_path = Path("G:\\Subtitulos")
settings.search_cache_ttl = timedelta(days=7)
settings.translation_cache_ttl = timedelta(days=30)
settings.translators = ["Google", "Libre", "Bing"]
settings.translators = ["Google"]
# settings.translators = []
settings.cache_whole_requests = True


init_logging(settings.addon_path.joinpath('logging_config_test.jsonc'))
logger = logging.getLogger('UniversalSubs')
logger.info("Settings: %s", to_yaml(settings))


# provider = FileSystemSourceProvider(settings)
# provider = PodnapisiSourceProvider(settings)
# provider = Addic7edSourceProvider(settings)
# provider = SubDivXSourceProvider(settings)
provider = OpenSubtitlesSourceProvider(settings)
# provider = ProvidersRegistry.build_from_settings(settings)

search_request = SearchRequest()
search_request.max_results = 100
search_request.languages = [
    Language.english,
    Language.spanish,
]
# search_request.manual_search_text = "Aquaman"
# search_request.title = "Weathering with You"
# search_request.year = 2019
# search_request.show_title = "Breaking Bad"
# search_request.show_season_number = 1
# search_request.show_episode_number = 2
# search_request.year = 2008
search_request.show_title = "Pluto"
search_request.show_season_number = 1
search_request.show_episode_number = 3
search_request.year = 2023
search_request.set_file_url_or_path("C:/Example/TestFile.mkv")
search_request.file_languages = [Language.unknown]
search_results = provider.search(search_request)


if len(search_results) > 0:  # and not settings.translators:
    get_request = GetRequest()
    get_request.search_result_id = search_results[len(search_results) - 1].id
    get_request.file_url = search_request.file_url
    get_results = provider.get(get_request)
    for get_result in get_results:
        get_result.write_into(settings.addon_user_path)
