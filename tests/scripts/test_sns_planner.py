"""SNS 投稿の選び方・割り振り・画像の検査(2026-11-09 第1段階)。すべて合成データ。外部への通信なし。"""
import json
import os
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import sns_planner as P  # noqa: E402

TODAY = date(2026, 11, 16)  # 月曜


def item(i, name="小規模事業者持続化補助金", days=60, area="全国", status="募集中", amount=2_000_000,
         url="https://example.invalid/x", issuer="", employees="従業員数の制約なし", tag="nationwide"):
    return {"id": f"t{i}", "name": name, "deadline": str(TODAY + timedelta(days=days)), "status": status,
            "target_area": area, "source_url": url, "max_amount": amount, "issuer": issuer,
            "employees": employees, "tag": tag}


def text(i, kind, status="確認済み"):
    return {"id": f"{kind}{i:02d}", "type": kind, "status": status}


# ---- 正確さの関門 ----
@pytest.mark.parametrize("kw,why", [
    ({"name": ""}, "制度名が無い"),
    ({"url": "原文参照"}, "原文のURLが無い"),
    ({"status": "要確認"}, "募集中ではない"),
    ({"days": 29}, "30日未満"),
])
def test_screen_rejects_unverifiable(kw, why):
    ok, reason = P.screen(item(1, **kw), TODAY)
    assert not ok and why in reason


def test_screen_rejects_unreadable_deadline():
    it = item(1)
    it["deadline"] = "要確認"
    assert P.screen(it, TODAY) == (False, "締切日が読めない")


def test_screen_accepts_30_days_and_missing_amount():
    assert P.screen(item(1, days=30, amount=None), TODAY) == (True, None)
    assert P.amount_text(item(1, amount=None)) == "金額は原文で確認"


# ---- 地域 ----
@pytest.mark.parametrize("kw", [
    {"name": "【倉敷市】実証実験サポート事業"},
    {"name": "京都市企業立地促進制度補助金"},
    {"name": "東京港物流効率化等事業補助金"},
    {"name": "工事費補助金【関東監督部】"},
    {"area": "北海道"},
])
def test_screen_rejects_outside_okinawa(kw):
    ok, reason = P.screen(item(1, **kw), TODAY)
    assert not ok and "沖縄県外" in reason


@pytest.mark.parametrize("kw", [
    {"name": "【沖縄】最低賃金引上げ支援", "area": "沖縄県"},
    {"name": "那覇市 創業支援補助金", "area": "沖縄県"},
    {"name": "【内閣府】地方創生に資する利子補給制度"},       # 役所の名前は地名ではない
    {"name": "都市ガス分野の災害対応支援事業"},              # 「都市」は地名ではない
])
def test_screen_keeps_okinawa_and_national(kw):
    assert P.screen(item(1, **kw), TODAY) == (True, None)


def test_okinawa_needs_area_not_tag():
    # 全国の制度に tag=okinawa が付いていても、沖縄限定には入れない
    assert not P.is_okinawa(item(1, name="携帯電話等エリア整備事業", area="全国 / 北海道", tag="okinawa"))
    assert P.is_okinawa(item(1, name="奨学金代理返還支援事業", area="沖縄県"))


# ---- 関係の薄い制度・大企業 ----
@pytest.mark.parametrize("name", ["排出削減(事業Ⅰ/鉄鋼)", "休廃止鉱山鉱害防止等工事費補助金",
                                  "電波遮へい対策事業(トンネル)", "鉄道事業の低炭素化", "難病患者非常用電源"])
def test_screen_rejects_unrelated(name):
    ok, reason = P.screen(item(1, name=name), TODAY)
    assert not ok and "関係が薄い" in reason


def test_screen_rejects_large_company():
    ok, reason = P.screen(item(1, employees="901名以上"), TODAY)
    assert not ok and "大企業" in reason


