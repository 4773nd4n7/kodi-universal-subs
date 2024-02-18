# -*- coding: utf-8 -*-

import re
from html import unescape

from unidecode import unidecode


def unescape_html(text: str, simplify_spaces=True) -> str:
    clean_text = unescape(text)
    if simplify_spaces:
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return clean_text


# def find_text_between(text: str, start_marker: str, end_marker: str, strip_markers: bool = False) -> str:
#     start_marker_index = text.find(start_marker)
#     if start_marker_index < 0:
#         return None
#     end_marker_index = text.find(end_marker, start_marker_index)
#     if end_marker_index < 0:
#         return None
#     if strip_markers:
#         result = text[start_marker_index + len(start_marker):end_marker_index]
#     else:
#         result = text[start_marker_index:end_marker_index + len(end_marker)]
#     return result


def normalize_text(text: str, lower: bool = True) -> str:
    normalized_text = re.sub(r"[^A-z0-9]+", " ", unidecode(text)).strip()
    return normalized_text.lower() if lower else normalized_text


def normalize_white_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_text_from(what: str, where: str, beginning_only=False) -> str:
    what = re.compile((r"^[\s\.]*" if beginning_only else r"[\s\.]*") + r"[\s\.]+".join([re.escape(s)
                      for s in re.split(r"[\s\.]+", what.strip())]) + r"[\s\.]*", re.IGNORECASE)
    stripped = re.sub(what, " ", where).strip()
    return stripped
