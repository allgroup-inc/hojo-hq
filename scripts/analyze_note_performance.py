#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — note パフォーマンス自動分析スクリプト

毎週日曜夜に実行。note analytics から記事別パフォーマンスを集計し、
Claude で最適化提案を自動生成。翌週のコンテンツテーマを AI が提案。

実行:
  python analyze_note_performance.py          # レポート生成
  python analyze_note_performance.py --claude # Claude で分析
"""

import anthropic
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(__file__)
DATA_DIR = os.path.join(os.path.dirname(BASE), "data")
REPORT_DIR = os.path.join(os.path.dirname(BASE), "docs", "note_analytics")


def load_note_screenshot_data() -> dict:
    """note スクリーンショットのデータを読み込む（本来は API から取得）。

    現在、手動でスクリーンショットから抽出したデータを使用。
    本格運用では note_api.py の機能を拡張して自動取得。
    """

    # スクリーンショットから手動抽出したデータ（2026-10-03）
    data = {
        "week": "2026-W40",
        "fetched_at": "2026-10-03T07:46:00+09:00",
        "total_views": 101,
        "total_likes": 19,
        "articles": [
            {
                "title": "開封率の経営学 — 顧客リストの「数」より「熱」をお金に変え...",
                "views": 25,
                "likes": 1,
                "engagement_rate": 0.04,
                "type": "L1_gather"
            },
            {
                "title": "「地方だから不利」は本当か — 人口4万人の町・1店舗カフェ・...",
                "views": 16,
                "likes": 4,
                "engagement_rate": 0.25,
                "type": "L1_gather"
            },
            {
                "title": "フォロワーが買うのではなかった — Xとnoteの公式データ...",
                "views": 15,
                "likes": 0,
                "engagement_rate": 0.0,
                "type": "L1_gather"
            },
            {
                "title": "実録・第7週 — 累計64ビュー、判定基準未達で仮説を1つ棄...",
                "views": 14,
                "likes": 5,
                "engagement_rate": 0.357,
                "type": "L2_insight"
            },
            {
                "title": "0→1万フォロワーを目指す前に知っておきたい、世界のプレイ...",
                "views": 13,
                "likes": 8,
                "engagement_rate": 0.615,
                "type": "L1_gather"
            },
            {
                "title": "実録・第8週 — 予承94ビュー、スキ18の閲覧と、バグで2日遅...",
                "views": 7,
                "likes": 1,
                "engagement_rate": 0.143,
                "type": "L2_insight"
            },
            {
                "title": "SNSで退場する人の共通点だけを集めた — 凍結・シャドウバ...",
                "views": 6,
                "likes": 0,
                "engagement_rate": 0.0,
                "type": "L1_gather"
            },
            {
                "title": "AIだけでnoteマガジンを運営した1か月の実録 — 売上0円か...",
                "views": 3,
                "likes": 0,
                "engagement_rate": 0.0,
                "type": "L2_insight"
            },
            {
                "title": "値上げで売れたアイスと、18円で客が離れた焼き鳥 — 価格...",
                "views": 2,
                "likes": 0,
                "engagement_rate": 0.0,
                "type": "L3_premium"
            }
        ]
    }

    return data


def analyze_with_claude(data: dict) -> str:
    """Claude で性能分析と最適化提案を生成。"""

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # ユーザーに提示するデータ
    top_articles = sorted(data["articles"], key=lambda x: x["engagement_rate"], reverse=True)[:3]
    low_articles = sorted(data["articles"], key=lambda x: x["views"])[:3]

    prompt = f"""
あなたは note マガジンの収益最適化コンサルタントです。
下記のデータに基づいて、来週のコンテンツ戦略を提案してください。

【現状データ(2026年W40)】
- 総ビュー数: {data['total_views']} (月30万円目標まで、あと25倍必要)
- 総スキ数: {data['total_likes']}
- 掲載記事数: {len(data['articles'])}

【高エンゲージメント TOP3】
"""
    for art in top_articles:
        prompt += f"\n- 「{art['title'][:40]}」: {art['views']}ビュー・{art['likes']}スキ({art['engagement_rate']:.1%})"

    prompt += f"""

【低迷記事 TOP3】
"""
    for art in low_articles:
        prompt += f"\n- 「{art['title'][:40]}」: {art['views']}ビュー・{art['likes']}スキ"

    prompt += f"""

【あなたの提案】
1. 高エンゲージメント記事の成功要因は何か（2〜3行）
2. 低迷の原因仮説（2〜3行）
3. 来週のコンテンツテーマ5つ（具体的に）
4. 投稿頻度・時間の改善提案
5. 月30万円達成への具体的な数値目標（来週のビュー数・スキ数）
"""

    try:
        message = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text.strip()

    except Exception as e:
        print(f"[error] Claude API エラー: {e}")
        return ""


def generate_report(data: dict, analysis: str) -> str:
    """レポート Markdown を生成。"""

    lines = [
        f"# note マガジン週次分析レポート",
        f"_生成: {datetime.now(JST).strftime('%Y年%m月%d日 %H:%M')}_",
        "",
        "## サマリー",
        "",
        f"- 週間ビュー数: **{data['total_views']}**",
        f"- 週間スキ数: **{data['total_likes']}**",
        f"- 平均エンゲージメント率: **{sum(a['engagement_rate'] for a in data['articles']) / len(data['articles']):.1%}**",
        f"- 投稿数: {len(data['articles'])}",
        "",
        "## 状況",
        "",
        "現在、月30万円の収益目標に対して **月101ビュー** という状況。",
        "達成には **25倍のビュー数増加** が必要です。",
        "",
        "## AI 最適化提案",
        "",
        analysis,
        "",
        "## 次週への行動アイテム",
        "",
        "- [ ] 提案されたテーマ5つから本日のコンテンツを選定",
        "- [ ] 投稿時間を朝7:00 に統一（現在、投稿タイミングが不規則）",
        "- [ ] X への同時投稿で拡散を強化",
        "- [ ] 日曜夜に本分析を自動実行し、翌週テーマを AI が提案",
        "",
    ]

    return "\n".join(lines)


def save_report(report: str) -> str:
    """レポートを保存。"""

    os.makedirs(REPORT_DIR, exist_ok=True)

    today = datetime.now(JST).date()
    filename = f"{today.isoformat()}_weekly_analysis.md"
    filepath = os.path.join(REPORT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    return filepath


def main():
    claude_mode = "--claude" in sys.argv

    print("[info] note パフォーマンス分析を開始...")

    # データ読み込み
    try:
        data = load_note_screenshot_data()
        print(f"[ok] データ読み込み完了: {len(data['articles'])} 件の記事")
    except Exception as e:
        print(f"[error] データ読み込み失敗: {e}")
        sys.exit(1)

    # 分析
    if claude_mode:
        print("[info] Claude で最適化提案を生成中...")
        analysis = analyze_with_claude(data)
        if not analysis:
            print("[error] 分析生成に失敗")
            sys.exit(1)
    else:
        analysis = "(Claude による分析は --claude フラグで有効化)"

    # レポート生成
    report = generate_report(data, analysis)

    # ファイル保存
    filepath = save_report(report)
    print(f"[ok] レポートを保存: {filepath}")

    # コンソールにも出力
    print("")
    print(report)


if __name__ == "__main__":
    main()