# ---- 表示 ----
def test_short_name_strips_only_year_and_ministry():
    assert P.short_name("【令和８年度】INPIT外国出願補助金") == "INPIT外国出願補助金"
    assert P.short_name("令和７年度（補正）　商用車等の電動化促進事業") == "商用車等の電動化促進事業"
    assert P.short_name("【経済産業省】ものづくり補助金（20次締切）") == "ものづくり補助金（20次締切）"
    assert P.short_name("【事前着手】転換支援事業") == "【事前着手】転換支援事業"   # 意味のある札は残す


def test_far_deadline_shows_month_not_days():
    assert P.deadline_text(item(1, days=1534), TODAY).endswith("月締切")
    assert "あと60日" in P.deadline_text(item(1, days=60), TODAY)


def test_amount_text():
    assert P.amount_text(item(1, amount=2_000_000)) == "上限 200万円"
    assert P.amount_text(item(1, amount=500_000_000)) == "上限 5億円"
    assert P.amount_text(item(1, amount=0)) == "金額は原文で確認"


def test_issuer_hidden_when_empty_or_program_like():
    assert P.issuer_text(item(1, issuer="")) == ""
    assert P.issuer_text(item(1, issuer="二酸化炭素排出抑制対策事業費等補助金")) == ""
    assert P.issuer_text(item(1, issuer="沖縄県産業振興公社")) == "沖縄県産業振興公社"


def test_program_key_merges_rounds():
    a = P.program_key(item(1, name="ものづくり補助金（20次締切）"))
    b = P.program_key(item(2, name="ものづくり補助金（21次締切）"))
    assert a == b
    assert a != P.program_key(item(3, name="IT導入補助金"))


# ---- 割り振り ----
def _items():
    return [item(1, "沖縄県奨学金代理返還支援事業", 120, area="沖縄県"),
            item(2, "ものづくり補助金（20次締切）", 45, amount=35_000_000),
            item(3, "ものづくり補助金（21次締切）", 130, amount=40_000_000),
            item(4, "小規模事業者持続化補助金", 90),
            item(5, "IT導入補助金", 100),
            item(6, "東京港物流効率化等事業補助金", 100),
            item(7, "地上基幹放送ネットワーク整備等事業", 100)]   # 優先③ 一覧には出さない


def _texts():
    return [text(i, "B") for i in range(1, 7)] + [text(i, "C") for i in range(1, 7)]


def test_plan_weekly_pattern_and_no_consecutive_type():
    r = P.plan(_items(), _texts(), TODAY, 13)
    posts = r["posts"]
    assert len(posts) == 13
    assert [p["date"].weekday() for p in posts[:3]] == [0, 2, 4]
    assert posts[0]["type"] == P.TYPE_OKINAWA and posts[1]["type"] == P.TYPE_B
    for a, b in zip(posts, posts[1:]):
        assert a["type"] != b["type"]


def test_plan_no_repeat_within_gap():
    r = P.plan(_items(), _texts(), TODAY, 13)
    seen = {}
    for p in r["posts"]:
        keys = ["p:" + P.program_key(x) for x in p.get("programs", [])]
        keys += ["t:" + p["text"]["id"]] if "text" in p else []
        for k in keys:
            if k in seen:
                assert (p["date"] - seen[k]).days > 28, k   # 28日は決めた値(定数を下げても見逃さない)
            seen[k] = p["date"]
    assert seen, "何も検査していない"


def test_plan_list_never_has_two_rounds_or_low_priority_or_outside():
    r = P.plan(_items(), _texts(), TODAY, 13)
    listed = [x for p in r["posts"] for x in p.get("programs", [])]
    assert listed, "何も検査していない"
    for p in r["posts"]:
        keys = [P.program_key(x) for x in p.get("programs", [])]
        assert len(keys) == len(set(keys))
    names = {x["name"] for x in listed}
    assert "東京港物流効率化等事業補助金" not in names
    assert "地上基幹放送ネットワーク整備等事業" not in names


