# -*- coding: utf-8 -*-

import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from resources.lib.common.language import Language
from resources.lib.common.mapped_languages import MappedLanguages
from resources.lib.common.settings import Settings
from resources.lib.providers.get_request import GetRequest
from resources.lib.providers.get_result import GetResult
from resources.lib.providers.search_request import (SearchRequest,
                                                   SearchResultsCounter)
from resources.lib.providers.search_result import SearchResult
from resources.lib.providers.source_provider import SourceProvider
from resources.lib.utils.http_client import HttpRequest
from resources.lib.utils.text import unescape_html

STAR_HTML = '<i class="fa fa-star rating-color">'


#: Cookie names that make up a SubDivX session; ``cf_clearance`` is the one Cloudflare requires.
KNOWN_SESSION_COOKIES = ("cf_clearance", "PHPSESSID", "__cf_bm")

RE_CURL_HEADER = re.compile(r"(?:-H|--header)\s+(['\"])(?P<value>.+?)\1", re.DOTALL)
RE_CURL_COOKIE = re.compile(r"(?:-b|--cookie)\s+(['\"])(?P<value>.+?)\1", re.DOTALL)
RE_CURL_USER_AGENT = re.compile(r"(?:-A|--user-agent)\s+(['\"])(?P<value>.+?)\1", re.DOTALL)
RE_POWERSHELL_HEADER = re.compile(
    r"['\"](?P<name>cookie|user-agent)['\"]\s*=\s*['\"](?P<value>[^'\"]*)['\"]", re.IGNORECASE)
RE_HEADER_LINE = re.compile(r"^\s*(?P<name>cookie|user-agent)\s*:\s*(?P<value>.+?)\s*$",
                            re.IGNORECASE | re.MULTILINE)
#: A bare ``cf_clearance`` value: base64url characters only, long enough to be a token. Standard
#: base64 padding (``=``, ``+``, ``/``) is excluded so a truncated session blob is not mistaken for one.
RE_CLEARANCE_VALUE = re.compile(r"^[A-Za-z0-9_-]{40,}$")


def encode_browser_session(session: Dict[str, str]) -> str:
    """The compact stored form of a session: base64 of the ``{"cookie", "ua"}`` JSON."""
    payload = {key: session[key] for key in ("cookie", "ua") if session.get(key)}
    return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")


def _normalize_cookie_header(value: str) -> str:
    """Keep the ``name=value`` pairs of a cookie header and drop everything else."""
    pairs: List[str] = []
    for part in (value or "").split(";"):
        pair = part.strip()
        if "=" not in pair:
            continue
        if not pair.split("=", 1)[0].strip():
            continue
        pairs.append(pair)
    return "; ".join(pairs)


def _parse_session_blob(value: str) -> Optional[Dict[str, str]]:
    """Decode the stored form: base64 JSON, or plain JSON pasted by hand."""
    candidates = [value]
    try:
        candidates.insert(0, base64.b64decode(value + "=" * (-len(value) % 4)).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        pass
    for text in candidates:
        try:
            data = json.loads(text)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("cookie"), str) and data["cookie"]:
            return data
    return None


def _parse_copied_request(value: str) -> Optional[Dict[str, str]]:
    """Cookie and user agent out of a request copied from the browser's developer tools.

    ``cf_clearance`` is HttpOnly, so ``document.cookie`` never sees it and a page script cannot
    capture the session. The Network tab can: "Copy as cURL" (bash, cmd or PowerShell) carries the
    cookie header together with the user agent the clearance was issued to.
    """
    cookie = ""
    user_agent = ""
    for match in RE_CURL_HEADER.finditer(value):
        name, _, header_value = match.group("value").partition(":")
        lowered = name.strip().lower()
        if lowered == "cookie" and not cookie:
            cookie = header_value.strip()
        elif lowered == "user-agent" and not user_agent:
            user_agent = header_value.strip()
    if not cookie:
        match = RE_CURL_COOKIE.search(value)
        cookie = match.group("value").strip() if match else ""
    if not user_agent:
        match = RE_CURL_USER_AGENT.search(value)
        user_agent = match.group("value").strip() if match else ""
    for pattern in (RE_POWERSHELL_HEADER, RE_HEADER_LINE):
        for match in pattern.finditer(value):
            name = match.group("name").lower()
            if name == "cookie" and not cookie:
                cookie = match.group("value").strip()
            elif name == "user-agent" and not user_agent:
                user_agent = match.group("value").strip()
    if not cookie:
        return None
    session = {"cookie": cookie}
    if user_agent:
        session["ua"] = user_agent
    return session


