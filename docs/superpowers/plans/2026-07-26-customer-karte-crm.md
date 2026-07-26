# 顧客カルテ(お客様管理)機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 別システムの書き出し(申込み＋接触履歴)を顧客IDで束ね、「申込み履歴＋接触タイムライン＋現在のリスク＋放置検知＋保全効果」を1顧客ずつ見られる顧客カルテを追加する。

**Architecture:** 既存の early-churn-risk パイプライン(`scripts/churn/`、純Python・標準ライブラリ・`private/`限定・read-only)を踏襲し、モジュールを追加する。申込みレコードへ `customer_id` を1項目足し、接触履歴CSVを新規に取り込み、顧客IDで結合して顧客プロファイルを組み立て、カルテHTML・要フォロー一覧・効果測定を出す。入力画面・サーバー・DBは作らない。

**Tech Stack:** Python 3.12・標準ライブラリのみ(`csv` `json` `datetime` `math` `argparse`)。テストは stdlib `unittest`(`python -m unittest`)。追加のpip依存なし。

## Global Constraints

- **Python 3.12 / 標準ライブラリのみ**。pandas・numpy 等は使わない。
- **個人情報は絶対にコミットしない**。入力CSV・顧客個人情報を含むカルテ出力はすべて `private/`(`.gitignore` 除外済み)。コミットはコードとPIIなしの例ファイルのみ。
- **名寄せキー = 既存の顧客ID(`customer_id`)**。推測・ファジー結合はしない。`customer_id` が空の申込みは顧客に束ねない(未紐付として除外)。
- **入力は別システム。本ツールは read-only**(書き出しCSVを取り込むだけ)。入力画面・サーバー・DB・自動同期は作らない。
- 早期解約 = 申込から6ヶ月以内(既存 `EARLY_CHURN_MONTHS = 6`)。
- 表示リスク%は `score.display_pct` で `[0.1, 99.0]` にクランプ(断定しない)。
- CLIは日付を暗黙に「今日」にせず、`--as-of YYYY-MM-DD` を必須にする(既存方針の継承)。

**参照設計書:** `docs/superpowers/specs/2026-07-26-customer-karte-crm-design.md`
**既存インターフェース(そのまま使う):**
- `schema.normalize_record(raw, column_map, as_of) -> dict`(キー: `apply_id, apply_date, product, channel, apply_form, amount, amount_band, age_band, gender, area, agent_id, cancel_date, cancel_reason, is_early_churn, is_resolved, is_scoreable`)
- `intake.load_records(csv_path, column_map, as_of)` / `intake.read_rows(csv_path)` / `intake.load_column_map(path)`
- `score.score_record(record, model) -> {risk, band, base_rate, hit_factors:[{field,value,odds_ratio,direction,n,reference}]}`
- `score.display_pct(risk) -> float`(`[0.1,99.0]`)
- `schema.parse_date(value) -> date|None`
- `fit.load_model(path) -> model`

---

### Task 1: スキーマ拡張(`customer_id`)と接触履歴の定数

**Files:**
- Modify: `scripts/churn/schema.py`(`normalize_record` の戻り値へ `customer_id` を1行追加)
- Modify: `scripts/churn/config.py`(接触履歴・放置検知の定数を追記)
- Modify: `docs/churn/column_map.example.json`(`customer_id` 対応を追加)
- Test: `tests/churn/test_customer_id.py`

**Interfaces:**
- Consumes: 既存 `schema.normalize_record`
- Produces:
  - `normalize_record` の戻り値に `"customer_id"` キー(`column_map["customer_id"]` が指す実列の値、無ければ `None`)
  - `config.FOLLOWUP_DAYS = 14`、`config.ADDITIONAL_GUIDANCE_KINDS = {"追加案内"}`、`config.INTERACTION_KIND_MAP`(表記ゆれ→正規化)

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_customer_id.py`:

```python
import unittest
from datetime import date
from scripts.churn import schema

COLUMN_MAP = {
    "customer_id": "顧客ID", "apply_id": "申込ID", "apply_date": "申込日",
    "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
    "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
    "cancel_date": "解約日", "cancel_reason": "解約理由",
}


def raw(**over):
    base = {"顧客ID": "C1", "申込ID": "A1", "申込日": "2026-01-01", "商品": "X",
            "集客": "催事", "申込形態": "対面", "金額": "5000", "年齢": "25",
            "性別": "女", "地域": "那覇", "営業担当": "S1", "解約日": "", "解約理由": ""}
    base.update(over)
    return base


