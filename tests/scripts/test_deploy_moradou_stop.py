"""moradou.jp 配信ツリーから山梨版を外すこと(山梨版停止に直接必要な検査のみ)。

- 実際の site/ から配信ツリーを tmp に作る(外部接続なし・データは読まない)。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import deploy_moradou as dm  # noqa: E402


def _build(tmp_path):
    out = tmp_path / "moradou"
    assert dm.build(str(out), "moradou.jp") == 0
    return out


def test_moradou_tree_has_no_yamanashi_and_keeps_fukugiiro(tmp_path):
    out = _build(tmp_path)
    assert not (out / "yamanashi").exists()
    assert (out / "index.html").is_file()
    assert (out / "shindan" / "index.html").is_file()
    assert (out / "go").is_dir()
    for dirpath, _, files in os.walk(out):
        for name in files:
            p = Path(dirpath) / name
            if p.suffix.lower() not in dm.TEXT_EXT:
                continue
            assert "/yamanashi/" not in p.read_text(encoding="utf-8", errors="replace"), p.name


def test_moradou_sitemap_and_404_have_no_yamanashi(tmp_path):
    out = _build(tmp_path)
    assert "yamanashi" not in (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "yamanashi" not in (out / "404.html").read_text(encoding="utf-8")
    assert (out / "sitemap.xml").read_text(encoding="utf-8").count("<loc>") > 0
