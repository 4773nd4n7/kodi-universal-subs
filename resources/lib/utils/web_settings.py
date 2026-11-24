# -*- coding: utf-8 -*-
"""Web settings page for the add-on: a browser form over every declared setting.

The form is built from ``resources/settings.xml`` at request time, so adding or changing a setting
needs no change here: labels come from ``strings.po``, and the supported types are ``string``,
``boolean``, ``integer``, ``path`` and ``list[string]``. Secrets (anything whose id mentions a key,
password, token or session) are write-only: the page never renders their value, and a save only
writes the ones actually filled in.

The server is meant for the loopback interface. Requests are accepted only when the ``Host`` header
names an IP literal or ``localhost`` (which defeats DNS rebinding), when ``Origin`` — if present —
matches that host, and when the peer is loopback or inside the configured allowlist.
"""

import html
import ipaddress
import json
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

DEFAULT_PORT = 39517
DEFAULT_BIND = "127.0.0.1"
MAX_BODY_BYTES = 256 * 1024

#: Pseudo-setting: the page posts it as free text, the add-on parses it into a session blob.
SESSION_FIELD = "subdivx_session"

SUPPORTED_TYPES = ("string", "boolean", "integer", "path", "list[string]")

PO_ENTRY = re.compile(r'msgctxt "#(\d+)"\s*msgid "((?:[^"\\]|\\.)*)"\s*(?:msgstr "((?:[^"\\]|\\.)*)")?',
                      re.MULTILINE)


class Field:
    """One editable setting, as declared by ``settings.xml``, with the category it belongs to."""

    __slots__ = ("id", "type", "label", "help", "default", "options", "minimum", "maximum",
                 "allow_empty", "hidden", "category_id", "category_label", "category_help", "group_id")

    def __init__(self, field_id: str, field_type: str, label: str = "", help_text: str = "",
                 default: str = "", options: Optional[List[Tuple[str, str]]] = None,
                 minimum: Optional[int] = None, maximum: Optional[int] = None, allow_empty: bool = True,
                 hidden: bool = False, category_id: str = "", category_label: str = "",
                 category_help: str = "", group_id: str = ""):
        self.id = field_id
        self.type = field_type
        self.label = label or field_id
        self.help = help_text
        self.default = default
        self.options = options or []
        self.minimum = minimum
        self.maximum = maximum
        self.allow_empty = allow_empty
        self.hidden = hidden
        self.category_id = category_id
        self.category_label = category_label or category_id
        self.category_help = category_help
        self.group_id = group_id

    @property
    def is_secret(self) -> bool:
        """Whether the stored value must never be rendered.

        Declared by ``<control><hidden>true</hidden></control>`` in ``settings.xml`` — the same marker
        Kodi masks in its own dialog — so a new credential cannot be forgotten in a naming convention.
        """
        return self.hidden


def load_string_table(po_path: Path, language: str = "") -> Dict[str, str]:
    """The label texts of a ``strings.po`` file, keyed by their numeric id."""
    try:
        text = po_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    table = {}
    for match in PO_ENTRY.finditer(text):
        msgid = match.group(2)
        msgstr = match.group(3) or ""
        table[match.group(1)] = msgstr if language and msgstr.strip() else msgid
    return table


def pick_string_table(language_dir: Path, language: str) -> Dict[str, str]:
    """The table for ``language`` (e.g. ``es``) when this add-on ships it, else English."""
    candidates = sorted(language_dir.glob("resource.language.%s*/strings.po" % language)) if language else []
    if language_dir.joinpath("resource.language.en_gb", "strings.po").is_file():
        candidates.append(language_dir / "resource.language.en_gb" / "strings.po")
    for path in candidates:
        table = load_string_table(path, language)
        if table:
            return table
    return {}


