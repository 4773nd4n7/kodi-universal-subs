# -*- coding: utf-8 -*-

"""Kodi service: receives the SubDivX browser session from the loopback receiver.

SubDivX is behind a Cloudflare managed challenge, so the add-on replays the browser's clearance
cookie. That cookie is HttpOnly, so it cannot be read from a page script: with Kodi running,
http://127.0.0.1:39517/ explains how to copy a request from the browser's developer tools, and this
service stores the parsed session in the ``subdivx_session`` setting.
"""

import xbmc
import xbmcaddon

from resources.lib.providers.subdivx_source_provider import (encode_browser_session,
                                                             explain_browser_session)
from resources.lib.utils.session_capture import DEFAULT_PORT, start_session_capture_server

ADDON_ID = "service.subtitles.universalsubs"
SETTING_ID = "subdivx_session"
CAPTURE_URL = "http://127.0.0.1:%d/" % DEFAULT_PORT


def handle_session(blob: str, browser_user_agent: str = "") -> str:
    """Store the pasted session; return an empty string on success, or the reason it was refused."""
    session, reason = explain_browser_session(blob, browser_user_agent)
    if not session:
        xbmc.log("Universal Subs: rejected a SubDivX session (%s)." % reason, xbmc.LOGWARNING)
        return reason
    if "cf_clearance=" not in session["cookie"]:
        reason = ("the pasted cookies have no cf_clearance; copy a request made after the Cloudflare "
                  "check passed")
        xbmc.log("Universal Subs: rejected a SubDivX session without a Cloudflare clearance.", xbmc.LOGWARNING)
        return reason
    xbmcaddon.Addon(ADDON_ID).setSetting(SETTING_ID, encode_browser_session(session))
    if "ua" not in session:
        xbmc.log("Universal Subs: stored a SubDivX session without a user agent; Cloudflare binds the "
                 "clearance to the browser's user agent, so copy the whole request (Copy as cURL) if "
                 "searches are still challenged.", xbmc.LOGWARNING)
    xbmc.executebuiltin('Notification("Universal Subs","SubDivX browser session captured",5000)')
    xbmc.log("Universal Subs: stored the SubDivX browser session.", xbmc.LOGINFO)
    return ""


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
