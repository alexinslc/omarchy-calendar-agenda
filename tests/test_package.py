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

    def test_agenda_has_one_settings_panel_and_visible_mode_selector(self) -> None:
        panel = (ROOT / "AgendaPanel.qml").read_text(encoding="utf-8")
        self.assertEqual(panel.count("SettingsPanel {"), 1)
        self.assertNotIn("id: settingsColumn", panel)
        self.assertIn('model: ["day", "week", "month"]', panel)


if __name__ == "__main__":
    unittest.main()
