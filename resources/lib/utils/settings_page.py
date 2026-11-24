# -*- coding: utf-8 -*-
"""Opening the add-on's settings page from inside Kodi.

Shared by ``main.py`` (the subtitle-module action) and ``open_settings.py`` (the button in Kodi's
add-on settings), so both paths behave the same on a device without a browser.
"""

ADDON_ID = "service.subtitles.universalsubs"
PAGE_TITLE = "Universal Subs Settings"


def open_page() -> None:
    """Open the settings page in a browser, or show its address when there is none."""
    import xbmc
    import xbmcaddon
    import xbmcgui

    from resources.lib.utils import web_settings

    addon = xbmcaddon.Addon(ADDON_ID)
    try:
        port = int(addon.getSetting("web_settings_port") or web_settings.DEFAULT_PORT)
    except (TypeError, ValueError):
        port = web_settings.DEFAULT_PORT
    bind = addon.getSetting("web_settings_bind") or web_settings.DEFAULT_BIND
    url = web_settings.page_url(bind, port)
    try:
        import webbrowser
        if webbrowser.open(url):
            return
    except Exception:
        pass
    message = "Open this address in a browser:"
    if bind in ("", "127.0.0.1", "::1", "localhost"):
        message += "\n\nThis device has no browser. To reach the page from another device in the " \
                   "network, set web_settings_bind to 0.0.0.0 in the add-on settings and list that " \
                   "device under web_settings_allowed_ips."
    xbmcgui.Dialog().ok(PAGE_TITLE, message, url)
    xbmc.log("Universal Subs: settings page at %s" % url, xbmc.LOGINFO)
