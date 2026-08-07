#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 週刊「沖縄補助金 定点観測」note記事ジェネレータ
(設計・議事: docs/note自動化設計.md / 2026-07-31 起案)

data/subsidies.json と前回スナップショット(data/note_snapshot.json)の差分から、
noteにそのまま貼れるMarkdown下書きを posts/note/ に全自動生成する。
公開(noteへの貼り付け)は人間が行う — noteに投稿公式APIはなく、
非公式手段の自動投稿は絶対ルール2により行わない。

制約(CLAUDE.md 絶対ルール#1 / 締切3層ルール):
- 制度名を出して紹介するのは「締切30日以上先」のみ
- 30日未満は件数のみ+LINEアラート誘導(「締切の約1か月前から」表現で統一)
- 金額・締切はデータの値をそのまま転記。上限未公表(0/None)は「要確認」
- 総額は 議事_総額ポテンシャル表示.md 準拠(上限1億円以下・公表分のみ・参考値表記+免責)
- AI編集後記(Claude API)は新しい事実・数字の生成禁止。禁止語検査に落ちたら定型文へ

使い方:
  python scripts/generate_note.py            # 生成+スナップショット更新
  python scripts/generate_note.py --dry-run  # 標準出力のみ(ファイル書き込みなし)
  python scripts/generate_note.py --preview  # Actions用: key=value で生成結果を出力
"""
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE, "data", "subsidies.json")
SNAPSHOT_PATH = os.path.join(BASE, "data", "note_snapshot.json")
SPONSORS_PATH = os.path.join(BASE, "data", "note_sponsors.json")
OUT_DIR = os.path.join(BASE, "posts", "note")

SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=note&utm_medium=article&utm_campaign=teiten"

PROMOTE_MIN_DAYS = 30      # 制度名を出して紹介できる最低残日数(締切3層ルール)
AMOUNT_CAP = 100_000_000   # 総額参考値に含める上限(1億円以下 = 中小向けレンジ)
PICK_MAX = 5               # 新着ピックアップの最大件数
GONE_MAX = 10              # 「消えた補助金」の最大件数

# 誇大表現の禁止語(AI編集後記の検査にも使用)
BANNED_WORDS = ("必ず", "絶対", "誰でも")

# 沖縄の経営者に近い順(ピックアップの優先度)
TAG_PRIORITY = {"okinawa": 0, "shokei": 1, "nationwide": 2}

DISCLAIMER = "※要件・締切・金額は必ず原文の公募要領でご確認ください。"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def days_left(deadline: str, today: date):
    """締切までの残日数。パース不能は None(=要確認扱い)。"""
    try:
        d = datetime.strptime(deadline, "%Y-%m-%d").date()
        return (d - today).days
    except (TypeError, ValueError):
        return None


def fmt_amount(v) -> str:
    if not v:
        return "要確認"
    if v >= 100_000_000:
        oku = v / 100_000_000
        return f"{oku:.1f}".rstrip("0").rstrip(".") + "億円"
    if v >= 10_000:
        return f"{v // 10_000:,}万円"
    return f"{v:,}円"


def area_label(item: dict) -> str:
    tag = item.get("tag")
    if tag == "okinawa":
        return "沖縄県"
    if tag == "shokei":
        return "事業承継"
    return "全国"


def pick_items(items, exclude_ids, today):
    """紹介可能(締切30日以上先)な制度を優先度順に選ぶ。"""
    ok = []
    for it in items:
        if it.get("id") in exclude_ids:
            continue
        left = days_left(it.get("deadline"), today)
        if left is None or left < PROMOTE_MIN_DAYS:
            continue
        ok.append((TAG_PRIORITY.get(it.get("tag"), 9), left, it))
    ok.sort(key=lambda t: (t[0], t[1]))
    return [it for _, _, it in ok[:PICK_MAX]]


def potential_sum(items):
    """議事_総額ポテンシャル表示.md 準拠: 上限1億円以下・公表分の合計。"""
    included = [i for i in items if 0 < (i.get("max_amount") or 0) <= AMOUNT_CAP]
    over = sum(1 for i in items if (i.get("max_amount") or 0) > AMOUNT_CAP)
    unknown = sum(1 for i in items if not i.get("max_amount"))
    return sum(i["max_amount"] for i in included), len(included), over, unknown


def ai_column(stats: dict) -> str:
    """AI編集後記。ANTHROPIC_API_KEY があれば Claude、失敗・不合格時は定型文。"""
    fallback = (
        f"今週も{stats['total']}件の制度を静かに見張っていました。"
        "制度は毎週、生まれては締め切られていきます。"
        "「知らなかった」で終わらせないために、来週もここで定点観測を続けます。(AI編集長)"
    )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return fallback
    try:
        import anthropic

        client = anthropic.Anthropic()
        prompt = (
            "あなたは沖縄の中小企業向け補助金情報サイト「沖縄企業のミカタ」のAI編集長です。"
            "週刊記事の締めに載せる「AI編集後記」を、日本語で2〜3文・180字以内で書いてください。\n"
            "条件: 与えた数字以外の事実・数字・制度名を出さない/誇大表現(必ず・絶対・誰でも等)禁止/"
            "専門用語をやさしく翻訳する温かいトーン/署名や見出しは不要。\n"
            f"今週の数字: 掲載{stats['total']}件、新着{stats['new']}件、"
            f"公募終了{stats['gone']}件、締切30日未満{stats['closing']}件。"
        )
        # max_tokensは思考+本文の合計上限のため余裕を持たせ、途中で切れた場合もフォールバック
        resp = client.messages.create(
            model="claude-opus-5",
            max_tokens=2000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason in ("refusal", "max_tokens"):
            return fallback
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = re.sub(r"\s+", "", text)
        if not text or len(text) > 250 or any(w in text for w in BANNED_WORDS):
            return fallback
        return text + "(AI編集長)"
    except Exception as e:
        print(f"[warn] AI編集後記の生成に失敗、定型文を使用: {e}")
        return fallback


def sponsor_section(today):
    """スポンサー枠(収益軸C / docs/収益軸拡張_設計.md)。

    data/note_sponsors.json が active かつ有効な枠がある時だけ差し込む。
    販売開始は小柳さん決裁後のため、初期値(active=false)では何も出ない。
    ステマ規制対応として【PR】表記はここで機械的に付す(手動運用に依存しない)。
    法務ルールは専門家掲載モデル準拠: 定額掲載料(広告)のみ・成果報酬型紹介料なし。
    """
    if not os.path.exists(SPONSORS_PATH):
        return []
    try:
        conf = load_json(SPONSORS_PATH)
    except (ValueError, OSError):
        return []
    if not conf.get("active"):
        return []
    slots = []
    for s in conf.get("slots", []):
        # 例示データの誤掲載防止+弁護士枠禁止(守り部確定ルール)の機械的ガード
        if s.get("_example") or "弁護士" in (s.get("office") or ""):
            print(f"[warn] スポンサー枠をスキップ(例示または弁護士枠): {s.get('office')}")
            continue
        until = s.get("until")
        try:
            if until and datetime.strptime(until, "%Y-%m-%d").date() < today:
                continue
        except ValueError:
            continue
        if s.get("office") and s.get("specialty"):
            slots.append(s)
    if not slots:
        return []
    L = ["## この制度、誰に頼めばいい?【PR】", ""]
    L.append("申請のご相談は、当メディア提携の専門家へ(掲載は定額広告です。紹介手数料はいただいていません)。")
    L.append("")
    for s in slots[:2]:
        line = f"- **{s['office']}**(得意分野: {s['specialty']})"
        if s.get("url"):
            line += f" — {s['url']}"
        L.append(line)
    L.append("")
    return L


def build_article(data, snapshot, today):
    items = data.get("items", [])
    current = {i["id"]: i for i in items if i.get("id")}
    prev = (snapshot or {}).get("items", {})
    first_run = not prev

    new_ids = [i for i in current if i not in prev]
    # DBから消えた=公募終了とは限らない(収集側の取りこぼしの可能性がある)。
    # 断定できるのは「締切日が過去」の場合のみ。締切が未来・不明なのに消えたものは
    # 制度名を出さず件数のみ(要確認扱い)にする(絶対ルール#1・2026-08-01再検証で修正)。
    gone_all = [prev[i] for i in prev if i not in current]
    gone = [
        g for g in gone_all
        if (dl := days_left(g.get("deadline"), today)) is not None and dl < 0
    ][:GONE_MAX]
    vanished_n = len(gone_all) - len(gone)

    closing = sum(
        1 for i in items
        if (dl := days_left(i.get("deadline"), today)) is not None and 0 <= dl < PROMOTE_MIN_DAYS
    )
    okinawa_n = sum(1 for i in items if i.get("tag") == "okinawa")

    if first_run:
        picks = pick_items(items, set(), today)
        pick_title = "注目ピックアップ(現在応募できる制度から)"
    else:
        picks = pick_items([current[i] for i in new_ids], set(), today)
        pick_title = "新着ピックアップ(今週DBに現れた制度)"

    total_amt, inc_n, over_n, unknown_n = potential_sum(items)

    dstr = today.strftime("%Y-%m-%d")
    # 同日再実行は同じvol番号・同じファイル名に上書き(冪等・重複記事防止)
    existing = sorted(glob.glob(os.path.join(OUT_DIR, "*_vol*.md")))
    same_day = [p for p in existing if os.path.basename(p).startswith(dstr)]
    if same_day:
        m = re.search(r"_vol(\d+)\.md$", os.path.basename(same_day[0]))
        vol = int(m.group(1)) if m else len(existing)
    else:
        vol = len(existing) + 1
    wstr = today.strftime("%Y年%m月%d日")

    stats = {"total": len(items), "new": len(new_ids), "gone": len(gone), "closing": closing}

    L = []
    L.append(f"# 週刊 沖縄補助金 定点観測 vol.{vol}({wstr})")
    L.append("")
    if first_run:
        L.append(
            "沖縄の企業が使える補助金・助成金を、AIが毎日巡回して集めているデータベースがあります。"
            "この連載は、そのデータベースの「今週の変化」をAI編集部がそのまま記事にする、"
            "たぶん日本初の補助金定点観測です。今回は記念すべき第1回、まずは現在地から。"
        )
    else:
        L.append(
            "沖縄の企業が使える補助金・助成金データベースの「今週の変化」を、"
            "AI編集部がそのまま記事にする週刊定点観測です。"
        )
    L.append("")
    L.append("## 今週の数字")
    L.append("")
    L.append(f"- 掲載中の制度: **{len(items)}件**(うち沖縄県・市町村の制度 {okinawa_n}件)")
    if not first_run:
        L.append(f"- 今週の新着: **{len(new_ids)}件**")
        L.append(f"- 今週締切を迎えた制度: **{len(gone)}件**")
        if vanished_n:
            L.append(f"- 締切前に掲載終了となった制度: **{vanished_n}件**(公募元の情報を確認中)")
    L.append(f"- 締切まで30日を切った制度: **{closing}件**")
    L.append("")

    L.append(f"## {pick_title}")
    L.append("")
    if picks:
        L.append("いずれも締切まで30日以上あり、いまから準備が間に合う制度です。")
        L.append("")
        for it in picks:
            left = days_left(it.get("deadline"), today)
            L.append(f"### {it.get('name', '(名称不明)')}")
            L.append("")
            L.append(f"- 対象: {area_label(it)} / 締切: {it.get('deadline', '要確認')}(残り{left}日)")
            L.append(f"- 上限額: {fmt_amount(it.get('max_amount'))}")
            L.append(f"- 原文: {it.get('source_url', '')}")
            L.append("")
    else:
        L.append("今週は、締切30日以上の余裕をもってご紹介できる新着はありませんでした。静かな週です。")
        L.append("")

    if not first_run:
        L.append("## 今週消えた補助金")
        L.append("")
        if gone:
            L.append("締切日を迎え、今週データベースから姿を消した制度の記録です。")
            L.append("「知っていれば出せたのに」を減らすことが、この連載の目的です。")
            L.append("")
            for g in gone:
                L.append(f"- {g.get('name', '(名称不明)')}(締切: {g.get('deadline', '不明')})")
            L.append("")
        else:
            L.append("今週、締切を迎えた制度はありませんでした。")
            L.append("")
        if vanished_n:
            L.append(
                f"このほか{vanished_n}件が締切前に掲載終了となりました。"
                "公募元での早期終了か掲載情報の変更かを確認中のため、制度名の記載は控えます。"
            )
            L.append("")

    L.append("## 公募上限額の合計(参考値)")
    L.append("")
    L.append(
        f"掲載中の制度のうち、上限額が公表されている1億円以下(中小向けレンジ)の{inc_n}件を単純合計すると "
        f"**{fmt_amount(total_amt)}** になります(上限額非公表{unknown_n}件・1億円超の大型公募{over_n}件は含めていません)。"
    )
    L.append(
        "※これは公募上限額の理論上の合計であり、受給できる金額や採択を保証するものではありません。"
        "各制度の要件・締切・金額は原文の公募要領でご確認ください。"
    )
    L.append("")

    L.append("## 締切が近い制度はLINEでお知らせしています")
    L.append("")
    L.append(
        f"締切まで30日を切った制度が現在{closing}件あります。"
        "直前のご案内では書類やgBizIDの準備が間に合わないため、この記事では制度名を挙げず、"
        "LINE登録者の方へ**締切の約1か月前から**関心テーマに応じて個別アラートをお届けしています。"
    )
    L.append("")
    L.append(f"👉 無料マッチング診断・LINE登録はこちら: {SITE_URL}")
    L.append("")

    L.extend(sponsor_section(today))

    L.append("## AI編集後記")
    L.append("")
    L.append(ai_column(stats))
    L.append("")
    L.append("---")
    L.append("")
    L.append(
        "この記事は「沖縄企業のミカタ」(運営: ALLGROUP)のAI編集部が制度データベースから自動生成し、"
        "人間スタッフが内容を確認したうえで公開しています。"
    )
    L.append(DISCLAIMER)
    L.append("")
    L.append("#沖縄 #補助金 #助成金 #沖縄経営者 #中小企業 #沖縄企業のミカタ")
    L.append("")

    stem = f"{dstr}_vol{vol}"
    stats["vol"] = vol
    return stem, "\n".join(L), current, gone, stats


def main():
    dry_run = "--dry-run" in sys.argv
    preview = "--preview" in sys.argv
    today = datetime.now(JST).date()

    data = load_json(DATA_PATH)
    snapshot = load_json(SNAPSHOT_PATH) if os.path.exists(SNAPSHOT_PATH) else None

    stem, article, current, gone, stats = build_article(data, snapshot, today)

    if dry_run:
        print(article)
        return

    # X告知パック(v3様式・A数字/B学び/C問い)。冒頭の削除ブロックに同梱し、
    # ナナコさんはコピペのみで運用できるようにする(hook-writer原則: 内容に誠実なhookのみ)
    if stats["gone"]:
        b_line = (f"B(学び): 補助金は「現れた」ニュースはあっても「消えた」記録はどこにもありません。"
                  f"今週締切を迎えて消えた{stats['gone']}件を、名前つきで記録しました")
        c_line = (f"C(問い): 御社が使えたかもしれない制度、今週{stats['gone']}件が静かに締切を迎えました。"
                  f"来週の分は、間に合ううちに")
    else:
        b_line = ("B(学び): 補助金は毎週入れ替わります。今週は1件も消えませんでした。"
                  "そういう週があることも、毎日見ているからわかる記録です")
        c_line = (f"C(問い): いま公募中の制度のうち、締切まで30日を切っているのは{stats['closing']}件。"
                  f"御社に関係する1件が入っていないと言い切れますか")
    xpack = "\n".join([
        "▼▼ 公開前にこのブロックを削除 ▼▼",
        "[週刊定点観測(無料)。公開前チェックは運用規程3-1の5項目]",
        "",
        "📣 X告知文パック(公開後、記事URLをリプ欄に。1日1本まで)",
        f"A(数字): 【今週の沖縄の補助金】掲載{stats['total']}件/新着{stats['new']}件/"
        f"締切30日切り{stats['closing']}件。AIが毎日見張る週刊定点観測 vol.{stats['vol']}(無料)",
        b_line,
        c_line,
        "▲▲ ここまで削除 ▲▲",
        "",
    ])

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{stem}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xpack + article)

    # 次回の差分検出用スナップショット(消滅コーナーで使う項目だけ保持)
    snap = {
        "generated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "items": {
            i: {"name": v.get("name"), "deadline": v.get("deadline")}
            for i, v in current.items()
        },
    }
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    # 締切到来で消えた制度を「消えたもの図鑑」(メンバー連載)用に蓄積する
    dstr = today.strftime("%Y-%m-%d")
    archive_path = os.path.join(BASE, "data", "gone_archive.json")
    archive = load_json(archive_path) if os.path.exists(archive_path) else {"items": []}
    seen = {(a.get("name"), a.get("deadline")) for a in archive["items"]}
    for g in gone:
        key = (g.get("name"), g.get("deadline"))
        if key not in seen:
            archive["items"].append(
                {"name": g.get("name"), "deadline": g.get("deadline"), "recorded": dstr}
            )
            seen.add(key)
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=1)

    if preview:
        title = article.splitlines()[0].lstrip("# ")
        # X告知文(コピー用・1行)。URLは公開後に人間が追記する(運用規程準拠・誇大表現なし)
        xpost = (
            f"【今週の沖縄の補助金】掲載{stats['total']}件/新着{stats['new']}件/"
            f"締切30日切り{stats['closing']}件。今週も静かに入れ替わりました。"
            f"AIが毎日見張る週刊定点観測 vol.{stats['vol']} を公開しました→ "
            f"#沖縄 #補助金 #助成金"
        )
        print(f"stem={stem}")
        print(f"title={title}")
        print(f"xpost={xpost}")
    else:
        print(f"[ok] {out_path} を生成しました(掲載{len(current)}件)")


if __name__ == "__main__":
    main()
