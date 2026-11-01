import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import generate_ig_hub as hub  # noqa: E402

LAUNCH = """# 投稿1

## キャプション
上限は1,000万円。
【募集中】テスト補助金A
🗓 締切：2026-12-31（残り76日）
💰 上限 1,000万円
詳細・申請は原文で👇
https://example.go.jp/a
""" + hub.HUB_GUIDE + """

## 出典
https://example.go.jp/a
"""

CAROUSEL = """## キャプション
締切まで30日以上ある補助金だけ、5件選びました。

1. テスト補助金B
　締切 2026-11-01・残り16日 / 上限 100万円
2. テスト補助金A
　締切 2026-12-31・残り76日 / 上限 1,000万円

## 出典
- テスト補助金B: https://example.go.jp/b
- テスト補助金A: https://example.go.jp/a
"""


def _tree(tmp_path):
    (tmp_path / "posts" / "launch").mkdir(parents=True)
    (tmp_path / "posts" / "carousel").mkdir(parents=True)
    (tmp_path / "posts" / "launch" / "01_seido.md").write_text(LAUNCH, encoding="utf-8")
    (tmp_path / "posts" / "launch" / "07_cta.md").write_text("## キャプション\n診断\n", encoding="utf-8")
    (tmp_path / "posts" / "carousel" / "caption.md").write_text(CAROUSEL, encoding="utf-8")
    return str(tmp_path)


def test_collect_dedupes_by_source_url(tmp_path):
    items = hub.collect(_tree(tmp_path))
    assert [it["url"] for it in items] == ["https://example.go.jp/b", "https://example.go.jp/a"]


def test_deadline_under_30_days_is_excluded(tmp_path):
    items = hub.filter_deadline(hub.collect(_tree(tmp_path)), date(2026, 10, 16))
    assert [it["name"] for it in items] == ["テスト補助金A"]


def test_render_links_and_separate_event_names(tmp_path):
    today = date(2026, 10, 16)
    page = hub.render(hub.filter_deadline(hub.collect(_tree(tmp_path)), today), today)
    assert 'href="https://example.go.jp/a"' in page
    assert 'data-ev="ig_hub_source_click"' in page
    assert 'data-ev="ig_hub_line_click"' in page
    assert "line_redirect" not in page
    assert 'href="../go/ig/"' in page


def test_empty_state_renders():
    page = hub.render([], date(2026, 10, 16))
    assert "準備しています" in page
