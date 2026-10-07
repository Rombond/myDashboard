import json

import pytest

from mydashboard.app import create_app
from mydashboard.config import Settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"entries": [
        {"id": "shelfmark", "name": "Shelfmark", "host": "shelfmark.example.com",
         "url": "https://shelfmark.example.com/", "groups": ["media"], "source": "oidc"},
        {"id": "wishlist", "name": "Wishlist", "host": "w.example.com",
         "url": "https://w.example.com/", "groups": ["family"], "source": "oidc"}]}))
    monkeypatch.setattr("mydashboard.app.fetch_containers", lambda host: [])
    s = Settings(rules_file=str(rules), overrides_file=str(tmp_path / "none.yml"), cache_seconds=0)
    return create_app(s).test_client()


def test_requires_authelia_headers(client):
    assert client.get("/").status_code == 401
    assert client.get("/healthz").status_code == 200


def test_page_marks_services_without_access(client):
    html = client.get("/", headers={"Remote-User": "alice", "Remote-Groups": "media,lldap_x"}).get_data(as_text=True)
    assert 'href="https://shelfmark.example.com/"' in html
    assert 'href="https://w.example.com/"' not in html
    assert "no access" in html and "1 / 2 available" in html


def test_api(client):
    r = client.get("/api/services", headers={"Remote-User": "u", "Remote-Groups": "family"}).get_json()
    assert {s["key"]: s["allowed"] for s in r["services"]} == {"shelfmark": False, "wishlist": True}


def test_trust_token(tmp_path, monkeypatch):
    monkeypatch.setattr("mydashboard.app.fetch_containers", lambda host: [])
    app = create_app(Settings(rules_file=str(tmp_path / "r.json"), overrides_file=str(tmp_path / "o.yml"),
                              trust_token="s3cret"))
    c = app.test_client()
    h = {"Remote-User": "u", "Remote-Groups": "users"}
    assert c.get("/", headers=h).status_code == 403
    assert c.get("/", headers={**h, "X-Dashboard-Token": "s3cret"}).status_code == 200


def test_account_menu_shows_identity_and_logout(tmp_path, monkeypatch):
    monkeypatch.setattr("mydashboard.app.fetch_containers", lambda host: [])
    ov = tmp_path / "o.yml"
    ov.write_text("auth_url: https://auth.example.com/\npublic_url: https://apps.example.com\n")
    c = create_app(Settings(rules_file=str(tmp_path / "r.json"), overrides_file=str(ov), cache_seconds=0)).test_client()
    html = c.get("/", headers={"Remote-User": "alice", "Remote-Name": "Alice Martin",
                               "Remote-Email": "m@example.com", "Remote-Groups": "family,media"}).get_data(as_text=True)
    assert ">AM<" in html and "@alice" in html and "m@example.com" in html
    assert "https://auth.example.com/settings" in html
    assert "https://auth.example.com/logout?rd=https%3A%2F%2Fapps.example.com%2F" in html


def test_account_menu_without_portal_url_has_no_links(client):
    html = client.get("/", headers={"Remote-User": "u", "Remote-Groups": "media"}).get_data(as_text=True)
    assert "Log out" not in html and "@u" in html


def test_service_links_open_in_a_new_tab(client):
    html = client.get("/", headers={"Remote-User": "u", "Remote-Groups": "media"}).get_data(as_text=True)
    assert 'href="https://shelfmark.example.com/" target="_blank" rel="noopener noreferrer"' in html


def test_new_tab_checkbox_defaults_to_checked(client):
    html = client.get("/", headers={"Remote-User": "u", "Remote-Groups": "media"}).get_data(as_text=True)
    assert 'id="newtab" checked' in html and "mydashboard.newtab" in html


def test_theme_switch_is_in_the_menu(client):
    html = client.get("/", headers={"Remote-User": "u", "Remote-Groups": "media"}).get_data(as_text=True)
    assert all(f'name="theme" value="{v}"' in html for v in ("auto", "light", "dark"))
    assert "mydashboard.theme" in html


class FakeLldap:
    def __init__(self):
        self.saved = {}

    def get_avatar(self, uid):
        return self.saved.get(uid)

    def set_avatar(self, uid, jpeg):
        self.saved[uid] = jpeg


@pytest.fixture
def avatar_client(tmp_path, monkeypatch):
    monkeypatch.setattr("mydashboard.app.fetch_containers", lambda host: [])
    s = Settings(rules_file=str(tmp_path / "r.json"), overrides_file=str(tmp_path / "none.yml"), cache_seconds=0)
    fake = FakeLldap()
    return create_app(s, lldap=fake).test_client(), fake


def _png():
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (300, 100), (255, 0, 0, 128)).save(buf, "PNG")
    return buf.getvalue()


def test_avatar_upload_is_jpeg_for_the_header_user_only(avatar_client):
    import io
    c, fake = avatar_client
    h = {"Remote-User": "alice", "X-Requested-With": "mydashboard"}
    r = c.post("/avatar", headers=h, data={"file": (io.BytesIO(_png()), "a.png")})
    assert r.status_code == 204
    assert list(fake.saved) == ["alice"] and fake.saved["alice"][:2] == b"\xff\xd8"
    assert c.get("/avatar", headers={"Remote-User": "alice"}).mimetype == "image/jpeg"
    assert c.get("/avatar", headers={"Remote-User": "bob"}).status_code == 404


def test_avatar_rejects_missing_csrf_header_and_non_images(avatar_client):
    import io
    c, fake = avatar_client
    data = {"file": (io.BytesIO(_png()), "a.png")}
    assert c.post("/avatar", headers={"Remote-User": "alice"}, data=data).status_code == 403
    bad = {"file": (io.BytesIO(b"nope"), "a.png")}
    h = {"Remote-User": "alice", "X-Requested-With": "mydashboard"}
    assert c.post("/avatar", headers=h, data=bad).status_code == 400
    assert not fake.saved


def test_avatar_disabled_without_lldap(client):
    assert client.get("/avatar", headers={"Remote-User": "a"}).status_code == 404
