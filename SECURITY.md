# Security Policy

## Scope

This project contains an unsandboxed Omarchy Quickshell plugin and a local
Google Calendar synchronization helper. A vulnerability may expose calendar
data, OAuth credentials, or the user's local account.

## Reporting

Do not open a public issue for suspected security vulnerabilities. Use GitHub's
private vulnerability reporting for this repository. Include the affected
commit, reproduction steps, impact, and any relevant logs with credentials
removed.

## Security requirements

- Only Google identity plus read-only calendar-list and event scopes are
  permitted.
- OAuth must use authorization-code PKCE, a random state value, and a
  loopback-only callback.
- Refresh tokens must be stored through the Linux Secret Service, never in
  source, logs, command-line arguments, or plaintext fallback files.
- Network destinations must be fixed Google HTTPS endpoints plus the exact
  production configuration endpoint on `calendar.alexinslc.com`.
- Event content is untrusted input and must be rendered as plain text.
- Event links may only be opened after an explicit user action and must use
  HTTPS.
- No shell execution, arbitrary URL fetching, dynamic code loading, or
  elevated privileges. QML may start only the bundled `calendar_agenda.py`
  entry point with fixed argument arrays for explicit account actions.
- The helper may invoke `secret-tool` only with an argument list and token
  input on stdin; it never uses `shell=True`. OAuth, API, and configuration
  URLs are fixed constants, and the only non-HTTPS URL is the 127.0.0.1
  callback.
- The cache path is
  `~/.local/state/omarchy/calendar-agenda/events.json`; its parent directory
  is mode `0700` and the file is mode `0600`, replaced with `os.replace` after
  flush and `fsync`.

Production OAuth client credentials are stored as encrypted Cloudflare Worker
secret bindings, never in Git or release archives. The Worker returns only the
distributable desktop-client configuration and never receives Google user data,
authorization codes, or tokens. The plugin validates and caches that
configuration with mode `0600`; developers may use the mode-`0600` private
override at `~/.config/omarchy/calendar-agenda/config.json`. The private account
registry contains stable provider identifiers and display metadata but never
tokens.
Refresh tokens remain exclusively in Secret Service. The helper can run as an
explicit one-shot sync or through the bundled 15-minute systemd user timer. QML
consumes only structured helper output and the versioned local cache, rejecting
malformed, expired, or unsupported data.

Removing an account revokes its Google grant when reachable, clears its Secret
Service entry, and purges its cached data. A user may explicitly choose local
removal when remote revocation is unavailable.

Marketplace verification is an additional provenance check, not a substitute
for source review or a complete security audit.
