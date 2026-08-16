# .claude/commands — カスタムスラッシュコマンド

SNSで話題になっていた「Claude 神コマンド40選」を元に作成した、`/コマンド名`で
呼び出せる汎用の応答スタイル指定コマンド集(2026-08-17)。

## スキルとの違い

- **スキル**(`.claude/skills/`): 関連する場面で自動的に発動する、まとまった手順書
- **ここ(コマンド)**: `/コマンド名 対象の内容` の形で明示的に呼び出す、短い応答スタイルの指定

このリポジトリに同じ目的のスキルが既にある場合(例: `/ghost`→`humanizer`、
`/plan`→`writing-plans`、`/debug`→`systematic-debugging`、`/brainstorm`→`brainstorming`、
`/caption`→`caption-writer`、`/hook`→`hook-writer`、`/carousel`→`carousel-writer`)は、
コマンド側からそのスキルを呼ぶようにしている(車輪の再発明をしない)。

## 除外したもの

- `simplify` — この環境に既に同名の組み込みコマンド(コードの簡素化用)があるため、
  衝突を避けて作成していない
- 元のSNS投稿の40個目(画像内で他の投稿のキャプションに隠れて読み取れなかった)は
  未収録。判明したら追加する

## 収録一覧(38個)

explainlikeim5 / brief / compare / critique / teacher / scout / pitch / ghost /
10x / devil / godmode / debate / roadmap / plan / summary / research / rewrite /
optimize / debug / review / mentor / coach / analyst / startup / pm / security /
interview / resume / brainstorm / email / translate / proofread / ideas /
caption / hook / checklist / template / carousel
