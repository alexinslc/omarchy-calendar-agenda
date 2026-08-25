import json
import shutil
import stat
import subprocess
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import Mock, patch

from sync.cache import CACHE_SCHEMA_VERSION, purge_account, write_events
from sync.cli import _connect_account, _remove_connected_account, main
from sync.config import ConfigError, GoogleConfig, load_config
from sync.google import (
    CALENDAR_ENDPOINT,
    GoogleCalendarClient,
    OAuthError,
    OAuthToken,
    READ_ONLY_SCOPE,
    READ_ONLY_SCOPES,
    SecretServiceError,
    SecretToolStore,
    authorization_url,
    exchange_code,
    normalize_event,
    pkce_pair,
    revoke_token,
    user_info,
)
from sync.registry import (
    Account,
    RegistryError,
    add_account,
    load_accounts,
    save_accounts,
)
from sync.scheduler import install_timer, remove_timer
from sync.status import load_sync_status, write_sync_status


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(__file__).parent / ".test-tmp"
        self.directory.mkdir(exist_ok=True)
        self.path = self.directory / "config.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_loads_client_id_and_account_ids(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "google": {
                        "client_id": "test-client.apps.googleusercontent.com",
                        "client_secret": "test-client-secret",
                        "accounts": ["personal", "work"],
                    }
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            load_config(self.path).accounts,
            ("personal", "work"),
        )

    def test_rejects_unknown_keys_and_invalid_client_id(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "google": {
                        "client_id": "not-a-client-id",
                        "client_secret": "test-client-secret",
                        "unsupported": True,
                    }
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ConfigError):
            load_config(self.path)

    def test_public_desktop_client_does_not_require_a_secret(self) -> None:
        self.path.write_text(
            json.dumps(
                {"google": {"client_id": "test-client.apps.googleusercontent.com"}}
            ),
            encoding="utf-8",
        )
        self.assertEqual(load_config(self.path).client_secret, "")


