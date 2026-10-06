"""Runtime settings (environment) and the optional overrides file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Settings:
    docker_host: str = "http://docker-socket-proxy:2375"
    rules_file: str = "/data/rules.json"
    overrides_file: str = "/config/overrides.yml"
    cache_seconds: int = 30
    title: str = "Services"
    trust_token: str = ""
    dev_mode: bool = False
    label_prefix: str = "dynacat"

    @classmethod
    def from_env(cls) -> Settings:
        e = os.environ.get
        return cls(
            docker_host=e("DOCKER_HOST", cls.docker_host).replace("tcp://", "http://"),
            rules_file=e("RULES_FILE", cls.rules_file),
            overrides_file=e("OVERRIDES_FILE", cls.overrides_file),
            cache_seconds=int(e("CACHE_SECONDS", cls.cache_seconds)),
            title=e("DASHBOARD_TITLE", cls.title),
            trust_token=e("TRUST_TOKEN", ""),
            dev_mode=e("DEV_MODE", "") == "1",
            label_prefix=e("LABEL_PREFIX", cls.label_prefix),
        )


@dataclass
class Overrides:
    """Hand-written exceptions: what Docker labels and Authelia cannot tell us."""

    default_groups: list[str] = field(default_factory=lambda: ["admins"])
    always_allow: list[str] = field(default_factory=lambda: ["admins"])
    lan_hosts: list[str] = field(default_factory=list)
    public_only: bool = False
    sso_only: bool = False
    auth_url: str = ""      # Authelia portal, e.g. https://auth.example.com (enables the account menu links)
    public_url: str = ""    # this dashboard's address, where logout sends you back
    hide: list[str] = field(default_factory=list)
    prometheus_url: str = ""                     # enables the ratio section, e.g. http://prometheus:9090
    ratio_groups: list[str] = field(default_factory=lambda: ["admins"])
    ratio_trackers: list[dict] = field(default_factory=list)   # [{name, metric | down + up}]
    # normalized service name -> {groups, url, name, icon, description}
    services: dict[str, dict] = field(default_factory=dict)
    extra: list[dict] = field(default_factory=list)


def norm(value: str) -> str:
    """Normalize a name for matching: 'Open WebUI' == 'open-webui'."""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def load_overrides(path: str) -> Overrides:
    p = Path(path)
    if not p.is_file():
        return Overrides()
    data = yaml.safe_load(p.read_text()) or {}
    o = Overrides()
    o.default_groups = list(data.get("default_groups", o.default_groups))
    o.always_allow = list(data.get("always_allow", o.always_allow))
    o.lan_hosts = list(data.get("lan_hosts", []))
    o.public_only = bool(data.get("public_only", False))
    o.sso_only = bool(data.get("sso_only", False))
    o.auth_url = str(data.get("auth_url", "")).rstrip("/")
    o.public_url = str(data.get("public_url", "")).rstrip("/")
    ratio = data.get("ratio") or {}
    o.prometheus_url = str(ratio.get("prometheus_url", "")).rstrip("/")
    o.ratio_groups = list(ratio.get("groups", o.ratio_groups))
    o.ratio_trackers = [
        t for t in ratio.get("trackers", []) if t.get("name") and (t.get("metric") or (t.get("down") and t.get("up")))
    ]
    for t in o.ratio_trackers:
        t.setdefault("metric", "")
    o.hide = [norm(x) for x in data.get("hide", [])]
    o.services = {norm(k): (v or {}) for k, v in (data.get("services") or {}).items()}
    o.extra = list(data.get("extra", []))
    return o
