"""Merge Docker labels, Authelia rules and overrides into the per-user service list."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .config import Overrides, norm
from .discovery import DockerService
from .icons import icon_url

ANY = "*"


@dataclass
class Service:
    key: str
    name: str
    url: str
    icon: str | None
    description: str
    groups: list[str]
    source: str  # docker | authelia | override | extra
    lan: bool = False
    always: list[str] = field(default_factory=list)
    sso: bool = False  # signs in through Authelia (forward auth / OIDC) or LDAP

    def allowed_for(self, user_groups: set[str]) -> bool:
        if ANY in self.groups:
            return True
        return bool(user_groups & (set(self.groups) | set(self.always)))


def load_rules(path: str) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text()).get("entries", [])
    except (OSError, ValueError):
        return []


def _is_lan(url: str, lan_hosts: list[str]) -> bool:
    host = urlparse(url).hostname or ""
    if host in lan_hosts or "." not in host:
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def build_catalog(docker: list[DockerService], entries: list[dict], ov: Overrides) -> list[Service]:
    by_host = {e["host"]: e for e in entries if e.get("host") and e["host"] not in ov.lan_hosts}
    by_name: dict[str, dict] = {}
    for e in entries:
        by_name.setdefault(norm(e["id"]), e)
        by_name.setdefault(norm(e["name"]), e)

    used: set[int] = set()
    out: dict[str, Service] = {}

    def add(s: Service) -> None:
        if s.key and s.key not in ov.hide:
            out.setdefault(s.key, s)

    for d in docker:
        key = norm(d.name)
        o = ov.services.get(key) or ov.services.get(norm(d.container)) or {}
        host = urlparse(d.url).hostname
        entry = by_host.get(host) or by_name.get(key)
        if entry:
            used.add(id(entry))
        groups = o.get("groups") or (entry["groups"] if entry else None) or ov.default_groups
        url = o.get("url") or d.url
        if not o.get("url") and entry and entry.get("url") and _is_lan(d.url, ov.lan_hosts):
            url = entry["url"]  # prefer the public address over host:port
        add(Service(key, o.get("name", d.name), url, o.get("icon", d.icon),
                    o.get("description", d.description), list(groups),
                    "authelia" if entry and not o.get("groups") else "docker",
                    _is_lan(url, ov.lan_hosts), ov.always_allow, bool(o.get("sso", entry is not None))))

    # Authelia knows services that carry no container label (e.g. Shelfmark, CWA).
    for e in entries:
        if id(e) in used or not e.get("url") or urlparse(e["url"]).hostname in ov.lan_hosts:
            continue
        key = norm(e["name"])
        o = ov.services.get(key) or ov.services.get(norm(e["id"])) or {}
        add(Service(key, o.get("name", e["name"]), o.get("url", e["url"]), o.get("icon"),
                    o.get("description", ""), list(o.get("groups") or e["groups"]),
                    "authelia", False, ov.always_allow, bool(o.get("sso", True))))

    for x in ov.extra:
        key = norm(x["name"])
        add(Service(key, x["name"], x["url"], x.get("icon"), x.get("description", ""),
                    list(x.get("groups") or ov.default_groups), "extra",
                    _is_lan(x["url"], ov.lan_hosts), ov.always_allow, bool(x.get("sso", False))))

    services = [s for s in out.values()
                if not (ov.public_only and s.lan) and not (ov.sso_only and not s.sso)]
    return sorted(services, key=lambda s: s.name.lower())


def view_for(services: list[Service], user_groups: set[str]) -> list[dict]:
    """Template/JSON-ready dicts; allowed services first."""
    rows = [
        {"key": s.key, "name": s.name, "url": s.url, "icon": icon_url(s.icon),
         "description": s.description, "lan": s.lan, "source": s.source,
         "allowed": s.allowed_for(user_groups),
         "needs": [g for g in s.groups if g != ANY]}
        for s in services
    ]
    return sorted(rows, key=lambda r: (not r["allowed"], r["name"].lower()))
