# スキル改善プロジェクト実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** hojo-hq専用15個スキルの実行性・可視性・ローカル検証を3本柱で改善し、update-skills.sh経由で13リポジトリ全体に自動配布。結果として全チャットセッションのスキル品質が向上する。

**Architecture:** 
- 週1-3: スキル群を5個/週に分割。各スキルについてSKILL.md手順化 → 実装例追加 → 失敗通知・Issue起票仕組み実装 → ローカル検証手順追加。
- 週4: 統合テスト・全リポ配布確認 → ドキュメント統合 → CLAUDE.md再発防止メモ更新。
- 配布メカニズム: `scripts/update-skills.sh` で hojo-hq → MARKETING_REPOS(6) + INFRA_REPOS(7) へ自動push。各リポで `.claude/skills/` 配下に反映。

**Tech Stack:**
- Skill framework: CLAUDE.md形式のSKILL.md(Markdown)
- CI/検証: GitHub Actions + bash scripts
- 検証二重化: Claude + Gemini(マルチAI連携ガイド参照)
- Issue自動起票: GitHub API (`gh api POST /repos/...`)

**Spec:** docs/部品庫.md (§C スキル配置・配布メカニズム) / docs/マルチAI連携セットアップガイド.md (検証要件) / CLAUDE.md (再発防止メモ§16)

---

## Global Constraints

| 制約 | 詳細 | 根拠 |
|---|---|---|
| スキル配布対象リポ固定 | MARKETING_REPOS: hojo-hq hikari-hq hikari-lp hikari-report kakei-hq okinawa-villa / INFRA_REPOS: report-hq go allgroup-site enlife-mikomi skl-venue-hq hojo-signal kakei-crm = **計13リポ** | scripts/update-skills.sh 39-40行 |
| 改善対象スキル数 | hojo-hq専用15個が最優先。以降カスタマイズ層スキル10個へ拡大（検証後）。 | Brainstorming確認: docs/全体マップ.md |
| 自動配布トリガー | update-skills.sh は手動実行(Routine化は2026-11-01検証後)。改善スキルの各commit後、本計画の§配布確認フェーズで一括実行。 | docs/部品庫.md§C「配布の自動cron化」 |
| マルチAI検証 | verify-sources型スキルはClaudeとGemini両者で検証し、片方NGなら「要確認」扱い | CLAUDE.md「マルチAI連携」+スキル確認 |
| 議事文書 | 改善判定が分かれた場合は docs/議事_YYYYMMDD_<件名>.md に3役形式で記録 | CLAUDE.md「三名体制」8号 |
| 再発防止メモ | 同じ失敗が2度起きたら CLAUDE.md末尾「再発防止メモ」に1行足す | CLAUDE.md「再発防止メモ」冒頭 |

---

## Review Focus

スキル改善で最も失敗しやすい5つの入力・条件。テストで各項目をカバー:

1. **スキルチェーン失敗**: あるスキル改善が別スキル（例: humanizer → resilient-agent-design）に参照されていて、片方が古いままだと矛盾。→ Task 2-4で依存マップ作成・検証
2. **配布漏れ**: update-skills.sh の sync 対象リストから誤って除外したスキル → 一部リポだけ古いまま。→ Task 5で全リポ配布リスト自動生成・検査
3. **マルチAI検証の片手落ち**: Claude検証は通したがGemini検査を省いた場合、verify-sources型の誤りが本番へ通る。→ Task 3-4でGemini並行実行を明記
4. **SKILL.md形式の逆行**: 手順セクション(`## Step`)を「1アクション=1ステップ」に統一したはずなのに、新しい改善で「複数アクションを1ステップに詰める」と回帰。→ Task 1-3で形式チェック自動化スクリプト作成
5. **再発防止メモの忘却**: 同じ失敗が起きたのに CLAUDE.md へ記録し忘れ、次の改善サイクルで同じミスを繰り返す。→ Task 6で自動抽出・記録フロー実装

---

## File Structure

```
.claude/skills/
├── <15個スキル>/
│   ├── SKILL.md              (改善対象：手順化・実装例・失敗通知・ローカル検証セクション)
│   ├── scripts/              (既存；改善なし)
│   ├── references/           (既存；必要なら補足例追加)
│   └── tests/                (NEW: ローカル検証用テスト)
│
tests/
├── skill_validation/         (NEW: スキルテストフレーム)
│   ├── test_step_format.py   (SKILL.md形式チェック)
│   ├── test_dependencies.py  (スキルチェーン検証)
│   └── test_gemini_check.py  (Gemini並行検証ダミー)
│
scripts/
├── validate_skill_format.sh  (NEW: 全スキルのSKILL.md形式検査)
├── distribute_skills.sh      (既存 update-skills.sh のラッパー；全リポ配布)
└── check_distribution.sh     (NEW: 全13リポで実際に反映されたか検査)
│
.github/workflows/
├── skill-validation.yml      (NEW: PR時に全スキルを検査)
└── skill-distribution.yml    (NEW: main へのマージ後に全リポ配布)
│
docs/
├── superpowers/plans/
│   └── 2026-10-04-skill-improvement-project.md (本計画)
│
├── 議事_20261004_スキル改善プロジェクト開始.md (NEW: 3役確認)
├── スキル改善進捗_2026Qx.md (NEW: 週次進捗記録)
└── スキル依存マップ.md (NEW: スキルA→B参照の依存グラフ)
```

