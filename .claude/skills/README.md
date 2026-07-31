# .claude/skills — Superpowers

このディレクトリのスキルは Claude Code のセッション開始時にディスクから自動検出される。
リポジトリにチェックインしてあるため、Claude Code on the web でも各チャットに最初から入っている。

## 中身: Superpowers (obra/superpowers v6.2.0 を vendoring)
TDD・計画・デバッグ・レビュー・Git ワークフロー等の 14 スキル。
- 出典: https://github.com/obra/superpowers (MIT License)
- 取り込み元 commit: `3dcbd5c4b48e02263fbf4a3c01e3fe4f81d584d9`
- 各スキルは自己完結(必要なスクリプトは各スキル配下の `scripts/` に同梱)。

セッション開始時に `.claude/hooks/superpowers-session-start.sh` が
`using-superpowers` スキルを注入し、「You have superpowers」で自動起動させる。

## なぜ vendoring なのか
Claude Code on the web は毎セッション `~/.claude` が作り直され、プラグインの
インストール状態は永続しない。SessionStart フックで `claude plugin install` しても
スキルレジストリは起動時に構築済みで同じセッションでは読み込まれない。
リポジトリに実体を置く vendoring が各チャットで確実に効く唯一の方法。

## 更新するには
```bash
git clone --depth 1 https://github.com/obra/superpowers.git /tmp/sp
for d in /tmp/sp/skills/*/; do
  name=$(basename "$d")
  rm -rf ".claude/skills/$name" && cp -r "$d" ".claude/skills/$name"
done
```
