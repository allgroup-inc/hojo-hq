#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沖縄企業のミカタ Instagram 投稿案(週5件)を data/subsidies.json から作る。

仕様: docs/superpowers/specs/2026-09-28-mikata-ig-redesign.md §1(テンプレート1〜3)
計画: docs/superpowers/plans/2026-09-28-mikata-ig-automation.md Task 13
参考: scripts/generate_ig_neta.py(もらいわすれ堂版。制度IDで書き出しを散らす手法)

ここで守ること(絶対ルール1・正確性最優先):
  1. **本文の金額は制度DBの数値欄からだけ作る**(max_amount / ig_before_amount /
     ig_after_amount)。仕様書キャプションの「400万円」「450万円」「1.5億円」は
     例示なのでそのまま書かない。万円で割り切れない額は丸めて断定しない
  2. **本文に日付・補助率を書かない**。補助率はDBに欄が無く、締切は照合前に
     断定になる。締切は画像の早見表の差し込み値と検証メモにだけ持たせる
  3. テンプレート2(県の相談窓口・支援事業)はDB上すべて「要確認」。金額を一切
     書かず、公式ページで締切を確かめるまで publish_blocked=True にする
  4. 締切3層ルール: SNS投稿は残り30日以上のみ。日付の無い締切は判定できない
     ため、テンプレート2(要確認扱い・投稿止め)以外は候補から外す
  5. 直近5週間に投稿した制度(data/ig_posts_history.json)は選ばない
  6. 出荷ゲート(scripts/shipping_gate.py)の禁止表現を出さない。特に承継・M&A系の
     ハッシュタグ(#事業承継 等)は制度名に「承継」があっても付けない
  7. LINE導線は /go/ig/ を経由する(lin.ee を直貼りしない: go-link-discipline)
  8. すべての案は approval_needed=True。月水金の承認ゲートを通るまで投稿しない

使い方:
  python scripts/generate_ig_posts_mikata.py                 # data/ig_posts_mikata_draft.json を書く
  python scripts/generate_ig_posts_mikata.py --dry-run       # 書き出さずに表示
  python scripts/generate_ig_posts_mikata.py --today 2026-10-04 --max-posts 5
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(SCRIPTS_DIR, "..")
DEFAULT_SUBSIDIES = os.path.join(BASE, "data", "subsidies.json")
DEFAULT_HISTORY = os.path.join(BASE, "data", "ig_posts_history.json")
DEFAULT_OUTPUT = os.path.join(BASE, "data", "ig_posts_mikata_draft.json")

JST = dt.timezone(dt.timedelta(hours=9))

MAX_POSTS = 5
SNS_MIN_DAYS = 30          # 締切3層ルール(CLAUDE.md)
HISTORY_WEEKS = 5          # 直近5週間の再掲を避ける

# テンプレートの優先順と、各テンプレートで有効な ig_priority の上限
TEMPLATE_ORDER = ("template1", "template2", "template3")
PRIORITY_MAX = {"template1": 40, "template2": 10, "template3": 5}
# 締切が日付でなくても候補に残すテンプレート(要確認で投稿止めにする)
UNKNOWN_DEADLINE_OK = ("template2",)
OPEN_STATUSES = ("募集中", "要確認")

# LINE導線(QR・プロフィール)。lin.ee 直貼りは出荷ゲートが止める
GO_LINK = "https://allgroup-inc.github.io/hojo-hq/go/ig/"
BRAND_TAG = "#沖縄企業のミカタ"

# 制度名のキーワード → (取り組みの言い方, ハッシュタグ)。先に当たったものを使う
THEMES = (
    ("電動化", "車両の電動化", "#EV導入"),
    ("蓄電", "蓄電池の導入", "#蓄電池"),
    ("水素", "水素の活用", "#水素"),
    ("省CO2", "省CO2の設備投資", "#省CO2"),
    ("省ＣＯ２", "省CO2の設備投資", "#省CO2"),
    ("脱炭素", "脱炭素の設備投資", "#脱炭素"),
    ("二酸化炭素", "脱炭素の設備投資", "#脱炭素"),
    ("再生可能", "再エネ設備の導入", "#再エネ"),
    ("再エネ", "再エネ設備の導入", "#再エネ"),
    ("水力", "発電設備の導入", "#再エネ"),
    ("ディマンドリスポンス", "設備のIoT化", "#IoT"),
    ("IoT", "設備のIoT化", "#IoT"),
    ("ものづくり", "設備投資・新サービス開発", "#ものづくり補助金"),
    ("働き方", "働き方改革の取り組み", "#働き方改革"),
    ("最低賃金", "賃上げと設備投資", "#賃上げ"),
    ("デジタル", "デジタル化", "#DX"),
    ("ＤＸ", "デジタル化", "#DX"),
    ("DX", "デジタル化", "#DX"),
    ("物流", "物流の効率化", "#物流"),
    ("エイジフレンドリー", "職場の安全対策", "#労働安全"),
    ("SDS", "化学物質管理の電子化", "#化学物質管理"),
    ("ＳＤＳ", "化学物質管理の電子化", "#化学物質管理"),
    ("ＰＣＢ", "変圧器の更新", "#省エネ"),
    ("PCB", "変圧器の更新", "#省エネ"),
    ("中山間", "農業経営の改善", "#農業支援"),
    ("転換", "事業転換", "#事業転換"),
    ("相談", "経営の相談", "#経営相談"),
    ("伴走", "経営の相談", "#経営相談"),
)
DEFAULT_THEME = ("設備投資", "#設備投資")

# ハッシュタグに絶対に入れない語(出荷ゲートのカモフラージュ設計と同じ理由)
TAG_BLOCKLIST = ("承継", "M&A", "Ｍ＆Ａ", "後継者")

# ---------------------------------------------------------------- 書き出しの散らし
# 同じ書き出しが1セットに並ぶと定型が透ける(仕様 §6)。制度IDで選ぶ

T1_HOOKS_EXAMPLE = [
    "「{industry}の{theme}、※試算例: {before}かかる場合、補助で実質{after}に。」",
    "「※試算例: {before}の{theme}が、補助を使うと実質{after}。{industry}の場合です。」",
    "「{theme}に{before}。※試算例ですが、補助で実質{after}まで下がります。」",
]
T1_HOOKS_PLAIN = [
    "「{theme}、上限{max}まで補助が出る制度があります。」",
    "「{industry}の{theme}に、上限{max}の補助金があります。」",
    "「『うちには関係ない』と思っていませんか？上限{max}の補助金です。」",
]
T2_HOOKS = [
    "「沖縄県で『{short}』の支援を受けられるって知ってますか？」",
    "「経営の困りごと、沖縄県内で相談できる窓口があります。」",
    "「何から始めればいいか分からない。そんなときの沖縄県の支援です。」",
]
T3_HOOKS = [
    "「{theme}は『大きなリスク』と思ってませんか？最大{max}の補助が出る制度があります。」",
    "「{theme}、ひとりで抱えていませんか？最大{max}まで補助する制度があります。」",
]


def _variant(key, options):
    """制度IDから決める(毎回同じ結果・セット内では散らばる)。"""
    return options[sum(ord(c) for c in (key or "")) % len(options)]


# ---------------------------------------------------------------- 値の整形

def format_yen(yen):
    """円 → 「500万円」「15億円」「1億4310万円」。表せない額は None(断定しない)。"""
    if not isinstance(yen, (int, float)) or isinstance(yen, bool) or yen <= 0:
        return None
    yen = int(yen)
    if yen % 10_000:
        return None
    man = yen // 10_000
    oku, rest = divmod(man, 10_000)
    if oku and rest:
        return f"{oku}億{rest}万円"
    if oku:
        return f"{oku}億円"
    return f"{man}万円"


def clean_name(name):
    """表示用の制度名。全角スペースだけ詰め、文言は変えない。"""
    return re.sub(r"[\s　]+", " ", (name or "")).strip()


def name_in_brackets(name):
    n = clean_name(name)
    return f"「{n}」" if "【" in n else f"【{n}】"


def short_name(name):
    """フック用の短い名前(括弧書き・年度の前置きを外す)。"""
    n = clean_name(name)
    n = re.sub(r"^【[^】]*】", "", n)
    n = re.sub(r"^(令和[0-9０-９]+年度[^ ]*?\s*)", "", n)
    n = re.sub(r"[（(][^）)]*[）)]", "", n)
    return n.strip() or clean_name(name)


def theme_of(name):
    for kw, theme, tag in THEMES:
        if kw in (name or ""):
            return theme, tag
    return DEFAULT_THEME


def area_label(area):
    return "沖縄県の" if (area or "").startswith("沖縄") else "国の"


def parse_deadline(value):
    try:
        return dt.date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def days_to_deadline(item, today):
    d = parse_deadline(item.get("deadline"))
    return (d - today).days if d else None


def _tag(word):
    t = "#" + re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龥ー]", "", word or "")[:14]
    return t if len(t) > 1 else None


