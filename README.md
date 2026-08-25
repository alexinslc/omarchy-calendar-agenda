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

- Google access uses the narrow calendar-list and event read-only scopes.
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

Open the calendar icon after installation. On first run, choose **Connect
Google Calendar**, complete Google's consent screen in the browser, and return
to the panel. The plugin stores the token in Secret Service, performs the first
sync, and enables its 15-minute user timer automatically.

A production release must include the project's public Google desktop OAuth
client configuration. A source checkout without that configuration displays a
clear unavailable message instead of starting an incomplete authorization.

See [PRIVACY.md](PRIVACY.md) for how Google account and calendar data is used,
stored, and deleted.

## Development

This first prototype uses the eventual permanent plugin ID:
`io.github.alexinslc.calendar-agenda`. No temporary clone is needed.

For local development, copy every runtime component without a network checkout:

```bash
mkdir -p ~/.config/omarchy/plugins/io.github.alexinslc.calendar-agenda
cp manifest.json AgendaBarWidget.qml AgendaPanel.qml AgendaModel.js \
  CompactToggle.qml SettingsPanel.qml OnboardingService.qml \
  OnboardingPanel.qml calendar_agenda.py \
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
Open the panel's gear button to add, reconnect, synchronize, or remove Google
accounts and configure displayed event fields, account visibility, and
calendar visibility. These display preferences are stored at
`~/.local/state/omarchy/calendar-agenda/settings.json`.

## Account onboarding

### Add an account

Choose **Connect Google Calendar** on the first-run screen, or **Add account**
in Settings. Authorization uses the system browser, authorization-code PKCE, a
random state value, and a loopback-only callback. The plugin requests only
basic account identity plus read-only calendar-list and event access.

After consent, the plugin discovers the Google identity, generates a private
local account ID, stores the refresh token in Linux Secret Service, runs the
first sync, and enables background synchronization. Connecting the same Google
account twice is rejected.

### Remove an account

Choose **Remove** beside the account in Settings and confirm. Calendar Agenda
revokes its Google grant, deletes its Secret Service entry, removes the local
registry record, and immediately purges that account's cached events. It never
deletes calendars or events in Google. If Google is unreachable, the panel
offers **Remove locally anyway** so local data can still be erased.

Removing the last account also disables the plugin-owned synchronization
timer. Remove all connected accounts before uninstalling the plugin so tokens,
cache data, and timer units are cleaned up.

### Account health and recovery

One broken account does not prevent healthy accounts from synchronizing.
Settings marks failed accounts as **Needs attention** and provides
**Reconnect**. **Sync now** refreshes every connected account immediately.

For diagnostics from the installed plugin directory:

```bash
python3 calendar_agenda.py --status
python3 calendar_agenda.py --doctor
python3 calendar_agenda.py --sync --json
```

The account registry and per-account health record are private files at
`~/.local/state/omarchy/calendar-agenda/accounts.json` and
`sync-status.json`. Refresh tokens never appear in those files, command-line
arguments, or logs.

## OAuth configuration for development

Release builds use a bundled `oauth-client.json` containing the project's
public Google desktop OAuth client configuration. Developers can instead copy
`oauth-client.example.json` to the private override below and supply a desktop
client ID from a Google Cloud test project:

```bash
mkdir -p ~/.config/omarchy/calendar-agenda
cp oauth-client.example.json ~/.config/omarchy/calendar-agenda/config.json
chmod 600 ~/.config/omarchy/calendar-agenda/config.json
```

Enable the Google Calendar API and configure the test project's consent screen
for these scopes:

- `openid`
- `email`
- `https://www.googleapis.com/auth/calendar.calendarlist.readonly`
- `https://www.googleapis.com/auth/calendar.events.readonly`

The optional `client_secret` may be left empty for a public desktop client.
Older private configurations with an `accounts` list are migrated into the
account registry; those accounts are labeled for a one-time reconnect.

The helper lists every calendar for every connected account, follows API
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