def _parse_cookie_header(value: str) -> Optional[Dict[str, str]]:
    """A bare ``Cookie`` header value, or a lone ``cf_clearance`` value pasted on its own.

    Copying the value out of Application -> Cookies is a common shortcut; it is taken as the
    clearance cookie. It is the weaker input, though: Cloudflare binds the clearance to the user
    agent, and a pasted value carries none, so the add-on falls back to its own header.
    """
    if "\n" in value:
        return None
    if re.match(r"(?i)\s*(curl|wget|invoke-)", value):
        return None
    if "=" in value:
        return {"cookie": value}
    if RE_CLEARANCE_VALUE.match(value):
        return {"cookie": "cf_clearance=" + value}
    return None


def _cookie_names(cookie: str) -> set:
    """The cookie names of a normalized cookie header."""
    return {pair.split("=", 1)[0].strip() for pair in cookie.split(";") if "=" in pair}


def parse_browser_session(raw: str) -> Dict[str, str]:
    """Decode a captured SubDivX session into the ``cookie`` and ``ua`` headers to replay.

    Three shapes are accepted, because there are three ways to get an HttpOnly clearance out of a
    browser: the compact base64 blob this add-on stores, a request copied from the developer tools
    (``Copy as cURL``, or a pasted header block), and the bare ``Cookie`` header value. Cloudflare
    binds ``cf_clearance`` to the user agent it was issued to, so both travel together. Text without
    any SubDivX session cookie yields an empty mapping, which keeps the anonymous request path.
    """
    return explain_browser_session(raw)[0]


def explain_browser_session(raw: str, browser_user_agent: str = "") -> Tuple[Dict[str, str], str]:
    """The parsed session, plus the reason the pasted text was rejected when it is empty.

    The reason is shown on the capture page and written to the Kodi log, because "rejected" alone
    gives the user nothing to act on: the usual mistake is copying the request Cloudflare answered
    with the challenge, which carries no clearance cookie yet.

    ``browser_user_agent`` is supplied by the capture page, which runs in the same browser that
    holds the clearance. It completes a session captured as a lone cookie value, the simplest way to
    get an HttpOnly cookie out of the browser.
    """
    value = (raw or "").strip()
    if not value:
        return {}, "nothing was pasted"
    session = (_parse_session_blob(value) or _parse_copied_request(value)
               or _parse_cookie_header(value))
    if not session:
        if re.search(r"(?i)(^|\s)(curl|invoke-|wget)|-H\s|--header\s", value):
            return {}, ("no cookie header was found in the pasted request; copy a request that was "
                        "made after the page finished loading")
        if "\n" not in value and "=" not in value:
            return {}, ("the pasted text looks like a cookie value without its name; paste the whole "
                        "request instead (Copy as cURL) so the user agent travels with the clearance")
        return {}, "the pasted text is not a copied request, a cookie header or a stored session"
    cookie = _normalize_cookie_header(session.get("cookie") or "")
    if not cookie:
        return {}, "the pasted cookie header is empty"
    if not _cookie_names(cookie).intersection(KNOWN_SESSION_COOKIES):
        return {}, "the pasted cookie header has no SubDivX cookie in it"
    parsed = {"cookie": cookie}
    user_agent = (session.get("ua") or "").strip() or (browser_user_agent or "").strip()
    if user_agent:
        parsed["ua"] = user_agent
    return parsed, ""


RE_CSRF_TOKEN = re.compile(r'name="csrf-token"\s+content="([^"]+)"', re.IGNORECASE)
RE_SITE_VERSION = re.compile(r'id="vs"[^>]*>\s*v?([\d.]+)\s*<', re.IGNORECASE)


def parse_csrf_token(html: str) -> str:
    """The CSRF token the site publishes in ``<meta name="csrf-token">``."""
    match = RE_CSRF_TOKEN.search(html or "")
    return match.group(1) if match else ""


def parse_search_field(html: str) -> str:
    """The result endpoint's search parameter name, e.g. ``buscar461`` for the page's ``v4.61``.

    The site derives it in JavaScript as ``"buscar" + $("#vs").text().replace(/[v.]/g, "")``. A
    hardcoded ``buscar`` is an unknown field to the endpoint, which answers with an empty body.
    """
    match = RE_SITE_VERSION.search(html or "")
    digits = re.sub(r"\D", "", match.group(1)) if match else ""
    return "buscar" + digits if digits else "buscar"


RE_FORCED_SUBTITLE_FILE_NAME = re.compile(r"\b(forced|forzado)\b", re.IGNORECASE)