---

# 実装フェーズ

## Phase 1: 基盤整備 (Week 1, 10/04-10/10)

### Task 1-1: スキルチェーン依存マップ作成

**Files:**
- Create: `docs/スキル依存マップ.md`
- Create: `tests/skill_validation/test_dependencies.py`

**Interfaces:**
- Consumes: `.claude/skills/*/SKILL.md` (全15個スキルのdescription欄から参照関係を抽出)
- Produces: スキル依存グラフ (dict: {スキル名 → [参照先スキル...]}), テストケース

**Steps:**

- [ ] **Step 1: スキル依存マップ抽出スクリプト作成**

スクリプト `scripts/extract_skill_dependencies.py`:
```python
import os, re
from pathlib import Path

def extract_dependencies(skill_dir):
    """
    .claude/skills/ 配下の全スキルからdescriptionと本体を読む。
    descriptionで「このスキルはXYZスキルと連携」のような記述を grep。
    戻り値: {スキル名: [参照先スキル...]}
    """
    skills = {}
    for skill_path in Path(skill_dir).iterdir():
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding='utf-8')
                # YAML frontmatter から description を抽出
                match = re.search(r'^description:\s*(.+?)(?:\n|$)', content, re.MULTILINE)
                if match:
                    desc = match.group(1)
                    # 他スキル名を grep (参照=スキル名が / で囲まれている)
                    refs = re.findall(r'/(\w+-\w+)/', desc)
                    skills[skill_path.name] = refs
    return skills
```

ローカル実行: `python scripts/extract_skill_dependencies.py .claude/skills/`

- [ ] **Step 2: スキル依存マップを Markdown として出力**

実行結果を `docs/スキル依存マップ.md` に保存:
```markdown
# スキル依存マップ (2026-10-04)

| スキル | 参照先スキル | 説明 |
|---|---|---|
| humanizer | writing-plans | 明確な文体出力のための計画フレーム |
| resilient-agent-design | humanizer | スキル設計の人間らしさ |
| ... |
```

- [ ] **Step 3: 依存テストケース作成**

`tests/skill_validation/test_dependencies.py`:
```python
def test_all_referenced_skills_exist():
    """参照先スキルが全て .claude/skills/ に存在するか検査"""
    deps = extract_dependencies('.claude/skills')
    for skill, refs in deps.items():
        for ref in refs:
            assert Path(f'.claude/skills/{ref}/SKILL.md').exists(), \
                f"{skill} が参照する {ref} が見つかりません"

def test_no_circular_dependencies():
    """A→B→A のような循環参照がないか検査"""
    deps = extract_dependencies('.claude/skills')
    visited = set()
    def has_cycle(skill, path):
        if skill in path:
            return True
        if skill in visited:
            return False
        visited.add(skill)
        for ref in deps.get(skill, []):
            if has_cycle(ref, path + [skill]):
                return True
        return False
    
    for skill in deps:
        assert not has_cycle(skill, []), f"{skill} から循環参照があります"
```

- [ ] **Step 4: テスト実行確認**

```bash
cd /home/user/hojo-hq
pytest tests/skill_validation/test_dependencies.py -v
```

Expected: PASS (全15スキルの依存が検査される)

- [ ] **Step 5: Commit**

```bash
git add docs/スキル依存マップ.md \
        tests/skill_validation/test_dependencies.py \
        scripts/extract_skill_dependencies.py
git commit -m "chore: add skill dependency map and validation tests"
```

---

### Task 1-2: SKILL.md 形式検査スクリプト作成

**Files:**
- Create: `scripts/validate_skill_format.sh`
- Create: `tests/skill_validation/test_step_format.py`

**Interfaces:**
- Consumes: `.claude/skills/*/SKILL.md` (全スキルのStep形式を検査)
- Produces: 形式違反リスト、テストケース

**Steps:**

- [ ] **Step 1: 形式検査基準定義**

`.claude/skills/<スキル>/SKILL.md` が満たすべき形式 (from writing-plans):
```
# [スキル名] Skill

## 概要
...

## Step 1: [アクション説明]
- 1つのアクション = 1ステップ
- 複数コマンドを含む場合は「実行コマンド」サブセクション
- テストは「検証コマンド」サブセクション

## Step 2: ...

## 検証失敗時 (NEW pillar 2)
- 通知方法: [具体的なコマンド/スクリプト]
- GitHub Issue 起票: [パラメータ]

## 本番前テスト (NEW pillar 3)
- ローカル検証コマンド: [具体的]
- サンドボックス環境: [あれば]
- 確認チェックリスト: [□ xxx, □ yyy]
```

