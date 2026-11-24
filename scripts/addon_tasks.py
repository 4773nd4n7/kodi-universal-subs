# -*- coding: utf-8 -*-

"""Build or install the addon the way Kodi sees it.

``package`` writes ``service.subtitles.universalsubs.zip`` next to the sources. ``install`` copies
the same file set into ``<kodi-home>/addons/service.subtitles.universalsubs``, which is what Kodi
reads at startup.

The Kodi home defaults to ``%APPDATA%\\Kodi`` on Windows and ``~/.kodi`` elsewhere; override it
with ``--kodi-home`` or the ``KODI_HOME`` environment variable (portable installs, media boxes).

When Kodi runs as its own local account — the usual HTPC arrangement, where the media centre logs in
as a dedicated user — the userdata lives in that account's profile, not the caller's ``%APPDATA%``.
``--kodi-user <name>`` targets it by account name; it and ``--kodi-home`` are mutually exclusive.

Both commands share one definition of "addon content", so a file that is left out of the zip is
also left out of the install and the two never drift.
"""

import argparse
import os
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Iterator, Tuple
from xml.etree import ElementTree

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

#: Development scaffolding, not addon content.
EXCLUDED_DIRECTORIES = {
    ".agents",
    ".git",
    ".github",
    ".dsh",
    ".dsh-worktrees",
    ".nox",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "examples",
    "scripts",
}

#: A bare name here is matched at the addon root only: development files Kodi never reads.
EXCLUDED_ROOT_NAMES = {
    ".editorconfig",
    ".gitignore",
    "AGENTS.md",
    ".python-version",
    "noxfile.py",
    "pyproject.toml",
    "uv.lock",
}

EXCLUDED_SUFFIXES = {".pyc", ".pyo"}

ADDON_XML = "addon.xml"

#: addon.xml carries this instead of a number; only the packaged/installed copy gets the real one.
VERSION_PLACEHOLDER = "@VERSION@"


def read_addon_id(root: Path = REPOSITORY_ROOT) -> str:
    """The addon id from addon.xml; it is also the folder name Kodi expects."""
    tree = ElementTree.parse(str(root / ADDON_XML))
    addon_id = tree.getroot().get("id")
    if not addon_id:
        raise SystemExit("%s has no id attribute" % (root / ADDON_XML))
    return addon_id


def project_version(root: Path = REPOSITORY_ROOT) -> str:
    """The version from pyproject.toml, the one place it is written down."""
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not version:
        raise SystemExit("pyproject.toml has no [project] version to substitute into addon.xml")
    return version


def rendered_addon_xml(root: Path = REPOSITORY_ROOT) -> str:
    """addon.xml with the version placeholder resolved, as Kodi has to see it."""
    text = (root / ADDON_XML).read_text(encoding="utf-8")
    if VERSION_PLACEHOLDER not in text:
        print(
            "[addon] warning: %s has no %s placeholder; shipping its literal version"
            % (ADDON_XML, VERSION_PLACEHOLDER),
            file=sys.stderr,
        )
        return text
    return text.replace(VERSION_PLACEHOLDER, project_version(root))


def addon_files(root: Path = REPOSITORY_ROOT) -> Iterator[Tuple[Path, Path]]:
    """Yield ``(absolute path, path relative to the addon root)`` for every addon file."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        if any(part.endswith(".egg-info") for part in relative.parts):
            continue
        if relative.parts and relative.parts[0] in EXCLUDED_ROOT_NAMES:
            continue
        if relative.parent == Path(".") and path.suffix.lower() == ".zip":
            # The archive this very command produces; never ship it inside the addon.
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path, relative


def default_kodi_home() -> Path:
    configured = os.environ.get("KODI_HOME")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        return Path(appdata).expanduser() / "Kodi" if appdata else Path.home() / "AppData" / "Roaming" / "Kodi"
    return Path.home() / ".kodi"


def users_root() -> Path:
    """The directory holding the local accounts' profile directories."""
    return Path("C:/Users") if os.name == "nt" else Path("/home")


