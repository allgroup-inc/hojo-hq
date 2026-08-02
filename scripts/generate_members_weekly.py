#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — メンバーシップ週刊「AI編集長週報」ジェネレータ
(運営計画: docs/note収益化_運営計画.md / 2026-08-01 小柳さん承認)

月額メンバーシップ向けの限定記事を週1本、3コーナー束ねで自動生成する。
  ①今週の編集部の数字(経営週報) — リポジトリから観測できる実数+手入力KPI
  ②消えたもの図鑑              — data/gone_archive.json の新規収蔵分
  ③AI三人会議                  — 読者/運営のお題を三役(スイシン/ウタガイ/ベッカイ)が討論
公開(noteメンバーシップ記事への貼り付け)は人間が行う。

制約(CLAUDE.md 絶対ルール#1・#3):
- 数字はリポジトリ観測値と data/note_kpi.json の手入力値のみ。未入力は「集計中」と
  正直に表示し、推測値を作らない
- 三人会議は一般論の討論に限定。個別の法律・税務・申請可否の判断はしない旨を
  フッターで機械的に付す(資格業務の線引き)。生成失敗・検査不合格時はお題を持ち越す

使い方:
  python scripts/generate_members_weekly.py            # 生成+お題消化
  python scripts/generate_members_weekly.py --dry-run  # 標準出力のみ(お題も消化しない)
  python scripts/generate_members_weekly.py --preview  # Actions用: key=value 出力
"""
import glob
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from generate_note import (  # noqa: E402
    BANNED_WORDS, BASE, DATA_PATH, JST, PROMOTE_MIN_DAYS,
    days_left, load_json,
)

OUT_DIR = os.path.join(BASE, "posts", "note", "members")
KPI_PATH = os.path.join(BASE, "data", "note_kpi.json")
TOPICS_PATH = os.path.join(BASE, "data", "sankai_topics.json")
ARCHIVE_PATH = os.path.join(BASE, "data", "gone_archive.json")

ZUKAN_MAX = 8  # 図鑑の週間新規収蔵の最大表示数

SANKAI_DISCLAIMER = (
    "※AI三人会議は一般論としての議論です。個別の制度の申請可否・法律・税務のご判断は、"
    "提携の専門家(社労士・行政書士・税理士)へご相談ください。"
)


def kpi_value(kpi, key, unit=""):
    v = (kpi or {}).get(key)
    return f"{v:,}{unit}" if isinstance(v, (int, float)) else "集計中"


def ai_sankai(topic: str):
    """お題を三役で討論。失敗・検査不合格時は None(お題は持ち越し)。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic

        client = anthropic.Anthropic()
        prompt = (
            "あなたは沖縄の中小企業向け補助金メディア「沖縄企業のミカタ」のAI編集部です。"
            "編集部には視点の異なる3役がいます: スイシン(推進・可能性を語る)、"
            "ウタガイ(懐疑・必ず反対や落とし穴を指摘する)、ベッカイ(前提を疑い別の見方を出す)。\n"
            f"次のお題について3役で討論してください。\nお題: {topic}\n"
            "形式(この4見出しを必ず使う):\n"
            "スイシン: (2〜3文)\nウタガイ: (2〜3文・必ず反対意見)\nベッカイ: (2〜3文)\n"
            "編集長まとめ: (2文)\n"
            "条件: 全体で700字以内/具体的な制度名・金額・統計数字を出さない(一般論に限定)/"
            "誇大表現(必ず・絶対・誰でも等)禁止/個別の法律・税務・申請可否の判断をしない/"
            "経営者に語りかけるやさしい日本語。"
        )
        resp = client.messages.create(
            model="claude-opus-5",
            max_tokens=3000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason in ("refusal", "max_tokens"):
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text or len(text) > 1200 or any(w in text for w in BANNED_WORDS):
            return None
        for label in ("スイシン", "ウタガイ", "ベッカイ", "編集長まとめ"):
            if label not in text:
                return None
        return text
    except Exception as e:
        print(f"[warn] 三人会議の生成に失敗、お題を持ち越し: {e}")
        return None


def build(today, dry_run):
    data = load_json(DATA_PATH)
    items = data.get("items", [])
    kpi = load_json(KPI_PATH) if os.path.exists(KPI_PATH) else {}
    archive = load_json(ARCHIVE_PATH) if os.path.exists(ARCHIVE_PATH) else {"items": []}
    topics = load_json(TOPICS_PATH) if os.path.exists(TOPICS_PATH) else {"queue": []}

    dstr = today.strftime("%Y-%m-%d")
    wstr = today.strftime("%Y年%m月%d日")
    closing = sum(
        1 for i in items
        if (dl := days_left(i.get("deadline"), today)) is not None and 0 <= dl < PROMOTE_MIN_DAYS
    )
    tanpatsu_n = len(glob.glob(os.path.join(BASE, "posts", "note", "tanpatsu", "*.md")))
    weekly_files = glob.glob(os.path.join(BASE, "posts", "note", "*_vol*.md"))
    published_n = 0
    for p in weekly_files:
        with open(p, encoding="utf-8") as f:
            if "published:" in f.read(2000):
                published_n += 1

    # 図鑑: 直近7日以内に収蔵されたもの
    recent = [
        a for a in archive.get("items", [])
        if a.get("recorded") and (today - datetime.strptime(a["recorded"], "%Y-%m-%d").date()).days <= 7
    ]

    L = []
    L.append(f"# 【メンバー限定】AI編集長週報 {wstr}号")
    L.append("")
    L.append(
        "このメディアの運営数字・裏側・議論を、AI編集長が毎週そのまま報告する連載です。"
        "きれいな話だけでなく、未達の数字もそのまま載せます。"
    )
    L.append("")

    L.append("## 1. 今週の編集部の数字")
    L.append("")
    L.append(f"- データベース掲載中の制度: **{len(items)}件**(うち締切30日未満 {closing}件)")
    L.append(f"- 図鑑への今週の新規収蔵(締切到来): **{len(recent)}件**(累計{len(archive.get('items', []))}件)")
    L.append(f"- 単発記事の在庫: **{tanpatsu_n}本** / 週刊定点観測の公開済み: **{published_n}本**")
    L.append(f"- noteフォロワー: **{kpi_value(kpi, 'followers', '人')}** / メンバー: **{kpi_value(kpi, 'members', '人')}** / 今月のnote売上: **{kpi_value(kpi, 'monthly_sales_yen', '円')}**")
    if not isinstance(kpi.get("followers"), (int, float)):
        L.append("")
        L.append("(「集計中」の項目は、noteの管理画面の数字を人間スタッフが入力すると翌週から表示されます。未入力のまま推測値を出すことはしません)")
    L.append("")

    L.append("## 2. 消えたもの図鑑 — 今週の新規収蔵")
    L.append("")
    if recent:
        L.append("締切日を迎え、データベースから静かに姿を消した制度たちの記録です。")
        L.append("")
        for a in recent[:ZUKAN_MAX]:
            L.append(f"- **{a.get('name', '(名称不明)')}**(締切: {a.get('deadline', '不明')}/収蔵日: {a.get('recorded')})")
        if len(recent) > ZUKAN_MAX:
            L.append(f"- ほか{len(recent) - ZUKAN_MAX}件")
    else:
        L.append("今週の新規収蔵はありませんでした。制度が消えなかった週は、それ自体が良い週です。")
    L.append("")

    L.append("## 3. AI三人会議")
    L.append("")
    open_topics = [t for t in topics.get("queue", []) if t.get("status") == "open"]
    discussion = None
    picked = None
    if open_topics:
        picked = open_topics[0]
        L.append(f"今週のお題: **{picked.get('topic')}**")
        L.append("")
        discussion = ai_sankai(picked.get("topic", ""))
        if discussion:
            L.append(discussion)
        else:
            L.append("(今週は編集会議が紛糾したため、このお題は来週に持ち越します)")
    else:
        L.append("お題の在庫が切れています。メンバーのみなさまからの相談・お題をお待ちしています。")
    L.append("")
    L.append(SANKAI_DISCLAIMER)
    L.append("")
    L.append("---")
    L.append("")
    L.append(
        "この記事は「沖縄企業のミカタ」AI編集部が自動生成し、人間スタッフが確認のうえ"
        "メンバー限定で公開しています。数字はデータベース観測値と運営の実数のみです。"
    )
    L.append("")

    # お題の消化(生成成功時のみ・dry-runでは消化しない)
    if picked and discussion and not dry_run:
        picked["status"] = "answered"
        picked["answered_on"] = dstr
        with open(TOPICS_PATH, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=1)

    return f"{dstr}_members", "\n".join(L)


def main():
    dry_run = "--dry-run" in sys.argv
    preview = "--preview" in sys.argv
    today = datetime.now(JST).date()

    stem, article = build(today, dry_run)

    if dry_run:
        print(article)
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{stem}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(article)

    if preview:
        # KPI鮮度チェック(運用規程: 未入力・8日以上放置でリマインド)
        kpi = load_json(KPI_PATH) if os.path.exists(KPI_PATH) else {}
        reminder = ""
        upd = kpi.get("updated")
        try:
            stale = (today - datetime.strptime(upd, "%Y-%m-%d").date()).days if upd else None
        except (TypeError, ValueError):
            stale = None
        if upd is None or stale is None:
            reminder = "⚠️ noteのKPIが未入力です。管理画面の数字(フォロワー/メンバー/今月売上)をチャットで教えてください"
        elif stale >= 8:
            reminder = f"⚠️ noteのKPIが{stale}日間更新されていません。最新の数字をチャットで教えてください"
        print(f"stem={stem}")
        print(f"title={article.splitlines()[0].lstrip('# ')}")
        print(f"kpireminder={reminder}")
    else:
        print(f"[ok] {out_path} を生成しました")


if __name__ == "__main__":
    main()
