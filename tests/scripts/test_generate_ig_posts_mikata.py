"""IG 自動化(沖縄企業のミカタ): generate_ig_posts_mikata.py の検査。

実データは毎日の巡回で締切が動くため、選定ロジックの検査は固定の小さな
制度データ(tmp_path)と固定の today で行う。実データでは「落ちずに動く・
断定を書かない」ことだけを確かめる(test_real_data_smoke)。
"""
import datetime as dt
import json
import os
import re
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import generate_ig_posts_mikata as gen  # noqa: E402
from generate_ig_posts_mikata import (  # noqa: E402
    format_yen,
    generate_ig_posts,
    load_historical_post_ids,
)

REAL_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "subsidies.json")
TODAY = dt.date(2026, 9, 29)

# 金額表記(億・万)を拾う。数字は半角・全角の両方
AMOUNT_RE = re.compile(r"[0-9０-９]+億(?:[0-9０-９]+万)?円|[0-9０-９]+万円")
DATE_RE = re.compile(r"20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}|\d{1,2}月\d{1,2}日")
RATE_RE = re.compile(r"\d/\d|\d+分の\d+|\d+%")


def _item(sid, template, priority, deadline="2026-12-31", max_amount=10_000_000,
          before=None, after=None, area="全国", name=None, industry="製造業",
          exclude=False, status="募集中", **extra):
    d = {
        "id": sid,
        "name": name or f"テスト制度{sid}",
        "issuer": "テスト省",
        "target_area": area,
        "max_amount": max_amount,
        "deadline": deadline,
        "source_url": f"https://example.go.jp/{sid}",
        "status": status,
        "ig_template": template,
        "ig_priority": priority,
        "ig_example_industry": industry,
        "ig_before_amount": before,
        "ig_after_amount": after,
        "ig_exclude": exclude,
    }
    d.update(extra)
    return d


def _write(tmp_path, items, history=None):
    sub = tmp_path / "subsidies.json"
    sub.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    hist = tmp_path / "ig_posts_history.json"
    if history is not None:
        hist.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
    return str(sub), str(hist)


def _fixture_items():
    return [
        _item("t1-a", "template1", 1, max_amount=5_000_000, before=4_000_000, after=1_000_000,
              name="【農林水産省】中山間地域所得確保推進事業", industry="農業"),
        _item("t1-b", "template1", 2, max_amount=1_500_000_000),
        _item("t1-c", "template1", 3, max_amount=143_100_000, name="商用車等の電動化促進事業"),
        _item("t1-d", "template1", 4, max_amount=13_700_000, name="働き方改革推進支援助成金"),
        _item("t1-e", "template1", 5, max_amount=1_000_000),
        _item("t1-late", "template1", 41, max_amount=9_000_000),  # 優先度の範囲外
        _item("t1-soon", "template1", 0 + 6, deadline="2026-10-20"),  # 残り21日
        _item("t1-excl", "template1", 7, exclude=True),
        _item("t1-closed", "template1", 8, status="募集終了"),
        _item("t2-a", "template2", 1, deadline="要確認", max_amount=None, before=1_500_000, after=0,
              area="沖縄県", name="事業承継推進事業", industry="小売業"),
        _item("t2-b", "template2", 2, deadline="要確認", max_amount=None, area="沖縄県",
              name="プッシュ型相談支援事業"),
        _item("t3-a", "template3", 1, max_amount=1_500_000_000, before=50_000_000, after=15_000_000,
              name="Scope3排出量削減のための企業間連携による省CO2設備投資促進事業"),
        _item("t3-b", "template3", 2, max_amount=72_000_000, name="事業転換促進補助金"),
        _item("none", None, None),
    ]


# ---------------------------------------------------------------- brief の3本

