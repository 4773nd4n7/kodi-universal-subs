---
name: commit-message
description: Write a commit message in this repository's chosen shape — a Conventional Commits subject line, a blank line, then the long past-tense paragraph that names every change.
whenToUse: Use when the user asks for a commit message, asks to commit staged changes, or asks whether an existing commit message matches this repository's conventions.
---

# Commit message

Messages have two layers:

1. a **Conventional Commits subject** — `type(scope): imperative summary` — so tooling and reviewers
   can classify the change at a glance;
2. a **descriptive body** in the repository's historical style: one past-tense paragraph that names
   every change with the class, file or behaviour it touched.

The body is not optional decoration. The subject can only name the dominant change; everything else
that moved belongs in the paragraph.

## Procedure

1. Read the diff. Prefer the staged one: `git diff --cached --stat`, then `git diff --cached`. If
   nothing is staged, read `git diff` and say the message describes unstaged changes. Never write a
   message from the branch name or from memory of the conversation.
2. Pick the `type` from the dominant change and the `scope` from the area it lives in (tables below).
   One scope only: when the commit spans areas, the dominant one goes in the subject and the rest are
   named in the body.
3. Write the subject, then the body, following "Shape" below. Return the finished message as plain
   text — subject, blank line, body — and stop there.

## Shape

```
feat(providers): add YTS Subs source provider

Added YtsSubsSourceProvider with its mapped languages, search and download
implementation, registered it in ProvidersRegistry, and added its entry to the
providers setting with strings for both languages. Added a provider test module
and extended EXPECTED_PROVIDER_NAMES so the registry contract covers it.
```

**Subject line**

- `type(scope): summary` — lowercase after the colon, imperative mood (`add`, not `added` or `adds`),
  no trailing period.
- At most 72 characters including the prefix.
- The prefix vocabulary and the scopes are the tables below; invent neither.
- Omit the scope only when the change is genuinely repo-wide.

**Body**

- One paragraph, past tense, capitalised first word, sentences separated by `. ` — exactly the style
  of the existing history (`Added`, `Updated`, `Fixed`, `Improved`, `Removed`, `Renamed`, `Moved`,
  `Replaced`, `Migrated`, `Bumped`, `Extracted`).
- Name the concrete thing: the class, module, provider, setting or behaviour. "Added
  SearchResultsCounter class to help with counting of response results, enforcing maximum results;
  updated providers to use it." beats "Refactored result handling."
- Order the sentences: new features and behaviour first, then fixes, then internal refactors, then
  docs, settings, strings and version bumps.
- Wrap at 72–100 columns. Do not reproduce the old single 1000-character line: it is a body now, and
  a wrapped paragraph reviews better.
- Length is otherwise unconstrained; the historical messages ran to 1152 characters, so be complete
  rather than terse.

**Footers** (optional, after a blank line): `Refs: #123`, `Closes: #45`. No sign-off, `Co-authored-by`
or other trailers.

## Types

| type | Use for |
| --- | --- |
| `feat` | a new provider, translator, subtitle format or setting; new user-visible behaviour |
| `fix` | a provider, parser, translator or cache that misbehaves |
| `refactor` | internal restructuring, renames, extraction — no behaviour change |
| `perf` | caches, request counts, parsing cost |
| `test` | test code only |
| `docs` | `README.md`, `AGENTS.md`, docstrings and comments |
| `build` | `pyproject.toml`, `uv.lock`, `scripts/addon_tasks.py` packaging rules |
| `ci` | `.github/workflows/` |
| `chore` | version bumps, housekeeping |
| `revert` | reverting an earlier commit |

## Scopes

| scope | Area |
| --- | --- |
| `providers` | `resources/lib/providers/` |
| `translation` | `resources/lib/translation/` |
| `formats` | `resources/lib/formats/` |
| `common` | `resources/lib/common/` — `Language`, `MappedLanguages`, `Settings` |
| `utils` | `resources/lib/utils/` |
| `tests` | `resources/lib/tests/` |
| `settings` | `resources/settings.xml` and the `strings.po` files |
| `addon` | `addon.xml`, packaging, install |
| `deps` | dependencies across `pyproject.toml`, `uv.lock` and `addon.xml` imports |
| `docs` | `README.md`, `AGENTS.md` |
| `ci` | `.github/workflows/` |

## Project-specific points

- **A new source provider is more than the provider.** The same commit usually updates
  `providers_registry.py`, the `providers` options in `resources/settings.xml`, both `strings.po`
  files, `test_provider_registry.py` (`EXPECTED_PROVIDER_NAMES`) and adds a `test_provider_*.py`.
  Name each of those in the body when the diff touches them.
- **A setting is more than `settings.xml`.** Name the strings and the `Settings` attribute too.
- **Do not mention a version bump** unless `pyproject.toml` actually changed.
- **Local artifacts** (`debug.log`, `*.zip`, `__pycache__`) are not changes to describe.

## Do not

- Invent a change that is not in the diff.
- Use a type or scope outside the tables above.
- Write an imperative subject that swallows the body — the body carries the detail.
- End the subject with a period, or capitalise it after the colon.
- Commit, amend, tag or push unless the user asked for that specific action.