def build_hashtags(item, template):
    theme_tag = theme_of(item.get("name"))[1]
    industry = _tag(item.get("ig_example_industry"))
    if template == "template2":
        # 相談窓口に既定の「#設備投資」を付けると内容と食い違う。当たった分野名だけ付ける
        if theme_tag == DEFAULT_THEME[1]:
            theme_tag = None
        tags = [BRAND_TAG, "#沖縄県", "#中小企業", theme_tag, "#経営相談"]
    elif template == "template3":
        tags = [BRAND_TAG, "#補助金", theme_tag, industry, "#沖縄企業"]
    else:
        tags = [BRAND_TAG, "#補助金", theme_tag, industry, "#中小企業支援"]
    out = []
    for t in tags:
        if not t or t in out or any(b in t for b in TAG_BLOCKLIST):
            continue
        out.append(t)
    return out


# ---------------------------------------------------------------- 検査の橋渡し

def _load_forbidden():
    try:
        sys.path.insert(0, SCRIPTS_DIR)
        from shipping_gate import FORBIDDEN  # noqa: WPS433
        return FORBIDDEN
    except Exception:  # 出荷ゲートが読めなくても最低限の禁止は守る
        return ((r"https?://lin\.ee/", "lin.ee 直貼り"),
                (r"#\s*(?:事業承継|沖縄M&A|後継者問題|M&A)\b", "承継・M&A系ハッシュタグ"))


