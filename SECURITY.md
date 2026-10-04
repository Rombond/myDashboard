# Security

## Reporting a vulnerability

Please report problems privately through GitHub's "Report a vulnerability" (Security tab) instead of a public issue. This is a hobby project written with AI assistance: expect a best-effort response.

## Trust model

- **Identity comes from HTTP headers** (`Remote-User`, `Remote-Groups`, ...). Whoever can reach the dashboard directly can claim to be anybody. Only expose it through a reverse proxy that runs Authelia's forward auth, and do not publish the container port to the internet or untrusted networks.
- Set **`TRUST_TOKEN`** and have the proxy send `X-Dashboard-Token` if other machines on your network can reach the port.
- The page only **lists links**. Hiding or crossing out a tile is not access control: Authelia and each application must still enforce who can open what.
- The tooltip on a crossed-out tile shows the group names needed. If group names are sensitive in your setup, do not use this dashboard.

## What the dashboard can access

- **Docker**: only the container list, through `docker-socket-proxy` with `CONTAINERS=1` and `POST=0`. Never mount `/var/run/docker.sock` into the dashboard.
- **Authelia**: nothing at runtime. A separate export writes `rules.json` (domains and group names only). Keep `configuration.yml` out of the container.
- **No secrets** are stored by the dashboard. Do not commit `config/overrides.yml` or `data/`; they are in `.gitignore`.

## Other notes

- The page loads icons from public CDNs in the visitor's browser.
- The container runs as an unprivileged user.
- This code has **not been independently audited** (see the README).
