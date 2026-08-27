import json
import unittest
from pathlib import Path

from sync.cache import CACHE_SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_manifest_and_runtime_files_are_complete(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["license"], "MIT")
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertTrue((ROOT / "preview.png").is_file())
        self.assertEqual(
            manifest["entryPoints"]["barWidget"],
            "AgendaBarWidget.qml",
        )
        for relative_path in (
            "AgendaBarWidget.qml",
            "AgendaPanel.qml",
            "AgendaModel.js",
            "SettingsPanel.qml",
            "CompactToggle.qml",
            "OnboardingService.qml",
            "OnboardingPanel.qml",
            "calendar_agenda.py",
            "sync/__init__.py",
            "sync/cache.py",
            "sync/cli.py",
            "sync/config.py",
            "sync/google.py",
            "sync/locking.py",
            "sync/registry.py",
            "sync/scheduler.py",
            "sync/status.py",
            "systemd/omarchy-calendar-agenda-sync.service",
            "systemd/omarchy-calendar-agenda-sync.timer",
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_fixture_uses_the_current_cache_schema(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures" / "events.json").read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["schemaVersion"], CACHE_SCHEMA_VERSION)
        self.assertIsInstance(fixture["accounts"], list)
        self.assertIsInstance(fixture["calendars"], list)
        self.assertIsInstance(fixture["events"], list)

    def test_sync_unit_runs_the_installed_python_module(self) -> None:
        service = (
            ROOT / "systemd" / "omarchy-calendar-agenda-sync.service"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "WorkingDirectory=%h/.config/omarchy/plugins/"
            "io.github.alexinslc.calendar-agenda",
            service,
        )
        self.assertIn(
            "ExecStart=/usr/bin/python3 %h/.config/omarchy/plugins/"
            "io.github.alexinslc.calendar-agenda/calendar_agenda.py --sync",
            service,
        )

    def test_onboarding_uses_only_the_bundled_helper(self) -> None:
        service = (ROOT / "OnboardingService.qml").read_text(encoding="utf-8")
        self.assertIn('property string helperPath: Quickshell.env("HOME")', service)
        self.assertIn('["/usr/bin/python3", root.helperPath', service)
        self.assertEqual(service.count("Process " + "{"), 2)

    def test_plugin_uses_the_plugin_scoped_public_urls(self) -> None:
        privacy_url = "https://omarchy.alexinslc.com/calendar-agenda/privacy/"
        config_url = (
            "https://omarchy.alexinslc.com/"
            "calendar-agenda/oauth/client-config"
        )
        onboarding = (ROOT / "OnboardingPanel.qml").read_text(encoding="utf-8")
        config = (ROOT / "sync" / "config.py").read_text(encoding="utf-8")
        self.assertIn(privacy_url, onboarding)
        self.assertIn(config_url, config)

    def test_hosted_site_and_oauth_credentials_are_not_committed(self) -> None:
        self.assertFalse((ROOT / "oauth-client.json").exists())
        self.assertFalse((ROOT / "site").exists())
        self.assertFalse((ROOT / "worker.js").exists())
        self.assertFalse((ROOT / "wrangler.jsonc").exists())
        self.assertFalse((ROOT / "screenshots").exists())
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("oauth-client.json", ignored)

    def test_agenda_has_one_settings_panel_and_visible_mode_selector(self) -> None:
        panel = (ROOT / "AgendaPanel.qml").read_text(encoding="utf-8")
        self.assertEqual(panel.count("SettingsPanel {"), 1)
        self.assertNotIn("id: settingsColumn", panel)
        self.assertIn('model: ["day", "week", "month"]', panel)

    def test_untrusted_calendar_labels_render_as_plain_text(self) -> None:
        for path in ROOT.glob("*.qml"):
            source = path.read_text(encoding="utf-8")
            self.assertEqual(
                source.count("Text {"),
                source.count("textFormat: Text.PlainText"),
                path.name,
            )

    def test_agenda_implements_the_bar_panel_handoff_contract(self) -> None:
        widget = (ROOT / "AgendaBarWidget.qml").read_text(encoding="utf-8")
        panel = (ROOT / "AgendaPanel.qml").read_text(encoding="utf-8")
        self.assertIn("readonly property bool popoutSwitchClosing", widget)
        self.assertIn("function closeForPopoutSwitch()", widget)
        self.assertIn("readonly property var barIdentity: hostWidget || root", panel)
        self.assertIn("onTabRequested:", panel)

    def test_account_labels_preserve_display_metadata(self) -> None:
        model = (ROOT / "AgendaModel.js").read_text(encoding="utf-8")
        panel = (ROOT / "SettingsPanel.qml").read_text(encoding="utf-8")
        self.assertIn('"displayName": account.displayName', model)
        self.assertIn("panel.accountLabel(modelData)", panel)

    def test_onboarding_surfaces_structured_errors_and_warnings(self) -> None:
        service = (ROOT / "OnboardingService.qml").read_text(encoding="utf-8")
        self.assertIn("property string statusError", service)
        self.assertIn("property string actionError", service)
        self.assertIn("function resultDetails(parsed)", service)
        self.assertIn("parsed.sync.errors", service)


if __name__ == "__main__":
    unittest.main()
