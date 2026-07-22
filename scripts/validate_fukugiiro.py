#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ 検証部(ケンショウさん)/ 守り部(マモリさん)ゲート
data/fukugiiro/seido.json をスキーマ・整合性・禁止表現の3層で機械検証する。
CI(fukugiiro-ci.yml)で毎push実行。エラーが1件でもあれば exit 1(=マージ不可=公開されない)。

方程式4(evalなき自動化は必ず事故る)の実装:
- --self-test でゴールデンセット(tests/golden_fukugiiro.json)を流し、
  「正例が通る・負例が落ちる」ことを毎回確認する。検証器自体の劣化を検知するためのeval。
"""
import json
import os
import re
import sys
from datetime import date, datetime

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE, "data", "fukugiiro", "seido.json")
GOLDEN_PATH = os.path.join(BASE, "tests", "golden_fukugiiro.json")

CATEGORIES = {"子育て", "住まい", "医療・健康", "教育", "仕事・失業", "生活支援", "介護", "防災・その他"}
LIFE_EVENTS = {"妊娠・出産", "子育て", "入園・入学", "就職・転職", "失業", "住宅取得・引越",
               "病気・けが", "介護", "障がい", "災害", "低所得・生活苦"}
DEADLINE_TYPES = {"常時", "期限あり", "年度内", "要確認"}
STATUSES = {"検証済み", "要確認", "終了"}
REQUIRED = ["id", "name", "category", "life_events", "issuer", "area", "target_household",
            "amount_note", "deadline_type", "how_to_apply", "source_url", "verified", "status"]

# マモリさんの禁止語リスト(変更はマモリさん審査+L2承認)
FORBIDDEN = ["必ずもらえる", "絶対", "審査なし", "誰でももらえる", "100%", "確実にもらえる", "無条件で支給"]
TEXT_FIELDS = ["name", "target_household", "amount_note", "notes"]

# 公的ドメイン(これ以外のsource_urlは警告)
PUBLIC_DOMAINS = (".go.jp", ".lg.jp", "pref.okinawa.jp", ".city.", ".town.", ".vill.")


def check_item(item, idx, today):
    """1エントリを検証し、(errors, warnings) を返す"""
    errors, warnings = [], []
    label = f"items[{idx}] ({item.get('id', '?')})"

    for key in REQUIRED:
        if key not in item or item[key] in ("", None) and key != "verified":
            errors.append(f"{label}: 必須フィールド '{key}' がない/空")

    if item.get("category") and item["category"] not in CATEGORIES:
        errors.append(f"{label}: category '{item['category']}' は語彙外")
    for ev in item.get("life_events", []):
        if ev not in LIFE_EVENTS:
            errors.append(f"{label}: life_event '{ev}' は語彙外")
    if not item.get("life_events"):
        errors.append(f"{label}: life_events が空")

    dt = item.get("deadline_type")
    if dt and dt not in DEADLINE_TYPES:
        errors.append(f"{label}: deadline_type '{dt}' は語彙外")
    if dt == "期限あり":
        d = item.get("deadline")
        if not d:
            errors.append(f"{label}: 期限あり なのに deadline がない")
        else:
            try:
                dd = datetime.strptime(d, "%Y-%m-%d").date()
                if dd < today and item.get("status") != "終了":
                    errors.append(f"{label}: deadline {d} は過去。status を『終了』にするか掲載を落とす")
            except ValueError:
                errors.append(f"{label}: deadline '{d}' は YYYY-MM-DD でない")

    url = item.get("source_url", "")
    if url and not url.startswith("https://"):
        errors.append(f"{label}: source_url が https でない")
    if url and not any(dom in url for dom in PUBLIC_DOMAINS):
        warnings.append(f"{label}: source_url が公的ドメイン外({url})— 守り部確認を推奨")

    if item.get("verified") is True:
        if not item.get("verified_at") or not item.get("verified_by"):
            errors.append(f"{label}: verified=true なのに verified_at/verified_by がない")
    else:
        if item.get("status") == "検証済み":
            errors.append(f"{label}: verified=false なのに status が『検証済み』")

    if item.get("status") and item["status"] not in STATUSES:
        errors.append(f"{label}: status '{item['status']}' は語彙外")

    for field in TEXT_FIELDS:
        text = item.get(field) or ""
        for word in FORBIDDEN:
            if word in text:
                errors.append(f"{label}: 禁止表現『{word}』が {field} に含まれる(マモリさんゲート)")

    return errors, warnings


def validate(data, today=None):
    """DB全体を検証し、(errors, warnings) を返す"""
    today = today or date.today()
    errors, warnings = [], []

    items = data.get("items")
    if items is None:
        return ["トップレベルに items がない"], []
    if data.get("count") != len(items):
        errors.append(f"count={data.get('count')} と items件数={len(items)} が不一致")

    seen = set()
    for idx, item in enumerate(items):
        iid = item.get("id")
        if iid in seen:
            errors.append(f"items[{idx}]: id '{iid}' が重複")
        seen.add(iid)
        e, w = check_item(item, idx, today)
        errors.extend(e)
        warnings.extend(w)
    return errors, warnings


def self_test():
    """ゴールデンセット: 正例が通り、負例が指定エラーで落ちることを確認する(検証器のeval)"""
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)
    today = datetime.strptime(golden["today"], "%Y-%m-%d").date()
    failed = 0
    for case in golden["cases"]:
        errors, _ = validate(case["data"], today=today)
        if case["expect"] == "pass" and errors:
            print(f"[SELF-TEST FAIL] {case['name']}: 正例なのにエラー: {errors}")
            failed += 1
        elif case["expect"] == "fail":
            if not errors:
                print(f"[SELF-TEST FAIL] {case['name']}: 負例なのに通過した")
                failed += 1
            elif case.get("must_contain") and not any(case["must_contain"] in e for e in errors):
                print(f"[SELF-TEST FAIL] {case['name']}: 期待した検出『{case['must_contain']}』が出ていない: {errors}")
                failed += 1
    total = len(golden["cases"])
    print(f"self-test: {total - failed}/{total} 合格")
    return failed == 0


def main():
    if "--self-test" in sys.argv:
        ok = self_test()
        if not ok:
            sys.exit(1)

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    errors, warnings = validate(data)

    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[ERROR] {e}")
    print(f"検証完了: {len(data.get('items', []))}件 / エラー {len(errors)} / 警告 {len(warnings)}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
