# 営業参謀本部 実装計画 (Insurance Eigyo-Sanbou Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ALLGROUP 保険対面営業の数値を個人/チーム/全体の3階層で把握し、反映(入力)の誤りを機械検知し、達成へ導く「営業参謀本部」の土台一式(数値モデル定義書・反映監査スクリプト・参謀チーム定義・レポ様式)を作る。

**Architecture:** ドキュメント成果物(`docs/insurance/`)＋純関数中心の監査スクリプト(`scripts/insurance/`)＋合成データによるユニットテスト(`tests/insurance/`)。ドメインロジック(負値検知・ロールアップ照合)は xlsx レイアウトから切り離した純関数として TDD。xlsx 読み取りは薄いアダプタ層に閉じ込め、実データに対しては最後に統合実行する。

**Tech Stack:** Python 3(openpyxl, pytest)。ドキュメントは Markdown。既存 repo の `.claude/agents/*.md` 書式に準拠。

## Global Constraints

- 設計書: `docs/insurance/00_設計書_営業参謀本部_v1.md`(本計画の親スペック)。
- **正確性最優先**: 監査結果は「要確認」表記。断定しない。原文=元セル座標を必ず併記。
- **プライバシー(守り)**: 個人名を含む生データ(受領xlsx)・実データ監査レポートは **git にコミットしない**。コミット対象は「スクリプト・合成データ・設計/様式・匿名化した例」のみ。実データ監査レポートはスクラッチパッド(`/tmp/claude-0/.../scratchpad`)に出力する。
- **最終決裁は小柳さん**。参謀は提案まで。
- 対象9管轄: 嘉手納(下地)/特殊(長澤兼任)/催事(仲宗根)/豊見城(金城)/札幌(泉谷)/ALL委託(島袋)/CRM(呉屋)/QCM(徳元)/LTV(上地)。地域=沖縄本島+札幌。
- 三名体制(スイシン/ウタガイ/ベッカイ)。ウタガイの反対理由が無い議事は無効。
- コミット author: `Claude <noreply@anthropic.com>`。コミットメッセージにモデル識別子を書かない。

---

## File Structure

作成/変更するファイルと責務:

- `docs/insurance/README.md` — 索引(何がどこにあるか)。
- `docs/insurance/10_数値モデル定義書.md` — KPI用語集・ファネル・3階層ロールアップ式・4列定義。
- `scripts/insurance/audit_reflection.py` — 反映監査の純関数＋xlsxアダプタ＋CLI。
- `scripts/insurance/README.md` — 監査スクリプトの使い方。
- `tests/insurance/test_audit_reflection.py` — 合成データによるユニットテスト。
- `tests/insurance/__init__.py` — (存在すれば不要)テストパッケージ化用。
- `docs/insurance/20_反映監査チェックリスト.md` — 人手チェックリスト＋スクリプト実行手順＋結果の読み方。
- `docs/insurance/agents/統括参謀.md` 他 計7ファイル — 参謀チーム定義。
- `docs/insurance/30_レポ様式_週次.md` / `docs/insurance/31_レポ様式_日次.md` — レポテンプレ。

依存順: Task1(モデル定義) → Task2(監査スクリプト) → Task3(監査チェックリスト) → Task4(参謀定義) → Task5(レポ様式)。Task2 が技術的中核(TDD)。他は文書成果物で受け入れ基準を検証ステップとする。

---

## Task 1: 数値モデル定義書 + 索引

**Files:**
- Create: `docs/insurance/README.md`
- Create: `docs/insurance/10_数値モデル定義書.md`

**Interfaces:**
- Produces: KPI用語・ファネル段・3階層ロールアップの共通語彙。後続タスク(監査・参謀・レポ)が参照する用語の正典。

- [ ] **Step 1: 索引 `README.md` を作成**

内容(実データ確認済みの事実のみ。未確定は「要確認」):
```markdown
# 営業参謀本部 — insurance/ 索引

ALLGROUP 保険対面営業(沖縄本島+札幌)の数値管理・戦略の置き場所。

- 00_設計書_営業参謀本部_v1.md — 設計書(親)
- 10_数値モデル定義書.md — KPI用語・ファネル・ロールアップ式
- 20_反映監査チェックリスト.md — 反映の正確性チェック手順
- 30_レポ様式_週次.md / 31_レポ様式_日次.md — レポテンプレ
- agents/ — 参謀チーム定義(統括+5参謀+数値監査役)
- （スクリプト）scripts/insurance/audit_reflection.py — 反映監査

生データ(個人名入りxlsx)はコミットしない(設計書§5)。
```