def test_generate_selects_template1_high_priority(tmp_path):
    """Template1(ig_priority 1-40)が先に・優先度順に選ばれる。"""
    sub, hist = _write(tmp_path, _fixture_items())
    drafts = generate_ig_posts(subsidies_json=sub, max_posts=5, history_json=hist, today=TODAY)

    assert len(drafts) == 5
    template1_drafts = [d for d in drafts if d["template"] == "template1"]
    assert len(template1_drafts) >= 3, "At least 3 of 5 weekly posts should be template1"
    priorities = [d["ig_priority"] for d in template1_drafts]
    assert all(p <= 40 for p in priorities), "Template1 priorities must be <= 40"
    assert priorities == sorted(priorities)
    assert [d["seido_id"] for d in drafts] == ["t1-a", "t1-b", "t1-c", "t1-d", "t1-e"]

    ids = {d["seido_id"] for d in drafts}
    # 締切30日未満・除外フラグ・募集終了・範囲外の優先度は入らない
    assert not ids & {"t1-soon", "t1-excl", "t1-closed", "t1-late", "none"}

    historical_ids = load_historical_post_ids(hist, today=TODAY)
    for draft in template1_drafts:
        assert draft["seido_id"] not in historical_ids


def test_caption_no_unsupported_assertions(tmp_path):
    """本文の金額は max_amount / ig_before_amount / ig_after_amount 由来だけ。日付・補助率は書かない。"""
    items = _fixture_items()
    # template1 を全部使い切らせて template2/3 まで出させる
    sub, hist = _write(tmp_path, items)
    drafts = generate_ig_posts(subsidies_json=sub, max_posts=20, history_json=hist, today=TODAY)
    templates = {d["template"] for d in drafts}
    assert templates == {"template1", "template2", "template3"}

    for draft in drafts:
        caption = draft["caption"].replace(draft["seido_name"], "")  # 制度名そのものの数字は除く
        allowed = {format_yen(v) for v in (draft.get("max_amount"),
                                           draft.get("ig_before_amount"),
                                           draft.get("ig_after_amount")) if v}
        for m in AMOUNT_RE.findall(caption):
            assert m in allowed, f"{draft['seido_id']}: unsupported amount assertion {m}"
        assert not DATE_RE.search(caption), f"{draft['seido_id']}: date asserted in caption"
        assert not RATE_RE.search(caption), f"{draft['seido_id']}: subsidy rate asserted in caption"

        if draft["template"] == "template2":
            # 要確認の制度: 金額は一切書かない(before/after が入っていても)
            assert not AMOUNT_RE.findall(caption), f"{draft['seido_id']}: template2 must not state amounts"
            assert "要確認" in caption
            assert draft["publish_blocked"] is True
        if draft.get("ig_before_amount") and draft["template"] == "template1":
            assert "試算例" in caption

    t1a = next(d for d in drafts if d["seido_id"] == "t1-a")
    assert "400万円" in t1a["caption"] and "100万円" in t1a["caption"] and "500万円" in t1a["caption"]


def test_excludes_recent_posts(tmp_path):
    """直近5週間に投稿した制度は選ばない。5週間より前なら再び候補に戻る。"""
    history = {"posts": [
        {"seido_id": "t1-a", "posted_at": "2026-09-22"},   # 1週前 → 除外
        {"seido_id": "t1-b", "posted_at": "2026-08-27"},   # 33日前 → 除外
        {"seido_id": "t1-c", "posted_at": "2026-08-01"},   # 59日前 → 候補に戻る
        {"seido_id": "t1-d"},                              # 日付なし → 安全側で除外
    ]}
    sub, hist = _write(tmp_path, _fixture_items(), history)

    recent = load_historical_post_ids(hist, today=TODAY)
    assert recent == {"t1-a", "t1-b", "t1-d"}

    drafts = generate_ig_posts(subsidies_json=sub, max_posts=5, history_json=hist, today=TODAY)
    ids = [d["seido_id"] for d in drafts]
    assert not set(ids) & recent
    assert "t1-c" in ids
    assert len(ids) == len(set(ids)) == 5


# ---------------------------------------------------------------- 追加の検査

def test_history_formats_and_missing_file(tmp_path):
    assert load_historical_post_ids(str(tmp_path / "nope.json"), today=TODAY) == set()
    p = tmp_path / "h.json"
    p.write_text(json.dumps(["x1", "x2"]), encoding="utf-8")
    assert load_historical_post_ids(str(p), today=TODAY) == {"x1", "x2"}
    p.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        load_historical_post_ids(str(p), today=TODAY)


