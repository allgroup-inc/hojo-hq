# ダッシュボード連携(顧客インデックス＋カルテリンク) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全顧客のカルテ・要フォロー・顧客インデックスを1コマンドで `private/console/` に生成し、リスク一覧の各行から該当顧客のカルテへ飛べるようにして、ローカルで回遊できる運用コンソールにする。

**Architecture:** 既存 `scripts/churn/` の read-only・純Python・`private/`限定を崩さず、`console.py`(顧客インデックス生成＋一括出力)を追加し、`report_list` に顧客カルテへのリンク列を足す。カルテ本体は既存 `karte.render_html`、要フォローは既存 `followups` を再利用する。

**Tech Stack:** Python 3.12・標準ライブラリのみ(`os` `re` `html`)。テストは stdlib `unittest`。追加のpip依存なし。

## Global Constraints

- **Python 3.12 / 標準ライブラリのみ**。
- **個人情報は絶対にコミットしない**。生成物(index/karte/followups HTML)はすべて `private/`(gitignore済)。コミットはコードのみ。
- HTML出力は **XSS安全**(`html.escape`)。カルテのファイル名は **customer_id をサニタイズ**(パス・トラバーサル防止:英数と `_ -` 以外を `_` に)。
- read-only(別システムの書き出しを読むだけ)。入力画面・サーバー・DBは作らない。
- 参照設計: `docs/superpowers/specs/2026-07-26-customer-karte-crm-design.md`(§5「次フェーズ:ダッシュボード一覧→顧客カルテへのリンク」)。

**既存インターフェース(そのまま使う):**
- `customer.build_customers(app_records, interaction_records, model, as_of) -> dict[str, profile]` / `customer.unlinked_counts(app_records, interaction_records) -> {"apps":int,"interactions":int}`
- `karte.render_html(profile, path)`
- `followups.list_followups(customers) -> list` / `followups.render_html(rows, path)`
- `report_list.build_rows(scoreable_records, model)` / `report_list.render_html(rows, path)` / `report_list._HEADERS`
- `cli`: `load_records`, `load_column_map`, `load_model`, `load_interactions`, `build_customers`, `_as_of`, `_print_unlinked` はロード済み

---

### Task 1: `console.py` — カルテのファイル名と顧客インデックス

**Files:**
- Create: `scripts/churn/console.py`
- Test: `tests/churn/test_console.py`

**Interfaces:**
- Consumes: 顧客プロファイル辞書(`customer.build_customers` の出力)
- Produces:
  - `console.karte_filename(customer_id) -> str`(`karte_<sanitized>.html`。英数・`_`・`-` 以外は `_`)
  - `console.build_index_rows(customers: dict) -> list[dict]`(各row: `customer_id, attr, n_applications, n_active, n_additional_guidance, max_risk_band, last_contact_date, needs_followup, karte_file`。要フォロー→リスク高→顧客IDの順にソート)
  - `console.render_index_html(rows: list[dict], path: str) -> None`(XSS安全。customer_id を `karte_file` へのリンクにする)

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_console.py`:

```python
import unittest
import tempfile
import os
from datetime import date
from scripts.churn import console


def prof(cid, band, apps=1, active=1, addl=0, last=None, followup=False):
    return {"customer_id": cid, "age_band": "20代", "gender": "女", "area": "那覇",
            "n_applications": apps, "n_active": active, "n_cancelled": 0,
            "n_early_churn": 0, "n_additional_guidance": addl, "applications": [],
            "interactions": [], "max_risk_band": band, "last_contact_date": last,
            "needs_followup": followup}


class TestConsole(unittest.TestCase):
    def test_karte_filename_sanitized(self):
        self.assertEqual(console.karte_filename("C-100"), "karte_C-100.html")
        self.assertEqual(console.karte_filename("a/b 学"), "karte_a_b__.html")

    def test_index_rows_sorted_followup_then_risk(self):
        customers = {
            "L": prof("L", "low"),
            "H": prof("H", "high"),
            "F": prof("F", "high", followup=True),
        }
        rows = console.build_index_rows(customers)
        self.assertEqual([r["customer_id"] for r in rows], ["F", "H", "L"])
        self.assertEqual(rows[0]["karte_file"], "karte_F.html")

    def test_render_index_links_to_karte(self):
        rows = console.build_index_rows({"C1": prof("C1", "high")})
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            console.render_index_html(rows, path)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            self.assertIn("C1", html)
            self.assertIn('href="karte_C1.html"', html)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_console -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: console を実装**

`scripts/churn/console.py`:

