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

    def test_public_site_and_plugin_use_the_same_privacy_url(self) -> None:
        privacy_url = "https://calendar.alexinslc.com/privacy/"
        onboarding = (ROOT / "OnboardingPanel.qml").read_text(encoding="utf-8")
        homepage = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        privacy = (ROOT / "site" / "privacy" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(privacy_url, onboarding)
        self.assertIn('href="/privacy/"', homepage)
        self.assertIn("Google API Services User Data Policy", privacy)

    def test_public_site_uses_real_sanitized_product_captures(self) -> None:
        homepage = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("agenda-window", homepage)
        for filename in (
            "tokyo-night-week.png",
            "catppuccin-latte-day.png",
            "matte-black-month.png",
        ):
            self.assertIn(f'/assets/{filename}', homepage)
            self.assertEqual(
                (ROOT / "site" / "assets" / filename).read_bytes(),
                (ROOT / "screenshots" / filename).read_bytes(),
            )
        self.assertTrue(
            (ROOT / "site" / "assets" / "tokyo-night-car.jpg").is_file()
        )

    def test_public_site_preserves_product_capture_aspect_ratio(self) -> None:
        styles = (ROOT / "site" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("img { display: block; max-width: 100%; height: auto; }", styles)
        self.assertIn("aspect-ratio: 23 / 27; object-fit: contain;", styles)
        self.assertNotIn("quattro", (ROOT / "site" / "index.html").read_text(
            encoding="utf-8"
        ).lower())

    def test_public_site_embeds_demo_with_a_narrow_csp_exception(self) -> None:
        homepage = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        headers = (ROOT / "site" / "_headers").read_text(encoding="utf-8")
        privacy = (ROOT / "site" / "privacy" / "index.html").read_text(
            encoding="utf-8"
        )
        embed_origin = "https://www.youtube-nocookie.com"
        self.assertIn(f'{embed_origin}/embed/VsQA0hfj4d4', homepage)
        self.assertIn(f"frame-src {embed_origin};", headers)
        self.assertNotIn("frame-src https://www.youtube.com", headers)
        self.assertIn("privacy-enhanced embed", privacy)

    def test_not_found_page_overrides_prose_page_padding(self) -> None:
        not_found = (ROOT / "site" / "404.html").read_text(encoding="utf-8")
        styles = (ROOT / "site" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('class="prose not-found"', not_found)
        self.assertRegex(styles, r"\.not-found\s*\{[^}]*padding-block:\s*0;")

    def test_worker_serves_site_on_the_verified_custom_domain(self) -> None:
        config = json.loads((ROOT / "wrangler.jsonc").read_text(encoding="utf-8"))
        self.assertEqual(config["assets"]["directory"], "./site")
        self.assertEqual(config["assets"]["binding"], "ASSETS")
        self.assertEqual(config["main"], "worker.js")
        self.assertEqual(
            config["secrets"]["required"],
            ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"],
        )
        self.assertEqual(
            config["routes"],
            [{"pattern": "calendar.alexinslc.com", "custom_domain": True}],
        )

    def test_production_oauth_credentials_are_not_committed(self) -> None:
        self.assertFalse((ROOT / "oauth-client.json").exists())
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("oauth-client.json", ignored)
        worker = (ROOT / "worker.js").read_text(encoding="utf-8")
        self.assertIn('const CLIENT_CONFIG_PATH = "/oauth/client-config";', worker)
        self.assertIn("env.GOOGLE_OAUTH_CLIENT_ID", worker)
        self.assertIn("env.GOOGLE_OAUTH_CLIENT_SECRET", worker)

    def test_agenda_has_one_settings_panel_and_visible_mode_selector(self) -> None:
        panel = (ROOT / "AgendaPanel.qml").read_text(encoding="utf-8")
        self.assertEqual(panel.count("SettingsPanel {"), 1)
        self.assertNotIn("id: settingsColumn", panel)
        self.assertIn('model: ["day", "week", "month"]', panel)

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
