# -*- coding: utf-8 -*-

import math
import re
from datetime import timedelta
from typing import List, Set, Tuple
from urllib.parse import quote

from bs4 import BeautifulSoup

from resources.lib.httpclient import HttpRequest
from resources.lib.language import Language
from resources.lib.providers.getrequest import GetRequest
from resources.lib.providers.getresult import GetResult
from resources.lib.providers.searchrequest import SearchRequest
from resources.lib.providers.searchresult import SearchResult
from resources.lib.providers.sourceprovider import (SourceProvider,
                                                    find_text_between,
                                                    normalize_white_space,
                                                    unescape_html)
from resources.lib.settings import Settings

MAX_TITLES_COUNT = 5


SUPPORTED_LANGUAGES = {
    "Abkhazian": "abk",
    "Afrikaans": "afr",
    "Albanian": "alb",
    "Amharic": "amh",
    "Arabic": "ara",
    "Aragonese": "arg",
    "Armenian": "arm",
    "Assamese": "asm",
    "Asturian": "ast",
    "Azerbaijani": "aze",
    "Basque": "baq",
    "Belarusian": "bel",
    "Bengali": "ben",
    "Bosnian": "bos",
    "Breton": "bre",
    "Bulgarian": "bul",
    "Burmese": "bur",
    "Catalan": "cat",
    "Chinese Simplified": "chi",
    "Chinese Traditional": "zht",
    "Chinese Bilingual": "zhe",
    "Croatian": "hrv",
    "Czech": "cze",
    "Danish": "dan",
    "Dari": "prs",
    "Dutch": "dut",
    "English": "eng",
    "Esperanto": "epo",
    "Estonian": "est",
    "Extremaduran": "ext",
    "Finnish": "fin",
    "French": "fre",
    "Gaelic": "gla",
    "Galician": "glg",
    "Georgian": "geo",
    "German": "ger",
    "Greek": "ell",
    "Hebrew": "heb",
    "Hindi": "hin",
    "Hungarian": "hun",
    "Icelandic": "ice",
    "Igbo": "ibo",
    "Indonesian": "ind",
    "Interlingua": "ina",
    "Irish": "gle",
    "Italian": "ita",
    "Japanese": "jpn",
    "Kannada": "kan",
    "Kazakh": "kaz",
    "Khmer": "khm",
    "Korean": "kor",
    "Kurdish": "kur",
    "Latvian": "lav",
    "Lithuanian": "lit",
    "Luxembourgish": "ltz",
    "Macedonian": "mac",
    "Malay": "may",
    "Malayalam": "mal",
    "Manipuri": "mni",
    "Marathi": "mar",
    "Mongolian": "mon",
    "Montenegrin": "mne",
    "Navajo": "nav",
    "Nepali": "nep",
    "Northern Sami": "sme",
    "Norwegian": "nor",
    "Occitan": "oci",
    "Odia": "ori",
    "Persian": "per",
    "Polish": "pol",
    "Portuguese (BR)": "pob",
    "Portuguese (MZ)": "pom",
    "Portuguese": "por",
    "Pushto": "pus",
    "Romanian": "rum",
    "Russian": "rus",
    "Santali": "sat",
    "Serbian": "scc",
    "Sindhi": "snd",
    "Sinhalese": "sin",
    "Slovak": "slo",
    "Slovenian": "slv",
    "Somali": "som",
    "Spanish (EU)": "spn",
    "Spanish (LA)": "spl",
    "Spanish": "spa",
    "Swahili": "swa",
    "Swedish": "swe",
    "Syriac": "syr",
    "Tagalog": "tgl",
    "Tamil": "tam",
    "Tatar": "tat",
    "Telugu": "tel",
    "Thai": "tha",
    "Toki Pona": "tok",
    "Turkish": "tur",
    "Turkmen": "tuk",
    "Ukrainian": "ukr",
    "Urdu": "urd",
    "Uzbek": "uzb",
    "Vietnamese": "vie",
    "Welsh": "wel",
}


class OpenSubtitlesSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._supported_languages = Language.build_languages_set(SUPPORTED_LANGUAGES)
        self._http_client.base_url = "https://www.opensubtitles.org"
        self._http_client.default_headers["Host"] = "www.opensubtitles.org"
        self._http_client.default_headers["Referer"] = "https://www.opensubtitles.org"
        self._http_client.default_headers["Accept"] = "text/html,application/xhtml+xml,application/xml"
        self._http_client.default_headers["Accept-Language"] = "en-US,en"
        self._http_client.force_https = True

    @property
    def name(self) -> str:
        return "OpenSubtitles"

    @property
    def short_name(self) -> str:
        return "OS"

    @property
    def supported_languages(self) -> Set[Language]:
        return self._supported_languages

    def __fetch_search_title_urls(self, request: SearchRequest, supported_request_languages: List[Language]) -> List[Tuple[str, str]]:
        search_term = self._build_search_term(request)
        language_codes = ",".join([l.three_letter_code for l in supported_request_languages]) \
            if supported_request_languages else 'all'
        http_request = HttpRequest("/en/search2/sublanguageid-%s/moviename-%s" % (language_codes, quote(search_term)))
        http_request.follow_redirects = False
        http_response = self._http_client.exchange(http_request)
        if 300 <= http_response.status_code < 400:
            redirect_url = http_response.get_header_value("Location").replace(" ", "+")
            if re.search(r"/en/search/sublanguageid-[^/]+/idmovie-\d+", redirect_url) or \
                    re.search(r"/en/search/imdbid-\d+/sublanguageid-[^/]+/moviename", redirect_url):
                self._logger.info("Detected redirect to single title URL: " + redirect_url)
                return [(search_term, redirect_url)]
            else:
                self._logger.info("Detected redirect to titles search URL: " + redirect_url)
                http_request = HttpRequest(redirect_url)
                http_response = self._http_client.exchange(http_request)
        titles: List[Tuple[str, str]] = []
        result_tr_tags = http_response.get_data_as_html().select("table#search_results > tbody > tr")[1:]
        for result_tr_tag in result_tr_tags:
            if len(result_tr_tag.find_all("td", recursive=False)) < 5:
                continue  # skip add rows
            if result_tr_tag.select_one('img[src$="/icons/tv-series.gif"]'):
                continue  # skip tv show rows (we are interested only in movies or episode results)
            # <a class="bnone" title="subtitles - &quot;Pluto&quot; Episode #1.3" href="/en/search/sublanguageid-eng,spa/idmovie-1406543">"Pluto" Episode #1.3 (2023)</a>
            result_anchor_tag = result_tr_tag.select_one("a.bnone")
            title_name = normalize_white_space(result_anchor_tag.get_text(strip=True))
            title_url = result_anchor_tag.attrs["href"]
            titles.append((title_name, title_url))
        return titles

    def __parse_single_search_result(self, result_html: BeautifulSoup) -> SearchResult:
        result = SearchResult()
        title_language_cds = normalize_white_space(result_html.select_one("h2").get_text(strip=True))
        match = re.search(
            r'(?P<title>[^<]+)\s+(?P<language>[A-z]+)\s+subtitles \((?P<year>\d\d\d\d)\) (?P<cds>\d+)CD\s+[^<]+', title_language_cds)
        if self._settings.exclude_splitted_subtitles and int(match["cds"]) > 1:
            return None
        result.title = "%s (%s)" % (match['title'], match["year"])
        result.language = Language(match["language"])
        result.is_hearing_impaired = result_html.select_one('h1').parent.select_one(
            'img[src$="/icons/hearing_impaired.gif"]') is not None
        details_tag = next(fs for fs in result_html.select("fieldset")
                           if fs.find("legend").get_text(strip=True) == "Subtitle details")
        result.downloads = details_tag.select_one('a[title="downloaded"]').get_text(strip=True)
        result.downloads = int(re.sub("[^\d]", "", result.downloads))
        result.id = details_tag.select_one('a[download="download"]').attrs["href"]
        release_image_tag = details_tag.select_one('img[title="Release name"]')
        result.release_info = normalize_white_space(release_image_tag.parent.get_text(strip=True))
        author_image_tag = details_tag.select_one('img[title="Uploader"]')
        result.author = author_image_tag.parent.get_text(strip=True)
        if result.author == "Anonymous":
            result.author = None
        result.rating = float(len(details_tag.select('div#subvote img[src$="/icons/star-on.gif"]')))
        return result

    def __parse_many_search_results(self, results_html: BeautifulSoup) -> List[SearchResult]:
        result_tr_tags = results_html.select("table#search_results > tbody > tr:not([style='display:none'])")[1:]
        results: List[SearchResult] = []
        for result_tr_tag in result_tr_tags:
            if len(result_tr_tag.find_all("td", recursive=False)) < 9:
                continue  # skip add rows
            cds = int(re.sub("CDS?", "", result_tr_tag.select_one("td:nth-child(3)").get_text(strip=1)))
            if self._settings.exclude_splitted_subtitles and cds > 1:
                continue  # skip multi cd results
            result = SearchResult()
            result.title = normalize_white_space(result_tr_tag.select_one("a.bnone").get_text(strip=True))
            result.release_info = result_tr_tag.select_one(
                'td:nth-child(1)').get_text(strip=True, separator="%----%").split("%----%")[1].split("\n")[-1:][0]
            result.is_hearing_impaired = result_tr_tag.select_one('img[src$="/icons/hearing_impaired.gif"]') is not None
            download_anchor = result_tr_tag.select_one('a[href^="/en/subtitleserve/"]')
            result.id = download_anchor.attrs["href"]
            result.downloads = int(re.sub(r"[^\d]", "", download_anchor.get_text(strip=True)))
            result.author = result_tr_tag.select_one('a[href^="/en/profile/iduser-"]').get_text(strip=True)
            result.language = Language(result_tr_tag.select_one("div.flag").parent.attrs["title"])
            result.rating = float(result_tr_tag.select_one('span[title$=" votes"]').get_text(strip=True))
            results.append(result)
        return results

    def _fetch_search_results(self, request: SearchRequest, supported_request_languages: List[Language]) -> List[SearchResult]:
        results: List[SearchResult] = []
        titles = self.__fetch_search_title_urls(request, supported_request_languages)
        for title_index, (title_name, title_url) in enumerate(titles[:MAX_TITLES_COUNT]):
            self._logger.info("Processing search results for title %s" % title_name)
            http_request = HttpRequest(title_url, follow_redirects=False)
            http_request.sleep_before = timedelta(seconds=1) if title_index > 0 else None
            http_response = self._http_client.exchange(http_request)
            if 300 <= http_response.status_code < 400:
                http_request = HttpRequest(http_response.get_header_value("Location"))
                http_response = self._http_client.exchange(http_request)
                result = self.__parse_single_search_result(http_response.get_data_as_html())
                if result:
                    results.append(result)
            else:
                http_response.write_into(self._settings.addon_user_path.joinpath("opensubs.html"))
                results.extend(self.__parse_many_search_results(http_response.get_data_as_html()))
            if request.max_results and len(results) >= request.max_results:
                results = results[:request.max_results]
                break
        return results

    def _get(self, request: GetRequest) -> List[GetResult]:
        http_request = HttpRequest(request.search_result_id)
        http_response = self._http_client.exchange(http_request)
        results = self._process_subtitles_data(http_response.file_name, http_response.data)
        return results