- [ ] **Step 2: `10_数値モデル定義書.md` を作成**

以下を必ず含む(設計書§1の内容を正典化):
- **用語集**: ANP(年換算新契約保険料)/ 保全 / 戻入(率・金額)/ 想定単価 / 稼動減率(稼動予→減率)/ 経過必要数 / 現差異 / 進捗 / 予算件数 / 予算ANP。各1行で定義。CRM・QCM・LTVは「要確認」と明記。
- **営業ファネル(縦軸)**: 実稼働時間 → 発信数・配布数 → キャッチ数・着座数 → アポ・前確OK・保全数 → 訪問・後確OK数・保全完了数 → 申込数・開通数・戻入金額。
- **3階層ロールアップ**: 個人【実数値】(日次) → 管轄【チーム進捗】 → 全体【ALLGRP】board。
- **4列の定義**: 実績 / 経過必要数(=目標を稼動日数・経過日数・残日数で按分) / 現差異(=実績−経過必要数、負値は正常にあり得る) / 進捗(=達成率)。
- **符号の約束**: 「実数値系(実稼働時間・発信数・件数・ANP等)は非負。負値は反映エラーの疑い」「現差異・各種"率の差"は負値が正常にあり得る」を表で明示 → 監査スクリプトの `NONNEG_METRICS` の根拠になる。

- [ ] **Step 3: 検証**

Run: `test -f docs/insurance/README.md && test -f docs/insurance/10_数値モデル定義書.md && grep -q "ANP" docs/insurance/10_数値モデル定義書.md && grep -q "非負" docs/insurance/10_数値モデル定義書.md && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add docs/insurance/README.md docs/insurance/10_数値モデル定義書.md
git commit -m "docs(insurance): 数値モデル定義書と索引(用語集・ファネル・ロールアップ・符号約束)"
```

---

## Task 2: 反映監査スクリプト(TDD)

**Files:**
- Create: `tests/insurance/test_audit_reflection.py`
- Create: `scripts/insurance/audit_reflection.py`
- Create: `scripts/insurance/README.md`

**Interfaces:**
- Consumes: Task1 の「符号の約束」(どの指標が非負か)。
- Produces:
  - `NONNEG_METRICS: set[str]` — 非負であるべき指標名の集合。
  - `detect_negative_anomalies(records: list[dict]) -> list[dict]` — record は `{"metric": str, "coord": str, "area": str, "value": float|None}`。metric が NONNEG かつ value<0 の record を返す(理由 `reason="negative"` 付き)。
  - `detect_blanks(records: list[dict]) -> list[dict]` — value が None の record を返す(`reason="blank"`)。
  - `check_rollup(parts: list[float], total: float, tol: float = 1.0) -> dict` — `{"ok": bool, "sum_parts": float, "total": float, "diff": float}`。
  - `extract_board_records(path: str) -> list[dict]` — ALLGRP board(xlsx)を上記 record 形式に変換(xlsxアダプタ、統合実行で使用)。
  - CLI: `python scripts/insurance/audit_reflection.py <board.xlsx> [--out report.md]` — 監査を実行し「要確認リスト」Markdownを出力。

- [ ] **Step 1: 失敗するテストを書く**

