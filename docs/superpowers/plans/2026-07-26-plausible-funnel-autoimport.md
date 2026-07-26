# Plausible ファネル自動取り込み Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub Actions が Plausible Stats API からイベント件数を取得し `data/fukugiiro/funnel.json` を生成、週次レポートが離脱段を自動集計・表示できるようにする。

**Architecture:** 純粋関数 `build_funnel(counts)` に集計ロジックを閉じ込め golden fixture で eval。ネットワーク取得は薄い `fetch_counts()`。週次レポは funnel.json があれば自動描画、無ければ現行の手動フォールバック。キー未設定でも全経路が無害に動く。

**Tech Stack:** Python 3.12 標準ライブラリのみ(urllib/json/os/sys/datetime)。GitHub Actions。追加依存なし。

## Global Constraints

- Python は**標準ライブラリのみ**(`urllib.request`/`json`/`os`/`sys`/`datetime`)。新規 pip 依存を足さない。
- `PLAUSIBLE_API_KEY` が環境変数に無ければ **何も書かず exit 0**(週次レポは手動フォールバック)。既存挙動を壊さない。
- 取得は**集計イベント件数のみ**。APIキーを**ログ出力しない**・リポジトリに置かない(env/Secret のみ)。
- **ゼロ除算しない**:分母が0の率は `None`。
- 断定的な因果表現をしない(「Q3で落ちている**傾向**」等、観測値として提示)。
- `funnel.json` は週次ワークフロー(bot)がコミット。手でプレースホルダを置かない(未生成=フォールバックが明確)。
- SITE_ID デフォルト `allgroup-inc.github.io`(analytics-config.js と同一)。API ベースは `PLAUSIBLE_API_BASE`(既定 `https://plausible.io`)、期間は `PLAUSIBLE_PERIOD`(既定 `7d`)で上書き可。
- 検証ゲート: `python scripts/fetch_plausible_funnel.py --self-test`。既存CIも壊さない(`validate_fukugiiro.py --self-test` / `check_lp_fukugiiro.py` / `node --test tests/shindan.test.mjs`)。
- 全コミット author `Claude <noreply@anthropic.com>`(コミット前に `git config user.email noreply@anthropic.com && git config user.name Claude`)。
- ブランチ: `claude/okinawa-disposable-income-plan-axxs6v`。push はコントローラが行う(実装者は push しない)。

---

### Task 1: `fetch_plausible_funnel.py`(集計コア + self-test)

**Files:**
- Create: `scripts/fetch_plausible_funnel.py`
- Create: `tests/golden_funnel.json`

**Interfaces:**
- Produces: `build_funnel(counts: dict[str,int]) -> dict` — 返り値キー: `stages`(list of `{key,label,count,cvr_from_prev,drop_rate}`)、`engagement`(dict)、`key_rates`(`{finish_rate,line_cvr,zero_rate}`)、`worst_drop`(`{stage,label,drop_rate}` or None)。率は 0..1 の float か None。
- Produces: `fetch_counts(api_key, site_id, period, api_base) -> dict[str,int]`
- Produces (Task 2 が読む): `data/fukugiiro/funnel.json`(main 実行時)

- [ ] **Step 1: golden fixture を書く**

`tests/golden_funnel.json`:
```json
{
  "_note": "fetch_plausible_funnel.py --self-test 用。build_funnel の集計を検証(方程式4)。率は round(値,4) で比較。",
  "cases": [
    {
      "name": "標準ファネル: 最大離脱は 完了→LINE",
      "counts": {"shindan_start":100,"shindan_step_q2":90,"shindan_step_q3":50,"shindan_step_q4":45,"shindan_step_q5":40,"shindan_complete":35,"line_add_click":12,"shindan_zero":3,"kit_click":8,"seido_done_mark":2,"jukyu_report_click":1},
      "expect": {"worst_drop_stage":"line_add_click","line_cvr":0.3429,"finish_rate":0.38,"zero_rate":0.0789}
    },
    {
      "name": "欠損イベントは0扱い",
      "counts": {"shindan_start":10,"shindan_complete":4},
      "expect": {"worst_drop_stage":"shindan_step_q2","line_cvr":0.0,"finish_rate":0.4,"zero_rate":0.0}
    },
    {
      "name": "開始0はゼロ除算せず None",
      "counts": {},
      "expect": {"worst_drop_stage":null,"line_cvr":null,"finish_rate":null,"zero_rate":null}
    }
  ]
}
```

