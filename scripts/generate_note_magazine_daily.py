#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — note マガジン毎日自動生成・投稿スクリプト(完全自動化)

目標: 月30万円の収益達成
手段: 毎日朝7時に高エンゲージメント記事を自動生成・自動投稿

コンテンツ戦略(3層):
  L1: 集客記事(8割)- 「〜前に知っておきたい」系 / ビュー13・スキ8の再現
  L2: インサイト(15%) - 業界分析・失敗事例
  L3: 有料販売(5%) - B2B白書・会員限定

実行: python generate_note_magazine_daily.py
     python generate_note_magazine_daily.py --post  # 自動投稿
     python generate_note_magazine_daily.py --analyze # 分析ループ
"""

import anthropic
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(os.path.dirname(BASE), "posts", "note_magazine")

CONTENT_THEMES = [
    {
        "type": "L1-gather",  # 集客記事
        "title_template": "{}の前に知っておきたい、{}",
        "topics": [
            ("助成金をもらう", "税務申告のリスク", "経営・税務"),
            ("フリーランスが単価を決める", "相場より重要な判断基準", "独立起業"),
            ("起業家が最初にやるべき", "資金確保より先にやること", "創業支援"),
            ("補助金の採択率を上げる", "企業の「本気度」の見せ方", "営業企画"),
            ("個人事業主が防ぐべき", "経理ルール・納税ミス5選", "経営・税務"),
            ("地方だから不利は本当か", "沖縄起業家が知らない有利条件", "地方創業"),
            ("法人化するなら知っておきたい", "損益分岐点・タイミング判断", "決算・会計"),
            ("補助金の返納を避ける", "要件変更・不採択時のリスク", "法務・コンプライ"),
        ]
    },
    {
        "type": "L2-insight",  # インサイト
        "title_template": "noteマガジン自動運営で売上0円だった1か月の真実 — {}",
        "topics": [
            ("AIより必要だった『人間の判断基準』", "失敗から学ぶ"),
            ("補助金は『現れた』ニュースはあっても『消えた』記録はない", "定点観測の価値"),
            ("沖縄×本州の補助金制度差をデータで見えた構造", "地域比較分析"),
        ]
    },
    {
        "type": "L3-premium",  # 有料販売
        "title_template": "[会員限定] {}",
        "topics": [
            ("2026年度沖縄補助金マップ＆活用戦略ガイド", "B2B白書"),
            ("沖縄中小企業の資金調達パターン辞典", "会員レポート"),
        ]
    }
]

BANNED_PHRASES = ("必ず", "絶対", "誰でも", "確実に稼")


def generate_article_with_claude(theme_config: dict, day_index: int) -> dict:
    """Claude API で高エンゲージメント記事を生成。"""

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # テーマを循環させる
    topic_list = theme_config["topics"]
    topic_idx = day_index % len(topic_list)
    topic = topic_list[topic_idx]

    if isinstance(topic, tuple):
        title_prefix = topic[0]
        subtitle = topic[1] if len(topic) > 1 else ""
        category = topic[2] if len(topic) > 2 else ""
    else:
        title_prefix = topic
        subtitle = ""
        category = ""

    title = theme_config["title_template"].format(title_prefix, subtitle) if subtitle else theme_config["title_template"].format(title_prefix)

    content_type = theme_config["type"]

    # コンテンツタイプ別プロンプト
    if "gather" in content_type:
        prompt = f"""
あなたは沖縄の中小企業・フリーランス向け情報メディアのAI編集です。
以下のテーマで、高エンゲージメント(スキ率40%以上)の記事を書いてください。

【テーマ】{title}

【要件】
- 1000〜1500字
- 「{title}」という疑問・困りに対して、読者が「へえ、そうなんだ」と思える視点
- 具体例・実例を最低3つ含む
- 末尾に「詳しくは LINE登録で個別相談」への導線
- 禁止語(必ず・絶対・誰でも・確実に稼)を使わない
- 見出し3〜4個
- 専門用語は括弧で補説

【スタイル】「家計の見直しやさん」と同じく、専門用語をやさしく翻訳する温かいトーン

本文のみを出力(見出しはなし)。
"""
    elif "insight" in content_type:
        prompt = f"""
あなたはnoteマガジン編集長です。失敗事例から学んだ本当の話を書いてください。

