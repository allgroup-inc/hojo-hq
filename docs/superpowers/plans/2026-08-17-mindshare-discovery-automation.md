# mindshare-arbitrage「発見」自動化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 毎朝、Reddit/Hacker Newsからネタ候補を自動収集し、Claude APIでスコア化・要約した上で、GitHub Issueにチェックボックス形式でレビュー待ちとして提示する。

**Architecture:** `scripts/discover_trends.py` が収集・スコアリング・保存の全ロジックを持つ単一スクリプト(既存の`verify_sources.py`と同じ構成方針)。`.github/workflows/discover-trends.yml` が毎朝6:00 JSTに実行し、`gh issue create`でIssueを起票する(`healthcheck.yml`と同じパターン)。

**Tech Stack:** Python 3.12、`anthropic` SDK(Claude API)、標準ライブラリ`urllib.request`(Reddit/HN取得。追加依存を増やさない)、GitHub Actions、`gh` CLI

## Global Constraints

- モデルは `claude-haiku-4-5`(既存 `scripts/verify_sources.py` と同じ。`CLAUDE_MODEL`定数として定義)
- `ANTHROPIC_API_KEY`が未設定の場合はClaude採点をスキップし、生の候補一覧のみをIssueに出す(既存`verify_sources.py`の「キー未設定時は従来動作」と同じ設計思想)
- Reddit/Hacker Newsの取得は認証不要の公開APIのみ使用し、追加のAPIキー・Secretsは不要
- 各ソースの取得件数は上位10件までに絞る(Claude API呼び出しコストを抑えるため)
- `data/discovery_candidates.json` は同日再実行で上書きされるべき込みで(件idempotent)、日付をキーにした辞書構造で保存する(過去日分は残す)
- Issueは日ごとに新規作成する(healthcheck.ymlのような「未解決なら追記」方式は使わない。理由: 候補は日替わりで意味が変わるため)
- 本番のIssue起票・LINE通知は `.github/workflows/discover-trends.yml` からのみ実行され、このリポジトリでのpushイベント等では実行しない(誤発火防止)

---

### Task 1: データ収集(Reddit/Hacker News)

**Files:**
- Create: `scripts/discover_trends.py`
- Create: `data/discovery_candidates.json`(空の初期構造 `{}`)

**Interfaces:**
- Produces:
  - `fetch_reddit(subreddits: list[str], limit: int = 10) -> list[dict]` — 各dictは `{"source": "reddit", "title": str, "url": str, "score": int, "created_utc": float, "subreddit": str}`
  - `fetch_hackernews(limit: int = 10) -> list[dict]` — 各dictは `{"source": "hackernews", "title": str, "url": str, "score": int, "created_utc": float}`

- [ ] **Step 1: `fetch_hackernews`を実装する**

`scripts/discover_trends.py` を新規作成し、以下を書く:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq SNS部/note編集部 — ネタ発見(Discovery)自動化
Reddit/Hacker Newsからネタ候補を収集し、Claude APIでスコア化・要約して
GitHub Issue起票用のデータを作る(mindshare-arbitrageスキルの①発見段階)。

出力:
  data/discovery_candidates.json ... 収集履歴(日付キー、べき等)
  discovery_issue_body.md        ... Issue本文(ワークフローがgh issue createで使う)
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "discovery_candidates.json")
ISSUE_BODY_PATH = os.path.join(BASE_DIR, "..", "discovery_issue_body.md")
CLAUDE_MODEL = "claude-haiku-4-5"
PER_SOURCE_LIMIT = 10
USER_AGENT = "hojo-hq-discovery-bot/1.0"


def _http_get_json(url: str, headers: dict | None = None) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[warn] fetch failed: {url}: {e}")
        return None


def fetch_hackernews(limit: int = PER_SOURCE_LIMIT) -> list[dict]:
    ids = _http_get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not ids:
        return []
    out = []
    for item_id in ids[: limit * 2]:  # 取得失敗を見込んで多めに引く
        item = _http_get_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
        if not item or item.get("type") != "story" or not item.get("title"):
            continue
        out.append({
            "source": "hackernews",
            "title": item["title"],
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
            "score": item.get("score", 0),
            "created_utc": float(item.get("time", 0)),
        })
        if len(out) >= limit:
            break
    return out


