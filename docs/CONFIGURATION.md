# Configuration

Two places: environment variables (set in your compose file) and `overrides.yml` (a file you can edit while the container runs; it is re-read every `CACHE_SECONDS`).

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DOCKER_HOST` | `http://docker-socket-proxy:2375` | Docker API endpoint. Must be `http(s)`; use a read-only proxy, never the raw socket. |
| `RULES_FILE` | `/data/rules.json` | Output of `mydashboard.authelia_export`. |
| `OVERRIDES_FILE` | `/config/overrides.yml` | Optional exceptions file. |
| `CACHE_SECONDS` | `30` | How long the merged service list is cached. |
| `DASHBOARD_TITLE` | `Services` | Page title. |
| `LABEL_PREFIX` | `dynacat` | Label namespace to read (`<prefix>.name`, `.url`, `.icon`, `.description`). |
| `TRUST_TOKEN` | empty | If set, every request must carry `X-Dashboard-Token: <value>` (add it in your proxy). |
| `LLDAP_URL` | empty | Internal LLDAP address, e.g. `http://lldap:17170`. With the two below, enables "Change picture" in the account menu. |
| `LLDAP_USER` | empty | LLDAP service account (needs the `lldap_admin` group to edit other users). |
| `LLDAP_PASSWORD` / `LLDAP_PASSWORD_FILE` | empty | Its password, or a file holding it (Docker secret). |
| `DEV_MODE` | empty | `1` = act as a dev user when no `Remote-User` header is present. Never use in production. |

## `overrides.yml`

All keys are optional. See `config/overrides.example.yml` for a commented file.

| Key | Default | Meaning |
|---|---|---|
| `default_groups` | `[admins]` | Groups allowed on a service that has no override and no Authelia rule. |
| `always_allow` | `[admins]` | Groups that can open every service. |
| `lan_hosts` | `[]` | Hostnames that exist only on your LAN. They never match Authelia rules and get a LAN badge. Hosts without a dot and private IPs count as LAN automatically. |
| `public_only` | `false` | Drop services whose final URL is a LAN address. |
| `sso_only` | `false` | Keep only services that use your SSO (see below). |
| `auth_url` | empty | Your Authelia portal, e.g. `https://auth.example.com`. Enables "Account settings" and "Log out". |
| `public_url` | empty | This dashboard's address, where logout sends you back. |
| `hide` | `[]` | Services to hide from everyone. |
| `services` | `{}` | Per-service exceptions, keyed by name. |
| `extra` | `[]` | Extra tiles for things that have no label and no Authelia entry. |

### `services` entries

Keys are matched loosely against the container's `dynacat.name`, its container name, or the Authelia client id/name: `Open WebUI`, `open-webui` and `openwebui` are the same. Each entry can set:

- `groups`: allowed groups. `["*"]` means any signed-in user.
- `url`, `name`, `icon`, `description`: replace what the label says.
- `sso: true`: this service signs in through your SSO even though Authelia does not know it (an app using LDAP, for example). Only matters with `sso_only`.

### `extra` entries

`name`, `url`, optional `icon`, `description`, `groups` (defaults to `default_groups`) and `sso`.

### Icons

`sh:name` (selfh.st icons), `di:name` (Dashboard Icons), `si:name` (Simple Icons), `mdi:name` (Material Design Icons), or a full `https://` URL.

## How access is decided

For each service, in order:

1. `groups` from its `overrides.yml` entry,
2. else the matching Authelia entry (same host as the service URL, or same name as the OIDC client id/name),
3. else `default_groups`.

The signed-in user can use it if any of their groups (the `Remote-Groups` header) is allowed, or is in `always_allow`. If a service's label URL is a LAN address and Authelia knows a public URL for it, the public URL is used.

## What counts as "SSO"

With `sso_only: true` a service stays if it matched an Authelia entry (forward auth or OIDC) or has `sso: true` in its override. Everything else is dropped.

## Tracker ratios

Optional section at the top of the page showing downloaded / uploaded / ratio for each private tracker, read from [Prometheus](https://prometheus.io/) (for example from tracker exporters). Only members of `groups` (and `always_allow`) get the tiles; the data is fetched by the server, so other users never receive it.

```yaml
ratio:
  prometheus_url: http://prometheus:9090
  groups: [torrents, admins]
  trackers:
    - name: Tracker A
      url: https://tracker-a.example/   # optional: makes the tile a link
      metric: tracker_a        # reads tracker_a_total_downloaded_bytes and tracker_a_total_uploaded_bytes
    - name: Tracker B
      down: b_downloaded       # or name both metrics yourself
      up: b_uploaded
```

Results are cached for `2 * CACHE_SECONDS`. A tracker without metrics shows "No data"; if Prometheus is unreachable every tile shows "No data". A ratio under 1 is shown in red.

## Profile pictures (LLDAP)

Users pick an image in the account menu. The dashboard resizes it to a 256 px JPEG and stores it in the user's LLDAP `avatar` attribute through LLDAP's GraphQL API, so LLDAP does not need to be reachable from the internet. Any app that reads `jpegPhoto` from LDAP shows it too.

- Put the dashboard on LLDAP's Docker network and set the three `LLDAP_*` variables.
- Create a dedicated service account for it. LLDAP only lets `lldap_admin` edit other users, so this account is powerful: keep its password in a secret and set `TRUST_TOKEN` so only your proxy can reach the dashboard.
- The dashboard only ever reads or writes the user named by the `Remote-User` header. Uploads need an `X-Requested-With` header, so a foreign site cannot post a picture for a signed-in user.
