#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ 収集部(シュシュ・個人向け管轄)v1 — シードURL方式
守り部承認済みドメイン(こども家庭庁・厚労省・文科省・内閣府 / 審査記録第2号)の
主要制度をシードとして、公式ページの到達性を確認できたものだけを data/fukugiiro/seido.json に書く。

設計原則(審査記録の遵守条件そのまま):
- 保持するのは事実情報(制度名・発行元・窓口・原文URL)のみ。説明文の転載はしない
- 金額・締切は書かない(amount_note=要確認)。ケンショウの一次ソース突合後に人が embellish する
- robots.txt を毎回確認・連絡先付きUA・リクエスト間隔1.5秒以上
- 到達性(HTTP 200)が確認できないシードはDBに書かない(壊れたリンクを公開しない)
- 書き込み前に validate_fukugiiro.validate() を通し、エラーがあれば書かずに異常終了
- 実行は GitHub Actions のみ・朝夕2回まで(第1次審査ウタガイ採用事項)

TODO(ベッカイ採用事項): 各府省RSS/新着の監視は v2 で追加(新設・随時給付の検知用)
"""
import json
import os
import sys
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from validate_fukugiiro import validate  # noqa: E402

JST = timezone(timedelta(hours=9))
UA = "hojo-hq-bot/1.0 (+https://allgroup-inc.github.io/hojo-hq; contact: bot@en-life.co.jp)"
BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "data", "fukugiiro", "seido.json")

# シード: 承認済みドメインの主要制度(URLは2026-07-22に検索で特定。到達性は毎回実行時に再確認)
SEEDS = [
    {
        "id": "fk-kuni-jidoteate",
        "name": "児童手当",
        "category": "子育て", "life_events": ["子育て"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "中学生以下(2024年10月以降は高校生年代まで拡充)のお子さんを育てている世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.cfa.go.jp/policies/kokoseido/jidouteate",
    },
    {
        "id": "fk-kuni-jidofuyoteate",
        "name": "児童扶養手当",
        "category": "子育て", "life_events": ["子育て", "低所得・生活苦"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "ひとり親家庭などでお子さんを育てている世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.cfa.go.jp/policies/hitori-oya/fuyou-teate",
    },
    {
        "id": "fk-kuni-shussan-ichijikin",
        "name": "出産育児一時金",
        "category": "子育て", "life_events": ["妊娠・出産"],
        "issuer": "厚生労働省(各健康保険)", "area": "全国",
        "target_household": "健康保険に加入している方(被扶養者を含む)が出産したときに対象となる可能性があります",
        "how_to_apply": "加入している健康保険(協会けんぽ・国保など)への申請。多くは医療機関での直接支払制度が利用できます",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/shussan/index.html",
    },
    {
        "id": "fk-kuni-ikuji-kyufu",
        "name": "育児休業給付(雇用保険)",
        "category": "子育て", "life_events": ["妊娠・出産", "子育て", "就職・転職"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "雇用保険に加入していて育児休業を取得する方が対象となる可能性があります",
        "how_to_apply": "原則、勤務先を通じてハローワークへ申請",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000158500.html",
    },
    {
        "id": "fk-kuni-jukyo-kakuho",
        "name": "住居確保給付金",
        "category": "住まい", "life_events": ["失業", "低所得・生活苦", "住宅取得・引越"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "離職・収入減少などで家賃の支払いにお困りの世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの自治体の自立相談支援機関",
        "source_url": "https://corona-support.mhlw.go.jp/jukyokakuhokyufukin/index.html",
    },
    {
        "id": "fk-kuni-kogaku-ryoyo",
        "name": "高額療養費制度",
        "category": "医療・健康", "life_events": ["病気・けが"],
        "issuer": "厚生労働省(各健康保険)", "area": "全国",
        "target_household": "1ヶ月の医療費の自己負担が上限額を超えた方が対象となる可能性があります",
        "how_to_apply": "加入している健康保険への申請(事前の限度額適用認定証の利用も可能です)",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/juuyou/kougakuiryou/index.html",
    },
    {
        "id": "fk-kuni-shugaku-shien",
        "name": "高等教育の修学支援新制度(授業料等減免・給付型奨学金)",
        "category": "教育", "life_events": ["入園・入学"],
        "issuer": "文部科学省", "area": "全国",
        "target_household": "大学・短大・高専・専門学校に進学する(在学中の)お子さんがいる世帯が対象となる可能性があります(2025年度から多子世帯の拡充があります)",
        "how_to_apply": "在学校・進学先を通じた申込み(日本学生支援機構)",
        "source_url": "https://www.mext.go.jp/kyufu/",
    },
    {
        "id": "fk-kuni-hitorioya-shien",
        "name": "ひとり親家庭への支援制度(全体案内)",
        "category": "子育て", "life_events": ["子育て", "低所得・生活苦"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "ひとり親家庭の世帯向けの各種支援(手当・貸付・就業支援など)の入口です",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.cfa.go.jp/policies/hitori-oya",
        "match_tokens": ["ひとり親家庭"],
    },
    {
        "id": "fk-kuni-ninpu-shien",
        "name": "妊婦のための支援給付・伴走型相談支援",
        "category": "子育て", "life_events": ["妊娠・出産"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "妊娠された方・出産された世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口(母子保健担当)",
        "source_url": "https://www.cfa.go.jp/policies/shussan-kosodate",
    },
    {
        "id": "fk-kuni-shugakushienkin-koko",
        "name": "高等学校等就学支援金",
        "category": "教育", "life_events": ["入園・入学"],
        "issuer": "文部科学省", "area": "全国",
        "target_household": "高校等に通うお子さんがいる世帯が対象となる可能性があります(制度改正の動きがあるため最新情報をご確認ください)",
        "how_to_apply": "在学する学校を通じた申請(オンライン申請 e-Shien)",
        "source_url": "https://www.mext.go.jp/a_menu/shotou/mushouka/1342674.htm",
    },
    {
        "id": "fk-kuni-shogaku-kyufukin-koko",
        "name": "高校生等奨学給付金",
        "category": "教育", "life_events": ["入園・入学", "低所得・生活苦"],
        "issuer": "文部科学省(窓口は都道府県)", "area": "全国",
        "target_household": "住民税非課税世帯等で高校生等のお子さんがいる世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの都道府県への申請(学校経由の場合あり)",
        "source_url": "https://www.mext.go.jp/a_menu/shotou/mushouka/1344089.htm",
    },
    {
        "id": "fk-kuni-kyushokusha-shien",
        "name": "求職者支援制度(職業訓練受講給付金)",
        "category": "仕事・失業", "life_events": ["失業", "就職・転職", "低所得・生活苦"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "雇用保険を受給できない求職中の方(フリーランス・自営業を廃業した方等を含む)が対象となる可能性があります",
        "how_to_apply": "ハローワーク",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/koyou/kyushokusha_shien/index.html",
    },
    {
        "id": "fk-kuni-kyoiku-kunren",
        "name": "教育訓練給付金",
        "category": "仕事・失業", "life_events": ["就職・転職"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "働きながら(または離職後に)資格取得やスキルアップを目指す方が対象となる可能性があります",
        "how_to_apply": "ハローワーク",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/jinzaikaihatsu/kyouiku.html",
    },
]

_robots_cache = {}


def robots_ok(url):
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    if host not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(f"https://{host}/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as res:
                rp.parse(res.read().decode("utf-8", "replace").splitlines())
        except Exception:
            rp = None  # robots.txt無し等 → 制限指定なし扱い
        _robots_cache[host] = rp
        time.sleep(1.5)
    rp = _robots_cache[host]
    return True if rp is None else rp.can_fetch(UA, url)


def reachable(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            return res.status == 200
    except Exception:
        return False


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    items, skipped = [], []
    for seed in SEEDS:
        url = seed["source_url"]
        if not robots_ok(url):
            skipped.append((seed["name"], "robots.txt不許可"))
            print(f"SKIP(robots): {seed['name']}")
            continue
        ok = reachable(url)
        time.sleep(1.5)
        if not ok:
            skipped.append((seed["name"], "URL到達不可"))
            print(f"SKIP(unreachable): {seed['name']} {url}")
            continue
        item = dict(seed)
        item.update({
            "amount_note": "要確認(公式ページでご確認ください)",
            "deadline_type": "常時" if seed["id"] != "fk-kuni-jukyo-kakuho" else "要確認",
            "deadline": None,
            "verified": False, "verified_at": None, "verified_by": None,
            "status": "要確認",
            "notes": "出典: " + seed["issuer"].split("(")[0] + "ウェブサイト",
            "fetched_at": now,
        })
        items.append(item)
        print(f"OK: {seed['name']}")

    data = {"updated_at": now, "count": len(items), "items": items}
    errors, warns = validate(data)
    for w in warns:
        print(f"[WARN] {w}")
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        print("検証エラーのため書き込みを中止")
        sys.exit(1)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"書き込み完了: {len(items)}件 / スキップ {len(skipped)}件 {skipped if skipped else ''}")
    # シードの半数以上が到達不可なら異常(サイト構造変化・ネットワーク断の疑い)
    if len(items) < len(SEEDS) / 2:
        print("[ERROR] シードの過半が取得不可 — 要調査")
        sys.exit(1)


if __name__ == "__main__":
    main()