def test_plan_respects_30_days_from_each_post_date():
    # 締切まで40日の制度は、開始から11日目以降の投稿には出ない
    r = P.plan([item(1, "IT導入補助金", 40), item(2, "持続化補助金", 200)], _texts(), TODAY, 13)
    for p in r["posts"]:
        for x in p.get("programs", []):
            assert (P.parse_deadline(x["deadline"]) - p["date"]).days >= P.MIN_DAYS_LEFT


def test_plan_drafts_only_with_allow_drafts():
    drafts = [text(i, "B", "下書き") for i in range(1, 4)] + [text(i, "C", "下書き") for i in range(1, 4)]
    r = P.plan([], drafts, TODAY, 6)
    assert not any("text" in p for p in r["posts"])
    assert len(r["skipped"]) == 6
    r2 = P.plan([], drafts, TODAY, 6, allow_drafts=True)
    assert all("text" in p for p in r2["posts"]) and r2["posts"]


def test_plan_does_not_mutate_history():
    h = {"t:B01": TODAY - timedelta(days=1)}
    P.plan(_items(), _texts(), TODAY, 5, history=h)
    assert h == {"t:B01": TODAY - timedelta(days=1)}


def test_evergreen_ledger_shape():
    d = json.load(open(os.path.join(ROOT, "data", "sns_evergreen.json"), encoding="utf-8"))
    ids = [e["id"] for e in d["items"]]
    assert len(ids) == len(set(ids))
    for e in d["items"]:
        assert e["type"] in ("B", "C") and e["status"] in ("下書き", "確認済み")
        if e["type"] == "B":
            assert e["title"] and len(e["columns"]) == 2
        else:
            assert e["title_main"] and len(e["checks"]) == 3


# ---- 画像の検査 ----
T = pytest.importorskip("sns_templates")


def _fonts_ok():
    try:
        T.Canvas((0, 0, 0))
        return True
    except T.LayoutError:
        return False


fonts = pytest.mark.skipif(not _fonts_ok(), reason="日本語フォントが無い環境")


@fonts
def test_render_all_types():
    ever = json.load(open(os.path.join(ROOT, "data", "sns_evergreen.json"), encoding="utf-8"))["items"]
    for e in ever:
        im = T.render({"type": e["type"], "text": e}, TODAY, "見本")
        assert im.size == (1080, 1080)
    progs = _items()[1:5]
    assert T.render({"type": "A", "programs": progs[:3]}, TODAY).size == (1080, 1080)
    assert T.render({"type": "A", "programs": progs[:1]}, TODAY).size == (1080, 1080)
    assert T.render({"type": "OKINAWA", "programs": _items()[:1]}, TODAY).size == (1080, 1080)


@fonts
def test_render_rejects_too_long_name():
    long = item(9, "あ" * 200)
    with pytest.raises(T.LayoutError):
        T.render({"type": "A", "programs": [long, item(2)]}, TODAY)


@fonts
def test_check_detects_overlap_and_overflow():
    c = T.Canvas((255, 255, 255))
    c.text((100, 200), "かさなる文字", 40, (0, 0, 0))
    c.text((110, 210), "かさなる文字", 40, (0, 0, 0))
    with pytest.raises(T.LayoutError, match="重なり"):
        c.check()
    c2 = T.Canvas((255, 255, 255))
    c2.text((900, 500), "はみ出す長い文字です", 60, (0, 0, 0))
    with pytest.raises(T.LayoutError, match="はみ出し"):
        c2.check()
    c3 = T.Canvas((255, 255, 255))
    c3.text((100, 200), "ふつうの文字", 40, (0, 0, 0))
    c3.text((100, 300), "ふつうの文字", 40, (0, 0, 0))
    c3.check()   # 正例: 重ならず収まっていれば通る


def test_preview_refuses_repo_output_dirs(tmp_path):
    import make_sns_month_preview as M
    assert M.main(["--out", os.path.join(ROOT, "posts", "x")]) == 2
    assert M.main(["--out", os.path.join(ROOT, "site")]) == 2
