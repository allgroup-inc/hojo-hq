#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seido.jsonのカテゴリ分布を分析"""
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent
SEIDO_FILE = BASE / "data" / "fukugiiro" / "seido.json"

with open(SEIDO_FILE, encoding="utf-8") as f:
    data = json.load(f)

items = data.get("items", [])

# カテゴリ別に集計
category_dist = defaultdict(lambda: {"total": 0, "verified": 0, "pending": 0})

for item in items:
    cat = item.get("category", "不明")
    status = item.get("status", "不明")

    category_dist[cat]["total"] += 1

    if status == "検証済み":
        category_dist[cat]["verified"] += 1
    elif status == "要確認":
        category_dist[cat]["pending"] += 1

# 結果表示
print("# カテゴリ別分布")
print(f"{'カテゴリ':<20} | {'全体':<5} | {'検証済み':<8} | {'要確認':<8} | {'その他':<8}")
print("-" * 70)

sorted_cats = sorted(category_dist.items(), key=lambda x: x[1]["pending"], reverse=True)
total_pending = 0

for cat, stats in sorted_cats:
    other = stats["total"] - stats["verified"] - stats["pending"]
    total_pending += stats["pending"]
    print(f"{cat:<20} | {stats['total']:<5} | {stats['verified']:<8} | {stats['pending']:<8} | {other:<8}")

print("-" * 70)
print(f"{'合計':<20} | {len(items):<5} | {sum(s['verified'] for s in category_dist.values()):<8} | {total_pending:<8}")
