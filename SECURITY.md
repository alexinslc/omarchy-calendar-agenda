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

- Only read-only Google Calendar scopes are permitted.
- OAuth must use authorization-code PKCE, a random state value, and a
  loopback-only callback.
- Refresh tokens must be stored through the Linux Secret Service, never in
  source, logs, command-line arguments, or plaintext fallback files.
- Network destinations must be fixed Google HTTPS endpoints.
- Event content is untrusted input and must be rendered as plain text.
- Event links may only be opened after an explicit user action and must use
  HTTPS.
- No shell execution, arbitrary URL fetching, dynamic code loading, or
  elevated privileges.
- The helper may invoke `secret-tool` only with an argument list and token
  input on stdin; it never uses `shell=True`. OAuth and API URLs are fixed
  constants, and the only non-HTTPS URL is the 127.0.0.1 callback.
- The cache path is
  `~/.local/state/omarchy/calendar-agenda/events.json`; its parent directory
  is mode `0700` and the file is mode `0600`, replaced with `os.replace` after
  flush and `fsync`.

The configuration file is
`~/.config/omarchy/calendar-agenda/config.json` and contains only a Google
OAuth client ID plus local account IDs. The client ID is not a secret. The
helper currently performs an explicit one-shot sync; a 15-minute scheduler and
QML cache consumption are intentionally deferred.

Marketplace verification is an additional provenance check, not a substitute
for source review or a complete security audit.
