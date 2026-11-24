# -*- coding: utf-8 -*-

"""Offline tests for the browser settings page: model, form, validation and request guards."""

import json
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from resources.lib.utils import web_settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_XML = REPOSITORY_ROOT / "resources" / "settings.xml"
ADDON_XML = REPOSITORY_ROOT / "addon.xml"
ENGLISH_PO = REPOSITORY_ROOT / "resources" / "language" / "resource.language.en_gb" / "strings.po"
CLEARANCE_VALUE = ("ChXpYt3ToRDKMxVv1yLtQ3aX1jqvfpG6Poyc24LcvarpvRu0Vqup7Z7eGnwPMhf__eweyL4IRmNkm8W"
                   "fnpD9hERuMBjB_dpVCM1D8lKFKBK1Zah7RLMOoDQ")


def model():
    strings = web_settings.load_string_table(ENGLISH_PO)
    return web_settings.parse_settings_model(SETTINGS_XML, strings)


def field(field_id):
    for candidate in model():
        if candidate.id == field_id:
            return candidate
    raise AssertionError("setting %s is missing from settings.xml" % field_id)


class SettingsModelTest(unittest.TestCase):

    def test_every_declared_setting_is_a_field(self) -> None:
        fields = model()
        self.assertGreaterEqual(len(fields), 20)
        self.assertIn("providers", [candidate.id for candidate in fields])
        self.assertIn("web_settings_port", [candidate.id for candidate in fields])

    def test_action_buttons_are_not_fields(self) -> None:
        # Kodi renders action entries as buttons; they hold no value and must not become inputs.
        fields = model()
        self.assertTrue(all(candidate.id for candidate in fields))
        self.assertNotIn("action", [candidate.type for candidate in fields])
        self.assertNotIn("open_web_settings", [candidate.id for candidate in fields])

    def test_the_action_button_has_a_control_kodi_can_render(self) -> None:
        # Format version 1 gives an action setting no control by itself: without <control> the row
        # never appears in Kodi's dialog (the legacy action=/option= attributes are ignored).
        from xml.etree import ElementTree
        actions = [element for element in ElementTree.parse(SETTINGS_XML).iter("setting")
                   if (element.get("type") or "") == "action"]
        self.assertTrue(actions, "expected at least one action setting")
        for action in actions:
            control = action.find("control")
            self.assertIsNotNone(control, "an action setting needs a <control> to render")
            self.assertEqual(control.get("type"), "button")
            self.assertEqual(control.get("format"), "action")
            data = action.findtext("data") or control.findtext("data")
            self.assertTrue(data, "the button needs RunPlugin/RunScript data")

    def test_the_button_runs_a_script_that_exists(self) -> None:
        # RunPlugin cannot reach a subtitle module, and RunScript on a bare file path runs without
        # addon context ("No module named 'resources.lib'"), so the button must run the addon id and
        # the addon must declare a script extension. Either half missing fails silently in Kodi.
        from xml.etree import ElementTree
        action = next(element for element in ElementTree.parse(SETTINGS_XML).iter("setting")
                      if (element.get("type") or "") == "action")
        self.assertEqual(action.findtext("data"), "RunScript($ID)")
        libraries = [extension.get("library") for extension in ElementTree.parse(ADDON_XML).iter("extension")
                     if extension.get("point") == "xbmc.python.script"]
        self.assertTrue(libraries, "RunScript($ID) needs an xbmc.python.script extension in addon.xml")
        for library in libraries:
            self.assertTrue((REPOSITORY_ROOT / library).is_file(),
                            "%s is declared as the script library but does not exist" % library)

    def test_types_labels_and_constraints_are_parsed(self) -> None:
        port = field("web_settings_port")
        self.assertEqual(port.type, "integer")
        self.assertEqual((port.minimum, port.maximum), (1024, 65535))
        providers = field("providers")
        self.assertEqual(providers.type, "list[string]")
        self.assertIn("Subscene", [value for value, _ in providers.options])
        self.assertEqual(providers.label, "Subtitle providers to use")  # resolved through strings.po

    def test_secrets_are_declared_in_the_settings_file(self) -> None:
        # <control><hidden>true</hidden></control> is what Kodi masks; the page reads the same marker.
        self.assertTrue(field("subdivx_session").is_secret)
        self.assertTrue(field("subdl_api_key").is_secret)
        self.assertTrue(field("opensubtitles_com_api_key").is_secret)
        self.assertTrue(field("opensubtitles_com_password").is_secret)
        self.assertFalse(field("providers").is_secret)
        self.assertFalse(field("opensubtitles_com_username").is_secret)

    def test_every_credential_looking_setting_is_declared_a_secret(self) -> None:
        # Guard against a new key being added without <hidden>: the page would render its value.
        fragments = ("api_key", "apikey", "password", "session", "token", "secret")
        for candidate in model():
            if any(fragment in candidate.id for fragment in fragments):
                self.assertTrue(candidate.hidden,
                                "%s looks like a credential but its control is not <hidden>"
                                % candidate.id)


