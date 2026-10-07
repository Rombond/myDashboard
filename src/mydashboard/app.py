"""Flask app: one page, the same for everyone, with the services you cannot use crossed out."""

from __future__ import annotations

import hmac
import logging
import time
from urllib.parse import quote

from flask import Flask, Response, abort, jsonify, render_template, request

from .access import build_catalog, load_rules, view_for
from .config import Overrides, Settings, load_overrides
from .discovery import fetch_containers, parse_containers
from .lldap import Lldap, LldapError, to_jpeg
from .ratio import RatioCache

log = logging.getLogger("mydashboard")


class Catalog:
    """Caches the merged service list for a few seconds (Docker + Authelia export + overrides)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._at = 0.0
        self._services = []
        self.overrides = Overrides()

    def get(self):
        if time.monotonic() - self._at < self.settings.cache_seconds and self._services:
            return self._services
        s = self.settings
        try:
            docker = parse_containers(fetch_containers(s.docker_host), s.label_prefix)
        except Exception as exc:  # proxy down: keep serving the last good list
            log.warning("docker discovery failed: %s", exc)
            if self._services:
                return self._services
            docker = []
        self.overrides = load_overrides(s.overrides_file)
        self._services = build_catalog(docker, load_rules(s.rules_file), self.overrides)
        self._at = time.monotonic()
        return self._services


def create_app(settings: Settings | None = None, lldap: Lldap | None = None) -> Flask:
    settings = settings or Settings.from_env()
    if lldap is None and settings.avatars:
        lldap = Lldap(settings.lldap_url, settings.lldap_user, settings.lldap_password)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
    catalog = Catalog(settings)
    ratios = RatioCache(settings.cache_seconds * 2)

    def current_user() -> dict:
        """Identity comes from Authelia's forward_auth headers (Remote-*)."""
        if settings.trust_token and not hmac.compare_digest(
            request.headers.get("X-Dashboard-Token", ""), settings.trust_token
        ):
            abort(403)
        user = request.headers.get("Remote-User")
        if not user and settings.dev_mode:
            return {"user": "dev", "name": "Dev", "groups": {"admins"}, "email": "dev@example.com"}
        if not user:
            abort(401)
        groups = {g.strip() for g in request.headers.get("Remote-Groups", "").split(",") if g.strip()}
        return {"user": user, "name": request.headers.get("Remote-Name") or user, "groups": groups,
                "email": request.headers.get("Remote-Email", "")}

    @app.get("/healthz")
    def healthz():
        return "ok"

    @app.get("/")
    def index():
        u = current_user()
        rows = view_for(catalog.get(), u["groups"])
        ov = catalog.overrides
        can_see_ratio = bool(ov.prometheus_url and ov.ratio_trackers
                             and (u["groups"] & set(ov.ratio_groups + ov.always_allow)))
        tiles = ratios.get(ov) if can_see_ratio else []
        back = ov.public_url or request.host_url.rstrip("/")
        words = [w for w in u["name"].replace(".", " ").split() if w]
        initials = "".join(w[0] for w in words[:2]).upper() or u["user"][:1].upper()
        account = {
            "initials": initials,
            "settings_url": f"{ov.auth_url}/settings" if ov.auth_url else "",
            "logout_url": f"{ov.auth_url}/logout?rd={quote(back + '/', safe='')}" if ov.auth_url else "",
        }
        return render_template("index.html", title=settings.title, user=u, account=account,
                               services=rows, ratios=tiles, avatars=lldap is not None,
                               allowed=sum(r["allowed"] for r in rows))

    @app.get("/api/services")
    def api_services():
        u = current_user()
        return jsonify(user=u["user"], groups=sorted(u["groups"]), services=view_for(catalog.get(), u["groups"]))

    @app.get("/avatar")
    def avatar_get():
        u = current_user()
        if lldap is None:
            abort(404)
        try:
            img = lldap.get_avatar(u["user"])
        except LldapError as exc:
            log.warning("avatar read failed: %s", exc)
            abort(502)
        if not img:
            abort(404)
        resp = Response(img, mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "private, max-age=60"
        return resp

    @app.post("/avatar")
    def avatar_set():
        u = current_user()
        if lldap is None:
            abort(404)
        if request.headers.get("X-Requested-With") != "mydashboard":  # forces a CORS preflight: no cross-site forms
            abort(403)
        f = request.files.get("file")
        if f is None:
            return jsonify(error="No file."), 400
        try:
            jpeg = to_jpeg(f.read())
        except ValueError:
            return jsonify(error="That file is not an image."), 400
        try:
            lldap.set_avatar(u["user"], jpeg)
        except LldapError as exc:
            log.warning("avatar write failed: %s", exc)
            return jsonify(error="Could not save the picture."), 502
        return "", 204

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(error="Image too large (8 MB max)."), 413

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("Cache-Control", "no-store")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    return app


def main() -> None:  # pragma: no cover - dev entrypoint
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="0.0.0.0", port=8080)


if __name__ == "__main__":  # pragma: no cover
    main()