`tests/insurance/test_audit_reflection.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "insurance"))
import audit_reflection as a


def test_detect_negative_flags_negative_working_hours():
    records = [
        {"metric": "実稼働時間", "coord": "H46", "area": "ALL委託", "value": -283.0},
        {"metric": "実稼働時間", "coord": "C46", "area": "豊見城", "value": 627.5},
    ]
    out = a.detect_negative_anomalies(records)
    assert len(out) == 1
    assert out[0]["coord"] == "H46"
    assert out[0]["reason"] == "negative"


def test_detect_negative_ignores_diff_metric_that_may_be_negative():
    # 現差異は負値が正常にあり得るので NONNEG に含めない
    records = [{"metric": "現差異", "coord": "F10", "area": "嘉手納", "value": -90.7}]
    assert a.detect_negative_anomalies(records) == []


def test_detect_blanks_flags_none():
    records = [
        {"metric": "予算ANP", "coord": "C11", "area": "嘉手納", "value": None},
        {"metric": "予算ANP", "coord": "H11", "area": "特殊", "value": 790.0},
    ]
    out = a.detect_blanks(records)
    assert len(out) == 1 and out[0]["coord"] == "C11"


def test_check_rollup_matches_within_tolerance():
    r = a.check_rollup([100.0, 50.0, 25.0], 175.4, tol=1.0)
    assert r["ok"] is True
    assert abs(r["sum_parts"] - 175.0) < 1e-9


def test_check_rollup_flags_mismatch():
    r = a.check_rollup([100.0, 50.0], 200.0, tol=1.0)
    assert r["ok"] is False
    assert abs(r["diff"] - 50.0) < 1e-9
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `cd /home/user/hojo-hq && python -m pytest tests/insurance/test_audit_reflection.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'audit_reflection'` 相当)

- [ ] **Step 3: 最小実装を書く**

`scripts/insurance/audit_reflection.py`:
```python
"""反映監査 — ALLGRP board の反映(入力)の正確性を機械検知する。
純関数(検知・照合)＋xlsxアダプタ＋CLI。断定せず「要確認」を出力する。"""
from __future__ import annotations
import argparse

# 非負であるべき指標(実数値系)。現差異・率の差など負値が正常な指標は含めない。
NONNEG_METRICS = {
    "実稼働時間", "発信数・配布数", "キャッチ数・着座数",
    "アポ・前確OK・保全数", "訪問・後確OK数・保全完了数",
    "申込数・開通数・戻入金額", "予算件数", "予算ANP",
    "時間→発信数", "想定単価",
}


def detect_negative_anomalies(records):
    out = []
    for r in records:
        v = r.get("value")
        if v is None:
            continue
        if r.get("metric") in NONNEG_METRICS and v < 0:
            out.append({**r, "reason": "negative"})
    return out


def detect_blanks(records):
    return [{**r, "reason": "blank"} for r in records if r.get("value") is None]


def check_rollup(parts, total, tol=1.0):
    s = sum(p for p in parts if p is not None)
    diff = s - total
    return {"ok": abs(diff) <= tol, "sum_parts": s, "total": total, "diff": diff}


def extract_board_records(path):
    """ALLGRP board(xlsx)を record 形式に変換する薄いアダプタ。
    各管轄ブロックの [実績/経過必要数/現差異/進捗] を走査し、非負指標セルを record 化。
    レイアウト依存のため統合実行で実データ検証する(ユニットテスト対象外)。"""
    import openpyxl
    from openpyxl.utils import get_column_letter
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    records = []
    metric = None
    for row in range(1, ws.max_row + 1):
        label = ws.cell(row, 2).value  # B列=指標名
        if isinstance(label, str) and label.strip():
            metric = label.strip()
        if metric not in NONNEG_METRICS:
            continue
        for col in range(3, ws.max_column + 1):
            v = ws.cell(row, col).value
            if isinstance(v, (int, float)):
                records.append({
                    "metric": metric,
                    "coord": f"{get_column_letter(col)}{row}",
                    "area": "",
                    "value": float(v),
                })
    wb.close()
    return records


def render_report(anomalies):
    lines = ["# 反映監査 要確認リスト", "", "> 断定ではなく「要確認」。原文=元セルで確認してください。", ""]
    if not anomalies:
        lines.append("要確認事項は検知されませんでした。")
    else:
        lines.append("| セル | 指標 | 値 | 種別 |")
        lines.append("|---|---|---|---|")
        for x in anomalies:
            lines.append(f"| {x['coord']} | {x['metric']} | {x['value']} | {x['reason']} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("board")
    p.add_argument("--out")
    args = p.parse_args(argv)
    records = extract_board_records(args.board)
    anomalies = detect_negative_anomalies(records)
    report = render_report(anomalies)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"wrote {args.out} ({len(anomalies)} anomalies)")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: テストを実行し合格を確認**

Run: `cd /home/user/hojo-hq && python -m pytest tests/insurance/test_audit_reflection.py -v`
Expected: PASS(5件)

