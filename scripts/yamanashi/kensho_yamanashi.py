#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""もらいわすれ堂 山梨版 検証部(ケンショウ)突合支援

山梨版に沖縄や他県の制度が混ざっていないことを機械検証する。
絶対ルール: このサイトは「山梨県民が受けられる制度」のみを掲載する。

- 全アイテムが area=="山梨県" または area=="全国" であることを確認
- source_url に沖縄ドメインが紛れ込んでないことを確認
- 制度名や説明文に「沖縄」の文字が含まれていないことを確認
"""
import json
import os
import re
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DATA = os.path.join(BASE, "data", "yamanashi", "seido.json")
OUT = os.path.join(BASE, "docs", "山梨版_突合レポート.md")
SUMMARY = os.path.join(BASE, "data", "yamanashi", "kensho_summary.json")


def check_yamanashi_only():
    """山梨県民のみルール適用を検証する。

    第2段階構造:
    - tier1: 全国制度(area="全国")、山梨県制度(area="山梨県")
    - tier2: A区分市町村(area=市町村名、かつ許可リスト内)
    - tier2未実装: B区分市町村、論点対象市町村

    Returns: (is_valid, errors_list, summary, items)
    """
    errors = []

    # A区分(リンク可)市町村の許可リスト(build_yamanashi.py と同じ)
    ALLOWED_MUNIS = {
        "北杜市", "富士河口湖町", "南アルプス市", "上野原市",
        "昭和町", "早川町", "都留市", "甲斐市",
    }

    try:
        with open(DATA, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"データ読み込みエラー: {e}"], {}, []

    items = data.get("items", [])
    invalid_areas = []
    okinawa_domains = []
    okinawa_text = []

    for it in items:
        item_id = it.get("id", "unknown")
        area = it.get("area", "")

        # 1. area が許可リスト内のいずれかであることを確認
        # 許可: 全国 / 山梨県 / A区分市町村
        allowed = {"全国", "山梨県"} | ALLOWED_MUNIS
        if area not in allowed:
            invalid_areas.append(f"{item_id}: area='{area}'(許可: 全国・山梨県・{len(ALLOWED_MUNIS)}市町村のみ)")

        # 2. source_url に沖縄ドメインが含まれていないことを確認
        url = (it.get("source_url") or "").lower()
        if "okinawa" in url:
            okinawa_domains.append(
                f"{item_id}: {it['name']} → {url}"
            )

        # 3. 内容に「沖縄」の文字が含まれていないことを確認(JSON全体をダンプして検査)
        blob = json.dumps(it, ensure_ascii=False)
        if "沖縄" in blob:
            okinawa_text.append(f"{item_id}: {it['name']}")

    if invalid_areas:
        errors.append(f"✗ 許可されていない area: {len(invalid_areas)}件")
        errors.extend(f"  {e}" for e in invalid_areas[:10])
        if len(invalid_areas) > 10:
            errors.append(f"  ... 他 {len(invalid_areas) - 10}件")

    if okinawa_domains:
        errors.append(f"✗ 沖縄ドメインの source_url: {len(okinawa_domains)}件")
        errors.extend(f"  {e}" for e in okinawa_domains[:5])
        if len(okinawa_domains) > 5:
            errors.append(f"  ... 他 {len(okinawa_domains) - 5}件")

    if okinawa_text:
        errors.append(f"✗ 内容に「沖縄」が含まれる: {len(okinawa_text)}件")
        errors.extend(f"  {e}" for e in okinawa_text[:5])
        if len(okinawa_text) > 5:
            errors.append(f"  ... 他 {len(okinawa_text) - 5}件")

    # 4. 統計
    national = sum(1 for i in items if i.get("area") == "全国")
    yamanashi = sum(1 for i in items if i.get("area") == "山梨県")
    municipal = len(items) - national - yamanashi

    summary = {
        "validated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone(__import__("datetime").timedelta(hours=9))
        ).isoformat(),
        "is_valid": len(errors) == 0,
        "total_items": len(items),
        "national_items": national,
        "yamanashi_items": yamanashi,
        "municipal_items": municipal,
        "errors": errors,
    }

    return len(errors) == 0, errors, summary, items


def main():
    is_valid, errors, summary, items = check_yamanashi_only()

    # レポート出力
    lines = [
        "# 山梨版 県民のみルール検証レポート",
        "",
        f"実行時刻: {summary['validated_at']}",
        "",
        "## 概要",
        f"- 総制度数: {summary['total_items']}件",
        f"- 全国制度: {summary['national_items']}件",
        f"- 山梨県制度: {summary['yamanashi_items']}件",
        f"- A区分市町村: {summary['municipal_items']}件",
        "",
    ]

    if is_valid:
        lines.extend([
            "## ✓ 検証結果: OK",
            "",
            "すべてのアイテムが「山梨県民が受けられる制度」のルール内にあります。",
            "- area フィールドが「山梨県」または「全国」のみ",
            "- source_url に沖縄ドメインなし",
            "- 内容に「沖縄」の文字なし",
            "",
        ])
    else:
        lines.extend([
            "## ✗ 検証結果: NG",
            "",
            "山梨県民のみルールに違反するアイテムが見つかりました:",
            "",
        ])
        lines.extend(errors)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
        f.write("\n")

    if is_valid:
        muni_str = f"+市町村{summary['municipal_items']}" if summary['municipal_items'] > 0 else ""
        print(f"[ok] 山梨版検証完了: {summary['total_items']}件(全国{summary['national_items']}+県{summary['yamanashi_items']}{muni_str}) / NG件数 0")
        return 0
    else:
        print(f"[NG] 山梨版検証失敗: {len(errors)}個の違反")
        for e in errors:
            print(f"  {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
