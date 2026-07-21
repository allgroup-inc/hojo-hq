#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq 収集部(シュウくん)
jGrants APIから沖縄県で使える補助金・助成金を取得し data/subsidies.json を更新する。
GitHub Actions cron で1日4回実行(6時間おき)。

方針(拡充版):
- jGrants の keyword 検索は「タイトル/概要」への部分一致。地域は keyword では絞れないため
  ジャンル横断の広いキーワード網で母集団を集め、target_area_search で沖縄適用を判定する。
- 沖縄で使える制度 = target_area_search が「全国」/「沖縄」を含む(または空)もの。
  → 全国対象で沖縄企業が申請できる制度を漏れなく拾う。
- 重複は id で除外。承継・M&A 系は shokei タグを最優先で付与(維持)。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
API_BASE = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subsidies.json")

# ── 広いジャンル横断キーワード網(タイトル/概要に部分一致)──────────────
# 補助金/助成金の一般語 + 政策テーマ(雇用/創業/設備/DX/観光/農業/販路 ほか)。
# 目的は「募集中の母集団」を取り切ること。id で重複除外するので網羅重視で重ねてよい。
KEYWORDS = [
    # 制度種別の一般語
    "補助金", "助成金", "支援", "給付", "奨励",
    # 事業一般
    "中小企業", "小規模", "経営", "事業", "生産性", "革新", "投資",
    # 雇用・人材
    "雇用", "人材", "賃上げ", "賃金", "リスキリング", "就職", "女性", "高齢", "障害",
    # 創業・スタートアップ
    "創業", "起業", "スタートアップ", "ベンチャー",
    # 設備・ものづくり・省力化
    "設備", "設備投資", "ものづくり", "省力化", "ロボット", "製造",
    # DX・IT・デジタル
    "DX", "IT導入", "IT", "デジタル", "システム",
    # 販路・海外・観光
    "販路", "販路開拓", "輸出", "海外", "観光", "インバウンド",
    # 一次産業・地域
    "農業", "漁業", "食品", "地域", "商店", "まちづくり",
    # 環境・エネルギー
    "省エネ", "脱炭素", "エネルギー", "環境", "再生可能",
    # 研究開発・その他政策
    "研究開発", "開発", "新規", "促進", "インボイス", "医療", "介護", "子育て", "防災",
]

# ── 承継・M&A系(shokei タグを最優先で付与)────────────────────────────
SHOKEI_KEYWORDS = ["事業承継", "M&A", "引継ぎ", "承継"]

# 承継判定に使う本文シグナル(キーワード経由でなくても shokei と判定)
SHOKEI_SIGNALS = ("事業承継", "承継", "引継ぎ", "引継", "M&A", "Ｍ＆Ａ")

# タグ優先度(数値が大きいほど優先)。重複時はこの優先度で上書き。
TAG_PRIORITY = {"nationwide": 1, "okinawa": 2, "shokei": 3}


def fetch_json(url: str, retries: int = 3) -> dict:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hojo-hq/1.0"})
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except Exception as e:
            print(f"[warn] fetch failed ({i+1}/{retries}): {e}", file=sys.stderr)
            time.sleep(2 * (i + 1))
    return {}


def search(keyword: str, acceptance: str = "1") -> list:
    """acceptance=1: 募集中のみ"""
    params = {
        "keyword": keyword,
        "sort": "acceptance_end_datetime",
        "order": "ASC",
        "acceptance": acceptance,
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    data = fetch_json(url)
    return data.get("result", [])


def is_okinawa_applicable(area: str) -> bool:
    """沖縄企業が申請できる制度か(全国 or 沖縄 を含む/地域指定なし)。"""
    if not area:
        return True
    return ("全国" in area) or ("沖縄" in area)


def decide_tag(area: str, title: str, via_shokei_kw: bool) -> str:
    """タグを決定。承継・M&A系は最優先で shokei。"""
    text = title or ""
    if via_shokei_kw or any(sig in text for sig in SHOKEI_SIGNALS):
        return "shokei"
    if "沖縄" in (area or ""):
        return "okinawa"
    return "nationwide"


def normalize(item: dict, tag: str) -> dict:
    def dt(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST).strftime("%Y-%m-%d")
        except Exception:
            return None

    deadline = dt(item.get("acceptance_end_datetime"))
    return {
        "id": item.get("id"),
        "name": item.get("title") or item.get("name"),
        "issuer": item.get("institution_name") or item.get("subsidy_catch_phrase") or "",
        "target_area": item.get("target_area_search") or "",
        "target_biz": item.get("industry") or "",
        "employees": item.get("target_number_of_employees") or "",
        "max_amount": item.get("subsidy_max_limit"),
        "deadline": deadline or "要確認",
        "source_url": f"https://www.jgrants-portal.go.jp/subsidy/{item.get('id')}",
        "tag": tag,  # okinawa / nationwide / shokei(承継・M&A)
        "fetched_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "status": "募集中",
    }


def main() -> None:
    results: dict[str, dict] = {}

    # クエリ = 広いキーワード網 + 承継系。重複keywordは除外。
    queries = []
    seen_kw = set()
    for kw in KEYWORDS + SHOKEI_KEYWORDS:
        if kw not in seen_kw:
            seen_kw.add(kw)
            queries.append(kw)

    scanned = 0
    for kw in queries:
        via_shokei_kw = kw in SHOKEI_KEYWORDS
        for item in search(kw):
            scanned += 1
            area = item.get("target_area_search") or ""
            if not is_okinawa_applicable(area):
                continue
            sid = item.get("id")
            if not sid:
                continue
            title = item.get("title") or item.get("name") or ""
            tag = decide_tag(area, title, via_shokei_kw)

            if sid not in results:
                results[sid] = normalize(item, tag)
            else:
                # 重複は id で除外しつつ、タグは優先度が高い方へ更新(shokei維持)
                cur = results[sid]["tag"]
                if TAG_PRIORITY.get(tag, 0) > TAG_PRIORITY.get(cur, 0):
                    results[sid]["tag"] = tag
        time.sleep(0.5)

    items = sorted(results.values(), key=lambda x: x["deadline"] or "9999")
    by_tag: dict[str, int] = {}
    for it in items:
        by_tag[it["tag"]] = by_tag.get(it["tag"], 0) + 1

    payload = {
        "updated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "count": len(items),
        "by_tag": by_tag,
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[ok] {len(items)} 件を書き出しました(走査 {scanned} 件) → data/subsidies.json")
    print(f"[tag] {by_tag}")


if __name__ == "__main__":
    main()
