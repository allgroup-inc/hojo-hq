#!/usr/bin/env python3
"""週次経営レポート生成。

- input/sales.csv を読み、直近7日(今週)とその前7日(前週)を集計
- KPI計算はすべてPython側で行い、Claudeには「所見の執筆」だけをさせる
  (数値の捏造・計算ミスを構造的に防ぐ)
- 出力: reports/<YYYY>-W<週番号>.md

使い方:
  python scripts/build_report.py               # 通常実行(要 ANTHROPIC_API_KEY)
  python scripts/build_report.py --offline     # AI所見なしのテスト実行
  python scripts/build_report.py --days 30     # 集計期間を30日に(月次化)

CSVの列を増やした場合は summarize() に集計を足し、レポートテンプレートに
表示を足せばよい。Claudeへは stats(集計結果のJSON)がそのまま渡る。
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_FILE = ROOT / "input" / "sales.csv"
REPORTS_DIR = ROOT / "reports"

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

SYSTEM_PROMPT = """あなたは中小企業の経営に伴走する経営参謀です。渡された集計データ(JSON)だけを根拠に、週次レポートの所見を書きます。

厳守事項:
- 数値はデータにあるものだけを使う。自分で計算・推定した数値を書かない
- 増減の要因は断定せず「〜の可能性」として書く(データに要因情報はないため)
- 提案は具体的な行動レベルで(「頑張る」ではなく「〇〇件に電話する」の粒度)
- 経営者が朝5分で読める分量に"""

COMMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "今週の総括(2〜3文)"},
        "highlights": {"type": "array", "items": {"type": "string"},
                       "description": "良かった点(最大3つ)"},
        "concerns": {"type": "array", "items": {"type": "string"},
                     "description": "注意すべき点(最大3つ)"},
        "next_actions": {"type": "array", "items": {"type": "string"},
                         "description": "来週の推奨アクション(最大3つ)"},
    },
    "required": ["summary", "highlights", "concerns", "next_actions"],
    "additionalProperties": False,
}


def load_rows() -> list:
    rows = []
    with CSV_FILE.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "date": date.fromisoformat(row["date"].strip()),
                    "category": row["category"].strip(),
                    "amount": int(row["amount"]),
                    "count": int(row.get("count") or 1),
                })
            except (ValueError, KeyError) as e:
                print(f"! 不正な行をスキップ: {row} ({e})")
    return rows


def summarize(rows: list, start: date, end: date) -> dict:
    """[start, end) の期間を集計する。"""
    period = [r for r in rows if start <= r["date"] < end]
    by_category = {}
    for r in period:
        c = by_category.setdefault(r["category"], {"amount": 0, "count": 0})
        c["amount"] += r["amount"]
        c["count"] += r["count"]
    return {
        "period": f"{start.isoformat()} 〜 {(end - timedelta(days=1)).isoformat()}",
        "total_amount": sum(r["amount"] for r in period),
        "total_count": sum(r["count"] for r in period),
        "by_category": by_category,
        "days_with_sales": len({r["date"] for r in period}),
    }


def pct_change(now: int, before: int) -> str:
    if before == 0:
        return "—(前期間データなし)"
    return f"{(now - before) / before * 100:+.1f}%"


def ai_commentary(stats: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": COMMENT_SCHEMA}},
        messages=[{"role": "user", "content":
                   "以下の週次集計データをもとに所見を書いてください。\n\n"
                   + json.dumps(stats, ensure_ascii=False, indent=1)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("モデルが処理を拒否しました")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def render(stats: dict, comment: dict, report_id: str) -> str:
    this_week, last_week = stats["this_week"], stats["last_week"]
    lines = [
        f"# 週次経営レポート {report_id}",
        "",
        f"対象期間: {this_week['period']}(比較: {last_week['period']})",
        "",
        "## 数字サマリー",
        "",
        "| 指標 | 今週 | 前週 | 前週比 |",
        "|---|---:|---:|---:|",
        f"| 売上合計 | {this_week['total_amount']:,}円 | {last_week['total_amount']:,}円 | "
        f"{pct_change(this_week['total_amount'], last_week['total_amount'])} |",
        f"| 件数合計 | {this_week['total_count']:,}件 | {last_week['total_count']:,}件 | "
        f"{pct_change(this_week['total_count'], last_week['total_count'])} |",
        "",
        "### カテゴリ別(今週)",
        "",
        "| カテゴリ | 売上 | 件数 | 前週売上 |",
        "|---|---:|---:|---:|",
    ]
    for name, c in sorted(this_week["by_category"].items(),
                          key=lambda x: -x[1]["amount"]):
        prev = last_week["by_category"].get(name, {"amount": 0})
        lines.append(f"| {name} | {c['amount']:,}円 | {c['count']:,}件 | {prev['amount']:,}円 |")

    lines += ["", "## 総括", "", comment["summary"], "", "## 良かった点", ""]
    lines += [f"- {h}" for h in comment["highlights"]] or ["- (なし)"]
    lines += ["", "## 注意点", ""]
    lines += [f"- {c}" for c in comment["concerns"]] or ["- (なし)"]
    lines += ["", "## 来週のアクション", ""]
    lines += [f"- [ ] {a}" for a in comment["next_actions"]] or ["- (なし)"]
    lines += ["", "---", "_このレポートは自動生成です。数値はCSVからの機械集計、所見はAIによる草案です。_", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="AI所見なしで実行(テスト用)")
    parser.add_argument("--days", type=int, default=7, help="集計期間の日数(既定7)")
    parser.add_argument("--asof", type=str, default=None, help="基準日 YYYY-MM-DD(既定: 今日)")
    args = parser.parse_args()

    asof = date.fromisoformat(args.asof) if args.asof else date.today()
    rows = load_rows()
    if not rows:
        print("エラー: input/sales.csv に有効なデータがありません")
        return 1

    span = timedelta(days=args.days)
    stats = {
        "this_week": summarize(rows, asof - span, asof),
        "last_week": summarize(rows, asof - span * 2, asof - span),
    }

    if args.offline:
        comment = {
            "summary": "(オフラインテスト実行のためAI所見は生成していません)",
            "highlights": ["--offline を外し、ANTHROPIC_API_KEY を設定すると所見が入ります"],
            "concerns": [], "next_actions": [],
        }
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("エラー: 環境変数 ANTHROPIC_API_KEY が未設定です(テストは --offline)")
            return 1
        comment = ai_commentary(stats)

    year, week, _ = asof.isocalendar()
    report_id = f"{year}-W{week:02d}"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"{report_id}.md"
    out.write_text(render(stats, comment, report_id), encoding="utf-8")
    print(f"レポート生成: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