def fetch_reddit(subreddits: list[str], limit: int = PER_SOURCE_LIMIT) -> list[dict]:
    out = []
    per_sub = max(1, limit // max(1, len(subreddits)))
    for sub in subreddits:
        data = _http_get_json(
            f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={per_sub}"
        )
        if not data:
            continue
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            if not d.get("title"):
                continue
            out.append({
                "source": "reddit",
                "title": d["title"],
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "score": d.get("score", 0),
                "created_utc": float(d.get("created_utc", 0)),
                "subreddit": sub,
            })
    return out


if __name__ == "__main__":
    hn = fetch_hackernews()
    rd = fetch_reddit(["smallbusiness", "marketing"])
    print(f"[ok] hackernews={len(hn)}件 reddit={len(rd)}件")
```

- [ ] **Step 2: `data/discovery_candidates.json`の初期ファイルを作る**

```bash
echo '{}' > /home/user/hojo-hq/data/discovery_candidates.json
```

- [ ] **Step 3: 実行して収集結果を確認する**

```bash
cd /home/user/hojo-hq && python3 scripts/discover_trends.py
```

Expected: `[ok] hackernews=N件 reddit=M件` が出力され、N・Mともに0より大きい
(ネットワークが通っていれば)。ネットワークエラーの場合は `[warn] fetch failed` が
出て件数は0になるが、スクリプト自体はエラー終了しないことを確認する。

- [ ] **Step 4: 動作確認用に、取得した候補の中身を1件printして目視確認する**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from discover_trends import fetch_hackernews, fetch_reddit
hn = fetch_hackernews()
print(hn[0] if hn else 'no hn results')
"
```

Expected: `title` `url` `score` `created_utc` を含む辞書が1件表示される。

- [ ] **Step 5: コミット**

```bash
cd /home/user/hojo-hq
git add scripts/discover_trends.py data/discovery_candidates.json
git commit -m "feat: Reddit/Hacker Newsからのネタ候補収集を実装"
```

---

### Task 2: Claude APIでのスコア化・要約・重複除外

**Files:**
- Modify: `scripts/discover_trends.py`

**Interfaces:**
- Consumes: Task 1の `fetch_hackernews() -> list[dict]`, `fetch_reddit(subreddits, limit) -> list[dict]`(各dictの`title`/`url`/`score`/`created_utc`キー)
- Produces:
  - `score_and_summarize(candidates: list[dict], client) -> list[dict]` — 各dictに`claude_score`(0〜10のfloat)と`summary_ja`(日本語要約1〜2文)を追加して返す。`client`が`None`の場合は`claude_score=None, summary_ja=None`のまま返す(採点スキップ)
  - `dedupe(candidates: list[dict], seen_urls: set[str]) -> list[dict]` — `seen_urls`に無いものだけを残す
  - `load_history() -> dict`, `save_history(history: dict) -> None` — `data/discovery_candidates.json`の読み書き(日付キー)

- [ ] **Step 1: `score_and_summarize`のプロンプト構築部分を書く(まずAPI呼び出し無しで検証できる形にする)**

`scripts/discover_trends.py` の末尾(`if __name__`より前)に追加:

```python
def build_score_prompt(candidates: list[dict]) -> str:
    lines = []
    for i, c in enumerate(candidates):
        lines.append(f"{i}. [{c['source']}] {c['title']} (score={c['score']})")
    listing = "\n".join(lines)
    return f"""以下は英語圏の話題候補一覧です。沖縄の中小企業経営者向けSNS発信の
ネタとして使えそうか、それぞれ0〜10のスコアと日本語1〜2文の要約を付けてください。
「新しさ」「経営者にとっての実用性」を重視してください。誇大な断定はしないでください。

{listing}

出力は次のJSON配列のみ(説明文不要): [{{"index": 0, "score": 7.5, "summary_ja": "..."}}]
"""


def parse_score_response(text: str, n: int) -> list[dict]:
    """Claudeの応答テキストからJSON配列を取り出してパースする。失敗時は空リスト。"""
    try:
        start = text.index("[")
        end = text.rindex("]") + 1
        parsed = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return []
    out = [None] * n
    for entry in parsed:
        idx = entry.get("index")
        if isinstance(idx, int) and 0 <= idx < n:
            out[idx] = {"score": entry.get("score"), "summary_ja": entry.get("summary_ja")}
    return out


def score_and_summarize(candidates: list[dict], client) -> list[dict]:
    if not candidates:
        return []
    if client is None:
        for c in candidates:
            c["claude_score"] = None
            c["summary_ja"] = None
        return candidates
    prompt = build_score_prompt(candidates)
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    results = parse_score_response(text, len(candidates))
    for c, r in zip(candidates, results):
        c["claude_score"] = r["score"] if r else None
        c["summary_ja"] = r["summary_ja"] if r else None
    return candidates


def dedupe(candidates: list[dict], seen_urls: set[str]) -> list[dict]:
    return [c for c in candidates if c["url"] not in seen_urls]


def load_history() -> dict:
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=1)
```

- [ ] **Step 2: `parse_score_response`をネットワーク無しで検証する**

このリポジトリにはPythonの自動テスト基盤(pytest等)が無い(`scripts/verify_sources.py`等の
既存スクリプトも同様に手動確認方式)。同じ方針で、実際にスクリプトを対話的に動かして
確認する:

```bash
cd /home/user/hojo-hq && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from discover_trends import parse_score_response

sample = '[{\"index\": 0, \"score\": 8.0, \"summary_ja\": \"テスト要約\"}]'
result = parse_score_response(sample, 1)
assert result[0]['score'] == 8.0
assert result[0]['summary_ja'] == 'テスト要約'

broken = parse_score_response('説明文のみでJSONが無い応答', 1)
assert broken == [None]

print('[ok] parse_score_response 動作確認OK')
"
```

Expected: `[ok] parse_score_response 動作確認OK` が出力される(異常系: JSON抽出失敗時に
例外を投げず`[None]`を返すことも確認済み)。

- [ ] **Step 3: `dedupe`を検証する**

```bash
cd /home/user/hojo-hq && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from discover_trends import dedupe

candidates = [{'url': 'https://a.com'}, {'url': 'https://b.com'}]
result = dedupe(candidates, seen_urls={'https://a.com'})
assert len(result) == 1
assert result[0]['url'] == 'https://b.com'
print('[ok] dedupe 動作確認OK')
"
```

Expected: `[ok] dedupe 動作確認OK` が出力される。

- [ ] **Step 4: `score_and_summarize`をclient無し(採点スキップ)経路で確認する**

```bash
cd /home/user/hojo-hq && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from discover_trends import score_and_summarize

candidates = [{'title': 'test', 'url': 'https://a.com', 'score': 1, 'source': 'hackernews'}]
result = score_and_summarize(candidates, client=None)
assert result[0]['claude_score'] is None
assert result[0]['summary_ja'] is None
print('[ok] score_and_summarize(client=None) 動作確認OK')
"
```

Expected: `[ok] score_and_summarize(client=None) 動作確認OK` が出力される。

**注記(このセッションでは確認できない範囲)**: `client`が実際に渡された場合の
Claude API呼び出し自体(`client.messages.create`)は、このサンドボックス環境に
`ANTHROPIC_API_KEY`が無く`anthropic`パッケージも未インストールのため、ここでは
実行確認できない。`scripts/verify_sources.py`の既存のClaude呼び出し部分と同じ
`anthropic.Anthropic()`クライアントの使い方に揃えてあるため、実際の動作確認は
Task 3のワークフロー本番実行時(Secretsが設定されたGitHub Actions環境)で行う。

- [ ] **Step 5: コミット**

```bash
cd /home/user/hojo-hq
git add scripts/discover_trends.py
git commit -m "feat: Claude APIでのスコア化・要約・重複除外を実装"
```

---

### Task 3: Issue起票・ワークフロー化

**Files:**
- Modify: `scripts/discover_trends.py`(`main()`関数を追加)
- Create: `.github/workflows/discover-trends.yml`

**Interfaces:**
- Consumes: Task 1・Task 2の全関数
- Produces: `build_issue_body(candidates: list[dict], today: str) -> str`、`main() -> None`

- [ ] **Step 1: `build_issue_body`と`main`を実装する**

`scripts/discover_trends.py` の末尾(`if __name__`の直前)に追加:

```python
def build_issue_body(candidates: list[dict], today: str) -> str:
    lines = [f"## 本日の候補({today})", ""]
    if not candidates:
        lines.append("(本日は候補がありませんでした)")
    else:
        ranked = sorted(
            candidates,
            key=lambda c: c.get("claude_score") if c.get("claude_score") is not None else c.get("score", 0),
            reverse=True,
        )
        for c in ranked:
            score_label = f"スコア: {c['claude_score']}" if c.get("claude_score") is not None else f"元スコア: {c['score']}"
            lines.append(f"- [ ] **{c['title']}**({score_label}) — 出典: {c['url']}")
            if c.get("summary_ja"):
                lines.append(f"  要約: {c['summary_ja']}")
    lines.append("")
    lines.append("チェックを入れた候補が、次回のSNS/note生成の題材候補になります。")
    return "\n".join(lines)


def main() -> None:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    history = load_history()
    seen_urls = {c["url"] for day in history.values() for c in day.get("candidates", [])}

    hn = fetch_hackernews()
    rd = fetch_reddit(["smallbusiness", "marketing"])
    all_candidates = dedupe(hn + rd, seen_urls)

    client = None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    else:
        print("[info] ANTHROPIC_API_KEY未設定: スコア化をスキップ(生の候補一覧のみ)")

    scored = score_and_summarize(all_candidates, client)

    history[today] = {"candidates": scored}
    save_history(history)

    body = build_issue_body(scored, today)
    with open(ISSUE_BODY_PATH, "w", encoding="utf-8") as f:
        f.write(body)

    print(f"[ok] {len(scored)}件の候補を{ISSUE_BODY_PATH}に出力しました")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: `build_issue_body`を確認する**

```bash
cd /home/user/hojo-hq && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from discover_trends import build_issue_body

candidates = [
    {'title': 'A', 'url': 'https://a.com', 'score': 10, 'claude_score': 8.5, 'summary_ja': '要約A'},
    {'title': 'B', 'url': 'https://b.com', 'score': 5, 'claude_score': None, 'summary_ja': None},
]
body = build_issue_body(candidates, '2026-08-17')
assert '## 本日の候補(2026-08-17)' in body
assert '- [ ] **A**(スコア: 8.5)' in body
assert '要約: 要約A' in body
assert '- [ ] **B**(元スコア: 5)' in body
print('[ok] build_issue_body 動作確認OK')
print(body)
"
```

Expected: `[ok] build_issue_body 動作確認OK` の後にIssue本文サンプルが表示される。

- [ ] **Step 3: `main()`を実際に実行して最終出力を確認する**

```bash
cd /home/user/hojo-hq && python3 scripts/discover_trends.py
cat discovery_issue_body.md
cat data/discovery_candidates.json | python3 -m json.tool | head -20
```

Expected: `[ok] N件の候補を...に出力しました` が表示され、`discovery_issue_body.md`に
Task 3 Step 2で確認した形式のIssue本文が、`data/discovery_candidates.json`に
本日日付キーの候補データが入っている。

- [ ] **Step 4: ワークフローファイルを作る**

`.github/workflows/discover-trends.yml` を新規作成:

```yaml
name: discover-trends

# SNS部/note編集部: 毎朝ネタ候補(Reddit/Hacker News)を自動収集し、Claude APIで
# スコア化・要約した上でGitHub Issueにチェックボックス形式で起票する
# (mindshare-arbitrageスキルの①発見段階)。

on:
  schedule:
    # JST 6:00(= UTC 前日21:00)
    - cron: "0 21 * * *"
  workflow_dispatch: {}

permissions:
  contents: write
  issues: write

concurrency:
  group: discover-trends
  cancel-in-progress: false

jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"

      - name: 依存インストール
        run: pip install anthropic

      - name: ネタ候補を収集・スコア化
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python scripts/discover_trends.py

      - name: Issueを起票
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -e
          gh label create discovery --color 0E8A16 \
            --description "ネタ発見(Discovery)の日次候補" 2>/dev/null || true
          gh issue create --label discovery \
            --title "💡 本日のネタ候補($(date -u -d '+9 hours' '+%Y-%m-%d'))" \
            --body-file discovery_issue_body.md

      - name: LINE通知(任意・Secrets未設定時はスキップ)
        if: ${{ vars.DISCOVERY_LINE_NOTIFY == 'true' }}
        uses: ./.github/actions/line-notify
        with:
          channel-access-token: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          to-user-id: ${{ secrets.LINE_ADMIN_USER_ID }}
          message: |
            💡【ミカタ】本日のネタ候補ができました
            ${{ github.server_url }}/${{ github.repository }}/issues

      - name: 収集データをコミット
        run: |
          git config user.name "hojo-hq-bot"
          git config user.email "bot@en-life.co.jp"
          git add data/discovery_candidates.json
          git diff --cached --quiet || git commit -m "auto: ネタ候補収集 $(date -u -d '+9 hours' '+%Y-%m-%d')"
          for i in 1 2 3; do
            git pull --rebase -X theirs origin main && git push && break
            git rebase --abort 2>/dev/null || true
            echo "push retry $i"; sleep 5
          done
```

- [ ] **Step 5: YAML構文を確認する**

```bash
python3 -c "import yaml; yaml.safe_load(open('/home/user/hojo-hq/.github/workflows/discover-trends.yml'))" && echo "[ok] YAML構文OK"
```

Expected: `[ok] YAML構文OK` が出力される(pyyamlが無ければ`pip install pyyaml`してから実行)。

- [ ] **Step 6: 生成された一時ファイルを`.gitignore`に追加する**

`discovery_issue_body.md`はワークフロー実行時の中間生成物なのでコミット対象にしない:

```bash
echo "" >> /home/user/hojo-hq/.gitignore
echo "# ネタ発見ワークフローの中間生成物" >> /home/user/hojo-hq/.gitignore
echo "discovery_issue_body.md" >> /home/user/hojo-hq/.gitignore
git -C /home/user/hojo-hq status --short | grep discovery_issue_body || echo "[ok] gitignore反映済み(untrackedに出ない)"
```

- [ ] **Step 7: コミット**

```bash
cd /home/user/hojo-hq
rm -f discovery_issue_body.md
git add scripts/discover_trends.py .github/workflows/discover-trends.yml .gitignore
git commit -m "feat: ネタ候補のIssue起票ワークフローを追加"
```

---

## Self-Review Notes

- Spec coverage: design docの「2. 全体の流れ」(収集→スコア化→保存→Issue起票→任意LINE通知)は
  Task 1(収集)・Task 2(スコア化・保存)・Task 3(Issue起票・ワークフロー)でカバーしている。
  「3. データ収集の詳細」(Reddit/HN・認証不要・上位10件・重複除外)もTask 1・2で反映済み。
  「4. Issue起票の形式」はTask 3の`build_issue_body`で反映
- LINE通知は設計書で「任意」としたため、`vars.DISCOVERY_LINE_NOTIFY`という明示的なON/OFF
  フラグを設け、デフォルトでは送らない設計にした(既存のhealthcheck.yml等は失敗時に常時
  通知するが、今回は「候補ができました」という日常的な通知なので、要否を選べる方が良い
  と判断。小柳さんが不要と感じれば`vars`を設定しないだけで良い)
- Claude API呼び出し自体(実際のネットワーク経由の`messages.create`)はこのセッションでは
  検証不能なため、Task 2で明記の上、パース・分岐ロジックのみ手動確認とした。本番動作確認は
  ワークフロー初回実行(`workflow_dispatch`)時に行う
- このリポジトリにPythonの自動テスト基盤が無いため、既存の`verify_sources.py`等と同じ
  「スクリプトを実際に実行して出力を確認する」方式を踏襲した(pytestを新規導入すると
  この1スクリプトだけ浮いてしまうため見送り)
