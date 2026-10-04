import json

import pytest

from mydashboard.app import create_app
from mydashboard.config import Settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"entries": [
        {"id": "shelfmark", "name": "Shelfmark", "host": "shelfmark.example.com",
         "url": "https://shelfmark.example.com/", "groups": ["medias"], "source": "oidc"},
        {"id": "wishlist", "name": "Wishlist", "host": "w.example.com",
         "url": "https://w.example.com/", "groups": ["family"], "source": "oidc"}]}))
    monkeypatch.setattr("mydashboard.app.fetch_containers", lambda host: [])
    s = Settings(rules_file=str(rules), overrides_file=str(tmp_path / "none.yml"), cache_seconds=0)
    return create_app(s).test_client()


def test_requires_authelia_headers(client):
    assert client.get("/").status_code == 401
    assert client.get("/healthz").status_code == 200


def test_page_marks_services_without_access(client):
    html = client.get("/", headers={"Remote-User": "romana", "Remote-Groups": "medias,lldap_x"}).get_data(as_text=True)
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
    h = {"Remote-User": "u", "Remote-Groups": "canada"}
    assert c.get("/", headers=h).status_code == 403
    assert c.get("/", headers={**h, "X-Dashboard-Token": "s3cret"}).status_code == 200


def test_account_menu_shows_identity_and_logout(tmp_path, monkeypatch):
    monkeypatch.setattr("mydashboard.app.fetch_containers", lambda host: [])
    ov = tmp_path / "o.yml"
    ov.write_text("auth_url: https://auth.example.com/\npublic_url: https://apps.example.com\n")
    c = create_app(Settings(rules_file=str(tmp_path / "r.json"), overrides_file=str(ov), cache_seconds=0)).test_client()
    html = c.get("/", headers={"Remote-User": "romana", "Remote-Name": "Maman Bond",
                               "Remote-Email": "m@example.com", "Remote-Groups": "family,medias"}).get_data(as_text=True)
    assert ">MB<" in html and "@romana" in html and "m@example.com" in html
    assert "https://auth.example.com/settings" in html
    assert "https://auth.example.com/logout?rd=https%3A%2F%2Fapps.example.com%2F" in html


def test_account_menu_without_portal_url_has_no_links(client):
    html = client.get("/", headers={"Remote-User": "u", "Remote-Groups": "medias"}).get_data(as_text=True)
    assert "Log out" not in html and "@u" in html


def test_service_links_open_in_a_new_tab(client):
    html = client.get("/", headers={"Remote-User": "u", "Remote-Groups": "medias"}).get_data(as_text=True)
    assert 'href="https://shelfmark.example.com/" target="_blank" rel="noopener noreferrer"' in html
