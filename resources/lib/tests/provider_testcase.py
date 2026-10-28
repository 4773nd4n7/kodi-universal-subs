# -*- coding: utf-8 -*-

"""Shared helpers for the source provider test cases.

The test cases rebuild what the addon does at runtime: create a ``Settings`` object, build a
``ProvidersRegistry`` from it and then exercise the two operations every provider exposes
(``search`` and ``get``).  One module per provider builds on top of this one:

* ``test_provider_opensubtitles.py``, ``test_provider_subscene.py``, ``test_provider_subdivx.py``
  and ``test_provider_addic7ed.py`` - live searches against the real provider sites, gated behind
  the ``UNIVERSAL_SUBS_NETWORK_TESTS`` environment variable. They share the assertions of
  ``OnlineSourceProviderTestCase`` and only supply the titles and languages of their provider.
* ``test_provider_local.py`` and ``test_provider_filesystem.py`` - offline tests for the providers
  that read from the local file system.
* ``test_provider_registry.py`` - the contract every provider satisfies, and provider composition.
* ``test_httpclient.py`` - the HTTP response helpers, notably case-insensitive header lookups.

Every test module lives in this package and is run through it with ``-m`` from the repository
root, without installing the addon into Kodi: ``-m`` supplies both the import path and the
package context the modules need, so none of them has to touch ``sys.path``.

Dependencies of this test suite (the addon expects Kodi to provide them at runtime)::

    uv run --no-project --python 3.11 --with chardet --with unidecode --with beautifulsoup4 \
        --with html5lib --with cachetools --with pyyaml python -m resources.lib.tests.test_provider_local

The live provider tests run by default. They reach the real sites, so set
``UNIVERSAL_SUBS_NETWORK_TESTS=0`` to skip them::

    UNIVERSAL_SUBS_NETWORK_TESTS=0 uv run --no-project --python 3.11 \
        --with chardet --with unidecode --with beautifulsoup4 --with html5lib \
        --with cachetools --with pyyaml python -m resources.lib.tests.test_provider_opensubtitles -v

RAR/7Z downloads need 7-Zip; set ``SEVEN_ZIP_PATH`` when it is not installed in a well known
location (ZIP downloads are unpacked with the standard library and always work).
"""

import os
import shutil
import socket
import tempfile
import unittest
import urllib.error
from datetime import timedelta
from pathlib import Path
from typing import Callable, List, Optional, Sequence, TypeVar

from resources.lib.common.language import Language
from resources.lib.common.settings import Settings
from resources.lib.providers.get_request import GetRequest
from resources.lib.providers.get_result import GetResult
from resources.lib.providers.providers_registry import ProvidersRegistry
from resources.lib.providers.search_request import SearchRequest
from resources.lib.providers.search_result import SearchResult
from resources.lib.utils.compression import Compression
from resources.lib.utils.text import bytes_to_string, normalize_text

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

#: File extensions the addon accepts as subtitle files (``vvt`` is the typo used by
#: ``SourceProvider.RE_SUBTITLE_FILE_NAME``; ``vtt`` is accepted here for tolerance).
SUBTITLE_FILE_EXTENSIONS = {".ass", ".srt", ".ssa", ".sub", ".vtt", ".vvt"}

#: Markers that identify the downloaded payload as subtitle data rather than an HTML page.
SUBTITLE_CONTENT_MARKERS = ("-->", "[Script Info]", "Dialogue:", "WEBVTT", "00:00:")

NETWORK_TESTS_ENVIRONMENT_VARIABLE = "UNIVERSAL_SUBS_NETWORK_TESTS"

#: ``urllib`` has no timeout of its own; without this a dead provider site would hang the run.
NETWORK_TIMEOUT_SECONDS = 30

SEVEN_ZIP_ENVIRONMENT_VARIABLE = "SEVEN_ZIP_PATH"

T = TypeVar("T")


