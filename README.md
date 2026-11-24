# Universal Subs Kodi Plugin

> One ring to rule them all, one ring to find them,<br/>
> One ring to bring them all, and in the darkness bind them;<br/>
> In the Land of Mordor where the shadows lie.

## Requirements

This is a Kodi add-on, so **Kodi provides the interpreter and the third-party libraries**; nothing
is bundled in the repository. The versions that matter:

| Kodi | `xbmc.python` | Python |
| --- | --- | --- |
| 20 Nexus | 3.0.1 | 3.11.2 |
| 21 Omega | 3.0.1 | 3.11.7 |

[addon.xml](addon.xml) declares `xbmc.python 3.0.1`, so the minimum is **Kodi 20 Nexus** and the
minimum interpreter is **Python 3.11**; `pyproject.toml` requires `>=3.11,<3.12`, which is what makes
uv pick that interpreter for local development. Kodi 19 Matrix (Python 3.8) is not supported.

Runtime libraries are declared in addon.xml as `script.module.*` imports (beautifulsoup4,
cachetools, chardet, html5lib, PyYAML, Unidecode, typing_extensions) plus the binary add-ons
`vfs.libarchive` and `vfs.rar`. Kodi ignores `pyproject.toml`; its `[project] dependencies` mirror
the same list so the code can run, and be tested, outside Kodi. Keep the two in sync when adding a
dependency.

## Development