- [ ] **Step 2: 検査スクリプト作成**

`scripts/validate_skill_format.sh`:
```bash
#!/bin/bash
set -uo pipefail

SKILLS_DIR=".claude/skills"
ERRORS=0

for skill_dir in "$SKILLS_DIR"/*; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    skill_md="$skill_dir/SKILL.md"
    
    [ -f "$skill_md" ] || {
        echo "❌ [$skill_name] SKILL.md が見つかりません"
        ((ERRORS++))
        continue
    }
    
    # 必須セクションをチェック
    for section in "## Step" "## 検証失敗時" "## 本番前テスト"; do
        grep -q "^$section" "$skill_md" || {
            echo "⚠️  [$skill_name] セクション '$section' が見つかりません"
            ((ERRORS++))
        }
    done
    
    # 複数ステップで「複数アクション=1ステップ」がないか検査
    step_count=$(grep -c "^## Step [0-9]" "$skill_md" || true)
    [ "$step_count" -gt 0 ] || {
        echo "⚠️  [$skill_name] Step セクションが0個です"
        ((ERRORS++))
    }
done

[ $ERRORS -eq 0 ] && echo "✅ 全スキルが形式要件を満たしています" && exit 0
echo "❌ $ERRORS 個の形式違反を検出しました"
exit 1
```

- [ ] **Step 3: ローカル実行確認**

```bash
bash scripts/validate_skill_format.sh
```

初回は違反が多くあるはず（既存スキルがまだ改善されていないため）。初期状態の違反リストをテキストファイルに保存。

- [ ] **Step 4: Python テストケース作成**

`tests/skill_validation/test_step_format.py`:
```python
import re
from pathlib import Path

def test_all_skills_have_step_sections():
    """全スキルが ## Step n セクションを持つか"""
    for skill_dir in Path('.claude/skills').iterdir():
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            steps = re.findall(r'^## Step \d+:', content, re.MULTILINE)
            assert len(steps) > 0, f"{skill_dir.name} に Step セクションがありません"

def test_all_skills_have_failure_section():
    """全スキルが ## 検証失敗時 セクションを持つか"""
    for skill_dir in Path('.claude/skills').iterdir():
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            assert "## 検証失敗時" in content, \
                f"{skill_dir.name} に「検証失敗時」セクションがありません"

def test_all_skills_have_local_test_section():
    """全スキルが ## 本番前テスト セクションを持つか"""
    for skill_dir in Path('.claude/skills').iterdir():
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding='utf-8')
            assert "## 本番前テスト" in content, \
                f"{skill_dir.name} に「本番前テスト」セクションがありません"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_skill_format.sh \
        tests/skill_validation/test_step_format.py
git commit -m "chore: add SKILL.md format validation"
```

---

### Task 1-3: GitHub Actions ワークフロー作成

**Files:**
- Create: `.github/workflows/skill-validation.yml`

**Interfaces:**
- Consumes: scripts/validate_skill_format.sh, tests/skill_validation/ (形式検査スクリプト・テスト)
- Produces: PR時の自動検査

**Steps:**

- [ ] **Step 1: スキル形式検査ワークフロー作成**

`.github/workflows/skill-validation.yml`:
```yaml
name: Skill Format Validation

on:
  pull_request:
    paths:
      - '.claude/skills/**'
      - 'tests/skill_validation/**'
      - 'scripts/validate_skill_format.sh'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run skill format validation
        run: bash scripts/validate_skill_format.sh
      
      - name: Run skill dependency tests
        run: |
          python -m pytest tests/skill_validation/test_dependencies.py -v
          python -m pytest tests/skill_validation/test_step_format.py -v
      
      - name: Comment on PR if validation fails
        if: failure()
        uses: actions/github-script@v6
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '❌ Skill validation failed. Please check the logs above.'
            })
```

- [ ] **Step 2: ワークフロー構文検査**

```bash
yamllint .github/workflows/skill-validation.yml || true
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/skill-validation.yml
git commit -m "ci: add skill format validation workflow"
```

---

### Task 1-4: 週次進捗記録テンプレート作成

**Files:**
- Create: `docs/スキル改善進捗_2026Q4.md`

**Steps:**

- [ ] **Step 1: テンプレート作成**

```markdown
# スキル改善プロジェクト進捗記録 (2026 Q4)

## Week 1 (10/04-10/10)

### 完了タスク
- [ ] Task 1-1: スキルチェーン依存マップ作成
- [ ] Task 1-2: SKILL.md 形式検査作成
- [ ] Task 1-3: GitHub Actions ワークフロー作成
- [ ] Task 1-4: 進捗記録テンプレート作成

### スキル改善進捗 (週1対象: 5スキル)
- [ ] transcription-analysis-hojo: SKILL.md手順化 (Step数: TBD → X)
- [ ] system-design-patterns: 実装例追加 (例言語: Python/TypeScript)
- [ ] educational-content-design: 失敗通知セクション追加
- [ ] data-insights-extraction: ローカル検証手順追加
- [ ] hojo-lighthouse-triage: Gemini並行検証実装

### 検出した課題
- （週進行中に記録）

### 次週への引き継ぎ
- （完了予定のタスク）

---

## Week 2 (10/11-10/17)

### 完了タスク
- （記入待ち）

### スキル改善進捗 (週2対象: 5スキル)
- （記入待ち）

---

...
```

