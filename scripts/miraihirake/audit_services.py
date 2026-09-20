#!/usr/bin/env python3
"""みらいひらけ堂: 台帳の定期監査(掲載基準v2 §7の機械監査)。

検査項目:
  1. 必須項目(data_source / last_verified)の欠落、review_status の不正値
  2. published の鮮度: 60日超=警告 / 120日超=自動で verified へ降格(非表示)
  3. 鮮度KPI(published のうち最終確認60日以内の割合)と撤退基準の判定
     80%未満=黄色(exit 2) / 60%未満=赤(exit 2)。CIを赤くして気づかせる
  4. --check-urls 指定時のみ、掲載URLの死活チェック(CI用。開発環境は外に出られない)

使い方:
  python scripts/miraihirake/audit_services.py            # 検査のみ(書き換えない)
  python scripts/miraihirake/audit_services.py --fix      # 120日超の自動降格を書き込む
  python scripts/miraihirake/audit_services.py --fix --check-urls   # CIでの週次実行

出力: data/miraihirake/audit_report.json
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/miraihirake/services.json"
REPORT = ROOT / "data/miraihirake/audit_report.json"
UA = "miraihirake-audit/0.1 (+https://github.com/allgroup-inc/hojo-hq)"
VALID_STATUS = {"draft", "verified", "published"}
WARN_DAYS = 60      # 警告表示
DEMOTE_DAYS = 120   # 自動非表示(掲載基準v2 §4)
KPI_YELLOW = 0.80   # 撤退基準: 黄色(掲載基準v2 §5)
KPI_RED = 0.60      # 撤退基準: 赤


def days_since(iso):
    try:
        return (date.today() - datetime.strptime(iso, "%Y-%m-%d").date()).days
    except (TypeError, ValueError):
        return None


def check_url(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            final = r.geturl()
            moved = final.split("//", 1)[-1].split("/", 1)[0] != url.split("//", 1)[-1].split("/", 1)[0]
            return {"status": r.status, "moved_host": moved}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="120日超のpublishedをverifiedへ降格して保存")
    ap.add_argument("--check-urls", action="store_true", help="URL死活チェックも行う(要ネット接続)")
    args = ap.parse_args()

    db = json.loads(DB.read_text(encoding="utf-8"))
    services = db.get("services", [])
    problems, warnings, demoted, url_alerts = [], [], [], []

    for s in services:
        sid = s.get("service_id", "(idなし)")
        st = s.get("review_status")
        if st not in VALID_STATUS:
            problems.append(f"{sid}: review_status が不正 ({st!r})")
        if not s.get("data_source"):
            problems.append(f"{sid}: 出典URL(data_source)が空")
        if not s.get("last_verified"):
            problems.append(f"{sid}: 最終確認日(last_verified)が空")
        d = days_since(s.get("last_verified"))
        if s.get("last_verified") and d is None:
            problems.append(f"{sid}: last_verified の形式が不正 ({s.get('last_verified')!r})")
        if st == "published" and d is not None:
            if d > DEMOTE_DAYS:
                s["review_status"] = "verified"
                s.setdefault("notes", "")
                s["notes"] = (s["notes"] + f" [監査{date.today().isoformat()}: 最終確認{d}日超のため自動非表示]").strip()
                demoted.append(f"{sid}: {d}日未確認 → verified へ降格(非表示)")
            elif d > WARN_DAYS:
                warnings.append(f"{sid}: 最終確認から{d}日。再確認が必要")

    pub = [s for s in services if s.get("review_status") == "published"]
    # 注意: days_since は「今日確認」で 0 を返す。`or` で欠損値を代用すると 0 が偽扱いされ
    # 最新レコードを古い扱いにしてしまうため、None 判定は明示的に行う
    fresh = [
        s for s in pub
        if (lambda d: d is not None and d <= WARN_DAYS)(days_since(s.get("last_verified")))
    ]
    kpi = (len(fresh) / len(pub)) if pub else None
    if kpi is None:
        kpi_level = "対象なし(published 0件)"
    elif kpi < KPI_RED:
        kpi_level = "赤(60%未満): published全件の一時非表示を検討。掲載基準v2 §5"
    elif kpi < KPI_YELLOW:
        kpi_level = "黄(80%未満): 新規掲載を止めて再確認を優先。掲載基準v2 §5"
    else:
        kpi_level = "正常"

    if args.check_urls:
        seen = set()
        for s in services:
            for key in ("official_url", "application_url", "data_source"):
                url = s.get(key)
                if not url or url in seen:
                    continue
                seen.add(url)
                res = check_url(url)
                if res.get("status") != 200 or res.get("moved_host"):
                    url_alerts.append({"service_id": s.get("service_id"), "field": key,
                                       "url": url, **res,
                                       "action": "審査中(非表示)候補。人が確認する"})
                time.sleep(2)

    report = {
        "audited_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(services),
        "published": len(pub),
        "freshness_kpi_60d": round(kpi, 3) if kpi is not None else None,
        "freshness_level": kpi_level,
        "problems": problems, "warnings": warnings,
        "auto_demoted": demoted, "url_alerts": url_alerts,
        "note": "掲載基準v2 §7 の機械監査。auto_demoted は --fix 時のみ実際に保存される。",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.fix and demoted:
        db["updated_at"] = date.today().isoformat()
        DB.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"監査完了: 全{len(services)}件 / published {len(pub)}件 / 鮮度KPI: {kpi_level}")
    for line in problems + demoted + warnings:
        print(" -", line)
    for a in url_alerts:
        print(" - URL:", a["service_id"], a["url"], a.get("status"))

    if problems or (kpi is not None and kpi < KPI_YELLOW):
        return 2  # CIを赤くして気づかせる(撤退基準・データ不備)
    return 0


if __name__ == "__main__":
    sys.exit(main())
