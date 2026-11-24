# AGENTS.md

Working notes for agents editing this repository. `README.md` is the user-facing manual; this file
records the rules that are easy to break and the files that must change together.

## What this is

A Kodi subtitle add-on (`service.subtitles.universalsubs`) for **Kodi 20 Nexus / 21 Omega**, running
on **Python 3.11 only** (`requires-python = ">=3.11,<3.12"`). Kodi embeds the interpreter and supplies
the third-party libraries through `script.module.*` imports, so the add-on installs no packages at
runtime: `[project] dependencies` in `pyproject.toml` only exist so the same code can be imported and
tested outside Kodi.

## Layout

| Path | Contents |
| --- | --- |
| `main.py` | Kodi subtitle-module entry point; constructs `SubtitleAddon` and calls `main()` |
| `open_settings.py` | `RunScript` entry point for the settings-dialog button: a subtitle module cannot receive `RunPlugin`, so the button runs this file |
| `service.py` | Kodi service; serves the web settings page that edits every setting from a browser |
| `resources/lib/subtitle_addon.py` | `SubtitleAddon`: argument parsing, Kodi UI/plugin calls, search and download orchestration |
| `resources/lib/providers/` | `Provider` → `SourceProvider` (remote sites, local files) and `DecoratorProvider` (translation, cleanup); `providers_registry.py` composes the chain from settings |
| `resources/lib/translation/` | `Translator` implementations (Google, Bing) and `translators_registry.py` |
| `resources/lib/formats/` | Subtitle format parsers/renderers: SubRip, ASS/SSA, WebVTT, MicroDVD, MPlayer2, SBV, Google Play |
| `resources/lib/common/` | `Language`, `MappedLanguages`, `Settings` |
| `resources/lib/utils/` | HTTP client, caches, logging, YAML/JSON, compression, media info, subprocess, web settings page, restart handshake |
| `resources/lib/tests/` | `unittest`-style cases discovered by pytest; one module per provider/translator |
| `resources/settings.xml`, `resources/language/` | Kodi settings UI and its translations |
| `scripts/addon_tasks.py` | the single definition of "addon content" used by `package` and `install` |

## Commands

`uv` builds `.venv` from `pyproject.toml` + `uv.lock`; `uv run` puts it on `PATH`, so nothing needs
activating.

| Goal | Command | Fallback without `uv` |
| --- | --- | --- |
| every test, live provider sites included | `uv run poe test` | `.venv\Scripts\pytest` |
| tests without touching the network | `uv run poe offline` | `$env:UNIVERSAL_SUBS_NETWORK_TESTS='0'; .venv\Scripts\pytest` |
| lint | `uv run poe lint` | `.venv\Scripts\ruff check .` |
| add-on zip | `uv run poe package` | `.venv\Scripts\python scripts/addon_tasks.py package` |
| copy into Kodi | `uv run poe install` — installs, then asks the running service to restart Kodi (a failure exits non-zero); `-- --kodi-user <name>` for another account, `-- --no-restart` to skip | `.venv\Scripts\python scripts/addon_tasks.py install` |

`ruff check .` passes on `main` and is the enforced gate — keep it that way. **`ruff format` is not
the project's formatter**: 73 files under `resources/lib` would be rewritten by it, and on ruff 0.17
`ruff format --check .` at the repository root panics outright. Never run formatting across the tree
as part of an unrelated fix.

Code style in practice: 4-space indentation, 120-column lines (`[tool.ruff] line-length`), CRLF line
endings, and most modules open with `# -*- coding: utf-8 -*-`. Ruff only enforces `E4`, `E7`, `E9`
and `F`, so quote style and import order are conventions, not gates.

## Tests

The suite is pytest running `unittest` cases, configured in `[tool.pytest.ini_options]`.
`testpaths` and `pythonpath` mean it must run **from the repository root**; run a single module with
`-m` (`python -m resources.lib.tests.test_provider_local`) rather than by path, or `resources` is not
importable.

Two kinds of test, both under `resources/lib/tests/`:

- **Offline** — `test_provider_local`, `test_provider_filesystem`, `test_provider_registry`,
  `test_httpclient`, the subtitle/cleanup/line-break modules, and every translator module. These are
  the ones to run while iterating.
- **Live** — `test_provider_opensubtitles`, `_opensubtitlescom`, `_subscene`, `_subdivx`,
  `_addic7ed`, `_subdl`, `_yts_subs` and the `*OnlineTest` translator classes reach the real sites
  and run **by default**. They fail when a site is down, changes shape, or starts blocking the
  client; that is intended. `UNIVERSAL_SUBS_NETWORK_TESTS=0` skips them.

RAR/7Z downloads need 7-Zip: set `SEVEN_ZIP_PATH` when it is not in a well-known location. ZIP
downloads always work through the standard library.

