# Changelog

## 1.0.1

- Profile pictures: "Change picture" in the account menu stores a resized JPEG in LLDAP (`LLDAP_URL`, `LLDAP_USER`, `LLDAP_PASSWORD`).
- Tracker ratio tiles (down / up / ratio) read from Prometheus, shown only to the groups listed under `ratio.groups`.
- Ratio tiles: optional `url` per tracker turns the tile into a link (http/https only).

## 1.0.0

First version.

- Discovery of services from `dynacat.*` container labels through a read-only Docker API proxy.
- Access rules read from a sanitized export of Authelia's configuration (forward-auth domains and OIDC clients).
- `overrides.yml` for exceptions: groups, URLs, names, icons, hidden and extra services.
- Per-user page with unavailable services crossed out; JSON API at `/api/services`.
- Options `public_only` and `sso_only`.
- Account menu with identity, groups, settings and logout links; theme switch and "open in a new tab" checkbox.
- Demo mode with fake data (`python -m mydashboard.demo`).
