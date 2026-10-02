"""data/subsidies.json に IG 自動化用の ig_* フィールドが揃っていることを検査する。

subsidies.json は {"updated_at", "count", "by_tag", "items", "by_source"} の辞書で、
制度レコードは "items" 配下にある(ブリーフの擬似コードはトップレベルを配列と
仮定していたため、実構造に合わせて items を走査する)。
"""
import json
import os

DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "subsidies.json"
)

IG_FIELDS = [
    "ig_template",
    "ig_priority",
    "ig_example_industry",
    "ig_before_amount",
    "ig_after_amount",
    "ig_exclude",
]


def _load_items():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


def _is_int(v):
    # bool は int のサブクラスなので明示的に除外する
    return isinstance(v, int) and not isinstance(v, bool)


def test_subsidies_schema_has_ig_fields():
    subsidies = _load_items()
    assert len(subsidies) > 0
    for item in subsidies:
        assert 'ig_template' in item, f"Missing ig_template in {item['id']}"
        assert 'ig_priority' in item
        assert 'ig_example_industry' in item
        assert 'ig_before_amount' in item
        assert 'ig_after_amount' in item
        assert 'ig_exclude' in item
        # Type checks
        assert item['ig_template'] in [None, "template1", "template2", "template3"]
        assert item['ig_priority'] is None or _is_int(item['ig_priority'])
        assert isinstance(item['ig_example_industry'], (str, type(None)))
        assert item['ig_before_amount'] is None or _is_int(item['ig_before_amount'])
        assert item['ig_after_amount'] is None or _is_int(item['ig_after_amount'])
        assert isinstance(item['ig_exclude'], bool)


def test_ig_fields_appended_at_end():
    """ig_* は既存フィールドの後ろに、この順で並ぶ(元の並びを崩さない)。"""
    for item in _load_items():
        keys = list(item.keys())
        assert keys[-len(IG_FIELDS):] == IG_FIELDS, f"order broken in {item['id']}"
