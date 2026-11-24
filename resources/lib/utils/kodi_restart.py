# -*- coding: utf-8 -*-
"""Restart handshake between the installer and the running add-on service.

``scripts/addon_tasks.py`` cannot start Kodi in another Windows account's session: a process it
creates runs as the caller, not on the media centre's console. The service already runs there, as the
right user, so the installer asks *it* to restart Kodi by dropping a file in the add-on profile.

On Windows the service cannot simply call ``RestartApp``: it shuts Kodi down and never starts it
again, leaving the media centre dark. Instead the service starts a detached helper that waits for this
process to exit and then launches Kodi, and only once that helper is running does it ask Kodi to quit.
Other platforms keep ``RestartApp``.

The module is plain standard library so both sides can share one definition of the file name.
"""

import os
import subprocess
from pathlib import Path

#: File the installer creates; the service deletes it before restarting Kodi.
RESTART_REQUEST_FILE = "restart.request"

#: Keeps a console window from flashing when the helper runs.
CREATE_NO_WINDOW = 0x08000000


def restart_request_path(profile_dir: Path) -> Path:
    """The trigger file inside an add-on profile directory."""
    return Path(profile_dir).joinpath(RESTART_REQUEST_FILE)


def write_restart_request(profile_dir: Path) -> bool:
    """Ask the running service to restart Kodi; False when the profile is not writable."""
    path = restart_request_path(profile_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("restart requested by the installer\n", encoding="utf-8")
    except OSError:
        return False
    return True


def take_restart_request(profile_dir: Path) -> bool:
    """True when a restart was requested, consuming the trigger so it fires once."""
    path = restart_request_path(profile_dir)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        # Present but not removable: still honour it, or the request would be lost silently.
        return path.exists()
    return True


def relaunch_script(executable: Path, pid: int) -> str:
    """The PowerShell that waits for ``pid`` to exit and then starts Kodi again.

    Retrying matters: the helper may start Kodi while the old process is still releasing its
    databases, so a failed attempt is followed by another one instead of leaving Kodi down.
    """
    target = str(executable).replace("'", "''")
    return (
        "while (Get-Process -Id %(pid)d -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 500 }\n"
        "for ($attempt = 0; $attempt -lt 3; $attempt++) {\n"
        "  Start-Process -FilePath '%(target)s'\n"
        "  Start-Sleep -Seconds 15\n"
        "  if (Get-Process -Name kodi -ErrorAction SilentlyContinue) { break }\n"
        "}" % {"pid": pid, "target": target})


def schedule_relaunch(executable: Path, pid: int) -> bool:
    """Start the relaunch helper; False when it could not be started and Kodi must not quit."""
    if os.name != "nt" or not Path(executable).is_file():
        return False
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
             "-Command", relaunch_script(executable, pid)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW, close_fds=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return True
