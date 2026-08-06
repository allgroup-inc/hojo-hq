# .claude/skills — Superpowers

このディレクトリのスキルは Claude Code のセッション開始時にディスクから自動検出される。
リポジトリにチェックインしてあるため、Claude Code on the web でも各チャットに最初から入っている。

## 中身: Superpowers (obra/superpowers v6.2.0 を vendoring)
TDD・計画・デバッグ・レビュー・Git ワークフロー等の 14 スキル。
- 出典: https://github.com/obra/superpowers (MIT License — 全文は `SUPERPOWERS-LICENSE`)
- 取り込み元 commit: `3dcbd5c4b48e02263fbf4a3c01e3fe4f81d584d9`
- 各スキルは自己完結(必要なスクリプトは各スキル配下の `scripts/` に同梱)。

## 中身: marketingskills (coreyhaines31/marketingskills を vendoring)
コピー・SEO・広告・価格設計・リサーチ等のマーケティング 48 スキル。
- 出典: https://github.com/coreyhaines31/marketingskills (ライセンス全文は `MARKETINGSKILLS-LICENSE`)
- 一括更新は `scripts/update-skills.sh`(Superpowers と同時に upstream 最新へ追従)。

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

## hojo-hq固有スキル(CLAUDE.md憲法をルール化)
vendoring した汎用スキルとは別に、このリポジトリの意思決定・運用ルールを
Claude が毎回思い出す必要がないようスキル化したもの。ベンダーからの更新対象外。

- `hojo-accuracy-check` — 制度データ(締切・金額・要件)を掲載・更新するとき。原文URL照合・「要確認」表示・断定禁止を強制。
- `hojo-deadline-alert` — 締切アラート・告知文面・配信タイミングを設計/レビューするとき。3層ルール(30日以上=SNSのみ/7〜29日=LINE個別/7日未満=次回予告)と「約1か月前から」表現を強制、誤った「締切7日前」表現を排除。
- `hojo-triangle-review` — 企画・施策・方針など意思決定を伴う議論をまとめるとき。スイシン/ウタガイ/ベッカイの三名体制でウタガイの反対理由必須の議事を強制。
- `humanizer` — SNS投稿・LINE配信・サイトコピーなど対外文面の最後の仕上げで必ず使う。AIっぽさ(定型フレーズ・過剰な絵文字/強調)を除き、憲法トーン(専門用語をやさしく翻訳)の自然な日本語に整える(事実情報・CV導線は変えない)。
- `resilient-agent-design` — GitHub Actions/cron/Claude Routines等の自動化・AIエージェントを新規設計/レビューするとき。壊れにくい設計の7原則(判断だけAIへ・状態は外部保存・べき等性・リトライ上限・権限は最小から・Hookと監視・分業は慎重に)と実行方式の選び方を提供。

同じパターンの姉妹スキルとして `glow-ma-triangle-review`(GLOW M&A向け)もある。

## MCPコネクタ(スキルとは別枠・アカウント設定が必要)
Context7(最新ライブラリのドキュメント取得)や Claude Mem 相当(Mem0など、長期記憶)は
スキルファイルではなく MCP コネクタのため、リポジトリへの vendoring では追加できない。
claude.ai のアカウント設定(コネクタ管理)側で接続する必要がある。接続すればアカウント
全体で使えるようになるが、チャットごとに有効化が必要な場合がある。
