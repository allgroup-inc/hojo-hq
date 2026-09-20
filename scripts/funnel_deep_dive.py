#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — ファネル深掘りレポート(手動実行)
「何人がどこまで見て、どこで離脱しているか」を全計測系統から一括で引く。
方針(hikari-report-thresholds準拠): 取れない項目は「取得不可」と明記し、黙って欠損させない。
出力: reports/hojo-mikata/funnel_deep_dive_<日付>.md
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
SITE_ID = "allgroup-inc.github.io"
LAUNCH = "2026-07-23"
GRAPH = "https://graph.facebook.com/v21.0"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.now(JST).date()


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def p_agg(h, period, metrics="visitors,pageviews", flt=None):
    url = (f"https://plausible.io/api/v1/stats/aggregate?site_id={SITE_ID}"
           f"&{period}&metrics={metrics}")
    if flt:
        url += "&filters=" + urllib.parse.quote(flt)
    return get(url, h)["results"]


def p_break(h, period, prop, flt=None, metrics="visitors,events", limit=12):
    url = (f"https://plausible.io/api/v1/stats/breakdown?site_id={SITE_ID}"
           f"&{period}&property={prop}&metrics={metrics}&limit={limit}")
    if flt:
        url += "&filters=" + urllib.parse.quote(flt)
    return get(url, h)["results"]


def event_count(h, period, name):
    try:
        r = p_agg(h, period, metrics="events,visitors", flt=f"event:name=={name}")
        return r["events"]["value"], r["visitors"]["value"]
    except Exception:
        return None, None


def fmt_pct(a, b):
    if not b:
        return "-"
    return f"{round(a / b * 100)}%"


def site_block(h, label, period):
    L = [f"### {label}"]
    try:
        agg = p_agg(h, period, "visitors,pageviews,visit_duration,bounce_rate")
        L.append(f"- 訪問者 **{agg['visitors']['value']}人** / 閲覧 {agg['pageviews']['value']}PV"
                 f" / 平均滞在 {agg['visit_duration']['value']}秒 / 直帰率 {agg['bounce_rate']['value']}%")
    except Exception as e:
        L.append(f"- サイト集計: 取得不可({type(e).__name__})")
        return "\n".join(L)

    v_total = agg["visitors"]["value"]

    # ファネル(ユニーク訪問者ベース)
    ev = {}
    for name in ["hojo_shindan_start", "hojo_shindan_complete", "hojo_step2_done"]:
        ev[name] = event_count(h, period, name)
    lr_ev, lr_vis = event_count(h, period, "line_redirect")

    def row(label2, pair, base):
        e, v = pair
        if e is None:
            return f"| {label2} | 取得不可 | - | - |"
        return f"| {label2} | {v}人 | {fmt_pct(v, base)} | {e}回 |"

    L.append("")
    L.append("| 段階 | 人数(ユニーク) | 到達率(訪問者比) | 回数 |")
    L.append("|---|---|---|---|")
    L.append(f"| サイト訪問 | {v_total}人 | 100% | - |")
    L.append(row("診断をさわり始めた", ev["hojo_shindan_start"], v_total))
    L.append(row("診断を実行(結果を見た)", ev["hojo_shindan_complete"], v_total))
    L.append(row("STEP2最終チェック回答", ev["hojo_step2_done"], v_total))
    L.append(row("LINE登録ボタンをタップ", (lr_ev, lr_vis), v_total))

    # LINEタップの経路内訳
    try:
        br = p_break(h, period, "event:props:channel", "event:name==line_redirect")
        if br:
            parts = [f"{r.get('channel') or '?'}: {r.get('events', 0)}回({r.get('visitors', 0)}人)" for r in br]
            L.append("- LINEタップの経路内訳: " + " / ".join(parts))
    except Exception:
        L.append("- LINEタップ経路内訳: 取得不可")

    # 流入元
    try:
        src = p_break(h, period, "visit:source", metrics="visitors")
        if src:
            parts = [f"{r.get('source') or '(直接)'}: {r.get('visitors', 0)}人" for r in src[:8]]
            L.append("- 流入元: " + " / ".join(parts))
    except Exception:
        L.append("- 流入元: 取得不可")
    try:
        utm = p_break(h, period, "visit:utm_source", metrics="visitors")
        if utm:
            parts = [f"{r.get('utm_source')}: {r.get('visitors', 0)}人" for r in utm[:8] if r.get('utm_source')]
            if parts:
                L.append("- UTM経由: " + " / ".join(parts))
    except Exception:
        pass

    # よく見られたページ
    try:
        pg = p_break(h, period, "event:page", metrics="visitors,pageviews")
        if pg:
            L.append("- よく見られたページ(訪問者数):")
            for r in pg[:10]:
                L.append(f"  - {r.get('page')}: {r.get('visitors', 0)}人 / {r.get('pageviews', 0)}PV")
    except Exception:
        L.append("- ページ内訳: 取得不可")
    return "\n".join(L)


