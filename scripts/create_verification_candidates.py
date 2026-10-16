#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 1検証: 高優先度要確認アイテムから検証候補を特定"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE = Path(__file__).parent.parent
SEIDO_FILE = BASE / "data" / "fukugiiro" / "seido.json"
REPORT_FILE = BASE / "docs" / "フクギイロ_Phase1検証候補一覧.md"

HIGH_PRIORITY_CATEGORIES = {"医療・健康", "生活支援", "子育て"}


def load_seido():
    with open(SEIDO_FILE, encoding="utf-8") as f:
        return json.load(f)


def is_verification_ready(item):
    """アイテムが検証に必要なデータをすべて持っているか判定"""
    checks = {
        "有効なID": bool(item.get("id")),
        "制度名": bool(item.get("name")),
        "カテゴリ": bool(item.get("category")),
        "source_url": bool(item.get("source_url")),
        "対象世帯記載": bool(item.get("target_household")) and "要確認" not in item.get("target_household", ""),
        "申請方法記載": bool(item.get("how_to_apply")),
    }
    return all(checks.values()), checks


def main():
    now = datetime.now(JST)

    data = load_seido()
    items = data.get("items", [])

    # 高優先度の要確認アイテムを抽出
    candidates = []
    incomplete = []

    for item in items:
        if (item.get("status") == "要確認" and
            item.get("category") in HIGH_PRIORITY_CATEGORIES):

            ready, checks = is_verification_ready(item)

            if ready:
                candidates.append(item)
            else:
                incomplete.append((item, checks))

    # レポート生成
    report = f"""# フクギイロ Phase 1検証候補一覧

**実施日**: {now.strftime("%Y-%m-%d %H:%M")}
**対象**: 高優先度要確認アイテム（医療・健康、生活支援、子育て）

## サマリー

| 項目 | 件数 |
|---|---|
| **検証対象** | {len(candidates) + len(incomplete)} |
| **検証準備完了** | {len(candidates)} |
| **データ不完全** | {len(incomplete)} |
| **検証進捗** | {100*len(candidates)//(len(candidates)+len(incomplete))}% |

---

## ✅ 検証準備完了 ({len(candidates)}件)

以下のアイテムは必須データがすべて揃っており、小柳さんの「検証OK」判定で即座に「検証済み」へ昇格可能です。

"""

    by_category = {}
    for item in candidates:
        cat = item.get("category")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)

    for cat in sorted(by_category.keys()):
        items_cat = by_category[cat]
        report += f"\n### {cat} ({len(items_cat)}件)\n\n"

        for item in sorted(items_cat, key=lambda x: x.get("name", "")):
            name = item.get("name", "")
            item_id = item.get("id", "")
            deadline = item.get("deadline", "")
            deadline_type = item.get("deadline_type", "")
            area = item.get("area", "")

            report += f"**{name}**\n"
            report += f"- ID: `{item_id}`\n"
            report += f"- 対象地域: {area}\n"
            report += f"- 対象世帯: {item.get('target_household', '')}\n"
            report += f"- 申請窓口: {item.get('how_to_apply', '')}\n"
            report += f"- 出典: {item.get('source_url', '')}\n"
            report += f"- 締切: {deadline_type}"
            if deadline:
                report += f" ({deadline})"
            report += "\n\n"

    if incomplete:
        report += f"""
---

## ⚠️ データ不完全 ({len(incomplete)}件)

以下のアイテムはデータが不完全のため、事前に情報補充が必要です。

"""
        for item, checks in sorted(incomplete, key=lambda x: x[0].get("name", "")):
            name = item.get("name", "")
            item_id = item.get("id", "")
            missing = [k for k, v in checks.items() if not v]

            report += f"**{name}** (`{item_id}`)\n"
            report += f"- 不足: {', '.join(missing)}\n\n"

    report += f"""
---

## 次ステップ (2026-10-23)

1. **検証準備完了({len(candidates)}件)**
   - 小柳さんの「検証OK」判定をご依頼ください
   - 判定後、自動で「検証済み」へ昇格します
   - 目標到達: 検証済み {116 + len(candidates)}件 ({100*(116+len(candidates))//265}%)

2. **データ不完全({len(incomplete)}件)**
   - 検証部(kensho.md)で情報補充を実施
   - 次週の検証対象へ

## KGI進捗

**検証済み率**: {116}件 (43.8%) → 目標 160件(60%+)
**必要追加検証**: {44}件
**本レポート対象**: {len(candidates)}件
**達成見込み**: {116+len(candidates)}件 ({100*(116+len(candidates))//265}%)

---

実施者: Claude (自動分析)
前回: 2026-10-16 検証エラー0件化
"""

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"""
[result] Phase 1検証候補リスト作成完了
  対象: {len(candidates) + len(incomplete)}件
  ✅ 検証準備完了: {len(candidates)}件
  ⚠️ データ不完全: {len(incomplete)}件

  レポート: {REPORT_FILE}
  推奨: {len(candidates)}件を小柳さんの判定対象へ
""")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