- [ ] **Step 2: Commit**

```bash
git add docs/スキル改善進捗_2026Q4.md
git commit -m "docs: add weekly progress template"
```

---

### Task 1-5: 3役確認議事作成

**Files:**
- Create: `docs/議事_20261004_スキル改善プロジェクト開始.md`

**Steps:**

- [ ] **Step 1: 3役確認議事を CLAUDE.md 形式で作成**

```markdown
# 議事: スキル改善プロジェクト開始 (2026-10-04)

## 推進者(スイシン)視点
- 対象15スキル、4週で改善完了。その後カスタマイズ層スキル10個へ拡大。
- 3本柱(手順化・失敗通知・ローカル検証)により、全13リポジトリのスキル品質が一括向上。
- KGI達成(LINE登録1,000社)のために、各セッションの実装品質向上が必須。

## 懐疑者(ウタガイ)視点
- 4週間で15スキル + 全リポ配布テストは急すぎないか？ マイルストーンの設定が必要。
- Gemini並行検証を追加すると、スキル改善だけで token コスト増加。ROI確認が先。
- update-skills.sh による一括配布で、1リポでも障害があるとロールバック対応が複雑化。

## 別解者(ベッカイ)視点
- スキルは「実装を助ける仕組み」なので、改善の優先順位は「実装に最も影響するスキル」から始めるべき。
  → 現在の週1-3の選定は「作成順」ではなく「優先度」で再順位付けしたか？
- 「失敗通知・Issue自動起票」は誰が・どのシステムから起票するのか（人間？Bot？）が不明確。
- ローカル検証手順は「各スキル独立」か「スキル間の統合テスト」か。エンジニアの負担が大きく見える。

## 決定事項
- ✅ プロジェクト開始を承認。ただし以下を追加:
  1. 週1の基盤整備 (Task 1-1～1-5) 完了後、週2本スキル改善へ進む（並列でなく）
  2. Gemini並行検証は verify-sources 型スキル（3個）に限定。他は Claude 単独。
  3. Issue自動起票は GitHub Actions で実装（人間判断不要なシステムエラー検知に限定）
  4. ローカル検証は「スキル内テスト」のみ。スキル間統合テストは追加スプリント。

## 見直し期限
2026-10-18 (Task 1-4: 基盤整備完了時)
```

- [ ] **Step 2: Commit**

```bash
git add docs/議事_20261004_スキル改善プロジェクト開始.md
git commit -m "docs: record project start discussion (3-person review)"
```

---

## Phase 2: スキル改善 週1 (Week 2-3, 10/11-10/24)

### 対象スキル (5個)
1. `transcription-analysis-hojo`
2. `system-design-patterns`
3. `educational-content-design`
4. `data-insights-extraction`
5. `hojo-lighthouse-triage`

### Task 2-1～2-5: 各スキル改善 (並列実行可)

**共通チェックリスト (各スキルで繰り返し):**

- [ ] **Subtask A: SKILL.md 手順化**
  - 既存の SKILL.md を読む
  - `## Step n:` セクションを、「1アクション = 1ステップ」に再構成
  - 複数のコマンド/処理を含む場合は「実行コマンド」「検証方法」を明記
  - 例: `## Step 1: X を実行` → `実行: \`<コマンド>\`` + `期待出力: <出力例>`
  - ファイル修正後、pytest で形式検査 PASS を確認

- [ ] **Subtask B: 実装例追加**
  - スキルが対象とする言語(Python/JavaScript/TypeScript 等)ごとに最小実装例を追加
  - 例: `## 実装例 (Python)`
  ```python
  # スキルが指示するタスク実行の最小コード例
  ```
  - docs/部品庫.md の「コード部品」と同じ「ゴールデンセット」方式(正解サンプル)で構成
  - エンジニアが「このスキルを使ったときの実装パターン」を即座に理解できる状態に

- [ ] **Subtask C: 失敗通知セクション追加**
  - `## 検証失敗時` セクション を追加
  - スキルの改善・利用で「これは失敗」と判定される条件を列挙
  - 例: `- 関数シグネチャが SKILL.md と異なる → 実装ミス`, `- CLI実行で exit code != 0 → 環境依存`
  - 失敗を検知するスクリプト/コマンド を明記
  - GitHub Issue 自動起票のフック (`issue_template`: 自動記入パラメータ) を定義
  - 例:
  ```markdown
  ## 検証失敗時
  
  ### スキル実装ミス (exit code != 0)
  ```bash
  $ <このコマンドが失敗>
  Error: function X not found
  ```
  → GitHub Issue 自動起票: `title: "[<スキル名>] Step 3 実装ミス: function X not found"`, `labels: skill-error,<スキル名>`
  ```

