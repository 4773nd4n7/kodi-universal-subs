# -*- coding: utf-8 -*-

"""Fixtures shared by the provider test cases.

The media title and the subtitle bodies are reused by several modules (``Local``, ``FileSystem``
and the ``Subscene`` parser test), so they live here instead of in whichever test happened to need
them first.
"""

from pathlib import Path

from resources.lib.providers.searchresult import SearchResult

MOVIE_TITLE = "The Matrix"
MOVIE_YEAR = 1999

ENGLISH_SUBTITLE_TEXT = """1
00:00:01,000 --> 00:00:03,000
Wake up, Neo.

2
00:00:03,500 --> 00:00:06,000
The Matrix has you.
"""

SPANISH_SUBTITLE_TEXT = """1
00:00:01,000 --> 00:00:03,000
Despierta, Neo.

2
00:00:03,500 --> 00:00:06,000
Matrix te tiene.
"""


def write_text_file(file_path: Path, text: str) -> Path:
    # Written as bytes so the fixture content is not affected by platform newline translation.
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(text.encode("utf-8"))
    return file_path


def find_result_by_id(search_results, expected_id: str) -> SearchResult:
    return next((result for result in search_results if result.id == expected_id), None)
