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

Each provider has its own module (`test_provider_opensubtitles.py`, `test_provider_subscene.py`,
`test_provider_subdivx.py`, `test_provider_addic7ed.py`, `test_provider_subdl.py`,
`test_provider_local.py`, `test_provider_filesystem.py`), plus `test_provider_registry.py` for the
contract shared by all of them and `test_httpclient.py` for the HTTP helpers. Any module can be run
on its own — either by node id, `pytest resources/lib/tests/test_provider_local.py`, or with
`python -m`, since each module still has its `unittest.main()` block.


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

## SubDivX and Cloudflare

`subdivx.com` sits behind a Cloudflare managed challenge, so the add-on cannot reach it with a
plain HTTP client. The browser can. With Kodi running, open **<http://127.0.0.1:39517/>** in a
browser on the same computer: that page shows the script, a Copy button, and the steps. Run the
script on `subdivx.com` and the add-on service stores the session automatically (it listens on
`127.0.0.1:39517`); if Kodi cannot be reached the script copies the blob for
**Settings -> Advanced -> SubDivX browser session**. When SubDivX is blocked and no session is
configured, Kodi also shows a notification with that address. The session expires: repeat when
SubDivX stops returning results.

## SubDL

SubDL is reached through its [search API](https://subdl.com/api-doc), which needs an API key.
Keys are free from the [account panel](https://subdl.com/panel/api) and allow 2,000 requests a
day. Paste one into **Settings -> Advanced -> SubDL API key**; while it is empty the provider
returns no results and the other providers are unaffected. The live test for this provider runs
only when `SUBDL_API_KEY` is set in the environment.
