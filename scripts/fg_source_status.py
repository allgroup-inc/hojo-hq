# -*- coding: utf-8 -*-
"""もらいわすれ堂: 公式ページ(出典)が無い(HTTP 404/410)と確かめた制度の、出典リンクだけを一時的に止める。

制度そのものは削除しない(掲載を続ける)。止めるのは「公式ページで確認する」などのリンクだけで、
代わりに「公式ページを確認中」と表示する。出典URL(source_url)は書き換えないので、
正しい公式URLを原文で確かめてシードの source_url を直せば、その回の収集から自動でリンクが戻る。

止める対象(推測で足さない):
  1. CONFIRMED_DEAD: 収集で 404/410 を受けたと記録が残っているURL(根拠の日時・制度・記録を書く)
  2. その回の収集で、いずれかのシードが 404/410 を受けたURL
ただし、その回の収集で実際に開けた(HTTP 200)URLは止めない。一時的な障害(503・タイムアウト)では止めない。

表示: 診断ページ(site/fukugiiro/shindan/index.html)・トップ(site/fukugiiro/index.html)・
申請準備シート(generate_kit_pages.py)・場面別ページ(generate_life_pages.py)・市町村別ページ(generate_area_pages.py)
"""
import html

DEAD_CODES = {"HTTP 404": 404, "HTTP 410": 410}

# 収集で 404/410 を確かめた公式ページ。足すときは、収集の記録(publish_status.json の failed)を根拠にする。
# 正しいURLを原文で確かめてシードを直したら、ここから外してよい(外さなくても、別のURLになれば効かない)
CONFIRMED_DEAD = {
    "https://www.pref.okinawa.lg.jp/kyoiku/kosodate/1008226/1008243/index.html": {
        "confirmed_at": "2026-11-04 10:21",
        "http": 404,
        "evidence": "収集で fk-kuni-jidofuyoteate が URL到達不可(HTTP 404)"
                    "(data/fukugiiro/publish_status.json・自動コミット d7e397b9e4)",
    },
}

LABEL = "公式ページを確認中"
# 制度が終わったと誤解されないように、「リンクを止めている理由」と「制度の終了ではない」ことを書く
NOTE = ("「公式ページを確認中」の制度は、公式ページが移動などで開けなくなったため、"
        "リンクを一時的にお休みしています。この表示は、制度が終わったという意味ではありません。"
        "内容や申請は、窓口でご確認ください。")


def dead_sources(seeds, failed, checked_ok=(), now=""):
    """止めるURL → {confirmed_at, http, evidence}。failed は {制度ID: 理由(例 'URL到達不可(HTTP 404)')}。"""
    dead = {u: dict(v) for u, v in CONFIRMED_DEAD.items()}
    by_id = {s["id"]: s for s in seeds}
    for sid, reason in sorted(failed.items()):
        code = next((c for k, c in DEAD_CODES.items() if k in (reason or "")), None)
        if code and sid in by_id:
            dead.setdefault(by_id[sid]["source_url"],
                            {"confirmed_at": now, "http": code, "evidence": f"収集で {sid} が {reason}"})
    for url in checked_ok:
        dead.pop(url, None)  # この回の収集で開けたURLは止めない
    return dead


def mark_unavailable(items, dead):
    """出典が止める対象の制度に source_unavailable を付ける(前回の印は付け直す)。付けた制度IDを返す。"""
    marked = []
    for it in items:
        it.pop("source_unavailable", None)
        d = dead.get(it.get("source_url"))
        if d:
            it["source_unavailable"] = {"since": d.get("confirmed_at", ""),
                                        "reason": f"公式ページが見つかりません(HTTP {d.get('http')})"}
            marked.append(it["id"])
    return marked


def unavailable(it):
    return bool(it.get("source_unavailable"))


def link(it, text, attrs='rel="noopener"'):
    """出典リンクのHTML。止めている制度は、リンクの代わりに「公式ページを確認中」を出す。"""
    if unavailable(it):
        return f'<span class="src-pending" style="color:#7a5b00;font-weight:700">{LABEL}</span>'
    return f'<a href="{html.escape(it.get("source_url", ""), quote=True)}" {attrs}>{text}</a>'


def note_html(items):
    """止めている制度が1つでもあるページに、1回だけ出す説明。"""
    if any(unavailable(it) for it in items):
        return f'<p class="note src-pending-note" style="color:#7a5b00">{NOTE}</p>'
    return ""


def jsonld_url(it):
    """構造化データの url。止めている制度は、開けないURLを載せない。"""
    return "" if unavailable(it) else it.get("source_url", "")


def without_empty_url(d):
    """構造化データの項目から、空の url / serviceUrl を外す(公式ページを確認中の制度)。"""
    return {k: v for k, v in d.items() if not (k in ("url", "serviceUrl") and not v)}