`old_test_translators.py` is a scratch script with hardcoded media paths, not a test. Do not extend
it.

## Hard rules

1. **Python 3.11 only.** No 3.12+ syntax (no `type` statements, no PEP 695 generics). `typing_extensions`
   is available for backports Kodi's runtime lacks.
2. **Never write a real version into `addon.xml`.** It keeps `version="@VERSION@"`; `pyproject.toml`
   holds the single source of truth, and `scripts/addon_tasks.py` substitutes the number into the
   packaged archive and the installed copy only. A checkout's `addon.xml` is therefore not loadable
   by Kodi as-is — install with `poe install` instead of copying the folder.
3. **Keep the dependency list in two places in step.** A new runtime import needs a
   `script.module.*` `<import>` in `addon.xml` (what Kodi provides) *and* the matching entry in
   `[project] dependencies` (what tests use). Adding only one of the two breaks either Kodi or the
   suite.
4. **`resources/lib` must stay importable outside Kodi.** Only `main.py`, `service.py`,
   `resources/lib/subtitle_addon.py`, `utils/compression.py` and `utils/logging.py` may import
   `xbmc*`, and only inside the code path that runs under Kodi (the latter two import lazily, inside
   a function, so tests can run without Kodi). Everywhere else, take what you need from `Settings` or
   `utils/` instead of calling `xbmcaddon` directly.
5. **A setting is never just `settings.xml`.** A new setting needs its `<setting>` entry, a `label`
   and `help` string id, and matching `msgctxt` entries in `resources/language/resource.language.en_gb/strings.po`
   and `resources/language/resource.language.es_ar/strings.po`, plus the attribute on `Settings` and
   the code that reads it. Follow the existing numbering scheme rather than inventing ids. The web
   settings page renders every setting from that file, so a new field appears there without any page
   change — keep its type within `string`, `boolean`, `integer`, `path` or `list[string]`. A
   credential is declared, never inferred: give its `<control>` a `<hidden>true</hidden>`, which Kodi
   masks in its own dialog and the page treats as write-only (`tests/test_web_settings.py` fails when
   an `api_key`/`password`/`token`/`session` setting lacks it).
6. **New add-on content vs development scaffolding.** `scripts/addon_tasks.py` decides what ships.
   A new top-level development file belongs in `EXCLUDED_ROOT_NAMES`; a new development directory
   belongs in `EXCLUDED_DIRECTORIES`. Otherwise it silently lands inside the release zip and in
   Kodi's `addons/` folder.
7. **Do not commit generated output.** `debug.log`, `*.zip`, `__pycache__`, caches and `resources/examples`
   are local artifacts.

## Adding a provider

A source provider touches all of these — a change that updates only some of them is incomplete:

1. `resources/lib/providers/<name>_source_provider.py` extending `SourceProvider`: implement the
   `name` and `short_name` properties (`id` derives from `name`), declare the class-level
   `MappedLanguages` for the languages the site serves, and implement `_fetch_search_results()` and
   `_get()`. Let the base class handle caching, scoring, language mapping, `release_info`
   normalization, compressed downloads and `is_sync`.
2. Register it in `providers_registry.py` — the `ProvidersRegistry.__init__` list.
3. Add its name to the `providers` options in `resources/settings.xml` (and the default when it
   should be on out of the box).
4. Add/refresh its strings in both `strings.po` files when the setting carries a new label or help.
5. Add `resources/lib/tests/test_provider_<name>.py`, extending `OnlineSourceProviderTestCase` and
   declaring only the movie/show it is known to index. Add the provider name to
   `EXPECTED_PROVIDER_NAMES` in `test_provider_registry.py`.
6. Mention it in `README.md` if user-facing behaviour changes.

Providers must tolerate a site that is down: `search()` records `last_error` and re-raises, and
unknown provider names from a stale Kodi setting are skipped with a warning rather than crashing.

## Releases

1. Bump `[project] version` in `pyproject.toml`.
2. Add a `<news>` entry for the new version at the top of the block in `addon.xml` (keep the older
   entries, use `vX.Y.Z (YYYY/MM/DD)` and `- ` bullets).
3. Tag `vX.Y.Z` and push the tag. `.github/workflows/create-tag-release.yml` refuses to publish when
   the tag and the `pyproject.toml` version disagree, then builds and attaches the zip.

## Commits

Two layers: a Conventional Commits subject (`type(scope): imperative summary`, ≤72 characters, no
trailing period), a blank line, then one past-tense paragraph naming every change and the classes or
files it touched. The body is where the detail lives — do not let the subject swallow it. Types and
scopes, plus the exact procedure, are in `.agents/skills/commit-message/SKILL.md`; invoke that skill
rather than improvising a message.

The 12 substantive commits before this convention are prefix-free single lines. Leave them alone;
they are history, not a template to revert to.