def network_tests_enabled() -> bool:
    """Whether the live provider tests should run.

    They run by default. Only an explicit false value (``0``, ``false``, ``no`` or ``off``) keeps
    a run offline, so a machine that reaches the sites tests them without any setup.
    """
    configured = os.environ.get(NETWORK_TESTS_ENVIRONMENT_VARIABLE)
    if configured is None:
        return True
    return configured.strip().lower() not in ("0", "false", "no", "off")


requires_network = unittest.skipUnless(
    network_tests_enabled(),
    "Live provider tests are disabled by %s=0; unset it to run them against the real provider "
    "sites." % NETWORK_TESTS_ENVIRONMENT_VARIABLE)


def find_seven_zip_executable() -> Optional[Path]:
    """Locate 7-Zip, which is required to unpack RAR and 7Z subtitle downloads."""
    candidates: List[Path] = []
    configured_path = os.environ.get(SEVEN_ZIP_ENVIRONMENT_VARIABLE)
    if configured_path:
        candidates.append(Path(configured_path))
    which_path = shutil.which("7z")
    if which_path:
        candidates.append(Path(which_path))
    if os.name == "nt":
        candidates.append(Path("C:/Program Files/7-Zip/7z.exe"))
        candidates.append(Path("C:/Program Files (x86)/7-Zip/7z.exe"))
    else:
        candidates.append(Path("/usr/bin/7z"))
        candidates.append(Path("/usr/local/bin/7z"))
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def configure_compression() -> Optional[Path]:
    """Point the addon at the local 7-Zip executable, when there is one."""
    seven_zip_executable_path = find_seven_zip_executable()
    if seven_zip_executable_path:
        Compression.seven_zip_exec_path = seven_zip_executable_path
    return seven_zip_executable_path


def build_settings(work_directory: Path) -> Settings:
    """Build the ``Settings`` object the providers expect, isolated inside a temporary directory."""
    work_directory.mkdir(parents=True, exist_ok=True)
    file_system_provider_path = work_directory.joinpath("file-system-provider")
    file_system_provider_path.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    settings.addon_id = "service.subtitles.universalsubs"
    settings.addon_path = REPOSITORY_ROOT
    settings.addon_user_path = work_directory
    settings.file_system_provider_path = file_system_provider_path
    settings.providers = []
    settings.translators = []
    settings.include_author_on_results = True
    settings.include_downloads_on_results = True
    settings.exclude_splitted_subtitles = True
    settings.cache_whole_requests = False
    # A zero TTL disables the persistent caches, so every run reaches the provider and results
    # from a previous run can never make a test pass.
    settings.search_cache_ttl = timedelta()
    settings.translation_cache_ttl = timedelta()
    settings.clean_up_subtitles = False
    settings.clean_up_ads = False
    settings.clean_up_hi_markers = False
    return settings


