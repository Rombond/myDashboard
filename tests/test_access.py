from mydashboard.access import build_catalog, view_for
from mydashboard.config import Overrides
from mydashboard.discovery import DockerService, parse_containers

ENTRIES = [
    {"id": "immich", "name": "Immich", "host": "immich.brebond.com", "url": "https://immich.brebond.com/",
     "groups": ["canada", "admins"], "source": "oidc"},
    {"id": "open-webui", "name": "Open WebUI", "host": "jarvis.brebond.com", "url": "https://jarvis.brebond.com/",
     "groups": ["family", "canada", "admins"], "source": "oidc"},
    {"id": "shelfmark", "name": "Shelfmark", "host": "shelfmark.brebond.com",
     "url": "https://shelfmark.brebond.com/", "groups": ["medias", "canada", "admins"], "source": "oidc"},
    {"id": "server.brebond", "name": "Server", "host": "server.brebond", "url": "https://server.brebond/",
     "groups": ["admins"], "source": "forward_auth"},
]


def ov(**kw):
    return Overrides(lan_hosts=["server.brebond"], **kw)


def svc(name, url, container=None):
    return DockerService(container or name.lower(), name, url, "di:x", "")


def get(cat, key):
    return next(s for s in cat if s.key == key)


def by_key(rows):
    return {r["key"]: r for r in rows}


def test_authelia_match_by_name_prefers_public_url():
    s = get(build_catalog([svc("Immich", "http://server.brebond:2283/")], ENTRIES, ov()), "immich")
    assert s.url == "https://immich.brebond.com/" and s.groups == ["canada", "admins"]


def test_name_match_ignores_punctuation():
    s = get(build_catalog([svc("OpenWebUI", "server.brebond:12083")], ENTRIES, ov()), "openwebui")
    assert s.groups == ["family", "canada", "admins"]
    assert s.url == "https://jarvis.brebond.com/"


def test_lan_host_never_matches_the_esphome_rule():
    s = get(build_catalog([svc("Sonarr", "http://server.brebond:8989/")], ENTRIES, ov()), "sonarr")
    assert s.groups == ["canada", "admins"]  # default, not ["admins"] from the server.brebond rule
    assert s.lan


def test_unlabelled_authelia_services_appear_but_not_lan_rules():
    keys = {s.key for s in build_catalog([], ENTRIES, ov())}
    assert keys == {"immich", "openwebui", "shelfmark"}


def test_overrides_win_and_hide_and_extra():
    o = ov(services={"jellyfin": {"groups": ["family"], "url": "https://j.example.com/"}},
           hide=["caddy"],
           extra=[{"name": "OMV", "url": "http://server.brebond:2080/", "groups": ["admins"]}])
    cat = build_catalog([svc("Jellyfin", "http://x/"), svc("Caddy", "http://c/")], [], o)
    keys = by_key(view_for(cat, {"family"}))
    assert "caddy" not in keys
    assert keys["jellyfin"]["allowed"] and keys["jellyfin"]["description"] == ""
    assert not keys["omv"]["allowed"]


def test_access_rules_and_admins_always_allowed():
    cat = build_catalog([svc("Immich", "http://x/")], ENTRIES, ov(always_allow=["admins"]))
    assert not cat[0].allowed_for({"family"})
    assert cat[0].allowed_for({"canada"})
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


def test_parse_containers_skips_children_and_urlless():
    cs = [
        {"Names": ["/a"], "Labels": {"dynacat.name": "A", "dynacat.url": "a.lan:1"}},
        {"Names": ["/db"], "Labels": {"dynacat.name": "DB", "dynacat.parent": "a"}},
        {"Names": ["/b"], "Labels": {"dynacat.name": "B"}},
        {"Names": ["/c"], "Labels": {}},
    ]
    out = parse_containers(cs)
    assert [(s.name, s.url) for s in out] == [("A", "http://a.lan:1")]
