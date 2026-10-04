"""Export a sanitized view of Authelia's access rules (domains + groups only).

Reads Authelia's configuration.yml and writes a small JSON file. The dashboard only ever
sees that JSON, never the configuration (which holds the OIDC signing key and digests).

    python -m mydashboard.authelia_export /path/configuration.yml /path/rules.json

Each entry: {id, name, host, url, groups, source}. `groups` is the list of LDAP/LLDAP
groups allowed (`["*"]` = any authenticated user, `[]` = nobody).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import yaml

ANY = "*"


def _groups_from_rules(rules: list[dict], default_policy: str, notes: list[str], ctx: str) -> list[str]:
    """Union of the groups of every non-deny rule; any rule without subject opens it to all."""
    groups: list[str] = []
    for rule in rules or []:
        if rule.get("policy") == "deny":
            continue
        subject = rule.get("subject")
        if not subject:
            return [ANY]
        for item in subject if isinstance(subject, list) else [subject]:
            if isinstance(item, list):  # AND-combination: too specific for a dashboard
                notes.append(f"{ctx}: AND subject {item} ignored")
                continue
            if item.startswith("group:"):
                groups.append(item[6:])
            else:
                notes.append(f"{ctx}: subject {item!r} ignored")
    if not groups and default_policy not in ("deny", None):
        return [ANY]
    return sorted(set(groups))


def export_rules(config: dict) -> dict:
    notes: list[str] = []
    entries: list[dict] = []

    # Forward-auth protected domains.
    ac = config.get("access_control", {}) or {}
    for i, rule in enumerate(ac.get("rules", []) or []):
        domains = rule.get("domain") or rule.get("domain_regex") or []
        for dom in domains if isinstance(domains, list) else [domains]:
            if "*" in dom:
                notes.append(f"rule {i}: wildcard domain {dom!r} skipped")
                continue
            groups = _groups_from_rules([rule], ac.get("default_policy"), notes, f"rule {i}")
            entries.append(
                {"id": dom, "name": dom.split(".")[0].capitalize(), "host": dom,
                 "url": f"https://{dom}/", "groups": groups, "source": "forward_auth"}
            )

    # OIDC clients, whose access is the policy they reference.
    oidc = (config.get("identity_providers", {}) or {}).get("oidc", {}) or {}
    policies = oidc.get("authorization_policies", {}) or {}
    for client in oidc.get("clients", []) or []:
        policy = client.get("authorization_policy", "two_factor")
        if policy in policies:
            p = policies[policy]
            groups = _groups_from_rules(p.get("rules", []), p.get("default_policy", "deny"),
                                        notes, f"client {client.get('client_id')}")
        else:  # built-in one_factor / two_factor = any authenticated user
            groups = [ANY]
        host, url = None, None
        for uri in client.get("redirect_uris", []) or []:
            u = urlparse(uri)
            if u.scheme == "https" and u.hostname:
                host, url = u.hostname, f"https://{u.hostname}/"
                break
        entries.append(
            {"id": client["client_id"], "name": client.get("client_name", client["client_id"]),
             "host": host, "url": url, "groups": groups, "source": "oidc"}
        )

    return {"generated": int(time.time()), "entries": entries, "notes": notes}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    config = yaml.safe_load(Path(argv[1]).read_text())
    data = export_rules(config)
    out = Path(argv[2])
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(out)
    print(f"{len(data['entries'])} entries -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