def parse_settings_model(settings_xml: Path, strings: Dict[str, str]) -> List[Field]:
    """Every storable setting declared by ``settings.xml``, in file order.

    ``type="action"`` entries are buttons, not values, so they are skipped. Unknown types are kept
    with their declared type so the page can show them as read-only rather than lose them.
    """
    try:
        tree = ElementTree.parse(str(settings_xml))
    except (OSError, ElementTree.ParseError):
        return []
    fields: List[Field] = []
    for section in tree.iter("section"):
        for category in section.findall("category"):
            category_id = category.get("id") or ""
            category_label = strings.get(category.get("label") or "", category.get("label") or category_id)
            category_help = strings.get(category.get("help") or "", "")
            groups = [(group.get("id") or "", group.findall("setting"))
                      for group in category.findall("group")]
            groups.append(("", category.findall("setting")))  # settings declared outside a group
            for group_id, elements in groups:
                for element in elements:
                    field = _build_field(element, strings, category_id, category_label,
                                         category_help, group_id)
                    if field is not None:
                        fields.append(field)
    return fields


def _build_field(element, strings: Dict[str, str], category_id: str, category_label: str,
                 category_help: str, group_id: str) -> Optional[Field]:
    """One ``<setting>`` element as a Field, or None for a button or an unidentifiable entry."""
    field_id = element.get("id")
    if not field_id:
        return None
    # Action entries are buttons Kodi renders; they hold no value, so they are not fields.
    if (element.get("type") or "").strip().lower() == "action":
        return None
    options = [(option.text or "", option.text or "") for option in element.iter("option")]
    minimum = maximum = None
    for child in element.iter("minimum"):
        try:
            minimum = int(child.text or "")
        except (TypeError, ValueError):
            minimum = None
    for child in element.iter("maximum"):
        try:
            maximum = int(child.text or "")
        except (TypeError, ValueError):
            maximum = None
    return Field(
        field_id=field_id,
        field_type=element.get("type") or "string",
        label=strings.get(element.get("label") or "", element.get("label") or field_id),
        help_text=strings.get(element.get("help") or "", ""),
        default=(element.findtext("default") or "").strip(),
        options=options,
        minimum=minimum,
        maximum=maximum,
        allow_empty=(element.findtext("constraints/allowempty") or "false").strip().lower() == "true",
        # Kodi masks these in its own dialog; the page must also never render the stored value.
        hidden=(element.findtext("control/hidden") or "false").strip().lower() == "true",
        category_id=category_id,
        category_label=category_label,
        category_help=category_help,
        group_id=group_id,
    )


