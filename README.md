# myDashboard

A tiny dashboard that shows **every service of your homelab, with the ones the signed-in user may not use crossed out**. It sits behind [Authelia](https://www.authelia.com/) (forward auth) and needs no database.

Services come from three places, merged in this order:

1. **Docker labels** (Dynacat/Glance style: `dynacat.name`, `dynacat.url`, `dynacat.icon`, `dynacat.description`, `dynacat.parent`). New containers appear by themselves.
2. **Authelia's own rules** (forward-auth domains and OIDC clients), exported to a small JSON file. This gives the allowed groups with nothing to maintain, and also lists services that have no label.
3. **`overrides.yml`** for what neither can know (apps with their own login, LAN-only apps, hidden services).

Anything without a rule falls back to `default_groups`, so a new service is never open by accident.

## How it decides

For each service: `overrides` groups, else the matching Authelia entry (matched by host or by name), else `default_groups`. A user sees a tile as usable when one of their groups (from Authelia's `Remote-Groups` header) is allowed, or when they are in `always_allow`. A service whose label URL is a LAN address is shown with its public URL if Authelia knows one.

## Run

```bash
cp config/overrides.example.yml config/overrides.yml
mkdir -p data
# Export the rules (the dashboard never reads Authelia's config itself, only this sanitized file):
PYTHONPATH=src python3 -m mydashboard.authelia_export /path/to/authelia/configuration.yml data/rules.json
docker compose -f docker-compose.example.yml up -d
```

See [docs/DEPLOY.md](docs/DEPLOY.md) for the reverse-proxy and Authelia side.

## Configuration (environment)

| Variable | Default | Meaning |
|---|---|---|
| `DOCKER_HOST` | `http://docker-socket-proxy:2375` | Docker API endpoint (use a read-only proxy) |
| `RULES_FILE` | `/data/rules.json` | Output of `authelia_export` |
| `OVERRIDES_FILE` | `/config/overrides.yml` | Optional exceptions |
| `CACHE_SECONDS` | `30` | How long the merged list is cached |
| `DASHBOARD_TITLE` | `Services` | Page title |
| `LABEL_PREFIX` | `dynacat` | Label namespace to read |
| `TRUST_TOKEN` | empty | If set, requests must carry `X-Dashboard-Token: <value>` (set it in your proxy) |
| `DEV_MODE` | empty | `1` = act as a dev user when no `Remote-User` header is sent |

## Security notes

- Identity is taken from `Remote-User` / `Remote-Groups`, so the dashboard must only be reachable through the proxy that runs Authelia. Do not publish its port; use `TRUST_TOKEN` if other hosts can reach it.
- The page is a list of links. Access is still enforced by Authelia and by each app.
- The Docker socket is never mounted into the dashboard. Use `docker-socket-proxy` with `CONTAINERS=1` only.

## Develop

```bash
pip install -r requirements-dev.txt
python -m pytest -q
DEV_MODE=1 PYTHONPATH=src python -m mydashboard.app
```
