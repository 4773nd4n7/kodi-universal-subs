# -*- coding: utf-8 -*-

"""The restart handshake the installer uses to make a running service restart Kodi."""

import tempfile
import unittest
from pathlib import Path

from resources.lib.utils import kodi_restart


class RestartRequestTest(unittest.TestCase):

    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.profile = Path(self._temporary_directory.name) / "userdata" / "addon_data" / "service.test"

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def test_a_request_is_written_into_the_profile_and_created_on_demand(self) -> None:
        self.assertFalse(self.profile.exists())
        self.assertTrue(kodi_restart.write_restart_request(self.profile))
        trigger = kodi_restart.restart_request_path(self.profile)
        self.assertTrue(trigger.is_file())
        self.assertEqual(trigger.name, kodi_restart.RESTART_REQUEST_FILE)

    def test_a_request_fires_once(self) -> None:
        kodi_restart.write_restart_request(self.profile)
        self.assertTrue(kodi_restart.take_restart_request(self.profile))
        self.assertFalse(kodi_restart.take_restart_request(self.profile))
        self.assertFalse(kodi_restart.restart_request_path(self.profile).exists())

    def test_no_request_means_no_restart(self) -> None:
        self.assertFalse(kodi_restart.take_restart_request(self.profile))

    def test_an_unwritable_profile_is_reported_instead_of_raising(self) -> None:
        blocker = Path(self._temporary_directory.name) / "file"
        blocker.write_text("not a directory", encoding="utf-8")
        self.assertFalse(kodi_restart.write_restart_request(blocker / "addon_data" / "service.test"))


class RelaunchTest(unittest.TestCase):

    def test_the_helper_waits_for_this_process_then_starts_kodi(self) -> None:
        script = kodi_restart.relaunch_script(Path(r"C:\Program Files\Kodi\kodi.exe"), 4242)
        self.assertIn("Get-Process -Id 4242", script)
        self.assertIn("Start-Process -FilePath 'C:\\Program Files\\Kodi\\kodi.exe'", script)
        # It retries, so a start that races the old process's shutdown does not leave Kodi down.
        self.assertIn("$attempt -lt 3", script)

    def test_a_quote_in_the_path_is_escaped(self) -> None:
        script = kodi_restart.relaunch_script(Path(r"C:\O'Brien\kodi.exe"), 1)
        self.assertIn("'C:\\O''Brien\\kodi.exe'", script)

    def test_a_missing_executable_is_not_scheduled(self) -> None:
        self.assertFalse(kodi_restart.schedule_relaunch(Path("no-such-kodi.exe"), 1))


if __name__ == "__main__":
    unittest.main()
