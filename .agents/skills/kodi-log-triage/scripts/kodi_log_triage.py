#!/usr/bin/env python3
"""Extract the last service.subtitles.universalsubs invocation from a Kodi log.

Kodi writes one *record* per log call, prefixed with a timestamp; a record's continuation lines
(tracebacks, YAML dumps) carry no timestamp of their own. This script rebuilds those records, groups
them into add-on invocations, and reports the last invocation only: its entries, its errors and its
warnings. An older error elsewhere in the log is deliberately not reported.

Usage:
    python kodi_log_triage.py                    # newest Kodi log on this machine
    python kodi_log_triage.py --kodi-user Kodi   # the log of another local account
    python kodi_log_triage.py --log D:\\archive\\kodi.log --all
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple

ADDON_ID = "service.subtitles.universalsubs"

#: One Kodi log record: ``2026-11-24 12:25:01.442 T:34628   error <general>: message``.
RECORD_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\s+T:(?P<thread>\d+)\s+"
    r"(?P<level>\w+)\s+<(?P<area>[^>]+)>:\s?(?P<body>.*)$")

#: Prefixes the add-on's own logger writes, including the abbreviated forms Kodi shortens names to.
ADDON_PREFIXES = ("UniversalSubs | ", "Universal Subs: ", "US.")

#: Records that open a plugin invocation, most specific first.
START_MARKERS = ("Command line args - plugin://" + ADDON_ID, "UniversalSubs | Settings:")

ERROR_LEVELS = ("error", "fatal")


class Record:
    """One log record, including the continuation lines that belong to it."""

    __slots__ = ("stamp", "thread", "level", "body", "lines")

    def __init__(self, stamp: str, thread: str, level: str, body: str, line: str):
        self.stamp = stamp
        self.thread = thread
        self.level = level
        self.body = body
        self.lines = [line]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def is_addon(self) -> bool:
        return self.body.startswith(ADDON_PREFIXES)

    @property
    def is_error(self) -> bool:
        return self.level in ERROR_LEVELS

    @property
    def is_warning(self) -> bool:
        return self.level == "warning"


def read_records(path: Path) -> List[Record]:
    records: List[Record] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\r\n")
            match = RECORD_RE.match(line)
            if match:
                records.append(Record(match.group("stamp"), match.group("thread"),
                                      match.group("level").lower(), match.group("body"), line))
            elif records:
                records[-1].lines.append(line)
    return records


def starts_invocation(record: Record) -> bool:
    return any(marker in record.body for marker in START_MARKERS)


def belongs_to_addon(record: Record) -> bool:
    """Whether a record is the add-on's own output or a Kodi core record about it."""
    if record.is_addon:
        return True
    if ADDON_ID in record.text:
        return True
    return record.is_error and ("EXCEPTION" in record.body or "Traceback" in record.text)


def invocation_ranges(records: Sequence[Record]) -> List[Tuple[int, int]]:
    starts = [index for index, record in enumerate(records) if starts_invocation(record)]
    if not starts:
        # Older builds may not log their argv: fall back to any record mentioning the add-on.
        starts = [index for index, record in enumerate(records) if ADDON_ID in record.text]
    starts = sorted(set(starts))
    ranges = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(records)
        ranges.append((start, end))
    return ranges


def user_log_paths(user: str) -> List[Path]:
    profiles = Path("C:/Users") if os.name == "nt" else Path("/home")
    profile = profiles / user.split("\\")[-1].strip()
    roots = [profile / "AppData" / "Roaming" / "Kodi"] if os.name == "nt" else [profile / ".kodi"]
    return [root / "kodi.log" for root in roots]


def candidate_logs() -> Iterator[Path]:
    """Every plausible Kodi log, caller's own first, then every local profile."""
    configured_home = os.environ.get("KODI_HOME")
    if configured_home:
        yield Path(configured_home).expanduser() / "kodi.log"
    appdata = os.environ.get("APPDATA")
    if appdata:
        yield Path(appdata) / "Kodi" / "kodi.log"
    yield Path.home() / ".kodi" / "kodi.log"
    profiles = Path("C:/Users") if os.name == "nt" else Path("/home")
    if profiles.is_dir():
        try:
            for profile in sorted(profiles.iterdir()):
                if profile.name in ("Public", "Default", "Default User", "All Users"):
                    continue
                if os.name == "nt":
                    yield profile / "AppData" / "Roaming" / "Kodi" / "kodi.log"
                else:
                    yield profile / ".kodi" / "kodi.log"
        except OSError:
            return