- [ ] **Step 5: スクリプトREADMEを作成**

`scripts/insurance/README.md`:
```markdown
# 反映監査 audit_reflection.py

ALLGRP board(xlsx)の反映(入力)の正確性を機械検知する。断定せず「要確認」を出す。

## 使い方
    python scripts/insurance/audit_reflection.py <board.xlsx> --out <report.md>

- 生データ・実データレポートは git にコミットしない(設計書§5)。
- 出力先はスクラッチパッド等の非追跡ディレクトリにする。

## 検知内容
- 非負であるべき指標の負値(NONNEG_METRICS)
- 空欄(blank)
- ロールアップ照合(個人合計=管轄=全体): check_rollup()
```

- [ ] **Step 6: 実データで統合実行(レポートは非追跡ディレクトリへ)**

Run(パスは実環境に合わせる):
```bash
cd /home/user/hojo-hq
python scripts/insurance/audit_reflection.py \
  "/root/.claude/uploads/219718b2-f459-596e-a773-ba28cda33b7b/d4c0a90e-_ALLGRP____.xlsx" \
  --out "/tmp/claude-0/-home-user-hojo-hq/219718b2-f459-596e-a773-ba28cda33b7b/scratchpad/audit_7月.md"
```
Expected: `wrote ... (N anomalies)`。N≥1(§設計書2.2 の ★ALL委託 負値が拾えること)。**検知結果はユーザーに要約報告し、レポート実体はコミットしない。**

- [ ] **Step 7: Commit(スクリプトとテストのみ)**

```bash
git add scripts/insurance/audit_reflection.py scripts/insurance/README.md tests/insurance/test_audit_reflection.py
git commit -m "feat(insurance): 反映監査スクリプト(負値・空欄・ロールアップ照合)+ ユニットテスト"
```

---

## Task 3: 反映監査チェックリスト(人手手順)

**Files:**
- Create: `docs/insurance/20_反映監査チェックリスト.md`

**Interfaces:**
- Consumes: Task2 のスクリプト(実行手順)、Task1 の符号約束。

- [ ] **Step 1: チェックリストを作成**

必ず含む:
- **運用リスクの前提**: `※反映のやり方`は手作業の値貼り付け中心/経過日数は手打ち(値貼り付け厳禁)→ 参照ズレ・範囲ミス・手打ち漏れが起きやすい。
- **毎日の反映後チェック(人手)**: ①負値が無いか ②空欄が無いか ③経過日数が正しいか ④6月版と7月版で列定義がズレていないか。
- **スクリプト実行手順**: Task2 のコマンド。出力の読み方(要確認リストの各行=元セルで原文確認)。
- **エスカレーション**: 要確認が出たら → 該当管轄責任者へ確認 → 直らなければ数値監査役 → 小柳さん。断定しない。

- [ ] **Step 2: 検証**

Run: `grep -q "値貼り付け" docs/insurance/20_反映監査チェックリスト.md && grep -q "audit_reflection.py" docs/insurance/20_反映監査チェックリスト.md && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add docs/insurance/20_反映監査チェックリスト.md
git commit -m "docs(insurance): 反映監査チェックリスト(人手手順+スクリプト連携+エスカレーション)"
```

---

## Task 4: 参謀チーム定義(agent .md 群)

**Files:**
- Create: `docs/insurance/agents/統括参謀.md`
- Create: `docs/insurance/agents/稼動参謀.md`
- Create: `docs/insurance/agents/ゼロイチ参謀.md`
- Create: `docs/insurance/agents/生産性参謀.md`
- Create: `docs/insurance/agents/営業参謀.md`
- Create: `docs/insurance/agents/物件参謀.md`
- Create: `docs/insurance/agents/数値監査役.md`

**Interfaces:**
- Consumes: Task1 の用語・ファネル、設計書§3 の役割表。
- 書式は既存 `.claude/agents/*.md`(ミッション/権限/KPI/施策/週次報告/禁止事項/判断原則)に準拠。

- [ ] **Step 1: 統括参謀.md を作成**