class ProviderTestCase(unittest.TestCase):
    """Base class with the plumbing needed to drive one provider end to end."""

    #: Name under which the provider is registered in ``ProvidersRegistry``.
    provider_name: str = None

    #: Maximum number of results the tests ask for; keeps the amount of provider traffic small.
    max_results: int = 10

    work_directory: Path = None
    settings: Settings = None
    registry: ProvidersRegistry = None
    _search_cache: dict = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        configure_compression()
        cls.work_directory = Path(tempfile.mkdtemp(prefix="universal-subs-tests-"))
        cls.settings = build_settings(cls.work_directory)
        cls.configure_settings(cls.settings)
        cls._search_cache = {}
        cls.registry = ProvidersRegistry(cls.settings)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work_directory, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def configure_settings(cls, settings: Settings) -> None:
        """Hook for test cases that need extra settings before the registry is built."""
        pass

    @classmethod
    def provider(cls):
        """The provider under test, built the same way the addon builds it."""
        if not cls.provider_name:
            raise unittest.SkipTest("No provider configured for this test case")
        provider = cls.registry.get_provider(cls.provider_name)
        if provider is None:
            raise AssertionError("Provider '%s' is not registered any more" % cls.provider_name)
        return provider

    # ------------------------------------------------------------------ requests

    @classmethod
    def create_media_file_url(cls, file_name: str = "The Matrix (1999).mkv") -> str:
        """A file URL for the media the caller would be watching.

        Remote providers only use the file name (to compute the ``is_sync`` flag), but the search
        request requires a file URL, so a path inside the temporary directory is used.
        """
        return cls.work_directory.joinpath(file_name).as_uri()

    @classmethod
    def build_movie_search_request(cls,
                                   title: str,
                                   year: int = None,
                                   languages: Sequence[Language] = (Language.english,),
                                   max_results: int = None) -> SearchRequest:
        request = SearchRequest()
        request.title = title
        request.year = year
        request.languages = list(languages)
        request.max_results = cls.max_results if max_results is None else max_results
        file_name = "%s (%s).mkv" % (title, year) if year else "%s.mkv" % title
        request.set_file_url_or_path(str(cls.work_directory.joinpath(file_name)))
        return request

    @classmethod
    def build_show_search_request(cls,
                                  show_title: str,
                                  season_number: int,
                                  episode_number: int,
                                  languages: Sequence[Language] = (Language.english,),
                                  max_results: int = None) -> SearchRequest:
        request = SearchRequest()
        request.show_title = show_title
        request.show_season_number = season_number
        request.show_episode_number = episode_number
        request.languages = list(languages)
        request.max_results = cls.max_results if max_results is None else max_results
        request.set_file_url_or_path(str(cls.work_directory.joinpath(
            "%s S%02dE%02d.mkv" % (show_title, season_number, episode_number))))
        return request

    # ------------------------------------------------------------------ operations

    @classmethod
    def search(cls, search_key: str, request: SearchRequest) -> List[SearchResult]:
        """Run ``Provider.search`` once per test case, so several tests share one network call."""
        if search_key not in cls._search_cache:
            try:
                cls._search_cache[search_key] = cls.provider().search(request)
            except BaseException as error:  # cached too: a dead provider should be reported once
                cls._search_cache[search_key] = error
        cached_value = cls._search_cache[search_key]
        if isinstance(cached_value, BaseException):
            raise cached_value
        return cached_value

    @classmethod
    def download(cls, search_result: SearchResult) -> List[GetResult]:
        """Run ``Provider.get`` for one search result, the way the addon downloads a subtitle."""
        request = GetRequest()
        request.language = search_result.language
        request.search_result_id = search_result.id
        request.file_url = cls.create_media_file_url()
        return cls.provider().get(request)

    # ------------------------------------------------------------------ assertions

    def assert_reasonable_search_results(self,
                                         search_results: List[SearchResult],
                                         expected_language: Language,
                                         title_keywords: Sequence[str],
                                         minimum_results: int = 1,
                                         maximum_results: int = None) -> None:
        """Check that a search produced results that look usable to a user."""
        maximum_results = self.max_results if maximum_results is None else maximum_results
        self.assertIsInstance(search_results, list, "search() must return a list of results")
        self.assertGreaterEqual(
            len(search_results), minimum_results,
            "Expected at least %s search result(s) for a title every provider should know, got %s"
            % (minimum_results, len(search_results)))
        self.assertLessEqual(
            len(search_results), maximum_results,
            "Search returned %s results but only %s were requested" % (len(search_results), maximum_results))

        found_languages: List[Language] = []
        found_identifiers: List[str] = []
        for index, search_result in enumerate(search_results):
            with self.subTest(search_result=index):
                self.assertIsInstance(search_result, SearchResult)
                self.assertIsInstance(search_result.id, str, "Search results must carry an id")
                self.assertTrue(search_result.id and search_result.id.strip(), "Search result id is empty")
                self.assertTrue(search_result.title and search_result.title.strip(),
                                "Search result %s has no title" % search_result.id)
                self.assertIsInstance(search_result.language, Language,
                                      "Search result %s has no language" % search_result.id)
                self.assertEqual(self.provider_name, search_result.provider_name,
                                 "Search result %s is not attributed to its provider" % search_result.id)
                self.assertGreaterEqual(search_result.downloads, -1,
                                        "Search result %s has an invalid downloads count" % search_result.id)
                self.assertGreaterEqual(search_result.rating, 0.0,
                                        "Search result %s has a negative rating" % search_result.id)
                self.assertLessEqual(search_result.rating, 5.0,
                                     "SearchResult.rating must be a value from 0.0 to 5.0, got %s for %s"
                                     % (search_result.rating, search_result.id))
                found_identifiers.append(search_result.id)
                found_languages.append(search_result.language)

        self.assertEqual(len(found_identifiers), len(set(found_identifiers)),
                         "Search returned duplicated ids: %s" % ", ".join(found_identifiers))
        self.assertIn(expected_language, found_languages,
                      "Expected at least one %s result, found: %s"
                      % (expected_language, ", ".join(sorted({str(language) for language in found_languages}))))

        normalized_keywords = [normalize_text(keyword) for keyword in title_keywords if keyword and keyword.strip()]
        matching_titles = [result.title for result in search_results
                           if any(keyword in normalize_text(result.title) for keyword in normalized_keywords)]
        self.assertTrue(
            matching_titles,
            "None of the results seems to be about '%s'; titles were: %s"
            % (" / ".join(title_keywords), "; ".join(result.title for result in search_results[:10])))

    def assert_valid_subtitle_results(self, get_results: List[GetResult], minimum_results: int = 1) -> None:
        """Check that a download produced subtitle files a user could actually use."""
        self.assertIsInstance(get_results, list, "get() must return a list of results")
        self.assertGreaterEqual(
            len(get_results), minimum_results,
            "The download produced no subtitle. Common causes: the provider now requires a login, "
            "served a bot challenge page instead of the file, or the archive was RAR/7Z and no "
            "7-Zip executable is available (%s)." % (Compression.seven_zip_exec_path,))
        for index, get_result in enumerate(get_results):
            with self.subTest(get_result=index):
                self.assertIsInstance(get_result, GetResult)
                self.assertIsInstance(get_result.file_name, str, "Downloaded subtitle has no file name")
                file_extension = Path(get_result.file_name).suffix.lower()
                self.assertIn(file_extension, SUBTITLE_FILE_EXTENSIONS,
                              "Downloaded file '%s' is not a subtitle file" % get_result.file_name)
                self.assertIsInstance(get_result.content, bytes, "Downloaded subtitle has no content")
                self.assertGreater(len(get_result.content), 0, "Downloaded subtitle is empty")
                self.assertEqual(self.provider_name, get_result.provider_name,
                                 "Downloaded subtitle is not attributed to its provider")
                subtitle_text = bytes_to_string(get_result.content)
                self.assertTrue(subtitle_text.strip(), "Downloaded subtitle content is empty")
                lowered_text = subtitle_text.lstrip().lower()
                self.assertFalse(
                    lowered_text.startswith("<!doctype") or lowered_text.startswith("<html"),
                    "The provider returned an HTML page (login form or bot challenge) instead of a subtitle")
                self.assertTrue(
                    any(marker.lower() in lowered_text for marker in SUBTITLE_CONTENT_MARKERS),
                    "Downloaded file '%s' does not look like a subtitle file; first characters: %r"
                    % (get_result.file_name, subtitle_text[:120]))

    def assert_result_can_be_saved(self, get_result: GetResult) -> Path:
        """Check the last step of a download: writing the subtitle next to the media file."""
        written_file_path = get_result.write_into(self.work_directory)
        self.assertTrue(written_file_path.exists(), "The subtitle was not written to '%s'" % written_file_path)
        self.assertGreater(written_file_path.stat().st_size, 0, "The written subtitle is empty")
        self.assertEqual(get_result.file_name, written_file_path.name)
        return written_file_path


