"""Tracker ratio tiles: upload / download totals read from Prometheus (one metric pair per tracker)."""

from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from .config import Overrides

log = logging.getLogger("mydashboard")

UNITS = (("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20))


def human_bytes(n: float) -> str:
    for unit, size in UNITS:
        if n >= size:
            return f"{n / size:.2f} {unit}"
    return f"{n / (1 << 20):.2f} MB"


def query_value(base_url: str, metric: str, timeout: float = 3.0) -> float | None:
    """First sample of an instant query, or None when the series is missing."""
    url = f"{base_url.rstrip('/')}/api/v1/query?{urlencode({'query': metric})}"
    with urlopen(url, timeout=timeout) as resp:  # noqa: S310 - URL comes from the admin's overrides.yml
        result = json.load(resp).get("data", {}).get("result", [])
    return float(result[0]["value"][1]) if result else None


def build_tiles(ov: Overrides, query=query_value) -> list[dict]:
    """One tile per configured tracker. A tracker whose metrics are missing is shown as unavailable."""
    tiles = []
    for t in ov.ratio_trackers:
        prefix = t["metric"]
        try:
            down = query(ov.prometheus_url, t.get("down") or f"{prefix}_total_downloaded_bytes")
            up = query(ov.prometheus_url, t.get("up") or f"{prefix}_total_uploaded_bytes")
        except Exception as exc:  # Prometheus down: stop early instead of waiting on every tracker
            log.warning("ratio query failed: %s", exc)
            return [{"name": x["name"], "url": x.get("url", ""), "ok": False} for x in ov.ratio_trackers]
        if down is None or up is None:
            tiles.append({"name": t["name"], "url": t.get("url", ""), "ok": False})
            continue
        ratio = up / down if down else None
        tiles.append({"name": t["name"], "url": t.get("url", ""), "ok": True,
                      "down": human_bytes(down), "up": human_bytes(up),
                      "ratio": f"{ratio:.2f}" if ratio is not None else "∞", "low": ratio is not None and ratio < 1})
    return tiles


class RatioCache:
    """Keeps the last tiles for `seconds`, so page loads do not hammer Prometheus."""

    def __init__(self, seconds: int = 60):
        self.seconds, self._at, self._tiles = seconds, 0.0, []

    def get(self, ov: Overrides, query=query_value) -> list[dict]:
        if self._at and time.monotonic() - self._at < self.seconds:
            return self._tiles
        self._tiles = build_tiles(ov, query)
        self._at = time.monotonic()
        return self._tiles
