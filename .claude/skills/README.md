# .claude/skills — スーパーパワーズ + hojo-hq 専用スキル

このディレクトリのスキルは **Claude Code のセッション開始時にディスクから自動検出** される。
リポジトリにチェックインしてあるため、Claude Code on the web でも
「毎回コンテナが作り直される」環境で **各チャットに最初から入っている**。

## 中身

### 1. Superpowers(obra/superpowers v6.2.0 を vendoring)
TDD・計画・デバッグ・レビュー・Git ワークフロー等の 14 スキル。
- 出典: https://github.com/obra/superpowers (MIT License)
- 取り込み元 commit: `3dcbd5c4b48e02263fbf4a3c01e3fe4f81d584d9`
- 各スキルは自己完結(必要なスクリプトは各スキル配下の `scripts/` に同梱)。

セッション開始時に `.claude/hooks/superpowers-session-start.sh` が
`using-superpowers` スキルを注入し、「You have superpowers」で自動起動させる。

### 2. hojo-hq 専用スキル(CLAUDE.md 憲法をスキル化)
- `hojo-deadline-alert` — 締切アラート3層ルール(「7日前」禁止・「約1か月前から」統一)
- `hojo-accuracy-check` — 正確性最優先(原文URL照合・「要確認」表示)
- `hojo-triangle-review` — 三名体制(スイシン/ウタガイ/ベッカイ)

## なぜ「フックでインストール」ではなく vendoring なのか
Claude Code on the web は毎セッション `~/.claude` が作り直され、
プラグインのインストール状態は永続しない。さらに SessionStart フックで
`claude plugin install` してもスキルレジストリは起動時に構築済みで、
**同じセッションでは読み込まれない**(検証済み)。
リポジトリに実体を置く vendoring が、各チャットで確実に効く唯一の方法。

## Superpowers を更新するには
```bash
git clone --depth 1 https://github.com/obra/superpowers.git /tmp/sp
# 既存スキルを入れ替え(hojo-* は消さない)
for d in /tmp/sp/skills/*/; do
  name=$(basename "$d")
  rm -rf ".claude/skills/$name" && cp -r "$d" ".claude/skills/$name"
done
# README の commit ハッシュも更新してコミット
```

## 他のプロジェクトにも入れるには(全プロジェクト展開)
web 環境ではユーザー全体設定が永続しないため、**各リポジトリにこの `.claude/` 一式
(`skills/` + `hooks/` + `settings.json`)をコピー**するのが確実。
`hojo-*` スキルはこのプロジェクト固有なので、他プロジェクトでは差し替える。