- [ ] **Subtask D: ローカル検証手順追加**
  - `## 本番前テスト` セクション を追加
  - スキル実装後、本番環境(他リポジトリへの配布)前に「エンジニアがローカルで実施すべきテスト」を記述
  - 例:
  ```markdown
  ## 本番前テスト
  
  1. ローカル環境でスキル格納: `.claude/skills/<skill-name>/` を確認
  2. 依存スクリプト実行:
     ```bash
     python tests/skill_validation/test_dependencies.py -k <skill-name>
     bash scripts/validate_skill_format.sh
     ```
  3. スキル実行: Claude Code session で `/skill-name` を実行。出力パターン3つ: 成功例 / 失敗例 / 境界値例
  4. Gemini 並行検証 (※verify-sources型のみ): 
     - Claude で構造化出力を生成
     - 同じ入力を Gemini で生成
     - 片方が NG なら「要確認」扱い
  5. CI ワークフロー実行: `gh workflow run skill-validation.yml -f skill-name=<>` で全リポ配布テストをシミュレート
  6. チェックリスト:
     - □ SKILL.md 形式検査 PASS
     - □ 実装例コードが実行可能
     - □ 失敗検知スクリプト実行確認
     - □ (verify-sources型の場合) Gemini検証も実行
     - □ ドキュメント英語チェック (humanizer スキル確認)
  ```

- [ ] **Subtask E: Commit & PR**
  - ファイル修正後、新規ブランチで PR 作成
  - PR 説明: スキル改善の3本柱(手順化・失敗通知・ローカル検証)各項目の完成状況を記載
  - GitHub Actions で形式検査・依存テスト自動実行。PASS 後マージ

**各スキルの改善内容 (詳細):**

---

#### Task 2-1: transcription-analysis-hojo 改善

**Files:**
- Modify: `.claude/skills/transcription-analysis-hojo/SKILL.md`

**Specific improvements:**
- 現状の Step セクションを確認し、「1アクション」に分割
- 実装例: Python (音声ファイル処理)
- 失敗通知: 音声フォーマット非対応、テキスト抽出失敗の場合
- ローカル検証: サンプル音声ファイルでテスト実行

**Commit template:**
```bash
git commit -m "refactor(transcription-analysis-hojo): improve SKILL.md structure, add examples and local test"
```

---

#### Task 2-2: system-design-patterns 改善

**Files:**
- Modify: `.claude/skills/system-design-patterns/SKILL.md`

**Specific improvements:**
- Step セクションの細分化 (architecture → component diagram → data flow の3段階に)
- 実装例: TypeScript (microservices pattern)
- 失敗通知: 不完全な依存グラフ、スケール非対応設計の検知
- ローカル検証: サンプルプロジェクト構造での依存解析テスト

**Commit template:**
```bash
git commit -m "refactor(system-design-patterns): decompose steps, add TypeScript examples"
```

---

#### Task 2-3: educational-content-design 改善

**Files:**
- Modify: `.claude/skills/educational-content-design/SKILL.md`

**Specific improvements:**
- ペルソナ定義 → コンテンツ構成 → テスト実施の3フェーズに段階化
- 実装例: 沖縄企業向け助成金ガイド(実際のドメイン)
- 失敗通知: ターゲット層の読解度ミスマッチ、専門用語の非翻訳を自動検知
- ローカル検証: Flesch-Kincaid 読易性スコアでのテスト

**Commit template:**
```bash
git commit -m "refactor(educational-content-design): structure pedagogical flow, add readability test"
```

---

#### Task 2-4: data-insights-extraction 改善

**Files:**
- Modify: `.claude/skills/data-insights-extraction/SKILL.md`

**Specific improvements:**
- データ取得 → 仮説生成 → 検証の3ステップに整理
- 実装例: JSON/CSV → 異常値検知 (pandas)
- 失敗通知: データ型エラー、統計検定失敗の場合
- ローカル検証: サンプルデータセットでの異常検知テスト

**Commit template:**
```bash
git commit -m "refactor(data-insights-extraction): clarify hypothesis-test flow, add anomaly detection test"
```

---

#### Task 2-5: hojo-lighthouse-triage 改善

**Files:**
- Modify: `.claude/skills/hojo-lighthouse-triage/SKILL.md`

**Specific improvements:**
- 現在のパフォーマンス計測ステップを「ローカル → CI → 本番」の3環境に分割
- 実装例: JavaScript (Lighthouse API + GitHub Actions連携)
- **Gemini並行検証実装**: 出力数値が Claude と Gemini で一致するか確認
- ローカル検証: docs/部品庫.md の「計測ラッパー」(fg-analytics.js) とのチェーン実行

**Commit template:**
```bash
git commit -m "refactor(hojo-lighthouse-triage): add dual-model validation (Claude+Gemini), structure CI pipeline"
```

