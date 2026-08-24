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

import shipping_gate

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "subsidies.json")
OUT_DIR = os.path.join(BASE_DIR, "..", "posts", "launch")

# 出荷ゲート(運用規程1-3)の通過日。**本ファイルのキャプション文面を書き換えたら必ず更新する。**
# 更新せずに放置すると shipping_gate.MAX_AGE_DAYS を超えた時点で自動投稿が止まる(フェイルクローズ)。
# 2026-08-17: 全10投稿を accuracy-check(出典・件数はdata由来)/ deadline-alert(「約1か月前から」で統一)/
#             humanizer(定型句・過剰な絵文字なし)で確認。
GATE_CHECKED = "2026-08-17"
# UTM付き(ヒロメさんのUTM運用: instagram/social/launch)。プロフィールリンクにも同URLを使用
SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=instagram&utm_medium=social&utm_campaign=launch"

# 選定しきい値
PROMOTE_MIN_DAYS = 30   # 通常投稿はこれ以上先の締切のみ
SOON_MAX_DAYS = 7       # これ未満は「予告」カードに回す

# hashtag-strategyスキル準拠: Instagramの5タグ上限を守り、話題ごとにセットを
# ローテーションする(固定1ブロックの使い回しはNG)。ニッチ・ミドルタグを優先。
HASHTAG_SETS = {
    "seido": "#沖縄補助金 #沖縄助成金 #沖縄経営者 #中小企業支援 #沖縄企業のミカタ",
    "shokei": "#事業承継 #沖縄M&A #後継者問題 #沖縄経営者 #沖縄企業のミカタ",
    "yokoku": "#沖縄補助金 #GビズID #中小企業支援 #沖縄経営者 #沖縄企業のミカタ",
    "deadline_alert": "#沖縄補助金 #締切管理 #中小企業支援 #沖縄経営者 #沖縄企業のミカタ",
}
DEFAULT_HASHTAGS = "#沖縄企業のミカタ #沖縄経営者 #沖縄補助金 #沖縄助成金 #中小企業支援"
DISCLAIMER = "※要件・締切・金額は必ず原文の公募要領でご確認ください。"


# 画像に載せる制度名の上限。これを超える場合は意味の切れ目で丸める。
IMG_SUB_LIMIT = 26
# 括弧の対応(開いたまま終わらせないために使う)
_BRACKETS = {"（": "）", "(": ")", "【": "】", "［": "］", "「": "」", "〔": "〕", "《": "》", "〈": "〉"}
# この文字の「直前」で切ると読みやすい(主に開き括弧)
_BREAK_BEFORE = "".join(_BRACKETS.keys())
# この文字の「直後」で切ると読みやすい
_BREAK_AFTER = "、。・／/　 _"
_TRIM = "　 、。・／/_"


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _unclosed_positions(s):
    """閉じられていない開き括弧の位置一覧を返す。"""
    stack = []
    for i, ch in enumerate(s):
        if ch in _BRACKETS:
            stack.append((i, _BRACKETS[ch]))
        elif stack and ch == stack[-1][1]:
            stack.pop()
    return [p for p, _ in stack]