- [ ] **Step 2: self-test を実行して失敗を確認**

Run: `python scripts/fetch_plausible_funnel.py --self-test`
Expected: FAIL(スクリプト未作成なので `No such file` / ImportError 相当)

- [ ] **Step 3: スクリプトを実装**

`scripts/fetch_plausible_funnel.py`:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ Plausible ファネル自動取り込み(計測レポート設計 第2段階)
Stats API からイベント件数を取得し data/fukugiiro/funnel.json を生成する。
- PLAUSIBLE_API_KEY 未設定なら何も書かず exit 0(週次レポは手動フォールバック)
- 集計値のみ。個人識別子は扱わない。APIキーはログに出さない。
使い方:
  PLAUSIBLE_API_KEY=xxx python scripts/fetch_plausible_funnel.py   # 取得して funnel.json 生成
  python scripts/fetch_plausible_funnel.py --self-test             # build_funnel を golden で検証
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "data", "fukugiiro", "funnel.json")
GOLDEN = os.path.join(BASE, "tests", "golden_funnel.json")

# 線形ファネル(順序が離脱段の計算に使われる)
FUNNEL = [
    ("shindan_start", "診断開始"),
    ("shindan_step_q2", "Q2到達"),
    ("shindan_step_q3", "Q3到達"),
    ("shindan_step_q4", "Q4到達"),
    ("shindan_step_q5", "Q5到達"),
    ("shindan_complete", "診断完了(1件以上)"),
    ("line_add_click", "LINE誘導クリック"),
]
ENGAGEMENT_KEYS = ["kit_click", "seido_done_mark", "jukyu_report_click", "shindan_zero"]


def build_funnel(counts):
    """{event_name: count} から stages/engagement/key_rates/worst_drop を組む(純粋関数)。"""
    def g(k):
        return int(counts.get(k, 0) or 0)

    stages = []
    prev = None
    for key, label in FUNNEL:
        c = g(key)
        if prev is None or prev <= 0:
            cvr = None
            drop = None
        else:
            cvr = c / prev
            drop = 1 - cvr
        stages.append({"key": key, "label": label, "count": c,
                       "cvr_from_prev": cvr, "drop_rate": drop})
        prev = c

    start = g("shindan_start")
    complete = g("shindan_complete")
    zero = g("shindan_zero")
    line = g("line_add_click")
    finished = complete + zero
    key_rates = {
        "finish_rate": (finished / start) if start > 0 else None,
        "line_cvr": (line / complete) if complete > 0 else None,
        "zero_rate": (zero / finished) if finished > 0 else None,
    }

    worst = None
    for i, s in enumerate(stages):
        if s["drop_rate"] is None:
            continue
        if worst is None or s["drop_rate"] > worst["drop_rate"]:
            worst = {"stage": s["key"],
                     "label": stages[i - 1]["label"] + "→" + s["label"],
                     "drop_rate": s["drop_rate"]}

    engagement = {k: g(k) for k in ENGAGEMENT_KEYS}
    return {"stages": stages, "engagement": engagement,
            "key_rates": key_rates, "worst_drop": worst}


def fetch_counts(api_key, site_id, period, api_base):
    """Plausible Stats API(event:name の breakdown)から {event_name: count} を取得。"""
    qs = urllib.parse.urlencode({
        "site_id": site_id, "period": period,
        "property": "event:name", "metrics": "events", "limit": "100",
    })
    url = api_base.rstrip("/") + "/api/v1/stats/breakdown?" + qs
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + api_key})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    counts = {}
    for row in data.get("results", []):
        name = row.get("name")
        if name is not None:
            counts[name] = int(row.get("events", 0) or 0)
    return counts


def _r(x):
    return None if x is None else round(x, 4)


