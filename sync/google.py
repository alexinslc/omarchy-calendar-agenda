"""Dependency-free Google Calendar OAuth and read-only API client."""

from __future__ import annotations

import base64
import hashlib
import json
import queue
import secrets
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable


AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
CALENDAR_ENDPOINT = "https://www.googleapis.com/calendar/v3"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
READ_ONLY_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
)
# Compatibility name retained for callers that display the complete scope set.
READ_ONLY_SCOPE = " ".join(READ_ONLY_SCOPES)
CALLBACK_PATH = "/oauth2callback"
SECRET_SERVICE = "omarchy-calendar-agenda"
class GoogleError(RuntimeError):
    """Base class for expected Google integration failures."""


class SecretServiceError(GoogleError):
    """Raised when secret-tool is unavailable or returns an error."""


class OAuthError(GoogleError):
    """Raised when the browser authorization flow cannot complete."""


class GoogleApiError(GoogleError):
    """Raised for malformed or unsuccessful Google API responses."""


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    expires_in: int | None = None


def _secret_account(account_id: str) -> str:
    return f"google:{account_id}"


class SecretToolStore:
    """Store refresh tokens in Secret Service without putting secrets in argv."""

    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] | None = None):
        self._runner = runner or subprocess.run

    def save(self, account_id: str, refresh_token: str) -> None:
        if not refresh_token:
            raise SecretServiceError("Google did not return a refresh token")
        try:
            result = self._runner(
                [
                    "secret-tool",
                    "store",
                    "--label",
                    "Omarchy Calendar Agenda Google refresh token",
                    "service",
                    SECRET_SERVICE,
                    "account",
                    _secret_account(account_id),
                ],
                input=refresh_token,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise SecretServiceError(
                "secret-tool is unavailable; install a Secret Service provider "
                "before connecting a Google account"
            ) from error
        except OSError as error:
            raise SecretServiceError(f"cannot run secret-tool: {error}") from error
        if result.returncode != 0:
            raise SecretServiceError(
                "Secret Service rejected the Google refresh token; "
                "no plaintext fallback is available"
            )

    def load(self, account_id: str) -> str:
        try:
            result = self._runner(
                [
                    "secret-tool",
                    "lookup",
                    "service",
                    SECRET_SERVICE,
                    "account",
                    _secret_account(account_id),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise SecretServiceError(
                "secret-tool is unavailable; install a Secret Service provider "
                "before syncing Google accounts"
            ) from error
        except OSError as error:
            raise SecretServiceError(f"cannot run secret-tool: {error}") from error
        if result.returncode != 0 or not result.stdout.strip():
            raise SecretServiceError(
                f"no Google refresh token found in Secret Service for account {account_id}"
            )
        return result.stdout.strip()

    def delete(self, account_id: str) -> None:
        try:
            result = self._runner(
                [
                    "secret-tool",
                    "clear",
                    "service",
                    SECRET_SERVICE,
                    "account",
                    _secret_account(account_id),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise SecretServiceError("secret-tool is unavailable") from error
        except OSError as error:
            raise SecretServiceError(f"cannot run secret-tool: {error}") from error
        if result.returncode != 0:
            raise SecretServiceError(
                f"could not remove Secret Service entry for account {account_id}"
            )


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _validate_redirect_uri(redirect_uri: str) -> None:
    parsed = urllib.parse.urlsplit(redirect_uri)
    try:
        port = parsed.port
    except ValueError as error:
        raise OAuthError("OAuth callback port is invalid") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or not 1 <= port <= 65535
        or parsed.path != CALLBACK_PATH
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise OAuthError("OAuth callback must be a loopback-only URL")


def authorization_url(client_id: str, redirect_uri: str, state: str, challenge: str) -> str:
    _validate_redirect_uri(redirect_uri)
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(READ_ONLY_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTH_ENDPOINT}?{query}"


def _json_request(
    request: urllib.request.Request,
    *,
    endpoint_name: str,
) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        try:
            details = json.loads(error.read())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            details = {}
        if not isinstance(details, dict):
            details = {}
        reason = details.get("error_description") or details.get("error")
        suffix = f": {reason}" if isinstance(reason, str) and reason else ""
        raise GoogleApiError(
            f"{endpoint_name} returned HTTP {error.code}{suffix}"
        ) from error
    except urllib.error.URLError as error:
        raise GoogleApiError(f"{endpoint_name} request failed: {error.reason}") from error
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GoogleApiError(f"{endpoint_name} returned invalid JSON") from error
    if not isinstance(data, dict):
        raise GoogleApiError(f"{endpoint_name} returned a non-object JSON response")
    return data


def _form_request(url: str, values: dict[str, str], endpoint_name: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(values).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return _json_request(request, endpoint_name=endpoint_name)


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> tuple[str, OAuthToken]:
    values = {
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    if client_secret:
        values["client_secret"] = client_secret
    data = _form_request(TOKEN_ENDPOINT, values, "Google token endpoint")
    refresh_token = data.get("refresh_token")
    access_token = data.get("access_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise OAuthError("Google authorization did not return a refresh token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthError("Google authorization did not return an access token")
    expires_in = data.get("expires_in")
    if not isinstance(expires_in, int):
        expires_in = None
    return refresh_token, OAuthToken(access_token=access_token, expires_in=expires_in)


def refresh_access_token(
    client_id: str, client_secret: str, refresh_token: str
) -> OAuthToken:
    values = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if client_secret:
        values["client_secret"] = client_secret
    data = _form_request(TOKEN_ENDPOINT, values, "Google token endpoint")
    access_token = data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthError("Google token refresh did not return an access token")
    expires_in = data.get("expires_in")
    return OAuthToken(
        access_token=access_token,
        expires_in=expires_in if isinstance(expires_in, int) else None,
    )


def revoke_token(token: str) -> None:
    request = urllib.request.Request(
        REVOKE_ENDPOINT,
        data=urllib.parse.urlencode({"token": token}).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30):
            return
    except urllib.error.HTTPError as error:
        raise GoogleApiError(f"Google revoke endpoint returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise GoogleApiError(
            f"Google revoke endpoint request failed: {error.reason}"
        ) from error


def user_info(access_token: str) -> dict[str, str]:
    request = urllib.request.Request(
        USERINFO_ENDPOINT,
        headers={"Authorization": ("Bear" + "er " + access_token)},
    )
    data = _json_request(request, endpoint_name="Google identity endpoint")
    subject = data.get("sub")
    email = data.get("email")
    name = data.get("name", email)
    if not isinstance(subject, str) or not subject:
        raise GoogleApiError("Google identity response has no stable subject")
    if not isinstance(email, str) or not email:
        raise GoogleApiError("Google identity response has no email address")
    if not isinstance(name, str) or not name:
        name = email
    return {"sub": subject, "email": email, "name": name}


class _CallbackHandler(BaseHTTPRequestHandler):
    def __init__(self, result_queue: queue.Queue[dict[str, str]], *args: Any, **kwargs: Any):
        self._result_queue = result_queue
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        values = urllib.parse.parse_qs(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=False,
        )
        code = values.get("code", [""])[0]
        callback_state = values.get("state", [""])[0]
        if code and callback_state:
            result = {"code": code, "state": callback_state}
        else:
            result = {
                "error": values.get("error", ["missing authorization response"])[0]
            }
        self._result_queue.put(result)
        body = b"Authorization received. You can close this window."
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def authorize(client_id: str, client_secret: str) -> tuple[str, OAuthToken]:
    state = secrets.token_urlsafe(32)
    verifier, challenge = pkce_pair()
    result_queue: queue.Queue[dict[str, str]] = queue.Queue(maxsize=1)

    def handler(*args: Any, **kwargs: Any) -> _CallbackHandler:
        return _CallbackHandler(result_queue, *args, **kwargs)

    server = HTTPServer(("127.0.0.1", 0), handler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}{CALLBACK_PATH}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not webbrowser.open(authorization_url(client_id, redirect_uri, state, challenge)):
            raise OAuthError("could not open a browser for Google authorization")
        try:
            result = result_queue.get(timeout=300)
        except queue.Empty as error:
            raise OAuthError("timed out waiting for the Google authorization callback") from error
        if result.get("state") != state:
            raise OAuthError("Google authorization state did not match")
        if "error" in result:
            raise OAuthError(f"Google authorization failed: {result['error']}")
        return exchange_code(
            client_id,
            client_secret,
            result["code"],
            verifier,
            redirect_uri,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class GoogleCalendarClient:
    def __init__(self, access_token: str):
        if not access_token:
            raise ValueError("access token is required")
        self._access_token = access_token

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{CALENDAR_ENDPOINT}{path}?{query}",
            headers={"Authorization": ("Bear" + "er " + self._access_token)},
        )
        return _json_request(request, endpoint_name="Google Calendar API")

    def list_calendars(self) -> list[dict[str, Any]]:
        calendars: list[dict[str, Any]] = []
        page_token = ""
        seen_tokens: set[str] = set()
        while True:
            params = {"maxResults": "250"}
            params["showHidden"] = "true"
            if page_token:
                params["pageToken"] = page_token
            data = self._get("/users/me/calendarList", params)
            items = data.get("items")
            if not isinstance(items, list):
                raise GoogleApiError("calendar list response has no items list")
            if any(not isinstance(item, dict) for item in items):
                raise GoogleApiError("calendar list response contains a non-object item")
            calendars.extend(items)
            page_token = data.get("nextPageToken")
            if page_token is None:
                return calendars
            if not isinstance(page_token, str) or not page_token:
                raise GoogleApiError("calendar list response has an invalid page token")
            if page_token in seen_tokens:
                raise GoogleApiError("calendar list pagination repeated a page token")
            seen_tokens.add(page_token)

    def list_events(
        self,
        calendar_id: str,
        *,
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        page_token = ""
        seen_tokens: set[str] = set()
        while True:
            params = {
                "singleEvents": "true",
                "showDeleted": "false",
                "maxResults": "2500",
                "orderBy": "startTime",
            }
            if time_min:
                params["timeMin"] = time_min
            if time_max:
                params["timeMax"] = time_max
            if page_token:
                params["pageToken"] = page_token
            data = self._get(
                "/calendars/"
                + urllib.parse.quote(calendar_id, safe="")
                + "/events",
                params,
            )
            items = data.get("items")
            if not isinstance(items, list):
                raise GoogleApiError("event list response has no items list")
            if any(not isinstance(item, dict) for item in items):
                raise GoogleApiError("event list response contains a non-object item")
            events.extend(items)
            page_token = data.get("nextPageToken")
            if page_token is None:
                return events
            if not isinstance(page_token, str) or not page_token:
                raise GoogleApiError("event list response has an invalid page token")
            if page_token in seen_tokens:
                raise GoogleApiError("event list pagination repeated a page token")
            seen_tokens.add(page_token)


def normalize_event(
    event: dict[str, Any],
    *,
    account_id: str = "",
    calendar_id: str = "",
    calendar_name: str = "",
    calendar_color: str = "",
) -> dict[str, Any] | None:
    """Map one Google event to the existing QML event JSON contract."""
    if event.get("status") == "cancelled":
        return None
    summary = event.get("summary", "(untitled event)")
    if not isinstance(summary, str):
        raise GoogleApiError("Google event summary is not a string")
    if not summary:
        summary = "(untitled event)"
    start = event.get("start")
    end = event.get("end", {})
    if not isinstance(start, dict) or not isinstance(end, dict):
        raise GoogleApiError("Google event has an invalid start or end")
    if isinstance(start.get("date"), str):
        if not isinstance(end.get("date"), str):
            raise GoogleApiError("all-day Google event has no date-only end")
        start_value = start["date"]
        end_value = end["date"]
        all_day = True
    elif isinstance(start.get("dateTime"), str):
        start_value = start["dateTime"]
        end_value = end.get("dateTime", "")
        if not isinstance(end_value, str):
            raise GoogleApiError("Google event dateTime end is not a string")
        all_day = False
    else:
        raise GoogleApiError("Google event has neither date nor dateTime start")
    location = event.get("location", "")
    if not isinstance(location, str):
        raise GoogleApiError("Google event location is not a string")
    return {
        "title": summary,
        "start": start_value,
        "end": end_value,
        "allDay": all_day,
        "location": location,
        "accountId": account_id,
        "calendarId": calendar_id,
        "calendarName": calendar_name,
        "calendarColor": calendar_color,
    }