def shorten_name(s, limit=IMG_SUB_LIMIT):
    """画像に載せる制度名を、意味の切れ目で丸める。

    単純な文字数カットだと「…補助金（第2次」のように括弧が開いたまま終わったり、
    文の途中でぶつ切りになる。ここでは区切り文字で切り、省略は「…」で明示する。
    (キャプション側は原文の正式名称をそのまま使うため、この関数は画像専用)
    """
    s = " ".join((s or "").split())
    if len(s) <= limit:
        return s

    # 名称全体が「」や【】で囲まれていて、閉じ括弧が切り詰め範囲の外にある場合は
    # 先頭の括弧を落とす(開いたままの括弧を画像に載せないため)
    if s[0] in _BRACKETS:
        close = s.find(_BRACKETS[s[0]], 1)
        if close < 0 or close >= limit:
            s = s[1:].lstrip(_TRIM)
            if len(s) <= limit:
                return s

    head = s[:limit]
    before = max((head.rfind(c) for c in _BREAK_BEFORE), default=-1)
    after = max((head.rfind(c) for c in _BREAK_AFTER), default=-1)
    cut = max(before, after + 1 if after >= 0 else -1)
    # 切りどころが早すぎる(名称がほとんど残らない)場合は上限で切る
    if cut < limit // 2:
        cut = limit

    out = head[:cut].rstrip(_TRIM)

    # 切り詰めが「新たに」括弧を開きっぱなしにした場合だけ、その手前まで戻す。
    # (元の名称からして閉じ括弧がない場合は、原文どおりを優先してそのまま残す)
    src_unclosed = set(_unclosed_positions(s))
    while out:
        introduced = [p for p in _unclosed_positions(out) if p not in src_unclosed]
        if not introduced:
            break
        pos = min(introduced)
        if pos <= 0:
            out = ""
            break
        out = out[:pos].rstrip(_TRIM)

    if not out:
        out = head.rstrip(_TRIM)
    return out + "…"


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
    hashtags = HASHTAG_SETS.get(slug, DEFAULT_HASHTAGS)
    body = f"""# 投稿{n}｜{role}

## 画像に載せる文言
- タイトル: {img_title}
- サブ: {img_sub}
- 数字: {img_number}{badge_line}

## キャプション
{caption}

{hashtags}

## 出典
{source}

{shipping_gate.render_stamp("scripts/generate_sns.py(SNS部・ヒロメさん)", GATE_CHECKED)}"""
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
        img_title="沖縄企業のミカタ、公開。",
        img_sub="補助金・助成金を、毎日ぜんぶ。",
        img_number=f"掲載 {count}件",
        caption=(
            f"沖縄で今使える補助金・助成金、{count}件。ぜんぶ無料で見られる場所を作りました🌺\n"
            "国・県・関係機関の情報を毎日集めて更新する「沖縄企業のミカタ」です。\n\n"
            "「知らなかった」で機会を逃さないために。\n"
            "📌 気になる制度は、締切の約1か月前からLINEでお知らせします。\n"
            f"まずは無料のLINE登録から👇\n{SITE_URL}"
        ),
        source=SITE_URL,
    ))

    # 2〜4) 締切30日以上先の制度(近い順)
    # 書き出しは3パターンを順繰り(humanizer: 同一文の反復を避ける。番号順で決定的=再生成しても同じ)
    seido_openers = [
        "📣 締切まで残り{dl}日。いまなら準備が間に合います。",
        "締切まで残り{dl}日。書類の準備、ここから始めれば間に合います。",
        "残り{dl}日。この制度、見逃していませんか?",
    ]
    seido_closers = [
        "詳細・申請は原文で👇",
        "公募要領の原文はこちら👇",
        "申請できるかは原文で確認を👇",
    ]
    for i, it in enumerate(seido3, start=2):
        dl = days_left(it, today)
        num = f"締切まで残り{dl}日" if dl is not None else "募集中"
        cap = (
            seido_openers[(i - 2) % len(seido_openers)].format(dl=dl) + "\n"
            f"【募集中】{it['name']}\n"
            f"🗓 {deadline_line(it, today)}\n"
            f"💰 {amount_text(it.get('max_amount'))}\n"
            f"🏝 実施主体：{it.get('issuer') or '要確認'}\n"
            "沖縄の事業者も、要件に合えば申請できます。準備の時間も取りやすい制度です。\n"
            f"{seido_closers[(i - 2) % len(seido_closers)]}\n{it['source_url']}\n"
            f"{DISCLAIMER}"
        )
        # 画像は制度名が主役(2026-08-24 小柳さん指摘「何の補助金かが分かりにくい」対応):
        # タイトル=制度名の全文(描画側が3行以内に自動折返し・縮小)、
        # サブ=金額(何がもらえるかの実利)、「いま募集中」は右上バッジへ
        made.append(write_post(
            i, "seido", f"締切が近い制度({i-1}/3・30日以上先)",
            img_title=shorten_name(it["name"], limit=60),
            img_sub=amount_text(it.get("max_amount")),
            img_number=num,
            caption=cap,
            source=it["source_url"],
            badge="いま募集中",
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
        # こちらも制度名を主役に(テーマ名は右上バッジへ移す)
        made.append(write_post(
            5, "shokei", "事業承継・M&A",
            img_title=shorten_name(shokei["name"], limit=60),
            img_sub=amount_text(shokei.get("max_amount")),
            img_number=num,
            caption=cap,
            source=shokei["source_url"],
            badge="事業承継・M&A",
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
            "補助金探しに、夜の時間を使わなくてよくなります。\n"
            "使い方はかんたん。市町村と業種を選ぶだけの30秒診断で、"
            "御社が使えそうな制度が出てきます。\n"
            "あとはLINEに登録しておけば、気になる制度の締切を"
            "約1か月前からお知らせします📲\n"
            "探すのは、私たちの仕事です。"
        ),
        source=SITE_URL,
    ))

    # 8) 締切アラート(締切3層ルール: LINE個別アラートは残り7〜29日の窓で出す。
    #    「7日前」は書類・gBizIDの準備が間に合わないため使わない)
    made.append(write_post(
        8, "deadline_alert", "締切アラート特典",
        img_title="LINEでお知らせ。",
        img_sub="間に合う時期に、お伝えします。",
        img_number="締切1か月前",
        caption=(
            "補助金の「知った時にはもう遅い」は、だいたい締切の1か月前に決まります。\n"
            "しかも申請には事業計画書や、国の電子申請で使うGビズIDの準備が要ることも。"
            "締切の直前に知っても、間に合わないことがあります。\n"
            "だからLINE登録で、気になる制度の締切の約1か月前からお知らせします。（無料）\n"
            "「知っていれば間に合った」を、なくすために。"
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
            "「うちに使える制度、あるのかな」。30秒でわかります。\n"
            "沖縄の事業者のための、補助金・助成金ナビ。会社名の入力は不要です🌺\n"
            f"診断も登録も無料です👇\n{SITE_URL}"
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
            img_sub="まずはGビズIDプライムの準備から。",
            img_number="今から準備",
            badge="次回公募に備える",
            caption=(
                "⏳ 締切が目前の制度は、いま慌てて申請すると要件を満たせないことも。\n"
                "次の公募に備えて、国の電子申請(jGrants)で使う【GビズIDプライム】を"
                "用意しておきましょう。マイナンバーカードとスマホがあれば、"
                "オンライン申請なら24時間365日、速やかに発行されます"
                "（書類の郵送申請は審査に最大1か月）。\n"
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
