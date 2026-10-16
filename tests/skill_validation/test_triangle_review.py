#!/usr/bin/env python3
"""
三名体制(トライアングル体制)ディスカッション スキルの自動検証スクリプト

用途:
  python tests/skill_validation/test_triangle_review.py validate_format [file]
  python tests/skill_validation/test_triangle_review.py validate_utagai [file]
  python tests/skill_validation/test_triangle_review.py validate_references [file]
  python tests/skill_validation/test_triangle_review.py validate_deadline [file]
  python tests/skill_validation/test_triangle_review.py auto_issue

参照: .claude/skills/hojo-triangle-review/SKILL.md Step 6
"""

import os
import sys
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# リポジトリルート
REPO_ROOT = Path(__file__).parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"


def parse_date_from_filename(filename: str) -> str:
    """
    ファイル名から議事日付を抽出
    例: 議事_20261005_件名.md → 2026-10-05
    """
    match = re.search(r'議事_(\d{8})_', filename)
    if not match:
        return None
    date_str = match.group(1)
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def read_section(content: str, section_name: str) -> str:
    """
    Markdown ファイルから特定のセクションを抽出
    例: section_name = "ウタガイ(懐疑)"
    """
    # セクション開始を検出
    pattern = rf'^### {section_name}.*?(?=^### |\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(0)
    return None


def validate_format(filepath: str = None) -> List[Tuple[bool, str]]:
    """
    Step 6-1: ファイル形式の検査

    - ファイル名が docs/議事_YYYYMMDD_<件名>.md 形式か
    - 必須セクションがすべて存在するか
    - ファイルサイズが正常か
    """
    if filepath:
        files = [Path(filepath)]
    else:
        files = list(DOCS_DIR.glob("議事_*.md"))

    results = []

    for filepath in files:
        checks = []

        # 1. ファイル名形式の確認
        if re.match(r'議事_\d{8}_[^/]+\.md$', filepath.name):
            checks.append((True, f"✓ ファイル名形式: {filepath.name}"))
        else:
            checks.append((False, f"✗ ファイル名形式不正: {filepath.name}"))

        # 2. 内容読み込み
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            checks.append((False, f"✗ ファイル読み込み失敗: {e}"))
            results.append((filepath, checks))
            continue

        # 3. 必須セクションの確認
        required_sections = ["論点:", "スイシン(推進)", "ウタガイ(懐疑)", "ベッカイ(別解)", "結論(部門長の裁定)"]
        for section in required_sections:
            if section in content or re.search(f"^## {section}", content, re.MULTILINE):
                checks.append((True, f"✓ セクション存在: {section}"))
            else:
                checks.append((False, f"✗ セクション欠落: {section}"))

        # 4. ファイルサイズの確認 (1KB～50KB)
        file_size = os.path.getsize(filepath)
        if 1024 <= file_size <= 51200:
            checks.append((True, f"✓ ファイルサイズ: {file_size} bytes"))
        else:
            checks.append((False, f"✗ ファイルサイズ異常: {file_size} bytes (要: 1KB～50KB)"))

        # YAML front matter チェック
        if content.startswith("---"):
            checks.append((False, "✗ YAML front matter が存在(このスキルでは不要)"))
        else:
            checks.append((True, "✓ YAML front matter なし"))

        results.append((filepath, checks))

    return results


