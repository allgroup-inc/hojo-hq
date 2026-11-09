#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沖縄企業のミカタ SNS 投稿の「選び方」と「割り振り」(2026-11-09 第1段階・見本用)。

今の定期投稿(post_social.py)は、決まった7枠を日付で順番に回すだけで、同じ型の画像が
2〜3週間ごとに戻ってくる。ここでは次のように選ぶ(この段階では、どこからも呼ばれない)。

制度の選び方(上から順に、通らなければ候補から外す。外した理由は必ず残す):
  1. 正確さ: 制度名・原文URL・締切日がそろっている/募集中/締切まで30日以上(締切3層ルール)
  2. 地域: 対象地域が沖縄県か全国。名前や対象地域に沖縄県外の地名だけがあるものは外す
  3. 関係の薄い制度を外す(EXCLUDE_WORDS。2026-11-09 の提案どおり)
  4. 優先: ①沖縄県・市町村の制度 ②小さな会社の定番(STAPLE_WORDS) ③それ以外
金額が無い制度は外さない(画像には「金額は原文で確認」と書く。推測で書かない)。

投稿の型:
  A        … 制度の比較・一覧(白)
  OKINAWA  … 沖縄県・市町村の制度だけ(白+オレンジ)
  B        … 豆知識・Q&A(オレンジ。文章は data/sns_evergreen.json)
  C        … 準備・チェックリスト(紺。文章は data/sns_evergreen.json)
