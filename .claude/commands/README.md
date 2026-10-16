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

## hojo-hq 専用コマンド（2026-10-02 追加）

コスト最適化・効率化のために追加された3つの専用コマンド：

### 1. `/token-budget-advisor` — トークン消費の可視化

**用途**: Claude Code Remote セッションのトークン使用量・費用を可視化・予算管理  
**実行頻度**: 週1回（毎週金曜 16:00 JST）  
**効果**: 複数セッション比較、月額トレンド、予算超過警告

**hojo-hq での活用**:
- 前回監査で発見: $36,093/月（52セッション）
- 毎週実行で高額セッション特定
- 月初に月末予測費用を小柳さんに報告

詳細: `token-budget-advisor.md`

### 2. `/strategic-compact` — コンテキスト圧縮・セッション効率化

**用途**: 複雑な長時間セッションのコンテキスト圧縮、マルチエージェント実行時の効率化  
**実行頻度**: 月1回（毎月初）+ 大規模実行前  
**効果**: 会話履歴の50-70%削減、セッション分割提案、キャッシュ戦略再設計

**hojo-hq での活用**:
- カチトーク続新: 49B cache_read tokens（異常）→ 圧縮予定
- 複数部門の並行実行 → 最適なセッション分割
- 毎月末に来月の効率計画を立案

詳細: `strategic-compact.md`

### 3. `/regex-vs-llm-structured-text` — AI 不要なタスク識別

**用途**: 単純な正規表現・データ処理をAIから外し、Bash/ツール化で効率化  
**実行頻度**: 月1回（月末の最適化時）+ 新規タスク設計時  
**効果**: 単純作業の5-100K tokens 削減、スクリプト化ロードマップ生成

**hojo-hq での活用**:
- CSV フィルタ（awk） → トークン 0 化
- JSON 整形（jq） → トークン 0 化
- 複雑ロジックだけ AI 投入 → 効率 3-5倍

詳細: `regex-vs-llm-structured-text.md`

### 3つコマンドの運用スケジュール

```
毎週金曜 16:00 JST:
  /token-budget-advisor → 週次レポに集計

毎月初 09:00 JST:
  /strategic-compact → 来月の効率計画立案

毎月末 15:00 JST:
  /regex-vs-llm-structured-text → 単純作業化リスト作成
```

### 期待削減額（3ヶ月）

| コマンド | 削減対象 | 期待削減額 |
|---|---|---|
| `/token-budget-advisor` | 可視化による削減 | $200-300/月 |
| `/strategic-compact` | セッション統合 | $500-700/月 |
| `/regex-vs-llm-structured-text` | 単純作業化 | $100-200/月 |
| **合計** | — | **$800-1,200/月（22-33%削減）** |

### 関連ドキュメント

- `docs/議事_20261002_Claude_Code_Remote_費用最適化決定.md` — 実装背景
- `docs/議事_20261002_基本スキル4つ追加決定.md` — スキル統合（同日実施）