def test_format_yen():
    assert format_yen(5_000_000) == "500万円"
    assert format_yen(1_500_000_000) == "15億円"
    assert format_yen(143_100_000) == "1億4310万円"
    assert format_yen(29_500_000_000) == "295億円"
    assert format_yen(None) is None
    assert format_yen(0) is None
    assert format_yen(12_345) is None  # 万円で割り切れない額は丸めて断定しない


def test_output_shape_and_gate(tmp_path):
    """出力の形・出荷ゲートの禁止表現・humanizer 検査を通ること。"""
    sub, hist = _write(tmp_path, _fixture_items())
    out = tmp_path / "draft.json"
    drafts = generate_ig_posts(subsidies_json=sub, max_posts=20, history_json=hist,
                               today=TODAY, output_json=str(out))
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved == drafts
    required = {"seido_id", "template", "ig_priority", "seido_name", "caption", "hashtags",
                "ig_before_amount", "ig_after_amount", "image_placeholders",
                "approval_needed", "generated_at"}
    for d in drafts:
        assert required <= set(d), required - set(d)
        assert d["approval_needed"] is True
        assert d["hashtags"][0] == "#沖縄企業のミカタ"
        assert len(d["hashtags"]) == len(set(d["hashtags"]))
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", d["generated_at"])
        assert gen.forbidden_findings(d["caption"] + "\n" + " ".join(d["hashtags"])) == []
        assert "lin.ee" not in json.dumps(d, ensure_ascii=False)
        for tag in d["hashtags"]:
            assert "承継" not in tag and "M&A" not in tag
        assert gen.humanizer_findings(d["seido_id"], d["caption"]) == []

    ph = {d["seido_id"]: d["image_placeholders"] for d in drafts}
    assert ph["t1-a"]["p1_number"] == "500万円"
    assert ph["t1-a"]["p2_before"] == "400万円" and ph["t1-a"]["p2_after"] == "100万円"
    assert ph["t1-b"]["p2_before"] is None  # 試算例が未設定なら空欄のまま(作らない)
    tags = {d["seido_id"]: d["hashtags"] for d in drafts}
    assert "#設備投資" not in tags["t2-a"]  # 相談窓口に既定の分野タグを付けない
    assert ph["t2-a"]["phone"] is None
    assert ph["t2-a"]["qr"].endswith("/go/ig/")
    assert ph["t3-a"]["p1_amount"] == "最大15億円"
    assert ph["t3-b"]["p1_title"] == "事業転換を検討していますか？"
    assert ph["t3-a"]["p1_title"] != "事業転換を検討していますか？"  # 設備投資の制度に「事業転換」と書かない


def test_hooks_are_scattered(tmp_path):
    """同じ週のセットで書き出しが全部同じにならない(定型が透けない)。"""
    sub, hist = _write(tmp_path, _fixture_items())
    drafts = generate_ig_posts(subsidies_json=sub, max_posts=5, history_json=hist, today=TODAY)
    hooks = [d["caption"].splitlines()[1] for d in drafts]
    assert len(set(hooks)) == len(hooks)


def test_verified_mismatch_is_skipped(tmp_path):
    """Task 14 の照合で不一致・矛盾が出た制度は選ばない。"""
    items = _fixture_items()
    items[0]["verified"] = {"claude_verified": False, "gemini_verified": None, "conflict": False}
    items[1]["verified"] = {"claude_verified": True, "gemini_verified": True, "conflict": True}
    sub, hist = _write(tmp_path, items)
    ids = [d["seido_id"] for d in generate_ig_posts(subsidies_json=sub, history_json=hist, today=TODAY)]
    assert "t1-a" not in ids and "t1-b" not in ids


def test_real_data_smoke():
    """実データで落ちずに動き、断定を書かない。"""
    drafts = generate_ig_posts(subsidies_json=REAL_DATA, max_posts=5,
                               history_json=os.devnull, today=TODAY)
    assert 1 <= len(drafts) <= 5
    for d in drafts:
        assert d["days_to_deadline"] is None or d["days_to_deadline"] >= 30
        assert gen.forbidden_findings(d["caption"] + " ".join(d["hashtags"])) == []
