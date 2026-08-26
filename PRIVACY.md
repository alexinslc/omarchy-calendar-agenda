# Privacy Policy

Last updated: August 25, 2026

Omarchy Calendar Agenda is a local desktop plugin that shows events from the
Google calendars a user explicitly connects.

## Google data accessed

The plugin requests the user's basic Google account identity (stable account
identifier and email address), the list of calendars available to that
account, and read-only access to calendar events. It cannot create, modify, or
delete Google calendars or events.

## How data is used

Google account identity is used to label connected accounts and prevent the
same account from being connected twice. Calendar names and events are used
only to display the local agenda selected by the user.

The plugin does not sell Google user data, use it for advertising, transfer it
to an external service, or use it to train machine-learning models. Its use of
Google user data adheres to the Google API Services User Data Policy, including
the Limited Use requirements.

## Storage and sharing

OAuth refresh tokens are stored in the user's Linux Secret Service. Account
metadata, synchronization status, calendar metadata, and a rolling local event
cache are stored only on the user's computer under private user permissions.
On first use and at most once per day afterward, the plugin contacts
`calendar.alexinslc.com` to retrieve its distributable Google desktop-client
configuration. That endpoint does not receive Google authorization codes,
tokens, account identity, calendars, or events. The project does not operate a
server that receives Google user data, and the plugin does not share Google
user data with the project maintainer or third parties.

## Retention and deletion

The event cache covers approximately 28 days and is replaced during
synchronization. Removing an account from Calendar Agenda revokes the Google
authorization when Google is reachable, deletes the local refresh token,
removes the account registry entry, and immediately purges that account's
cached calendar data. Users may also revoke access from their Google Account
permissions page.

## Security and questions

Security issues should be reported through this repository's private
vulnerability reporting process as described in `SECURITY.md`. General privacy
questions may be opened in the repository issue tracker without including
calendar contents, OAuth tokens, or other private account information.