`pyproject.toml` declares the development environment and `uv.lock` pins it.
[uv](https://docs.astral.sh/uv/) reads `requires-python` from `pyproject.toml`, so one command
builds the virtualenv:

```powershell
uv sync             # .venv with the dependencies and the dev tools
uv run poe test     # every test, live providers included
uv run poe offline  # skips the live providers
uv run poe lint     # ruff check
```

`uv run` puts `.venv` on `PATH`, so nothing needs activating. `uv run poe` lists the tasks; they
live in `[tool.poe.tasks]`:

| Task | Runs |
| --- | --- |
| `poe test` | `pytest` (every test) |
| `poe offline` | `pytest` with `UNIVERSAL_SUBS_NETWORK_TESTS=0` |
| `poe lint` / `poe format` | `ruff check .` / `ruff format .` |
| `poe package` | `scripts/addon_tasks.py package` |
| `poe install` | `scripts/addon_tasks.py install` |

Extra arguments reach pytest after `poe <task> --`, for example `uv run poe test -- -k cleanup`,
`uv run poe test -- -x --tb=line`, or `uv run poe install -- --kodi-home "$env:APPDATA\Kodi"`.

`poe install` writes to `<Kodi userdata>\addons\service.subtitles.universalsubs`. That userdata
belongs to the Windows account running Kodi, which is not necessarily the one you build from: a
media centre usually runs Kodi as its own account, so `%APPDATA%\Kodi` of your shell is the wrong
place. Name that account instead of spelling out the path:

```powershell
uv run poe install -- --kodi-user Kodi   # C:\Users\Kodi\AppData\Roaming\Kodi
```

`--kodi-user` also accepts the `DOMAIN\name` form and rejects an account that has no profile
directory. It and `--kodi-home` are mutually exclusive, and `KODI_HOME` still covers the portable
case. Either way the install replaces the add-on folder wholesale and rewrites `addon.xml` with the
real version.

A running Kodi is restarted after the copy, because the service and the settings schema are only read
at startup. The install does not launch it itself — a process spawned from the shell would run as the
caller, which is useless when Kodi owns the media centre's session. Instead it drops `restart.request`
into the add-on's profile, and the running service does the restart: on Windows it starts a detached
helper that waits for Kodi to exit and then launches it again, and only then quits, because Kodi's own
`RestartApp` shuts down on Windows without starting back up. `uv run poe install -- --no-restart`
skips the trigger altogether.

When the service does not react — an older build, or no service running — the install reports it and
exits non-zero, leaving Kodi as it was. Starting Kodi is deliberately out of scope: spawned from
another account's shell it cannot reach the media centre's session, which is the whole reason the
service performs the restart.

The suite runs on [pytest](https://docs.pytest.org/), which discovers the `unittest`-style test
cases as they are. `-v` is part of the configured `addopts`, so the console names each test as it
starts and appends the outcome when it finishes; `-q` swaps that for the compact dots view.
`-ra` lists the reason for every skip and `--tb=short` keeps tracebacks readable. Runner options
worth knowing: `-x` stops at the first failure, `-k` selects by name, `--lf` re-runs the last
failures, `--durations=10` shows the slowest tests, and `--junitxml=report.xml` writes the result
for CI. Configuration lives in `[tool.pytest.ini_options]`.

The version is written once, in `pyproject.toml`. `addon.xml` carries the `@VERSION@` placeholder
and only the packaged archive and the installed copy receive the real number, so packaging never
rewrites a tracked file and two builds of the same tree are byte identical. The flip side: the
`addon.xml` in a checkout is not loadable by Kodi as-is, so install with `poe install` (or ship a
`poe package` archive) instead of copying the folder into `addons/`. The release workflow performs
the same substitution and refuses to publish when the tag and the `pyproject.toml` version differ.

Without uv, install the same dependencies into a Python 3.11 environment and run pytest directly:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install beautifulsoup4 cachetools chardet html5lib PyYAML Unidecode typing_extensions poethepoet pytest ruff
.venv\Scripts\python -m pytest
```

Each provider has its own module (`test_provider_opensubtitles.py`, `test_provider_opensubtitlescom.py`,
`test_provider_subscene.py`, `test_provider_subdivx.py`, `test_provider_addic7ed.py`,
`test_provider_subdl.py`, `test_provider_yts_subs.py`, `test_provider_local.py`,
`test_provider_filesystem.py`), plus
`test_provider_registry.py` for the contract shared by all of them and `test_httpclient.py` for the
HTTP helpers. Any module can be run on its own — either by node id,
`pytest resources/lib/tests/test_provider_local.py`, or with `python -m`, since each module still
has its `unittest.main()` block.

The translators follow the same layout and are entirely offline: `test_translator.py` covers the
behaviour every translator inherits, one module per implementation (`test_translator_bing.py`,
`test_translator_google.py`) covers the requests it builds and the
responses it parses, `test_subtitle_translator.py` covers the subtitle-format round trip and
`test_translators_registry.py` the lookups. `translator_testcase.py` holds the shared fake HTTP
client that replays canned responses.

Each translator module also has a `*OnlineTest` class that drives the real service, gated by the
same `UNIVERSAL_SUBS_NETWORK_TESTS` switch as the live provider tests: those fail when a service is
down, changes shape, or starts refusing this client, which is the point of keeping them.

The modules are part of the `resources.lib.tests` package, so run them with `-m` from the
repository root. Running `python resources/lib/tests/test_provider_local.py` directly fails
with `No module named 'resources'`, which only `-m` puts on the import path.

The live provider tests reach the real subtitle sites. They run by default; set
`UNIVERSAL_SUBS_NETWORK_TESTS=0` (or run `uv run poe offline`) to keep a run offline:

```powershell
$env:UNIVERSAL_SUBS_NETWORK_TESTS='0'
.venv\Scripts\python -m resources.lib.tests.test_provider_opensubtitles -v
```

RAR/7Z downloads need 7-Zip; set `SEVEN_ZIP_PATH` if it is not installed in a standard location.
`resources/lib/tests/old_test_providers.py` and `old_test_translators.py` are manual scratch
scripts, not tests: they run live searches with hardcoded media paths.

## Web settings page

Every setting the add-on declares can be edited from a browser instead of Kodi's settings dialog:

- **Add-ons -> Universal Subs -> Configure -> Web settings page -> Open the settings page in a
  browser**, or open **<http://127.0.0.1:39517/>** directly. The button runs `RunScript(<add-on id>)`
  through the `xbmc.python.script` extension provided by `open_settings.py`: a subtitle module has no
  plugin handler, so `RunPlugin` reaches nothing, and a bare file path runs without add-on context,
  which breaks its imports.
- The form is generated from `resources/settings.xml` on every request, so a setting added there
  appears without any page code. Secrets (API keys, passwords, the SubDivX session) are write-only:
  the page never renders a stored value, and leaving a field empty keeps it.
- Saving writes straight into Kodi's settings, and only the fields you changed are submitted. The
  next search uses the new values; no restart is needed.

Three settings control the page itself, under **Settings -> Web settings page**:

| Setting | Default | Purpose |
| --- | --- | --- |
| Settings page port | `39517` | TCP port; raise it when the port is taken (applies on Kodi's next start) |
| Settings page address | `127.0.0.1` | `0.0.0.0` listens on the LAN so other devices can reach it |
| Allowed client addresses | empty | IPs or ranges such as `192.168.1.50` or `192.168.1.0/24`, allowed when listening beyond loopback |

The page refuses a `Host` that is not an IP address or `localhost` (which defeats DNS rebinding) and
an `Origin` that is not its own, so another website cannot post to it. On a device without a
browser, the settings button shows the address to open elsewhere instead.

## SubDivX and Cloudflare

`subdivx.com` sits behind a Cloudflare managed challenge, so the add-on cannot reach it with a plain
HTTP client. The browser can, but the clearance cookie Cloudflare issues (`cf_clearance`) is marked
`HttpOnly`, so no script running in the page can read it. It has to be copied out by hand, into the
**SubDivX browser session** field of the [web settings page](#web-settings-page):

1. On `subdivx.com`, press `F12`, open **Application -> Cookies -> https://www.subdivx.com**, select
   `cf_clearance` and copy its **value**. The settings page attaches your browser's user agent
   automatically, which Cloudflare needs next to the clearance.
2. Paste that into **SubDivX browser session** and save. To capture the site login as well, copy a
   whole request instead: in **Network**, pick a request made after the page loaded (the first one
   can be the challenge itself), right-click it, **Copy -> Copy as cURL**, and paste that.
3. The session is stored when you save. It expires, so repeat when SubDivX stops returning results.
   Anyone holding it can act as that browser session, so do not share it.

If Kodi refuses the value, the form reports the reason per field: "no cookie header" usually means
the challenge request was copied instead of a later one, while "no cf_clearance" means the clearance
had not been issued yet. When SubDivX is blocked and no session is configured, Kodi shows a
notification pointing at the settings page.

## SubDL

SubDL is reached through its [search API](https://subdl.com/api-doc), which needs an API key.
Keys are free from the [account panel](https://subdl.com/panel/api) and allow 2,000 requests a
day. Paste one into **Settings -> Advanced -> SubDL API key**; while it is empty the provider
returns no results and the other providers are unaffected. The live test for this provider runs
only when `SUBDL_API_KEY` is set in the environment.

## OpenSubtitles.com

`OpenSubtitles.com` is a separate provider from `OpenSubtitles`, which scrapes the older
opensubtitles.org site. The .com service is API-only and needs three settings under
**Settings -> Advanced**:

- **OpenSubtitles.com API key** — free from the developer page of your OpenSubtitles.com account.
- **OpenSubtitles.com username** and **password** — the account *username*. The API only returns
  download links to authenticated users, and free accounts have a daily download quota, so the
  add-on logs in once per session and reuses the token.

Searching works with just the key; downloading needs the login. The live tests run only when
`OPENSUBTITLES_COM_API_KEY`, `OPENSUBTITLES_COM_USERNAME` and `OPENSUBTITLES_COM_PASSWORD` are set.
