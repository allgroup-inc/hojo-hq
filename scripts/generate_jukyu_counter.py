#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ 実受給額カウンター 生成/検証(ソロバン×ケンショウ ゲート)

北極星・第0階層(受給実感 = 実受給額累計・受給世帯数)を可視化するための集計器。
data/fukugiiro/jukyu_reports.json の reports を検証し、
「検証済み(verified=true)かつ status=計上」の報告だけを summary に積み上げる。

方針(docs/フクギイロ_計測レポート設計.md §3・絶対ルール1「正確性最優先」):
- 未検証・保留・対象外の報告は絶対に金額へ計上しない(誇張防止)
- 金額はすべて利用者の自己申告。summary には検証部が突合できたぶんのみ。
- 個人が特定される項目は台帳に持たない(氏名・住所・電話・生年月日は禁止フィールド)

使い方:
  python scripts/generate_jukyu_counter.py            # 検証して summary を再計算し書き戻す
  python scripts/generate_jukyu_counter.py --check    # 検証のみ(書き込まない)。CIゲート用
  python scripts/generate_jukyu_counter.py --self-test # ゴールデンセットで検証器自体をeval

方程式4(evalなき自動化は必ず事故る)の実装として --self-test を必須CIに載せる。
"""
import json
import os
import re
import sys
from datetime import date

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE, "data", "fukugiiro", "jukyu_reports.json")
SEIDO_PATH = os.path.join(BASE, "data", "fukugiiro", "seido.json")
GOLDEN_PATH = os.path.join(BASE, "tests", "golden_jukyu.json")

REQUIRED_REPORT = [
    "id", "reported_at", "seido_id", "seido_name", "area",
    "amount_type", "amount_yen", "source", "verified", "status",
]
AMOUNT_TYPES = {"継続", "一時金"}
STATUSES = {"計上", "保留", "対象外"}
SOURCES = {"自己申告"}
# 個人が特定される情報は台帳に持たない(守り部・個人情報最小化)
FORBIDDEN_FIELDS = {"name", "氏名", "address", "住所", "tel", "phone", "電話", "birth", "生年月日", "email"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_seido_ids():
    """seido.json が読めれば掲載制度IDの集合を返す(照合用)。読めなければ None。"""
    try:
        with open(SEIDO_PATH, encoding="utf-8") as f:
            db = json.load(f)
        return {it.get("id") for it in db.get("items", []) if it.get("id")}
    except Exception:
        return None


def validate(ledger, seido_ids=None):
    """台帳を検証し errors のリストを返す(空ならOK)。"""
    errors = []
    if not isinstance(ledger, dict):
        return ["ルートがオブジェクトでない"]

    if not isinstance(ledger.get("reports"), list):
        errors.append("reports が配列でない")
        return errors

    seen_ids = set()
    for idx, r in enumerate(ledger["reports"]):
        label = f"reports[{idx}] ({r.get('id', '?') if isinstance(r, dict) else '?'})"
        if not isinstance(r, dict):
            errors.append(f"{label}: オブジェクトでない")
            continue

        for key in REQUIRED_REPORT:
            if key not in r or r[key] in ("", None):
                errors.append(f"{label}: 必須フィールド '{key}' がない/空")

        # 個人情報の混入禁止
        for bad in FORBIDDEN_FIELDS:
            if bad in r:
                errors.append(f"{label}: 禁止フィールド '{bad}'(個人情報は台帳に持たない)")

        rid = r.get("id")
        if rid in seen_ids:
            errors.append(f"{label}: id が重複")
        seen_ids.add(rid)

        for df in ("reported_at", "verified_at"):
            if r.get(df) and not DATE_RE.match(str(r[df])):
                errors.append(f"{label}: {df} は YYYY-MM-DD 形式(値: {r[df]})")

        if r.get("amount_type") and r["amount_type"] not in AMOUNT_TYPES:
            errors.append(f"{label}: amount_type '{r['amount_type']}' は語彙外")
        if r.get("status") and r["status"] not in STATUSES:
            errors.append(f"{label}: status '{r['status']}' は語彙外")
        if r.get("source") and r["source"] not in SOURCES:
            errors.append(f"{label}: source '{r['source']}' は語彙外")

        amt = r.get("amount_yen")
        if not isinstance(amt, int) or isinstance(amt, bool) or amt < 0:
            errors.append(f"{label}: amount_yen は0以上の整数(値: {amt})")
        cost = r.get("cost_yen")
        if cost is not None and (not isinstance(cost, int) or isinstance(cost, bool) or cost < 0):
            errors.append(f"{label}: cost_yen は0以上の整数(値: {cost})")

        if not isinstance(r.get("verified"), bool):
            errors.append(f"{label}: verified は真偽値")

        # 計上するなら検証済みでなければならない(未検証の金額計上を防ぐ)
        if r.get("status") == "計上" and r.get("verified") is not True:
            errors.append(f"{label}: status=計上 なのに verified=true でない(未検証の計上は禁止)")

        # seido.json と照合できるなら未知IDを警告(検証済み前提の整合)
        if seido_ids is not None and r.get("seido_id") and r["seido_id"] not in seido_ids:
            errors.append(f"{label}: seido_id '{r['seido_id']}' が制度DBに存在しない")

    return errors


def aggregate(ledger):
    """検証済み・計上ぶんだけを積算した summary を返す(updated_at 以外)。"""
    total = 0
    households = set()
    seido = set()
    counted = 0
    for i, r in enumerate(ledger.get("reports", [])):
        if r.get("verified") is True and r.get("status") == "計上":
            total += int(r.get("amount_yen", 0))
            # 匿名の世帯キー(あれば)で重複排除。無ければ報告単位で数える。
            hk = r.get("household_key") or f"__report_{r.get('id', i)}"
            households.add(hk)
            if r.get("seido_id"):
                seido.add(r["seido_id"])
            counted += 1
    return {
        "total_amount_yen": total,
        "household_count": len(households),
        "seido_count": len(seido),
        "counted_reports": counted,
    }


def run(write=True):
    with open(DATA_PATH, encoding="utf-8") as f:
        ledger = json.load(f)

    errors = validate(ledger, _load_seido_ids())
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        print(f"受給報告台帳の検証に失敗: {len(errors)}件")
        return 1

    agg = aggregate(ledger)
    counted = agg.pop("counted_reports")
    summary = ledger.get("summary", {})
    summary.update(agg)
    if counted > 0:
        summary["updated_at"] = date.today().isoformat()
        ledger["phase"] = "公開中"
        summary["note"] = "検証部が公式制度と突合できた受給報告のみを計上しています。"
    else:
        # 実績ゼロのあいだは金額を誇張しない。準備中のまま正直に出す。
        summary.setdefault("updated_at", None)
        ledger["phase"] = "受付準備中"
    ledger["summary"] = summary

    if write:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print(
        "受給報告台帳 OK: "
        f"計上{counted}件 / 累計{summary['total_amount_yen']:,}円 / "
        f"{summary['household_count']}世帯 / {summary['seido_count']}制度"
    )
    return 0


def self_test():
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)

    failed = 0
    for case in golden["cases"]:
        errors = validate(case["ledger"])  # seido照合は自己テストでは行わない
        ok = (len(errors) == 0)
        if ok != case["valid"]:
            failed += 1
            print(f"[SELFTEST FAIL] {case['name']}: expected valid={case['valid']} got {ok}")
            for e in errors:
                print(f"    - {e}")
            continue
        if case["valid"] and "expect" in case:
            agg = aggregate(case["ledger"])
            for k, v in case["expect"].items():
                if agg.get(k) != v:
                    failed += 1
                    print(f"[SELFTEST FAIL] {case['name']}: {k} expected {v} got {agg.get(k)}")

    total = len(golden["cases"])
    if failed:
        print(f"自己テスト失敗: {failed}/{total}")
        return 1
    print(f"自己テスト OK: {total}件(正例通過・負例排除・集計一致)")
    return 0


def main():
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if "--check" in sys.argv:
        sys.exit(run(write=False))
    sys.exit(run(write=True))


if __name__ == "__main__":
    main()
