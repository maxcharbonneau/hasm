# Security Policy

HASM handles Home Assistant access tokens, so security reports are taken seriously.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Instead, report it privately using GitHub's **"Report a vulnerability"** feature
(repository **Security** tab → *Report a vulnerability*). If that is unavailable, contact the
maintainer directly.

You will receive an acknowledgement as soon as possible, and updates as the issue is addressed.

## Handling of secrets

- Access tokens are stored in Home Assistant's encrypted config entry store and are never logged.
- HASM only contacts the remote instances you explicitly configure.

## Supported versions

The latest released version receives security fixes.