含む: ミッション(全体最適・ボトルネック特定・単一ネクストアクション)/ 権限(提案まで・決裁は小柳さん)/ 監視KPI(予算件数・予算ANP の全体進捗、経過必要数との差)/ 週次・日次レポ責務(§Task5様式)/ 意思決定フロー(3役→統括裁定→上申)/ 判断原則(迷ったら「達成に近づくか」)。統括は議論の当事者にならず裁定者。

- [ ] **Step 2: 5参謀 md を作成(稼動/ゼロイチ/生産性/営業/物件)**

各ファイル共通骨子＋固有KPI:
- 稼動参謀: 実稼働時間・稼動減率。無駄な稼働ゼロ日の削減。
- ゼロイチ参謀: 発信→キャッチ→アポ、アポ・パーミ・リーズ化率。新規の立ち上げ。
- 生産性参謀: 着座率・歩留まり、無生産性(非生産時間)の削減。
- 営業参謀: 訪問→申込、予算ANP・想定単価・後確OK率。
- 物件参謀: 保全・保全完了、返送率、戻入(率・金額)。
各 md に「三名体制で議論/ウタガイの反対理由記録必須」「個人・チーム・全体の3視点で担当KPIを見る」を明記。

- [ ] **Step 3: 数値監査役.md を作成**

含む: 独立性(統括の指揮系統外・報告は小柳さん直)/ ミッション(反映の機械照合・異常検知)/ 手段(Task2スクリプト+Task3チェックリスト)/ 禁止(断定・生データの外部送信)/ 原則(要確認で止める、原文照合)。

- [ ] **Step 4: 検証**

Run: `ls docs/insurance/agents/*.md | wc -l | grep -q 7 && grep -q "ウタガイ" docs/insurance/agents/統括参謀.md && grep -q "指揮系統外" docs/insurance/agents/数値監査役.md && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add docs/insurance/agents/
git commit -m "docs(insurance): 参謀チーム定義(統括+5参謀+独立監査役、三名体制準拠)"
```

---

## Task 5: レポ様式(週次/日次)

**Files:**
- Create: `docs/insurance/30_レポ様式_週次.md`
- Create: `docs/insurance/31_レポ様式_日次.md`

**Interfaces:**
- Consumes: Task1 のファネル/4列、設計書§1.4 の按分(稼動日数・経過日数・残日数)。

- [ ] **Step 1: 週次様式を作成**

board準拠のセクション: ①今週の結論(単一ネクストアクション)②全体進捗(予算件数・予算ANP vs 経過必要数、現差異・進捗)③管轄別内訳(9管轄)④ファネル各段の歩留まり⑤責任者能力図(5軸S/A/B)⑥反映監査の結果(要確認件数)⑦人間の次アクション。記入枠(空欄テンプレ)で提供。

- [ ] **Step 2: 日次様式を作成**

軽量版: 反映〆(翌9時)チェック / 当日の稼動・発信・アポ・申込 / 経過必要数との差 / 要確認(負値・空欄) / 明日の一手。

- [ ] **Step 3: 検証**

Run: `grep -q "単一ネクストアクション" docs/insurance/30_レポ様式_週次.md && grep -q "経過必要数" docs/insurance/31_レポ様式_日次.md && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add docs/insurance/30_レポ様式_週次.md docs/insurance/31_レポ様式_日次.md
git commit -m "docs(insurance): レポ様式(週次/日次、board準拠・単一ネクストアクション)"
```

---

## Self-Review(計画作成後の点検)

- **Spec coverage**: 設計書§1(数値モデル)=Task1 / §2(反映監査)=Task2,3 / §3(チーム)=Task4 / §4成果物=Task1-5 / §5プライバシー=Global Constraints+Task2手順 / §7未確定=各所「要確認」。網羅OK。
- **Placeholder scan**: コード・検証コマンド・様式内容はすべて実体を記載。TODO/TBD無し。
- **Type consistency**: `detect_negative_anomalies` / `detect_blanks` / `check_rollup` / `extract_board_records` / `NONNEG_METRICS` は Task2 内で定義・使用が一致。テストの record キー(metric/coord/area/value)と実装が一致。
- **未確定依存**: CRM/QCM/LTV名称・目標値・KGI は §7 未確定のまま。各成果物は「要確認」で明示し、判明後に追記する設計(監査スクリプトは目標値に依存せず異常を検知するため先行可能)。
