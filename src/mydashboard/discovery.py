"""Discover services from container labels (Dynacat/Glance style) through a Docker API proxy."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class DockerService:
    container: str
    name: str
    url: str
    icon: str | None
    description: str


def _normalize_url(url: str) -> str:
    url = url.strip()
    if url and "://" not in url:
        url = "http://" + url
    return url


def parse_containers(containers: list[dict], prefix: str = "dynacat") -> list[DockerService]:
    """Keep top-level, labelled containers that have a URL (sub-containers have a `parent`)."""
    out: list[DockerService] = []
    for c in containers:
        labels = c.get("Labels") or {}
        name = labels.get(f"{prefix}.name")
        url = labels.get(f"{prefix}.url")
        if not name or not url or labels.get(f"{prefix}.parent"):
            continue
        out.append(
            DockerService(
                container=(c.get("Names") or ["?"])[0].lstrip("/"),
                name=name,
                url=_normalize_url(url),
                icon=labels.get(f"{prefix}.icon"),
                description=labels.get(f"{prefix}.description", ""),
            )
        )
    return out


def fetch_containers(docker_host: str) -> list[dict]:
    """GET /containers/json from a (read-only) Docker API endpoint."""
    if urlparse(docker_host).scheme not in ("http", "https"):
        raise ValueError("DOCKER_HOST must be an http(s) URL (use docker-socket-proxy)")
    with urllib.request.urlopen(docker_host.rstrip("/") + "/containers/json", timeout=5) as r:
        return json.load(r)
