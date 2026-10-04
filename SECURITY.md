# Security Policy

## Supported versions

Fixes go into the newest release only. The version is shown in **Settings → About** inside the
app, and in the release name on the [Releases page](https://github.com/QuAndy2016/SerialDesk/releases).

| Version | Supported |
| --- | --- |
| The latest release | ✅ |
| Anything older | ❌ — please update first and retry |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private advisory form: **[Report a vulnerability](https://github.com/QuAndy2016/SerialDesk/security/advisories/new)**
(also reachable from the repository's **Security** tab → *Report a vulnerability*).

Helpful details:

- what you did, what you expected, what happened;
- the app version (**Settings → About** copies it, together with the diagnostics) and your
  Windows version;
- the smallest input that reproduces it — a received byte sequence, a saved log excerpt, or a
  specification file, if one is involved;
- **redact anything device-specific** you would rather not share; a trimmed example with the
  same shape is usually enough.

## What to expect

1. An acknowledgement, normally within a few days.
2. An assessment: either a fix plan with a version, or an explanation of why the report is not a
   vulnerability in this application.
3. Credit in the release notes, if you want it.

## Scope

**In scope** — the application itself: parsing received data, reading and writing its own
configuration and logs, the update check, and the installer.

**Out of scope** — vulnerabilities in third-party components (please report those upstream:
Python, PySide6, pySerial), and anything that requires an already-compromised machine.

## Privacy note

The application works offline. The only outbound request it makes is the optional update check,
which asks the public releases API for the newest tag; it sends nothing about this machine.
