# Omarchy Calendar Agenda

A lightweight, agenda-focused Google Calendar widget for Omarchy.

This project is in prototype development. The current prototype provides a
top-right bar icon with compact day, week, and month agenda views. It reads
normalized events from the private Google sync cache and reports an actionable
error when no valid cache is available. Google access uses read-only OAuth
with support for multiple accounts and calendars.

## Security model

Omarchy plugins run unsandboxed with the user's permissions. This project
therefore treats the repository, review process, and release provenance as its
security boundary.

- Google access is read-only and limited to the Calendar read-only scope.
- OAuth refresh tokens are stored in the Linux Secret Service.
- Calendar data is cached locally and written atomically.
- The sync helper will use Python's standard library only.
- QML and helper code must not execute arbitrary shell commands, load remote
  code, or accept arbitrary network endpoints.
- Releases will be produced from protected, signed tags and accompanied by
  checksums, an SBOM, and GitHub artifact attestations.

See [SECURITY.md](SECURITY.md) for reporting and trust-boundary details.

## Development

This first prototype uses the eventual permanent plugin ID:
`io.github.alexinslc.calendar-agenda`. No temporary clone is needed.

For local development, install without a network checkout:

```bash
mkdir -p ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda
cp manifest.json AgendaBarWidget.qml AgendaPanel.qml AgendaModel.js \
  ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda/
cp -r fixtures ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda/
omarchy-shell shell rescanPlugins
```

Add the widget to the top-right of the bar in
`~/.config/omarchy/shell.json`:

```json
{
  "version": 1,
  "bar": {
    "position": "top",
    "layout": {
      "right": [
        { "id": "io.github.alexinslc.calendar-agenda" }
      ]
    }
  }
}
```

The `defaultSection` in `manifest.json` is `right`; `shell.json` remains the
source of truth and can move the widget to another section. The popup reads the
sync cache at
`~/.local/state/omarchy/calendar-agenda/events.json`, reloads it when the
file changes, and checks for updates while the shell is running. If no cache
exists or contains invalid data, it shows an error instead of presenting
misleading fixture events. Google Calendar synchronization is a one-shot
command for now; periodic 15-minute scheduling will be added in a later phase.

## Google sync foundation

The helper uses Python's standard library only. It reads this configuration
file:
`~/.config/omarchy/calendar-agenda/config.json`

```json
{
  "google": {
    "client_id": "YOUR-OAUTH-CLIENT-ID.apps.googleusercontent.com",
    "client_secret": "YOUR-DESKTOP-CLIENT-SECRET",
    "accounts": ["personal", "work"]
  }
}
```

Create an OAuth client in Google Cloud as a desktop application and copy both
the client ID and client secret into this local file. Add one stable local
account ID for each Google account. Install `secret-tool` and a
Secret Service provider (for example, GNOME Keyring or KeePassXC), then
authorize each configured account:

```bash
python3 -m sync.cli --authorize --account personal
python3 -m sync.cli --sync
```

`--authorize` opens the browser and uses read-only authorization-code PKCE
with a random state and a loopback-only callback. Refresh tokens are stored
under Secret Service attributes `service=omarchy-calendar-agenda` and
`account=google:<account-id>`. If Secret Service is unavailable, authorization
and sync fail clearly; there is no plaintext fallback. Use
`--disconnect --account personal` to revoke and remove a stored token.

The helper lists every calendar for every configured account, follows API
pagination, and normalizes Google events to the existing QML contract:
`title`, `start`, `end`, `allDay`, and `location`. Canceled events are omitted
and missing Google summaries are represented explicitly as `(untitled event)`.
The cache is written atomically, with mode `0600`, at:
`~/.local/state/omarchy/calendar-agenda/events.json`

Data flow is: config → browser OAuth → Secret Service refresh token → fixed
Google HTTPS endpoints → normalized in-memory events → atomic cache write.
Tokens never appear in command-line arguments, logs, or files. Tests mock
browser, Secret Service, and HTTP boundaries; they never require credentials or
make network calls.

If a local Quickshell runtime is available, model checks can be run with:

```bash
timeout 5s env QT_QPA_PLATFORM=offscreen quickshell -p model_test.qml
```

The test prints `agenda model tests passed`; the timeout is expected because a
standalone Quickshell config has no application-level quit handler.
