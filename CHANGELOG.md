# Changelog

## 1.0.0

First version.

- Discovery of services from `dynacat.*` container labels through a read-only Docker API proxy.
- Access rules read from a sanitized export of Authelia's configuration (forward-auth domains and OIDC clients).
- `overrides.yml` for exceptions: groups, URLs, names, icons, hidden and extra services.
- Per-user page with unavailable services crossed out; JSON API at `/api/services`.
- Options `public_only` and `sso_only`.
- Account menu with identity, groups, settings and logout links; theme switch and "open in a new tab" checkbox.
- Demo mode with fake data (`python -m mydashboard.demo`).
