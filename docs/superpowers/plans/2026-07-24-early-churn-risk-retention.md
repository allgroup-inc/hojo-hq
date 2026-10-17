# 早期解約リスク保全システム Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 申込〜解約の実績(CSV)から「6ヶ月以内解約リスク%」を要因つきで算出し、高リスク先へ先回り保全をあてるための一覧/カード/レポートを出す。

**Architecture:** 4段パイプライン（取込 → 学習 → 採点 → 出力）を、それぞれ独立した純Pythonモジュールとして実装する。学習は「成熟した実績のみ」から要因別リスク率（スムージング付き）を算出し `risk_model.json` に保存。採点はナイーブベイズ流にオッズ比を合成して確率を出し、ヒット要因トップ3とリスク帯を返す。将来のB案（機械学習）は `fit`/`score` の内部だけ差し替え可能。

**Tech Stack:** Python 3.12・標準ライブラリのみ（`csv` `json` `datetime` `math` `argparse`）。テストは stdlib `unittest`（`python -m unittest`）。追加のpip依存なし。

## Global Constraints

- **Python 3.12 / 標準ライブラリのみ**。pandas・numpy・scikit-learn 等は使わない（既存 `scripts/*.py` の作法に準拠）。
- **個人情報は絶対にコミットしない**。入力CSV・モデル・出力はすべて `private/` 配下（`.gitignore` 除外）。コミットするのはコードと **PIIを含まない例ファイル**のみ。
- **入力の正準形式は CSV**（統一エクセルの1シートをCSVエクスポートしたもの）。列名のゆらぎは `column_map` で吸収する。
- **早期解約の定義 = 申込から6ヶ月以内の解約**（`EARLY_CHURN_MONTHS = 6`）。
- **学習に使うのは成熟した実績のみ**（6ヶ月経過済み or 既に6ヶ月以内解約）。未成熟の継続中は母数に入れない。
- **採点対象は「継続中 × 申込から6ヶ月未満」**（=これから手を打てる人）。
- **名称は仮置き**（部門名・スペシャリスト名・QCMの正式定義は小柳さん決裁事項）。コード内の識別子は英語、利用者向け表示は日本語。
- 顧客の年齢は年代にビン化し、氏名は使わず `apply_id` で扱う。

**参照設計書:** `docs/superpowers/specs/2026-07-24-early-churn-risk-retention-design.md`

---

### Task 1: パッケージ雛形・PII除外・日付ユーティリティ

**Files:**
- Create: `scripts/churn/__init__.py`
- Create: `scripts/churn/dates.py`
- Create: `tests/churn/__init__.py`
- Create: `tests/churn/test_dates.py`
- Modify: `.gitignore`（末尾に `private/` を追加）

**Interfaces:**
- Consumes: なし
- Produces:
  - `add_months(d: datetime.date, n: int) -> datetime.date`（月末クランプ付き。例: 1/31 + 1ヶ月 = 2/28）
  - `has_reached_months(start: date, as_of: date, months: int) -> bool`（`as_of >= start + months`）
  - `is_within_months(start: date, end: date, months: int) -> bool`（`end <= start + months`、6ヶ月"以内"は境界含む）

- [ ] **Step 1: `.gitignore` に private/ を追加**

`.gitignore` の末尾に追記：

```
# 早期解約リスク保全: 顧客個人データ・モデル・出力はコミットしない
private/
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/churn/__init__.py` は空ファイルで作成。`tests/churn/test_dates.py`:

```python
import unittest
from datetime import date
from scripts.churn.dates import add_months, has_reached_months, is_within_months


class TestDates(unittest.TestCase):
    def test_add_months_simple(self):
        self.assertEqual(add_months(date(2026, 1, 15), 6), date(2026, 7, 15))

    def test_add_months_clamps_end_of_month(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_add_months_crosses_year(self):
        self.assertEqual(add_months(date(2025, 10, 10), 6), date(2026, 4, 10))

    def test_has_reached_months_true_on_boundary(self):
        self.assertTrue(has_reached_months(date(2026, 1, 1), date(2026, 7, 1), 6))

    def test_has_reached_months_false_before(self):
        self.assertFalse(has_reached_months(date(2026, 1, 1), date(2026, 6, 30), 6))

    def test_is_within_months_inclusive_boundary(self):
        self.assertTrue(is_within_months(date(2026, 1, 1), date(2026, 7, 1), 6))

    def test_is_within_months_excludes_after(self):
        self.assertFalse(is_within_months(date(2026, 1, 1), date(2026, 7, 2), 6))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_dates -v`
Expected: FAIL（`ModuleNotFoundError: scripts.churn.dates`）

- [ ] **Step 4: 実装する**

`scripts/churn/__init__.py` は空ファイル。`scripts/churn/dates.py`:

```python
"""日付ユーティリティ：6ヶ月境界の判定を1か所に集約する。"""
from __future__ import annotations
import calendar
from datetime import date


def add_months(d: date, n: int) -> date:
    """d の n ヶ月後。月末は対象月の末日にクランプする（1/31 + 1ヶ月 = 2/28）。"""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def has_reached_months(start: date, as_of: date, months: int) -> bool:
    """start から months ヶ月が経過したか（境界当日を含む）。"""
    return as_of >= add_months(start, months)


def is_within_months(start: date, end: date, months: int) -> bool:
    """end が start から months ヶ月以内か（境界当日を含む）。"""
    return end <= add_months(start, months)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_dates -v`
Expected: PASS（7件）

- [ ] **Step 6: コミット**

```bash
git add .gitignore scripts/churn/__init__.py scripts/churn/dates.py tests/churn/__init__.py tests/churn/test_dates.py
git commit -m "feat(churn): 日付ユーティリティとprivate/除外を追加"
```

---

### Task 2: レコード正規化スキーマ（属性ビン化・成熟度・早期解約フラグ）

**Files:**
- Create: `scripts/churn/config.py`
- Create: `scripts/churn/schema.py`
- Create: `tests/churn/test_schema.py`

**Interfaces:**
- Consumes: `scripts.churn.dates`（Task 1）
- Produces:
  - `config.EARLY_CHURN_MONTHS = 6`, `config.AGE_BANDS`, `config.AMOUNT_EDGES`, `config.FACTOR_FIELDS`
  - `schema.bin_age(age: int | None) -> str`
  - `schema.bin_amount(amount: float | None, edges: list[float]) -> str`
  - `schema.parse_date(value: str | None) -> datetime.date | None`（`YYYY-MM-DD` / `YYYY/M/D` を許容、空は None）
  - `schema.parse_amount(value: str | None) -> float | None`（カンマ・「円」除去、空は None）
  - `schema.normalize_record(raw: dict, column_map: dict, as_of: date) -> dict`
    返すキー: `apply_id, apply_date, product, channel, apply_form, amount, amount_band, age_band, gender, area, agent_id, cancel_date, cancel_reason, is_early_churn(0/1/None), is_resolved(bool), is_scoreable(bool)`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_schema.py`:

```python
import unittest
from datetime import date
from scripts.churn import schema
from scripts.churn.config import AMOUNT_EDGES

