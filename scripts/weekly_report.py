#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 週次レポート(小柳さんのLINEへ毎週月曜8:00 JSTに配信)
サイト・LINE導線・LINE友だち・Instagram・Facebookの1週間の数字をまとめる。

方針(hikari-report-thresholds準拠): 取得できない項目は「未接続/取得不可」と明記し、
静かに欠損させない。1項目の失敗でレポート全体は止めない。

必要なSecrets(すべて登録済み):
  PLAUSIBLE_API_KEY / LINE_CHANNEL_ACCESS_TOKEN / LINE_ADMIN_USER_ID
  FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN / IG_USER_ID
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
SITE_ID = "allgroup-inc.github.io"
GRAPH = "https://graph.facebook.com/v21.0"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "reports", "hojo-mikata")


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def section_site():
    key = os.environ.get("PLAUSIBLE_API_KEY", "")
    if not key:
        return "🌐 サイト: 未接続(PLAUSIBLE_API_KEY未設定)"
    h = {"Authorization": "Bearer " + key}
    try:
        agg = get(f"https://plausible.io/api/v1/stats/aggregate?site_id={SITE_ID}"
                  "&period=7d&metrics=visitors,pageviews", h)["results"]
        lines = [f"🌐 サイト(7日間)",
                 f"・訪問者: {agg['visitors']['value']}人 / 閲覧: {agg['pageviews']['value']}PV"]
    except Exception as e:  # noqa: BLE001
        return f"🌐 サイト: 取得不可({type(e).__name__})"
    try:
        br = get(f"https://plausible.io/api/v1/stats/breakdown?site_id={SITE_ID}"
                 "&period=7d&property=event:props:channel"
                 "&filters=" + urllib.parse.quote("event:name==line_redirect")
                 + "&metrics=events", h)["results"]
        if br:
            parts = [f"{r.get('channel') or '?'} {r.get('events', 0)}回" for r in br]
            lines.append("・LINE登録ボタンのタップ: " + " / ".join(parts))
        else:
            lines.append("・LINE登録ボタンのタップ: 0回")
    except Exception:
        lines.append("・LINE登録タップ: 取得不可")
    return "\n".join(lines)


def section_line():
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        return "💬 LINE: 未接続"
    date = (datetime.now(JST) - timedelta(days=1)).strftime("%Y%m%d")
    try:
        r = get(f"https://api.line.me/v2/bot/insight/followers?date={date}",
                {"Authorization": "Bearer " + token})
        if r.get("status") == "ready":
            return f"💬 LINE公式: 友だち {r.get('followers', '?')}人(有効リーチ {r.get('targetedReaches', '?')}人)"
        return "💬 LINE公式: 集計待ち(明日以降に反映)"
    except Exception as e:  # noqa: BLE001
        return f"💬 LINE公式: 取得不可({type(e).__name__})"


def section_instagram():
    ig = os.environ.get("IG_USER_ID", "")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not (ig and token):
        return "📷 Instagram: 未接続"
    try:
        prof = get(f"{GRAPH}/{ig}?fields=followers_count,media_count&access_token={token}")
        lines = [f"📷 Instagram: フォロワー {prof.get('followers_count', '?')}人"
                 f" / 投稿 {prof.get('media_count', '?')}件"]
        media = get(f"{GRAPH}/{ig}/media?fields=timestamp,like_count,comments_count"
                    f"&limit=15&access_token={token}").get("data", [])
        since = datetime.now(timezone.utc) - timedelta(days=7)
        likes = comments = posts = 0
        for m in media:
            ts = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
            if ts >= since:
                posts += 1
                likes += m.get("like_count", 0)
                comments += m.get("comments_count", 0)
        lines.append(f"・今週の投稿 {posts}件 / いいね {likes} / コメント {comments}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"📷 Instagram: 取得不可({type(e).__name__})"


def section_facebook():
    page = os.environ.get("FB_PAGE_ID", "")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not (page and token):
        return "📘 Facebook: 未接続"
    try:
        prof = get(f"{GRAPH}/{page}?fields=fan_count,followers_count&access_token={token}")
        return (f"📘 Facebookページ: フォロワー {prof.get('followers_count', '?')}人"
                f"(いいね {prof.get('fan_count', '?')})")
    except Exception as e:  # noqa: BLE001
        return f"📘 Facebook: 取得不可({type(e).__name__})"


def section_note():
    """note運営の週次数字(docs/note運用規程.md: アカリさん週次レポへの組込)。"""
    import glob as _glob
    base = os.path.dirname(__file__)
    try:
        weekly = _glob.glob(os.path.join(base, "..", "posts", "note", "*_vol*.md"))
        published = 0
        for p in weekly:
            with open(p, encoding="utf-8") as f:
                if "published:" in f.read(2000):
                    published += 1
        lines = ["📝 note運営",
                 f"・週刊下書き: {len(weekly)}本 / 公開済み: {published}本"]
        unpublished = len(weekly) - published
        if unpublished >= 4:
            lines.append(f"⚠️ 未公開の下書きが{unpublished}本(運用規程: 4本たまったら継続を再議論)")
        kpi_path = os.path.join(base, "..", "data", "note_kpi.json")
        kpi = {}
        if os.path.exists(kpi_path):
            with open(kpi_path, encoding="utf-8") as f:
                kpi = json.load(f)

        def v(k, u):
            x = kpi.get(k)
            return f"{x:,}{u}" if isinstance(x, (int, float)) else "未入力"

        lines.append(f"・フォロワー: {v('followers', '人')} / メンバー: {v('members', '人')}"
                     f" / 今月売上: {v('monthly_sales_yen', '円')}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"📝 note運営: 取得不可({type(e).__name__})"


def push_line(text):
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    to = os.environ["LINE_ADMIN_USER_ID"]
    payload = json.dumps({"to": to, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push", data=payload, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)


def write_report(now, body):
    """LINE配信本文をrepoにも永続化する(reports/fukugiiroと同じパターン)。
    LINE直送だけだと別セッションのアカリさんが過去のKPI推移を追えないため。"""
    week_tag = now.strftime("%G-W%V")
    md = "\n\n".join([
        f"# 沖縄企業のミカタ 週次レポート {week_tag}",
        f"生成: {now.strftime('%Y-%m-%d %H:%M')} JST(統括アカリさん・自動生成)",
        body,
        "> 未接続/取得不可の項目は、真のKPI(面談・相談件数)・GLOW接続数を含め手動追跡中。"
        "自動集計への組み込みはタスク一覧を参照。",
    ])
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"{week_tag}_weekly.md"), "w", encoding="utf-8") as f:
        f.write(md + "\n")
    with open(os.path.join(OUT_DIR, "latest.md"), "w", encoding="utf-8") as f:
        f.write(md + "\n")


def main():
    now = datetime.now(JST)
    start = (now - timedelta(days=7)).strftime("%-m/%-d") if os.name != "nt" else (now - timedelta(days=7)).strftime("%m/%d")
    end = now.strftime("%-m/%-d") if os.name != "nt" else now.strftime("%m/%d")
    body = "\n\n".join([
        f"📊【ミカタ】週次レポート({start}〜{end})",
        section_site(),
        section_line(),
        section_instagram(),
        section_facebook(),
        section_note(),
        "詳しい内訳: GA4アプリ/Clarityでいつでも確認できます🌺",
    ])
    print(body)
    write_report(now, body)
    if "--dry-run" in sys.argv:
        print("[ok] dry-run: 送信なし(reports/hojo-mikata/は更新しました)")
        return
    push_line(body)
    print("[ok] LINEへ送信しました")


if __name__ == "__main__":
    main()