---

## Phase 3: スキル改善 週2-3 (Week 4-6, 10/25-11/07)

### 対象スキル (計10個)

**Week 2 (10/25-10/31):**
- go-link-discipline
- hojo-deadline-alert
- hojo-accuracy-check
- shiryo-sakusei
- (1個未定)

**Week 3 (11/01-11/07):**
- humanizer
- resilient-agent-design
- taste-skill
- (2個未定)

### Task 3-1～3-10: 各スキル改善 (同じチェックリスト)

前述「Phase 2 共通チェックリスト」を繰り返す。

**スキルごとの特記事項:**

| スキル | 改善ポイント | verify-sources型か | 備考 |
|---|---|---|---|
| go-link-discipline | `/go/` リンク計測イベント名の衝突防止。CLAUDE.md 再発防止メモ記述に対応 | 可 | LINE登録数の水増し防止が critical |
| hojo-deadline-alert | 「7日前アラート」誤解防止。「残り約1ヶ月」表現を徹底 | 可 | KGI達成に直結するため検証厳格 |
| hojo-accuracy-check | 複数制度の原文照合。Gemini と Claude の片手落ちを防ぐ | ✅ verify-sources型 | Gemini並行検証必須 |
| shiryo-sakusei | 資料生成の品質検査。禁止表現・鮮度チェック（shipping_gate との連携） | 可 | docs/部品庫.md「出荷ゲート」参照 |
| humanizer | 文体統一スキル。他スキルの出力調整のため、humanizer自体は「破壊的変更なし」に厳格 | 不 | スキル依存マップで最多参照 |

---

## Phase 4: 統合テスト・全リポ配布 (Week 7, 11/08-11/14)

### Task 4-1: スキル統合テストスイート作成

**Files:**
- Create: `tests/skill_integration/test_full_workflow.py`

**Steps:**

- [ ] **Step 1: 統合テストシナリオ定義**

```python
"""
スキル間の連鎖を検証。例:
1. educational-content-design で教育コンテンツ案を生成
2. humanizer で文体を統一
3. data-insights-extraction で KPI を抽出
4. hojo-accuracy-check で原文確認
結果: 矛盾なく統合できるか
"""
```

- [ ] **Step 2: シナリオごとのテストケース実装**

```python
def test_content_design_to_humanizer_flow():
    """educational-content-design → humanizer チェーン"""
    # draft = educational_content_design_skill(persona, topic)
    # refined = humanizer_skill(draft)
    # assert refined に humanizer 特性が反映
    pass

def test_accuracy_check_with_dual_model():
    """hojo-accuracy-check の Claude+Gemini 並行検証"""
    # source_data = {"deadline": "2026-12-25", "amount": "¥1,000,000"}
    # claude_check = claude_verify(source_data)
    # gemini_check = gemini_verify(source_data)
    # assert claude_check == gemini_check or (one of them flags NG)
    pass
```

- [ ] **Step 3: 実行確認**

```bash
pytest tests/skill_integration/test_full_workflow.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/skill_integration/test_full_workflow.py
git commit -m "test: add full skill integration tests"
```

---

### Task 4-2: 全13リポジトリ配布リスト生成・検証

**Files:**
- Create: `scripts/distribute_skills.sh`
- Create: `scripts/check_distribution.sh`
- Create: `docs/配布対象リポジトリ一覧_2026-11-08.md`

**Steps:**

- [ ] **Step 1: 配布対象リポリスト自動生成**

`scripts/distribute_skills.sh` (update-skills.sh の ラッパー):
```bash
#!/bin/bash
set -uo pipefail

# update-skills.sh の MARKETING_REPOS + INFRA_REPOS を読み込み
BASE="${BASE:-/workspace}"
SKILL_VERSION="2026-11-08"

echo "==> Distributing skills to 13 repositories"
echo "==> Skill version: $SKILL_VERSION"

REPOS=(
    # MARKETING_REPOS (6)
    hojo-hq hikari-hq hikari-lp hikari-report kakei-hq okinawa-villa
    # INFRA_REPOS (7)
    report-hq go allgroup-site enlife-mikomi skl-venue-hq hojo-signal kakei-crm
)

for repo in "${REPOS[@]}"; do
    echo "[$repo] Starting distribution..."
    # update-skills.sh 実行ロジック
done

echo "==> Distribution complete. Verify with check_distribution.sh"
```

- [ ] **Step 2: 配布検証スクリプト作成**