GA4_FUNNEL = [  # (GA4イベント名, 表示ラベル)
    ("diagnosis_start", "診断をさわり始めた"),
    ("diagnosis_run", "診断を実行(結果を見た)"),
    ("step2_done", "STEP2最終チェック回答"),
    ("line_cta_click", "LINE登録ボタンをタップ"),
]


def site_block_ga4(token, label, start, end):
    """GA4版(2026-08-24 Plausible契約終了→切替)。ミカタLPプロパティの
    ファネルイベント+ /go/ 側(もらいわすれ堂プロパティ)のline_redirect内訳。"""
    import ga4_client  # noqa: PLC0415
    prop = os.environ["GA4_MIKATA_PROPERTY_ID"]
    L = [f"### {label}"]
    try:
        agg = ga4_client.aggregate(token, prop, start, end)
        L.append(f"- 訪問者 **{agg['visitors']}人** / 閲覧 {agg['pageviews']}PV"
                 f" / 平均滞在 {agg['visit_duration']}秒 / 直帰率 {agg['bounce_rate']}%"
                 "(操作なし直帰はGA4に載らないため、実際の訪問はこれより多い可能性)")
    except Exception as e:  # noqa: BLE001
        L.append(f"- サイト集計: 取得不可({type(e).__name__})")
        return "\n".join(L)
    v_total = agg["visitors"] or 0

    try:
        ev = ga4_client.event_counts(token, prop, start, end,
                                     [n for n, _ in GA4_FUNNEL])
    except Exception as e:  # noqa: BLE001
        L.append(f"- ファネルイベント: 取得不可({type(e).__name__})")
        ev = {}
    L.append("")
    L.append("| 段階 | 人数(ユニーク) | 到達率(訪問者比) | 回数 |")
    L.append("|---|---|---|---|")
    L.append(f"| サイト訪問 | {v_total}人 | 100% | - |")
    for name, label2 in GA4_FUNNEL:
        d = ev.get(name)
        if d is None:
            L.append(f"| {label2} | 0人 | {fmt_pct(0, v_total)} | 0回 |")
        else:
            L.append(f"| {label2} | {d['users']}人 | {fmt_pct(d['users'], v_total)} | {d['events']}回 |")

    # LINEタップの経路内訳(LP側 line_cta_click / go側 line_redirect)
    br = ga4_client.channel_breakdown(token, prop, start, end, "line_cta_click")
    if br is None:
        L.append("- LPのLINEタップ経路内訳: 取得不可(GA4カスタムディメンション channel 未登録)")
    elif br:
        L.append("- LPのLINEタップ経路内訳: "
                 + " / ".join(f"{ch}: {e}回({u}人)" for ch, e, u in br))
    go_prop = os.environ.get("GA4_PROPERTY_ID", "")
    if go_prop:
        br2 = ga4_client.channel_breakdown(token, go_prop, start, end, "line_redirect")
        if br2 is None:
            L.append("- /go/中間ページ到達の内訳: 取得不可(channel未登録)")
        elif br2:
            L.append("- /go/中間ページ到達の内訳: "
                     + " / ".join(f"{ch}: {e}回({u}人)" for ch, e, u in br2))
        else:
            L.append("- /go/中間ページ到達: 0回")

    # 流入元
    try:
        data = ga4_client.run_report(token, prop, {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "sessionSource"}],
            "metrics": [{"name": "activeUsers"}], "limit": "8",
            "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}]})
        rows = data.get("rows") or []
        if rows:
            parts = [f"{r['dimensionValues'][0]['value']}: {r['metricValues'][0]['value']}人"
                     for r in rows]
            L.append("- 流入元: " + " / ".join(parts))
    except Exception:  # noqa: BLE001
        L.append("- 流入元: 取得不可")

    # よく見られたページ
    try:
        data = ga4_client.run_report(token, prop, {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "pagePath"}],
            "metrics": [{"name": "activeUsers"}, {"name": "screenPageViews"}],
            "limit": "10",
            "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}]})
        rows = data.get("rows") or []
        if rows:
            L.append("- よく見られたページ(訪問者数):")
            for r in rows:
                L.append(f"  - {r['dimensionValues'][0]['value']}:"
                         f" {r['metricValues'][0]['value']}人 / {r['metricValues'][1]['value']}PV")
    except Exception:  # noqa: BLE001
        L.append("- ページ内訳: 取得不可")
    return "\n".join(L)


def line_block():
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        return "- LINE: 未接続"
    h = {"Authorization": "Bearer " + token}
    date = (datetime.now(JST) - timedelta(days=1)).strftime("%Y%m%d")
    try:
        r = get(f"https://api.line.me/v2/bot/insight/followers?date={date}", h)
        return (f"- 友だち **{r.get('followers', '?')}人**"
                f"(有効リーチ {r.get('targetedReaches', '?')}人 / ブロック {r.get('blocks', '?')}人)")
    except Exception as e:
        return f"- LINE: 取得不可({type(e).__name__})"


