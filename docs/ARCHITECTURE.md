# Architecture

```
 browser ──► reverse proxy ──forward_auth──► Authelia
                 │  (adds Remote-User / Remote-Groups / Remote-Name / Remote-Email)
                 ▼
           myDashboard (Flask + gunicorn)
             ├─ discovery.py   container labels   ◄── docker-socket-proxy ◄── Docker
             ├─ access.py      merge + decide     ◄── rules.json (Authelia export), overrides.yml
             └─ app.py         page + JSON API
```

## Modules (`src/mydashboard/`)

| File | Role |
|---|---|
| `discovery.py` | Reads `/containers/json` from the Docker API proxy and keeps containers with a name and a URL. |
| `authelia_export.py` | Standalone exporter: reads Authelia's `configuration.yml` and writes a sanitized `rules.json` (host, name, allowed groups). Run it by cron. |
| `access.py` | Merges the three sources into `Service` objects and decides, per user, which are usable. |
| `config.py` | Environment settings and the `overrides.yml` loader. |
| `icons.py` | Turns `sh:`, `di:`, `si:`, `mdi:` icon references into image URLs. |
| `app.py` | Flask app: `/` (HTML), `/api/services` (JSON), `/healthz`. Reads identity from the `Remote-*` headers. |
| `demo.py` | Runs the app with the fake data in `demo/`. |
| `templates/`, `static/` | One HTML template and one stylesheet, no JavaScript framework. |

## Why an export step

Authelia has no API to list its access rules. The only source is its configuration file, which also contains the OIDC signing key and client secret digests. Mounting that file into a web-facing container would expose those if the container were compromised, so a separate script extracts only domains and group names into `rules.json`, and the dashboard only mounts that.

## Request flow

1. The proxy asks Authelia to authenticate the request and copies its headers.
2. `app.py` rejects requests without `Remote-User` (401), or without the right `X-Dashboard-Token` when `TRUST_TOKEN` is set (403).
3. The cached service list (rebuilt every `CACHE_SECONDS`) is filtered into "usable" and "not usable" for the user's groups, usable ones first.
4. If the Docker proxy is down, the last good list keeps being served.

## Matching rules (Authelia entry to container)

- By host: the host of the service URL equals the host of the Authelia domain or OIDC redirect URI (LAN hosts excluded).
- Or by name: the container's `dynacat.name`, normalized (lowercase, letters and digits only), equals the OIDC client id or name.

An Authelia entry with no matching container still becomes a tile (that is how services without labels show up).