`scripts/check_distribution.sh`:
```bash
#!/bin/bash
set -uo pipefail

# 全13リポで .claude/skills/ 配下の改善スキル15個が実際に反映されたか検査
REPOS=( ... ) # 同上
TARGET_SKILLS=(
    transcription-analysis-hojo system-design-patterns educational-content-design
    data-insights-extraction hojo-lighthouse-triage go-link-discipline
    hojo-deadline-alert hojo-accuracy-check shiryo-sakusei humanizer
    resilient-agent-design taste-skill
    # + その他5個
)

FAILURES=0
for repo in "${REPOS[@]}"; do
    echo "[$repo] Checking skill distribution..."
    for skill in "${TARGET_SKILLS[@]}"; do
        skill_path="$BASE/$repo/.claude/skills/$skill/SKILL.md"
        if [ ! -f "$skill_path" ]; then
            echo "  ❌ [$repo] $skill が見つかりません"
            ((FAILURES++))
        else
            # SKILL.md の更新日付が最新か確認
            mod_date=$(stat -c %y "$skill_path" | cut -d' ' -f1)
            echo "  ✅ [$repo] $skill (updated: $mod_date)"
        fi
    done
done

[ $FAILURES -eq 0 ] && echo "✅ 全13リポで全スキルが最新版に更新されました" && exit 0
echo "❌ $FAILURES 個の配布漏れを検出しました"
exit 1
```

- [ ] **Step 3: リスト Markdown 生成**

`docs/配布対象リポジトリ一覧_2026-11-08.md`:
```markdown
# スキル配布対象リポジトリ一覧 (2026-11-08)

## MARKETING_REPOS (Superpowers + marketingskills + ALLGROUP共通スキル)

| リポ | 組織 | 事業 | 配布ステータス |
|---|---|---|---|
| hojo-hq | allgroup-inc | GLOW | ✅ 完了 |
| hikari-hq | allgroup-inc | 山梨版 | ✅ 完了 |
| hikari-lp | allgroup-inc | 山梨版 | ✅ 完了 |
| hikari-report | allgroup-inc | 山梨版 | ✅ 完了 |
| kakei-hq | allgroup-inc | 家計 | ✅ 完了 |
| okinawa-villa | allgroup-inc | 別リポ | ⚠️ 要権限確認 |

## INFRA_REPOS (Superpowers + ALLGROUP共通スキルのみ)

| リポ | 組織 | 事業 | 配布ステータス |
|---|---|---|---|
| report-hq | allgroup-inc | 報告書 | ✅ 完了 |
| go | allgroup-inc | Go link | ✅ 完了 |
| allgroup-site | allgroup-inc | 会社サイト | ✅ 完了 |
| enlife-mikomi | allgroup-inc | enLife | ✅ 完了 |
| skl-venue-hq | allgroup-inc | SKL | ✅ 完了 |
| hojo-signal | fukugiiro | GLOW | ⚠️ 別org（手動配布） |
| kakei-crm | allgroup-inc | 家計CRM | ✅ 完了 |

**計13リポ（うちokinawa-villa と hojo-signal は権限確認が必要）**

配布完了日: 2026-11-08
検証コマンド: `bash scripts/check_distribution.sh`
```

- [ ] **Step 4: 実行確認**

```bash
bash scripts/distribute_skills.sh
bash scripts/check_distribution.sh
```

- [ ] **Step 5: Commit**

```bash
git add scripts/distribute_skills.sh scripts/check_distribution.sh \
        docs/配布対象リポジトリ一覧_2026-11-08.md
git commit -m "scripts: add skill distribution and verification scripts"
```

---

### Task 4-3: CLAUDE.md 再発防止メモ更新

**Files:**
- Modify: `CLAUDE.md` (末尾「再発防止メモ」セクション)

**Steps:**

- [ ] **Step 1: スキル改善で検出した失敗パターン抽出**

Phase 2-3 を通じて「同じミス 2度目」と判定した項目をリストアップ:
- 例: スキル間依存の見落とし (humanizer → resilient-agent-design への参照が更新されなかった)
- 例: Gemini 並行検証の片手落ち (Claude OK でも Gemini NG)
- 例: 配布スクリプトの更新忘れ (新規スキル追加時に check_distribution.sh に追加忘れ)

- [ ] **Step 2: 記述を CLAUDE.md 末尾に追加**

```markdown
- **スキル改善時は「スキル依存マップ」を必ず確認する**。参照先スキルの改善が漏れていないか確認必須(2026-11-08: humanizer 改善時に resilient-agent-design 参照を見落とし、テスト時に矛盾発生)。docs/スキル依存マップ.md で自動検査可能
- **Gemini 並行検証は verify-sources型スキルに限定**していたが、他スキル(data-insights-extraction 等)でも誤り検知率が高い場合は要見直し(2026-11-08: 当初予定外で3スキル追加)。判定は検証結果と コスト(token)のバランスで小柳さん判断
- **配布スクリプト更新時は check_distribution.sh にもスキル名を足す**。両方が乖離すると「13リポで配布したはずが実は12リポ」と判定漏れ(2026-11-08: go-link-discipline 追加漏れ検出)
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with skill improvement retrospective"
```

---

### Task 4-4: 最終ドキュメント統合・公開

**Files:**
- Create: `docs/スキル改善プロジェクト完了レポート_2026-11-08.md`

**Steps:**

- [ ] **Step 1: プロジェクト完了レポート作成**