def ig_block():
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    ig = os.environ.get("IG_USER_ID", "")
    if not (token and ig):
        return "- Instagram: 未接続"
    L = []
    try:
        acc = get(f"{GRAPH}/{ig}?fields=followers_count,media_count&access_token={token}")
        L.append(f"- フォロワー **{acc.get('followers_count', '?')}人** / 投稿 {acc.get('media_count', '?')}件")
    except Exception as e:
        L.append(f"- アカウント集計: 取得不可({type(e).__name__})")
    try:
        media = get(f"{GRAPH}/{ig}/media?fields=id,caption,timestamp,media_type,"
                    f"like_count,comments_count&limit=15&access_token={token}")["data"]
        L.append("")
        L.append("| 投稿(冒頭) | 種類 | 日付 | リーチ | 表示回数 | いいね/コメント |")
        L.append("|---|---|---|---|---|---|")
        for m in media:
            cap = (m.get("caption") or "").split("\n")[0][:22]
            date = (m.get("timestamp") or "")[:10]
            reach = views = "-"
            try:
                ins = get(f"{GRAPH}/{m['id']}/insights?metric=reach&access_token={token}")["data"]
                for d in ins:
                    if d["name"] == "reach":
                        reach = d["values"][0]["value"]
            except Exception:
                pass
            try:
                ins2 = get(f"{GRAPH}/{m['id']}/insights?metric=views&access_token={token}")["data"]
                for d in ins2:
                    if d["name"] == "views":
                        views = d["values"][0]["value"]
            except Exception:
                pass
            L.append(f"| {cap} | {m.get('media_type','?')} | {date} | {reach} | {views} "
                     f"| {m.get('like_count',0)}/{m.get('comments_count',0)} |")
    except Exception as e:
        L.append(f"- 投稿別データ: 取得不可({type(e).__name__})")
    return "\n".join(L)


def main():
    key = os.environ.get("PLAUSIBLE_API_KEY", "")
    h = {"Authorization": "Bearer " + key} if key else None
    out = [f"# ファネル深掘りレポート({TODAY})",
           "",
           "「何人が・どこまで来て・どこで離脱しているか」の全量。取得できない項目は正直に「取得不可」と表記。",
           ""]
    if os.environ.get("GA4_SA_JSON") and os.environ.get("GA4_MIKATA_PROPERTY_ID"):
        out.append("## サイト(GA4計測 ※2026-08-24にPlausibleから方式変更・数字は直接比較不可)")
        try:
            import ga4_client  # noqa: PLC0415
            token = ga4_client.get_token()
            out.append(site_block_ga4(token, f"GA4計測開始(2026-08-24)〜{TODAY}",
                                      "2026-08-24", "today"))
            out.append("")
            out.append(site_block_ga4(token, "直近7日", "7daysAgo", "today"))
        except Exception as e:  # noqa: BLE001
            out.append(f"サイト集計: 取得不可(GA4認証 {type(e).__name__})")
        out.append("")
        out.append(f"※Plausible時代(公開{LAUNCH}〜8/24)の最終値は"
                   " reports/hojo-mikata/funnel_deep_dive_2026-09-04.md と data/hojo/funnel.json(8/16取得)を参照")
    elif not h:
        out.append("サイト計測: 未接続(GA4_SA_JSON+GA4_MIKATA_PROPERTY_ID 未設定。手順: docs/GA4計測復旧手順_20260904.md)")
    else:
        out.append("## サイト(Plausible)")
        out.append(site_block(h, f"全期間(公開{LAUNCH}〜{TODAY})",
                              f"period=custom&date={LAUNCH},{TODAY}"))
        out.append("")
        out.append(site_block(h, "直近7日", "period=7d"))
    out.append("")
    out.append("## LINE公式(昨日時点)")
    out.append(line_block())
    out.append("")
    out.append("## Instagram(投稿別)")
    out.append(ig_block())
    out.append("")
    out.append("## 計測できていないもの(正直な注記)")
    out.append("- IGの「プロフィールのリンクを押した人数」は直接は取れないため、サイト側の流入元(instagram / UTM)で代替")
    out.append("- LINE登録ボタンのタップ後、実際に友だち追加まで完了した人数は突合不可(タップ数と友だち数の両方で見る)")
    out.append("- 会社情報登録・相談の件数は台帳(スプレッドシート)側。自動集計はv1.7で追加予定")
    path = os.path.join(BASE, "reports", "hojo-mikata", f"funnel_deep_dive_{TODAY}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"[ok] {path}")


if __name__ == "__main__":
    main()
