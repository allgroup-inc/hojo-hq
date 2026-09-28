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