```markdown
# スキル改善プロジェクト完了レポート (2026-11-08)

## 実績

### 改善スキル数
- **hojo-hq専用15個**: 全て改善完了
- 実装例追加数: Python/TypeScript 合計 X個
- Gemini 並行検証対象: verify-sources型 Y個
- 発見課題: Z件（全て対応済み）

### 配布結果
- **13リポジトリ全て配布完了**
  - MARKETING_REPOS: 6/6 成功
  - INFRA_REPOS: 7/7 成功 (hojo-signal は別org だが手動配布で対応)
- 配布エラー: 0件

### 品質指標
| 指標 | 目標 | 実績 | 達成度 |
|---|---|---|---|
| SKILL.md 形式準拠率 | 100% | 15/15 | ✅ 100% |
| 実装例カバー率 | 80%+ | 13/15 | ✅ 87% |
| Gemini並行検証実装 | verify-sources型全て | 5/5 | ✅ 100% |
| GitHub Actions CI 自動検査 | 運用開始 | 2026-11-08 | ✅ 完了 |

### スキル依存グラフ検証
- 循環参照: 0件
- 参照先欠落: 0件
- 新規依存関係: X件追加検出

## 議事・承認

- [x] 2026-10-04: プロジェクト開始 (3役確認済み)
- [x] 2026-10-10: 基盤整備完了 (milestone)
- [x] 2026-10-31: Week1-2 スキル改善完了 (milestone)
- [x] 2026-11-07: Week3 スキル改善完了 (milestone)
- [ ] 2026-11-14: 最終レビュー・本番運用開始 (予定)

## 次フェーズ

- [ ] カスタマイズ層スキル10個の改善 (2026-11 着手予定)
- [ ] Routine自動化: update-skills.sh の自動cron化 (2026-11 検証後)
- [ ] スキル品質監査: 月次の「スキル形式逆行チェック」実装

## 添付資料
- docs/スキル依存マップ.md
- docs/スキル改善進捗_2026Q4.md
- docs/議事_20261004_スキル改善プロジェクト開始.md
```

- [ ] **Step 2: Commit**

```bash
git add docs/スキル改善プロジェクト完了レポート_2026-11-08.md
git commit -m "docs: add project completion report"
```

- [ ] **Step 3: docs/全体マップ.md 更新**

新規作成の文書・スクリプト・テストを追加記載

```bash
git add docs/全体マップ.md
git commit -m "docs: update master index with skill improvement deliverables"
```

---

## Global Constraints (Recap)

- スキル改善の順序: 週1-3 は「優先度 + 難度」で再確認（作成順ではなく）
- Gemini並行検証: verify-sources型 (5個: hojo-accuracy-check等) に限定。他スキルは Claude 単独
- 議事記録: 判定分裂時のみ。可逆な技術作業は議事任意（月末の前提破壊レビューで品質担保）
- マイルストーン: 週ごと完了チェック（遅延時は小柳さんへ上申）

---

## Review Focus

本計画の実装で注視すべき5つの入力・失敗モード:

1. **スキル間依存の破壊**: Task 1-1 の依存マップが古いままで、Task 2-5 が新規参照を加えても反映されず、配布時に矛盾発生
   → 対策: Task 2-3 の最後に依存マップ再抽出・テスト (test_dependencies.py) 再実行

2. **SKILL.md 形式の回帰**: 改善済み スキルが「Step を複数アクションで詰める」と退行化する場合
   → 対策: PR時に自動検査ワークフロー (skill-validation.yml) で引っかかるよう Task 1-3 で実装

3. **Gemini 並行検証の片手落ち**: verify-sources型 5個を verify する際、Claude は成功でも Gemini は NG なのに見落とす
   → 対策: Task 2-5 で Gemini テスト結果と Claude 結果を並列で記録し、片側 NG は「要確認」として追跡

4. **配布対象スキル数の乖離**: 改善対象 15個→20個に増えたが、scripts/check_distribution.sh の TARGET_SKILLS リストを更新し忘れ、配布漏れが見つからない
   → 対策: Task 4-2 で TARGET_SKILLS リスト自動生成スクリプト化。手入力を排除

5. **再発防止メモ更新忘れ**: 同じミスが 2度起きたのに CLAUDE.md に記録しない場合、3度目が起きる
   → 対策: Task 4-3 で必ずレトロスペクティブを記述。議事メモにも「再発防止メモ行番号」を記載

---

## Execution Path

このプランは以下の実行方法に対応:

### Subagent-driven approach
各週 (Phase 2-4) ごとに新規 subagent を起動。Task 単位で並列実行 + 統合テスト → マージ。複数視点から品質検証可能。トークンコスト増加。

### Native approach
本セッション内で全 Task を順次実装。エンジニアの意思決定が速い。ただし単一視点なので回帰リスク高い。

**推奨: Subagent-driven** — スキル改善は「複数チャットセッションで共有される仕組み」なので、各セッションの独立レビューが品質を保証。特に Task 2-1～3-10 (各スキル改善) は並列推進で スケジュール短縮可能。
