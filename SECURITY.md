# Security Policy

## Supported Version

Selects is currently a local-first alpha. Security fixes are applied to the latest minor release and the latest commit on `main`; older snapshots are not supported.

## Local security boundary

- The local server binds to loopback and rejects unexpected Host headers.
- Project-changing requests require JSON and browser responses use a restrictive content-security policy.
- The media route resolves only source IDs already stored in the project; it does not accept filesystem paths.
- Originals are read-only inputs. Selects writes its database, cache, previews, backups, and exports under its application-data directory.
- An OpenAI key entered in the Assistant tab is held for one request, is not logged or stored in SQLite, and is sent only to OpenAI's Responses API.
- Imported proposals remain pending until a user accepts them.

The localhost service is not designed for exposure on a LAN or the public internet. Do not run it behind a public proxy.

## Reporting A Vulnerability

Please use GitHub's private **Report a vulnerability** flow in the repository's Security tab. Do not open a public issue containing credentials, personal data, exploit details, or private user content.

Include:

- the affected file, endpoint, or workflow;
- steps to reproduce;
- the impact you observed;
- whether any secret or personal data may have been exposed; and
- a safe way to confirm the fix.

Do not test against live user data or third-party accounts without explicit authorization.
