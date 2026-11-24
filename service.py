# -*- coding: utf-8 -*-

"""Kodi service: serves the add-on's settings page for editing from a browser.

The page is built from ``resources/settings.xml`` on every request, so a setting added to that file
appears without touching this service. It listens on the configured loopback address (optionally on
the LAN, restricted to an allowlist) and writes straight to Kodi's settings, which every search
re-reads on its next invocation.

It also performs the restart the installer asks for: that script cannot start Kodi in the media
centre's session, so it drops a trigger file in this add-on's profile and the service calls
``RestartApp`` as the user who owns the session.
"""

import os
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

from resources.lib.utils import kodi_restart, web_settings

ADDON_ID = "service.subtitles.universalsubs"
PAGE_TITLE = "Universal Subs Settings"

#: How often the service looks for the installer's restart trigger.
RESTART_POLL_SECONDS = 2


def _addon_path(addon) -> Path:
    return Path(xbmcvfs.translatePath(addon.getAddonInfo("path")))


def _settings_model(addon) -> list:
    addon_path = _addon_path(addon)
    language = ""
    try:
        language = xbmc.getLanguage(xbmc.ISO_639_1) or ""
    except Exception:
        pass
    strings = web_settings.pick_string_table(addon_path.joinpath("resources", "language"), language)
    return web_settings.parse_settings_model(addon_path.joinpath("resources", "settings.xml"), strings)


def _read_int(addon, setting_id: str, default: int) -> int:
    try:
        return int(addon.getSetting(setting_id) or default)
    except (TypeError, ValueError):
        return default


def _profile_path(addon) -> Path:
    return Path(xbmcvfs.translatePath(addon.getAddonInfo("profile")))


def _restart_kodi() -> None:
    """Restart Kodi the way this platform allows.

    On Windows ``RestartApp`` shuts Kodi down and never starts it again, leaving the media centre
    dark, so a detached helper — already running as this account and in this session — does the
    launch, and Kodi quits only once that helper exists. Elsewhere ``RestartApp`` is enough.
    """
    if os.name != "nt":
        xbmc.log("Universal Subs: restart requested by the installer, restarting Kodi.", xbmc.LOGINFO)
        xbmc.executebuiltin("RestartApp")
        return
    executable = Path(xbmcvfs.translatePath("special://xbmc/")) / "kodi.exe"
    if not kodi_restart.schedule_relaunch(executable, os.getpid()):
        xbmc.log("Universal Subs: restart requested but the relaunch helper could not be started "
                 "(%s); Kodi stays open. Restart it yourself." % executable, xbmc.LOGERROR)
        return
    xbmc.log("Universal Subs: restart requested by the installer; quitting so the helper starts %s"
             % executable, xbmc.LOGINFO)
    xbmc.executebuiltin("Quit")


def main() -> None:
    addon = xbmcaddon.Addon(ADDON_ID)
    model = _settings_model(addon)
    if not model:
        xbmc.log("Universal Subs: settings.xml could not be read, the settings page is unavailable.",
                 xbmc.LOGWARNING)
        return
    port = _read_int(addon, "web_settings_port", web_settings.DEFAULT_PORT)
    bind = addon.getSetting("web_settings_bind") or web_settings.DEFAULT_BIND
    allowed_ips = addon.getSetting("web_settings_allowed_ips") or ""
    try:
        server = web_settings.start_web_settings_server(
            bind=bind,
            port=port,
            allowed_ips=allowed_ips,
            model=model,
            get_values=lambda: {field.id: addon.getSetting(field.id) for field in model},
            set_value=addon.setSetting,
            title=PAGE_TITLE,
        )
    except OSError as error:
        xbmc.log("Universal Subs: settings page unavailable on %s:%d (%s); change web_settings_port "
                 "or web_settings_bind." % (bind, port, error), xbmc.LOGWARNING)
        return
    xbmc.log("Universal Subs: settings page at %s" % web_settings.page_url(bind, port), xbmc.LOGINFO)
    profile_path = _profile_path(addon)
    monitor = xbmc.Monitor()
    try:
        while not monitor.abortRequested() and not monitor.waitForAbort(RESTART_POLL_SECONDS):
            # The installer cannot start Kodi in this account's session, so it drops a file here and
            # this service performs the restart as the user that owns the session.
            if kodi_restart.take_restart_request(profile_path):
                _restart_kodi()
                return
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
