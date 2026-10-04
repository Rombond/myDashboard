from mydashboard.authelia_export import export_rules

CONFIG = {
    "access_control": {
        "default_policy": "deny",
        "rules": [
            {"domain": ["server.brebond"], "subject": "group:admins", "policy": "two_factor"},
            {"domain": ["books.brebond.com"],
             "subject": ["group:medias", "group:canada", "group:admins"], "policy": "two_factor"},
        ],
    },
    "identity_providers": {"oidc": {
        "authorization_policies": {
            "family": {"default_policy": "deny", "rules": [
                {"policy": "two_factor", "subject": ["group:family", "group:admins"]}]},
        },
        "clients": [
            {"client_id": "wishlist", "client_name": "Wishlist", "authorization_policy": "family",
             "redirect_uris": ["https://souhait.brebond.com/login"]},
            {"client_id": "plain", "redirect_uris": ["http://lan:1/cb", "https://plain.example.com/cb"]},
        ],
    }},
}


def test_forward_auth_and_oidc_entries():
    data = export_rules(CONFIG)
    by_id = {e["id"]: e for e in data["entries"]}
    assert by_id["books.brebond.com"]["groups"] == ["admins", "canada", "medias"]
    assert by_id["wishlist"]["groups"] == ["admins", "family"]
    assert by_id["wishlist"]["host"] == "souhait.brebond.com"
    assert by_id["plain"]["groups"] == ["*"]  # built-in two_factor: any authenticated user
    assert by_id["plain"]["host"] == "plain.example.com"  # first https redirect only


def test_and_subjects_are_ignored_with_a_note():
    cfg = {"access_control": {"default_policy": "deny", "rules": [
        {"domain": "x.example.com", "subject": [["group:a", "group:b"]], "policy": "two_factor"}]}}
    data = export_rules(cfg)
    assert data["entries"][0]["groups"] == []
    assert any("AND" in n for n in data["notes"])


def test_deny_rule_and_open_rule():
    cfg = {"access_control": {"default_policy": "deny", "rules": [
        {"domain": "a.example.com", "policy": "deny"},
        {"domain": "b.example.com", "policy": "one_factor"}]}}
    by_host = {e["host"]: e for e in export_rules(cfg)["entries"]}
    assert by_host["a.example.com"]["groups"] == []
    assert by_host["b.example.com"]["groups"] == ["*"]
