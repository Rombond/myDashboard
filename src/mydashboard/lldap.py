"""Profile pictures stored in LLDAP (`avatar` / jpegPhoto), written through its GraphQL API.

The dashboard logs in with a service account and only ever touches the user named by Authelia's
`Remote-User` header, so LLDAP itself never has to be reachable from the internet."""

from __future__ import annotations

import base64
import io
import json
import time
import urllib.request

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard
SIZE = 256


class LldapError(Exception):
    pass


def to_jpeg(data: bytes) -> bytes:
    """Square-crop, resize and re-encode any common image as a small JPEG (LLDAP only stores JPEG)."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, "white")
            bg.paste(img, mask=img.getchannel("A"))
            img = bg
        img = ImageOps.fit(img.convert("RGB"), (SIZE, SIZE))
    except Exception as exc:
        raise ValueError("not a valid image") from exc
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()


class Lldap:
    def __init__(self, url: str, user: str, password: str, timeout: float = 5.0):
        self.url = url.rstrip("/")
        self.user, self.password, self.timeout = user, password, timeout
        self._token = ""
        self._token_at = 0.0
        self._cache: dict[str, tuple[float, bytes | None]] = {}

    def _post(self, path: str, body: dict, token: str = "") -> dict:
        req = urllib.request.Request(self.url + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 - configured URL
                return json.load(r)
        except Exception as exc:
            raise LldapError(f"LLDAP request failed: {exc}") from exc

    def _login(self) -> str:
        if not self._token or time.monotonic() - self._token_at > 600:
            self._token = self._post("/auth/simple/login", {"username": self.user, "password": self.password})["token"]
            self._token_at = time.monotonic()
        return self._token

    def _gql(self, query: str, variables: dict) -> dict:
        res = self._post("/api/graphql", {"query": query, "variables": variables}, self._login())
        if res.get("errors"):
            self._token = ""  # maybe an expired token: log in again next time
            raise LldapError(f"LLDAP error: {res['errors'][0].get('message', 'unknown')}")
        return res["data"]

    def get_avatar(self, uid: str) -> bytes | None:
        hit = self._cache.get(uid)
        if hit and time.monotonic() - hit[0] < 300:
            return hit[1]
        data = self._gql("query($id: String!) { user(userId: $id) { avatar } }", {"id": uid})
        b64 = (data.get("user") or {}).get("avatar")
        img = base64.b64decode(b64) if b64 else None
        self._cache[uid] = (time.monotonic(), img)
        return img

    def set_avatar(self, uid: str, jpeg: bytes) -> None:
        self._gql("mutation($u: UpdateUserInput!) { updateUser(user: $u) { ok } }",
                  {"u": {"id": uid, "avatar": base64.b64encode(jpeg).decode()}})
        self._cache[uid] = (time.monotonic(), jpeg)
