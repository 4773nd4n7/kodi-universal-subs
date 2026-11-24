# -*- coding: utf-8 -*-

import sys

ACTION_OPEN_WEB_SETTINGS = "open_web_settings"
ADDON_ID = "service.subtitles.universalsubs"


def open_web_settings() -> None:
    """Open the add-on's settings page in a browser, or show its address when there is none."""
    from resources.lib.utils.settings_page import open_page

    open_page()


def main() -> None:
    if any(ACTION_OPEN_WEB_SETTINGS in argument for argument in sys.argv[1:]):
        open_web_settings()
        return
    from resources.lib.subtitle_addon import SubtitleAddon

    SubtitleAddon().main(sys.argv)


if __name__ == "__main__":
    main()
