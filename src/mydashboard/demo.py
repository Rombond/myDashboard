"""Run the dashboard with fake data, for screenshots, development and trying it out.

    python -m mydashboard.demo [--user alice] [--groups family] [--port 8080]

No Docker, no Authelia: containers and rules come from the ``demo/`` folder, and every request is treated as
coming from the chosen user (a real deployment gets that from Authelia's headers).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import app as app_module
from .config import Settings

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo"


class _AsUser:
    """WSGI middleware that plays the part of Authelia: it adds the Remote-* headers."""

    def __init__(self, wsgi, user: str, name: str, groups: str):
        self.wsgi, self.headers = wsgi, {
            "HTTP_REMOTE_USER": user,
            "HTTP_REMOTE_NAME": name,
            "HTTP_REMOTE_EMAIL": f"{user}@example.com",
            "HTTP_REMOTE_GROUPS": groups,
        }

    def __call__(self, environ, start_response):
        for key, value in self.headers.items():
            environ.setdefault(key, value)
        return self.wsgi(environ, start_response)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default="alice")
    ap.add_argument("--name", default="Alice Martin")
    ap.add_argument("--groups", default="family")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    containers = json.loads((DEMO_DIR / "containers.json").read_text())
    app_module.fetch_containers = lambda _host: containers
    settings = Settings(
        rules_file=str(DEMO_DIR / "rules.json"),
        overrides_file=str(DEMO_DIR / "overrides.yml"),
        title="Home services",
        cache_seconds=0,
    )
    app = app_module.create_app(settings)
    app.wsgi_app = _AsUser(app.wsgi_app, args.user, args.name, args.groups)
    app.run(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