```python
"""運用コンソール生成：顧客インデックス＋各カルテ＋要フォローを private/ に出す。"""
from __future__ import annotations
import html
import re

_BAND_RANK = {"high": 2, "med": 1, "low": 0}
_BAND_JP = {"high": "🔴 高", "med": "🟡 中", "low": "🟢 低", None: "—"}


def karte_filename(customer_id):
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", str(customer_id))
    return f"karte_{safe}.html"


def build_index_rows(customers):
    rows = []
    for c in customers.values():
        rows.append({
            "customer_id": c["customer_id"],
            "attr": f'{c.get("age_band","不明")} / {c.get("gender","不明")} / {c.get("area","不明")}',
            "n_applications": c.get("n_applications", 0),
            "n_active": c.get("n_active", 0),
            "n_additional_guidance": c.get("n_additional_guidance", 0),
            "max_risk_band": c.get("max_risk_band"),
            "last_contact_date": c.get("last_contact_date"),
            "needs_followup": bool(c.get("needs_followup")),
            "karte_file": karte_filename(c["customer_id"]),
        })
    rows.sort(key=lambda r: (
        not r["needs_followup"],
        -_BAND_RANK.get(r["max_risk_band"], -1),
        str(r["customer_id"]),
    ))
    return rows


def render_index_html(rows, path):
    trs = []
    for r in rows:
        fu = '<span class="fu">要フォロー</span>' if r["needs_followup"] else ""
        last = r["last_contact_date"] or "接触なし"
        trs.append(
            f'<tr><td><a href="{html.escape(r["karte_file"])}">{html.escape(str(r["customer_id"]))}</a> {fu}</td>'
            f'<td>{html.escape(str(r["attr"]))}</td><td>{r["n_applications"]}</td>'
            f'<td>{r["n_active"]}</td><td>{r["n_additional_guidance"]}</td>'
            f'<td>{_BAND_JP.get(r["max_risk_band"])}</td><td>{html.escape(str(last))}</td></tr>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>顧客インデックス</title>'
        '<style>body{font-family:"Noto Sans JP","Meiryo",sans-serif;padding:20px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #dce4ec;padding:8px;font-size:13px}'
        'th{background:#00335c;color:#fff}a{color:#0a4a7a;font-weight:700}'
        '.fu{background:#fbe9e2;color:#dc4e28;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:700}'
        'h1{font-size:18px}</style>'
        '<h1>顧客インデックス(顧客IDで名寄せ)</h1>'
        '<table><thead><tr><th>顧客ID</th><th>属性</th><th>累計申込</th><th>継続中</th>'
        '<th>追加案内</th><th>最大リスク</th><th>最終接触</th></tr></thead>'
        f'<tbody>{"".join(trs) or "<tr><td colspan=7>顧客なし</td></tr>"}</tbody></table>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_console -v`
Expected: PASS(3件)

- [ ] **Step 5: コミット**

```bash
git add scripts/churn/console.py tests/churn/test_console.py
git commit -m "feat(console): カルテファイル名と顧客インデックス生成"
```

---

### Task 2: `console.generate` ＋ CLI `console` サブコマンド

**Files:**
- Modify: `scripts/churn/console.py`(`generate` を追加)
- Modify: `scripts/churn/cli.py`(`console` サブコマンド追加)
- Modify: `scripts/churn/README.md`(コンソール生成の手順追記)
- Test: `tests/churn/test_console_cli.py`

**Interfaces:**
- Consumes: `console.build_index_rows`/`render_index_html`/`karte_filename`(Task 1)、`karte.render_html`、`followups.list_followups`/`followups.render_html`
- Produces:
  - `console.generate(customers: dict, out_dir: str) -> dict`(`out_dir` に `index.html`＋各 `karte_<id>.html`＋`followups.html` を書き出し、`{"index":path, "n_kartes":int, "followups":path}` を返す)
  - `cli.cmd_console(app_csv, app_map, inter_csv, inter_map, model_path, out_dir, as_of) -> dict`

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_console_cli.py`:

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
        lines.append(f"M{i},X{i},2025-01-01,X,催事,対面,5000,25,女,那覇,S1,2025-03-01,高い")
        lines.append(f"N{i},Y{i},2025-01-01,Y,紹介,オンライン,8000,42,男,浦添,S2,,")
    lines.append("C1,NEW1,2026-06-01,X,催事,対面,5000,25,女,那覇,S1,,")
    return "\n".join(lines) + "\n"


class TestConsoleCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.acsv = os.path.join(self.dir, "apps.csv")
        self.icsv = os.path.join(self.dir, "inter.csv")
        self.amap = os.path.join(self.dir, "amap.json")
        self.imap = os.path.join(self.dir, "imap.json")
        self.model = os.path.join(self.dir, "model.json")
        self.out = os.path.join(self.dir, "console")
        with open(self.acsv, "w", encoding="utf-8") as f:
            f.write(make_apps())
        with open(self.icsv, "w", encoding="utf-8") as f:
            f.write("顧客ID,接触日,種別,担当,案内内容,メモ\nC1,2026-06-10,架電,東さん,見直し,不在\n")
        json.dump(AMAP, open(self.amap, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(IMAP, open(self.imap, "w", encoding="utf-8"), ensure_ascii=False)

    def test_console_generates_index_and_kartes(self):
        cli.main(["fit", "--csv", self.acsv, "--column-map", self.amap,
                  "--model", self.model, "--as-of", "2026-07-26"])
        res = cli.cmd_console(self.acsv, self.amap, self.icsv, self.imap,
                              self.model, self.out, "2026-07-26")
        self.assertTrue(os.path.exists(os.path.join(self.out, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(self.out, "followups.html")))
        self.assertTrue(os.path.exists(os.path.join(self.out, "karte_C1.html")))
        self.assertGreaterEqual(res["n_kartes"], 1)
        with open(os.path.join(self.out, "index.html"), encoding="utf-8") as f:
            self.assertIn('href="karte_C1.html"', f.read())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_console_cli -v`
