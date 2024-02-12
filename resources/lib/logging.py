# -*- coding: utf-8 -*-

import logging
import logging.config
from pathlib import Path

from resources.lib.json import from_json


def init_logging(config_path: Path) -> None:
    with open(config_path, 'rt') as config_file:
        config = from_json(config_file.read())
        logging.config.dictConfig(config)


try:
    import xbmc
    from xbmc import LOGDEBUG, LOGERROR, LOGFATAL, LOGINFO, LOGNONE, LOGWARNING

    class KodiLogHandler(logging.Handler):

        def __init__(self) -> None:
            logging.Handler.__init__(self=self)

        def ___logging_level_to_kodi_level(self, levelno: int) -> int:
            if levelno == logging.DEBUG:
                # return LOGDEBUG
                return LOGINFO
            if levelno == logging.INFO:
                return LOGINFO
            if levelno == logging.WARNING:
                return LOGWARNING
            if levelno == logging.ERROR:
                return LOGERROR
            if levelno == logging.FATAL:
                return LOGFATAL
            return LOGFATAL

        def emit(self, record: logging.LogRecord) -> None:
            xbmc.log(self.formatter.format(record), self.___logging_level_to_kodi_level(record.levelno))

except ImportError:
    pass