def parse_allowed_ips(value: str) -> List[ipaddress._BaseNetwork]:
    """The allowlist entries, ignoring anything unparsable."""
    networks = []
    for part in (value or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return networks


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _host_name(host_header: str) -> str:
    host_header = (host_header or "").strip()
    if host_header.startswith("["):  # [::1]:39517
        return host_header[1:].split("]", 1)[0]
    return host_header.rsplit(":", 1)[0] if host_header.count(":") == 1 else host_header


def request_allowed(peer: str, host_header: str, origin: Optional[str], bind: str,
                    allowed_ips: Sequence[ipaddress._BaseNetwork]) -> str:
    """Why a request must be refused, or an empty string when it may proceed."""
    host = _host_name(host_header)
    if not host:
        return "missing Host header"
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host.lower() != "localhost":
            return "Host must be an IP address or localhost"
    if origin:
        if origin != "http://" + (host_header or "").strip():
            return "cross-origin request rejected"
    peer_loopback = _is_loopback(peer)
    if not peer_loopback:
        try:
            peer_address = ipaddress.ip_address(peer)
        except ValueError:
            return "unrecognised client address"
        if not any(peer_address in network for network in allowed_ips):
            return "client address is not in the allowlist"
    elif not _is_loopback(host) and not _is_loopback(bind):
        return "loopback client must use a loopback Host"
    if _is_loopback(bind) and not peer_loopback:
        return "the page only listens on the loopback interface"
    return ""


def page_url(bind: str, port: int) -> str:
    """The address to open: the LAN address when listening beyond loopback."""
    host = bind
    if bind in ("", "0.0.0.0", "::"):
        host = local_ipv4() or "127.0.0.1"
    return "http://%s:%d/" % (host, port)


def local_ipv4() -> str:
    """This machine's primary IPv4 address, or an empty string when it cannot be determined."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # TEST-NET-1: never routed, no packet is sent
        return probe.getsockname()[0]
    except OSError:
        return ""
    finally:
        probe.close()


def _escape(value: str) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _render_field(field: Field, values: Dict[str, str]) -> str:
    current = values.get(field.id, "")
    name = _escape(field.id)
    parts = ['<div class="field" id="row-%s">' % name,
             '<label for="f-%s">%s</label>' % (name, _escape(field.label))]
    if field.is_secret:
        placeholder = "already set - leave blank to keep it" if current else "not set"
        if field.id == SESSION_FIELD:
            parts.append('<textarea id="f-%s" name="%s" spellcheck="false" placeholder="%s" '
                         'data-initial=""></textarea>' % (name, name, placeholder))
            parts.append('<p class="help">Paste the <code>cf_clearance</code> value (Application '
                         '&rarr; Cookies) or a request copied from the developer tools. The page '
                         'attaches your browser\'s user agent.</p>')
        else:
            parts.append('<input type="password" id="f-%s" name="%s" autocomplete="off" '
                         'placeholder="%s" value="" data-initial="">' % (name, name, placeholder))
            parts.append('<label class="inline"><input type="checkbox" name="%s__clear"> clear</label>'
                         % name)
    elif field.type == "boolean":
        checked = " checked" if str(current).lower() in ("true", "1") else ""
        initial = "checked" if checked else ""
        parts.append('<input type="checkbox" id="f-%s" name="%s" data-initial="%s"%s>'
                     % (name, name, initial, checked))
    elif field.type == "integer":
        bounds = ""
        if field.minimum is not None:
            bounds += ' min="%d"' % field.minimum
        if field.maximum is not None:
            bounds += ' max="%d"' % field.maximum
        parts.append('<input type="number" id="f-%s" name="%s" value="%s" data-initial="%s"%s>'
                     % (name, name, _escape(current), _escape(current), bounds))
    elif field.type == "list[string]" and field.options:
        parts.append('<div class="choices">')
        selected = {item.strip() for item in (current or "").split("|") if item.strip()}
        for value, option_label in field.options:
            checked = " checked" if value in selected else ""
            initial = "checked" if value in selected else ""
            parts.append('<label class="inline"><input type="checkbox" name="%s" value="%s" '
                         'data-list="1" data-initial="%s"%s> %s</label>'
                         % (name, _escape(value), initial, checked, _escape(option_label)))
        parts.append('</div>')
    else:
        parts.append('<input type="text" id="f-%s" name="%s" value="%s" data-initial="%s" '
                     'spellcheck="false">'
                     % (name, name, _escape(current), _escape(current)))
    if field.type not in SUPPORTED_TYPES:
        parts.append('<p class="help warn">This setting type (%s) is not editable here; use Kodi\'s '
                     'own settings.</p>' % _escape(field.type))
    if field.help:
        parts.append('<p class="help">%s</p>' % _escape(field.help))
    parts.append('</div>')
    return "".join(parts)


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
 body { font-family: system-ui, sans-serif; margin: 1.5rem auto; max-width: 52rem; line-height: 1.45;
        padding: 0 1rem; }
 .field { margin: 0 0 1.1rem; }
 fieldset { border: 1px solid #ddd; border-radius: 6px; margin: 0 0 1.4rem; padding: .4rem 1rem 1rem; }
 legend { font-size: 1.1rem; font-weight: 700; padding: 0 .35rem; }
 nav.categories { display: flex; flex-wrap: wrap; gap: .5rem; margin: 0 0 1.2rem; }
 nav.categories a { border: 1px solid #ddd; border-radius: 999px; padding: .15rem .7rem;
                    text-decoration: none; background: #fafafa; }
 label { font-weight: 600; display: block; }
 label.inline { font-weight: 400; display: inline-block; margin-right: 1rem; }
 input[type=text], input[type=password], input[type=number], textarea {
   width: 100%%; padding: .35rem; box-sizing: border-box; font: inherit; }
 textarea { height: 7rem; font: 12px/1.4 ui-monospace, monospace; }
 .help { margin: .2rem 0 0; color: #555; font-size: .85rem; }
 .warn { color: #a40; }
 .status { position: sticky; top: 0; padding: .5rem; margin-bottom: 1rem; background: #eef; }
 .status.error { background: #fee; }
 code { background: #eee; padding: 0 .2rem; border-radius: 3px; }
</style>
</head>
<body>
<h1>%(title)s</h1>
<div id="status" class="status">%(notice)s</div>
%(nav)s
<form id="form">
%(fields)s
<p><button type="submit">Save changed settings</button></p>
</form>
<script>
const form = document.getElementById("form");
const status = document.getElementById("status");

// Every input carries data-initial, so a save submits exactly what the user touched: secrets stay
// empty and untouched, lists are compared as sets, and checkboxes as their checked state.
function collectChanges() {
  const values = {};
  const lists = {};
  for (const element of form.elements) {
    if (!element.name || element.name.endsWith("__clear")) continue;
    if (!("initial" in element.dataset)) continue;
    if (element.dataset.list === "1") {
      if (!lists[element.name]) lists[element.name] = [];
      lists[element.name].push(element);
      continue;
    }
    if (element.type === "checkbox") {
      const initial = element.dataset.initial === "checked";
      if (element.checked !== initial) values[element.name] = element.checked ? "true" : "false";
    } else if (element.value !== element.dataset.initial) {
      values[element.name] = element.value;
    }
  }
  for (const [name, elements] of Object.entries(lists)) {
    const current = elements.filter((element) => element.checked).map((element) => element.value);
    const initial = elements.filter((element) => element.dataset.initial === "checked")
                            .map((element) => element.value);
    if (current.join("|") !== initial.join("|")) values[name] = current;
  }
  for (const element of form.elements) {
    if (element.name && element.name.endsWith("__clear") && element.checked) {
      values[element.name.slice(0, -7)] = "";
    }
  }
  return values;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = collectChanges();
  status.className = "status";
  if (!Object.keys(values).length) {
    status.textContent = "Nothing changed.";
    return;
  }
  status.textContent = "Saving...";
  try {
    const response = await fetch("/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: values, ua: navigator.userAgent }),
    });
    const result = await response.json();
    if (result.ok) {
      status.textContent = "Saved " + result.saved + " setting(s).";
      location.replace("/?saved=" + encodeURIComponent(result.saved));
    } else {
      status.className = "status error";
      status.textContent = "Not saved: " + JSON.stringify(result.errors || result.error || result);
    }
  } catch (error) {
    status.className = "status error";
    status.textContent = "Could not reach Kodi: " + error;
  }
});
</script>
</body>
</html>
"""


def render_page(title: str, fields: Sequence[Field], values: Dict[str, str], notice: str = "") -> str:
    """The settings form, grouped by category like Kodi's own dialog, secrets never rendered."""
    rows: List[str] = []
    categories: List[Tuple[str, str]] = []
    current_category = None
    for field in fields:
        if field.category_id != current_category:
            if current_category is not None:
                rows.append("</fieldset>")
            categories.append((field.category_id, field.category_label))
            rows.append('<fieldset id="cat-%s"><legend>%s</legend>'
                        % (_escape(field.category_id), _escape(field.category_label)))
            if field.category_help:
                rows.append('<p class="help">%s</p>' % _escape(field.category_help))
            current_category = field.category_id
        field_values = dict(values)
        if field.is_secret:
            field_values[field.id] = "" if not values.get(field.id) else "set"
        rows.append(_render_field(field, field_values))
    if current_category is not None:
        rows.append("</fieldset>")
    nav = ""
    if len(categories) > 1:
        nav = '<nav class="categories">%s</nav>' % "".join(
            '<a href="#cat-%s">%s</a>' % (_escape(category_id), _escape(label))
            for category_id, label in categories)
    return PAGE_TEMPLATE % {
        "title": _escape(title),
        "notice": _escape(notice),
        "nav": nav,
        "fields": "\n".join(rows),
    }


def normalise_submission(field: Field, raw, browser_user_agent: str = "") -> Tuple[Optional[str], str]:
    """The value to store for ``field``, or an error message explaining why it cannot be."""
    if field.id == SESSION_FIELD:
        from resources.lib.providers.subdivx_source_provider import (encode_browser_session,
                                                                     explain_browser_session)
        session, reason = explain_browser_session(str(raw or ""), browser_user_agent)
        if not session:
            return None, reason
        if "cf_clearance=" not in session["cookie"]:
            return None, ("the pasted cookies have no cf_clearance; copy a request made after the "
                          "Cloudflare check passed")
        return encode_browser_session(session), ""
    if field.type == "boolean":
        return ("true" if str(raw).strip().lower() in ("1", "true", "yes", "on") else "false"), ""
    if field.type == "integer":
        try:
            number = int(str(raw).strip())
        except (TypeError, ValueError):
            return None, "must be a whole number"
        if field.minimum is not None and number < field.minimum:
            return None, "must be at least %d" % field.minimum
        if field.maximum is not None and number > field.maximum:
            return None, "must be at most %d" % field.maximum
        return str(number), ""
    if field.type == "list[string]" and field.options:
        allowed = {value for value, _ in field.options}
        picked = [item for item in (raw if isinstance(raw, list) else [raw]) if item in allowed]
        return "|".join(dict.fromkeys(picked)), ""
    text = "" if raw is None else str(raw).strip()
    if not text and not field.allow_empty:
        return None, "cannot be empty"
    return text, ""


class WebSettingsHandler(BaseHTTPRequestHandler):
    """Serve the form and accept partial saves."""

    server_version = "UniversalSubsWeb/1.0"

    def log_message(self, format: str, *args) -> None:
        pass  # Kodi owns the log.

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        if path not in ("/", "/index.html"):
            self._send_text(404, "Not found")
            return
        refusal = self._refusal()
        if refusal:
            self._send_text(403, "Refused: %s" % refusal)
            return
        notice = ""
        match = re.search(r"(?:^|&)saved=(\d+)(?:&|$)", query)
        if match:
            notice = "Saved %s setting(s). They apply from the next search." % match.group(1)
        self._send_text(200, self.server.render(notice), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/settings":
            self._send_json(404, {"ok": False, "error": "unknown path"})
            return
        refusal = self._refusal()
        if refusal:
            self._send_json(403, {"ok": False, "error": refusal})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"ok": False, "error": "invalid body size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._send_json(400, {"ok": False, "error": "body is not JSON"})
            return
        self._send_json(200, self.server.save(payload))

    def _refusal(self) -> str:
        peer = self.client_address[0] if self.client_address else ""
        return request_allowed(peer, self.headers.get("Host", ""), self.headers.get("Origin"),
                               self.server.bind, self.server.allowed_ips)

    def _send_text(self, status: int, body: str, content_type: str = "text/plain; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send_text(status, json.dumps(payload), "application/json")


class WebSettingsServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, bind: str, allowed_ips, model: Sequence[Field],
                 get_values: Callable[[], Dict[str, str]],
                 set_value: Callable[[str, str], None], title: str):
        self.bind = bind
        self.allowed_ips = allowed_ips
        self.model = model
        self.get_values = get_values
        self.set_value = set_value
        self.title = title
        super().__init__(address, WebSettingsHandler)

    def render(self, notice: str = "") -> str:
        return render_page(self.title, self.model, self.get_values(), notice)

    def save(self, payload: dict) -> dict:
        """Validate and store the submitted fields; returns the JSON body for the page."""
        submitted = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(submitted, dict):
            return {"ok": False, "error": "no values submitted"}
        browser_user_agent = payload.get("ua") if isinstance(payload.get("ua"), str) else ""
        fields = {field.id: field for field in self.model}
        saved = 0
        errors: Dict[str, str] = {}
        for field_id, raw in submitted.items():
            field = fields.get(field_id)
            if field is None:
                errors[field_id] = "unknown setting"
                continue
            value, reason = normalise_submission(field, raw, browser_user_agent)
            if value is None:
                errors[field_id] = reason
                continue
            try:
                self.set_value(field_id, value)
            except Exception as error:  # Kodi raises on a setting it does not know yet
                errors[field_id] = "Kodi refused the value (%s); restart Kodi if it is new" % error
                continue
            saved += 1
        return {"ok": not errors, "saved": saved, "errors": errors} if errors else {"ok": True, "saved": saved}


def start_web_settings_server(bind: str, port: int, allowed_ips: str, model: Sequence[Field],
                              get_values: Callable[[], Dict[str, str]],
                              set_value: Callable[[str, str], None], title: str) -> WebSettingsServer:
    """Bind the page in a daemon thread; raises OSError when the address is taken."""
    resolved_bind = (bind or DEFAULT_BIND).strip()
    server = WebSettingsServer((resolved_bind, port), resolved_bind, parse_allowed_ips(allowed_ips),
                              model, get_values, set_value, title)
    thread = threading.Thread(target=server.serve_forever, name="web-settings", daemon=True)
    thread.start()
    return server