Expected: FAIL(`AttributeError: ... 'cmd_console'`)

- [ ] **Step 3: `console.generate` を実装**

`scripts/churn/console.py` の import 群に追加:

```python
import os

from .karte import render_html as render_karte_html
from .followups import list_followups, render_html as render_followups_html
```

ファイル末尾に追加:

```python
def generate(customers, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for c in customers.values():
        render_karte_html(c, os.path.join(out_dir, karte_filename(c["customer_id"])))
        n += 1
    index_path = os.path.join(out_dir, "index.html")
    render_index_html(build_index_rows(customers), index_path)
    fu_path = os.path.join(out_dir, "followups.html")
    render_followups_html(list_followups(customers), fu_path)
    return {"index": index_path, "n_kartes": n, "followups": fu_path}
```

- [ ] **Step 4: cli に console を追加**

`scripts/churn/cli.py` の import 群に追加:

```python
from .console import generate as generate_console
```

`cmd_karte_effect`(または最後の cmd_ 関数)の下に追加:

```python
def cmd_console(app_csv, app_map, inter_csv, inter_map, model_path, out_dir, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    _print_unlinked(apps, inters)
    model = load_model(model_path)
    customers = build_customers(apps, inters, model, as_of_d)
    res = generate_console(customers, out_dir)
    print(f"[console] 顧客{res['n_kartes']}件のカルテ＋index＋followups → {out_dir}/")
    return res
```

`main()` のサブコマンド定義に追加:

```python
    sp_console = sub.add_parser("console")
    sp_console.add_argument("--csv", required=True)
    sp_console.add_argument("--column-map", required=True)
    sp_console.add_argument("--interactions", required=True)
    sp_console.add_argument("--interaction-map", required=True)
    sp_console.add_argument("--model", required=True)
    sp_console.add_argument("--out-dir", required=True)
    sp_console.add_argument("--as-of", required=True)
```

`main()` の分岐に追加:

```python
    elif args.cmd == "console":
        cmd_console(args.csv, args.column_map, args.interactions, args.interaction_map,
                    args.model, args.out_dir, args.as_of)
```

- [ ] **Step 5: READMEに追記**

`scripts/churn/README.md` の末尾に追記:

```markdown

## 運用コンソール(一括生成)
全顧客のカルテ＋顧客インデックス＋要フォローを1コマンドで `private/console/` に出す。
`python -m scripts.churn.cli console --csv private/apps.csv --column-map private/column_map.json --interactions private/inter.csv --interaction-map private/interaction_map.json --model private/risk_model.json --out-dir private/console --as-of 2026-07-26`
生成物は顧客個人情報を含むため `private/` 限定・コミットしない。`private/console/index.html` を開いて回遊する。
```

- [ ] **Step 6: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_console_cli -v`
Expected: PASS(1件)

- [ ] **Step 7: 全体テストを流す**

Run: `python -m unittest discover -s tests/churn -v`
Expected: 全PASS

- [ ] **Step 8: コミット**

```bash
git add scripts/churn/console.py scripts/churn/cli.py scripts/churn/README.md tests/churn/test_console_cli.py
git commit -m "feat(console): 一括生成コマンドconsoleと運用手順"
```

---

### Task 3: リスク一覧に顧客カルテへのリンク列を足す

**Files:**
- Modify: `scripts/churn/report_list.py`
- Test: `tests/churn/test_report_list_link.py`

**Interfaces:**
- Consumes: `console.karte_filename`(Task 1)
- Produces: `report_list.build_rows` の各row に `customer_id` と `karte_link` を追加。`render_html` は customer_id セルを、customer_id があれば `karte_link` へのリンクにする。CSVには `customer_id` 列(プレーン)を含める。

- [ ] **Step 1: 失敗するテストを書く**

`tests/churn/test_report_list_link.py`:

```python
import unittest
import tempfile
import os
from scripts.churn import fit, report_list