class RenderTest(unittest.TestCase):

    def test_the_form_never_renders_a_stored_secret(self) -> None:
        values = {"subdivx_session": "cf_clearance=super-secret-value", "providers": "Subscene|Local"}
        page = web_settings.render_page("Universal Subs", model(), values)
        self.assertNotIn("super-secret-value", page)
        self.assertIn("already set - leave blank to keep it", page)

    def test_current_values_are_rendered_for_ordinary_settings(self) -> None:
        page = web_settings.render_page("Universal Subs", model(), {"web_settings_port": "41234"})
        self.assertIn('value="41234"', page)
        self.assertIn("Save changed settings", page)

    def test_the_session_field_is_a_textarea(self) -> None:
        page = web_settings.render_page("Universal Subs", model(), {})
        self.assertIn("<textarea", page)
        self.assertIn("cf_clearance", page)

    def test_fields_keep_their_category(self) -> None:
        fields = model()
        self.assertEqual(fields[0].category_id, "general")  # the category order of settings.xml
        self.assertEqual(fields[-1].category_id, "web")     # the web page category sits last
        self.assertEqual(fields[-1].category_label, "Web settings page")
        self.assertEqual(field("providers").category_id, "general")
        self.assertEqual({candidate.category_id for candidate in fields},
                         {"web", "general", "credentials", "subtitles_cleanup", "file_system",
                          "advanced"})

    def test_secrets_are_grouped_in_one_visible_category(self) -> None:
        # Credentials used to hide in "Advanced" (level 2), which Kodi's default Standard level
        # hides, so the SubDL key could not be entered without changing the settings level.
        from xml.etree import ElementTree
        secrets = [candidate for candidate in model() if candidate.is_secret]
        self.assertEqual(len(secrets), 4)
        self.assertEqual({candidate.category_id for candidate in secrets}, {"credentials"})
        self.assertEqual(field("subdivx_session").category_label, "Credentials")
        secret_ids = {candidate.id for candidate in secrets}
        for element in ElementTree.parse(SETTINGS_XML).iter("setting"):
            if element.get("id") in secret_ids:
                self.assertLessEqual(int(element.findtext("level") or 2), 1,
                                     "%s must show at Kodi's default settings level" % element.get("id"))

    def test_the_page_groups_settings_by_category(self) -> None:
        page = web_settings.render_page("Universal Subs", model(), {})
        self.assertEqual(page.count("<fieldset"), 6)
        self.assertIn("<legend>Web settings page</legend>", page)
        self.assertIn("<legend>General</legend>", page)
        self.assertIn("<legend>Credentials</legend>", page)
        self.assertLess(page.index("<legend>General</legend>"), page.index("<legend>Web settings page</legend>"))
        self.assertEqual(page.count('<nav class="categories">'), 1)
        self.assertEqual(page.count('<a href="#cat-'), 6)

    def test_every_input_carries_its_initial_value_for_the_client_diff(self) -> None:
        # Without data-initial the page's diff logic collects nothing and every save is a no-op.
        page = web_settings.render_page("Universal Subs", model(), {"web_settings_port": "41234"})
        self.assertIn('data-initial="41234"', page)
        self.assertIn('data-initial=""', page)      # secrets and the session box start empty
        self.assertIn('data-list="1"', page)        # list checkboxes are grouped by name
        self.assertIn('"initial" in element.dataset', page)

    def test_the_page_forwards_the_browser_user_agent_alongside_the_session(self) -> None:
        page = web_settings.render_page("Universal Subs", model(), {})
        self.assertIn('name="subdivx_session"', page)
        self.assertIn("navigator.userAgent", page)


class SubmissionTest(unittest.TestCase):

    def test_integers_are_bounded(self) -> None:
        port = field("web_settings_port")
        self.assertEqual(web_settings.normalise_submission(port, "41234"), ("41234", ""))
        self.assertIn("at most", web_settings.normalise_submission(port, "70000")[1])
        self.assertIn("at least", web_settings.normalise_submission(port, "80")[1])
        self.assertIn("whole number", web_settings.normalise_submission(port, "abc")[1])

    def test_booleans_are_normalised(self) -> None:
        cleaning = field("clean_up_ads")
        self.assertEqual(web_settings.normalise_submission(cleaning, "true"), ("true", ""))
        self.assertEqual(web_settings.normalise_submission(cleaning, "false"), ("false", ""))
        self.assertEqual(web_settings.normalise_submission(cleaning, True), ("true", ""))

    def test_lists_keep_only_declared_options(self) -> None:
        providers = field("providers")
        value, reason = web_settings.normalise_submission(providers, ["Subscene", "NotAProvider", "Local"])
        self.assertEqual((value, reason), ("Subscene|Local", ""))

    def test_the_session_field_is_parsed_into_a_stored_blob(self) -> None:
        value, reason = web_settings.normalise_submission(field("subdivx_session"), CLEARANCE_VALUE)
        self.assertEqual(reason, "")
        self.assertNotIn("cf_clearance", value)  # stored base64, not the raw header
        from resources.lib.providers.subdivx_source_provider import parse_browser_session
        self.assertEqual(parse_browser_session(value)["cookie"], "cf_clearance=" + CLEARANCE_VALUE)

    def test_a_bad_session_is_reported_per_field(self) -> None:
        value, reason = web_settings.normalise_submission(field("subdivx_session"), "nonsense")
        self.assertIsNone(value)
        self.assertIn("cookie value without its name", reason)


