#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq 収集部(シュウくん) — 自治体ソース収集
沖縄県・関係機関の公式サイトから、jGrants に載らない地域独自の補助金・助成金を
収集し data/subsidies.json に「追加マージ」する。fetch_jgrants.py の後に実行する。

遵法・安全設計(CLAUDE.md 絶対ルール#2 / docs/守り部審査記録.md 準拠):
- robots.txt を urllib.robotparser で必ず確認し、Disallow のURLは取得しない
- 明示的 User-Agent(連絡先付き)+ リクエスト間 REQUEST_DELAY 秒のレート制限
- 本文は <main> 要素にスコープを限定し、サイドバー/フッターの他制度リンクを誤取得しない
- 保持するのは 制度名・締切・実施主体・原文URL のみ(本文の転載はしない)
- 締切・金額が本文から確実に取れない場合は断定せず「要確認」(絶対ルール#1)
- 取得失敗時は既存 subsidies.json を壊さない(追加分が0件になるだけ)
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subsidies.json")

UA = "hojo-hq-bot/1.0 (+https://allgroup-inc.github.io/hojo-hq; contact: bot@en-life.co.jp)"
REQUEST_DELAY = 1.5  # 秒。自治体サーバへの配慮
DETAIL_LIMIT = 60    # 1ソースあたり詳細取得の上限(暴走防止)

# ── ソース定義(守り部審査記録.md で承認済みのもののみ)──────────────────
SOURCES = [
    {
        "key": "okinawa_pref_sangyo",
        "label": "沖縄県(産業・公募補助金)",
        "listing": "https://www.pref.okinawa.lg.jp/shigoto/keizai/1009879/1010143/index.html",
        "link_re": re.compile(r'href="([^"]*?/shigoto/keizai/1009879/1010143/(?!index\.html)[^"]+\.html)"'),
        "tag": "okinawa",
        # 本文<main>あり → 詳細を取得して締切・終了を判定
        "fetch_detail": True,
    },
    {
        "key": "okinawa_ric",
        "label": "沖縄県産業振興公社",
        "listing": "https://okinawa-ric.jp/service/subsidy.html",
        # 制度ページ /service/*.html のみ(nav/広告/セミナーは除外)
        "link_re": re.compile(r'href="(https?://okinawa-ric\.jp/service/(?!index)[\w./-]+\.html)"'),
        "deny_basename": {"seminar.html", "ads.html", "subsidy.html"},
        "tag": "okinawa",
        # <main>が無く終了判定が誤りやすいため詳細取得はせず、締切は「要確認」で掲載
        "fetch_detail": False,
    },
    {
        "key": "naha_city",
        "label": "那覇市(企業支援)",
        "listing": "https://www.city.naha.okinawa.jp/business/kigyouricchi/kigyoushien/index.html",
        # 一覧<main>内の市サイト事業ページ(相対リンク)。indexは除外
        "link_re": re.compile(r'href="((?:\.\./)*(?:business|kurasitetuduki)/[\w./-]*(?<!index)\.html)"'),
        "tag": "okinawa",
        # 補助金・支援事業のみ採用(条例・調査報告・窓口案内等を除外)
        "name_require": re.compile(r"補助|助成|支援事業|支援金"),
        "name_deny": ("条例", "報告書", "実態調査", "ポータル", "窓口", "市長賞",
                      "ロゴ", "キャラクター", "商品一覧", "情報",
                      "支援・助成制度"),  # カテゴリ(ハブ)ページ
        # 詳細に<main>+公募期間表記あり → 締切抽出可能
        "fetch_detail": True,
    },
]

# 締切抽出に使うシグナル(この語の直後に出る日付を締切候補とみなす)
PERIOD_KW = (
    r"(?:募集期間|公募期間|受付期間|申請期間|応募期間|募集期限|公募期限|"
    r"受付期限|応募期限|申請期限|受付締切|応募締切|締切|締め切り|必着|まで)"
)
DATE_RE = re.compile(r"令和(\d+)年(\d+)月(\d+)日|(\d{4})年(\d+)月(\d+)日")
# 終了を示すシグナル(本文<main>内に出た場合のみ有効)
CLOSED_SIGNALS = (
    "終了しました", "終了いたしました", "受付を終了", "募集を終了", "公募は終了",
    "受付終了", "募集終了", "締め切りました", "受付は終了",
)
# 一覧のリンク文言に出る終了マーカー
CLOSED_NAME_SIGNALS = ("終了", "終わりました")

# 承継・M&A 判定(shokei タグを最優先で付与)
SHOKEI_SIGNALS = ("事業承継", "承継", "引継ぎ", "引継", "M&A", "Ｍ＆Ａ")
TAG_PRIORITY = {"nationwide": 1, "okinawa": 2, "shokei": 3}

# 現在の元号年(令和)。名称に「令和N年度」があり、これより2年以上前で
# 締切が取れないものは残存(掲載終了)とみなしスキップする。
CURRENT_REIWA = datetime.now(JST).year - 2018
REIWA_FY_RE = re.compile(r"令和(\d+)年度")

MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def http_get(url: str, retries: int = 3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as res:
                charset = res.headers.get_content_charset() or "utf-8"
                return res.read().decode(charset, "replace")
        except Exception as e:
            print(f"[warn] GET failed ({i+1}/{retries}) {url}: {e}", file=sys.stderr)
            time.sleep(1.5 * (i + 1))
    return None


def robots_ok(url: str, cache: dict) -> bool:
    """robots.txt を確認し can_fetch を返す。取得不能時は標準通り許可(404=allow)。"""
    parts = urllib.parse.urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    rp = cache.get(root, "unset")
    if rp == "unset":
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(root + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        cache[root] = rp
    if rp is None:
        return True
    try:
        return rp.can_fetch(UA, url) and rp.can_fetch("*", url)
    except Exception:
        return True


def main_text(html: str) -> str:
    m = MAIN_RE.search(html)
    body = m.group(1) if m else html
    return WS_RE.sub(" ", TAG_RE.sub(" ", body)).strip()


def clean_name(raw_html: str) -> str:
    return WS_RE.sub(" ", TAG_RE.sub("", raw_html)).strip()


def to_date(year, month, day):
    try:
        return datetime(int(year), int(month), int(day), tzinfo=JST).date()
    except Exception:
        return None


def extract_deadline(text: str):
    """本文から締切候補(期間キーワード近傍の最も遅い日付)を返す。無ければ None。"""
    cands = []
    for km in re.finditer(PERIOD_KW, text):
        window = text[km.start(): km.start() + 80]
        for dm in DATE_RE.finditer(window):
            if dm.group(1):  # 令和
                d = to_date(2018 + int(dm.group(1)), dm.group(2), dm.group(3))
            else:            # 西暦
                d = to_date(dm.group(4), dm.group(5), dm.group(6))
            if d:
                cands.append(d)
    return max(cands) if cands else None


def is_closed(text: str) -> bool:
    return any(sig in text for sig in CLOSED_SIGNALS)


def decide_tag(base_tag: str, name: str) -> str:
    if any(s in (name or "") for s in SHOKEI_SIGNALS):
        return "shokei"
    return base_tag


def crawl_source(src: dict, robots_cache: dict) -> list:
    items = []
    listing_url = src["listing"]
    if not robots_ok(listing_url, robots_cache):
        print(f"[skip] robots disallow: {listing_url}", file=sys.stderr)
        return items

    html = http_get(listing_url)
    time.sleep(REQUEST_DELAY)
    if not html:
        print(f"[warn] listing fetch failed: {listing_url}", file=sys.stderr)
        return items

    lmain = MAIN_RE.search(html)
    scope = lmain.group(1) if lmain else html

    deny = src.get("deny_basename", set())
    entries = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', scope, re.S):
        href = m.group(1)
        if not src["link_re"].search(f'href="{href}"'):
            continue
        name = clean_name(m.group(2))
        if not name or len(name) < 6:
            continue
        req = src.get("name_require")
        if req and not req.search(name):
            continue
        if any(d in name for d in src.get("name_deny", ())):
            continue
        abs_url = urllib.parse.urljoin(listing_url, href)
        if abs_url.rsplit("/", 1)[-1] in deny:
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        entries.append((name, abs_url))

    print(f"[info] {src['label']}: 一覧 {len(entries)} 件", file=sys.stderr)

    today = datetime.now(JST).date()
    fetch_detail = src.get("fetch_detail", True)
    fetched = 0
    for name, url in entries:
        if any(sig in name for sig in CLOSED_NAME_SIGNALS):
            continue

        deadline = "要確認"
        status = "要確認"
        if fetch_detail:
            if fetched >= DETAIL_LIMIT:
                break
            if not robots_ok(url, robots_cache):
                continue
            dhtml = http_get(url)
            fetched += 1
            time.sleep(REQUEST_DELAY)
            if dhtml:
                text = main_text(dhtml)
                if is_closed(text):
                    continue  # 終了は掲載しない
                d = extract_deadline(text)
                if d:
                    if d < today:
                        continue  # 期限切れ
                    deadline = d.strftime("%Y-%m-%d")
                    status = "募集中"

        # 締切不明のまま、名称が2年以上前の年度 → 残存(掲載終了)とみなしスキップ
        if status != "募集中":
            fym = REIWA_FY_RE.search(name)
            if fym and int(fym.group(1)) <= CURRENT_REIWA - 2:
                continue

        tag = decide_tag(src["tag"], name)
        sid = f"{src['key']}-{re.sub(r'[^0-9]', '', url.rsplit('/', 1)[-1]) or str(fetched)}"
        items.append({
            "id": sid,
            "name": name,
            "issuer": src["label"],
            "target_area": "沖縄県",
            "target_biz": "",
            "employees": "",
            "max_amount": None,
            "deadline": deadline,
            "source_url": url,
            "tag": tag,
            "source": src["label"],
            "fetched_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
            "status": status,
        })

    print(f"[info] {src['label']}: 採用 {len(items)} 件", file=sys.stderr)
    return items


def main() -> None:
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = {"items": []}
    existing = payload.get("items", [])
    existing_urls = {it.get("source_url") for it in existing}
    existing_ids = {it.get("id") for it in existing}

    robots_cache: dict = {}
    added = []
    for src in SOURCES:
        for it in crawl_source(src, robots_cache):
            if it["source_url"] in existing_urls or it["id"] in existing_ids:
                continue
            existing_urls.add(it["source_url"])
            existing_ids.add(it["id"])
            added.append(it)

    merged = existing + added
    merged.sort(key=lambda x: (x.get("deadline") or "9999"))

    by_tag: dict = {}
    by_source: dict = {}
    for it in merged:
        by_tag[it.get("tag", "?")] = by_tag.get(it.get("tag", "?"), 0) + 1
        s = it.get("source", "jGrants")
        by_source[s] = by_source.get(s, 0) + 1

    payload["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    payload["count"] = len(merged)
    payload["by_tag"] = by_tag
    payload["by_source"] = by_source
    payload["items"] = merged

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[ok] local +{len(added)} 件 / 合計 {len(merged)} 件 → data/subsidies.json")
    print(f"[by_source] {by_source}")


if __name__ == "__main__":
    main()
