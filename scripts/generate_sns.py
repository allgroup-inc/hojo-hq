#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq SNS部(ヒロメさん) — ローンチ投稿ジェネレータ
data/subsidies.json から制度を抽出し、Instagram等のローンチ用に
「キャプション + 画像テキスト(タイトル/サブ/数字)」を posts/launch/ に出力する。

制度選定(2026-07-22 改定):
- 通常投稿は「締切30日以上先」の制度から、締切が近い順に選ぶ
  （直前締切の制度を推してしまい、読者が間に合わない事故を防ぐ）
- 「締切7日未満」の制度は "次回公募に備える予告"(gBizID取得の呼びかけ)カード1枚に回す

制約(CLAUDE.md 絶対ルール#1 準拠):
- 誇大表現は使わない(「必ず」「絶対」「誰でももらえる」等は使用しない)
- 金額・締切は data(=原文) の値をそのまま表示。上限が未設定(0/None)は「要確認」
- 各制度投稿には必ず出典URLを記載
"""
import glob
import json
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "subsidies.json")
OUT_DIR = os.path.join(BASE_DIR, "..", "posts", "launch")
SITE_URL = "https://allgroup-inc.github.io/hojo-hq/"

# 選定しきい値
PROMOTE_MIN_DAYS = 30   # 通常投稿はこれ以上先の締切のみ
SOON_MAX_DAYS = 7       # これ未満は「予告」カードに回す

HASHTAGS = "#沖縄 #補助金 #助成金 #沖縄経営者 #事業承継 #沖縄企業のミカタ"
DISCLAIMER = "※要件・締切・金額は必ず原文の公募要領でご確認ください。"


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def amount_text(v):
    """金額を原文通りに表示。未設定(0/None)は要確認。億・万で読みやすく。"""
    if not v:
        return "上限額は要確認（原文でご確認ください）"
    if v >= 100_000_000:
        oku = f"{v / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"上限 {oku}億円（{v:,}円）"
    if v >= 10000:
        return f"上限 {v // 10000:,}万円（{v:,}円）"
    return f"上限 {v:,}円"


def deadline_line(it, today):
    dl = it["deadline"]
    d = parse_date(dl)
    if not d:
        return f"締切：{dl}"
    days = (d - today).days
    if days > 0:
        return f"締切：{dl}（残り{days}日）"
    if days == 0:
        return f"締切：{dl}（本日締切）"
    return f"締切：{dl}"


def days_left(it, today):
    d = parse_date(it["deadline"])
    return (d - today).days if d else None


def write_post(n, slug, role, img_title, img_sub, img_number, caption, source, badge=""):
    fname = f"{n:02d}_{slug}.md"
    path = os.path.join(OUT_DIR, fname)
    badge_line = f"\n- バッジ: {badge}" if badge else ""
    body = f"""# 投稿{n}｜{role}

## 画像に載せる文言
- タイトル: {img_title}
- サブ: {img_sub}
- 数字: {img_number}{badge_line}

## キャプション
{caption}

{HASHTAGS}

## 出典
{source}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return fname


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    count = data["count"]
    today = datetime.now(JST).date()

    dated = [it for it in items if parse_date(it.get("deadline"))]
    dated.sort(key=lambda it: it["deadline"])

    def dleft(it):
        return (parse_date(it["deadline"]) - today).days

    # 通常投稿: 締切30日以上先を近い順に
    promote = [it for it in dated if dleft(it) >= PROMOTE_MIN_DAYS]
    seido3 = [it for it in promote if it.get("tag") != "shokei"][:3]
    shokei_pool = [it for it in promote if it.get("tag") == "shokei"]
    if not shokei_pool:  # 30日以上のshokeiが無ければ近い順で代替
        shokei_pool = [it for it in dated if it.get("tag") == "shokei"]
    shokei = shokei_pool[0] if shokei_pool else None

    # 予告カード: 締切7日未満のうち最短のものを例に
    soon = [it for it in dated if dleft(it) < SOON_MAX_DAYS]
    yokoku_item = soon[0] if soon else None

    # 出力ディレクトリを再生成(古い番号ファイルを一掃)
    os.makedirs(OUT_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(OUT_DIR, "[0-9][0-9]_*.md")):
        os.remove(old)

    made = []

    # 1) ローンチ告知
    made.append(write_post(
        1, "launch", "ローンチ告知",
        img_title="沖縄企業のミカタ、公開しました",
        img_sub="補助金・助成金を、毎日ぜんぶ。",
        img_number=f"掲載 {count}件",
        caption=(
            "🌺 沖縄の事業者向けに、国・県・関係機関の補助金・助成金情報を"
            "まとめて毎日更新する無料サイト「沖縄企業のミカタ」を公開しました。\n\n"
            "「知らなかった」で機会を逃さないために。\n"
            "📌 気になる制度は、締切7日前にLINEでお知らせします。\n"
            f"まずは無料のLINE登録から👇\n{SITE_URL}"
        ),
        source=SITE_URL,
    ))

    # 2〜4) 締切30日以上先の制度(近い順)
    for i, it in enumerate(seido3, start=2):
        dl = days_left(it, today)
        num = f"締切まで残り{dl}日" if dl is not None else "募集中"
        cap = (
            f"📣【募集中】{it['name']}\n"
            f"🗓 {deadline_line(it, today)}\n"
            f"💰 {amount_text(it.get('max_amount'))}\n"
            f"🏝 実施主体：{it.get('issuer') or '要確認'}\n"
            "沖縄の事業者も、要件に合えば申請できます。準備の時間も取りやすい制度です。\n"
            f"詳細・申請は原文で👇\n{it['source_url']}\n"
            f"{DISCLAIMER}"
        )
        made.append(write_post(
            i, "seido", f"締切が近い制度({i-1}/3・30日以上先)",
            img_title="いま募集中の補助金",
            img_sub=it["name"][:26],
            img_number=num,
            caption=cap,
            source=it["source_url"],
        ))

    # 5) 事業承継(shokei)
    if shokei:
        dl = days_left(shokei, today)
        num = f"締切まで残り{dl}日" if dl is not None else "募集中"
        cap = (
            f"🤝【事業承継・M&A】{shokei['name']}\n"
            f"🗓 {deadline_line(shokei, today)}\n"
            f"💰 {amount_text(shokei.get('max_amount'))}\n"
            "後継者・M&Aのお悩みは、GLOWの専門チームにもおつなぎできます。\n"
            f"制度の詳細・申請は原文で👇\n{shokei['source_url']}\n"
            f"{DISCLAIMER}"
        )
        made.append(write_post(
            5, "shokei", "事業承継・M&A",
            img_title="事業承継・M&Aを考えるなら",
            img_sub=shokei["name"][:26],
            img_number=num,
            caption=cap,
            source=shokei["source_url"],
        ))

    # 6) なぜ無料か
    made.append(write_post(
        6, "why_free", "なぜ無料か",
        img_title="なぜ、無料なのか。",
        img_sub="先に、全部話します。",
        img_number="利用料 ¥0",
        caption=(
            "💡「なぜ無料？」とよく聞かれます。\n"
            "運営費は、対応いただける専門家様の掲載料や、ご希望の方への経営相談でまかないます。"
            "登録企業様から利用料をいただくことはありません。\n"
            "だから毎日、情報を全部ひらけます。"
        ),
        source=SITE_URL,
    ))

    # 7) 使い方(3ステップ)
    made.append(write_post(
        7, "how", "使い方",
        img_title="使い方は、3ステップ。",
        img_sub="探すのは、私たちの仕事。",
        img_number="3ステップ",
        caption=(
            "🔎 ① 簡単な診断で条件を選ぶ\n"
            "📋 ② あなたの会社が使えるかもしれない制度を表示\n"
            "📲 ③ LINE登録で締切アラートを受け取る\n"
            "気になる制度を見逃さないための、かんたんな流れです。"
        ),
        source=SITE_URL,
    ))

    # 8) 締切7日前アラート
    made.append(write_post(
        8, "deadline_alert", "締切アラート特典",
        img_title="締切7日前に、お知らせします。",
        img_sub="「気づけなかった」をなくす。",
        img_number="締切7日前",
        caption=(
            "⏰ 補助金・助成金は、締切を過ぎると申請できません。\n"
            "LINE登録で、気になる制度の締切7日前にリマインドをお届けします。（無料）\n"
            "準備の時間を、少しでも多く。"
        ),
        source=SITE_URL,
    ))

    # 9) まとめ / LINE登録CTA
    made.append(write_post(
        9, "cta", "まとめ・LINE登録",
        img_title="まずは、LINE登録から。",
        img_sub="沖縄企業のミカタ",
        img_number=f"掲載 {count}件",
        caption=(
            "🌺 沖縄の事業者のための、補助金・助成金ナビ。\n"
            "いま使える制度が見つかるかもしれません。\n"
            f"まずは無料のLINE登録から👇\n{SITE_URL}"
        ),
        source=SITE_URL,
    ))

    # 10) 次回公募に備える予告(締切7日未満は今回は狙わず、次に備える)
    if yokoku_item:
        dl = days_left(yokoku_item, today)
        ex = (
            f"例）{yokoku_item['name']}（{deadline_line(yokoku_item, today)}）\n"
            f"参考: {yokoku_item['source_url']}\n"
        )
        made.append(write_post(
            10, "yokoku", "次回公募に備える予告",
            img_title="次の公募に、備える。",
            img_sub="まずは gBizID プライムの取得から。",
            img_number="今から準備",
            badge="次回公募に備える",
            caption=(
                "⏳ 締切が目前の制度は、いま慌てて申請すると要件を満たせないことも。\n"
                "次の公募に確実に間に合わせるために、まずは電子申請に必須の"
                "【gBizIDプライム】を取得しておきましょう。発行に2〜3週間かかることがあります。\n"
                f"{ex}"
                "今回が難しくても、備えておけば次のチャンスをつかめます。\n"
                f"制度一覧はこちら👇\n{SITE_URL}\n"
                f"{DISCLAIMER}"
            ),
            source=yokoku_item["source_url"],
        ))

    print(f"[ok] {len(made)} 投稿を posts/launch/ に出力（掲載 {count}件・基準日 {today}）")
    print(f"     通常投稿は締切{PROMOTE_MIN_DAYS}日以上先／予告カードは締切{SOON_MAX_DAYS}日未満から抽出")
    for m in made:
        print("  -", m)


if __name__ == "__main__":
    main()
