# -*- coding: utf-8 -*-

"""Kodi service: receives the SubDivX browser session from the loopback receiver.

SubDivX is behind a Cloudflare managed challenge, so the add-on replays the browser's clearance
cookie. With Kodi running, http://127.0.0.1:39517/ shows the browser script that captures it; the
script posts the session here and this service stores it in the ``subdivx_session`` setting.
"""

import xbmc
import xbmcaddon

from resources.lib.providers.subdivxsourceprovider import parse_browser_session
from resources.lib.utils.session_capture import DEFAULT_PORT, start_session_capture_server

ADDON_ID = "service.subtitles.universalsubs"
SETTING_ID = "subdivx_session"
CAPTURE_URL = "http://127.0.0.1:%d/" % DEFAULT_PORT


def handle_session(blob: str) -> bool:
    session = parse_browser_session(blob)
    if not session or "cf_clearance=" not in session["cookie"]:
        xbmc.log("Universal Subs: rejected a SubDivX session without a Cloudflare clearance.", xbmc.LOGWARNING)
        return False
    xbmcaddon.Addon(ADDON_ID).setSetting(SETTING_ID, blob)
    xbmc.executebuiltin('Notification("Universal Subs","SubDivX browser session captured",5000)')
    xbmc.log("Universal Subs: stored the SubDivX browser session.", xbmc.LOGINFO)
    return True


def main() -> None:
    monitor = xbmc.Monitor()
    try:
        server = start_session_capture_server(handle_session)
    except OSError as error:
        xbmc.log("Universal Subs: SubDivX session capture unavailable (%s)." % error, xbmc.LOGWARNING)
        return
    xbmc.log("Universal Subs: open %s in a browser to capture a SubDivX session." % CAPTURE_URL, xbmc.LOGINFO)
    try:
        while not monitor.abortRequested() and not monitor.waitForAbort(5):
            pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