def self_test():
    with open(GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    failed = 0
    for case in golden["cases"]:
        fn = build_funnel(case["counts"])
        exp = case["expect"]
        got_stage = fn["worst_drop"]["stage"] if fn["worst_drop"] else None
        checks = {
            "worst_drop_stage": got_stage,
            "line_cvr": _r(fn["key_rates"]["line_cvr"]),
            "finish_rate": _r(fn["key_rates"]["finish_rate"]),
            "zero_rate": _r(fn["key_rates"]["zero_rate"]),
        }
        for k, want in exp.items():
            if checks.get(k) != want:
                failed += 1
                print(f"[SELFTEST FAIL] {case['name']}: {k} expected {want} got {checks.get(k)}")
    total = len(golden["cases"])
    if failed:
        print(f"自己テスト失敗: {failed} 件")
        return 1
    print(f"自己テスト OK: {total} ケース(集計・離脱段・率が一致)")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    api_key = os.environ.get("PLAUSIBLE_API_KEY")
    if not api_key:
        print("[info] PLAUSIBLE_API_KEY 未設定: ファネル取得をスキップ(週次レポは確認先表示にフォールバック)")
        return 0
    site_id = os.environ.get("PLAUSIBLE_SITE_ID", "allgroup-inc.github.io")
    period = os.environ.get("PLAUSIBLE_PERIOD", "7d")
    api_base = os.environ.get("PLAUSIBLE_API_BASE", "https://plausible.io")
    counts = fetch_counts(api_key, site_id, period, api_base)
    fn = build_funnel(counts)
    out = {"schema_version": 1, "updated_at": date.today().isoformat(),
           "period": period, "source": "plausible-stats-api"}
    out.update(fn)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    ws = fn["worst_drop"]["stage"] if fn["worst_drop"] else "-"
    print(f"funnel.json 生成: 段数{len(fn['stages'])} / 最大離脱段={ws}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: self-test を実行して通過を確認**

Run: `python scripts/fetch_plausible_funnel.py --self-test`
Expected: PASS(`自己テスト OK: 3 ケース`)

- [ ] **Step 5: キー未設定フォールバックを確認**

Run: `python scripts/fetch_plausible_funnel.py`(環境変数なし)
Expected: `[info] PLAUSIBLE_API_KEY 未設定…` を表示し exit 0。`data/fukugiiro/funnel.json` は生成されない(`ls data/fukugiiro/funnel.json` が無い)。

- [ ] **Step 6: コミット**

```bash
git add scripts/fetch_plausible_funnel.py tests/golden_funnel.json
git commit -m "feat(fukugiiro): Plausibleファネル取得+集計(build_funnel/self-test)"
```

---

### Task 2: 週次レポートを funnel.json に接続

**Files:**
- Modify: `scripts/weekly_report_fukugiiro.py`

**Interfaces:**
- Consumes: `data/fukugiiro/funnel.json`(Task 1 の出力スキーマ: `stages`/`engagement`/`key_rates`/`worst_drop`/`updated_at`/`period`)

- [ ] **Step 1: `load_funnel()` と `render_funnel_section()` を追加**

`scripts/weekly_report_fukugiiro.py` の定数に追加(`SEIDO = ...` 付近):
```python
FUNNEL_PATH = os.path.join(BASE, "data", "fukugiiro", "funnel.json")
```

`load_jukyu()` の後に関数を追加:
```python
def load_funnel():
    """Plausible自動取得のファネル。無ければ None(手動フォールバック)。"""
    try:
        with open(FUNNEL_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _pct(x):
    return "—" if x is None else f"{round(x * 100)}%"


_MANUAL_FUNNEL = """## 2. ファネル(Plausibleで確認 → 数値を記入)

計測は稼働中ですが、外部ダッシュボードの数値は自動取得できないため**確認先**を示します。
ダッシュボード: https://plausible.io/allgroup-inc.github.io

| 段 | イベント名 | 今週の値(手動記入) |
|---|---|---|
| サイト来訪 | pageview | |
| 診断開始 | shindan_start | |
| 診断完了 | shindan_complete | |
| 準備シート表示 | kit_click | |
| 印刷 | kit_print / print_click | |
| 共有 | share_click | |
| 再訪(つづき) | shindan_resume | |
| 受給ずみマーク | seido_done_mark | |

*転換率(完了÷開始、シート÷完了)を毎週ここに残すと、離脱段が一目でわかります。*"""


def render_funnel_section(funnel):
    """funnel あれば自動集計セクション、無ければ手動フォールバックを返す。"""
    if not funnel or not funnel.get("stages"):
        return _MANUAL_FUNNEL
    rows = "\n".join(
        f"| {s['label']} | {s['count']} | {_pct(s['cvr_from_prev'])} | {_pct(s['drop_rate'])} |"
        for s in funnel["stages"]
    )
    kr = funnel.get("key_rates", {})
    eng = funnel.get("engagement", {})
    wd = funnel.get("worst_drop")
    worst_line = (f"**最大離脱**: {wd['label']}(−{_pct(wd['drop_rate'])})← 今週ここが一番落ちている傾向。"
                  if wd else "**最大離脱**: 算出に十分なデータがまだありません。")
    return (
        f"## 2. ファネル(自動取得 — Plausible Stats API / 直近{funnel.get('period','7d')})\n\n"
        f"更新: {funnel.get('updated_at','-')}。集計値のみ(個人識別子なし)。\n\n"
        "| 段 | 件数 | 前段比 | 離脱率 |\n|---|---|---|---|\n"
        f"{rows}\n\n"
        f"{worst_line}\n\n"
        f"**診断完了→LINE誘導**: {_pct(kr.get('line_cvr'))}(KPI 30%) / "
        f"**完了率**: {_pct(kr.get('finish_rate'))} / **0件率**: {_pct(kr.get('zero_rate'))}\n\n"
        f"補助: 準備シート {eng.get('kit_click',0)} / 受給ずみ {eng.get('seido_done_mark',0)} / "
        f"受給報告 {eng.get('jukyu_report_click',0)} / 0件 {eng.get('shindan_zero',0)}"
    )
```

- [ ] **Step 2: `pick_bottleneck()` を funnel 対応に**

`def pick_bottleneck(db, jukyu, keisai):` を `def pick_bottleneck(db, jukyu, keisai, funnel=None):` に変更。
最後の `return (...)`(「主要ゲートは通過…」)を次に置換:
```python
    wd = (funnel or {}).get("worst_drop")
    line_cvr = ((funnel or {}).get("key_rates") or {}).get("line_cvr")
    if wd:
        return (
            f"主要ゲートは通過。実測ファネルの最大離脱は {wd['label']}(離脱 {_pct(wd['drop_rate'])})。"
            + (f" 診断完了→LINE は {_pct(line_cvr)}(KPI30%)。" if line_cvr is not None else ""),
            f"離脱が最大の「{wd['label']}」に的を絞り、その段の文言/導線をA/B候補で1つだけ変更し、みがきの会で効果検証する。",
        )
    return (
        "主要ゲートは通過。次の律速は『診断→LINE登録率』の改善(M4条件30%)。",
        "診断完了画面のLINE誘導の文言・位置をA/B候補で1つだけ変更し、みがきの会で効果検証する。",
    )
```

- [ ] **Step 3: `main()` で funnel を読み、§2を差し替え**

`main()` 内、`bottleneck, nextaction = pick_bottleneck(db, jukyu, keisai)` を次に置換:
```python
    funnel = load_funnel()
    funnel_section = render_funnel_section(funnel)
    bottleneck, nextaction = pick_bottleneck(db, jukyu, keisai, funnel)
```

`md = f"""..."""` の中の §2 ブロック(`## 2. ファネル(Plausibleで確認 → 数値を記入)` から `*転換率(完了÷開始、シート÷完了)を毎週ここに残すと、離脱段が一目でわかります。*` まで)を、丸ごと次の1行に置換:
```
{funnel_section}
```

- [ ] **Step 4: funnel 無し(現状)で実行して壊れないか確認**

Run: `python scripts/weekly_report_fukugiiro.py`
Expected: 例外なく生成。`sed -n '/## 2. ファネル/,/## 3./p' reports/fukugiiro/latest.md` に**手動フォールバック**(「Plausibleで確認 → 数値を記入」)が出る。

- [ ] **Step 5: funnel 有りで自動描画を確認(一時ファイル)**

Run:
```bash
cat > data/fukugiiro/funnel.json <<'JSON'
{"schema_version":1,"updated_at":"2026-07-26","period":"7d","source":"plausible-stats-api",
 "stages":[{"key":"shindan_start","label":"診断開始","count":100,"cvr_from_prev":null,"drop_rate":null},
 {"key":"shindan_complete","label":"診断完了(1件以上)","count":35,"cvr_from_prev":0.35,"drop_rate":0.65},
 {"key":"line_add_click","label":"LINE誘導クリック","count":12,"cvr_from_prev":0.3429,"drop_rate":0.6571}],
 "engagement":{"kit_click":8,"seido_done_mark":2,"jukyu_report_click":1,"shindan_zero":3},
 "key_rates":{"finish_rate":0.38,"line_cvr":0.3429,"zero_rate":0.0789},
 "worst_drop":{"stage":"shindan_complete","label":"診断開始→診断完了(1件以上)","drop_rate":0.65}}
JSON
python scripts/weekly_report_fukugiiro.py
sed -n '/## 2. ファネル/,/## 3./p' reports/fukugiiro/latest.md
rm -f data/fukugiiro/funnel.json
git checkout -- reports/fukugiiro/ 2>/dev/null || true
```
Expected: §2 が「自動取得」の表(件数・前段比・離脱率)+「最大離脱」行で出る。確認後 funnel.json を削除しレポート生成物を戻す。

- [ ] **Step 6: コミット**

```bash
git add scripts/weekly_report_fukugiiro.py
git commit -m "feat(fukugiiro): 週次レポにPlausibleファネル自動描画+離脱段ボトルネックを統合"
```

---

### Task 3: ワークフロー配線(取得ジョブ + CI self-test)

**Files:**
- Modify: `.github/workflows/fukugiiro-weekly-report.yml`
- Modify: `.github/workflows/fukugiiro-ci.yml`

**Interfaces:** なし(CI/CD 配線)

- [ ] **Step 1: 週次ワークフローに取得ステップを追加**

`.github/workflows/fukugiiro-weekly-report.yml` の「週次レポート生成(統括ユイさん)」ステップの**直前**に挿入:
```yaml
      - name: Plausibleファネル取得(キーが有れば)
        continue-on-error: true
        env:
          PLAUSIBLE_API_KEY: ${{ secrets.PLAUSIBLE_API_KEY }}
        run: python scripts/fetch_plausible_funnel.py
```
同ファイルの Commit ステップの `git add reports/fukugiiro` を次に変更:
```yaml
          git add reports/fukugiiro data/fukugiiro/funnel.json
```

- [ ] **Step 2: CI に self-test を追加(paths + step)**

`.github/workflows/fukugiiro-ci.yml` の `push:` と `pull_request:` の `paths:` 両方に2行追加:
```yaml
      - "scripts/fetch_plausible_funnel.py"
      - "tests/golden_funnel.json"
```
「LP検査…」ステップの**前**にステップを追加:
```yaml
      - name: Plausibleファネル集計 自己テスト
        run: python scripts/fetch_plausible_funnel.py --self-test
```

- [ ] **Step 3: YAML の妥当性と self-test を確認**

Run:
```bash
python -c "import yaml,sys; [yaml.safe_load(open(p)) for p in ['.github/workflows/fukugiiro-weekly-report.yml','.github/workflows/fukugiiro-ci.yml']]; print('YAML OK')" 2>/dev/null || python -c "print('pyyaml未導入のためYAMLロード確認はCIに委ねる')"
python scripts/fetch_plausible_funnel.py --self-test
```
Expected: YAML OK(または pyyaml 未導入メッセージ)/ self-test PASS

- [ ] **Step 4: git status が意図どおりか確認**

Run: `git status --short`
Expected: 変更は2つのワークフローのみ。`data/fukugiiro/funnel.json` や `reports/` の残骸が無い(Task 2 Step5 で戻したもの以外に無い)。

- [ ] **Step 5: コミット**

```bash
git add .github/workflows/fukugiiro-weekly-report.yml .github/workflows/fukugiiro-ci.yml
git commit -m "ci(fukugiiro): 週次にPlausible取得ステップ追加+ファネルself-testをCIゲート化"
```

---

## Self-Review(この計画の点検)

- **Spec coverage**: §1アーキ=Task1+3。§2.1 fetch script=Task1。§2.2 funnel.json スキーマ=Task1(main 出力)。§2.3 週次ワークフロー=Task3 Step1。§2.4 週次レポ統合(load_funnel/render/ pick_bottleneck)=Task2。§3 テスト(self-test+golden+欠損/ゼロ除算)=Task1 golden の3ケース。§3 CI=Task3 Step2。§4 守り(集計のみ・キー非ログ・None率)=Global Constraints+build_funnel。✅ 網羅。
- **Placeholder scan**: 全ステップに実コードを提示。Task3 Step3 の YAML ロードは pyyaml 有無で分岐する運用注記(TODOではない)。
- **Type consistency**: `build_funnel` 返却キー(stages/engagement/key_rates/worst_drop、各 `count/cvr_from_prev/drop_rate`、`worst_drop.{stage,label,drop_rate}`)は Task1 定義=Task2 消費で一致。`load_funnel()`/`render_funnel_section()`/`_pct()` 参照名一致。`pick_bottleneck(db,jukyu,keisai,funnel=None)` の追加引数は Task2 Step2 と Step3 で一致。
- **フォールバックの一貫性**: キー無し→funnel.json 未生成→`load_funnel()`=None→`render_funnel_section`=手動→既存挙動維持。3経路が整合。
