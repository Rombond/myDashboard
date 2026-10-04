# Deploying behind Caddy + Authelia

## 1. Run the stack
Use `docker-compose.example.yml`. Keep `config/overrides.yml` and `data/rules.json` next to it.

## 2. Keep the Authelia export fresh
`rules.json` is a snapshot. Regenerate it whenever Authelia's rules change, or on a schedule:

```cron
*/15 * * * * PYTHONPATH=/path/to/myDashboard/src python3 -m mydashboard.authelia_export /path/to/authelia/configuration.yml /path/to/myDashboard/data/rules.json
```
Needs Python 3 with PyYAML on the host (or run the same command in a throwaway container with the config mounted read-only).

## 3. Authelia rule
Let every group that should see the page in, for example:

```yaml
access_control:
  rules:
    - domain: ['apps.example.com']
      subject: ['group:users', 'group:admins']
      policy: two_factor
```

## 4. Caddy
```caddyfile
apps.example.com {
    forward_auth authelia:9091 {
        uri /api/authz/forward-auth
        copy_headers Remote-User Remote-Groups Remote-Email Remote-Name
    }
    reverse_proxy dashboard:8080 {
        # header_up X-Dashboard-Token change-me   # only if TRUST_TOKEN is set
    }
}
```
Optionally set Authelia's `default_redirection_url` to this address so people land on the dashboard after signing in.
