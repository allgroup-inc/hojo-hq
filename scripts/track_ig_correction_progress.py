#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IG投稿修正進捗を追跡し、修正状況をレポートする。

対象:
- docs/修正計画_IG投稿_2026-10-03.md で定義した修正対象
- data/kpi/ig_posts.json の verification_status フィールド

出力:
- スタンダード: terminal に進捗サマリー
- --json: JSON 形式で進捗状況
- --send-report: Haruka へメール送信(オプション)
"""
import json
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent
IG_POSTS_FILE = REPO_ROOT / "data" / "kpi" / "ig_posts.json"
CORRECTION_PLAN_FILE = REPO_ROOT / "docs" / "修正計画_IG投稿_2026-10-03.md"


def load_ig_posts():
    """投稿実績ファイルを読み込み"""
    try:
        with open(IG_POSTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ エラー: {IG_POSTS_FILE} が読み込めません: {e}", file=sys.stderr)
        sys.exit(1)


def analyze_progress():
    """修正進捗を分析"""
    data = load_ig_posts()
    posts = data.get("posts", [])

    progress = {
        "total": len(posts),
        "緊急_完了": 0,
        "緊急_進行中": 0,
        "緊急_未着手": 0,
        "高優先_完了": 0,
        "高優先_進行中": 0,
        "高優先_未着手": 0,
        "標準_完了": 0,
        "標準_進行中": 0,
        "標準_未着手": 0,
        "問題なし": 0,
    }

    urgent_ids = {"ひとり親手当_⑨", "奨学給付金_私立_⑤", "電気代_⑩"}
    high_priority_ids = {"給付付き税額控除", "奨学給付金_高校_1"}

    items_by_priority = {
        "緊急": [],
        "高優先": [],
        "標準": [],
        "問題なし": []
    }

    for post in posts:
        no = post.get("no", "")
        title = post.get("title", "")
        status = post.get("verification_status", "")
        note = post.get("note", "")

        # ステータスを分類
        if status == "照合記録あり":
            priority = "問題なし"
            state = "完了"
            progress["問題なし"] += 1
        elif "修正中" in status:
            priority = "緊急"
            state = "進行中"
            progress["緊急_進行中"] += 1
        elif no in urgent_ids:
            if "完了" in note or "修正済み" in note:
                priority = "緊急"
                state = "完了"
                progress["緊急_完了"] += 1
            else:
                priority = "緊急"
                state = "未着手"
                progress["緊急_未着手"] += 1
        elif no in high_priority_ids:
            priority = "高優先"
            state = "未着手"
            progress["高優先_未着手"] += 1
        elif status == "確認_断定なし" or status == "確認_DB未照合":
            priority = "標準"
            state = "未着手"
            progress["標準_未着手"] += 1
        else:
            priority = "標準"
            state = "未着手"
            progress["標準_未着手"] += 1

        items_by_priority[priority].append({
            "no": no,
            "title": title,
            "status": status,
            "state": state,
            "note": note
        })

    return progress, items_by_priority


def print_report(progress, items_by_priority):
    """ターミナルにレポート出力"""
    print("\n" + "="*80)
    print("IG投稿修正進捗レポート — 2026-10-03")
    print("="*80 + "\n")

    # サマリー
    print("【全体進捗】")
    print(f"  総投稿数: {progress['total']}件")
    print(f"  問題なし: {progress['問題なし']}件 ✅")
    print(f"  緊急: 完了 {progress['緊急_完了']}件 / 進行中 {progress['緊急_進行中']}件 / 未着手 {progress['緊急_未着手']}件")
    print(f"  高優先: 完了 {progress['高優先_完了']}件 / 進行中 {progress['高優先_進行中']}件 / 未着手 {progress['高優先_未着手']}件")
    print(f"  標準: 完了 {progress['標準_完了']}件 / 進行中 {progress['標準_進行中']}件 / 未着手 {progress['標準_未着手']}件")
    print()

    # 優先度別詳細
    for priority in ["緊急", "高優先", "標準", "問題なし"]:
        items = items_by_priority.get(priority, [])
        if not items:
            continue

        icon = {"緊急": "🔴", "高優先": "🟡", "標準": "🟢", "問題なし": "✅"}[priority]
        print(f"{icon} 【{priority}】({len(items)}件)")

        for item in items:
            state_icon = {"完了": "✅", "進行中": "⏳", "未着手": "⭕"}[item["state"]]
            print(f"  {state_icon} {item['no']:20s} {item['title'][:40]}")
            if item['note']:
                print(f"     {item['note'][:70]}")
        print()

    # 次のステップ
    print("【次のステップ】")
    if progress['緊急_未着手'] > 0:
        print(f"  🔴 緊急修正が{progress['緊急_未着手']}件待機中。2026-10-05 までに完了予定")
    if progress['高優先_未着手'] > 0:
        print(f"  🟡 高優先確認が{progress['高優先_未着手']}件待機中。2026-10-10 までに確認予定")
    if progress['標準_未着手'] > 0:
        print(f"  🟢 標準優先が{progress['標準_未着手']}件待機中。2026-10-24 までに確認予定")

    print("\n見直し期限: 2026-10-24")
    print("="*80 + "\n")


def export_json(progress, items_by_priority):
    """JSON形式で出力"""
    report = {
        "generated_at": datetime.now().isoformat(),
        "progress": progress,
        "items_by_priority": items_by_priority
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    progress, items_by_priority = analyze_progress()

    if "--json" in sys.argv:
        export_json(progress, items_by_priority)
    else:
        print_report(progress, items_by_priority)


if __name__ == "__main__":
    main()
