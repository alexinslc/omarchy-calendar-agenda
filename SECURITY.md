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

Marketplace verification is an additional provenance check, not a substitute
for source review or a complete security audit.

