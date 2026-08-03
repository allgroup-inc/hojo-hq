#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
受給報告を台帳(data/fukugiiro/jukyu_reports.json)に安全に追加する補助ツール。

北極星・第0階層(❷ 受給できた報告 1,000件)の運用を、手編集の事故なく回すための入口。
generate_jukyu_counter.py の検証器をそのまま使い、追加のたびに次を保証する:
  - 必須フィールド・語彙(amount_type/status/source)・日付形式・金額(0以上の整数)を検証
  - 個人が特定される情報(氏名・住所・電話・生年月日・メール)は受け付けない(守り部・PII最小化)
  - status=計上 は verified=true のときだけ(未検証の金額計上を禁止=正確性最優先)
  - seido_id は制度DB(seido.json)に存在するもののみ(検証済み前提)
検証に通らなければ台帳には一切書き込まない。通れば追記し、summary/phase を自動再計算する。

使い方(検証部ケンショウが、LINEで届いた自己申告を公式制度と突合したうえで実行):
  python scripts/add_jukyu_report.py \
      --seido-id fk-kuni-shussan-ichijikin --seido-name "出産育児一時金" \
      --area 那覇市 --amount-type 一時金 --amount-yen 500000 \
      --status 計上 --verified --verified-at 2026-08-10
  # まだ突合できていない/対象外なら:
  python scripts/add_jukyu_report.py ... --status 保留            (verified無し)
  # 実行せず内容だけ確認:
  python scripts/add_jukyu_report.py ... --dry-run

注意:
  - 金額は利用者の「おおよその自己申告」で構わない(概算)。名前・口座・住所は絶対に受け取らない/入力しない。
  - household_key は同一世帯の重複計上を避けたいときだけ、個人を特定しない匿名キー(例: 端末ハッシュ)を渡す。
"""
import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_jukyu_counter as gjc  # noqa: E402

DATA_PATH = gjc.DATA_PATH
# 引数として受け取ってはいけない個人情報の気配(値の中身も軽く走査する)
PII_HINT = ("氏名", "電話", "住所", "口座", "生年月日", "@")


def _next_id(reports):
    today = date.today().isoformat()
    n = sum(1 for r in reports if str(r.get("id", "")).startswith(f"jr-{today}")) + 1
    return f"jr-{today}-{n:02d}"


def build_record(args):
    rec = {
        "id": args.id or None,  # 後で採番
        "reported_at": args.reported_at or date.today().isoformat(),
        "seido_id": args.seido_id,
        "seido_name": args.seido_name,
        "area": args.area,
        "amount_type": args.amount_type,
        "amount_yen": args.amount_yen,
        "source": "自己申告",
        "verified": bool(args.verified),
        "status": args.status,
    }
    if args.cost_yen is not None:
        rec["cost_yen"] = args.cost_yen
    if args.verified_at:
        rec["verified_at"] = args.verified_at
    if args.household_key:
        rec["household_key"] = args.household_key
    return rec


def _pii_guard(rec):
    """値の中に個人情報の気配があれば止める(フィールド名は検証器が禁止済み。ここは値の保険)。"""
    hits = []
    for k, v in rec.items():
        if isinstance(v, str) and any(h in v for h in PII_HINT):
            hits.append(f"{k}={v!r}")
    return hits


def main():
    p = argparse.ArgumentParser(description="受給報告を台帳に安全に追加する")
    p.add_argument("--seido-id", required=True, help="制度ID(seido.json に存在するもの)")
    p.add_argument("--seido-name", required=True, help="制度名(表示用)")
    p.add_argument("--area", required=True, help="市町村など(例: 那覇市)。個人が特定される住所は不可")
    p.add_argument("--amount-type", required=True, choices=sorted(gjc.AMOUNT_TYPES), help="継続 / 一時金")
    p.add_argument("--amount-yen", required=True, type=int, help="おおよその受給額(円・自己申告)")
    p.add_argument("--status", required=True, choices=sorted(gjc.STATUSES), help="計上 / 保留 / 対象外")
    p.add_argument("--verified", action="store_true", help="検証部が公式制度と突合できた場合に付ける")
    p.add_argument("--verified-at", default=None, help="検証日 YYYY-MM-DD")
    p.add_argument("--reported-at", default=None, help="報告日 YYYY-MM-DD(既定: 今日)")
    p.add_argument("--cost-yen", type=int, default=None, help="かかった費用(任意・円)")
    p.add_argument("--household-key", default=None, help="匿名の世帯キー(任意・重複排除用。個人特定情報は不可)")
    p.add_argument("--id", default=None, help="ID を明示指定(既定: 自動採番 jr-YYYYMMDD-NN)")
    p.add_argument("--dry-run", action="store_true", help="書き込まず内容と検証結果のみ表示")
    args = p.parse_args()

    with open(DATA_PATH, encoding="utf-8") as f:
        ledger = json.load(f)

    rec = build_record(args)
    if not rec["id"]:
        rec["id"] = _next_id(ledger.get("reports", []))

    pii = _pii_guard(rec)
    if pii:
        print("[中止] 個人情報の気配を検知しました(値を修正してください):")
        for h in pii:
            print("   -", h)
        return 2

    candidate = json.loads(json.dumps(ledger))  # deep copy
    candidate.setdefault("reports", []).append(rec)

    errors = gjc.validate(candidate, gjc._load_seido_ids())
    if errors:
        print("[中止] 検証に失敗したため台帳には書き込みません:")
        for e in errors:
            print("   -", e)
        return 1

    print("追加する報告:")
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("(--dry-run のため書き込みませんでした)")
        return 0

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(candidate, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # summary / phase を検証器で正規に再計算(0件なら準備中のまま・計上があれば公開中へ)
    rc = gjc.run(write=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
