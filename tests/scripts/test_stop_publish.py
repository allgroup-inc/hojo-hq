"""公開停止(山梨版)の成果物処理 scripts/stop_publish.py と、404・update.yml の配線の検査。

- 合成データだけを使う(実データは読まない)。
"""
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import stop_publish as sp  # noqa: E402

CFG = ROOT / "scripts" / "stopped_sites.json"
WF = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
FETCH = (ROOT / ".github" / "workflows" / "fukugiiro-fetch.yml").read_text(encoding="utf-8")


def _cfg():
    return sp.load_config(CFG)


def _url(loc):
    return f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>2026-10-15</lastmod>\n  </url>\n"


@pytest.fixture
def pages(tmp_path):
    root = tmp_path / "pages"
    (root / "fukugiiro" / "kit").mkdir(parents=True)
    (root / "fukugiiro" / "index.html").write_text("<p>福岡</p>", encoding="utf-8")
    (root / "yamanashi" / "kit").mkdir(parents=True)
    (root / "yamanashi" / "index.html").write_text("<p>山梨</p>", encoding="utf-8")
    (root / "go" / "ymn-top").mkdir(parents=True)
    (root / "go" / "ymn-top" / "index.html").write_text("<p>LINE</p>", encoding="utf-8")
    (root / "data" / "yamanashi").mkdir(parents=True)
    (root / "data" / "yamanashi" / "seido.json").write_text("{}", encoding="utf-8")
    (root / "data" / "fukugiiro").mkdir(parents=True)
    (root / "data" / "fukugiiro" / "seido.json").write_text("{}", encoding="utf-8")
    (root / "404.html").write_text("<a href='/hojo-hq/fukugiiro/'>福岡</a>", encoding="utf-8")
    sm = '<?xml version="1.0"?>\n<urlset>\n' + _url("https://x.example/hojo-hq/") + _url(
        "https://x.example/hojo-hq/fukugiiro/") + _url("https://x.example/hojo-hq/yamanashi/") + _url(
        "https://x.example/hojo-hq/yamanashi/kit/") + "</urlset>\n"
    (root / "sitemap.xml").write_text(sm, encoding="utf-8")
    return root


def test_config_is_valid_and_keeps_go_pages():
    cfg = _cfg()
    assert cfg["version"] == 1
    assert "go/ymn-" in cfg["keep"]
    site = cfg["stopped"][0]
    assert site["site_prefixes"] == ["yamanashi/"]
    assert site["data_prefixes"] == ["data/yamanashi/"]


def test_apply_removes_yamanashi_and_its_data_only(pages):
    rep = sp.apply(pages, _cfg())
    assert not (pages / "yamanashi").exists()
    assert not (pages / "data" / "yamanashi").exists()
    assert (pages / "fukugiiro" / "index.html").exists()
    assert (pages / "data" / "fukugiiro" / "seido.json").exists()
    assert (pages / "go" / "ymn-top" / "index.html").exists()
    assert rep["sitemap_dropped"] == 2


def test_apply_keeps_non_yamanashi_sitemap_entries(pages):
    sp.apply(pages, _cfg())
    text = (pages / "sitemap.xml").read_text(encoding="utf-8")
    assert "/yamanashi/" not in text
    assert "https://x.example/hojo-hq/fukugiiro/" in text
    assert "https://x.example/hojo-hq/" in text
    assert text.count("<url>") == 2


def test_check_passes_after_apply_and_404_cleaned(pages):
    sp.apply(pages, _cfg())
    assert sp.check(pages, _cfg()) == []


def test_check_fails_when_yamanashi_path_remains(pages):
    assert any("残っている" in label for _, label, _ in sp.check(pages, _cfg()))


def test_check_fails_on_yamanashi_link_in_any_page(pages):
    sp.apply(pages, _cfg())
    (pages / "404.html").write_text("<a href='/hojo-hq/yamanashi/'>x</a>", encoding="utf-8")
    fails = sp.check(pages, _cfg())
    assert any("参照がある" in label for _, label, _ in fails)


def test_apply_refuses_keep_overlap(pages, tmp_path):
    cfg = _cfg()
    cfg["keep"] = ["yamanashi/"]
    with pytest.raises(SystemExit):
        sp.apply(pages, cfg)


def test_main_returns_codes(pages, capsys):
    cfgp = str(CFG)
    assert sp.main(["--root", str(pages), "--config", cfgp, "--check"]) == 1
    assert sp.main(["--root", str(pages), "--config", cfgp, "--apply"]) == 0
    assert sp.main(["--root", str(pages), "--config", cfgp, "--check"]) == 0
    assert sp.main(["--root", str(pages / "missing"), "--config", cfgp, "--check"]) == 1


def test_site_404_has_no_yamanashi_link():
    html = (ROOT / "site" / "404.html").read_text(encoding="utf-8")
    assert "/yamanashi/" not in html
    assert "/hojo-hq/fukugiiro/" in html


def test_update_yml_applies_stop_before_upload_and_checks_it():
    steps = yaml.safe_load(WF)["jobs"]["fetch-and-deploy"]["steps"]
    names = [s.get("name") or s.get("uses") or "" for s in steps]

    def idx(p):
        return next(i for i, n in enumerate(names) if n.startswith(p))

    assert idx("Prepare Pages artifact") < idx("Verify artifact (C3") < idx("Guard (C4") < idx("公開停止の検査") < idx("Upload site")
    assert "stop_publish.py --root /tmp/pages-deploy --config scripts/stopped_sites.json --apply" in WF
    assert "stop_publish.py --root /tmp/pages-deploy --config scripts/stopped_sites.json --check" in WF


def test_fukugiiro_fetch_no_longer_builds_yamanashi():
    assert "python scripts/yamanashi/build_yamanashi.py" not in FETCH
    assert "python scripts/kensho_yamanashi.py" not in FETCH
    add_line = next(l for l in FETCH.splitlines() if l.strip().startswith("git add data/fukugiiro/seido.json"))
    assert "site/yamanashi" not in add_line
    assert "data/yamanashi" in add_line
