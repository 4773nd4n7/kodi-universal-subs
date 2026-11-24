---
name: kodi-log-triage
description: Read the Kodi log, find the most recent Universal Subs invocation, say whether it failed, and troubleshoot only that failure.
whenToUse: Use when the user reports a Kodi error, pastes kodi.log output, asks what the add-on logged, or asks to debug why a search or download failed.
---

# Kodi log triage

The Kodi log is append-only and noisy: the same traceback repeats across runs, older failures sit
above newer successes, and Kodi interleaves other add-ons. This skill reads the log through a script
that rebuilds Kodi's records (timestamp + continuation lines), groups them into add-on invocations,
and reports **only the last invocation**.

## Run it

```powershell
$py = if (Test-Path .venv\Scripts\python.exe) { ".venv\Scripts\python.exe" } else { "python" }
& $py .agents\skills\kodi-log-triage\scripts\kodi_log_triage.py
```

The script finds the log itself: `--log PATH` when given, else `--kodi-user NAME`, else the most
recently written `kodi.log` across the local profiles — Kodi usually runs as its own account, so the
caller's `%APPDATA%\Kodi\kodi.log` is often the wrong file. It reads that single log and no other:
when the log holds no invocation, it says so and prints the log's last record time, so a stale log is
obvious instead of silently reading a different file.

| Option | Use |
| --- | --- |
| `--log PATH` | a specific `kodi.log`, e.g. an archive the user pasted |
| `--kodi-user NAME` | the log of another local account (`C:\Users\NAME\AppData\Roaming\Kodi\kodi.log`) |
| `--all` | list every invocation with its verdict, for context |
| `--max-lines N` | cap the printed excerpt (default 500) |

## Read the verdict

- **`Verdict: no error in the last invocation`** — say exactly that. Report any warnings it lists,
  and do not go hunting for an older error: the user asked about the latest run, and a previous
  traceback in the log is not evidence about this one.
- **`Verdict: ERROR in the last invocation`** — the `--- error detail ---` block is the failure to
  explain. Ignore errors belonging to other invocations, even if they look similar.
- **`no invocation ... was found`** — the add-on has not run since Kodi started this log (the script
  prints the log's last record time, so a stale log is visible). Ask the user to reproduce the action
  with Kodi running, then run this script again.

## Troubleshoot the failure

1. **Start from the last add-on frame, not the last frame.** Tracebacks end inside
   `C:\Program Files\Kodi\system\python\...`; the frame that matters is the deepest one under
   `...\addons\service.subtitles.universalsubs\resources\lib\`.
2. **Map the path to the repository.** An installed path
   `...\addons\service.subtitles.universalsubs\resources\lib\utils\http_client.py` is
   `resources/lib/utils/http_client.py` here.
3. **Check whether the source actually matches.** Log line numbers come from the *installed* copy,
   which may predate the working tree (`git status`, `git log --oneline -3`). Verify the reported
   line contains what the traceback says before blaming the current source.
4. **Read the context above the traceback** — the script prints it: request URL, provider, parsed
   arguments, settings dump. That is usually where the cause is visible.
5. **Name the failing call and the bad data.** For example `JSONDecodeError: Expecting value: line 1
   column 1 (char 0)` raised from `get_data_as_json` means the response body was HTML, not JSON —
   typically a Cloudflare challenge or a login page, not a parser bug.
6. **Separate code defects from environment.** A blocked site, a missing credential, an expired
   session or a Kodi build with an unexpected Python version is not a code fix; say which it is.

## Report

Present, in this order:

1. the invocation timestamp and the verdict line;
2. the extracted entries verbatim (trim to the relevant tail if `--max-lines` cut them);
3. the diagnosis, citing `file:line` in repository terms;
4. the smallest fix, or the environment cause with what the user must do.

## Do not

- Report an error when the verdict says the last invocation was clean.
- Mix in failures from earlier invocations.
- Quote a log line as proof without reading the code it points at.
- Edit, truncate or delete the Kodi log; Kodi holds it open, and it is the user's evidence.
- Assume the installed build equals the working tree — check first.
