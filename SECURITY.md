# Security Policy

## Supported versions

Security fixes are currently targeted at the latest `main` branch and the
latest published release. Older releases may not receive security updates.

## Deployment model

MultiDisplay is designed for a trusted local Mac-to-phone network:

- The dashboard binds to `127.0.0.1` by default. Keep that default unless the
  dashboard must be accessed from another machine.
- The receiver intentionally binds to the local network for Android and uses
  HTTP/MJPEG. It is not an Internet-facing service and does not provide TLS.
- Stream, cursor, and input endpoints require a session cookie issued after
  entering the pairing code. Pairing attempts are rate-limited per source IP.
- The pairing code and session cookie are bearer credentials. Do not publish
  them or expose the receiver port through port forwarding.
- Only connect devices you trust. The receiver can inject mouse and keyboard
  events into macOS after successful pairing.

For a more restrictive setup, bind the receiver to a specific LAN interface
with `--receiver-host` and use a firewall to limit access to the phone.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's **Report a
vulnerability** flow on the repository Security tab. Include the affected
version or commit, platform, reproduction steps, impact, and any proof of
concept needed to reproduce the issue. Do not open a public issue for an
unfixed security vulnerability.

If private reporting is unavailable, open a minimal issue requesting a private
contact channel without including exploit details.

## Scope

Reports involving authentication or pairing bypass, unintended remote input,
unauthorized frame access, secret exposure, unsafe default network behavior,
or dependency vulnerabilities are in scope. Issues requiring a user to
explicitly expose the service to the public Internet are still useful to
report, but the deployment warning above is part of the intended threat model.