def find_log(explicit: Optional[Path], user: Optional[str]) -> Tuple[Optional[Path], bool]:
    """The log to read: explicit path, another account's, or the most recently written one."""
    if explicit:
        return (explicit, False) if explicit.is_file() else (None, False)
    if user:
        for path in user_log_paths(user):
            if path.is_file():
                return path, False
        return None, False
    existing = [path for path in dict.fromkeys(candidate_logs()) if path.is_file()]
    if not existing:
        return None, True
    return max(existing, key=lambda path: path.stat().st_mtime), True


def summarise(records: Sequence[Record], ranges: Sequence[Tuple[int, int]]) -> List[str]:
    lines = []
    for position, (start, end) in enumerate(ranges, start=1):
        window = records[start:end]
        errors = sum(1 for record in window if record.is_error)
        verdict = "ERROR" if errors else "ok"
        lines.append("  %2d. %s  %-5s  %d error(s), %d record(s)"
                     % (position, records[start].stamp, verdict, errors, len(window)))
    return lines


def excerpt(records: Sequence[Record], start: int, end: int, max_lines: int) -> Tuple[List[str], int]:
    """The add-on related records of one invocation, capped at ``max_lines``."""
    selected = [record for record in records[start:end] if belongs_to_addon(record)]
    lines: List[str] = []
    for record in selected:
        lines.extend(record.lines)
    omitted = 0
    if len(lines) > max_lines:
        omitted = len(lines) - max_lines
        lines = lines[:max_lines]
    return lines, omitted


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Review the last Universal Subs invocation in a Kodi log.")
    parser.add_argument("--log", type=Path, default=None, help="kodi.log to read")
    parser.add_argument("--kodi-user", default=None, metavar="NAME",
                        help="local account whose Kodi log to read (Kodi often runs as its own user)")
    parser.add_argument("--all", action="store_true", help="list every invocation with its verdict")
    parser.add_argument("--max-lines", type=int, default=500,
                        help="cap the printed excerpt (default: 500 lines)")
    arguments = parser.parse_args(list(argv) if argv is not None else None)

    log_path, discovered = find_log(arguments.log, arguments.kodi_user)
    if log_path is None:
        if arguments.log or arguments.kodi_user:
            print("No Kodi log at the requested location.", file=sys.stderr)
        else:
            print("No Kodi log found in any local profile.", file=sys.stderr)
        return 1

    records = read_records(log_path)
    ranges = invocation_ranges(records)
    print("Log:         %s%s" % (log_path, " (auto-discovered, most recently written)" if discovered else ""))
    print("Addon:       %s" % ADDON_ID)
    print("Log records: %d" % len(records))
    if not ranges:
        print("\nVerdict: no invocation of this add-on was found in this log.")
        if records:
            print("Last record: %s - the add-on has not run since this log started; reproduce the "
                  "action with Kodi running, then run this script again." % records[-1].stamp)
        return 2

    print("Invocations: %d" % len(ranges))
    if arguments.all:
        print("All invocations:")
        for line in summarise(records, ranges):
            print(line)

    start, end = ranges[-1]
    window = records[start:end]
    errors = [record for record in window if record.is_error and belongs_to_addon(record)]
    warnings = [record for record in window if record.is_warning and belongs_to_addon(record)]
    selected = [record for record in window if belongs_to_addon(record)]
    print("Selected:    invocation %d of %d, started %s (%d add-on record(s))"
          % (len(ranges), len(ranges), records[start].stamp, len(selected)))

    if errors:
        print("\nVerdict: ERROR in the last invocation - %d error record(s), %d warning(s)"
              % (len(errors), len(warnings)))
    else:
        print("\nVerdict: no error in the last invocation - 0 errors, %d warning(s)" % len(warnings))

    lines, omitted = excerpt(records, start, end, max(1, arguments.max_lines))
    print("\n--- entries for invocation %d ---" % len(ranges))
    print("\n".join(lines))
    if omitted:
        print("\n[... %d more line(s) omitted; raise --max-lines to see them]" % omitted)

    if errors:
        print("\n--- error detail ---")
        for record in errors:
            print(record.text)
    if warnings and not errors:
        print("\n--- warnings in this invocation ---")
        for record in warnings:
            print(record.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