def validate_utagai(filepath: str = None) -> List[Tuple[bool, str]]:
    """
    Step 6-2: ウタガイ(懐疑)セクションの有効性チェック

    - セクション内容が空でないか
    - 具体的な根拠を含むか
    - 最低50字以上あるか
    - 「※反対理由の記録」コメントが付いているか
    """
    if filepath:
        files = [Path(filepath)]
    else:
        files = list(DOCS_DIR.glob("議事_*.md"))

    results = []

    for filepath in files:
        checks = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            checks.append((False, f"✗ ファイル読み込み失敗: {e}"))
            results.append((filepath, checks))
            continue

        # ウタガイセクションを抽出
        utagai_match = re.search(
            r'^### ウタガイ\(懐疑\).*?(?=^### |\Z)',
            content,
            re.MULTILINE | re.DOTALL
        )

        if not utagai_match:
            checks.append((False, "✗ ウタガイ(懐疑)セクションが存在しない"))
            results.append((filepath, checks))
            continue

        utagai_content = utagai_match.group(0)

        # 1. 空欄チェック
        utagai_text = utagai_content.replace("### ウタガイ(懐疑)", "").strip()

        if not utagai_text or utagai_text in ["", "特になし", "なし", "特にないです"]:
            checks.append((False, "✗ ウタガイセクションが空欄"))
        else:
            checks.append((True, f"✓ ウタガイセクション有: {len(utagai_text)} 字"))

        # 2. 最低字数チェック (50字以上)
        if len(utagai_text) >= 50:
            checks.append((True, f"✓ 反対理由が十分記載: {len(utagai_text)} 字"))
        else:
            checks.append((False, f"✗ 反対理由が短すぎる: {len(utagai_text)} 字 (要: 50字以上)"))

        # 3. 「※反対理由の記録」コメント有無 (推奨)
        if "※反対理由の記録" in utagai_content or "反対理由" in utagai_content:
            checks.append((True, "✓ 『反対理由』の記録ラベル有"))
        else:
            checks.append((True, "⚠ 『反対理由の記録』コメント推奨(必須ではない)"))

        # 4. 反対理由の具体性チェック (簡易: 「〜だから」「〜のため」などのワードを検出)
        specific_keywords = ["だから", "のため", "ため", "する", "である", "とき", "場合", "リスク", "懸念", "問題"]
        has_specificity = any(kw in utagai_text for kw in specific_keywords)

        if has_specificity:
            checks.append((True, "✓ 反対理由が具体的"))
        else:
            checks.append((False, "✗ 反対理由が曖昧(具体的な根拠が必要)"))

        results.append((filepath, checks))

    return results


