from mydashboard.access import build_catalog, view_for
from mydashboard.config import Overrides
from mydashboard.discovery import DockerService, parse_containers

ENTRIES = [
    {"id": "immich", "name": "Immich", "host": "immich.example.com", "url": "https://immich.example.com/",
     "groups": ["users", "admins"], "source": "oidc"},
    {"id": "open-webui", "name": "Open WebUI", "host": "chat.example.com", "url": "https://chat.example.com/",
     "groups": ["family", "users", "admins"], "source": "oidc"},
    {"id": "shelfmark", "name": "Shelfmark", "host": "shelfmark.example.com",
     "url": "https://shelfmark.example.com/", "groups": ["media", "users", "admins"], "source": "oidc"},
    {"id": "nas.lan", "name": "Server", "host": "nas.lan", "url": "https://nas.lan/",
     "groups": ["admins"], "source": "forward_auth"},
]


def ov(**kw):
    return Overrides(lan_hosts=["nas.lan"], **kw)


def svc(name, url, container=None):
    return DockerService(container or name.lower(), name, url, "di:x", "")


def get(cat, key):
    return next(s for s in cat if s.key == key)


def by_key(rows):
    return {r["key"]: r for r in rows}


def test_authelia_match_by_name_prefers_public_url():
    s = get(build_catalog([svc("Immich", "http://nas.lan:2283/")], ENTRIES, ov()), "immich")
    assert s.url == "https://immich.example.com/" and s.groups == ["users", "admins"]


def test_name_match_ignores_punctuation():
    s = get(build_catalog([svc("OpenWebUI", "nas.lan:12083")], ENTRIES, ov()), "openwebui")
    assert s.groups == ["family", "users", "admins"]
    assert s.url == "https://chat.example.com/"


def test_lan_host_never_matches_a_lan_only_rule():
    s = get(build_catalog([svc("Sonarr", "http://nas.lan:8989/")], ENTRIES, ov()), "sonarr")
    assert s.groups == ["admins"]  # default, not ["admins"] from the nas.lan rule
    assert s.lan


def test_unlabelled_authelia_services_appear_but_not_lan_rules():
    keys = {s.key for s in build_catalog([], ENTRIES, ov())}
    assert keys == {"immich", "openwebui", "shelfmark"}


def test_overrides_win_and_hide_and_extra():
    o = ov(services={"jellyfin": {"groups": ["family"], "url": "https://j.example.com/"}},
           hide=["caddy"],
           extra=[{"name": "OMV", "url": "http://nas.lan:2080/", "groups": ["admins"]}])
    cat = build_catalog([svc("Jellyfin", "http://x/"), svc("Caddy", "http://c/")], [], o)
    keys = by_key(view_for(cat, {"family"}))
    assert "caddy" not in keys
    assert keys["jellyfin"]["allowed"] and keys["jellyfin"]["description"] == ""
    assert not keys["omv"]["allowed"]


def test_access_rules_and_admins_always_allowed():
    cat = build_catalog([svc("Immich", "http://x/")], ENTRIES, ov(always_allow=["admins"]))
    assert not cat[0].allowed_for({"family"})
    assert cat[0].allowed_for({"users"})
    assert cat[0].allowed_for({"admins"})


def test_star_means_any_authenticated_user():
    o = ov(services={"x": {"groups": ["*"]}})
    cat = build_catalog([svc("X", "http://x/")], [], o)
    assert cat[0].allowed_for(set())


def test_view_sorts_allowed_first():
    cat = build_catalog([svc("Aaa", "http://a/"), svc("Zzz", "http://z/")], [],
                        ov(services={"aaa": {"groups": ["nope"]}, "zzz": {"groups": ["family"]}}))
    rows = view_for(cat, {"family"})
    assert [r["name"] for r in rows] == ["Zzz", "Aaa"]


def test_parse_containers_keeps_children_with_a_url_and_drops_urlless():
    cs = [
        {"Names": ["/a"], "Labels": {"dynacat.name": "A", "dynacat.url": "a.lan:1"}},
        {"Names": ["/child"], "Labels": {"dynacat.name": "Child", "dynacat.parent": "a", "dynacat.url": "http://c/"}},
        {"Names": ["/db"], "Labels": {"dynacat.name": "DB", "dynacat.parent": "a"}},
        {"Names": ["/b"], "Labels": {"dynacat.name": "B"}},
        {"Names": ["/c"], "Labels": {}},
    ]
    out = parse_containers(cs)
    assert [(s.name, s.url) for s in out] == [("A", "http://a.lan:1"), ("Child", "http://c/")]


def test_public_only_drops_lan_services_but_keeps_those_with_a_public_url():
    docker = [svc("Sonarr", "http://nas.lan:8989/"), svc("Immich", "http://nas.lan:2283/"),
              svc("Wiki", "https://wiki.example.com/")]
    keys = {s.key for s in build_catalog(docker, ENTRIES, ov(public_only=True))}
    assert "sonarr" not in keys
    assert {"immich", "wiki"} <= keys  # Immich is rewritten to its public Authelia URL
    assert "sonarr" in {s.key for s in build_catalog(docker, ENTRIES, ov())}


def test_sso_only_keeps_authelia_ldap_flagged_and_drops_the_rest():
    docker = [svc("Immich", "http://nas.lan:2283/"),      # Authelia OIDC client
              svc("Jellyfin", "https://jf.example.com/"),        # LDAP, flagged by override
              svc("Vault", "https://vault.example.com/")]        # own login
    o = ov(sso_only=True, services={"jellyfin": {"sso": True, "groups": ["family"]}})
    keys = {s.key for s in build_catalog(docker, ENTRIES, o)}
    assert keys == {"immich", "jellyfin", "openwebui", "shelfmark"}  # unlabelled Authelia entries count as SSO
    assert "vault" in {s.key for s in build_catalog(docker, ENTRIES, ov())}