def forbidden_findings(text):
    """出荷ゲートの禁止表現に当たったものを返す(空なら通過)。"""
    out = []
    for pat, why in _load_forbidden():
        m = re.search(pat, text or "")
        if m:
            out.append(f"禁止表現「{m.group(0)}」: {why}")
    return out


def humanizer_findings(name, caption):
    try:
        sys.path.insert(0, SCRIPTS_DIR)
        from check_humanizer import check_one  # noqa: WPS433
    except Exception:
        return []
    return check_one(name, caption)


# ---------------------------------------------------------------- 入力

def load_items(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["items"] if isinstance(data, dict) else data


def _history_entries(data):
    if isinstance(data, dict):
        data = data.get("posts", [])
    return data if isinstance(data, list) else []


def load_historical_post_ids(history_json=DEFAULT_HISTORY, today=None, weeks=HISTORY_WEEKS):
    """直近 weeks 週に投稿した seido_id の集合。

    受け付ける形: ["id", ...] / [{"seido_id", "posted_at"}, ...] / {"posts": [...]}
    日付の無い記録は「最近」とみなす(安全側)。ファイルが無ければ空集合。
    壊れたJSONは黙って空にせず ValueError(重複投稿を黙って許さない)。
    """
    today = today or dt.datetime.now(JST).date()
    if not history_json or not os.path.exists(history_json):
        return set()
    with open(history_json, encoding="utf-8") as f:
        raw = f.read()
    if not raw.strip():
        return set()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"{history_json} を読めません: {e}") from e
    cutoff = today - dt.timedelta(weeks=weeks)
    ids = set()
    for entry in _history_entries(data):
        if isinstance(entry, str):
            ids.add(entry)
            continue
        if not isinstance(entry, dict) or not entry.get("seido_id"):
            continue
        when = parse_deadline(entry.get("posted_at") or entry.get("date")
                              or entry.get("generated_at"))
        if when is None or when > cutoff:
            ids.add(entry["seido_id"])
    return ids


def _verified_ng(item):
    """Task 14 の照合結果で不一致・矛盾が出ているか(未照合は NG にしない)。"""
    v = item.get("verified")
    if not isinstance(v, dict):
        return False
    return bool(v.get("conflict")) or v.get("claude_verified") is False \
        or v.get("gemini_verified") is False


