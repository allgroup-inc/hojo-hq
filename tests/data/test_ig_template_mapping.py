"""IG 自動化: subsidies.json の ig_template 割当ルールを検査する。

実データ構造は {"items": [...]} で、金額フィールドは max_amount(円)。
ブリーフの擬似コード(トップレベル配列・max_amount_yen)は実構造に合わせて読み替えた。
"""
import datetime
import json
import os

DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "subsidies.json"
)

# SNS投稿は締切まで残り30日以上のみ(CLAUDE.md 締切3層ルール)
SNS_MIN_DAYS = 30
# 事業再構築補助金クラスの規模(5000万円)
TEMPLATE3_MIN_AMOUNT = 50_000_000


def _load_items():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["items"]


def _is_template3_eligible(item):
    max_amount = item.get("max_amount") or 0
    is_transformation = "転換" in (item.get("name") or "")
    is_large = max_amount >= TEMPLATE3_MIN_AMOUNT
    return is_transformation or is_large


def test_template3_mapping_rule():
    items = _load_items()
    template3_items = [s for s in items if s.get("ig_template") == "template3"]

    assert 3 <= len(template3_items) <= 5, (
        f"template3 は3〜5件の想定だが {len(template3_items)} 件"
    )

    priorities = []
    for item in template3_items:
        assert _is_template3_eligible(item), (
            f"{item['id']} は事業転換または5000万円以上でないため template3 不可"
        )
        p = item.get("ig_priority")
        assert isinstance(p, int) and not isinstance(p, bool) and 1 <= p <= 5, (
            f"{item['id']} の ig_priority が 1〜5 の整数でない: {p!r}"
        )
        priorities.append(p)
        assert item.get("ig_example_industry"), (
            f"{item['id']} の ig_example_industry が未設定"
        )
        assert item.get("ig_exclude") is not True, (
            f"{item['id']} は ig_exclude=True なのに template3 に割当"
        )

    assert len(set(priorities)) == len(priorities), (
        f"template3 の ig_priority が重複: {sorted(priorities)}"
    )


def test_template3_respects_sns_30day_rule():
    """template3 に割り当てた時点で締切まで30日以上あること(データ更新日基準)。"""
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    base = datetime.datetime.strptime(
        data["updated_at"][:10], "%Y-%m-%d"
    ).date()
    for item in data["items"]:
        if item.get("ig_template") != "template3":
            continue
        dl = item.get("deadline")
        if not dl:
            continue
        days = (datetime.date.fromisoformat(dl) - base).days
        assert days >= SNS_MIN_DAYS, (
            f"{item['id']} は締切まで{days}日でSNS投稿の対象外(30日以上が必要)"
        )


def test_eligibility_rule_self_check():
    """ガードの正例・負例(再発防止メモ: 検査を足したら正例で試す)。"""
    assert _is_template3_eligible({"name": "テスト", "max_amount": 50_000_000})
    assert _is_template3_eligible({"name": "業態転換支援", "max_amount": 0})
    assert not _is_template3_eligible({"name": "小規模", "max_amount": 49_999_999})
    assert not _is_template3_eligible({"name": None, "max_amount": None})


# --- template1: 上限額100万円以上 AND 締切まで30日以上 ---------------------
# ブリーフの擬似コードは max_amount_yen / days_to_deadline を使っていたが、
# 実データは max_amount(円)と deadline(YYYY-MM-DD)。日数は deadline から計算する。
# 基準日は割当を行った日に固定する(today() 基準だと時間経過だけで CI が落ちる)。
# 投稿時点での「残り30日以上」判定は投稿生成スクリプト側で改めて行う(締切3層ルール)。
TEMPLATE1_REFERENCE_DATE = datetime.date(2026, 9, 28)
TEMPLATE1_MIN_AMOUNT = 1_000_000
TEMPLATE1_MAX_PRIORITY = 40


def _days_to_deadline(item, base=TEMPLATE1_REFERENCE_DATE):
    deadline = item.get("deadline")
    if not deadline:
        return None  # 通年募集(締切なし)
    return (datetime.date.fromisoformat(deadline) - base).days


def _is_template1_eligible(item):
    max_amount = item.get("max_amount")
    if not isinstance(max_amount, int) or isinstance(max_amount, bool):
        return False  # 金額不明(None)は対象外
    days = _days_to_deadline(item)
    return max_amount >= TEMPLATE1_MIN_AMOUNT and (days is None or days >= SNS_MIN_DAYS)


def _template1_items():
    return [s for s in _load_items() if s.get("ig_template") == "template1"]


def test_template1_mapping_rule():
    template1_items = _template1_items()
    assert template1_items, "template1 が1件も割り当てられていない"
    assert len(template1_items) <= TEMPLATE1_MAX_PRIORITY

    for item in template1_items:
        assert _is_template1_eligible(item), (
            f"{item['id']} (max_amount={item.get('max_amount')}, "
            f"締切まで{_days_to_deadline(item)}日) は template1 の条件"
            "(100万円以上・締切30日以上)を満たさない"
        )
        p = item.get("ig_priority")
        assert isinstance(p, int) and not isinstance(p, bool), (
            f"{item['id']} の ig_priority が整数でない: {p!r}"
        )
        assert 1 <= p <= TEMPLATE1_MAX_PRIORITY, (
            f"{item['id']} の ig_priority {p} が 1〜40 の範囲外"
        )
        industry = item.get("ig_example_industry")
        assert isinstance(industry, str) and industry.strip(), (
            f"{item['id']} の ig_example_industry が未設定"
        )
        assert item.get("ig_exclude") is False, (
            f"{item['id']} は ig_exclude={item.get('ig_exclude')!r} なのに template1 に割当"
        )


def test_template1_priorities_are_unique_and_contiguous():
    priorities = sorted(s["ig_priority"] for s in _template1_items())
    assert priorities == list(range(1, len(priorities) + 1)), (
        f"template1 の ig_priority は 1 からの連番・重複なしであること: {priorities}"
    )


def test_template1_priority_order_follows_amount_then_deadline():
    """順位 = 金額の降順、同額なら締切までの日数の降順(締切なしは最長扱い)。"""
    ranked = sorted(_template1_items(), key=lambda s: s["ig_priority"])

    def sort_key(s):
        days = _days_to_deadline(s)
        return (-s["max_amount"], -(days if days is not None else 10**9))

    assert [s["id"] for s in ranked] == [s["id"] for s in sorted(ranked, key=sort_key)]


def test_template1_eligibility_self_check():
    """ガードの正例・負例(再発防止メモ: 検査を足したら正例で試す)。"""
    ok = {"max_amount": 1_000_000, "deadline": "2026-10-28"}  # ちょうど30日
    assert _is_template1_eligible(ok)
    assert _is_template1_eligible({"max_amount": 5_000_000, "deadline": ""})  # 通年
    assert not _is_template1_eligible({"max_amount": 999_999, "deadline": "2027-01-01"})
    assert not _is_template1_eligible({"max_amount": 1_000_000, "deadline": "2026-10-27"})
    assert not _is_template1_eligible({"max_amount": None, "deadline": "2027-01-01"})
    assert not _is_template1_eligible({"max_amount": True, "deadline": "2027-01-01"})
