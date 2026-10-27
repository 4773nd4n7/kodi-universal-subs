# Universal Subs Kodi Plugin

> One ring to rule them all, one ring to find them,<br/>
> One ring to bring them all, and in the darkness bind them;<br/>
> In the Land of Mordor where the shadows lie.

## Requirements

This is a Kodi add-on, so **Kodi provides the interpreter and the third-party libraries**; nothing
is bundled in the repository. The versions that matter:

| Kodi | `xbmc.python` | Python |
|---|---|---|
| 20 Nexus | 3.0.1 | 3.11.2 |
| 21 Omega | 3.0.1 | 3.11.7 |

[addon.xml](addon.xml) declares `xbmc.python 3.0.1`, so the minimum is **Kodi 20 Nexus** and the
minimum interpreter is **Python 3.11**; [.python-version](.python-version) pins that for local
development. Kodi 19 Matrix (Python 3.8) is not supported.

Runtime libraries are declared in addon.xml as `script.module.*` imports (beautifulsoup4,
cachetools, chardet, html5lib, PyYAML, Unidecode, typing_extensions) plus the binary add-ons
`vfs.libarchive` and `vfs.rar`. Kodi ignores `requirements.txt`; that file mirrors the same list so
the code can run, and be tested, outside Kodi. Keep the two in sync when adding a dependency.

## Development

Create a virtual environment and install the dependencies. With [uv](https://docs.astral.sh/uv/),
which honours `.python-version`:

```powershell
uv venv
uv pip install -r requirements.txt
```

With plain Python (install Python 3.11 first if needed):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

Run the test suite from the repository root, so that `resources` is importable. It uses
`unittest`:

```powershell
# everything
.venv\Scripts\python -m unittest discover -s resources/lib/tests -t . -v

# one module (hermetic: no network)
.venv\Scripts\python -m resources.lib.tests.test_provider_local -v
```

Each provider has its own module (`test_provider_opensubtitles.py`, `test_provider_subscene.py`,
`test_provider_subdivx.py`, `test_provider_addic7ed.py`, `test_provider_local.py`,
`test_provider_filesystem.py`), plus `test_provider_registry.py` for the contract shared by all of
them and `test_httpclient.py` for the HTTP helpers. Any module can be run on its own with `-m`,
which is handy while iterating.

The modules are part of the `resources.lib.tests` package, so run them with `-m` from the
repository root. Running `python resources/lib/tests/test_provider_local.py` directly fails
with `No module named 'resources'`, which only `-m` puts on the import path.

The live provider tests reach the real subtitle sites and are skipped unless enabled:

```powershell
$env:UNIVERSAL_SUBS_NETWORK_TESTS='1'
.venv\Scripts\python -m resources.lib.tests.test_provider_opensubtitles -v
```

RAR/7Z downloads need 7-Zip; set `SEVEN_ZIP_PATH` if it is not installed in a standard location.
`resources/lib/tests/old_test_providers.py` and `old_test_translators.py` are manual scratch
scripts, not tests: they run live searches with hardcoded media paths.

## SubDivX and Cloudflare

`subdivx.com` sits behind a Cloudflare managed challenge, so the add-on cannot reach it with a
plain HTTP client. The browser can. With Kodi running, open **http://127.0.0.1:39517/** in a
browser on the same computer: that page shows the script, a Copy button, and the steps. Run the
script on `subdivx.com` and the add-on service stores the session automatically (it listens on
`127.0.0.1:39517`); if Kodi cannot be reached the script copies the blob for
**Settings -> Advanced -> SubDivX browser session**. When SubDivX is blocked and no session is
configured, Kodi also shows a notification with that address. The session expires: repeat when
SubDivX stops returning results.
