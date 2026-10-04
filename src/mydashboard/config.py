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
    def from_env(cls) -> "Settings":
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

    default_groups: list[str] = field(default_factory=lambda: ["canada", "admins"])
    always_allow: list[str] = field(default_factory=lambda: ["admins"])
    lan_hosts: list[str] = field(default_factory=list)
    public_only: bool = False
    sso_only: bool = False
    hide: list[str] = field(default_factory=list)
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
    o.hide = [norm(x) for x in data.get("hide", [])]
    o.services = {norm(k): (v or {}) for k, v in (data.get("services") or {}).items()}
    o.extra = list(data.get("extra", []))
    return o