class CacheTests(unittest.TestCase):
    def test_writes_contract_atomically_with_private_permissions(self) -> None:
        directory = Path(__file__).parent / ".test-tmp"
        directory.mkdir(exist_ok=True)
        path = directory / "events.json"
        try:
            write_events(
                [{"title": "Planning", "start": "2026-08-24"}],
                path,
                generated_at="2026-08-24T15:00:00Z",
                range_start="2026-08-24T15:00:00Z",
                range_end="2026-09-21T15:00:00Z",
                accounts=[{"id": "personal"}],
                calendars=[
                    {
                        "accountId": "personal",
                        "id": "primary",
                        "name": "Personal",
                        "color": "#4285f4",
                    }
                ],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schemaVersion"], CACHE_SCHEMA_VERSION)
            self.assertEqual(payload["generatedAt"], "2026-08-24T15:00:00Z")
            self.assertEqual(payload["rangeEnd"], "2026-09-21T15:00:00Z")
            self.assertEqual(payload["accounts"], [{"id": "personal"}])
            self.assertEqual(payload["calendars"][0]["name"], "Personal")
            self.assertEqual(payload["events"][0]["title"], "Planning")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertFalse(list(directory.glob(".events.json.*.tmp")))
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class GoogleTests(unittest.TestCase):
    def test_normalizes_timed_all_day_and_cancelled_events(self) -> None:
        timed = normalize_event(
            {
                "summary": "Review",
                "start": {"dateTime": "2026-08-24T09:00:00-06:00"},
                "end": {"dateTime": "2026-08-24T10:00:00-06:00"},
                "location": "Room A",
            }
        )
        all_day = normalize_event(
            {
                "summary": "Holiday",
                "start": {"date": "2026-08-25"},
                "end": {"date": "2026-08-26"},
            }
        )
        self.assertEqual(timed["allDay"], False)
        self.assertEqual(timed["location"], "Room A")
        self.assertEqual(all_day["allDay"], True)
        self.assertIsNone(normalize_event({"status": "cancelled"}))

    def test_pkce_and_authorization_url_are_fixed_and_read_only(self) -> None:
        verifier, challenge = pkce_pair()
        self.assertGreaterEqual(len(verifier), 43)
        url = authorization_url(
            "test-client.apps.googleusercontent.com",
            "http://127.0.0.1:4321/oauth2callback",
            "random-state",
            challenge,
        )
        self.assertTrue(url.startswith("https://accounts.google.com/o/oauth2/v2/auth?"))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(set(query["scope"][0].split()), set(READ_ONLY_SCOPES))
        self.assertIn(
            "https://www.googleapis.com/auth/calendar.events.readonly",
            READ_ONLY_SCOPE,
        )
        self.assertNotIn(
            "https://www.googleapis.com/auth/calendar.readonly", READ_ONLY_SCOPES
        )
        self.assertIn("code_challenge_method=S256", url)
        self.assertNotIn(CALENDAR_ENDPOINT, url)
        with self.assertRaises(OAuthError):
            authorization_url(
                "test-client.apps.googleusercontent.com",
                "https://example.invalid/oauth2callback",
                "random-state",
                challenge,
            )

    def test_secret_tool_uses_per_account_attributes_and_never_token_argv(self) -> None:
        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, stdout="refresh-token\n", stderr="")

        store = SecretToolStore(runner=runner)
        store.save("work", "refresh-token")
        self.assertEqual(calls[0][0][-2:], ["account", "google:work"])
        self.assertNotIn("refresh-token", calls[0][0])
        self.assertEqual(calls[0][1]["input"], "refresh-token")
        self.assertEqual(store.load("work"), "refresh-token")

    def test_secret_tool_failure_is_explicit(self) -> None:
        def missing(*args, **kwargs):
            raise FileNotFoundError

        with self.assertRaisesRegex(SecretServiceError, "secret-tool is unavailable"):
            SecretToolStore(runner=missing).load("personal")

    def test_revoke_accepts_google_empty_success_response(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

        with patch("sync.google.urllib.request.urlopen", return_value=Response()):
            revoke_token("refresh-token")

    @patch(
        "sync.google._form_request",
        return_value={
            "refresh_token": "refresh-token",
            "access_token": "access-token",
        },
    )
    def test_public_client_exchange_omits_an_empty_secret(self, request_mock) -> None:
        exchange_code(
            "test-client.apps.googleusercontent.com",
            "",
            "authorization-code",
            "verifier",
            "http://127.0.0.1:4321/oauth2callback",
        )
        self.assertNotIn("client_secret", request_mock.call_args.args[1])

    def test_user_info_requires_stable_subject_and_email(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return json.dumps(
                    {"sub": "google-subject", "email": "alex@example.com", "name": "Alex"}
                ).encode()

        with patch("sync.google.urllib.request.urlopen", return_value=Response()):
            self.assertEqual(user_info("access-token")["sub"], "google-subject")

    def test_calendar_api_follows_calendar_and_event_pagination(self) -> None:
        responses = iter(
            [
                {"items": [{"id": "primary"}], "nextPageToken": "calendar-page-2"},
                {"items": [{"id": "work"}]},
                {"items": [{"summary": "First"}], "nextPageToken": "event-page-2"},
                {"items": [{"summary": "Second"}]},
            ]
        )
        captured_calls = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return json.dumps(next(responses)).encode("utf-8")

        def open_url(request, **kwargs):
            captured_calls.append(request)
            return Response()

        with patch("sync.google.urllib.request.urlopen", side_effect=open_url):
            client = GoogleCalendarClient("access-token")
            calendars = client.list_calendars()
            events = client.list_events("primary")

        self.assertEqual([calendar["id"] for calendar in calendars], ["primary", "work"])
        self.assertEqual([event["summary"] for event in events], ["First", "Second"])
        event_query = urllib.parse.parse_qs(
            urllib.parse.urlsplit(captured_calls[2].full_url).query
        )
        self.assertNotIn("calendarId", event_query)
        self.assertEqual(
            urllib.parse.unquote(urllib.parse.urlsplit(captured_calls[2].full_url).path),
            "/calendar/v3/calendars/primary/events",
        )


class CliTests(unittest.TestCase):
    @patch("sync.cli.write_sync_status")
    @patch("sync.cli.write_events")
    @patch("sync.cli.GoogleCalendarClient")
    @patch("sync.cli.refresh_access_token", return_value=OAuthToken("access-token"))
    @patch("sync.cli.SecretToolStore")
    @patch(
        "sync.cli.load_config",
        return_value=GoogleConfig(
            client_id="test-client.apps.googleusercontent.com",
            client_secret="client-secret",
            accounts=("personal",),
        ),
    )
    @patch(
        "sync.cli.migrate_legacy_accounts",
        return_value=(
            Account(
                id="personal",
                provider_subject="legacy:personal",
                email="",
                display_name="personal",
                legacy=True,
            ),
        ),
    )
    def test_sync_writes_coverage_and_calendar_metadata(
        self,
        _migrate_accounts,
        _load_config,
        store_class,
        _refresh_access_token,
        client_class,
        write_events_mock,
        write_status_mock,
    ) -> None:
        store_class.return_value.load.return_value = "refresh-token"
        client = client_class.return_value
        client.list_calendars.return_value = [
            {
                "id": "primary",
                "summary": "Personal",
                "backgroundColor": "#4285f4",
            }
        ]
        client.list_events.return_value = [
            {
                "summary": "Review",
                "start": {"dateTime": "2026-08-24T09:00:00-06:00"},
                "end": {"dateTime": "2026-08-24T10:00:00-06:00"},
            }
        ]

        self.assertEqual(main(["--sync"]), 0)

        args, kwargs = write_events_mock.call_args
        self.assertEqual(args[0][0]["accountId"], "personal")
        self.assertEqual(kwargs["accounts"][0]["id"], "personal")
        self.assertEqual(kwargs["accounts"][0]["displayName"], "personal")
        self.assertEqual(kwargs["calendars"][0]["name"], "Personal")
        self.assertTrue(kwargs["generated_at"].endswith("Z"))
        self.assertTrue(kwargs["range_start"].endswith("Z"))
        self.assertTrue(kwargs["range_end"].endswith("Z"))
        write_status_mock.assert_called_once()
        self.assertEqual(
            write_status_mock.call_args.args[0]["personal"],
            {"ok": True, "error": ""},
        )


class RegistryTests(unittest.TestCase):
    def test_round_trip_is_private_and_rejects_duplicate_google_account(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            first = Account("one", "subject-one", "one@example.com", "One")
            save_accounts((first,), path)
            self.assertEqual(load_accounts(path), (first,))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaisesRegex(RegistryError, "already connected"):
                add_account(
                    Account("two", "subject-one", "alias@example.com", "Alias"),
                    path,
                )

    def test_purge_removes_only_selected_account_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.json"
            write_events(
                [
                    {"accountId": "one", "title": "Private"},
                    {"accountId": "two", "title": "Keep"},
                ],
                path,
                generated_at="2026-08-24T15:00:00Z",
                range_start="2026-08-24T15:00:00Z",
                range_end="2026-09-21T15:00:00Z",
                accounts=[{"id": "one"}, {"id": "two"}],
                calendars=[
                    {"accountId": "one", "id": "a"},
                    {"accountId": "two", "id": "b"},
                ],
            )
            purge_account("one", path)
            payload = json.loads(path.read_text())
            self.assertEqual(payload["accounts"], [{"id": "two"}])
            self.assertEqual(payload["events"], [{"accountId": "two", "title": "Keep"}])

    def test_purge_discards_an_unusable_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.json"
            path.write_text("not-json", encoding="utf-8")
            purge_account("one", path)
            self.assertFalse(path.exists())

    def test_sync_health_round_trip_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sync-status.json"
            values = {
                "one": {"ok": False, "error": "authorization expired"},
                "two": {"ok": True, "error": ""},
            }
            write_sync_status(values, path)
            self.assertEqual(load_sync_status(path), values)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


class AccountLifecycleTests(unittest.TestCase):
    @patch("sync.cli._sync_accounts", return_value={"ok": True})
    @patch("sync.cli.install_timer")
    @patch(
        "sync.cli.user_info",
        return_value={"sub": "subject", "email": "alex@example.com", "name": "Alex"},
    )
    @patch("sync.cli.authorize", return_value=("refresh-token", OAuthToken("access-token")))
    def test_connect_registers_identity_and_enables_timer(
        self, _authorize, _identity, install_timer_mock, _sync
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "accounts.json"
            store = Mock()
            config = GoogleConfig("test.apps.googleusercontent.com", "", ())
            with patch("sync.cli.DEFAULT_REGISTRY_PATH", registry):
                result = _connect_account(config, store)
            self.assertTrue(result["ok"])
            self.assertEqual(load_accounts(registry)[0].email, "alex@example.com")
            store.save.assert_called_once()
            install_timer_mock.assert_called_once()

    @patch("sync.cli._sync_accounts", return_value={"ok": True})
    @patch("sync.cli.remove_timer")
    @patch("sync.cli.purge_account")
    @patch("sync.cli.revoke_token")
    def test_remove_revokes_token_purges_cache_and_disables_last_timer(
        self, revoke_mock, purge_mock, remove_timer_mock, _sync
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "accounts.json"
            account = Account("one", "subject", "one@example.com", "One")
            save_accounts((account,), registry)
            store = Mock()
            store.load.return_value = "refresh-token"
            config = GoogleConfig("test.apps.googleusercontent.com", "", ())
            with patch("sync.cli.DEFAULT_REGISTRY_PATH", registry):
                result = _remove_connected_account(
                    "one", config, store, local_only=False
                )
            self.assertTrue(result["ok"])
            self.assertEqual(load_accounts(registry), ())
            revoke_mock.assert_called_once_with("refresh-token")
            purge_mock.assert_called_once_with("one")
            remove_timer_mock.assert_called_once()

    @patch("sync.cli._sync_accounts", return_value={"ok": True})
    @patch("sync.cli.remove_timer")
    @patch("sync.cli.purge_account")
    @patch("sync.cli.revoke_token")
    def test_local_only_remove_does_not_require_google_or_oauth_config(
        self, revoke_mock, _purge, _remove_timer, _sync
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "accounts.json"
            save_accounts(
                (Account("one", "subject", "one@example.com", "One"),),
                registry,
            )
            store = Mock()
            with patch("sync.cli.DEFAULT_REGISTRY_PATH", registry):
                result = _remove_connected_account(
                    "one", None, store, local_only=True
                )
            self.assertTrue(result["ok"])
            revoke_mock.assert_not_called()
            store.load.assert_not_called()


class SchedulerTests(unittest.TestCase):
    def test_install_and_remove_manage_only_named_user_units(self) -> None:
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as directory:
            units = Path(directory)
            install_timer(units, runner=runner)
            self.assertTrue((units / "omarchy-calendar-agenda-sync.timer").is_file())
            remove_timer(units, runner=runner)
            self.assertFalse((units / "omarchy-calendar-agenda-sync.timer").exists())
        self.assertIn(["systemctl", "--user", "daemon-reload"], calls)


if __name__ == "__main__":
    unittest.main()
