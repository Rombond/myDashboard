import json

from mydashboard.app import create_app
from mydashboard.config import Overrides, Settings, load_overrides
from mydashboard.ratio import build_tiles, human_bytes

VALUES = {"a_total_downloaded_bytes": 1 << 40, "a_total_uploaded_bytes": 3 << 40,
          "b_total_downloaded_bytes": 2 << 30, "b_total_uploaded_bytes": 1 << 30}


def fake(_url, metric):
    return VALUES.get(metric)


def ov(**kw):
    return Overrides(prometheus_url="http://prom:9090", ratio_trackers=[
        {"name": "Alpha", "metric": "a"}, {"name": "Beta", "metric": "b"}, {"name": "Gone", "metric": "z"}], **kw)


def test_human_bytes():
    assert human_bytes(3 << 40) == "3.00 TB" and human_bytes(5 << 20) == "5.00 MB"


def test_tiles_ratio_low_and_missing():
    a, b, gone = build_tiles(ov(), fake)
    assert (a["ratio"], a["up"], a["low"]) == ("3.00", "3.00 TB", False)
    assert (b["ratio"], b["low"]) == ("0.50", True)
    assert gone == {"name": "Gone", "ok": False}


def test_prometheus_down_marks_all_unavailable():
    def boom(_u, _m):
        raise OSError("down")
    assert [t["ok"] for t in build_tiles(ov(), boom)] == [False, False, False]


def test_load_overrides_ratio(tmp_path):
    p = tmp_path / "o.yml"
    p.write_text("ratio:\n  prometheus_url: http://prom:9090/\n  groups: [torrents]\n  trackers:\n"
                 "    - {name: A, metric: a}\n    - {name: B, down: x, up: y}\n    - {name: bad}\n")
    o = load_overrides(str(p))
    assert o.prometheus_url == "http://prom:9090" and o.ratio_groups == ["torrents"]
    assert [t["name"] for t in o.ratio_trackers] == ["A", "B"]


def test_only_allowed_groups_see_ratios(tmp_path, monkeypatch):
    p = tmp_path / "o.yml"
    p.write_text("ratio:\n  prometheus_url: http://prom:9090\n  groups: [torrents]\n"
                 "  trackers:\n    - {name: Alpha, metric: a}\n")
    (tmp_path / "r.json").write_text(json.dumps({"entries": []}))
    monkeypatch.setattr("mydashboard.app.fetch_containers", lambda host: [])
    monkeypatch.setattr("mydashboard.ratio.query_value", fake)
    monkeypatch.setattr("mydashboard.ratio.RatioCache.get",
                        lambda self, o, query=fake: build_tiles(o, fake))
    c = create_app(Settings(rules_file=str(tmp_path / "r.json"), overrides_file=str(p), cache_seconds=0)).test_client()

    def page(g):
        return c.get("/", headers={"Remote-User": "u", "Remote-Groups": g}).get_data(as_text=True)

    assert "Alpha" in page("torrents") and "Alpha" in page("admins")
    assert "Alpha" not in page("family")