def rec(product, early=None, resolved=True, apply_id="A", cid="C1"):
    return {"customer_id": cid, "apply_id": apply_id, "product": product,
            "channel": "催事", "apply_form": "f", "amount_band": "a", "age_band": "20代",
            "gender": "女", "area": "那覇", "agent_id": "S1",
            "is_resolved": resolved, "is_early_churn": early}


def build_model():
    recs = [rec("X", 1) for _ in range(30)] + [rec("Y", 0) for _ in range(90)]
    return fit.fit_model(recs)


class TestReportListLink(unittest.TestCase):
    def test_rows_carry_customer_id_and_link(self):
        model = build_model()
        rows = report_list.build_rows([rec("X", None, False, "NEW", "C-7")], model)
        self.assertEqual(rows[0]["customer_id"], "C-7")
        self.assertEqual(rows[0]["karte_link"], "karte_C-7.html")

    def test_html_links_customer_to_karte(self):
        model = build_model()
        rows = report_list.build_rows([rec("X", None, False, "NEW", "C-7")], model)
        fd, path = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        try:
            report_list.render_html(rows, path)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            self.assertIn('href="karte_C-7.html"', html)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `python -m unittest tests.churn.test_report_list_link -v`
Expected: FAIL(`KeyError: 'customer_id'`)

- [ ] **Step 3: report_list を実装(変更)**

`scripts/churn/report_list.py` の import 群に追加:

```python
from .console import karte_filename
```

`_HEADERS` を変更(`customer_id` を先頭に追加):

```python
_HEADERS = ["customer_id", "apply_id", "agent_id", "product", "channel", "risk_pct", "band", "hit_summary", "action"]
```

`build_rows` の row 辞書に2キーを追加(既存キーは残す):

```python
            "customer_id": r.get("customer_id") or "",
            "karte_link": karte_filename(r.get("customer_id")) if r.get("customer_id") else "",
```

`render_html` の行セル生成で、`customer_id` 列だけリンクにする。既存の `render_html` のセル生成ループ内で、ヘッダ名が `customer_id` かつ `karte_link` があるときにアンカーを出す。具体的には、セルを組み立てている箇所を次のように分岐させる(他の列は従来どおり `html.escape`):

```python
    for r in rows:
        color = _BAND_COLOR.get(r["band"], "#fff")
        cells = []
        for h in _HEADERS:
            val = html.escape(str(r.get(h, "")))
            if h == "customer_id" and r.get("karte_link"):
                val = f'<a href="{html.escape(r["karte_link"])}">{val}</a>'
            cells.append(f"<td>{val}</td>")
        trs.append(f'<tr style="background:{color}">{"".join(cells)}</tr>')
```

(既存の `render_html` が別の組み立て方をしている場合も、customer_id セルにだけ `karte_link` へのアンカーを付ける、という同じ結果にすること。CSV出力(`render_csv`)は `customer_id` をプレーン値のまま含める=変更不要。)

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest tests.churn.test_report_list_link -v`
Expected: PASS(2件)

- [ ] **Step 5: 既存の report_list テストが壊れていないか確認**

Run: `python -m unittest tests.churn.test_report_list tests.churn.test_report_list_link -v`
Expected: 全PASS(customer_id 列追加で既存テストが落ちる場合は、既存テストの期待を「新しい列を含む」よう最小修正)

- [ ] **Step 6: 全体テストを流す**

Run: `python -m unittest discover -s tests/churn -v`
Expected: 全PASS

- [ ] **Step 7: コミット**

```bash
git add scripts/churn/report_list.py tests/churn/test_report_list_link.py
git commit -m "feat(console): リスク一覧→顧客カルテのリンク列"
```

---

## 実装後の確認(全体)
- [ ] `python -m unittest discover -s tests/churn -v` が全PASS
- [ ] `git status` に `private/` の中身が出ていない(PII非コミット)
- [ ] 合成データで `fit → console --out-dir private/console` を実行し、`index.html` から各カルテ・要フォローへリンクで回遊できる
- [ ] リスク一覧HTMLの顧客ID列から該当カルテへ飛べる

## 次フェーズ(この計画のスコープ外)
- 顧客インデックスの検索/絞り込み(現状は静的テーブル)
- カルテからの「保全実施」入力(別システム側の役割)