COLUMN_MAP = {
    "apply_id": "申込ID", "apply_date": "申込日", "product": "商品",
    "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}


def raw(**over):
    base = {"申込ID": "A1", "申込日": "2026-01-01", "商品": "X", "集客": "催事",
            "申込形態": "対面", "金額": "5,000円", "年齢": "25", "性別": "女",
            "地域": "那覇", "営業担当": "S1", "解約日": "", "解約理由": ""}
    base.update(over)
    return base


class TestSchema(unittest.TestCase):
    def test_bin_age(self):
        self.assertEqual(schema.bin_age(25), "20代")
        self.assertEqual(schema.bin_age(None), "不明")

    def test_bin_amount(self):
        self.assertEqual(schema.bin_amount(5000, AMOUNT_EDGES), "3千〜1万")
        self.assertEqual(schema.bin_amount(None, AMOUNT_EDGES), "不明")

    def test_parse_amount_strips_symbols(self):
        self.assertEqual(schema.parse_amount("5,000円"), 5000.0)
        self.assertIsNone(schema.parse_amount(""))

    def test_early_churn_within_6_months(self):
        r = schema.normalize_record(raw(解約日="2026-04-01"), COLUMN_MAP, date(2026, 7, 25))
        self.assertEqual(r["is_early_churn"], 1)
        self.assertTrue(r["is_resolved"])
        self.assertFalse(r["is_scoreable"])

    def test_late_cancel_is_not_early_churn(self):
        r = schema.normalize_record(raw(解約日="2026-09-01"), COLUMN_MAP, date(2026, 12, 1))
        self.assertEqual(r["is_early_churn"], 0)
        self.assertTrue(r["is_resolved"])

    def test_survived_active_past_6_months(self):
        r = schema.normalize_record(raw(), COLUMN_MAP, date(2026, 8, 1))
        self.assertEqual(r["is_early_churn"], 0)
        self.assertTrue(r["is_resolved"])
        self.assertFalse(r["is_scoreable"])

    def test_active_under_6_months_is_scoreable_not_resolved(self):
        r = schema.normalize_record(raw(), COLUMN_MAP, date(2026, 3, 1))
        self.assertIsNone(r["is_early_churn"])
        self.assertFalse(r["is_resolved"])
        self.assertTrue(r["is_scoreable"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_schema -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: config を実装**

`scripts/churn/config.py`:

```python
"""早期解約リスク保全システムの定数・チューニング値。"""

EARLY_CHURN_MONTHS = 6

# 年代ビン
AGE_BANDS = [(0, 19, "〜10代"), (20, 29, "20代"), (30, 39, "30代"),
             (40, 49, "40代"), (50, 59, "50代"), (60, 200, "60代〜")]

# 金額ビンの境界（円）。商品特性に応じて小柳さん決裁で調整可。
AMOUNT_EDGES = [3000, 10000, 30000]
AMOUNT_LABELS = ["〜3千", "3千〜1万", "1万〜3万", "3万〜"]

# リスク要因として使う内部項目
FACTOR_FIELDS = ["product", "channel", "apply_form", "amount_band",
                 "age_band", "gender", "area", "agent_id"]

# 学習のスムージング強度（大きいほど少件数を全体平均へ強く引き寄せる）
SMOOTHING_K = 30
# 「参考値」と注記する最小件数（これ未満は母数不足）
MIN_RELIABLE_N = 20

# リスク帯の閾値（ベース解約率に対する倍率）
BAND_HIGH_MULT = 2.0
BAND_LOW_MULT = 1.0
```

- [ ] **Step 4: schema を実装**

`scripts/churn/schema.py`:

```python
"""生CSV行 → 内部正規化レコード。成熟度・早期解約フラグまで計算する。"""
from __future__ import annotations
from datetime import date, datetime

from .config import AGE_BANDS, AMOUNT_EDGES, AMOUNT_LABELS, EARLY_CHURN_MONTHS
from .dates import has_reached_months, is_within_months


def bin_age(age):
    if age is None:
        return "不明"
    for lo, hi, label in AGE_BANDS:
        if lo <= age <= hi:
            return label
    return "不明"


def bin_amount(amount, edges=AMOUNT_EDGES):
    if amount is None:
        return "不明"
    for i, edge in enumerate(edges):
        if amount < edge:
            return AMOUNT_LABELS[i]
    return AMOUNT_LABELS[len(edges)]


def parse_date(value):
    if not value or not str(value).strip():
        return None
    text = str(value).strip().replace("/", "-")
    parts = text.split("-")
    if len(parts) != 3:
        raise ValueError(f"日付を解釈できません: {value!r}")
    y, m, d = (int(p) for p in parts)
    return date(y, m, d)


def parse_amount(value):
    if value is None:
        return None
    text = str(value).replace(",", "").replace("円", "").strip()
    if not text:
        return None
    return float(text)


def _get(raw, column_map, key):
    """column_map[key] で指す実列の値。マップに無ければ None。"""
    col = column_map.get(key)
    if col is None:
        return None
    return raw.get(col)


def normalize_record(raw, column_map, as_of):
    apply_date = parse_date(_get(raw, column_map, "apply_date"))
    cancel_date = parse_date(_get(raw, column_map, "cancel_date"))
    age_raw = _get(raw, column_map, "age")
    age = int(str(age_raw).strip()) if age_raw and str(age_raw).strip() else None
    amount = parse_amount(_get(raw, column_map, "amount"))

    is_early_churn = None
    is_resolved = False
    is_scoreable = False
    if cancel_date is not None and apply_date is not None:
        is_resolved = True
        is_early_churn = 1 if is_within_months(apply_date, cancel_date, EARLY_CHURN_MONTHS) else 0
    elif apply_date is not None:
        if has_reached_months(apply_date, as_of, EARLY_CHURN_MONTHS):
            is_resolved = True
            is_early_churn = 0  # 6ヶ月生存
        else:
            is_scoreable = True  # 継続中・6ヶ月未満 = これから手を打てる

    return {
        "apply_id": _get(raw, column_map, "apply_id"),
        "apply_date": apply_date,
        "product": (_get(raw, column_map, "product") or "不明"),
        "channel": (_get(raw, column_map, "channel") or "不明"),
        "apply_form": (_get(raw, column_map, "apply_form") or "不明"),
        "amount": amount,
        "amount_band": bin_amount(amount),
        "age_band": bin_age(age),
        "gender": (_get(raw, column_map, "gender") or "不明"),
        "area": (_get(raw, column_map, "area") or "不明"),
        "agent_id": (_get(raw, column_map, "agent_id") or "不明"),
        "cancel_date": cancel_date,
        "cancel_reason": (_get(raw, column_map, "cancel_reason") or ""),
        "is_early_churn": is_early_churn,
        "is_resolved": is_resolved,
        "is_scoreable": is_scoreable,
    }
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_schema -v`
Expected: PASS（7件）

- [ ] **Step 6: コミット**

```bash
git add scripts/churn/config.py scripts/churn/schema.py tests/churn/test_schema.py
git commit -m "feat(churn): レコード正規化・年代/金額ビン化・成熟度判定"
```

---

### Task 3: CSV取込（column_map で列名のゆらぎを吸収）

**Files:**
- Create: `scripts/churn/intake.py`
- Create: `docs/churn/column_map.example.json`（PIIなし・コミット可）
- Create: `tests/churn/test_intake.py`

**Interfaces:**
- Consumes: `scripts.churn.schema.normalize_record`（Task 2）
- Produces:
  - `intake.load_column_map(path: str) -> dict`
  - `intake.read_rows(csv_path: str) -> list[dict]`（`csv.DictReader`）
  - `intake.load_records(csv_path: str, column_map: dict, as_of: date) -> list[dict]`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_intake.py`:

```python
import unittest
import tempfile
import os
from datetime import date
from scripts.churn import intake

COLUMN_MAP = {
    "apply_id": "申込ID", "apply_date": "申込日", "product": "商品",
    "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}

CSV = (
    "申込ID,申込日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由\n"
    "A1,2026-01-01,X,催事,対面,5000,25,女,那覇,S1,2026-03-01,高い\n"
    "A2,2026-01-10,Y,紹介,オンライン,8000,42,男,浦添,S2,,\n"
)


class TestIntake(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(CSV)

    def tearDown(self):
        os.remove(self.path)

    def test_read_rows(self):
        rows = intake.read_rows(self.path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["商品"], "X")

    def test_load_records_normalizes(self):
        recs = intake.load_records(self.path, COLUMN_MAP, date(2026, 7, 25))
        self.assertEqual(recs[0]["is_early_churn"], 1)
        self.assertEqual(recs[1]["product"], "Y")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_intake -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: intake を実装**

`scripts/churn/intake.py`:

```python
"""CSV取込：実列 → column_map → 正規化レコード。"""
from __future__ import annotations
import csv
import json

from .schema import normalize_record


def load_column_map(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_records(csv_path, column_map, as_of):
    return [normalize_record(row, column_map, as_of) for row in read_rows(csv_path)]
```

- [ ] **Step 4: 例 column_map を作成**

`docs/churn/column_map.example.json`（実エクセルの列名に合わせて `private/column_map.json` にコピーして使う。PIIなし）:

```json
{
  "apply_id": "申込ID",
  "apply_date": "申込日",
  "product": "商品",
  "channel": "集客チャネル",
  "apply_form": "申込形態",
  "amount": "金額",
  "age": "年齢",
  "gender": "性別",
  "area": "地域",
  "agent_id": "営業担当",
  "cancel_date": "解約日",
  "cancel_reason": "解約理由"
}
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_intake -v`
Expected: PASS（2件）

- [ ] **Step 6: コミット**

```bash
git add scripts/churn/intake.py docs/churn/column_map.example.json tests/churn/test_intake.py
git commit -m "feat(churn): CSV取込とcolumn_map（列名ゆらぎ吸収）"
```

---

### Task 4: 学習（要因別リスク率＋スムージング → risk_model.json）

**Files:**
- Create: `scripts/churn/fit.py`
- Create: `tests/churn/test_fit.py`

**Interfaces:**
- Consumes: `scripts.churn.config`（`FACTOR_FIELDS`, `SMOOTHING_K`）
- Produces:
  - `fit.odds(p: float) -> float`（`p/(1-p)`、pを`[1e-6, 1-1e-6]`にクランプ）
  - `fit.fit_model(records: list[dict], factor_fields=FACTOR_FIELDS, smoothing_k=SMOOTHING_K) -> dict`
    model構造: `{"base_rate": float, "smoothing_k": int, "n_resolved": int, "temperature": 1.0, "factors": {field: {value: {"n": int, "rate": float, "odds_ratio": float}}}}`
  - `fit.save_model(model: dict, path: str) -> None` / `fit.load_model(path: str) -> dict`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_fit.py`:

```python
import unittest
import tempfile
import os
from scripts.churn import fit


def rec(product, early, resolved=True):
    return {"product": product, "channel": "c", "apply_form": "f",
            "amount_band": "a", "age_band": "20代", "gender": "女",
            "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}


class TestFit(unittest.TestCase):
    def test_base_rate_uses_resolved_only(self):
        recs = [rec("X", 1), rec("X", 0), rec("Y", 0),
                rec("Z", None, resolved=False)]  # 未成熟は除外
        model = fit.fit_model(recs)
        self.assertAlmostEqual(model["base_rate"], 1 / 3, places=6)
        self.assertEqual(model["n_resolved"], 3)

    def test_high_risk_factor_has_odds_ratio_above_one(self):
        recs = [rec("X", 1) for _ in range(40)] + [rec("Y", 0) for _ in range(40)]
        model = fit.fit_model(recs)
        self.assertGreater(model["factors"]["product"]["X"]["odds_ratio"], 1.0)
        self.assertLess(model["factors"]["product"]["Y"]["odds_ratio"], 1.0)

    def test_smoothing_pulls_small_n_toward_base(self):
        # Xは1件だけ全部解約。スムージングで rate は 1.0 より十分低い。
        recs = [rec("X", 1)] + [rec("Y", 0) for _ in range(40)] + [rec("Y", 1) for _ in range(10)]
        model = fit.fit_model(recs, smoothing_k=30)
        self.assertLess(model["factors"]["product"]["X"]["rate"], 0.6)
        self.assertEqual(model["factors"]["product"]["X"]["n"], 1)

    def test_save_and_load_roundtrip(self):
        model = fit.fit_model([rec("X", 1), rec("X", 0)])
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            fit.save_model(model, path)
            loaded = fit.load_model(path)
            self.assertEqual(loaded["n_resolved"], model["n_resolved"])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_fit -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: fit を実装**

`scripts/churn/fit.py`:

```python
"""学習：成熟実績から要因別リスク率（スムージング付き）とオッズ比を算出。"""
from __future__ import annotations
import json

from .config import FACTOR_FIELDS, SMOOTHING_K

_EPS = 1e-6


def odds(p):
    p = min(max(p, _EPS), 1 - _EPS)
    return p / (1 - p)


def fit_model(records, factor_fields=FACTOR_FIELDS, smoothing_k=SMOOTHING_K):
    resolved = [r for r in records if r.get("is_resolved")]
    n_resolved = len(resolved)
    n_churn = sum(r["is_early_churn"] for r in resolved)
    base_rate = (n_churn / n_resolved) if n_resolved else 0.0
    base_odds = odds(base_rate)

    factors = {}
    for field in factor_fields:
        buckets = {}
        for r in resolved:
            value = r.get(field, "不明")
            b = buckets.setdefault(value, {"n": 0, "c": 0})
            b["n"] += 1
            b["c"] += r["is_early_churn"]
        field_out = {}
        for value, b in buckets.items():
            # スムージング：観測解約率を全体平均へ smoothing_k 件ぶん引き寄せる
            smoothed = (b["c"] + smoothing_k * base_rate) / (b["n"] + smoothing_k)
            field_out[value] = {
                "n": b["n"],
                "rate": smoothed,
                "odds_ratio": odds(smoothed) / base_odds,
            }
        factors[field] = field_out

    return {
        "base_rate": base_rate,
        "smoothing_k": smoothing_k,
        "n_resolved": n_resolved,
        "temperature": 1.0,
        "factors": factors,
    }


def save_model(model, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)


def load_model(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_fit -v`
Expected: PASS（4件）

- [ ] **Step 5: コミット**

```bash
git add scripts/churn/fit.py tests/churn/test_fit.py
git commit -m "feat(churn): 学習（要因別リスク率・スムージング・オッズ比）"
```

---

### Task 5: 採点（リスク%・ヒット要因トップ3・リスク帯）

**Files:**
- Create: `scripts/churn/score.py`
- Create: `tests/churn/test_score.py`

**Interfaces:**
- Consumes: `scripts.churn.fit`（`odds`, model構造）, `scripts.churn.config`（`FACTOR_FIELDS`, `BAND_HIGH_MULT`, `BAND_LOW_MULT`, `MIN_RELIABLE_N`）
- Produces:
  - `score.score_record(record: dict, model: dict) -> dict`
    返り値: `{"risk": float(0..1), "band": "high"|"med"|"low", "base_rate": float, "hit_factors": [{"field","value","odds_ratio","direction","n","reference": bool}]}`
  - `score.band_of(risk: float, base_rate: float) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_score.py`:

```python
import unittest
from scripts.churn import fit, score


def rec(product, early, resolved=True, **extra):
    base = {"product": product, "channel": "c", "apply_form": "f",
            "amount_band": "a", "age_band": "20代", "gender": "女",
            "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}
    base.update(extra)
    return base


def build_model():
    recs = [rec("X", 1) for _ in range(40)] + [rec("Y", 0) for _ in range(40)]
    return fit.fit_model(recs)


class TestScore(unittest.TestCase):
    def test_high_risk_product_scores_higher_than_low(self):
        model = build_model()
        high = score.score_record(rec("X", None, resolved=False), model)
        low = score.score_record(rec("Y", None, resolved=False), model)
        self.assertGreater(high["risk"], low["risk"])
        self.assertEqual(high["band"], "high")

    def test_hit_factors_top3_sorted_by_impact(self):
        model = build_model()
        out = score.score_record(rec("X", None, resolved=False), model)
        self.assertLessEqual(len(out["hit_factors"]), 3)
        impacts = [abs(f["odds_ratio"] - 1) for f in out["hit_factors"]]
        self.assertEqual(impacts, sorted(impacts, reverse=True))
        self.assertEqual(out["hit_factors"][0]["direction"], "up")

    def test_risk_between_0_and_1(self):
        model = build_model()
        out = score.score_record(rec("X", None, resolved=False), model)
        self.assertTrue(0.0 <= out["risk"] <= 1.0)

    def test_low_n_factor_flagged_reference(self):
        recs = [rec("X", 1)] + [rec("Y", 0) for _ in range(60)]
        model = fit.fit_model(recs)
        out = score.score_record(rec("X", None, resolved=False), model)
        x_hit = [f for f in out["hit_factors"] if f["field"] == "product" and f["value"] == "X"]
        self.assertTrue(x_hit and x_hit[0]["reference"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_score -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: score を実装**

`scripts/churn/score.py`:

```python
"""採点：モデルのオッズ比を合成してリスク%・帯・ヒット要因を返す。"""
from __future__ import annotations
import math

from .config import (BAND_HIGH_MULT, BAND_LOW_MULT, FACTOR_FIELDS, MIN_RELIABLE_N)
from .fit import odds


def band_of(risk, base_rate):
    if risk >= BAND_HIGH_MULT * base_rate:
        return "high"
    if risk <= BAND_LOW_MULT * base_rate:
        return "low"
    return "med"


def score_record(record, model, factor_fields=FACTOR_FIELDS):
    base_rate = model["base_rate"]
    temperature = model.get("temperature", 1.0)
    log_odds = math.log(odds(base_rate))
    contributions = []

    for field in factor_fields:
        value = record.get(field, "不明")
        entry = model["factors"].get(field, {}).get(value)
        if not entry:
            continue  # 未知の値は寄与なし（ベースのまま）
        or_v = entry["odds_ratio"]
        log_odds += temperature * math.log(or_v)
        contributions.append({
            "field": field, "value": value, "odds_ratio": or_v,
            "direction": "up" if or_v > 1 else "down",
            "n": entry["n"], "reference": entry["n"] < MIN_RELIABLE_N,
        })

    combined_odds = math.exp(log_odds)
    risk = combined_odds / (1 + combined_odds)
    contributions.sort(key=lambda c: abs(math.log(c["odds_ratio"])), reverse=True)

    return {
        "risk": risk,
        "band": band_of(risk, base_rate),
        "base_rate": base_rate,
        "hit_factors": contributions[:3],
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_score -v`
Expected: PASS（4件）

- [ ] **Step 5: コミット**

```bash
git add scripts/churn/score.py tests/churn/test_score.py
git commit -m "feat(churn): 採点（リスク%・帯・ヒット要因トップ3）"
```

---

### Task 6: バックテスト（本当に当たるかの品質ゲート）＋温度較正

**Files:**
- Create: `scripts/churn/evaluate.py`
- Create: `tests/churn/test_evaluate.py`

**Interfaces:**
- Consumes: `scripts.churn.fit.fit_model`, `scripts.churn.score.score_record`
- Produces:
  - `evaluate.auc(pairs: list[tuple[float, int]]) -> float`（`(risk, actual0/1)` から Mann-Whitney AUC。全同一クラスは0.5）
  - `evaluate.split_by_apply_date(records: list[dict], split: date) -> tuple[list, list]`（train=`apply_date < split`, test=`apply_date >= split`。どちらも `is_resolved` のみ）
  - `evaluate.backtest(records: list[dict], split: date) -> dict`
    返り値: `{"n_train","n_test","pred_mean","actual_mean","auc","top_decile_lift"}`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_evaluate.py`:

```python
import unittest
from datetime import date
from scripts.churn import evaluate


class TestEvaluate(unittest.TestCase):
    def test_auc_perfect_separation(self):
        pairs = [(0.9, 1), (0.8, 1), (0.2, 0), (0.1, 0)]
        self.assertAlmostEqual(evaluate.auc(pairs), 1.0, places=6)

    def test_auc_single_class_is_half(self):
        self.assertEqual(evaluate.auc([(0.9, 1), (0.8, 1)]), 0.5)

    def test_split_by_apply_date(self):
        recs = [
            {"apply_date": date(2025, 1, 1), "is_resolved": True},
            {"apply_date": date(2026, 6, 1), "is_resolved": True},
            {"apply_date": date(2026, 6, 1), "is_resolved": False},  # 未成熟は除外
        ]
        train, test = evaluate.split_by_apply_date(recs, date(2026, 1, 1))
        self.assertEqual(len(train), 1)
        self.assertEqual(len(test), 1)

    def test_backtest_reports_metrics(self):
        def r(product, early, apply_d):
            return {"product": product, "channel": "c", "apply_form": "f",
                    "amount_band": "a", "age_band": "20代", "gender": "女",
                    "area": "那覇", "agent_id": "S1", "apply_date": apply_d,
                    "is_resolved": True, "is_early_churn": early}
        recs = ([r("X", 1, date(2025, i % 12 + 1, 1)) for i in range(40)]
                + [r("Y", 0, date(2025, i % 12 + 1, 1)) for i in range(40)]
                + [r("X", 1, date(2026, 6, 1)) for _ in range(10)]
                + [r("Y", 0, date(2026, 6, 1)) for _ in range(10)])
        m = evaluate.backtest(recs, date(2026, 1, 1))
        self.assertEqual(m["n_test"], 20)
        self.assertGreaterEqual(m["auc"], 0.8)  # X/Yで綺麗に分かれる


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_evaluate -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: evaluate を実装**

`scripts/churn/evaluate.py`:

```python
"""バックテスト：過去の一時点で採点したら当たったかを検証する品質ゲート。"""
from __future__ import annotations

from .fit import fit_model
from .score import score_record


def auc(pairs):
    """(risk, actual) のリストから Mann-Whitney AUC。"""
    pos = [r for r, y in pairs if y == 1]
    neg = [r for r, y in pairs if y == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(pos) * len(neg))


def split_by_apply_date(records, split):
    resolved = [r for r in records if r.get("is_resolved") and r.get("apply_date")]
    train = [r for r in resolved if r["apply_date"] < split]
    test = [r for r in resolved if r["apply_date"] >= split]
    return train, test


def backtest(records, split):
    train, test = split_by_apply_date(records, split)
    model = fit_model(train)
    scored = [(score_record(r, model)["risk"], r["is_early_churn"]) for r in test]
    n_test = len(test)
    pred_mean = sum(s for s, _ in scored) / n_test if n_test else 0.0
    actual_mean = sum(y for _, y in scored) / n_test if n_test else 0.0

    # 上位10%のリフト（高リスク上位の実際の解約率 / 全体）
    top_decile_lift = 0.0
    if n_test >= 10 and actual_mean > 0:
        ranked = sorted(scored, key=lambda x: x[0], reverse=True)
        k = max(1, n_test // 10)
        top_rate = sum(y for _, y in ranked[:k]) / k
        top_decile_lift = top_rate / actual_mean

    return {
        "n_train": len(train), "n_test": n_test,
        "pred_mean": pred_mean, "actual_mean": actual_mean,
        "auc": auc(scored), "top_decile_lift": top_decile_lift,
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_evaluate -v`
Expected: PASS（4件）

- [ ] **Step 5: コミット**

```bash
git add scripts/churn/evaluate.py tests/churn/test_evaluate.py
git commit -m "feat(churn): バックテスト（AUC・較正・上位リフト）"
```

---

### Task 7: 一覧出力（リスク高い順・帯・ヒット要因・推奨アクション）

**Files:**
- Create: `scripts/churn/actions.py`
- Create: `scripts/churn/report_list.py`
- Create: `tests/churn/test_report_list.py`

**Interfaces:**
- Consumes: `scripts.churn.score.score_record`
- Produces:
  - `actions.action_for_band(band: str) -> str`
  - `report_list.build_rows(scoreable_records: list[dict], model: dict) -> list[dict]`
    各row: `{"apply_id","agent_id","product","channel","risk","risk_pct","band","hit_summary","action"}`、risk降順
  - `report_list.render_csv(rows: list[dict], path: str) -> None`
  - `report_list.render_html(rows: list[dict], path: str) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_report_list.py`:

```python
import unittest
import tempfile
import os
from scripts.churn import fit, report_list, actions


def rec(product, early=None, resolved=True, apply_id="A", **ov):
    base = {"apply_id": apply_id, "product": product, "channel": "催事",
            "apply_form": "f", "amount_band": "a", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}
    base.update(ov)
    return base


def build_model():
    recs = [rec("X", 1) for _ in range(40)] + [rec("Y", 0) for _ in range(40)]
    return fit.fit_model(recs)


class TestReportList(unittest.TestCase):
    def test_rows_sorted_by_risk_desc(self):
        model = build_model()
        scoreable = [rec("Y", None, False, "LOW"), rec("X", None, False, "HIGH")]
        rows = report_list.build_rows(scoreable, model)
        self.assertEqual(rows[0]["apply_id"], "HIGH")
        self.assertGreaterEqual(rows[0]["risk"], rows[1]["risk"])

    def test_action_maps_band(self):
        self.assertIn("安心コール", actions.action_for_band("high"))
        self.assertEqual(actions.action_for_band("low"), "通常運用")

    def test_render_csv_and_html(self):
        model = build_model()
        rows = report_list.build_rows([rec("X", None, False, "HIGH")], model)
        for ext, render in ((".csv", report_list.render_csv), (".html", report_list.render_html)):
            fd, path = tempfile.mkstemp(suffix=ext)
            os.close(fd)
            try:
                render(rows, path)
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("HIGH", content)
            finally:
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_report_list -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: actions を実装**

`scripts/churn/actions.py`:

```python
"""リスク帯 → 手厚い保全アクションの型（テアツ部門設計）。"""
from __future__ import annotations

_ACTIONS = {
    "high": "申込直後の安心コール＋3ヶ月まで定期接触＋ヒット要因に応じた個別フォロー（7日以内に初回）",
    "med": "オンボーディング配信＋1回フォロー。改善なければ高扱いへ",
    "low": "通常運用",
}


def action_for_band(band):
    return _ACTIONS.get(band, "通常運用")
```

- [ ] **Step 4: report_list を実装**

`scripts/churn/report_list.py`:

```python
"""一覧出力：継続中×6ヶ月未満をリスク高い順に並べる（CSV / HTML）。"""
from __future__ import annotations
import csv
import html

from .score import score_record
from .actions import action_for_band

_HEADERS = ["apply_id", "agent_id", "product", "channel", "risk_pct", "band", "hit_summary", "action"]
_BAND_COLOR = {"high": "#F88800", "med": "#FFD27F", "low": "#EAF2F8"}


def _hit_summary(hit_factors):
    parts = []
    for f in hit_factors:
        arrow = "↑" if f["direction"] == "up" else "↓"
        ref = "(参考)" if f["reference"] else ""
        parts.append(f'{f["field"]}={f["value"]}{arrow}×{f["odds_ratio"]:.1f}{ref}')
    return " / ".join(parts)


def build_rows(scoreable_records, model):
    rows = []
    for r in scoreable_records:
        s = score_record(r, model)
        rows.append({
            "apply_id": r.get("apply_id"), "agent_id": r.get("agent_id"),
            "product": r.get("product"), "channel": r.get("channel"),
            "risk": s["risk"], "risk_pct": round(s["risk"] * 100, 1),
            "band": s["band"], "hit_summary": _hit_summary(s["hit_factors"]),
            "action": action_for_band(s["band"]),
        })
    rows.sort(key=lambda x: x["risk"], reverse=True)
    return rows


def render_csv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_HEADERS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def render_html(rows, path):
    th = "".join(f"<th>{h}</th>" for h in _HEADERS)
    trs = []
    for r in rows:
        color = _BAND_COLOR.get(r["band"], "#fff")
        tds = "".join(f"<td>{html.escape(str(r.get(h, '')))}</td>" for h in _HEADERS)
        trs.append(f'<tr style="background:{color}">{tds}</tr>')
    doc = (
        '<!doctype html><meta charset="utf-8">'
        '<title>早期解約リスク一覧</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        '<h1>早期解約リスク一覧（継続中・6ヶ月未満）</h1>'
        f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_report_list -v`
Expected: PASS（3件）

- [ ] **Step 6: コミット**

```bash
git add scripts/churn/actions.py scripts/churn/report_list.py tests/churn/test_report_list.py
git commit -m "feat(churn): 一覧出力（リスク順・帯色・ヒット要因・推奨アクション）"
```

---

### Task 8: CLI（fit / score / backtest を通しで実行）

**Files:**
- Create: `scripts/churn/cli.py`
- Create: `scripts/churn/README.md`
- Create: `tests/churn/test_cli.py`

**Interfaces:**
- Consumes: `intake.load_records`, `intake.load_column_map`, `fit.fit_model`, `fit.save_model`, `fit.load_model`, `report_list.build_rows/render_csv/render_html`, `evaluate.backtest`
- Produces:
  - `cli.cmd_fit(csv_path, column_map_path, model_path, as_of) -> dict`（学習してモデル保存、summaryを返す）
  - `cli.cmd_score(csv_path, column_map_path, model_path, out_prefix, as_of) -> int`（採点して一覧CSV/HTMLを出力、件数を返す）
  - `cli.cmd_backtest(csv_path, column_map_path, split, as_of) -> dict`
  - `cli.main(argv: list[str] | None = None) -> int`（argparse。サブコマンド `fit` `score` `backtest`）

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_cli.py`:

```python
import unittest
import tempfile
import os
import json
from scripts.churn import cli

COLUMN_MAP = {
    "apply_id": "申込ID", "apply_date": "申込日", "product": "商品",
    "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}

# X商品は解約多め、Y商品は継続。末尾に継続中(6ヶ月未満)の採点対象を2件。
def make_csv():
    lines = ["申込ID,申込日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由"]
    for i in range(40):
        lines.append(f"X{i},2025-01-01,X,催事,対面,5000,25,女,那覇,S1,2025-03-01,高い")
        lines.append(f"Y{i},2025-01-01,Y,紹介,オンライン,8000,42,男,浦添,S2,,")
    lines.append("NEW_X,2026-06-01,X,催事,対面,5000,25,女,那覇,S1,,")
    lines.append("NEW_Y,2026-06-01,Y,紹介,オンライン,8000,42,男,浦添,S2,,")
    return "\n".join(lines) + "\n"


class TestCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.csv = os.path.join(self.dir, "data.csv")
        self.cmap = os.path.join(self.dir, "map.json")
        self.model = os.path.join(self.dir, "model.json")
        with open(self.csv, "w", encoding="utf-8") as f:
            f.write(make_csv())
        with open(self.cmap, "w", encoding="utf-8") as f:
            json.dump(COLUMN_MAP, f, ensure_ascii=False)

    def test_fit_then_score_produces_list(self):
        cli.main(["fit", "--csv", self.csv, "--column-map", self.cmap,
                  "--model", self.model, "--as-of", "2026-07-25"])
        self.assertTrue(os.path.exists(self.model))
        prefix = os.path.join(self.dir, "list")
        n = cli.cmd_score(self.csv, self.cmap, self.model, prefix, "2026-07-25")
        self.assertEqual(n, 2)  # 採点対象は NEW_X, NEW_Y
        self.assertTrue(os.path.exists(prefix + ".csv"))
        self.assertTrue(os.path.exists(prefix + ".html"))

    def test_backtest_returns_metrics(self):
        m = cli.cmd_backtest(self.csv, self.cmap, "2025-06-01", "2026-07-25")
        self.assertIn("auc", m)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_cli -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: cli を実装**

`scripts/churn/cli.py`:

```python
"""CLI：fit / score / backtest を通しで実行する。

例（顧客データは private/ 配下で実行する）:
  python -m scripts.churn.cli fit --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json
  python -m scripts.churn.cli score --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --out private/list
  python -m scripts.churn.cli backtest --csv private/data.csv --column-map private/column_map.json --split 2026-01-01
"""
from __future__ import annotations
import argparse
from datetime import date

from .intake import load_records, load_column_map
from .fit import fit_model, save_model, load_model
from .report_list import build_rows, render_csv, render_html
from .evaluate import backtest


def _as_of(value):
    if not value:
        raise SystemExit("--as-of は YYYY-MM-DD で指定してください（PII保護のため既定日は使いません）")
    y, m, d = (int(p) for p in value.split("-"))
    return date(y, m, d)


def cmd_fit(csv_path, column_map_path, model_path, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    model = fit_model(records)
    save_model(model, model_path)
    summary = {"n_resolved": model["n_resolved"], "base_rate": model["base_rate"]}
    print(f"[fit] 学習完了: 成熟実績={summary['n_resolved']}件 ベース解約率={summary['base_rate']:.1%}")
    return summary


def cmd_score(csv_path, column_map_path, model_path, out_prefix, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    scoreable = [r for r in records if r.get("is_scoreable")]
    model = load_model(model_path)
    rows = build_rows(scoreable, model)
    render_csv(rows, out_prefix + ".csv")
    render_html(rows, out_prefix + ".html")
    high = sum(1 for r in rows if r["band"] == "high")
    print(f"[score] 採点対象={len(rows)}件 うち高リスク={high}件 → {out_prefix}.csv / .html")
    return len(rows)


def cmd_backtest(csv_path, column_map_path, split, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    y, m, d = (int(p) for p in split.split("-"))
    metrics = backtest(records, date(y, m, d))
    print(f"[backtest] n_test={metrics['n_test']} AUC={metrics['auc']:.3f} "
          f"pred={metrics['pred_mean']:.1%} actual={metrics['actual_mean']:.1%} "
          f"top10%lift={metrics['top_decile_lift']:.2f}")
    return metrics


def main(argv=None):
    p = argparse.ArgumentParser(prog="churn", description="早期解約リスク保全")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("fit", "score", "backtest"):
        sp = sub.add_parser(name)
        sp.add_argument("--csv", required=True)
        sp.add_argument("--column-map", required=True)
        sp.add_argument("--as-of", required=True)
        if name in ("fit", "score"):
            sp.add_argument("--model", required=True)
        if name == "score":
            sp.add_argument("--out", required=True)
        if name == "backtest":
            sp.add_argument("--split", required=True)

    args = p.parse_args(argv)
    if args.cmd == "fit":
        cmd_fit(args.csv, args.column_map, args.model, args.as_of)
    elif args.cmd == "score":
        cmd_score(args.csv, args.column_map, args.model, args.out, args.as_of)
    elif args.cmd == "backtest":
        cmd_backtest(args.csv, args.column_map, args.split, args.as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 運用READMEを作成**

`scripts/churn/README.md`:

```markdown
# 早期解約リスク保全（churn）

申込〜解約の実績（CSV）から「6ヶ月以内解約リスク%」を出し、高リスク先へ先回り保全をあてる。

## 大原則
- **顧客個人データは `private/`（gitignore）でのみ扱う。絶対にコミットしない。**
- 入力は統一エクセルの1シートをCSVエクスポートしたもの。列名は `column_map.json` で対応づける。

## 手順
1. `docs/churn/column_map.example.json` を `private/column_map.json` にコピーし、実エクセルの列名に合わせる。
2. 学習: `python -m scripts.churn.cli fit --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --as-of 2026-07-25`
3. 妥当性確認（品質ゲート）: `python -m scripts.churn.cli backtest --csv private/data.csv --column-map private/column_map.json --split 2026-01-01 --as-of 2026-07-25` → AUCが0.5付近なら本番に出さない。
4. 採点・一覧出力: `python -m scripts.churn.cli score --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --out private/list --as-of 2026-07-25`

## テスト
`python -m unittest discover -s tests/churn -v`
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_cli -v`
Expected: PASS（2件）

- [ ] **Step 6: 全体テストを流す**

Run: `python -m unittest discover -s tests/churn -v`
Expected: 全モジュールのテストが PASS

- [ ] **Step 7: コミット**

```bash
git add scripts/churn/cli.py scripts/churn/README.md tests/churn/test_cli.py
git commit -m "feat(churn): CLI（fit/score/backtest）と運用README"
```

---

### Task 9: カード出力（申込1件の詳細）

**Files:**
- Create: `scripts/churn/report_card.py`
- Create: `tests/churn/test_report_card.py`
- Modify: `scripts/churn/cli.py`（`card` サブコマンド追加）

**Interfaces:**
- Consumes: `scripts.churn.score.score_record`, `scripts.churn.actions.action_for_band`
- Produces:
  - `report_card.build_card(record: dict, model: dict) -> dict`
    `{"apply_id","risk_pct","band","base_pct","hit_factors":[...],"action","reasons":[str]}`
  - `report_card.render_html(card: dict, path: str) -> None`
  - `cli.cmd_card(csv_path, column_map_path, model_path, apply_id, out_path, as_of) -> dict`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_report_card.py`:

```python
import unittest
import tempfile
import os
from scripts.churn import fit, report_card


def rec(product, early=None, resolved=True, apply_id="A", **ov):
    base = {"apply_id": apply_id, "product": product, "channel": "催事",
            "apply_form": "対面", "amount_band": "3千〜1万", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}
    base.update(ov)
    return base


class TestReportCard(unittest.TestCase):
    def setUp(self):
        recs = [rec("X", 1) for _ in range(40)] + [rec("Y", 0) for _ in range(40)]
        self.model = fit.fit_model(recs)

    def test_build_card_has_reasons(self):
        card = report_card.build_card(rec("X", None, False, "NEW"), self.model)
        self.assertEqual(card["apply_id"], "NEW")
        self.assertEqual(card["band"], "high")
        self.assertTrue(card["reasons"])
        self.assertIn("安心コール", card["action"])

    def test_render_html_contains_id_and_pct(self):
        card = report_card.build_card(rec("X", None, False, "NEW"), self.model)
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            report_card.render_html(card, path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("NEW", content)
            self.assertIn("%", content)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_report_card -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: report_card を実装**

`scripts/churn/report_card.py`:

```python
"""カード出力：申込1件の「%・なぜ高いか・型アクション」。"""
from __future__ import annotations
import html

from .score import score_record
from .actions import action_for_band

_BAND_LABEL = {"high": "🔴 高リスク", "med": "🟡 中リスク", "low": "🟢 低リスク"}


def _reason(f):
    direction = "上げている" if f["direction"] == "up" else "下げている"
    ref = "（件数が少なく参考値）" if f["reference"] else ""
    return f'{f["field"]}={f["value"]} がリスクを{direction}（×{f["odds_ratio"]:.1f}）{ref}'


def build_card(record, model):
    s = score_record(record, model)
    return {
        "apply_id": record.get("apply_id"),
        "risk_pct": round(s["risk"] * 100, 1),
        "band": s["band"],
        "base_pct": round(s["base_rate"] * 100, 1),
        "hit_factors": s["hit_factors"],
        "action": action_for_band(s["band"]),
        "reasons": [_reason(f) for f in s["hit_factors"]],
    }


def render_html(card, path):
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in card["reasons"])
    doc = (
        '<!doctype html><meta charset="utf-8"><title>リスクカード</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:24px;max-width:640px}'
        '.pct{font-size:48px;color:#F88800;font-weight:bold}'
        '.band{font-size:20px;margin:8px 0}.action{background:#EAF2F8;padding:12px;border-radius:8px}</style>'
        f'<h1>申込 {html.escape(str(card["apply_id"]))} のリスク</h1>'
        f'<div class="pct">{card["risk_pct"]}%</div>'
        f'<div class="band">{_BAND_LABEL.get(card["band"], card["band"])}（全体平均 {card["base_pct"]}%）</div>'
        f'<h2>なぜ高い/低いか</h2><ul>{reasons}</ul>'
        f'<h2>推奨アクション</h2><div class="action">{html.escape(card["action"])}</div>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
```

- [ ] **Step 4: cli に card サブコマンドを追加**

`scripts/churn/cli.py` の import 群に追加:

```python
from .report_card import build_card, render_html as render_card_html
```

`cmd_backtest` の下に関数を追加:

```python
def cmd_card(csv_path, column_map_path, model_path, apply_id, out_path, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    target = next((r for r in records if str(r.get("apply_id")) == str(apply_id)), None)
    if target is None:
        raise SystemExit(f"申込ID {apply_id} が見つかりません")
    model = load_model(model_path)
    card = build_card(target, model)
    render_card_html(card, out_path)
    print(f"[card] {apply_id}: {card['risk_pct']}% ({card['band']}) → {out_path}")
    return card
```

`main()` のサブコマンド定義ループの後（`args = p.parse_args(argv)` の前）に追加:

```python
    sp_card = sub.add_parser("card")
    sp_card.add_argument("--csv", required=True)
    sp_card.add_argument("--column-map", required=True)
    sp_card.add_argument("--as-of", required=True)
    sp_card.add_argument("--model", required=True)
    sp_card.add_argument("--apply-id", required=True)
    sp_card.add_argument("--out", required=True)
```

`main()` の分岐に追加（`backtest` 分岐の後）:

```python
    elif args.cmd == "card":
        cmd_card(args.csv, args.column_map, args.model, args.apply_id, args.out, args.as_of)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_report_card tests.churn.test_cli -v`
Expected: PASS（既存CLIテストも含め継続してPASS）

- [ ] **Step 6: コミット**

```bash
git add scripts/churn/report_card.py scripts/churn/cli.py tests/churn/test_report_card.py
git commit -m "feat(churn): カード出力（1件詳細・なぜ高いか・推奨アクション）"
```

---

### Task 10: 集計レポート＋効果測定

**Files:**
- Create: `scripts/churn/report_agg.py`
- Create: `tests/churn/test_report_agg.py`
- Modify: `scripts/churn/cli.py`（`report` サブコマンド追加）

**Interfaces:**
- Consumes: なし（レコードの `is_resolved`/`is_early_churn` を直接集計）
- Produces:
  - `report_agg.aggregate_by(records: list[dict], field: str) -> list[dict]`
    各row: `{"value","n","churn","churn_rate"}`（成熟実績のみ、churn_rate降順）
  - `report_agg.effect_compare(followed: list[dict], not_followed: list[dict]) -> dict`
    `{"followed_rate","not_followed_rate","diff","n_followed","n_not_followed"}`
  - `report_agg.render_html(sections: dict[str, list[dict]], path: str) -> None`
  - `cli.cmd_report(csv_path, column_map_path, out_path, as_of, fields) -> dict`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_report_agg.py`:

```python
import unittest
from scripts.churn import report_agg


def rec(agent, early, resolved=True):
    return {"agent_id": agent, "is_resolved": resolved, "is_early_churn": early}


class TestReportAgg(unittest.TestCase):
    def test_aggregate_by_agent_sorted_by_rate(self):
        recs = [rec("S1", 1), rec("S1", 1), rec("S2", 0), rec("S2", 0),
                rec("S3", None, resolved=False)]  # 未成熟は無視
        rows = report_agg.aggregate_by(recs, "agent_id")
        self.assertEqual(rows[0]["value"], "S1")
        self.assertAlmostEqual(rows[0]["churn_rate"], 1.0)
        self.assertEqual(sum(r["n"] for r in rows), 4)

    def test_effect_compare_diff(self):
        followed = [rec("S1", 0), rec("S1", 0), rec("S1", 1)]      # 1/3
        not_followed = [rec("S2", 1), rec("S2", 1), rec("S2", 0)]  # 2/3
        out = report_agg.effect_compare(followed, not_followed)
        self.assertAlmostEqual(out["followed_rate"], 1 / 3, places=6)
        self.assertAlmostEqual(out["not_followed_rate"], 2 / 3, places=6)
        self.assertAlmostEqual(out["diff"], -1 / 3, places=6)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_report_agg -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: report_agg を実装**

`scripts/churn/report_agg.py`:

```python
"""集計レポート：営業マン別/チャネル別/商品別の解約傾向と、保全の効果測定。"""
from __future__ import annotations
import html


def aggregate_by(records, field):
    resolved = [r for r in records if r.get("is_resolved")]
    buckets = {}
    for r in resolved:
        value = r.get(field, "不明")
        b = buckets.setdefault(value, {"n": 0, "churn": 0})
        b["n"] += 1
        b["churn"] += r["is_early_churn"]
    rows = [{"value": v, "n": b["n"], "churn": b["churn"],
             "churn_rate": b["churn"] / b["n"] if b["n"] else 0.0}
            for v, b in buckets.items()]
    rows.sort(key=lambda x: x["churn_rate"], reverse=True)
    return rows


def effect_compare(followed, not_followed):
    def rate(recs):
        r = [x for x in recs if x.get("is_resolved")]
        return (sum(x["is_early_churn"] for x in r) / len(r)) if r else 0.0
    fr, nr = rate(followed), rate(not_followed)
    return {"followed_rate": fr, "not_followed_rate": nr, "diff": fr - nr,
            "n_followed": len(followed), "n_not_followed": len(not_followed)}


def render_html(sections, path):
    blocks = []
    for title, rows in sections.items():
        trs = "".join(
            f'<tr><td>{html.escape(str(r["value"]))}</td><td>{r["n"]}</td>'
            f'<td>{r["churn"]}</td><td>{r["churn_rate"]*100:.1f}%</td></tr>'
            for r in rows)
        blocks.append(
            f'<h2>{html.escape(title)}</h2>'
            f'<table><thead><tr><th>値</th><th>件数</th><th>早期解約</th><th>解約率</th></tr></thead>'
            f'<tbody>{trs}</tbody></table>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>解約傾向レポート</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;margin-bottom:24px}th,td{border:1px solid #ccc;padding:6px}'
        'th{background:#00335C;color:#fff}</style>'
        '<h1>解約傾向レポート（成熟実績ベース）</h1>' + "".join(blocks)
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
```

- [ ] **Step 4: cli に report サブコマンドを追加**

`scripts/churn/cli.py` の import 群に追加:

```python
from .report_agg import aggregate_by, render_html as render_agg_html
```

`cmd_card` の下に追加:

```python
def cmd_report(csv_path, column_map_path, out_path, as_of, fields=("agent_id", "channel", "product")):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    labels = {"agent_id": "営業マン別", "channel": "チャネル別", "product": "商品別"}
    sections = {labels.get(f, f): aggregate_by(records, f) for f in fields}
    render_agg_html(sections, out_path)
    print(f"[report] 集計軸={list(sections)} → {out_path}")
    return sections
```

`main()` のサブコマンド定義に追加:

```python
    sp_report = sub.add_parser("report")
    sp_report.add_argument("--csv", required=True)
    sp_report.add_argument("--column-map", required=True)
    sp_report.add_argument("--as-of", required=True)
    sp_report.add_argument("--out", required=True)
```

`main()` の分岐に追加:

```python
    elif args.cmd == "report":
        cmd_report(args.csv, args.column_map, args.out, args.as_of)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest discover -s tests/churn -v`
Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add scripts/churn/report_agg.py scripts/churn/cli.py tests/churn/test_report_agg.py
git commit -m "feat(churn): 集計レポート（営業マン/チャネル/商品別）＋効果測定"
```

---

## 実装後の確認（全体）

- [ ] `python -m unittest discover -s tests/churn -v` が全PASS
- [ ] `git status` に `private/` の中身が出ていない（PII非コミットの確認）
- [ ] `scripts/churn/README.md` の手順どおり、合成データ or 実データ（private）で fit → backtest → score が通る
- [ ] バックテストのAUCを確認し、0.5付近（当たっていない）なら本番投入しない旨をREADMEどおり運用

## 次フェーズ（この計画のスコープ外・別計画）
- 掛け合わせ要因（催事×20代×低単価 等）の個別ルール化
- 温度較正のチューニング自動化
- B案（機械学習）への `fit`/`score` 差し替え評価
- 「保全実施」列を実データに追加し、`effect_compare` で高リスク群の実効果を継続測定
