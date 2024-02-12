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
from ..json import to_json
from ..language import Language
from ..logging import init_logging
from ..providers.getresult import GetResult
from ..settings import Settings
from ..translation.bingtranslator import BingTranslator
from ..translation.googletranslator import GoogleTranslator
from ..translation.libretranslator import LibreTranslator
from ..translation.subtitletranslator import SubtitleTranslator

Compression.seven_zip_exec_path = Path("C:/Program Files/7-Zip/7z.exe")

settings: Settings = Settings()
settings.addon_id = "service.subtitles.universalsubs"
settings.addon_version = "0.0.1"
settings.addon_path = Path(".").absolute()
settings.addon_user_path = Path("../../userdata/addon_data/" + settings.addon_id).absolute()
settings.include_author_on_results = True
settings.include_downloads_on_results = True
settings.exclude_splitted_subtitles = True
settings.search_cache_ttl = timedelta(minutes=30)
settings.translation_cache_ttl = timedelta(days=30)

init_logging(settings.addon_path.joinpath('logging_config_test.jsonc'))
logger = logging.getLogger('UniversalSubs')
logger.info("Settings: %s", to_json(settings))

examples_path = settings.addon_path.joinpath("resources", "examples")

subtitle = GetResult()
for file_name in [
    "AdvancedSubStationAlpha.ass",
    "GooglePlay.json",
    "MicroDVD.sub",
    "MPlayer2.txt",
    "SubRip.srt",
    "SubStationAlpha.ssa",
    "WebVTT.vtt",
    "WebVTT2.vtt",
    "YouTubeSBV.sbv"
]:
    subtitle.file_name = file_name
    subtitle.content = None
    with open(examples_path.joinpath(subtitle.file_name).absolute(), 'rb') as file:
        subtitle.content = file.read()
    subtitle.is_forced = False
    subtitle.is_hearing_impaired = False
    translator = SubtitleTranslator(LibreTranslator(settings))
    translated_subtitle = translator.translate(subtitle, Language.english, Language.spanish)
    (file_name, file_ext) = os.path.splitext(file_name)
    translated_subtitle.file_name = file_name + "." + Language.spanish.two_letter_code + file_ext
    logger.info("%s\n%s" % (translated_subtitle.file_name, translated_subtitle.content.decode("utf-8")))
    translated_subtitle.write_into(examples_path)