class SubDivXSourceProvider(SourceProvider):

    def __init__(self, settings: Settings):
        super().__init__(settings, MappedLanguages([Language.spanish]))
        self._http_client.base_url = "https://www.subdivx.com/"
        self._http_client.default_headers["Referer"] = "https://www.subdivx.com/index.php"
        self.__browser_session = parse_browser_session(settings.subdivx_session)
        if self.__browser_session:
            self._http_client.default_headers["Cookie"] = self.__browser_session["cookie"]
            if self.__browser_session.get("ua"):
                # cf_clearance is bound to the user agent that obtained it.
                self._http_client.default_headers["User-Agent"] = self.__browser_session["ua"]
        self.__csrf_token = ""
        self.__search_field = "buscar"
        self.__search_token = ""
        self.__session_initialized = False

    @property
    def name(self) -> str:
        return "SubDivX"

    @property
    def short_name(self) -> str:
        return "SDX"

    def missing_credentials(self) -> str:
        """SubDivX cannot reach the site without a clearance cookie.

        Cloudflare challenges every client that is not a browser, so the session is required rather
        than optional. Whether a *stored* one is still valid can only be learned by making a request;
        that case is reported from the challenge response instead.
        """
        if not self.__browser_session:
            return "SubDivX needs a browser session (Cloudflare blocks this client)"
        return ""

    @property
    def _overrides_ratings_from_downloads(self) -> bool:
        return True

    def __initialize_search_session(self) -> None:
        """Read the CSRF token and the search field name the site currently expects.

        Done once per provider instance. The homepage also hands out the site's own session cookie,
        which the result endpoint needs alongside the clearance.
        """
        if self.__session_initialized:
            return
        self.__session_initialized = True
        try:
            home_html = self._http_client.exchange(
                HttpRequest("/", "GET", allow_caching=False)).get_data_as_text()
        except Exception as error:
            self._logger.warning("Could not load the SubDivX homepage: %s", error)
            return
        self.__csrf_token = parse_csrf_token(home_html)
        self.__search_field = parse_search_field(home_html)
        if self.__csrf_token:
            self._http_client.default_headers["X-CSRF-Token"] = self.__csrf_token
        self.__search_token = self.__request_search_token()

    def __request_search_token(self) -> str:
        """The per-session token the site's own search requests send as ``token``."""
        if not self.__csrf_token:
            return ""
        try:
            request = HttpRequest("/inc/gt.php", "GET", allow_caching=False)
            request.add_url_query_params({"gt": 1})
            token_data = self._http_client.exchange(request).get_data_as_json()
        except Exception as error:
            self._logger.warning("Could not obtain the SubDivX search token: %s", error)
            return ""
        return str(token_data.get("token") or "") if isinstance(token_data, dict) else ""

    def _fetch_search_results(self, request: SearchRequest, request_internal_languages: List[Language]) -> List[SearchResult]:
        self.__initialize_search_session()
        form_data = {"tabla": "resultados", self.__search_field: self._build_search_term(request)}
        if self.__search_token:
            form_data["token"] = self.__search_token
        http_request = HttpRequest("/inc/ajax.php", "POST")
        http_request.set_urlencoded_form_data(form_data)
        http_response = self._http_client.exchange(http_request)
        payload = http_response.data
        if not payload:
            raise ValueError(
                "SubDivX returned an empty response to a search request; the endpoint's request "
                "shape has changed again (the search field name is derived from the site version, "
                "so check parse_search_field)")
        if payload.lstrip()[:1] not in (b"{", b"["):
            raise ValueError(
                "SubDivX answered a search request with %d bytes that are not JSON; the body is "
                "probably a Cloudflare challenge, so re-capture the browser session" % len(payload))
        results_data: Dict[str, Any] = http_response.get_data_as_json()
        results: List[SearchResult] = []
        results_counter: SearchResultsCounter = request.build_counter()
        for result_data in results_data["aaData"]:
            if self._settings.exclude_splitted_subtitles and result_data.get("cds", 1) > 1:
                continue
            result = SearchResult()
            result.id = result_data["id"]
            result.title = unescape_html(result_data["titulo"])
            result.release_info = unescape_html(re.sub(r"</?[^>]+>", "", result_data["descripcion"]))
            result.author = re.sub(r".*/>\s*([^<]+)\s*</a>\s*</div>.*", r"\1", result_data.get("nick", ""))
            result.downloads = result_data["descargas"]
            result.rating = self.__parse_rating(result_data)
            result.language = Language.spanish
            results.append(result)
            results_counter.try_accept_result(result)
            if results_counter.reached_max_results:
                return results
        return results

    @staticmethod
    def __parse_rating(result_data: Dict[str, Any]) -> float:
        """The result's average rating, from ``promedio`` or the older rendered-star field."""
        promedio = str(result_data.get("promedio") or "").strip()
        if promedio:
            try:
                return float(promedio)
            except ValueError:
                return 0.0
        return float(str(result_data.get("calificacion", "")).count(STAR_HTML))

    def _is_forced_subtitle_file_name(self, file_name: str) -> bool:
        return bool(RE_FORCED_SUBTITLE_FILE_NAME.search(file_name))

    def _get(self, request: GetRequest) -> List[GetResult]:
        http_request = HttpRequest("/descargar.php")
        http_request.add_url_query_params({"id": request.search_result_id})
        http_response = self._http_client.exchange(http_request)
        results = self._process_get_subtitles_data(http_response.file_name, http_response.data)
        return results
