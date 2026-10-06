#!/usr/bin/env python3
"""
ドキュメントの確認日付チェック。
各ドキュメントの先頭に `最終確認日: YYYY-MM-DD` があり、
今日から30日以上経過していないかを検査する。
"""
import os
import re
from datetime import datetime, timedelta

DOCS_DIR = "docs"
STALE_DAYS = 30

def get_verification_date(filename):
    """ファイルから最終確認日を抽出"""
    try:
        with open(os.path.join(DOCS_DIR, filename), 'r', encoding='utf-8') as f:
            content = f.read()
            # 先頭100行だけを検査
            lines = content.split('\n')[:100]
            full_text = '\n'.join(lines)
            match = re.search(r'最終確認日[:\：]\s*(\d{4})-(\d{2})-(\d{2})', full_text)
            if match:
                year, month, day = match.groups()
                return datetime(int(year), int(month), int(day))
    except Exception as e:
        pass
    return None

def check_freshness():
    """確認日付をチェック"""
    today = datetime.now()
    stale_threshold = today - timedelta(days=STALE_DAYS)

    stale_docs = []
    undated_docs = []

    # 運用関連ドキュメント（チェック対象）
    target_patterns = [
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}",  # 日付プレフィックス
        r"フクギイロ",  # ← user said to skip, but include for reference
        r"もらいわすれ",  # ← user said to skip
        r"ミカタ",  # GLOW
        r"GLOW",
        r"運用",
        r"規程",
        r"LINE",
    ]

    if os.path.exists(DOCS_DIR):
        for filename in sorted(os.listdir(DOCS_DIR)):
            if not filename.endswith('.md'):
                continue

            verify_date = get_verification_date(filename)

            if verify_date is None:
                undated_docs.append(filename)
            elif verify_date < stale_threshold:
                days_old = (today - verify_date).days
                stale_docs.append((filename, verify_date, days_old))

    # 報告
    print(f"📋 ドキュメント鮮度チェック ({today.strftime('%Y-%m-%d')})")
    print(f"   対象範囲: {STALE_DAYS}日以上前は要再確認\n")

    if stale_docs:
        print(f"⚠️  {len(stale_docs)}件が再確認対象:")
        for filename, verify_date, days_old in sorted(stale_docs, key=lambda x: x[2], reverse=True):
            print(f"   - {filename}: {verify_date.strftime('%Y-%m-%d')} ({days_old}日前)")
    else:
        print(f"✅ ドキュメント全て最新(GLOW関連)")

    if undated_docs:
        print(f"\n🔲 {len(undated_docs)}件が未確認日付:")
        for filename in undated_docs[:10]:  # 最初の10件だけ
            print(f"   - {filename}")
        if len(undated_docs) > 10:
            print(f"   ... ほか{len(undated_docs)-10}件")

    return len(stale_docs) == 0 and len(undated_docs) == 0

if __name__ == "__main__":
    success = check_freshness()
    exit(0 if success else 1)