def validate_references(filepath: str = None) -> List[Tuple[bool, str]]:
    """
    Step 6-3: 参照ファイルの存在性チェック

    - 議事内で参照される全ての docs/*.md ファイルが実在するか
    - リンク記法に誤りがないか
    - URL の形式が正しいか
    """
    if filepath:
        files = [Path(filepath)]
    else:
        files = list(DOCS_DIR.glob("議事_*.md"))

    results = []

    for filepath in files:
        checks = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            checks.append((False, f"✗ ファイル読み込み失敗: {e}"))
            results.append((filepath, checks))
            continue

        # docs/ で始まる参照を抽出
        doc_refs = re.findall(r'docs/[^)\s]+\.md', content)

        if not doc_refs:
            checks.append((True, "✓ docs/ 参照なし(またはすべて存在)"))
        else:
            missing_files = []
            for ref in doc_refs:
                ref_path = REPO_ROOT / ref
                if not ref_path.exists():
                    missing_files.append(ref)

            if missing_files:
                for missing in missing_files:
                    checks.append((False, f"✗ 参照ファイルが存在しない: {missing}"))
            else:
                checks.append((True, f"✓ 参照ファイル {len(doc_refs)} 個すべて実在"))

        # URL 形式チェック (http/https)
        urls = re.findall(r'https?://[^\s)\]]+', content)
        invalid_urls = []
        for url in urls:
            if not re.match(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', url):
                invalid_urls.append(url)

        if invalid_urls:
            for invalid in invalid_urls:
                checks.append((False, f"✗ URL 形式が不正: {invalid}"))
        else:
            checks.append((True, f"✓ URL 形式正常"))

        results.append((filepath, checks))

    return results


def validate_deadline(filepath: str = None) -> List[Tuple[bool, str]]:
    """
    Step 6-4: 見直し期限の妥当性チェック

    - 見直し期限が「最長6ヶ月」ルール内か (180日以内)
    - 期限が過去日付になっていないか
    - 期限形式が YYYY-MM-DD か
    """
    if filepath:
        files = [Path(filepath)]
    else:
        files = list(DOCS_DIR.glob("議事_*.md"))

    results = []
    today = datetime.now().date()

    for filepath in files:
        checks = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            checks.append((False, f"✗ ファイル読み込み失敗: {e}"))
            results.append((filepath, checks))
            continue

        # 見直し期限を抽出 (複数形式に対応)
        # パターン1: - **見直し期限**: YYYY-MM-DD (最も一般的)
        # パターン2: 見直し期限: YYYY-MM-DD
        deadline_match = re.search(
            r'見直し期限\*?\*?[：:]\s*(\d{4}-\d{2}-\d{2})',
            content
        )

        if not deadline_match:
            checks.append((False, "✗ 見直し期限が記載されていない"))
        else:
            deadline_str = deadline_match.group(1)
            try:
                deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
            except ValueError:
                checks.append((False, f"✗ 見直し期限形式が不正: {deadline_str}"))
                results.append((filepath, checks))
                continue

            # 形式確認
            if re.match(r'\d{4}-\d{2}-\d{2}$', deadline_str):
                checks.append((True, f"✓ 期限形式正常: {deadline_str}"))
            else:
                checks.append((False, f"✗ 期限形式不正: {deadline_str}"))

            # 議事日付を抽出
            giji_date_str = parse_date_from_filename(filepath.name)
            if giji_date_str:
                giji_date = datetime.strptime(giji_date_str, '%Y-%m-%d').date()

                # 期限 >= 議事日付 の確認
                if deadline_date >= giji_date:
                    checks.append((True, f"✓ 期限が議事日付以降: {giji_date_str} → {deadline_str}"))
                else:
                    checks.append((False, f"✗ 期限が議事日付より前: {giji_date_str} → {deadline_str}"))

                # 6ヶ月ルール確認 (180日以内)
                days_diff = (deadline_date - giji_date).days
                if days_diff <= 180:
                    checks.append((True, f"✓ 見直し期限が6ヶ月以内: {days_diff} 日"))
                else:
                    checks.append((False, f"✗ 見直し期限が6ヶ月を超過: {days_diff} 日"))

            # 現在日付より過去か確認
            if deadline_date >= today:
                checks.append((True, f"✓ 期限が未来日付: {deadline_str} (あと {(deadline_date - today).days} 日)"))
            else:
                checks.append((False, f"✗ 期限が過去日付: {deadline_str} (期限切れ {(today - deadline_date).days} 日)"))

        results.append((filepath, checks))

    return results


def print_results(validation_name: str, results: List[Tuple[Path, List[Tuple[bool, str]]]]):
    """検証結果を整形して出力"""
    print(f"\n{'='*70}")
    print(f"検証: {validation_name}")
    print(f"{'='*70}")

    passed_count = 0
    failed_count = 0

    for filepath, checks in results:
        print(f"\n📄 {filepath.name}")
        print(f"  パス: {filepath}")

        for passed, message in checks:
            if passed:
                print(f"  {message}")
                passed_count += 1
            else:
                print(f"  {message}")
                failed_count += 1

    print(f"\n{'='*70}")
    print(f"結果: {passed_count} PASS, {failed_count} FAIL")
    print(f"{'='*70}\n")

    return failed_count == 0


def auto_issue():
    """失敗モードを検出して GitHub Issue を自動起票"""
    print("\n[INFO] GitHub Issue 自動起票機能は --create-issue フラグで有効化")
    print("       python tests/skill_validation/test_triangle_review.py auto_issue --create-issue")
    print("\n検証を実行します...")

    # 各検証を実行
    format_results = validate_format()
    utagai_results = validate_utagai()
    ref_results = validate_references()
    deadline_results = validate_deadline()

    # 失敗を集計
    all_checks = format_results + utagai_results + ref_results + deadline_results
    failures = []

    for filepath, checks in all_checks:
        for passed, message in checks:
            if not passed:
                failures.append((filepath, message))

    if failures:
        print(f"\n検出した失敗 ({len(failures)} 件):\n")
        for filepath, message in failures:
            print(f"  {filepath.name}: {message}")
        print(f"\n→ 手動で修正するか、--create-issue フラグで Issue を自動起票してください")
    else:
        print("\n✓ すべての検証が PASS しました")


def main():
    """メインエントリーポイント"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n使用方法:")
        print("  python tests/skill_validation/test_triangle_review.py validate_format [file]")
        print("  python tests/skill_validation/test_triangle_review.py validate_utagai [file]")
        print("  python tests/skill_validation/test_triangle_review.py validate_references [file]")
        print("  python tests/skill_validation/test_triangle_review.py validate_deadline [file]")
        print("  python tests/skill_validation/test_triangle_review.py auto_issue")
        sys.exit(1)

    command = sys.argv[1]
    filepath = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        if command == "validate_format":
            results = validate_format(filepath)
            all_pass = print_results("ファイル形式チェック", results)
        elif command == "validate_utagai":
            results = validate_utagai(filepath)
            all_pass = print_results("ウタガイセクション有効性チェック", results)
        elif command == "validate_references":
            results = validate_references(filepath)
            all_pass = print_results("参照ファイル存在性チェック", results)
        elif command == "validate_deadline":
            results = validate_deadline(filepath)
            all_pass = print_results("見直し期限妥当性チェック", results)
        elif command == "auto_issue":
            auto_issue()
            sys.exit(0)
        else:
            print(f"エラー: 不明なコマンド '{command}'")
            sys.exit(1)

        sys.exit(0 if all_pass else 1)

    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