def eligible(item, today, recent_ids):
    """候補に残すなら (True, 残り日数)、外すなら (False, 理由)。"""
    tpl = item.get("ig_template")
    if tpl not in TEMPLATE_ORDER:
        return False, "テンプレート未割当"
    if item.get("ig_exclude"):
        return False, "ig_exclude"
    pri = item.get("ig_priority")
    if not isinstance(pri, int) or not 1 <= pri <= PRIORITY_MAX[tpl]:
        return False, "優先度が範囲外"
    if item.get("status") not in OPEN_STATUSES:
        return False, f"status={item.get('status')}"
    if item.get("id") in recent_ids:
        return False, "直近5週間に投稿済み"
    if _verified_ng(item):
        return False, "照合で不一致"
    days = days_to_deadline(item, today)
    if days is None:
        if tpl not in UNKNOWN_DEADLINE_OK:
            return False, "締切が日付でない(判定不能)"
    elif days < SNS_MIN_DAYS:
        return False, f"締切まで{days}日(30日未満)"
    return True, days


def select(items, today, recent_ids, max_posts):
    picked = []
    for it in items:
        ok, _ = eligible(it, today, recent_ids)
        if ok:
            picked.append(it)
    picked.sort(key=lambda i: (TEMPLATE_ORDER.index(i["ig_template"]), i["ig_priority"], i["id"]))
    seen, out = set(), []
    for it in picked:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        out.append(it)
        if len(out) >= max_posts:
            break
    return out


# ---------------------------------------------------------------- キャプション

def _example_amounts(item):
    """Before/After の試算例。両方がDBにあり Before > After > 0 のときだけ使う。"""
    b, a = format_yen(item.get("ig_before_amount")), format_yen(item.get("ig_after_amount"))
    if b and a and item["ig_before_amount"] > item["ig_after_amount"]:
        return b, a
    return None, None


def caption_template1(item):
    """仕様 §テンプレート1(数字と限定感)。"""
    theme, _ = theme_of(item.get("name"))
    industry = item.get("ig_example_industry") or "中小企業"
    mx = format_yen(item.get("max_amount"))
    before, after = _example_amounts(item)
    key = item.get("id")
    if before:
        hook = _variant(key, T1_HOOKS_EXAMPLE).format(industry=industry, theme=theme,
                                                     before=before, after=after)
    elif mx:
        hook = _variant(key, T1_HOOKS_PLAIN).format(industry=industry, theme=theme, max=mx)
    else:
        hook = f"「{industry}の{theme}に使える補助金があります。」"

    support = f"【上限{mx}】" if mx else "（上限額は公式ページで確認。要確認）"
    lines = [
        "【1行フック】", hook, "",
        "【本文】",
        f"{theme}は「高い」と思ってませんか？",
        f"実は、{area_label(item.get('target_area'))}{name_in_brackets(item.get('name'))}なら{support}で支援されます。",
        "（補助率・対象条件は公式ページで確認してください。要確認）",
    ]
    if before:
        lines.append("（活用例は試算例です。実際の補助額は条件により異なります）")
    lines += [
        "",
        "このカルーセルでは、",
        "✓ 活用イメージ（試算例・業種別）",
        "✓ 補助率・対象条件（公式情報を確認）",
        "✓ 申請スケジュール",
        "",
        "を紹介します。",
        "",
        "「うちの業種でも対象かな?」と思ったら、プロフィールのLINEから無料相談できます。",
    ]
    return lines


def caption_template2(item):
    """仕様 §テンプレート2(トリアージ)。DB上すべて要確認のため金額・日付・無料を書かない。"""
    issuer = clean_name(item.get("issuer")) or "沖縄県の支援機関"
    hook = _variant(item.get("id"), T2_HOOKS).format(short=short_name(item.get("name")))
    return [
        "【1行フック】", hook, "",
        "【本文】",
        "経営の困りごと、どこに相談すればいいか分からない。",
        f"そんな県内の事業者向けに、{issuer}が案内しているのが{name_in_brackets(item.get('name'))}です。",
        "",
        "✓ 沖縄県の事業者が対象（詳しい条件は要確認）",
        "✓ 支援内容・費用・締切は公式ページで確認（要確認）",
        "✓ まずは相談したい、という段階でもOK",
        "",
        "「うちは対象になるのかな？」と思ったら、プロフィールのLINEから相談できます。",
        "",
        "詳細は公式ページで。（リンクはプロフィールのご案内から）",
    ]


