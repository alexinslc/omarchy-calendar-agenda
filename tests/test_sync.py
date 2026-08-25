import json
import shutil
import stat
import subprocess
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

from sync.cache import write_events
from sync.config import ConfigError, load_config
from sync.google import (
    CALENDAR_ENDPOINT,
    GoogleCalendarClient,
    OAuthError,
    READ_ONLY_SCOPE,
    SecretServiceError,
    SecretToolStore,
    authorization_url,
    normalize_event,
    pkce_pair,
    revoke_token,
)


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


class CacheTests(unittest.TestCase):
    def test_writes_contract_atomically_with_private_permissions(self) -> None:
        directory = Path(__file__).parent / ".test-tmp"
        directory.mkdir(exist_ok=True)
        path = directory / "events.json"
        try:
            write_events([{"title": "Planning", "start": "2026-08-24"}], path)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"events": [{"title": "Planning", "start": "2026-08-24"}]},
            )
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
        self.assertIn("scope=" + "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar.readonly", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertNotIn(CALENDAR_ENDPOINT, url)
        self.assertEqual(READ_ONLY_SCOPE, "https://www.googleapis.com/auth/calendar.readonly")
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


if __name__ == "__main__":
    unittest.main()
