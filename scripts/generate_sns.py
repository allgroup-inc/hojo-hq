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
# 2026-09-11: 構成変更(自己紹介系カード廃止・制度5枠=沖縄2/金額2/締切1+shokei/30秒診断/予告)。
#             フック別の書き出しを含む全8投稿を同3観点で確認。
GATE_CHECKED = "2026-09-11"
# UTM付き(ヒロメさんのUTM運用: instagram/social/launch)。プロフィールリンクにも同URLを使用
SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=instagram&utm_medium=social&utm_campaign=launch"

# 選定しきい値
PROMOTE_MIN_DAYS = 30   # 通常投稿はこれ以上先の締切のみ
SOON_MAX_DAYS = 7       # これ未満は「予告」カードに回す

# hashtag-strategyスキル準拠: Instagramの5タグ上限を守り、話題ごとにセットを
# ローテーションする(固定1ブロックの使い回しはNG)。ニッチ・ミドルタグを優先。
HASHTAG_SETS = {
    "seido": "#沖縄補助金 #沖縄助成金 #沖縄経営者 #中小企業支援 #沖縄企業のミカタ",
    # カモフラージュ設計(2026-08-11)により承継系ハッシュタグは使わない(2026-08-29 小柳さん指摘で是正)
    "shokei": "#沖縄企業のミカタ #沖縄補助金 #助成金 #沖縄の中小企業 #経営",
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


def amount_short(v):
    """画像の「数字ドン」用の短い金額表示。未設定(0/None)はNone(=型を変える)。"""
    if not v:
        return None
    if v >= 100_000_000:
        oku = f"{v / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"最大 {oku}億円"
    if v >= 10000:
        return f"最大 {v // 10000:,}万円"
    return f"最大 {v:,}円"


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


def write_post(n, slug, role, img_title, img_sub, img_number, caption, source, badge="",
               template="brand", rows=None):
    fname = f"{n:02d}_{slug}.md"
    path = os.path.join(OUT_DIR, fname)
    badge_line = f"\n- バッジ: {badge}" if badge else ""
    # 画像テンプレ(IG広告画像_マスタープロンプト.mdの型を自動生成に実装。2026-09-11
    # 小柳さん指示「毎回同じに見える」対応): generate_images.py が描き分ける
    tpl_line = f"\n- テンプレ: {template}"
    rows_lines = "".join(f"\n- 行{i}: {r}" for i, r in enumerate(rows or [], start=1))
    hashtags = HASHTAG_SETS.get(slug, DEFAULT_HASHTAGS)
    body = f"""# 投稿{n}｜{role}

## 画像に載せる文言
- タイトル: {img_title}
- サブ: {img_sub}
- 数字: {img_number}{badge_line}{tpl_line}{rows_lines}

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

    # 通常投稿の母集団: 締切30日以上先
    promote = [it for it in dated if dleft(it) >= PROMOTE_MIN_DAYS]

    # 興味フック優先の選定(2026-09-11 小柳さん指示「見た人が『使えるかも』『これ何?』と
    # 思うものを。サービス自体の説明には誰も興味がない」):
    # 締切近い順だけだとニッチな全国制度が上位を占めるため、
    # ①沖縄限定(自分ごと度が最も高い) ②金額が大きい(数字のフック) ③締切が近い
    # の順で枠を取る。同じ制度・同名の重複は除く。
    non_shokei = [it for it in promote if it.get("tag") != "shokei"]
    picked = []
    _seen = set()

    def _norm_name(s):
        """名寄せ用: 年度・補正・括弧書きを落とす(「令和6年度補正 ◯◯事業」と
        「令和7年度補正 ◯◯事業(建設機械)」が同じフィードに並ぶのを防ぐ)。"""
        import re as _re
        s = _re.sub(r"令和[0-9０-９]+年度|平成[0-9０-９]+年度|補正予算|補正|"
                    r"（[^）]*）|\([^)]*\)|【[^】]*】|［[^］]*］|[\s　]", "", s or "")
        return s

    def _take(pool, n, hook):
        got = 0
        for it in pool:
            key = _norm_name(it["name"])
            if key in _seen:
                continue
            _seen.add(key)
            picked.append((it, hook))
            got += 1
            if got >= n:
                return

    # 金額枠は「1社あたりの上限」として現実的な帯(100万〜10億円)に絞る。
    # 数十億〜数百億は制度全体の予算枠であることが多く、フックに使うと誇大に見える
    AMT_MIN, AMT_MAX = 1_000_000, 1_000_000_000
    # 沖縄枠: tag=okinawa は全国制度も混ざるため使わない(2026-09-11 検証で確認)。
    # 「対象は沖縄県内」とキャプションで言い切る以上、target_area が正確に沖縄県のみの制度に限る
    def _okinawa_only(it):
        return " ".join((it.get("target_area") or "").split()) == "沖縄県"

    _take(sorted([it for it in non_shokei if _okinawa_only(it)],
                 key=lambda x: x["deadline"]), 2, "okinawa")
    _take(sorted([it for it in non_shokei
                  if AMT_MIN <= (it.get("max_amount") or 0) <= AMT_MAX],
                 key=lambda x: -x["max_amount"]), 2, "amount")
    _take(sorted(non_shokei, key=lambda x: x["deadline"]), 1, "deadline")

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

    # サービス自己紹介系のカード(ローンチ告知/なぜ無料/使い方/締切アラート)は
    # 2026-09-11 小柳さん指示で廃止: 「聞いたことのないサービスの説明には誰も興味がない。
    # 制度データそのもので『使えるかも』『これ何?』と思わせる」。以降は制度が主役。

    # 1〜5) 制度投稿。書き出しは選定フックに合わせる(番号順で決定的=再生成しても同じ)
    hook_openers = {
        "okinawa": [
            "沖縄の事業者向けの募集が出ています。全国枠ではなく、沖縄向けです。",
            "対象は沖縄県内の事業者。うちも当てはまるかも、と思ったら締切だけ先に控えてください。",
        ],
        "amount": [
            "{amt}の制度が、いま募集中です。",
            "上限は{amt}。この規模の募集は、そう多くありません。",
        ],
        "deadline": [
            "📣 締切まで残り{dl}日。いまなら準備が間に合います。",
        ],
    }
    seido_closers = [
        "詳細・申請は原文で👇",
        "公募要領の原文はこちら👇",
        "申請できるかは原文で確認を👇",
        "対象になるかは、原文の要件欄でわかります👇",
        "まずは原文をざっと見てみてください👇",
    ]
    # 見た目テンプレの週次ローテーション(2026-09-11 小柳さん指示「毎回同じに見える」対応):
    # IG広告画像_マスタープロンプト.mdの型のうち、事実データだけで自動生成できる4型を
    # 制度投稿で順繰りにする。週番号でずらすため、同じ制度でも週が変われば見た目が変わる。
    # 決定論的(同じ日は同じ出力)なので、承認ゲートのプレビューと実投稿はずれない。
    week = today.isocalendar()[1]
    # フックごとの型(週番号で入れ替え): 沖縄枠は対象地域が見える型、金額枠は数字が主役の型
    hook_templates = {
        "okinawa": ["facts", "news"],
        "amount": ["number", "brand"],
        "deadline": ["news", "brand"],
    }

    def facts_rows(it2, dl2):
        # 金額未設定の「要確認」行は画像では弱いので載せず、対象地域・実施主体で埋める
        rows = [f"締切　{it2['deadline']}(残り{dl2}日)" if dl2 is not None else f"締切　{it2['deadline']}"]
        if it2.get("max_amount"):
            rows.append(amount_text(it2.get("max_amount")))
        area = " ".join((it2.get("target_area") or "").split())
        if area and len(area) <= 20:
            rows.append(f"対象地域　{area}")
        if len(rows) < 3:
            rows.append(f"実施主体　{it2.get('issuer') or '要確認'}")
        return rows[:3]

    def sub_line(it2):
        """number型以外のサブ行: 金額があれば金額、なければ実施主体(「要確認」を画像に出さない)"""
        if it2.get("max_amount"):
            return amount_text(it2["max_amount"])
        return f"実施主体：{it2.get('issuer') or '原文参照'}"

    hook_count = {}
    for i, (it, hook) in enumerate(picked, start=1):
        dl = days_left(it, today)
        num = f"締切まで残り{dl}日" if dl is not None else "募集中"
        k = hook_count.get(hook, 0)
        hook_count[hook] = k + 1
        opener = hook_openers[hook][k % len(hook_openers[hook])].format(
            dl=dl, amt=amount_short(it.get("max_amount")) or "")
        # 沖縄枠は書き出しで対象を言い切っているため、汎用の一文は重ねない
        body_line = ("" if hook == "okinawa"
                     else "沖縄の事業者も、要件に合えば申請できます。準備の時間も取りやすい制度です。\n")
        cap = (
            opener + "\n"
            f"【募集中】{it['name']}\n"
            f"🗓 {deadline_line(it, today)}\n"
            f"💰 {amount_text(it.get('max_amount'))}\n"
            f"🏝 実施主体：{it.get('issuer') or '要確認'}\n"
            f"{body_line}"
            f"{seido_closers[(i - 1) % len(seido_closers)]}\n{it['source_url']}\n"
            f"{DISCLAIMER}"
        )
        template = hook_templates[hook][(week + i) % len(hook_templates[hook])]
        # 数字ドン型は金額が主役。上限額が未設定の制度では成立しないため事実カード型に切替
        if template == "number" and not amount_short(it.get("max_amount")):
            template = "facts"
        # 画像は制度名が主役(2026-08-24 小柳さん指摘「何の補助金かが分かりにくい」対応):
        # タイトル=制度名の全文(描画側が3行以内に自動折返し・縮小)。
        # number型のみ数字=短い金額、それ以外は数字=残り日数
        made.append(write_post(
            i, "seido", f"制度紹介({i}/5・{hook}枠・締切30日以上先)",
            img_title=shorten_name(it["name"], limit=60),
            img_sub=(num if template == "number" else sub_line(it)),
            img_number=(amount_short(it.get("max_amount")) if template == "number" else num),
            caption=cap,
            source=it["source_url"],
            badge=("沖縄の事業者向け" if hook == "okinawa" else "いま募集中"),
            template=template,
            rows=facts_rows(it, dl) if template == "facts" else None,
        ))

    # 5) 事業承継(shokei)
    if shokei:
        dl = days_left(shokei, today)
        num = f"締切まで残り{dl}日" if dl is not None else "募集中"
        # カモフラージュ設計(2026-08-11): 承継・M&Aの直接訴求はしない。
        # この枠も他の制度紹介と同じ扱い(制度名は事実としてそのまま。2026-08-29 小柳さん指摘で是正)
        cap = (
            f"【募集中】{shokei['name']}\n"
            f"🗓 {deadline_line(shokei, today)}\n"
            f"💰 {amount_text(shokei.get('max_amount'))}\n"
            "沖縄の事業者も、要件に合えば申請できます。\n"
            f"制度の詳細・申請は原文で👇\n{shokei['source_url']}\n"
            f"{DISCLAIMER}"
        )
        tpl5 = ["brand", "news"][week % 2]
        made.append(write_post(
            6, "shokei", "制度紹介(30日以上先・6件目)",
            img_title=shorten_name(shokei["name"], limit=60),
            img_sub=amount_text(shokei.get("max_amount")),
            img_number=num,
            caption=cap,
            source=shokei["source_url"],
            badge="いま募集中",
            template=tpl5,
        ))

    # 7) 30秒診断(唯一残すサービス系カード: 「うちに使える制度あるのかな」という
    #    読者自身の問いから入るため、自己紹介ではなく興味フックとして機能する)
    made.append(write_post(
        7, "cta", "30秒診断・LINE登録",
        img_title=r"うちに使える制度、\nあるのかな。",  # \nは描画側で改行に変換
        img_sub="診断も登録も、無料です。",
        img_number="30秒",
        template="number",
        caption=(
            "「うちに使える制度、あるのかな」。30秒でわかります。\n"
            "沖縄の事業者のための、補助金・助成金ナビ。会社名の入力は不要です🌺\n"
            f"診断も登録も無料です👇\n{SITE_URL}"
        ),
        source=SITE_URL,
    ))

    # 8) 次回公募に備える予告(締切7日未満は今回は狙わず、次に備える)
    if yokoku_item:
        dl = days_left(yokoku_item, today)
        ex = (
            f"例）{yokoku_item['name']}（{deadline_line(yokoku_item, today)}）\n"
            f"参考: {yokoku_item['source_url']}\n"
        )
        made.append(write_post(
            8, "yokoku", "次回公募に備える予告",
            img_title="次の公募に、備える。",
            img_sub="まずはGビズIDプライムの準備から。",
            img_number="今から準備",
            badge="次回公募に備える",
            template="news",
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