def _t3_theme(item):
    return "事業転換" if "転換" in (item.get("name") or "") else "大型の設備投資"


def caption_template3(item):
    """仕様 §テンプレート3(季節キャンペーン)。事業転換でない制度に「事業転換」と書かない。"""
    theme = _t3_theme(item)
    purpose = theme_of(item.get("name"))[0]
    mx = format_yen(item.get("max_amount"))
    if mx:
        hook = _variant(item.get("id"), T3_HOOKS).format(theme=theme, max=mx)
        cap_line = f"✓ 最大{mx}の補助（上限額。要件あり）"
    else:
        hook = f"「{theme}を考えている経営者へ。国の補助金があります。」"
        cap_line = "✓ 補助の上限額は公式ページで確認（要確認）"
    return [
        "【1行フック】", hook, "",
        "【本文】",
        "経営環境が大きく変わる時代。",
        "「今のままじゃ5年後が不安」と感じている経営者へ。",
        "",
        f"{area_label(item.get('target_area'))}{name_in_brackets(item.get('name'))}は、",
        f"✓ {purpose}を支援",
        cap_line,
        "✓ 準備期間は約6ヶ月が目安（一般的な目安）",
        "",
        "このカルーセルでは、",
        f"▶ {theme}のイメージ例（試算例・業種別）",
        "▶ 準備スケジュール（逆算チェックリスト）",
        "▶ 補助率・対象条件の確認ポイント（要確認）",
        "",
        "を紹介します。",
        "",
        "「うちは対象になる？」と迷ったら、プロフィールのLINEで無料相談できます。",
        "",
        f"国が応援する{theme}。締切から逆算して、早めに準備を始めましょう。",
    ]


CAPTION_BUILDERS = {
    "template1": caption_template1,
    "template2": caption_template2,
    "template3": caption_template3,
}


def build_caption(item, hashtags):
    lines = CAPTION_BUILDERS[item["ig_template"]](item)
    lines += ["", "【ハッシュタグ】", " ".join(hashtags)]
    return "\n".join(lines)


# ---------------------------------------------------------------- 画像の差し込み値

def image_placeholders(item):
    tpl = item["ig_template"]
    mx = format_yen(item.get("max_amount"))
    deadline = item.get("deadline")
    if tpl == "template1":
        before, after = _example_amounts(item)
        return {
            "p1_number": mx,
            "p1_industry": item.get("ig_example_industry"),
            "p1_title": clean_name(item.get("name")),
            "p2_industry": item.get("ig_example_industry"),
            "p2_before": before,
            "p2_after": after,
            "p2_note": "試算例" if before else None,
            "p3_industry": None,  # 別業種の試算例はDBに無い。作らない(要作成)
            "p3_before": None,
            "p3_after": None,
            "p4_rate": "要確認",
            "p4_target": item.get("target_area"),
            "p4_deadline": deadline,
            "p4_source_url": item.get("source_url"),
            "cta_url": GO_LINK,
        }
    if tpl == "template2":
        return {
            "title": clean_name(item.get("name")),
            "issuer": clean_name(item.get("issuer")),
            "steps": ["相談", "公式情報の確認", "申込方法の確認"],
            "phone": None,  # 電話番号は照合できていないため載せない(Task 12 決定)
            "qr": GO_LINK,
            "source_url": item.get("source_url"),
            "deadline": "要確認",
        }
    theme = _t3_theme(item)
    before, after = _example_amounts(item)
    return {
        "p1_title": f"{theme}を検討していますか？",
        "p1_amount": f"最大{mx}" if mx else "要確認",
        "p2_p4_examples": None,  # 業種別の事例はDBに無い。実在事例と誤読される書き方をしない
        "p2_industry": item.get("ig_example_industry"),
        "p2_before": before,
        "p2_after": after,
        "p5_checklist": ["6ヶ月前", "3ヶ月前", "1ヶ月前", "申請直前"],
        "p5_deadline": deadline,
        "p6_source_url": item.get("source_url"),
        "p6_qr": GO_LINK,
    }


