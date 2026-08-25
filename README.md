# Omarchy Calendar Agenda

A lightweight, agenda-focused Google Calendar widget for Omarchy.

This project is in active development. The current version provides a
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
- Releases are produced from version tags and accompanied by
  checksums, an SBOM, and GitHub artifact attestations.

See [SECURITY.md](SECURITY.md) for reporting and trust-boundary details.

## Install

Install the plugin directly from its public repository:

```bash
omarchy plugin add https://github.com/alexinslc/omarchy-calendar-agenda.git --enable
```

Configure Google access as described below, authorize at least one account,
and run the first sync before opening the agenda.

## Development

This first prototype uses the eventual permanent plugin ID:
`io.github.alexinslc.calendar-agenda`. No temporary clone is needed.

For local development, copy every runtime component without a network checkout:

```bash
mkdir -p ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda
cp manifest.json AgendaBarWidget.qml AgendaPanel.qml AgendaModel.js \
  CompactToggle.qml SettingsPanel.qml \
  ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda/
cp -r sync systemd ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda/
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
file changes. If no cache exists, is expired, or contains invalid data, it shows
an error instead of presenting misleading fixture events. The cache records its
generation time and coverage window; navigation stops outside that window and
partially covered views are labeled explicitly.
Open the panel's gear button to configure displayed event fields, account and
calendar visibility. These preferences are stored at
`~/.local/state/omarchy/calendar-agenda/settings.json`.

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

Create the directory and configuration file, then enter the installed plugin
directory before running its Python module:

```bash
mkdir -p ~/.config/omarchy/calendar-agenda
cd ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda
```

Create an OAuth client in Google Cloud as a desktop application and copy both
the client ID and client secret into this local file. Add one stable local
account ID for each Google account. Restrict the configuration to your user:

```bash
chmod 600 ~/.config/omarchy/calendar-agenda/config.json
```

Install `secret-tool` and a
Secret Service provider (for example, GNOME Keyring or KeePassXC), then
authorize each configured account:

```bash
python3 -m sync.cli --authorize --account personal
python3 -m sync.cli --sync
```

To keep the cache current, install and enable the bundled user timer after the
first successful sync:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/omarchy-calendar-agenda-sync.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now omarchy-calendar-agenda-sync.timer
```

Check scheduling and the most recent result with:

```bash
systemctl --user status omarchy-calendar-agenda-sync.timer
journalctl --user -u omarchy-calendar-agenda-sync.service --since today
```

Before removing the plugin, disable and remove its user timer:

```bash
systemctl --user disable --now omarchy-calendar-agenda-sync.timer
rm -f ~/.config/systemd/user/omarchy-calendar-agenda-sync.{service,timer}
systemctl --user daemon-reload
```

`--authorize` opens the browser and uses read-only authorization-code PKCE
with a random state and a loopback-only callback. Refresh tokens are stored
under Secret Service attributes `service=omarchy-calendar-agenda` and
`account=google:<account-id>`. If Secret Service is unavailable, authorization
and sync fail clearly; there is no plaintext fallback. Use
`--disconnect --account personal` to revoke and remove a stored token.

The helper lists every calendar for every configured account, follows API
pagination, and synchronizes events from the current moment through the next
28 days. It normalizes Google events to the existing QML contract:
`title`, `start`, `end`, `allDay`, and `location`. Canceled events are omitted
and missing Google summaries are represented explicitly as `(untitled event)`.
The versioned cache includes generation time, coverage bounds, account and
calendar metadata, and normalized events. It is written atomically, with mode
`0600`, at:
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

Validate the plugin manifest before opening a pull request:

```bash
omarchy plugin validate .
python3 -m unittest discover -s tests -v
```

## Releases

Push a tag matching the version in `manifest.json`, such as `v0.2.0`, to run
the release workflow. It validates the project, builds a source archive,
generates SHA-256 checksums and an SPDX JSON SBOM, creates a GitHub release, and
records build provenance for the archive and checksums.
