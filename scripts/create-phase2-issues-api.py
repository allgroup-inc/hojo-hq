#!/usr/bin/env python3
"""
Phase 2 GitHub Issues REST API 直接作成ツール
環境変数 GITHUB_TOKEN が必須
"""

import json
import urllib.request
import urllib.error
import os
import sys
from pathlib import Path

def load_issues():
    """PHASE2-ISSUES-JSON.json から Issue 定義を読み込み"""
    issues_file = Path(__file__).parent.parent / "docs/kakehashi-poc/PHASE2-ISSUES-JSON.json"
    with open(issues_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_milestone_id(token, repo_owner, repo_name, milestone_title):
    """マイルストーン名から ID を取得"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/milestones"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            milestones = json.loads(response.read().decode('utf-8'))
            for m in milestones:
                if m['title'] == milestone_title:
                    return m['number']
        return None
    except Exception as e:
        print(f"  ⚠️  マイルストーン取得失敗: {e}")
        return None

def create_issue_api(token, repo_owner, repo_name, title, body, labels, milestone_id):
    """GitHub REST API で Issue 作成"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"

    data = {
        "title": title,
        "body": body,
        "labels": labels,
    }

    if milestone_id:
        data["milestone"] = milestone_id

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
            return result.get('number'), result.get('html_url')
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"  ❌ API エラー ({e.code})")
        try:
            error_json = json.loads(error_body)
            if 'message' in error_json:
                print(f"     {error_json['message']}")
        except:
            print(f"     {error_body[:200]}")
        return None, None

def main():
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ エラー: GITHUB_TOKEN 環境変数が設定されていません")
        return 1

    issues_data = load_issues()
    metadata = issues_data['metadata']
    issues = issues_data['issues']

    repo = metadata['repo']
    repo_owner, repo_name = repo.split('/')
    milestone_title = metadata['milestone']

    print(f"🚀 Phase 2 GitHub Issues REST API 作成開始")
    print(f"   リポジトリ: {repo}")
    print(f"   マイルストーン: {milestone_title}")
    print(f"   Issue 数: {len(issues)}")
    print(f"   認証: GITHUB_TOKEN ✓")
    print("")

    # マイルストーン ID 取得
    print("🔍 マイルストーン取得中...")
    milestone_id = get_milestone_id(token, repo_owner, repo_name, milestone_title)
    if milestone_id:
        print(f"   ✅ マイルストーン ID: {milestone_id}")
    else:
        print(f"   ⚠️  マイルストーン '{milestone_title}' が見つかりません (手動作成が必要)")
        print(f"      GitHub リポジトリ → Issues → Milestones → New milestone")
        print("")
    print("")

    created_count = 0
    failed_count = 0
    issue_map = {}

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

        print(f"📌 Issue #{issue_num}: {title[:50]}...", end=" ", flush=True)

        created_num, url = create_issue_api(
            token, repo_owner, repo_name, title, body, labels, milestone_id
        )

        if created_num:
            issue_map[issue_num] = (created_num, url)
            print(f"✅ #{created_num}")
            created_count += 1
        else:
            print(f"❌")
            failed_count += 1

    # 結果表示
    print("")
    print("=" * 70)
    print(f"✅ インポート完了: {created_count} / {len(issues)} issue 作成")
    if failed_count > 0:
        print(f"❌ エラー: {failed_count} issue の作成に失敗")
    print("")

    if issue_map:
        print("📊 作成済み Issue:")
        for def_num in sorted(issue_map.keys()):
            created_num, url = issue_map[def_num]
            print(f"   #{def_num:2d} → #{created_num} ({url})")

    print("")
    print(f"🎯 GitHub Projects で進捗追跡:")
    print(f"   https://github.com/{repo}/projects")
    print("")

    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