class TestCustomerId(unittest.TestCase):
    def test_customer_id_extracted(self):
        r = schema.normalize_record(raw(), COLUMN_MAP, date(2026, 3, 1))
        self.assertEqual(r["customer_id"], "C1")

    def test_customer_id_absent_is_none(self):
        cmap = {k: v for k, v in COLUMN_MAP.items() if k != "customer_id"}
        r = schema.normalize_record(raw(), cmap, date(2026, 3, 1))
        self.assertIsNone(r["customer_id"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_customer_id -v`
Expected: FAIL(`KeyError: 'customer_id'`)

- [ ] **Step 3: schema と config を実装**

`scripts/churn/schema.py` の `normalize_record` の `return {` 辞書の先頭に1行追加:

```python
        "customer_id": _get(raw, column_map, "customer_id"),
```

`scripts/churn/config.py` の末尾に追記:

```python
# --- 顧客カルテ(接触履歴・放置検知) ---
# 高リスクで直近この日数、接触が無ければ「要フォロー(放置)」とみなす
FOLLOWUP_DAYS = 14
# 「追加案内 ◯回」に数える接触種別
ADDITIONAL_GUIDANCE_KINDS = {"追加案内"}
# 接触種別の表記ゆれ → 正規化。未知の値は原文を保持する
INTERACTION_KIND_MAP = {
    "架電": "架電", "電話": "架電", "TEL": "架電", "tel": "架電",
    "案内": "案内", "追加案内": "追加案内", "来店": "来店",
    "メール": "メール", "mail": "メール", "面談": "面談",
}
```

- [ ] **Step 4: 例 column_map を更新**

`docs/churn/column_map.example.json` の先頭(既存キー群の中)へ `customer_id` を追加(実列名の例):

```json
  "customer_id": "顧客ID",
```

(既存のJSONの他キーはそのまま。妥当なJSONになるようカンマに注意。)

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_customer_id -v`
Expected: PASS(2件)

- [ ] **Step 6: 既存テストが壊れていないことを確認**

Run: `python -m unittest discover -s tests/churn -v`
Expected: 既存も含め全PASS(`customer_id` 追加は既存consumerに影響しない)

- [ ] **Step 7: コミット**

```bash
git add scripts/churn/schema.py scripts/churn/config.py docs/churn/column_map.example.json tests/churn/test_customer_id.py
git commit -m "feat(karte): 申込みレコードにcustomer_id追加・接触履歴の定数"
```

---

### Task 2: 接触履歴の取込(`interactions.py`)

**Files:**
- Create: `scripts/churn/interactions.py`
- Create: `docs/churn/interaction_column_map.example.json`(PIIなし・コミット可)
- Test: `tests/churn/test_interactions.py`

**Interfaces:**
- Consumes: `schema.parse_date`、`intake.read_rows`、`intake.load_column_map`、`config.INTERACTION_KIND_MAP`
- Produces:
  - `interactions.normalize_kind(raw_kind: str | None) -> str`(`INTERACTION_KIND_MAP` で正規化、未知は原文、空は "その他")
  - `interactions.normalize_interaction(raw: dict, imap: dict) -> dict`(キー: `customer_id, date(date|None), kind, agent, content, memo`)
  - `interactions.load_interactions(csv_path: str, imap: dict) -> list[dict]`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_interactions.py`:

```python
import unittest
import tempfile
import os
from datetime import date
from scripts.churn import interactions

IMAP = {"customer_id": "顧客ID", "date": "接触日", "kind": "種別",
        "agent": "担当", "content": "案内内容", "memo": "メモ"}

CSV = (
    "顧客ID,接触日,種別,担当,案内内容,メモ\n"
    "C1,2026-02-01,電話,東さん,医療保険の見直し,不在\n"
    "C1,2026-03-05,追加案内,東さん,がん保険の提案,前向き\n"
)


class TestInteractions(unittest.TestCase):
    def test_normalize_kind(self):
        self.assertEqual(interactions.normalize_kind("電話"), "架電")
        self.assertEqual(interactions.normalize_kind("謎の種別"), "謎の種別")
        self.assertEqual(interactions.normalize_kind(""), "その他")

    def test_normalize_interaction(self):
        raw = {"顧客ID": "C1", "接触日": "2026-02-01", "種別": "電話",
               "担当": "東さん", "案内内容": "見直し", "メモ": "不在"}
        r = interactions.normalize_interaction(raw, IMAP)
        self.assertEqual(r["customer_id"], "C1")
        self.assertEqual(r["date"], date(2026, 2, 1))
        self.assertEqual(r["kind"], "架電")
        self.assertEqual(r["agent"], "東さん")

    def test_load_interactions(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(CSV)
        try:
            recs = interactions.load_interactions(path, IMAP)
            self.assertEqual(len(recs), 2)
            self.assertEqual(recs[1]["kind"], "追加案内")
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_interactions -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: interactions を実装**

`scripts/churn/interactions.py`:

```python
"""接触履歴の取込：実列 → interaction_column_map → 正規化レコード。"""
from __future__ import annotations

from .schema import parse_date
from .intake import read_rows
from .config import INTERACTION_KIND_MAP


def normalize_kind(raw_kind):
    if raw_kind is None or not str(raw_kind).strip():
        return "その他"
    key = str(raw_kind).strip()
    return INTERACTION_KIND_MAP.get(key, key)


def _get(raw, imap, key):
    col = imap.get(key)
    return raw.get(col) if col is not None else None


def normalize_interaction(raw, imap):
    return {
        "customer_id": _get(raw, imap, "customer_id"),
        "date": parse_date(_get(raw, imap, "date")),
        "kind": normalize_kind(_get(raw, imap, "kind")),
        "agent": (_get(raw, imap, "agent") or "不明"),
        "content": (_get(raw, imap, "content") or ""),
        "memo": (_get(raw, imap, "memo") or ""),
    }


def load_interactions(csv_path, imap):
    return [normalize_interaction(row, imap) for row in read_rows(csv_path)]
```

- [ ] **Step 4: 例 interaction_column_map を作成**

`docs/churn/interaction_column_map.example.json`:

```json
{
  "customer_id": "顧客ID",
  "date": "接触日",
  "kind": "種別",
  "agent": "担当",
  "content": "案内内容",
  "memo": "メモ"
}
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_interactions -v`
Expected: PASS(3件)

- [ ] **Step 6: コミット**

```bash
git add scripts/churn/interactions.py docs/churn/interaction_column_map.example.json tests/churn/test_interactions.py
git commit -m "feat(karte): 接触履歴の取込(種別正規化・interaction_column_map)"
```

---

### Task 3: 顧客の束ね(`customer.py`)

**Files:**
- Create: `scripts/churn/customer.py`
- Test: `tests/churn/test_customer.py`

**Interfaces:**
- Consumes: `score.score_record`、`config.FOLLOWUP_DAYS`、`config.ADDITIONAL_GUIDANCE_KINDS`
- Produces:
  - `customer.highest_band(bands: list[str]) -> str | None`(`high>med>low`、空は None)
  - `customer.build_customers(app_records: list[dict], interaction_records: list[dict], model: dict, as_of: date) -> dict[str, dict]`
    profile キー: `customer_id, age_band, gender, area, n_applications, n_active, n_cancelled, n_early_churn, n_additional_guidance, applications(list), interactions(list, date降順), max_risk_band, last_contact_date, needs_followup`
    各 application は元の申込みレコード＋ `risk`(scoreableなら`score_record`の`risk`、それ以外None)・`band`・`hit_factors` を付与。

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_customer.py`:

```python
import unittest
from datetime import date
from scripts.churn import fit, customer


def app(cid, product, early=None, resolved=True, scoreable=False, apply_id="A", cancel=None):
    return {"customer_id": cid, "apply_id": apply_id, "product": product,
            "channel": "催事", "apply_form": "対面", "amount_band": "3千〜1万",
            "age_band": "20代", "gender": "女", "area": "那覇", "agent_id": "S1",
            "apply_date": date(2026, 1, 1), "cancel_date": cancel, "cancel_reason": "",
            "is_early_churn": early, "is_resolved": resolved, "is_scoreable": scoreable}


def inter(cid, d, kind):
    return {"customer_id": cid, "date": d, "kind": kind, "agent": "東さん",
            "content": "案内", "memo": ""}


def build_model():
    recs = [app("m", "X", 1) for _ in range(30)] + [app("m", "Y", 0) for _ in range(90)]
    return fit.fit_model(recs)


class TestCustomer(unittest.TestCase):
    def test_highest_band(self):
        self.assertEqual(customer.highest_band(["low", "high", "med"]), "high")
        self.assertIsNone(customer.highest_band([]))

    def test_rollup_counts_and_timeline(self):
        model = build_model()
        apps = [app("C1", "X", 1, apply_id="A1", cancel=date(2026, 3, 1)),   # 早期解約
                app("C1", "Y", None, resolved=False, scoreable=True, apply_id="A2")]  # 継続中
        inters = [inter("C1", date(2026, 2, 1), "架電"),
                  inter("C1", date(2026, 3, 5), "追加案内")]
        cs = customer.build_customers(apps, inters, model, date(2026, 4, 1))
        c = cs["C1"]
        self.assertEqual(c["n_applications"], 2)
        self.assertEqual(c["n_early_churn"], 1)
        self.assertEqual(c["n_additional_guidance"], 1)
        self.assertEqual(c["interactions"][0]["date"], date(2026, 3, 5))  # 降順
        self.assertEqual(c["last_contact_date"], date(2026, 3, 5))

    def test_unlinked_records_excluded(self):
        model = build_model()
        apps = [app(None, "X", 1), app("", "Y", 0)]
        cs = customer.build_customers(apps, [], model, date(2026, 4, 1))
        self.assertEqual(cs, {})

    def test_needs_followup_high_risk_no_recent_contact(self):
        model = build_model()
        # 継続中・高リスク(product=X)で、接触が28日以上前 → 要フォロー
        apps = [app("C2", "X", None, resolved=False, scoreable=True)]
        inters = [inter("C2", date(2026, 3, 1), "架電")]
        cs = customer.build_customers(apps, inters, model, date(2026, 4, 1))  # 31日経過
        self.assertTrue(cs["C2"]["needs_followup"])
        self.assertEqual(cs["C2"]["max_risk_band"], "high")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_customer -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: customer を実装**

`scripts/churn/customer.py`:

```python
"""顧客の束ね：申込み＋接触履歴を顧客IDで結合し、プロファイルを作る。"""
from __future__ import annotations

from .score import score_record
from .config import FOLLOWUP_DAYS, ADDITIONAL_GUIDANCE_KINDS

_BAND_RANK = {"low": 0, "med": 1, "high": 2}


def highest_band(bands):
    ranked = [b for b in bands if b in _BAND_RANK]
    if not ranked:
        return None
    return max(ranked, key=lambda b: _BAND_RANK[b])


def _scored_application(app, model):
    out = dict(app)
    if app.get("is_scoreable"):
        s = score_record(app, model)
        out["risk"] = s["risk"]
        out["band"] = s["band"]
        out["hit_factors"] = s["hit_factors"]
    else:
        out["risk"] = None
        out["band"] = None
        out["hit_factors"] = []
    return out


def build_customers(app_records, interaction_records, model, as_of):
    groups = {}
    for app in app_records:
        cid = app.get("customer_id")
        if not cid:  # 未紐付(顧客ID欠損)は束ねない
            continue
        groups.setdefault(cid, {"apps": [], "inters": []})["apps"].append(app)
    for it in interaction_records:
        cid = it.get("customer_id")
        if not cid:
            continue
        groups.setdefault(cid, {"apps": [], "inters": []})["inters"].append(it)

    customers = {}
    for cid, g in groups.items():
        apps = [_scored_application(a, model) for a in g["apps"]]
        inters = sorted(
            [i for i in g["inters"] if i.get("date")],
            key=lambda i: i["date"], reverse=True)
        active = [a for a in apps if a.get("is_scoreable")]
        max_band = highest_band([a["band"] for a in active if a.get("band")])
        last_contact = inters[0]["date"] if inters else None
        needs_followup = (
            max_band == "high"
            and (last_contact is None or (as_of - last_contact).days > FOLLOWUP_DAYS))
        latest_attr = g["apps"][-1] if g["apps"] else {}
        customers[cid] = {
            "customer_id": cid,
            "age_band": latest_attr.get("age_band", "不明"),
            "gender": latest_attr.get("gender", "不明"),
            "area": latest_attr.get("area", "不明"),
            "n_applications": len(apps),
            "n_active": len(active),
            "n_cancelled": sum(1 for a in apps if a.get("cancel_date")),
            "n_early_churn": sum(1 for a in apps if a.get("is_early_churn") == 1),
            "n_additional_guidance": sum(1 for i in g["inters"]
                                         if i.get("kind") in ADDITIONAL_GUIDANCE_KINDS),
            "applications": apps,
            "interactions": inters,
            "max_risk_band": max_band,
            "last_contact_date": last_contact,
            "needs_followup": needs_followup,
        }
    return customers
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_customer -v`
Expected: PASS(4件)

- [ ] **Step 5: コミット**

```bash
git add scripts/churn/customer.py tests/churn/test_customer.py
git commit -m "feat(karte): 顧客の束ね(申込み+接触の結合・集計・放置検知)"
```

---

### Task 4: 顧客カルテHTML(`karte.py`)

**Files:**
- Create: `scripts/churn/karte.py`
- Test: `tests/churn/test_karte.py`

**Interfaces:**
- Consumes: `score.display_pct`、`actions.action_for_band`、顧客プロファイル(Task 3)
- Produces:
  - `karte.render_html(profile: dict, path: str) -> None`(顧客カルテHTMLを書き出す。`html.escape` でXSS安全)

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_karte.py`:

```python
import unittest
import tempfile
import os
from datetime import date
from scripts.churn import karte


def profile():
    return {
        "customer_id": "C1", "age_band": "20代", "gender": "女", "area": "那覇",
        "n_applications": 2, "n_active": 1, "n_cancelled": 1, "n_early_churn": 1,
        "n_additional_guidance": 1, "max_risk_band": "high",
        "last_contact_date": date(2026, 3, 5), "needs_followup": True,
        "applications": [
            {"apply_id": "A2", "product": "医療保険A", "amount": 5000, "channel": "催事",
             "agent_id": "東さん", "apply_date": date(2026, 3, 1), "cancel_date": None,
             "is_early_churn": None, "is_scoreable": True, "risk": 0.999,
             "band": "high", "hit_factors": [
                 {"field": "product", "value": "医療保険A", "odds_ratio": 1.7,
                  "direction": "up", "n": 40, "reference": False}]},
            {"apply_id": "A1", "product": "がん保険B", "amount": 3000, "channel": "SNS",
             "agent_id": "東さん", "apply_date": date(2025, 1, 1),
             "cancel_date": date(2025, 3, 1), "is_early_churn": 1, "is_scoreable": False,
             "risk": None, "band": None, "hit_factors": []},
        ],
        "interactions": [
            {"date": date(2026, 3, 5), "kind": "追加案内", "agent": "東さん",
             "content": "がん保険の提案", "memo": "前向き"},
            {"date": date(2026, 2, 1), "kind": "架電", "agent": "東さん",
             "content": "見直し", "memo": "不在"},
        ],
    }


class TestKarte(unittest.TestCase):
    def test_render_html_contains_key_facts(self):
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            karte.render_html(profile(), path)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            self.assertIn("C1", html)
            self.assertIn("99.0%", html)          # display_pctクランプ(100%を出さない)
            self.assertNotIn("100.0%", html)
            self.assertIn("追加案内", html)         # タイムライン
            self.assertIn("要フォロー", html)        # 放置検知
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_karte -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: karte を実装**

`scripts/churn/karte.py`:

```python
"""顧客カルテHTML：申込み履歴＋接触タイムライン＋現在リスク＋放置検知。"""
from __future__ import annotations
import html

from .score import display_pct
from .actions import action_for_band

_BAND_JP = {"high": "🔴 高", "med": "🟡 中", "low": "🟢 低", None: "—"}


def _e(v):
    return html.escape(str(v if v is not None else ""))


def _status(app):
    if app.get("is_early_churn") == 1:
        return "早期解約"
    if app.get("cancel_date"):
        return "解約"
    return "継続中"


def _app_rows(apps):
    out = []
    for a in apps:
        risk = f"{display_pct(a['risk'])}%" if a.get("risk") is not None else "—"
        out.append(
            f"<tr><td>{_e(a.get('apply_id'))}</td><td>{_e(a.get('product'))}</td>"
            f"<td>{_e(a.get('amount'))}</td><td>{_e(a.get('channel'))}</td>"
            f"<td>{_e(a.get('agent_id'))}</td><td>{_e(a.get('apply_date'))}</td>"
            f"<td>{_e(_status(a))}</td><td>{risk} {_BAND_JP.get(a.get('band'))}</td></tr>")
    return "".join(out)


def _timeline(inters):
    out = []
    for i in inters:
        out.append(
            f"<li><b>{_e(i.get('date'))}</b> <span class='kind'>{_e(i.get('kind'))}</span> "
            f"／ {_e(i.get('agent'))}<br>{_e(i.get('content'))}"
            f"<span class='memo'>{_e(i.get('memo'))}</span></li>")
    return "".join(out) or "<li>接触履歴なし</li>"


def render_html(profile, path):
    p = profile
    followup = ('<div class="followup">⚠️ 要フォロー：高リスクなのに直近の接触がありません</div>'
                if p.get("needs_followup") else "")
    doc = (
        '<!doctype html><meta charset="utf-8"><title>顧客カルテ ' + _e(p["customer_id"]) + '</title>'
        '<style>body{font-family:"Noto Sans JP","Meiryo",sans-serif;padding:20px;max-width:920px;margin:auto;color:#12212e}'
        'h1{font-size:20px}.sum{display:flex;gap:18px;flex-wrap:wrap;margin:12px 0}'
        '.sum div{background:#eef3f8;border-radius:10px;padding:10px 14px;font-size:13px}'
        '.sum b{font-size:20px;display:block}'
        '.followup{background:#fbe9e2;color:#dc4e28;font-weight:700;padding:10px 14px;border-radius:10px;margin:10px 0}'
        'table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}'
        'th,td{border:1px solid #dce4ec;padding:7px 9px;text-align:left}th{background:#00335c;color:#fff}'
        'ul.tl{list-style:none;padding:0}ul.tl li{border-left:3px solid #f88800;padding:6px 12px;margin:6px 0;background:#f7f9fb;font-size:13px}'
        '.kind{background:#00335c;color:#fff;border-radius:4px;padding:1px 7px;font-size:11px}'
        '.memo{color:#5c6e7e;margin-left:8px}h2{font-size:15px;border-bottom:2px solid #dce4ec;padding-bottom:4px;margin-top:24px}</style>'
        f'<h1>顧客カルテ — {_e(p["customer_id"])}</h1>'
        f'<div>{_e(p["age_band"])} ／ {_e(p["gender"])} ／ {_e(p["area"])}</div>'
        f'{followup}'
        '<div class="sum">'
        f'<div>累計申込<b>{p["n_applications"]}回</b></div>'
        f'<div>継続中<b>{p["n_active"]}件</b></div>'
        f'<div>解約<b>{p["n_cancelled"]}件</b></div>'
        f'<div>早期解約<b>{p["n_early_churn"]}件</b></div>'
        f'<div>追加案内<b>{p["n_additional_guidance"]}回</b></div>'
        f'<div>現在の最大リスク<b>{_BAND_JP.get(p["max_risk_band"])}</b></div>'
        '</div>'
        '<h2>申込み履歴</h2>'
        '<table><thead><tr><th>申込ID</th><th>商品</th><th>金額</th><th>集客</th>'
        '<th>担当</th><th>申込日</th><th>状態</th><th>リスク</th></tr></thead>'
        f'<tbody>{_app_rows(p["applications"])}</tbody></table>'
        '<h2>接触タイムライン</h2>'
        f'<ul class="tl">{_timeline(p["interactions"])}</ul>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_karte -v`
Expected: PASS(1件)

- [ ] **Step 5: コミット**

```bash
git add scripts/churn/karte.py tests/churn/test_karte.py
git commit -m "feat(karte): 顧客カルテHTML(申込み履歴・接触タイムライン・放置検知)"
```

---

### Task 5: CLI `karte` サブコマンド＋README

**Files:**
- Modify: `scripts/churn/cli.py`(`karte` サブコマンド追加)
- Modify: `scripts/churn/README.md`(顧客カルテの手順追記)
- Test: `tests/churn/test_cli_karte.py`

**Interfaces:**
- Consumes: `intake.load_records/load_column_map`、`interactions.load_interactions`、`fit.load_model`、`customer.build_customers`、`karte.render_html`、既存 `cli._as_of`
- Produces: `cli.cmd_karte(app_csv, app_map, inter_csv, inter_map, model_path, customer_id, out_path, as_of) -> dict`(対象顧客のprofileを返す)

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_cli_karte.py`:

```python
import unittest
import tempfile
import os
import json
from scripts.churn import cli

AMAP = {"customer_id": "顧客ID", "apply_id": "申込ID", "apply_date": "申込日",
        "product": "商品", "channel": "集客", "apply_form": "申込形態", "amount": "金額",
        "age": "年齢", "gender": "性別", "area": "地域", "agent_id": "営業担当",
        "cancel_date": "解約日", "cancel_reason": "解約理由"}
IMAP = {"customer_id": "顧客ID", "date": "接触日", "kind": "種別",
        "agent": "担当", "content": "案内内容", "memo": "メモ"}


def make_apps():
    lines = ["顧客ID,申込ID,申込日,商品,集客,申込形態,金額,年齢,性別,地域,営業担当,解約日,解約理由"]
    for i in range(30):
        lines.append(f"CM{i},X{i},2025-01-01,X,催事,対面,5000,25,女,那覇,S1,2025-03-01,高い")
        lines.append(f"CN{i},Y{i},2025-01-01,Y,紹介,オンライン,8000,42,男,浦添,S2,,")
    lines.append("C1,NEW1,2026-06-01,X,催事,対面,5000,25,女,那覇,S1,,")   # 継続中
    return "\n".join(lines) + "\n"


class TestCliKarte(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.acsv = os.path.join(self.dir, "apps.csv")
        self.icsv = os.path.join(self.dir, "inter.csv")
        self.amap = os.path.join(self.dir, "amap.json")
        self.imap = os.path.join(self.dir, "imap.json")
        self.model = os.path.join(self.dir, "model.json")
        with open(self.acsv, "w", encoding="utf-8") as f:
            f.write(make_apps())
        with open(self.icsv, "w", encoding="utf-8") as f:
            f.write("顧客ID,接触日,種別,担当,案内内容,メモ\nC1,2026-06-10,架電,東さん,見直し,不在\n")
        json.dump(AMAP, open(self.amap, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(IMAP, open(self.imap, "w", encoding="utf-8"), ensure_ascii=False)

    def test_fit_then_karte(self):
        cli.main(["fit", "--csv", self.acsv, "--column-map", self.amap,
                  "--model", self.model, "--as-of", "2026-07-26"])
        out = os.path.join(self.dir, "karte_C1.html")
        prof = cli.cmd_karte(self.acsv, self.amap, self.icsv, self.imap,
                             self.model, "C1", out, "2026-07-26")
        self.assertEqual(prof["customer_id"], "C1")
        self.assertEqual(prof["n_applications"], 1)
        self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_cli_karte -v`
Expected: FAIL(`AttributeError: module ... has no attribute 'cmd_karte'`)

- [ ] **Step 3: cli に karte を実装**

`scripts/churn/cli.py` の import 群に追加:

```python
from .interactions import load_interactions
from .customer import build_customers
from .karte import render_html as render_karte_html
```

`cmd_report`(または最後の cmd_ 関数)の下に追加:

```python
def cmd_karte(app_csv, app_map, inter_csv, inter_map, model_path, customer_id, out_path, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    model = load_model(model_path)
    customers = build_customers(apps, inters, model, as_of_d)
    prof = customers.get(str(customer_id))
    if prof is None:
        raise SystemExit(f"顧客ID {customer_id} が見つかりません")
    render_karte_html(prof, out_path)
    print(f"[karte] {customer_id}: 累計申込{prof['n_applications']}回 "
          f"最大リスク{prof['max_risk_band']} → {out_path}")
    return prof
```

`main()` のサブコマンド定義に追加(既存の `report` サブパーサ定義の近く):

```python
    sp_karte = sub.add_parser("karte")
    sp_karte.add_argument("--csv", required=True)
    sp_karte.add_argument("--column-map", required=True)
    sp_karte.add_argument("--interactions", required=True)
    sp_karte.add_argument("--interaction-map", required=True)
    sp_karte.add_argument("--model", required=True)
    sp_karte.add_argument("--customer-id", required=True)
    sp_karte.add_argument("--out", required=True)
    sp_karte.add_argument("--as-of", required=True)
```

`main()` の分岐に追加:

```python
    elif args.cmd == "karte":
        cmd_karte(args.csv, args.column_map, args.interactions, args.interaction_map,
                  args.model, args.customer_id, args.out, args.as_of)
```

- [ ] **Step 4: READMEに手順追記**

`scripts/churn/README.md` の末尾に追記:

```markdown

## 顧客カルテ(お客様管理)
別システムから「申込み台帳」と「接触履歴」をCSVで書き出し、顧客IDで束ねてカルテを出す。
- 接触履歴の列名は `docs/churn/interaction_column_map.example.json` を `private/interaction_map.json` にコピーして合わせる。
- カルテ出力: `python -m scripts.churn.cli karte --csv private/apps.csv --column-map private/column_map.json --interactions private/inter.csv --interaction-map private/interaction_map.json --model private/risk_model.json --customer-id C1 --out private/karte_C1.html --as-of 2026-07-26`
- カルテは顧客個人情報を含むため `private/` に出力し、コミットしない。
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_cli_karte -v`
Expected: PASS(1件)

- [ ] **Step 6: 全体テストを流す**

Run: `python -m unittest discover -s tests/churn -v`
Expected: 全PASS

- [ ] **Step 7: コミット**

```bash
git add scripts/churn/cli.py scripts/churn/README.md tests/churn/test_cli_karte.py
git commit -m "feat(karte): CLI karteサブコマンドと運用手順"
```

---

### Task 6: 要フォロー一覧(放置検知の出力)

**Files:**
- Create: `scripts/churn/followups.py`
- Modify: `scripts/churn/cli.py`(`followups` サブコマンド追加)
- Test: `tests/churn/test_followups.py`

**Interfaces:**
- Consumes: 顧客プロファイル辞書(Task 3 の `build_customers` 出力)
- Produces:
  - `followups.list_followups(customers: dict) -> list[dict]`(`needs_followup` が真の顧客を、最終接触が古い順に)
  - `followups.render_html(rows: list[dict], path: str) -> None`
  - `cli.cmd_followups(app_csv, app_map, inter_csv, inter_map, model_path, out_path, as_of) -> int`(件数を返す)

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_followups.py`:

```python
import unittest
import tempfile
import os
from datetime import date
from scripts.churn import followups


def cust(cid, needs, last):
    return {"customer_id": cid, "needs_followup": needs, "last_contact_date": last,
            "max_risk_band": "high", "n_active": 1, "age_band": "20代",
            "area": "那覇", "n_applications": 1}


class TestFollowups(unittest.TestCase):
    def test_list_only_needs_followup_sorted_oldest_first(self):
        customers = {
            "A": cust("A", True, date(2026, 3, 1)),
            "B": cust("B", False, date(2026, 3, 20)),
            "C": cust("C", True, None),   # 接触なし → 最優先
        }
        rows = followups.list_followups(customers)
        self.assertEqual([r["customer_id"] for r in rows], ["C", "A"])

    def test_render_html(self):
        rows = followups.list_followups({"A": cust("A", True, date(2026, 3, 1))})
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            followups.render_html(rows, path)
            with open(path, encoding="utf-8") as f:
                self.assertIn("A", f.read())
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_followups -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: followups を実装**

`scripts/churn/followups.py`:

```python
"""要フォロー一覧：高リスク×直近接触なし(放置)の顧客を洗い出す。"""
from __future__ import annotations
import html
from datetime import date

_MIN = date(1, 1, 1)


def list_followups(customers):
    rows = [c for c in customers.values() if c.get("needs_followup")]
    # 最終接触が古い順(未接触=最優先)
    rows.sort(key=lambda c: c.get("last_contact_date") or _MIN)
    return rows


def render_html(rows, path):
    trs = []
    for c in rows:
        last = c.get("last_contact_date") or "接触なし"
        trs.append(
            f"<tr><td>{html.escape(str(c.get('customer_id')))}</td>"
            f"<td>{html.escape(str(c.get('age_band')))} / {html.escape(str(c.get('area')))}</td>"
            f"<td>{c.get('n_active')}</td><td>{html.escape(str(last))}</td></tr>")
    doc = (
        '<!doctype html><meta charset="utf-8"><title>要フォロー一覧</title>'
        '<style>body{font-family:"Noto Sans JP","Meiryo",sans-serif;padding:20px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #dce4ec;padding:8px}'
        'th{background:#dc4e28;color:#fff}h1{font-size:18px}</style>'
        '<h1>⚠️ 要フォロー(高リスク×直近接触なし)</h1>'
        '<table><thead><tr><th>顧客ID</th><th>属性</th><th>継続中</th><th>最終接触</th></tr></thead>'
        f'<tbody>{"".join(trs) or "<tr><td colspan=4>該当なし</td></tr>"}</tbody></table>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
```

- [ ] **Step 4: cli に followups を追加**

`scripts/churn/cli.py` の import 群に追加:

```python
from .followups import list_followups, render_html as render_followups_html
```

`cmd_karte` の下に追加:

```python
def cmd_followups(app_csv, app_map, inter_csv, inter_map, model_path, out_path, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    model = load_model(model_path)
    customers = build_customers(apps, inters, model, as_of_d)
    rows = list_followups(customers)
    render_followups_html(rows, out_path)
    print(f"[followups] 要フォロー {len(rows)}件 → {out_path}")
    return len(rows)
```

`main()` のサブコマンド定義に追加:

```python
    sp_fu = sub.add_parser("followups")
    sp_fu.add_argument("--csv", required=True)
    sp_fu.add_argument("--column-map", required=True)
    sp_fu.add_argument("--interactions", required=True)
    sp_fu.add_argument("--interaction-map", required=True)
    sp_fu.add_argument("--model", required=True)
    sp_fu.add_argument("--out", required=True)
    sp_fu.add_argument("--as-of", required=True)
```

`main()` の分岐に追加:

```python
    elif args.cmd == "followups":
        cmd_followups(args.csv, args.column_map, args.interactions, args.interaction_map,
                      args.model, args.out, args.as_of)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_followups tests.churn.test_cli_karte -v`
Expected: PASS

- [ ] **Step 6: コミット**

```bash
git add scripts/churn/followups.py scripts/churn/cli.py tests/churn/test_followups.py
git commit -m "feat(karte): 要フォロー一覧(放置検知の出力)"
```

---

### Task 7: 保全の効果測定(接触あり/なしで実解約率を比較)

**Files:**
- Create: `scripts/churn/karte_effect.py`
- Modify: `scripts/churn/cli.py`(`karte-effect` サブコマンド追加)
- Test: `tests/churn/test_karte_effect.py`

**Interfaces:**
- Consumes: 正規化申込みレコード(`schema.normalize_record` 出力)、正規化接触レコード(Task 2)
- Produces:
  - `karte_effect.was_contacted(customer_id, apply_date, interactions_by_cid, kinds, within_days) -> bool`(申込日から `within_days` 日以内に対象種別の接触があったか)
  - `karte_effect.contact_effect(app_records, interaction_records, kinds=("架電","案内","追加案内"), within_days=90) -> dict`
    返り値: `{contacted_rate, not_contacted_rate, diff, n_contacted, n_not_contacted}`(成熟実績のみ・顧客ID有りのみ)

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_karte_effect.py`:

```python
import unittest
from datetime import date
from scripts.churn import karte_effect


def app(cid, early, apply_d=date(2025, 1, 1)):
    return {"customer_id": cid, "apply_date": apply_d, "is_resolved": True,
            "is_early_churn": early}


def inter(cid, d, kind="架電"):
    return {"customer_id": cid, "date": d, "kind": kind}


class TestKarteEffect(unittest.TestCase):
    def test_was_contacted_window(self):
        by_cid = {"C1": [inter("C1", date(2025, 2, 1))]}
        self.assertTrue(karte_effect.was_contacted(
            "C1", date(2025, 1, 1), by_cid, ("架電",), 90))
        self.assertFalse(karte_effect.was_contacted(
            "C2", date(2025, 1, 1), by_cid, ("架電",), 90))

    def test_contact_effect_diff(self):
        apps = [app("C1", 0), app("C2", 0), app("C3", 1), app("C4", 1)]
        # C1,C2 に保全接触あり(解約せず) / C3,C4 は接触なし(解約)
        inters = [inter("C1", date(2025, 2, 1)), inter("C2", date(2025, 2, 1))]
        out = karte_effect.contact_effect(apps, inters, kinds=("架電",), within_days=90)
        self.assertEqual(out["n_contacted"], 2)
        self.assertEqual(out["n_not_contacted"], 2)
        self.assertAlmostEqual(out["contacted_rate"], 0.0)
        self.assertAlmostEqual(out["not_contacted_rate"], 1.0)
        self.assertAlmostEqual(out["diff"], -1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_karte_effect -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: karte_effect を実装**

`scripts/churn/karte_effect.py`:

```python
"""保全の効果測定：申込後に保全接触があった群/なかった群で実早期解約率を比較。"""
from __future__ import annotations


def was_contacted(customer_id, apply_date, interactions_by_cid, kinds, within_days):
    if apply_date is None:
        return False
    for it in interactions_by_cid.get(customer_id, []):
        d = it.get("date")
        if d is None or it.get("kind") not in kinds:
            continue
        delta = (d - apply_date).days
        if 0 <= delta <= within_days:
            return True
    return False


def contact_effect(app_records, interaction_records, kinds=("架電", "案内", "追加案内"),
                   within_days=90):
    by_cid = {}
    for it in interaction_records:
        cid = it.get("customer_id")
        if cid:
            by_cid.setdefault(cid, []).append(it)

    contacted, not_contacted = [], []
    for a in app_records:
        cid = a.get("customer_id")
        if not cid or not a.get("is_resolved"):
            continue
        if was_contacted(cid, a.get("apply_date"), by_cid, kinds, within_days):
            contacted.append(a)
        else:
            not_contacted.append(a)

    def rate(group):
        return (sum(x["is_early_churn"] for x in group) / len(group)) if group else 0.0

    cr, nr = rate(contacted), rate(not_contacted)
    return {"contacted_rate": cr, "not_contacted_rate": nr, "diff": cr - nr,
            "n_contacted": len(contacted), "n_not_contacted": len(not_contacted)}
```

- [ ] **Step 4: cli に karte-effect を追加**

`scripts/churn/cli.py` の import 群に追加:

```python
from .karte_effect import contact_effect
```

`cmd_followups` の下に追加:

```python
def cmd_karte_effect(app_csv, app_map, inter_csv, inter_map, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    m = contact_effect(apps, inters)
    print(f"[karte-effect] 保全接触あり {m['n_contacted']}件 解約率{m['contacted_rate']:.1%} / "
          f"なし {m['n_not_contacted']}件 解約率{m['not_contacted_rate']:.1%} / "
          f"差{m['diff']:+.1%}")
    return m
```

`main()` のサブコマンド定義に追加:

```python
    sp_ke = sub.add_parser("karte-effect")
    sp_ke.add_argument("--csv", required=True)
    sp_ke.add_argument("--column-map", required=True)
    sp_ke.add_argument("--interactions", required=True)
    sp_ke.add_argument("--interaction-map", required=True)
    sp_ke.add_argument("--as-of", required=True)
```

`main()` の分岐に追加:

```python
    elif args.cmd == "karte-effect":
        cmd_karte_effect(args.csv, args.column_map, args.interactions,
                         args.interaction_map, args.as_of)
```

- [ ] **Step 5: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_karte_effect -v`
Expected: PASS(2件)

- [ ] **Step 6: 全体テストを流す**

Run: `python -m unittest discover -s tests/churn -v`
Expected: 全PASS(既存 + 顧客カルテの全モジュール)

- [ ] **Step 7: コミット**

```bash
git add scripts/churn/karte_effect.py scripts/churn/cli.py tests/churn/test_karte_effect.py
git commit -m "feat(karte): 保全の効果測定(接触あり/なしで実解約率を比較)"
```

---

## 実装後の確認(全体)

- [ ] `python -m unittest discover -s tests/churn -v` が全PASS
- [ ] `git status` に `private/` の中身が出ていない(PII非コミット)
- [ ] 合成データで `fit → karte → followups → karte-effect` が通る
- [ ] カルテHTMLに 100.0%/0.0% が出ない(display_pctクランプ)

## 次フェーズ(この計画のスコープ外)
- ダッシュボード一覧(`report_list`)から顧客カルテHTMLへのリンク(顧客IDとカルテ出力パスの受け渡し)
- 顧客インデックス(全顧客の検索・一覧)
- 別システム書き出しの取込自動化(cron)