class OnlineSourceProviderTestCase(ProviderTestCase):
    """Test cases shared by every provider that queries a remote site.

    Subclasses only configure the titles they are known to index; the assertions live here so a
    new provider gets the same coverage by declaring its test data.
    """

    #: Movie every provider under test is expected to know, and the language to search it in.
    movie_title: str = None
    movie_year: int = None
    movie_languages: Sequence[Language] = (Language.english,)

    #: TV show used to cover episode searches (providers that index episodes).
    show_title: str = None
    show_season_number: int = 1
    show_episode_number: int = 1
    show_languages: Sequence[Language] = (Language.english,)

    #: Providers that only index one kind of content set the matching flag to ``False``.
    supports_movies: bool = True
    supports_tv_shows: bool = True

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # urllib has no timeout of its own; without this a site that accepts the connection and then
        # stalls would hang the whole run instead of failing the test.
        socket.setdefaulttimeout(NETWORK_TIMEOUT_SECONDS)

    def perform_provider_operation(self, description: str, operation: Callable[[], T]) -> T:
        """Run one provider operation and turn a site outage into a readable failure."""
        try:
            return operation()
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, TimeoutError,
                ConnectionError) as error:
            raise AssertionError(
                "%s failed: %s\n"
                "The provider site could not serve this request: it may be offline, blocking automated "
                "clients, or asking for authentication. Check the site in a browser before treating this "
                "as a regression in the addon." % (description, error)) from None

    @staticmethod
    def title_keywords(title: str) -> List[str]:
        """The words a result title must mention for the result to be about the searched title."""
        normalized_words = [word for word in normalize_text(title or "").split() if len(word) > 3]
        if not normalized_words:
            return [normalize_text(title or "")]
        return normalized_words[-2:]

    @classmethod
    def movie_search_results(cls) -> List[SearchResult]:
        return cls.search("movie", cls.build_movie_search_request(
            cls.movie_title, cls.movie_year, cls.movie_languages))

    @classmethod
    def tv_show_search_results(cls) -> List[SearchResult]:
        return cls.search("tv-show", cls.build_show_search_request(
            cls.show_title, cls.show_season_number, cls.show_episode_number, cls.show_languages))

    # ------------------------------------------------------------------ tests

    def test_search_movie_returns_reasonable_results(self) -> None:
        if not self.supports_movies:
            self.skipTest("%s does not index movies" % self.provider_name)
        search_results = self.perform_provider_operation(
            "Searching '%s' in %s" % (self.movie_title, self.movie_languages[0]),
            self.movie_search_results)
        self.assert_reasonable_search_results(
            search_results,
            expected_language=self.movie_languages[0],
            title_keywords=self.title_keywords(self.movie_title))

    def test_search_tv_show_returns_reasonable_results(self) -> None:
        if not self.supports_tv_shows:
            self.skipTest("%s does not index TV show episodes" % self.provider_name)
        search_results = self.perform_provider_operation(
            "Searching '%s' S%02dE%02d in %s" % (self.show_title, self.show_season_number,
                                                 self.show_episode_number, self.show_languages[0]),
            self.tv_show_search_results)
        self.assert_reasonable_search_results(
            search_results,
            expected_language=self.show_languages[0],
            title_keywords=self.title_keywords(self.show_title))

    def test_get_first_search_result_downloads_a_subtitle(self) -> None:
        if self.supports_movies:
            search_results = self.perform_provider_operation(
                "Searching '%s' in %s" % (self.movie_title, self.movie_languages[0]),
                self.movie_search_results)
        elif self.supports_tv_shows:
            search_results = self.perform_provider_operation(
                "Searching '%s' S%02dE%02d in %s" % (self.show_title, self.show_season_number,
                                                     self.show_episode_number, self.show_languages[0]),
                self.tv_show_search_results)
        else:
            self.skipTest("%s has no content type configured" % self.provider_name)
        self.assertGreaterEqual(len(search_results), 1,
                                "Cannot download the first result because the search returned nothing")
        get_results = self.perform_provider_operation(
            "Downloading the first search result", lambda: self.download(search_results[0]))
        self.assert_valid_subtitle_results(get_results)
        self.assert_result_can_be_saved(get_results[0])