def verification_notes(item, days):
    notes = []
    mx = format_yen(item.get("max_amount"))
    if item["ig_template"] == "template2":
        notes.append("締切・金額・費用が要確認。公式ページで締切を確かめるまで本番投稿不可(締切3層ルール判定不能)")
    else:
        if mx:
            notes.append(f"上限額 {mx} を原文で確認")
        else:
            notes.append("上限額がDBに無い(要確認)")
        notes.append(f"締切 {item.get('deadline')}(残り{days}日)を原文で確認")
        notes.append("補助率はDBに無い。画像・本文とも「要確認」のまま")
    if _example_amounts(item)[0]:
        notes.append("Before/After は試算例。制度の補助率と矛盾しないか確認")
    elif item["ig_template"] == "template1":
        notes.append("Before/After の試算例が未設定(p2 は空欄)")
    return notes


# ---------------------------------------------------------------- 本体

def build_draft(item, today, generated_at):
    days = days_to_deadline(item, today)
    tags = build_hashtags(item, item["ig_template"])
    caption = build_caption(item, tags)
    problems = forbidden_findings(caption + "\n" + " ".join(tags))
    if problems:
        raise ValueError(f"{item['id']}: 出荷ゲートの禁止表現 {problems}")
    is_t2 = item["ig_template"] == "template2"
    return {
        "seido_id": item["id"],
        "template": item["ig_template"],
        "ig_priority": item["ig_priority"],
        "seido_name": clean_name(item.get("name")),
        "caption": caption,
        "hashtags": tags,
        "ig_before_amount": None if is_t2 else item.get("ig_before_amount"),
        "ig_after_amount": None if is_t2 else item.get("ig_after_amount"),
        "max_amount": None if is_t2 else item.get("max_amount"),
        "deadline": item.get("deadline"),
        "days_to_deadline": days,
        "target_area": item.get("target_area"),
        "source_url": item.get("source_url"),
        "image_placeholders": image_placeholders(item),
        "verification_needed": verification_notes(item, days),
        "publish_blocked": is_t2,
        "approval_needed": True,
        "generated_at": generated_at,
    }


def generate_ig_posts(
    subsidies_json: str = DEFAULT_SUBSIDIES,
    max_posts: int = MAX_POSTS,
    history_json: str = DEFAULT_HISTORY,
    today: dt.date = None,
    output_json: str = None,
) -> list:
    """
    Generate weekly IG draft posts from subsidies.json, ranked by ig_priority.

    template1 > template2 > template3 の順、同じテンプレート内は ig_priority の小さい順。
    output_json を渡したときだけファイルに書く(テストで実データを汚さないため)。
    """
    today = today or dt.datetime.now(JST).date()
    items = load_items(subsidies_json)
    recent = load_historical_post_ids(history_json, today=today)
    chosen = select(items, today, recent, max_posts)
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    drafts = [build_draft(it, today, generated_at) for it in chosen]
    if output_json:
        os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(drafts, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return drafts


def main(argv=None):
    ap = argparse.ArgumentParser(description="沖縄企業のミカタ IG投稿案(週5件)を作る")
    ap.add_argument("--subsidies", default=DEFAULT_SUBSIDIES)
    ap.add_argument("--history", default=DEFAULT_HISTORY)
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    ap.add_argument("--max-posts", type=int, default=MAX_POSTS)
    ap.add_argument("--today", help="YYYY-MM-DD(既定: JSTの今日)")
    ap.add_argument("--dry-run", action="store_true", help="書き出さずに表示だけ")
    args = ap.parse_args(argv)

    today = dt.date.fromisoformat(args.today) if args.today else None
    drafts = generate_ig_posts(
        subsidies_json=args.subsidies,
        max_posts=args.max_posts,
        history_json=args.history,
        today=today,
        output_json=None if args.dry_run else args.output,
    )
    for d in drafts:
        print(f"- [{d['template']} #{d['ig_priority']}] {d['seido_id']} {d['seido_name'][:40]}"
              f"(残り{d['days_to_deadline']}日){' 投稿止め' if d['publish_blocked'] else ''}")
    if args.dry_run:
        print(json.dumps(drafts, ensure_ascii=False, indent=2))
    else:
        print(f"{len(drafts)}件を書き出しました: {os.path.relpath(args.output, BASE)}")
    if len(drafts) < args.max_posts:
        print(f"注意: 候補が{len(drafts)}件しかありません(目標{args.max_posts}件)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