def kodi_home_for_user(user: str) -> Path:
    """The Kodi userdata directory of another local account.

    Kodi commonly runs as a dedicated account, so its add-ons belong in that account's profile
    rather than in the caller's ``%APPDATA%``. A ``DOMAIN\\name`` or ``.\\name`` form is accepted, and
    the profile has to exist: a mistyped name would otherwise install into a directory nobody reads.
    """
    account = user.split("\\")[-1].strip()
    profile = users_root() / account
    if not account or not profile.is_dir():
        raise SystemExit(
            "[addon] no local profile for user '%s' (looked for %s)" % (user, profile))
    if os.name == "nt":
        return profile / "AppData" / "Roaming" / "Kodi"
    return profile / ".kodi"


def package(output: Path) -> int:
    files = list(addon_files())
    addon_xml = rendered_addon_xml()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(output), "w", zipfile.ZIP_DEFLATED) as archive:
        for path, relative in files:
            arcname = str(Path(REPOSITORY_ROOT.name) / relative)
            if relative == Path(ADDON_XML):
                # The manifest is the one file whose bytes differ from the working tree. Reuse the
                # file's own timestamp so two builds of the same tree are byte identical.
                info = zipfile.ZipInfo.from_file(str(path), arcname)
                archive.writestr(info, addon_xml)
            else:
                archive.write(str(path), arcname)
    size = output.stat().st_size
    print(
        "[addon] packaged %d files into %s (%.1f kB, version %s)"
        % (len(files), output, size / 1024, project_version())
    )
    return 0


def ensure_outside_repository(kodi_home: Path) -> None:
    """Refuse a Kodi home inside the repository.

    ``addon_files`` scans the whole checkout, so a target inside it would be collected as add-on
    content and then deleted by ``install`` while it is being copied.
    """
    try:
        kodi_home.resolve().relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return
    raise SystemExit(
        "[addon] refusing to install into %s: it is inside the repository, so the file scan would "
        "copy the installed add-on back into itself" % kodi_home)


def install(kodi_home: Path) -> int:
    ensure_outside_repository(kodi_home)
    addon_id = read_addon_id()
    target = kodi_home / "addons" / addon_id
    files = list(addon_files())
    addon_xml = rendered_addon_xml()

    try:
        if target.exists():
            shutil.rmtree(str(target))
        for path, relative in files:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if relative == Path(ADDON_XML):
                destination.write_text(addon_xml, encoding="utf-8")
            else:
                shutil.copy2(str(path), str(destination))
    except PermissionError as error:
        raise SystemExit(
            "[addon] cannot write to %s: %s\n"
            "Another account owns that userdata directory; run an elevated shell, or install with "
            "--kodi-home." % (target, error))

    print(
        "[addon] installed %d files into %s (version %s)"
        % (len(files), target, project_version())
    )
    print("[addon] restart Kodi so it picks up the new code")
    return 0


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or install the Universal Subs Kodi addon.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    package_parser = subparsers.add_parser("package", help="write the addon zip")
    package_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="zip to write (default: <addon id>.zip next to the sources)",
    )

    install_parser = subparsers.add_parser("install", help="copy the addon into Kodi")
    target_group = install_parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--kodi-home",
        type=Path,
        default=None,
        help="Kodi userdata directory (default: $KODI_HOME, %%APPDATA%%\\Kodi or ~/.kodi)",
    )
    target_group.add_argument(
        "--kodi-user",
        default=None,
        metavar="NAME",
        help="local account whose Kodi userdata to install into, as Kodi usually runs as its own "
             "user (cannot be combined with --kodi-home)",
    )

    # poe appends a literal '--' ahead of extra task arguments; argparse would stop there.
    argv = [item for item in (argv if argv is not None else sys.argv[1:]) if item != "--"]
    arguments = parser.parse_args(argv)
    if arguments.command == "package":
        output = arguments.output or (REPOSITORY_ROOT / (read_addon_id() + ".zip"))
        return package(output.resolve())
    if arguments.kodi_user:
        kodi_home = kodi_home_for_user(arguments.kodi_user)
    else:
        kodi_home = arguments.kodi_home or default_kodi_home()
    return install(kodi_home.expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
