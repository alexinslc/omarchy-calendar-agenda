# Calendar Agenda

A read-only Google Calendar agenda for the [Omarchy](https://omarchy.org) bar.
Click the calendar icon to see your day, week, or month without opening a
browser. The panel follows your active Omarchy theme.

| Tokyo Night · Week | Catppuccin Latte · Day | Matte Black · Month |
| --- | --- | --- |
| <img src="https://omarchy.alexinslc.com/assets/tokyo-night-week.png" alt="Calendar Agenda showing the week under Tokyo Night" width="280"> | <img src="https://omarchy.alexinslc.com/assets/catppuccin-latte-day.png" alt="Calendar Agenda showing the day under Catppuccin Latte" width="280"> | <img src="https://omarchy.alexinslc.com/assets/matte-black-month.png" alt="Calendar Agenda showing the month under Matte Black" width="280"> |

[Watch the 13-second demo](https://youtu.be/VsQA0hfj4d4) ·
[Plugin website](https://omarchy.alexinslc.com/calendar-agenda/) ·
[Privacy policy](https://omarchy.alexinslc.com/calendar-agenda/privacy/)

## Install

```bash
omarchy plugin add https://github.com/alexinslc/omarchy-calendar-agenda.git --enable
```

Open the new calendar icon and choose **Connect Google Calendar**. Approve
read-only access in your browser, then return to the panel. The first sync runs
automatically and refreshes every 15 minutes.

Calendar Agenda uses only components already included with Omarchy. It does not
install third-party Python modules, npm packages, or privileged services.

## Features

- Day, week, and month agenda views
- Multiple Google accounts and calendar filters
- All-day and timed events with optional calendar and location details
- 12- or 24-hour time
- Theme-aware colors, borders, and typography
- Keyboard shortcuts: `D`, `W`, `M`, `T`, `[` and `]`
- Clear sync status and reconnect controls

The synchronized window covers today through the next 28 days.

## Accounts

Add another account from **Settings → Add account**.

To disconnect one, choose **Remove** beside the account. Calendar Agenda
revokes its Google access, removes its stored credential, and purges that
account's local events. If Google is unavailable, **Remove locally anyway**
cleans up the local credential and cache without remote revocation.

Remove connected accounts before uninstalling the plugin.

## Privacy

- Google access is limited to calendar-list and event read-only scopes.
- Sign-in happens in the system browser using PKCE.
- Refresh tokens are stored in Linux Secret Service.
- Calendar data stays in private local files on your computer.
- The project does not operate a server that receives your Google account,
  calendars, events, authorization codes, or tokens.

See the [Privacy Policy](https://omarchy.alexinslc.com/calendar-agenda/privacy/)
and [Security Policy](SECURITY.md) for details.

## Diagnostics

Run these from the installed plugin directory:

```bash
python3 calendar_agenda.py --status
python3 calendar_agenda.py --doctor
python3 calendar_agenda.py --sync --json
```

## Uninstall

After removing connected accounts:

```bash
omarchy plugin remove io.github.alexinslc.calendar-agenda
```

## Development

```bash
omarchy plugin validate .
python3 -m unittest discover -s tests -v
timeout 5s env QT_QPA_PLATFORM=offscreen quickshell -p model_test.qml
```

The Quickshell test is successful when it prints `agenda model tests passed`;
the timeout is expected because the test configuration has no quit handler.

For local OAuth development, copy `oauth-client.example.json` to
`~/.config/omarchy/calendar-agenda/config.json`, add credentials from a private
Google Cloud Desktop client, and set the file mode to `0600`.

## License

[MIT](LICENSE)