【テーマ】{title}

【要件】
- 1200〜1800字
- 実績・データに基づいた「反省」「学び」
- 「AIだけでは駄目だった理由」「人間の判断が要る場面」を具体的に
- 禁止語(必ず・絶対・誰でも)を使わない
- 見出し4〜5個
- 最後に「次のマガジン号では〇〇を検証します」と予告

本文のみを出力。
"""
    else:  # premium
        prompt = f"""
あなたはB2B向けレポート編集です。企業の参考になる白書を書いてください。

【テーマ】{title}

【要件】
- 2000字程度
- 統計・データを多用(ただし創作禁止、一般知識のみ)
- 実用的なチェックリスト・判断基準を1つ
- 「会員限定」を強調
- 禁止語(必ず・絶対)を使わない

本文のみを出力。
"""

    try:
        message = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=3000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        body = message.content[0].text.strip()

        # 禁止語チェック
        for phrase in BANNED_PHRASES:
            if phrase in body:
                print(f"[warn] 禁止語 '{phrase}' が検出されたため、フォールバックテキストを使用")
                body = f"(記事生成失敗のため、本日の記事は明日に延期します)"
                break

        return {
            "title": title,
            "body": body,
            "category": category,
            "type": content_type,
            "generated_at": datetime.now(JST).isoformat()
        }

    except Exception as e:
        print(f"[error] Claude API エラー: {e}")
        return None


def build_markdown(article: dict) -> str:
    """記事を Markdown に変換。"""

    md_lines = [
        f"# {article['title']}",
        "",
        f"_更新: {datetime.now(JST).strftime('%Y年%m月%d日 %H:%M')}_",
        "",
        article["body"],
        "",
        "---",
        "",
        "📱 この記事の続きと限定コンテンツは、LINE登録者向けに毎日配信中。",
        "[無料マッチング診断・LINE登録はこちら](https://allgroup-inc.github.io/hojo-hq/?utm_source=note&utm_medium=article)",
        "",
        f"#沖縄 #補助金 #助成金 #{article['category'].replace('・', ' #') if article['category'] else '中小企業'}",
        ""
    ]

    return "\n".join(md_lines)


def save_article(article: dict, day_index: int) -> str:
    """記事をファイルに保存。"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today = datetime.now(JST).date()
    filename = f"{today.isoformat()}_vol{day_index}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    markdown = build_markdown(article)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    return filepath


def publish_to_note(article_path: str) -> bool:
    """note への自動投稿。現在は draft 生成のみ。

    環境変数 NOTE_PUBLISH_ENABLED=true かつ NOTE_API_TOKEN が設定されている場合のみ実行。
    """

    if not os.environ.get("NOTE_PUBLISH_ENABLED"):
        print(f"[info] note 投稿は無効です。記事ドラフト: {article_path}")
        return False

    # 実装: Power Automate / Selenium で自動投稿
    # 本実装は別途 scripts/publish_note_via_automation.py に分離
    print(f"[info] note への投稿準備完了: {article_path}")
    return True


def main():
    # コマンドラインオプション
    post_enabled = "--post" in sys.argv
    analyze_mode = "--analyze" in sys.argv

    if analyze_mode:
        print("[info] 分析モード: 実装は analyze_note_performance.py で行う")
        return

    # 本日の記事を生成
    today = datetime.now(JST).date()
    day_num = int(today.strftime("%d"))  # 日付をシードにしてテーマを決定

    # L1 記事を生成（80%の確率）
    if day_num % 10 < 8:
        theme = CONTENT_THEMES[0]  # L1: 集客記事
    elif day_num % 10 < 9:
        theme = CONTENT_THEMES[1]  # L2: インサイト
    else:
        theme = CONTENT_THEMES[2]  # L3: プレミアム

    print(f"[info] {theme['type']} 記事を生成中...")

    article = generate_article_with_claude(theme, day_num)
    if not article:
        print("[error] 記事生成に失敗しました")
        sys.exit(1)

    # ファイル保存
    filepath = save_article(article, day_num)
    print(f"[ok] 記事を保存: {filepath}")

    # 投稿
    if post_enabled:
        publish_to_note(filepath)
    else:
        print(f"[info] --post フラグなしのため、自動投稿はスキップ。手動で投稿してください")


if __name__ == "__main__":
    main()