曜日: 月=沖縄限定(候補が無ければ A)/水=B/金=C と A を交互。
同じ型を2回続けない。同じ制度・同じ文章は28日間出さない。
B・C の文章は「確認済み」だけを使う(見本のときだけ allow_drafts=True で下書きも使う)。
"""
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 2026-09-28 の IG 投稿案の仕組みと、除外の印・投稿の記録を共有する(同じデータを読むスクリプトは
# 除外のフラグを共有する: CLAUDE.md 再発防止メモ 2026-09-20)。写さずに、あちらの関数をそのまま使う。
import generate_ig_posts_mikata as _IG  # noqa: E402

MIN_DAYS_LEFT = 30          # 締切3層ルール: SNS は残り30日以上だけ
REPEAT_GAP_DAYS = 28        # 同じ制度・同じ文章を出さない日数
PROGRAMS_PER_POST = 3       # 一覧に並べる制度の数(最大)

OKINAWA_MUNICIPALITIES = (
    "那覇市", "宜野湾市", "石垣市", "浦添市", "名護市", "糸満市", "沖縄市", "豊見城市",
    "うるま市", "宮古島市", "南城市", "国頭村", "大宜味村", "東村", "今帰仁村", "本部町",
    "恩納村", "宜野座村", "金武町", "伊江村", "読谷村", "嘉手納町", "北谷町", "北中城村",
    "中城村", "西原町", "与那原町", "南風原町", "渡嘉敷村", "座間味村", "粟国村", "渡名喜村",
    "南大東村", "北大東村", "伊平屋村", "伊是名村", "久米島町", "八重瀬町", "多良間村",
    "竹富町", "与那国町",
)
PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県",
    "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県",
    "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府",
    "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県",
    "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県",
    "鹿児島県", "沖縄県",
)
# 名前に出てくる沖縄県外の地名(札が無い書き方: 「京都市企業立地…」「東京港…」など)。
# 都道府県名から「都・府・県」を外した形と、地方の名前。「北海道」はそのまま。
_OTHER_PLACE_STEMS = tuple(
    p[:-1] if p[-1] in "都府県" else p for p in PREFECTURES if p != "沖縄県"
) + ("関東", "東北", "近畿", "北陸", "東海", "四国", "いわき市")
# 2026-11-09 提案: 沖縄の小さな会社には関係が薄い制度
EXCLUDE_WORDS = ("鉄鋼", "鉱山", "鉱害", "トンネル", "鉄道", "難病")
# 小さな会社の定番(優先②)
STAPLE_WORDS = ("持続化", "ものづくり", "IT導入", "省力化", "事業承継", "創業", "雇用",
                "人材", "賃上げ", "販路", "省エネ", "小規模")
# 名前の先頭にある「年度」「省庁」の札(意味を変えずに外せるものだけ)
_PREFIX_RE = re.compile(
    r"^(?:\s*(?:【[^】]*(?:年度|省|庁)】|令和\s*[0-9０-９元]+\s*年度(?:\s*[（(]補正[）)])?[_\s　]*|補正予算[\s　]*))+")
# 同じ制度の「回」(20次締切・第4回受付 など)。一覧に同じ制度を並べないためのまとめ方
_ROUND_RE = re.compile(r"[（(【\[]?\s*(?:第\s*)?[0-9０-９一二三四五六七八九十]+\s*(?:次|回)[^）)】\]]*[）)】\]]?")
# 【倉敷市】 (◯◯町) のような地名の札
_PLACE_TAG_RE = re.compile(r"[【\[（(]([^】\]）)]{1,10}?(?:都|道|府|県|市|区|町|村))[】\]）)]")

TYPE_A, TYPE_OKINAWA, TYPE_B, TYPE_C = "A", "OKINAWA", "B", "C"
TYPE_LABEL = {TYPE_A: "比較・一覧", TYPE_OKINAWA: "沖縄限定", TYPE_B: "豆知識・Q&A",
              TYPE_C: "準備・チェックリスト"}


def parse_deadline(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def is_okinawa(item):
    """沖縄県・県内市町村の制度か。

    データの tag="okinawa" だけでは判断しない(全国の制度に付いていることがある)。
    対象地域が「全国」を含まず沖縄を名指ししているか、実施主体・名前が沖縄のものだけ。
    """
    area = str(item.get("target_area") or "")
    if "全国" in area:
        return False
    text = f"{area} {item.get('issuer', '')} {item.get('name', '')}"
    return "沖縄" in text or any(m in text for m in OKINAWA_MUNICIPALITIES)


def _outside_okinawa(item):
    """沖縄県外の地名だけが書かれていれば、その理由を返す(沖縄・全国なら None)。"""
    area = str(item.get("target_area") or "")
    if area and "沖縄" not in area and "全国" not in area:
        named = [p for p in PREFECTURES if p in area]
        if named:
            return f"対象地域が沖縄県外({named[0]})"
    for place in _PLACE_TAG_RE.findall(str(item.get("name") or "")):
        if "沖縄" in place or place in OKINAWA_MUNICIPALITIES or place == "全国" \
                or place.endswith(("内閣府", "政府")):  # 府で終わる役所の名前は地名ではない
            continue
        return f"名前に沖縄県外の地名({place})"
    if not is_okinawa(item):
        name = str(item.get("name") or "")
        for stem in _OTHER_PLACE_STEMS:
            if stem in name:
                return f"名前に沖縄県外の地名({stem})"
    return None


def screen(item, today):
    """候補にできるか。(True, None) か (False, 外した理由)。"""
    name = str(item.get("name") or "").strip()
    if not name:
        return False, "制度名が無い"
    if not re.match(r"^https?://", str(item.get("source_url") or "")):
        return False, "原文のURLが無い"
    dl = parse_deadline(item.get("deadline"))
    if not dl:
        return False, "締切日が読めない"
    if item.get("status") != "募集中":
        return False, f"募集中ではない({item.get('status') or '状態なし'})"
    left = (dl - today).days
    if left < MIN_DAYS_LEFT:
        return False, f"締切まで{MIN_DAYS_LEFT}日未満(残り{left}日)"
    if item.get("ig_exclude"):
        return False, "IG投稿から外す印(ig_exclude)が付いている"
    if _IG._verified_ng(item):
        return False, "原文の照合で不一致・矛盾が出ている"
    why = _outside_okinawa(item)
    if why:
        return False, why
    hit = [w for w in EXCLUDE_WORDS if w in name]
    if hit:
        return False, f"沖縄の小さな会社には関係が薄い({hit[0]})"
    if "901名以上" in str(item.get("employees") or ""):
        return False, "大企業向け(従業員901名以上)"
    return True, None


def priority(item):
    """小さいほど優先。1=沖縄県・市町村 2=小さな会社の定番 3=それ以外。"""
    if is_okinawa(item):
        return 1
    if any(w in str(item.get("name") or "") for w in STAPLE_WORDS):
        return 2
    return 3


def short_name(name):
    """先頭の「年度」「省庁」の札だけを外す(意味が変わる部分は残す)。"""
    s = _PREFIX_RE.sub("", str(name or "")).strip(" 　_")
    return s or str(name or "").strip()


def program_key(item):
    """同じ制度の別の回(20次・21次 など)を1つにまとめる鍵。"""
    return re.sub(r"[\s　_]+", "", _ROUND_RE.sub("", short_name(item.get("name"))))


def deadline_text(item, today):
    dl = parse_deadline(item.get("deadline"))
    left = (dl - today).days
    if left > 180:
        return f"{dl.year}年{dl.month}月締切"
    return f"締切 {dl.month}月{dl.day}日(あと{left}日)"


def amount_text(item):
    v = item.get("max_amount")
    try:
        v = int(v or 0)
    except (TypeError, ValueError):
        v = 0
    if v <= 0:
        return "金額は原文で確認"
    if v >= 100_000_000 and v % 100_000_000 == 0:
        return f"上限 {v // 100_000_000:,}億円"
    if v >= 10_000:
        man = v / 10_000
        return f"上限 {int(man):,}万円" if man == int(man) else f"上限 {man:,.1f}万円"
    return f"上限 {v:,}円"


def issuer_text(item):
    """実施主体。空・制度名の一部・お知らせの見出しのようなものは出さない。"""
    iss = str(item.get("issuer") or "").strip()
    name = str(item.get("name") or "")
    if not iss or iss in name or name[:12] in iss or "補助金" in iss or "事業" in iss:
        return ""
    return iss


def screen_all(items, today):
    ok, rejected = [], []
    for it in items:
        good, why = screen(it, today)
        (ok.append(it) if good else rejected.append((it, why)))
    return ok, rejected


def post_dates(start, count):
    """start 以降の月・水・金を count 日分。"""
    out, d = [], start
    while len(out) < count:
        if d.weekday() in (0, 2, 4):
            out.append(d)
        d += timedelta(days=1)
    return out


def desired_type(day, friday_index):
    if day.weekday() == 0:
        return TYPE_OKINAWA
    if day.weekday() == 2:
        return TYPE_B
    return TYPE_C if friday_index % 2 == 0 else TYPE_A


def _recent(history, key, day):
    """REPEAT_GAP_DAYS 日以内(その日ちょうども含む)に出していれば True。"""
    last = history.get(key)
    return last is not None and (day - last).days <= REPEAT_GAP_DAYS


def _pick_programs(cands, day, history, only_okinawa):
    # 締切3層ルールは「投稿する日」から数える(月の後半の投稿で残り30日を切らないように)
    pool = [c for c in cands
            if not _recent(history, "p:" + program_key(c), day)
            and (parse_deadline(c["deadline"]) - day).days >= MIN_DAYS_LEFT]
    if only_okinawa:
        pool = [c for c in pool if is_okinawa(c)]
    else:
        # 一覧の見出しは「小さな会社でも使いやすい」。それに当たらない制度(優先③)は載せない
        pool = [c for c in pool if priority(c) <= 2]
    pool.sort(key=lambda c: (priority(c), parse_deadline(c["deadline"]), str(c.get("id"))))
    picked, keys = [], set()
    for c in pool:                       # 同じ制度の別の回は1つだけ(締切が近い回)
        k = program_key(c)
        if k in keys:
            continue
        keys.add(k)
        picked.append(c)
        if len(picked) == PROGRAMS_PER_POST:
            break
    return picked


def _pick_text(evergreen, kind, day, history, allow_drafts):
    for e in evergreen:
        if e.get("type") != kind:
            continue
        if e.get("status") != "確認済み" and not allow_drafts:
            continue
        if _recent(history, "t:" + e["id"], day):
            continue
        return e
    return None


def load_recent_ids(path=None, today=None):
    """2026-09-28 の仕組みの投稿の記録(data/ig_posts_history.json)から、直近5週間に投稿した制度ID。

    ファイルが無ければ空。壊れていれば ValueError(黙って重複投稿を許さない。あちらと同じ扱い)。
    """
    return _IG.load_historical_post_ids(path or _IG.DEFAULT_HISTORY, today=today)


def plan(items, evergreen, start, count=13, history=None, allow_drafts=False, recent_ids=None):
    """count 回分の投稿予定を作る。

    戻り値: {"posts": [...], "rejected": [(item, 理由)], "skipped": [(日付, 理由)]}
    posts の1件: {"date", "type", "programs"(制度の一覧) または "text"(文章の台帳の1件)}
    history: {"p:<制度の鍵(program_key)>" or "t:<文章id>": 最後に出した日}。渡したものは書き換えない。
    recent_ids: 直近5週間に投稿した制度ID(load_recent_ids の戻り値)。これらは候補から外す。
    """
    history = dict(history or {})
    recent_ids = set(recent_ids or ())
    cands, rejected = [], []
    for it in items:
        if str(it.get("id")) in recent_ids:
            rejected.append((it, "直近5週間に投稿済み(ig_posts_history.json)"))
        else:
            cands.append(it)
    cands, more = screen_all(cands, start)
    rejected += more
    posts, skipped, prev, fridays = [], [], None, 0
    for day in post_dates(start, count):
        want = desired_type(day, fridays)
        if day.weekday() == 4:
            fridays += 1
        order = [want] + [t for t in (TYPE_A, TYPE_C, TYPE_B, TYPE_OKINAWA) if t != want]
        chosen = None
        for kind in order:
            if kind == prev:
                continue
            if kind in (TYPE_A, TYPE_OKINAWA):
                progs = _pick_programs(cands, day, history, kind == TYPE_OKINAWA)
                # 1件でも出す(1件のときは大きく1つを紹介する形になる)
                if progs:
                    chosen = {"date": day, "type": kind, "programs": progs}
                    break
            else:
                text = _pick_text(evergreen, kind, day, history, allow_drafts)
                if text:
                    chosen = {"date": day, "type": kind, "text": text}
                    break
        if not chosen:
            skipped.append((day, "出せる候補が無い(同じ型の連続・28日以内の再登場を避けた結果)"))
            continue
        for p in chosen.get("programs", []):
            history["p:" + program_key(p)] = day
        if "text" in chosen:
            history["t:" + chosen["text"]["id"]] = day
        posts.append(chosen)
        prev = chosen["type"]
    return {"posts": posts, "rejected": rejected, "skipped": skipped}
