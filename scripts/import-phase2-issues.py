#!/usr/bin/env python3
"""
Phase 2 GitHub Issues インポートツール
使用法: python3 scripts/import-phase2-issues.py

前提条件:
  - gh CLI がインストール・認証済み
  - GitHub Personal Access Token (リポジトリ作成権限) が設定済み
  - または GitHub CLI が auth済みの状態
"""

import json
import subprocess
import sys
from pathlib import Path

def load_issues():
    """PHASE2-ISSUES-JSON.json から Issue 定義を読み込み"""
    issues_file = Path(__file__).parent.parent / "docs/kakehashi-poc/PHASE2-ISSUES-JSON.json"
    with open(issues_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_issue_gh_cli(repo, title, body, labels, milestone, blockers_str=""):
    """gh CLI を使用して Issue を作成"""
    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
        "--milestone", milestone,
    ]

    if labels:
        for label in labels:
            cmd.extend(["--label", label])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Issue URL から Issue 番号を抽出
        output = result.stdout.strip()
        if "/" in output:
            issue_num = output.split("/")[-1]
            return int(issue_num)
        return None
    except subprocess.CalledProcessError as e:
        print(f"  ❌ 作成失敗: {e.stderr}")
        return None

def create_issue_api(token, repo_owner, repo_name, title, body, labels, milestone):
    """GitHub REST API を使用して Issue を作成 (token 認証)"""
    import urllib.request
    import urllib.error

    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"

    data = {
        "title": title,
        "body": body,
        "labels": labels,
        "milestone": None,  # milestone は ID が必要なため、作成後に手動で設定
    }

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('number')
    except urllib.error.HTTPError as e:
        print(f"  ❌ API エラー ({e.code}): {e.read().decode('utf-8')}")
        return None

def main():
    issues_data = load_issues()
    metadata = issues_data['metadata']
    issues = issues_data['issues']

    repo = metadata['repo']
    repo_owner, repo_name = repo.split('/')
    milestone = metadata['milestone']

    print(f"🚀 Phase 2 GitHub Issues インポート開始")
    print(f"   リポジトリ: {repo}")
    print(f"   マイルストーン: {milestone}")
    print(f"   Issue 数: {len(issues)}")
    print("")

    # gh CLI の可用性チェック
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
        use_gh_cli = True
        print("✅ gh CLI が利用可能です。gh CLI を使用して作成します。")
    except (FileNotFoundError, subprocess.CalledProcessError):
        use_gh_cli = False
        print("⚠️  gh CLI が利用不可です。")
        print("   次のいずれかを実施してください:")
        print("   1. gh CLI をインストール: https://cli.github.com")
        print("   2. GitHub Web UI で手動作成: https://github.com/{}/issues/new".format(repo))
        print("   3. PHASE2-ISSUES-JSON.json を使用して別ツールでインポート")
        print("")
        return 1

    created_count = 0
    failed_count = 0
    issue_map = {}  # issue_num -> created_issue_num のマッピング

    for issue in issues:
        issue_num = issue['number']
        title = issue['title']
        body = issue['body']
        labels = issue.get('labels', [])
        blockers = issue.get('blockers', [])

        # body にブロッカー情報を追加
        if blockers:
            blocker_links = ", ".join([f"#{b}" for b in blockers])
            body = f"{body}\n\n**依存Issue**: {blocker_links}"

        print(f"📌 Issue #{issue_num}: {title[:50]}...")

        if use_gh_cli:
            created_num = create_issue_gh_cli(repo, title, body, labels, milestone)
            if created_num:
                issue_map[issue_num] = created_num
                print(f"   ✅ 作成成功 → Issue #{created_num}")
                created_count += 1
            else:
                print(f"   ⚠️  作成失敗 (詳細は上を参照)")
                failed_count += 1

        print("")

    # 結果表示
    print("=" * 60)
    print(f"✅ インポート完了: {created_count} / {len(issues)} issue 作成")
    if failed_count > 0:
        print(f"❌ エラー: {failed_count} issue の作成に失敗")
    print("")
    print("📊 作成済み Issue:")
    for issue_num, created_num in sorted(issue_map.items()):
        print(f"   定義 #{issue_num:2d} → GitHub #{created_num}")
    print("")
    print(f"🎯 GitHub Projects で進捗追跡: https://github.com/{repo}/projects")
    print("")

    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