class RequestGuardTest(unittest.TestCase):

    def test_loopback_client_with_loopback_host_is_allowed(self) -> None:
        self.assertEqual(web_settings.request_allowed(
            "127.0.0.1", "127.0.0.1:39517", None, "127.0.0.1", []), "")

    def test_a_cross_site_origin_is_refused(self) -> None:
        reason = web_settings.request_allowed(
            "127.0.0.1", "127.0.0.1:39517", "http://evil.example", "127.0.0.1", [])
        self.assertIn("cross-origin", reason)

    def test_a_domain_host_is_refused(self) -> None:
        # DNS rebinding: an attacker domain pointed at 127.0.0.1.
        reason = web_settings.request_allowed(
            "127.0.0.1", "evil.example:39517", None, "127.0.0.1", [])
        self.assertIn("IP address or localhost", reason)

    def test_lan_clients_need_the_allowlist(self) -> None:
        allowed = web_settings.parse_allowed_ips("192.168.1.50")
        refused = web_settings.request_allowed("192.168.1.77", "192.168.1.5:39517", None, "0.0.0.0", allowed)
        self.assertIn("allowlist", refused)
        self.assertEqual(web_settings.request_allowed("192.168.1.50", "192.168.1.5:39517", None, "0.0.0.0",
                                                      allowed), "")

    def test_loopback_bind_refuses_lan_clients_even_when_allowlisted(self) -> None:
        allowed = web_settings.parse_allowed_ips("192.168.1.0/24")
        reason = web_settings.request_allowed("192.168.1.50", "192.168.1.5:39517", None, "127.0.0.1", allowed)
        self.assertIn("loopback", reason)

    def test_the_page_url_uses_the_lan_address_when_bind_is_open(self) -> None:
        self.assertEqual(web_settings.page_url("127.0.0.1", 39517), "http://127.0.0.1:39517/")
        self.assertTrue(web_settings.page_url("0.0.0.0", 39517).startswith("http://"))


class ServerTest(unittest.TestCase):

    def setUp(self) -> None:
        self.saved = {}
        self.current = {"web_settings_port": "39517", "subdivx_session": "cf_clearance=stored"}
        self.server = web_settings.start_web_settings_server(
            bind="127.0.0.1", port=0, allowed_ips="", model=model(),
            get_values=lambda: dict(self.current),
            set_value=lambda field_id, value: (self.saved.__setitem__(field_id, value),
                                               self.current.__setitem__(field_id, value)),
            title="Universal Subs")
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]

    def test_get_serves_the_form(self) -> None:
        with urllib.request.urlopen(self.base + "/", timeout=5) as response:
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertIn("Providers", page)
        self.assertNotIn("cf_clearance=stored", page)

    def test_post_saves_only_submitted_fields(self) -> None:
        request = urllib.request.Request(
            self.base + "/settings", data=json.dumps({"values": {"web_settings_port": "41234"}}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload, {"ok": True, "saved": 1})
        self.assertEqual(self.saved, {"web_settings_port": "41234"})

    def test_invalid_values_are_reported_per_field(self) -> None:
        request = urllib.request.Request(
            self.base + "/settings",
            data=json.dumps({"values": {"web_settings_port": "1", "no_such_setting": "x"}}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertFalse(payload["ok"])
        self.assertIn("web_settings_port", payload["errors"])
        self.assertIn("no_such_setting", payload["errors"])
        self.assertEqual(self.saved, {})

    def test_a_cross_site_post_is_refused(self) -> None:
        request = urllib.request.Request(
            self.base + "/settings", data=json.dumps({"values": {"web_settings_port": "41234"}}).encode(),
            headers={"Content-Type": "application/json", "Origin": "http://evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 403)
        self.assertEqual(self.saved, {})

    def test_a_saved_notice_is_rendered_after_the_redirect(self) -> None:
        with urllib.request.urlopen(self.base + "/?saved=2", timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn("Saved 2 setting(s)", page)

    def test_unknown_paths_are_not_found(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.base + "/elsewhere", timeout=5)
        self.assertEqual(context.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
