# Omarchy Calendar Agenda

A lightweight, agenda-focused Google Calendar widget for Omarchy.

This project is in prototype development. It is intended to provide a
top-right bar icon with compact day, week, and month agenda views. The first
Google integration will use read-only OAuth and support multiple accounts and
calendars.

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
source of truth and can move the widget to another section. The popup is
fixture-backed only. Edit `fixtures/events.json` and reload the shell to try
different events. Google OAuth, networking, event links, and cache syncing are
intentionally out of scope for this prototype.

If a local Quickshell runtime is available, model checks can be run with:

```bash
timeout 5s env QT_QPA_PLATFORM=offscreen quickshell -p model_test.qml
```

The test prints `agenda model tests passed`; the timeout is expected because a
standalone Quickshell config has no application-level quit handler.
