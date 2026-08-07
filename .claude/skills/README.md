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

## 中身: taste-skill (Leonxlnx/taste-skill を vendoring)
AIが生成しがちな「テンプレっぽいデザイン」を避けるためのLP/フロントエンドデザインスキル。
- 出典: https://github.com/Leonxlnx/taste-skill (MIT License — 全文は `TASTE-SKILL-LICENSE`)
- 元リポジトリは複数のサブスキルを含むが、中核の `taste-skill` のみ取り込み。
- React/npm前提の記述を含む(hojo-hqは静的HTML)。デザイン原則(ブリーフ推論・
  variance/motion/density の3ダイヤル・AIっぽい既定デザインを避ける)は技術非依存で活きる。

## 中身: last30days (mvanhorn/last30days-skill を vendoring)
Reddit・X・YouTube・TikTok・Hacker News等を横断して、直近30日の話題を要約するリサーチスキル。
- 出典: https://github.com/mvanhorn/last30days-skill (MIT License — 全文は `LAST30DAYS-LICENSE`)
- 追加のAPIキー(SCRAPECREATORS_API_KEY等)は任意。未設定でもWebSearchで動作する設計。
- デモ用メディア(assets/)とテスト/評価用スクリプトは除外(upstream の `.skillignore` 基準に準拠)。
- 組織総点検で出た「世の中の成功事例を常にウォッチする」の実行手段として導入。

## 中身: social-media-skills (social-media-skills/skills を厳選 vendoring)
106スキットのうち、Instagram運用(SNS部)とX/note運用(note編集部)に直結する8スキルのみ選定。
- 出典: https://github.com/social-media-skills/skills (MIT License — 全文は `SOCIAL-MEDIA-SKILLS-LICENSE`)
- 選定: `instagram-growth` `caption-writer` `carousel-writer` `hashtag-strategy`
  `content-calendar` `thread-writer` `hook-writer` `platform-specs-and-validation`
- evals/ は除外(実行時不要、他のvendoringと同じ方針)。

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
- `resilient-agent-design` — cron・定期ワークフロー・無人稼働の自動化を新規設計/レビューするとき、または「壊れる・重複する・止まらない」トラブル時に使う。4層設計(Trigger/Workflow/Agent/Guardrail)と壊れにくい設計の7原則(判断だけAIへ・状態は外部保存・べき等性・リトライ上限・権限は最小から・Hookと監視・分業は慎重に)、実行方式の選び方を提供。
- `mindshare-arbitrage` — SNS投稿・note記事のネタ探し〜生成〜投稿を仕組み化するとき。他の場で伸びた型を自分の言葉で翻訳する考え方と、発見→レビュー→生成→スライド化→承認投稿→分析学習の6段パイプライン(人が関わるのはレビューと承認投稿の2箇所だけ)。生成工程は`humanizer`と連携するwriter→humanizer→criticループを使う。

同じパターンの姉妹スキルとして `glow-ma-triangle-review`(GLOW M&A向け)もある。

## 検討したが見送ったもの
- `agent-browser`(ok-skills内) — ブラウザ自動化CLI。`agent-browser install` を実際に試したが、
  この実行環境の通信制限でChromeのダウンロードに失敗し動作確認できなかったため未導入
  (2026-08-06)。再検討する場合は、環境に既にあるPlaywright/Chromiumへの接続方法を先に確認する。
- `claude-hud` — 「Claudeの状態をリアルタイム表示」はダッシュボードUIが本体で、
  SKILL.md(指示書)だけでは実現できないため対象外。

## MCPコネクタ(スキルとは別枠・アカウント設定が必要)
Context7(最新ライブラリのドキュメント取得)や Claude Mem 相当(Mem0など、長期記憶)は
スキルファイルではなく MCP コネクタのため、リポジトリへの vendoring では追加できない。
claude.ai のアカウント設定(コネクタ管理)側で接続する必要がある。接続すればアカウント
全体で使えるようになるが、チャットごとに有効化が必要な場合がある。
