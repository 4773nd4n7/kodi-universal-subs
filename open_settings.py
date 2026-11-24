# -*- coding: utf-8 -*-

"""RunScript entry point for the button in Kodi's add-on settings.

``RunPlugin`` cannot reach this add-on: it is a subtitle module, not a plugin, so the button used to
do nothing. ``RunScript`` on this file works, and ``settings_page.open_page`` is the same code the
``open_web_settings`` module action uses.
"""

import os
import sys

# Kodi runs an add-on script with the add-on on sys.path; make that explicit so the import below
# works the same from a packaged install and from a checkout.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from resources.lib.utils.settings_page import open_page

    open_page()
