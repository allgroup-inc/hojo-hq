# WikiSkill統合アーキテクチャ設計仕様書

**作成日**: 2026-10-06 / **v1.1 改訂**: 2026-10-06(小柳さん基本承認・修正4点とDecision 8件を反映)  
**段階**: 基本承認済み → Phase 1 実装計画へ(実装は未着手)  
**対象**: hojo-hq + 13配布リポジトリ全体  
**決定者**: 小柳さん

---

## v1.1 改訂: 承認時の修正事項(4点)と承認済みDecision(8件)

### 修正事項(設計に反映済み。該当コンポーネント節も書き換えた)

| # | 修正 | 反映先 |
|---|---|---|
| 1 | **Experience Logger の silent fail 禁止**。開発作業は止めないが、保存失敗は必ず監査ログ(`.claude/experience/_audit.log`)に残し、かつ hook の `systemMessage` で利用者に警告を出す | A |
| 2 | **Memory Bootstrap は毎セッション自動実行**。ただし全Wiki・全Decisionを投入せず、現在の作業に関連する「重要Decision / その前提 / 未解決事項 / 過去の重要な失敗 / 再発防止事項 / 現在有効な関連Skill」だけを取得する。目的は「大量に覚えさせる」ではなく「必要な時に正しい記憶を取り出す」 | D |
| 3 | **Decision と Experience を明確に分離**。Experience=「何が起きたか」(機械記録・低信頼)、Decision=「何を決めたか・なぜ決めたか」(人間記録・高信頼)。矛盾時は Decision を上位に置く | C, A, J |
| 4 | **Phase 1 では Skill の自動改善・自動更新を実装しない**。まず Experience → Decision → Memory Bootstrap → 新セッションで復元、が機能することを検証する | Phase 1, F, H |

### 承認済み Decision(2026-10-06 小柳さん)

| # | 項目 | 決定 | 反映先 |
|---|---|---|---|
| 1 | Memory Bootstrap | **ON。全セッションで自動実行。関連情報のみ取得** | D |
| 2 | Decision 見直し期限 | **決定ごとに設定。未指定なら180日** | C |
| 3 | 三名体制 | **半自動。AIによる評価・判定補助は許可。最終Gateは人間** | H |
| 4 | Experience 保存 | **原本を保持。定期的にArchive。Git肥大化を監視** | A, I |
| 5 | GLOW世界(❻) | **初期分類は Private。原則「迷ったら Private」。Public化には明示的判定が必要** | K |
| 6 | Knowledge Extractor | **AIによる自動抽出・提案は許可。正式Wikiへの昇格は人間確認** | B |
| 7 | Rollback | **緊急Rollbackは守り部が実行可能。その後、小柳Decision Gateで正式判断・記録** | I |
| 8 | Concurrency Lock | **基本timeout 30分。heartbeatがあれば延長可。stale lockを安全に判定・解除できること** | L |

### 信頼階層(修正3を全コンポーネント共通の原則として明文化)

```
高 ┃ Decision(議事・小柳決裁)        … 「何を・なぜ決めたか」。人間が書き、ウタガイ反対理由つき
   ┃ 失敗台帳(docs/失敗台帳.md)       … ニドナシ機構が真因まで確認した失敗
   ┃ 再発防止メモ(CLAUDE.md 末尾)     … 2度起きたミスの1行ルール
   ┃ Wiki パターン(Phase 2〜)         … Experience から抽出し人間が昇格させた知識
低 ┃ Experience(.claude/experience/)  … 機械が記録した「何が起きたか」。単独では判断根拠にしない
```
Memory Bootstrap はこの順で表示し、各項目に出典ラベルを付ける。Conflict Resolver(Phase 3)もこの階層を第一基準にする。

---

## エグゼクティブサマリー

### 目的
Claude Codeセッションが過去の意思決定・失敗・成功を「必要なとき自動的に復元」し、Skillを継続改善できる環境を実現。記録することが目的ではなく、**新しいセッション開始時に思い出させる仕組み**を構築する。

### 現状の問題
- セッション終了時にコンテキスト破棄→知識が散逸
- Skillの「実行されたか」「成功したか」「改善効果があったか」が未測定
- 過去の意思決定の「前提」や「反対理由」が時間とともに埋もれる
- 複数セッション並行時の競合リスク（同時編集で片方が消える）
- Obsidianは同期遅延のため「リアルタイム正本」ではない

### 設計の基本原則

| 原則 | 理由 |
|---|---|
| **GitHub Single Source of Truth** | Git履歴で全操作が追跡可能。Rollback可能。Obsidianはバックアップ・検索層 |
| **既存システム最大再利用** | 110 Skills / 13リポ同期 / 三名体制 / hooks は維持。壊さない |
| **Public/Private絶対分離** | 顧客PII・M&A戦略が公開リポへ漏れない。非公開Experienceはprivateリポ内のみ |
| **段階的導入** | Phase 1で基盤、Phase 5で自動化。各フェーズはロールバック可能 |
| **人間Decision Gate必須** | Skill更新は完全に自動化しない。Proposal→Evaluation→三名体制→小柳承認の順序守出 |
| **Git追跡可能** | 記録・メタデータ・ロックすべてGit管理。設定ファイルで依存しない |

---

## 13コンポーネント仕様

### コンポーネント A: Experience Logger

**優先度**: 🔴 **必須**

**目的**: 各Claude Codeセッションで実行した内容・使用Skill・結果・フィードバックを自動記録。後の知識抽出の素材。

**論文WikiSkillとの関係**: 論文「Raw Experience」層の実装

**入力**:
- セッション開始時刻・セッションID
- 実行コマンド(git, bash)
- 使用Skill名リスト
- 成功/失敗判定(commit成功時=成功、revert=失敗等)
- エラーメッセージ
- ユーザーコメント("うまくいった"、"失敗"など)
- 最終成果物(commit hash, file list)

**処理**:
1. `.claude/hooks/experience-logger.sh` が毎セッション開始時に自動注入
2. Session ID + タイムスタンプを記録
3. 使用Skillを自動検出（実行ログから）
4. Commit発火時にメタデータ記録
5. セッション終了時に日記形式でフラッシュ

**出力**:
```
.claude/experience/
├── YYYYMMDD/
│   ├── session-<id>.jsonl  ← Raw Experience （Raw format）
│   └── session-<id>.md     ← Human-readable summary
```

**データ形式** (session-<id>.jsonl):
```json
{
  "timestamp": "2026-10-06T10:23:45Z",
  "event": "skill_invoked",
  "skill_name": "writing-plans",
  "session_id": "session_abc123",
  "context": "Created implementation plan for Skill X"
}
{
  "timestamp": "2026-10-06T10:45:12Z",
  "event": "commit",
  "hash": "f3a2b1c",
  "message": "feat: implement Skill Y",
  "files_changed": 5,
  "success": true
}
{
  "timestamp": "2026-10-06T11:00:00Z",
  "event": "session_end",
  "total_duration_seconds": 3600,
  "skills_used": ["writing-plans", "systematic-debugging"],
  "outcome": "success"
}
```

**保存場所**: hojo-hq `.claude/experience/YYYY-MM/session-<id>.jsonl` （Git管理・原本保持。Decision 4）  
**実行タイミング**: SessionStart + PostToolUse(Bash / Skill のみ) + SessionEnd（実在する Claude Code hook イベントのみ使う）  
**担当Agent**: Session hook（自動）。利用者の感想・最終成果は Claude が `scripts/experience_log.py note` で追記（`.claude/commands/` は13リポへ同期されるため、コマンドは追加しない）  
**失敗時動作（修正1: silent fail 禁止）**: 保存失敗は開発作業を止めない。ただし **必ず** ①`.claude/experience/_audit.log` に失敗理由を追記 ②hook 出力の `systemMessage` で「Experience記録に失敗(理由)」を利用者へ警告 ③audit.log 自体にも書けない場合は stderr に出し exit 0。「黙って落ちる」経路をゼロにする  
**記録しないもの（Privacy）**: 利用者のプロンプト本文・Bashコマンド全文・プロジェクト外のパス・ツール出力本文。記録するのは ツール名 / Bashは先頭トークン(プログラム名)のみ / Skill名 / 変更ファイルのプロジェクト内相対パス / セッション中のcommit(hash+件名) / 所要時間 / 任意の note  
**Security分類**: INTERNAL（公開リポに載る前提で、上記の記録範囲に限定）  
**Git管理**: ✅ YES （JSONL行追記・セッション毎に別ファイルなので並行セッションでも競合しない。`_local/`(未確定の一時ファイル)と `_audit.log` は `.gitignore`）  
**信頼度**: 低（Decision より下位。単独では判断根拠にしない。修正3）

**hojo-hq向け変更点**:
- 既存`using-superpowers`hook と統合（SessionStart時に同時実行）
- Routine月額$36K削減を進めるため、Cloud API呼び出しは最小限（JSON形式は軽量）
- 複数部門の並行セッション対応（Session ID で分離）

**既存システムで実現済み部分**:
- ✅ Commit message記録 = `git log`で全て追跡可能
- ✅ Skill実行検出 = `.claude/skills/*/SKILL.md`で明示的
- ✅ セッション管理 = Claude Code標準機構

**判定**: **本当に必要**（ただし超軽量に。JSONLのみ、処理不要）

---

### コンポーネント B: Knowledge Extractor / Wiki Maintainer

**優先度**: 🔴 **必須**

**目的**: Raw Experienceから「再利用価値のある知識」だけを構造化・抽出。ログコピーではなく、パターン化。

**論文WikiSkillとの関係**: 論文「Knowledge Extraction」層の実装。ただしAI自動抽出ではなく半自動（人間が確認）

**入力**:
- Experience Logger の session-<id>.jsonl
- 成功パターンリスト
- 失敗パターンリスト
- 設計判断シート（ウタガイのコメント等）

**処理**:
1. 月1回（月末）、月間Experienceを自動集約
2. Success pattern検出：同じSkillで連続成功 → Pattern化
3. Failure pattern検出：エラー再発 → Root Cause分析対象へ
4. Decision Extraction：commit messageから「決定」検出
5. 人間レビュー（統括akari）で承認してからWikiへ記録

**出力**:
```
docs/wiki/
├── patterns/
│   ├── success/
│   │   ├── skill-writing-plans-pattern-20260930.md ← 「実装計画は最初に全タスク一覧化が効果的」
│   │   └── ...
│   └── failure/
│       ├── concurrency-conflict-pattern-20260915.md ← 「2セッション同時編集で上書きリスク」
│       └── ...
├── decisions/
│   ├── architecture-<domain>-decisions.md
│   └── implementation-guidelines-<domain>.md
└── metadata/
    └── extraction-log-202609.jsonl ← 抽出過程のaudit trail
```

**保存場所**: hojo-hq `docs/wiki/` （Git管理）  
**実行タイミング**: 月末（自動Routine）+ 必要に応じて手動（統括指示）  
**担当Agent**: 統括（akari） + Knowledge Extractor script  
**失敗時動作**: 抽出失敗時は月末レポ「未処理」欄に記載。Wiki更新スキップ  
**Security分類**: PUBLIC（ただし extraction source が private の場合は private wiki へ）  
**Git管理**: ✅ YES （audit trail を `.jsonl` で記録）

**hojo-hq向け変更点**:
- 既存「学び_2026-W**.md」形式と統合（週次→月次へ統合）
- 三名体制（スイシン/ウタガイ/ベッカイ）のコメント自動抽出
- success/failure 分類は業務ドメイン別（収集部/検証部/SNS部等）

**既存システムで実現済み部分**:
- ✅ 「学び」の記録 = `docs/学び/学び_2026-W**.md`で既存
- ✅ 「議事」の記録 = `docs/議事_YYYYMMDD_<件名>.md` で既存（ウタガイ反対理由も記録）
- ✅ パターン化の手法 = 再発防止メモ（CLAUDE.md末尾）で既存

**Decision 6 の反映**: AI による自動抽出・提案（候補ファイルの生成）は許可する。ただし **正式 Wiki（`docs/wiki/`）への昇格は人間確認が必須**。候補は `docs/wiki/_candidates/` に置き、人間が移動（= 昇格）するまで Memory Bootstrap は読まない

**判定**: **本当に必要**（Knowledge Extractorは新規。ただし既存「学び」「議事」と統合）

---

### コンポーネント C: Decision Memory

**優先度**: 🔴 **必須**

**目的**: 「何を決めたか」だけでなく「なぜ決めたか」「前提は何か」「代替案は何か」「反対理由は何か」を構造化保存。6ヶ月後、決定の背景を即座に復元できること。

**論文WikiSkillとの関係**: 論文「Knowledge Base」の「Decision」部分。ただしスキル提案には直接使わず、セッション開始時のMemory Bootstrap材料として活用。

**入力**:
- 議事ドキュメント（`docs/議事_YYYYMMDD_<件名>.md`）
- コミットメッセージ
- Design spec (`docs/superpowers/specs/`)
- Review comments

**処理**:
1. 定期的に議事・commit・specを走査
2. 「決定」パターン検出（「採用」「却下」「延期」等の語）
3. 決定に紐付いた「根拠」「前提」「反対意見」を構造化
4. 見直し期限を自動計算（6ヶ月後を目安）
5. Obsidian連携用にメタデータ出力

**出力**:
```
docs/decisions/
├── decision-index.jsonl ← 全Decision のindex
├── <YYYYMMDD-decision-name>.md ← 個別Decision記録
│   # 決定: Skill改善の三本柱化（2026-08-15）
│   
│   ## 決定内容
│   手順化 / 失敗通知 / ローカル検証の3軸で全Skill改善する
│   
│   ## 背景・なぜ
│   - 実行精度が不安定
│   - 失敗パターンが非可視化
│   - テスト不足で本番トラブル
│   
│   ## 前提
│   1. 複数部門が並行実装可能
│   2. 110Skillsをすべて改善する（段階的）
│   3. 既存110Skillsは壊さない
│   
│   ## 代替案と却下理由
│   - 案A「1つのSkill完璧化」→ 時間がかかりすぎ、他が wait
│   - 案B「自動テストだけ」→ 手順化なしに失敗パターン検出困難
│   
│   ## スイシン側の根拠（推進）
│   - 3本柱なら各部門が独立進行可能
│   - 月単位で改善効果測定できる
│   
│   ## ウタガイの懸念（反対理由、**必須記録**）
│   - 反対理由タイプ: [コスト | リスク | 代替案あり | 前提疑わしい | 長期負債]
│   - 具体的懸念: 「手順化と失敗通知は確実に実装できるが、ローカル検証テストはSkillの性質によって実装困難では？」
│   - ネガティブシナリオ: もし検証テストが実装できない場合、7割のSkillで検証スキップ → 改善効果が限定的
│   - 発生確度: 中
│   - 影響度: 重大
│   - 代替案: 検証テスト対象を「重要度High」に限定する
│   
│   ## ベッカイの前提問い直し
│   - 「110Skillsすべて同じペースで改善する必要があるか？優先度つけるべきでは？」
│   - 「三本柱の重み付けは均等か？実は手順化が最重要では？」
│   
│   ## 採用理由
│   - ウタガイの代替案（検証テスト対象限定）を採用することで、実装リスク低減
│   - ベッカイの優先度付けは別途議事で決める
│   
│   ## 見直し期限
│   2027-02-15（6ヶ月後）
│   
│   ## 関連ファイル
│   - docs/スキル改善進捗_2026Q4.md
│   - docs/Phase4_完了レポート_2026-10-05.md
│   
│   ## Rollback条件
│   「手順化で実装困難な事例が3件以上発生」→ 方針見直し
│
```

**保存場所（v1.1 変更）**: 新しい `docs/decisions/` は作らない。**既存の議事ファイル（`docs/議事_YYYYMMDD_<件名>.md` / `docs/議事/*.md`）そのものを Decision の正本とし、先頭に YAML frontmatter を足して機械可読にする**（既存ルール「議事は docs/議事_… に置く」を変えない）。過去の議事は frontmatter なしのまま、ファイル名の日付・「見直し期限」・「ウタガイ」行をヒューリスティックで読む  
**実行タイミング**: 意思決定時（議事作成と同時）。`scripts/decision_memory.py --check` が CI で frontmatter 必須項目・ウタガイ非空・見直し期限を検査  
**担当Agent**: 部門長 / 統括（akari）  
**失敗時動作**: ウタガイ反対理由がない議事は無効（既存ルール）。検査は新規作成分のみ対象（過去50件は遡及しない）  
**見直し期限（Decision 2）**: 決定ごとに `review_by` を設定。未指定なら `date + 180日` を自動補完  
**信頼度（修正3）**: 高。Experience と矛盾したら Decision を優先。Decision 同士の矛盾は Conflict Resolver（Phase 3）か人間へ  
**Security分類**: PUBLIC（private リポの議事は private リポ内に留まる。hojo-hq の Bootstrap は他リポを読まない）  
**Git管理**: ✅ YES

**hojo-hq向け変更点**:
- 既存「議事_YYYYMMDD_<件名>.md」形式の構造化版
- ウタガイ反対理由の義務化ルール（CLAUDE.md に既出）を自動検証スクリプト化
- 見直し期限 6ヶ月のカウント自動化

**既存システムで実現済み部分**:
- ✅ 議事文書化 = `docs/議事_YYYYMMDD_<件名>.md` で既存
- ✅ ウタガイ反対理由記録 = 三名体制運営規程で義務化済み
- ✅ Decision Gate = 小柳さんの最終決裁（CLAUDE.md に明記）

**判定**: **本当に必要**（既存議事をメタデータ化するだけ。新規システム最小限）

---

### コンポーネント D: Memory Bootstrap

**優先度**: 🔴 **必須**

**目的**: 新しいClaude Codeセッション開始時に、**必要な過去知識だけ**を自動検索・取得・セッション初期化。全Wikiをコンテキストに投入しない（トークン無駄）。

**論文WikiSkillとの関係**: 論文「Memory Retrieval」層の実装

**入力**:
- セッション開始時刻
- ユーザーが作業するリポジトリ（通常 hojo-hq）
- ユーザーのメッセージ（「Skill X を改善したい」等）
- 現在のGitブランチ・最近のcommit

**処理**:
1. セッション開始時、SessionStart hook が発火
2. リポジトリから「このセッションが関連するドメイン」を自動判定
   - ブランチ名 → 対象Feature判定（claude/superpowers-per-chat-* → Skill改善）
   - 最近のcommit → 過去Taskの復帰判定
   - ユーザーメッセージ（first message） → 明示的キーワード検索
3. 関連Decision検索：`docs/decisions/decision-index.jsonl` をタイムスタンプ + scope で検索
4. 関連Pattern検索：`docs/wiki/patterns/` をドメイン別に検索
5. 関連Skillメトリクス検索：実績・成功率・改善履歴
6. 最大5件のDecision + 3件のPattern + 関連Skill を「Memory Context」として注入

**出力**:
```
【セッション初期化メッセージ例】

---
# 🧠 Memory Bootstrap

このセッションは **Skill改善** のようです。以下の過去情報をロードしました：

## 関連決定（見直し期限内）
- [決定] Skill改善の三本柱化（2026-08-15、見直し期限 2027-02-15）
  → 手順化 / 失敗通知 / ローカル検証の3軸で進める

## 関連パターン
- ✅ [Success] writing-plans活用で実装計画の品質向上（過去5件連続成功）
- ❌ [Failure] 複数Skill同時改善で priority衝突（2026-09-15で検出）
  → 代替案：週1Skill × 3週のシーケンシャル進行

## 関連Skillメトリクス
- writing-plans: 用途別成功率 92%, 改善回数 2 → 最新版を推奨使用
- systematic-debugging: 成功率 85%, 改善候補あり

## 推奨アクション
- 前回のPhase 4 を参考に（docs/Phase4_完了レポート_2026-10-05.md）
- ウタガイ反対理由を必ず記録してください

---
```

**保存場所**: セッション初期化メモ（ディスク不要、hook の `additionalContext` として注入）  
**実行タイミング（Decision 1・修正2）**: **全セッションで自動実行**。2段構え:
- 段1 SessionStart: ブランチ名・直近10 commit の件名・origin/main との差分ファイル名 から検索語を作り取得（既存 `superpowers-session-start.sh` と同じ SessionStart 配列に2本目として登録。既存hookは触らない）
- 段2 UserPromptSubmit（そのセッションの**最初の1回だけ**。`.claude/experience/_local/<session_id>.bootstrapped` マーカーで制御）: 利用者の最初の指示文から検索語を追加し、段1で足りなかった関連項目を補う。2回目以降は何もしない  
**取得するもの（これだけ。修正2）**: ①関連する重要Decision（件名・なぜ・前提・見直し期限） ②その Decision の未解決事項（`docs/決裁キュー.md` の未チェック項目で関連するもの） ③関連する過去の重要な失敗（`docs/失敗台帳.md` の FK 行） ④関連する再発防止事項（CLAUDE.md 末尾の箇条書き） ⑤現在有効な関連Skill（`.claude/skills/*/SKILL.md` の name/description） ⑥同じブランチの直近 Experience 要約（低信頼ラベル付き・最大3件）  
**上限**: 全体 6,000文字 / 区分ごと最大5件。関連度スコアが閾値未満なら区分ごと省略（「空」を明示）。全Wiki投入は禁止  
**担当Agent**: SessionStart hook + UserPromptSubmit hook + `scripts/memory_bootstrap.py`  
**失敗時動作**: 取得失敗は作業を止めない。ただし A と同じく `_audit.log` + `systemMessage` で警告（silent fail 禁止）  
**Security分類**: SEMI-PUBLIC。**現在のリポジトリ内のファイルしか読まない**（他リポ・private リポを横断検索しない。Decision 5「迷ったら Private」）  
**Git管理**: ❌ NO（スクリプトは Git管理、出力は一時的、マーカーは `_local/` で `.gitignore`）  
**性能目標**: 段1・段2 とも 500ms 以内（Python 3.11、docs 約300ファイル走査）。超過したら警告

**hojo-hq向け変更点**:
- ドメイン判定を「部門」別に（収集部/検証部/SNS部等）
- 既存Agent定義（`.claude/agents/akari.md` 等）の推奨Agentも同時ロード
- Obsidian同期遅延対応（GitHub上の最新を直接参照）

**既存システムで実現済み部分**:
- ✅ セッション開始 = Claude Code 標準 SessionStart hook
- ✅ リポジトリ判定 = Git metadata（branch, remote）
- ✅ Skill推奨 = `.claude/skills/*/SKILL.md` metadata

**判定**: **本当に必要**（実装量少ない。Bash script + JSON検索）

---

### コンポーネント E: Skill Metrics

**優先度**: 🟡 **良い**（初期段階は簡易版で十分）

**目的**: Skillごとに「使用回数」「成功率」「改善回数」「改善前後比較」を測定。改善効果を定量化。GitRepo肥大化しない設計。

**論文WikiSkillとの関係**: 論文「Evaluation」層の測定部分

**入力**:
- Experience Logger の session-<id>.jsonl （Skill実行ログ）
- Commit message の「Skill名」抽出
- Skill update のタイムスタンプ（version bump）

**処理**:
1. 月1回、Experience logs を集計
2. Skill ごとに：
   - `total_invocations`: 実行回数
   - `success_count`: 成功回数（commit成功 = 成功判定）
   - `failure_count`: 失敗回数
   - `success_rate`: success_count / total_invocations
3. Skill version 更新を検出。更新前後のメトリクス比較
4. 結果を `.claude/skills/<skill-name>/metrics.jsonl` に追記

**出力**:
```
.claude/skills/writing-plans/metrics.jsonl:

{
  "period": "2026-09",
  "total_invocations": 12,
  "success_count": 11,
  "failure_count": 1,
  "success_rate": 0.917,
  "avg_duration_seconds": 1245,
  "versions_used": [1, 2],
  "version_2_success_rate": 0.95
}

{
  "period": "2026-10-01-to-06",
  "total_invocations": 5,
  "success_count": 5,
  "failure_count": 0,
  "success_rate": 1.0,
  "avg_duration_seconds": 890,
  "versions_used": [2]
}
```

**保存場所**: `.claude/skills/<skill-name>/metrics.jsonl` （Git管理、行追記のみ）  
**実行タイミング**: 月末（自動Routine）  
**担当Agent**: Metrics aggregator script  
**失敗時動作**: 集計失敗時は黙って skip。次月末へ carry forward  
**Security分類**: INTERNAL  
**Git管理**: ✅ YES （JSONL行追記形式で差分最小）

**hojo-hq向け変更点**:
- 部門別にメトリクス分類（SNS部のSkill vs 検証部のSkill で条件が異なる）
- 改善効果は「version更新前後の success_rate 上昇」で定義
- メトリクス1件 = 30バイト程度 → 100件/年で3KB。Git肥大化なし

**既存システムで実現済み部分**:
- ✅ Commit履歴 = git log に全記録
- ✅ Skill version = `.claude/skills/*/SKILL.md` の frontmatter に記載可能

**判定**: **あると良い**（MVP段階では簡易版 = metrics.md テキストで十分。JSONL化は Phase 3）

---

### コンポーネント F: Skill Proposer

**優先度**: 🟡 **良い**（ただし初期段階は自動提案禁止。人間トリガーのみ）

**目的**: Experience + Wiki + Metrics から「Skill改善候補」を提案。ただし AI が直接本番 Skill を書き換えることは禁止。「改善のアイデア」だけを提案する段階。

**論文WikiSkillとの関係**: 論文「Skill Proposal Generation」層。ただし本論文と異なり、AI自動提案ではなく、意思決定後の提案。

**入力**:
- Failure pattern（例：「複数Skill同時編集で上書き」）
- Skill metrics（成功率が低いSkill）
- Decision history（「これを改善しろ」という直近の決定）

**処理**:
1. 失敗パターンが再発 → その失敗を防ぐSkill改善を検出
2. 成功率が低いSkillを検出
3. 過去のDecisionで「改善対象」と決定されたSkillをリスト
4. 提案リストを生成（手動トリガー時のみ）

**出力** (docs/proposals/):
```
proposal-<YYYYMMDD-name>.md:

# Skill改善提案: writing-plans v2.2

## 背景
- 成功率: 92% (目標 95%)
- 失敗ケース: 「大規模実装計画でタスク分解が粗くなる」が3件検出
- 決定: 2026-10-06 「Plan quality向上を2026Q4の優先課題に」

## 改善案
1. **タスク粒度チェック**: 各タスクが「2時間以内」で完結するか自動検証
2. **Step granularity の厳格化**: 既存ルール「各stepは1つのアクション」を explicit に
3. **Proportion check 自動化**: 「plan字数 > spec字数」は警告

## 検証方法
- 既存テストケース3件で re-run
- 新たな失敗ケース発見されなければ OK

## 実装者（案）
- Claude Code + systematic-debugging skill

## 見積り
- 実装: 2時間
- テスト・レビュー: 1時間

---
```

**保存場所**: `docs/proposals/` （Git管理）  
**実行タイミング**: 手動トリガー（統括が「改善提案を作って」と指示）  
**担当Agent**: 統括（akari）またはAI assistant（提案作成のみ）  
**失敗時動作**: 提案作成失敗時は「提案できません」と報告  
**Security分類**: PUBLIC  
**Git管理**: ✅ YES

**hojo-hq向け変更点**:
- 既存「学び」「Pattern」と統合
- 提案は「Skill author」へメンション（GitHub review assigned）

**既存システムで実現済み部分**:
- ✅ Skill version管理 = Git tag で実現可能

**判定**: **あると良い**（MVP段階では「アイデア帳」テキストで十分。自動化は Phase 4）

---

### コンポーネント G: Skill Validator

**優先度**: 🔴 **必須**（ただし Phase 2 から）

**目的**: 旧Skill と新Skill を同一Evaluation Set で実行比較。Regression（性能低下）があれば不採用。

**論文WikiSkillとの関係**: 論文「Skill Evaluation」層

**入力**:
- 旧Skill code
- 新Skill code
- Evaluation set（過去のテストケース）

**処理**:
1. 旧Skill で evaluation set を実行 → 結果 A
2. 新Skill で evaluation set を実行 → 結果 B
3. 結果 A と結果 B を比較
   - success_rate 低下 → NG
   - 新しい failure case → NG
   - success_rate 向上 → OK
4. 結果レポートを自動生成

**出力**:
```
docs/evaluations/skill-<name>-eval-20261006.md:

# Skill Evaluation: writing-plans v2.1 vs v2.2

## Evaluation Set
- Test case 1: 小規模実装計画(10タスク未満)
- Test case 2: 中規模実装計画(15～30タスク)
- Test case 3: 大規模実装計画(50タスク以上)

## 旧Version (v2.1) 結果
- Test 1: ✅ PASS (completion rate 95%)
- Test 2: ✅ PASS (completion rate 89%)
- Test 3: ⚠️ PARTIAL (completion rate 68%, タスク粒度粗)

## 新Version (v2.2) 結果
- Test 1: ✅ PASS (completion rate 96%)
- Test 2: ✅ PASS (completion rate 91%)
- Test 3: ✅ PASS (completion rate 78%, ただし粒度改善)

## 判定
- Regression: ❌ NO
- Improvement: ✅ YES （Test 3 で粒度改善）
- 承認: 🟢 **OK** → 次ステップ（三名体制レビュー）へ進む

---
```

**保存場所**: `docs/evaluations/` （Git管理）  
**実行タイミング**: Skill改善提案後、三名体制レビュー前  
**担当Agent**: AI validator script + 検証部（kensho）  
**失敗時動作**: Regression検出時は「不採用」と判定。提案段階に戻す  
**Security分類**: PUBLIC  
**Git管理**: ✅ YES

**hojo-hq向け変更点**:
- Evaluation Set を skill ごとに `<skill-name>-evals.jsonl` で保管
- 既存「検証部」の知見を活用

**既存システムで実現済み部分**:
- ✅ テストケース概念 = existing skills に evals/ folder で既出

**判定**: **本当に必要**（ただし Phase 2 からで OK。Phase 1 では簡易版）

---

### コンポーネント H: Skill Evolution Gate

**優先度**: 🔴 **必須**

**目的**: Skill 更新のワークフロー管理。Proposal → Test → Evaluation → 三名体制 → 小柳 Decision → Merge の順序を絶対守出。

**論文WikiSkillとの関係**: 論文に直接に対応するコンポーネントなし。hojo-hq独自（三名体制 + 小柳Gate）

**入力**:
- Skill改善提案
- Evaluation結果
- 三名体制のコメント

**処理**:
```
PROPOSED
  ↓ [Skill Validator実行]
EVALUATED
  ↓ [Regression なし？]
  ├ YES → REVIEW_REQUIRED
  └ NO  → REJECTED
  ↓ [三名体制レビュー、スイシン・ウタガイ・ベッカイ comment]
TRIPLECHECK_PASSED (全員 approve)
  or
TRIPLECHECK_NEEDS_REVISION (ウタガイ・ベッカイ反対)
  ↓ [反対理由記録]
  ↓ [提案者が revision commit]
  ↓ [再度レビュー]
  ↓
TRIPLECHECK_PASSED
  ↓ [小柳さんへ最終判定request]
AWAITING_DECISION
  ↓ [小柳さんの approve/reject]
  ├ APPROVED → MERGE_READY
  └ REJECTED → REJECTED
  ↓ [if MERGE_READY: PR merge]
MERGED
  ↓ [13リポへ自動配布（update-skills.sh）]
DEPLOYED
```

**保存場所**: GitHub PR status（native機構）  
**実行タイミング**: Skill改善提案から merge まで  
**担当Agent**: GitHub workflow (or Manual)  
**失敗時動作**: Gate の任意のステップで reject → 提案に戻る  
**Security分類**: PUBLIC (decision記録は public/private分離)  
**Git管理**: ✅ YES （PR履歴 = Git全履歴）

**hojo-hq向け変更点**:
- 既存「議事は三名体制」ルールを Skill gate に組み込み
- 小柳さんの approval = `CODEOWNERS` review (GitHub native)
- **Decision 3（半自動）**: AI が Evaluation 結果の要約・三役それぞれの論点案・regression 判定の補助を出してよい。ただし「ウタガイの反対理由」は人間（担当者）が確定し、最終 Gate（Merge 可否）は小柳さんのみ。AI の判定だけで Merge される経路は作らない
- **修正4**: Phase 1 ではこの Gate も Proposer も実装しない。既存 PR レビューのまま

**既存システムで実現済み部分**:
- ✅ PR review = GitHub standard
- ✅ 三名体制 = CLAUDE.md に規定済み
- ✅ 小柳Decision = 既存意思決定プロセス

**判定**: **本当に必要**（既存仕組みの明示化 + 自動化）

---

### コンポーネント I: Rollback

**優先度**: 🔴 **必須**

**目的**: Skill 更新後に問題発生時、直前の stable version へ即座に戻す。ワンコマンドで。

**論文WikiSkillとの関係**: 論文にはなし。hojo-hq の Git discipline で実現。

**処理**:
```bash
# Skill v2.2 で障害発生
# → 直前の v2.1 へロールバック

git checkout <prev-stable-commit> -- .claude/skills/writing-plans/
git commit -m "revert: writing-plans v2.2 → v2.1 (障害対応)"
git push origin main
# 13リポへも自動配布
```

**保存場所**: Git commit history + 緊急停止スイッチ  
**実行タイミング**: 問題検出時（即座）  
**担当Agent（Decision 7）**: **緊急Rollbackは守り部（mamori）が単独で実行可能**。実行後48時間以内に小柳Decision Gateへ上げ、議事（Decision記録）として正式判断・記録する  
**2段階の戻し方**:
1. **緊急停止（commit不要・数秒）**: `.claude/memory.off` ファイルを置く（または `HOJO_MEMORY_OFF=1`）。全hook（Experience / Bootstrap）が先頭でこれを見て即 exit 0。既存の `superpowers-session-start.sh` には影響しない
2. **正式Rollback（Git）**: Phase 1 は1つのマージPRで導入し、マージ時に `wikiskill-phase1-v1` タグを打つ。`git revert -m 1 <merge commit>` で settings.json・hooks・scripts・docs が一括で元に戻る。Skill更新時の戻しは `git checkout <tag> -- .claude/skills/<name>/` （Phase 4〜）  
**失敗時動作**: revert が競合したら守り部が手で解決し、解決内容を議事に残す  
**Security分類**: INTERNAL  
**Git管理**: ✅ YES （全操作git履歴。`.claude/memory.off` は `.gitignore`）

**hojo-hq向け変更点**:
- Skill stable version タグ化 (v2.0, v2.1, v2.2)
- Rollback SOP を docs/ に記載

**既存システムで実現済み部分**:
- ✅ Git rollback = 標準
- ✅ update-scripts.sh で配布自動化済み

**判定**: **本当に必要**（既存Git を活用するだけ）

---

### コンポーネント J: Knowledge Conflict Resolver

**優先度**: 🟡 **良い**（Phase 3 以降）

**目的**: 古い知識と新しい知識が矛盾する場合、どちらを採用するか判定。「新しい = 正しい」ではなく、confidence + scope + timestamp で判定。

**入力**:
- 古い Decision（例：「Skill A の成功率は 80%」、作成日 2026-08-01）
- 新しい Observation（例：「Skill A の成功率は 75%」、観測日 2026-10-06）

**処理**:
1. Source 確認（Decisionなのか Observation なのか）
2. Confidence 確認（データ点数、根拠の質）
3. Scope 確認（全環境 vs 特定環境）
4. Timestamp確認（新しい方が優先）
5. Judgment

**判定ロジック**:
```
if (新しい.timestamp > 古い.timestamp) and (新しい.confidence ≥ 70%)
  → 新しい を採用、古い を archive
elif (古い.scope == "全体" and 新しい.scope == "部分")
  → 「古い」は全体、「新しい」は部分的差異 → 統合記録
else
  → 判定不可、人間へ escalate
```

**出力**:
```
docs/conflicts/
├── resolved-conflict-<id>.md
└── pending-conflicts.md
```

**保存場所**: `docs/conflicts/` （Git管理）  
**実行タイミング**: Monthly knowledge audit  
**担当Agent**: 統括（akari）  
**失敗時動作**: 判定不可時は人間（小柳さん）へエスカレート  
**Security分類**: PUBLIC  
**Git管理**: ✅ YES

**判定**: **あると良い**（Phase 3 以降。初期段階は不要）

---

### コンポーネント K: Privacy Boundary Enforcer

**優先度**: 🔴 **必須**

**目的**: Public/Private を跨いだ知識統合を禁止。Private Experience（glow-docs-private の内容）から生成された Wiki / Skill が public リポへ漏れない仕組み。

**処理**:
1. Experience logger がセッションリポジトリを判定（public or private）
2. Private Experience は `.claude/experience/private/` へ保存
3. Knowledge Extractor が private experience を読む場合、明示的に `source: private` タグを付与
4. Skill Proposer が `source: private` Skillを提案しない
5. CI pipeline（`scripts/check_repo_scope.py`）が「privateタグ付きコンテンツが public repo へ混入」を検出したら fail

**フロー**:
```
glow-docs-private での作業
  ↓ Experience logging
  ↓ .claude/experience/private/
  ↓ Knowledge Extraction (source: private タグ付与)
  ↓ private wiki へ記録
  ↓
hojo-hq (public) での作業
  ↓ 新しいセッション開始
  ↓ Memory Bootstrap: "source: private" のコンテンツは表示しない
  ↓ Skill Proposer: "source: private" のアイデアは採用しない
```

**既存の仕組み**:
- `.gitignore` で glow-ma/data/*.csv (M&A営業数値) を除外
- `scripts/check_repo_scope.py` で forbidden content 検査済み
- `.claude/settings.json` で repo access control 実装中

**保存場所**: 各リポジトリ自身の `.claude/experience/`（logger は `$CLAUDE_PROJECT_DIR` 配下にしか書かない。private リポの記録は private リポに留まる）  
**実行タイミング**: リアルタイム（記録時に `visibility` を判定）+ CI（`repo-scope` ワークフローに検査ステップを追加）  
**判定ルール（Decision 5）**: `git remote get-url origin` が **PUBLIC許可リスト**（hojo-hq 等、明示列挙）に無ければ `visibility: private`。**迷ったら Private**。GLOW世界（❻）の記録は初期分類 Private（glow-docs-private 側）。Public 化は小柳さんの明示的判定（議事）を要する  
**CI検査（`scripts/check_experience_privacy.py`）**: hojo-hq 内の全 Experience について ①`visibility == public` ②`repo == hojo-hq` ③パスがプロジェクト内相対 ④自由記述は `note` のみ（1,000文字以内） ⑤既存 `check_repo_scope.py` の FORBIDDEN_CONTENT に触れない、を検査。1件でも違反したら fail  
**担当Agent**: Hooks（自動） + 守り部（mamori、違反時の対応）  
**失敗時動作**: CI fail → マージ不可 → 守り部が該当行を削除し失敗台帳へ記録  
**Security分類**: CRITICAL  
**Git管理**: ✅ YES

**判定**: **本当に必要**（既存仕組みの強化）

---

### コンポーネント L: Concurrency Protection

**優先度**: 🟡 **良い**（Phase 2 以降、ただし第1優先）

**目的**: 複数 Claude Code セッションの同時編集を排除。セッションA がSkill編集中に、セッションB がSame Skill を編集してセッションA の作業を上書きする問題を防止。

**既存問題例** (2026-08-30):
```
Session A: writing-plans/SKILL.md 編集中
Session B: 同じファイルを編集
→ Session A の commit が Session B で上書きされた
→ cherry-pick で復旧（手動対応）
```

**実装方式選択肢**:

#### 選択肢 1: Git-native lock (推奨)
```
# Session A が Skill編集を開始
mkdir .git-locks/writing-plans.lock
touch .git-locks/writing-plans.lock/session-abc123
# Session B が同じSkillを編集しようとする
→ lock file 検出 → error: "Skill is locked by session-abc123"
→ Session B は待機 or 他のSkillへ変更

# Session A が commit 完了
rm -rf .git-locks/writing-plans.lock
# lock 解放 → Session B が proceed可能
```

**実装場所**: `.claude/hooks/git-lock-manager.sh`

**コスト**:
- 実装: bash script 50行
- 保存: `.git-locks/` directory (git-ignored)

#### 選択肢 2: GitHub lock (API call)
```
# GitHub の create_check 機構を流用
# Session A が Skill編集中に、GitHub check を PENDING にする
# Session B が pull する際に check status を見て判定
# コスト高（API call / GitHub workflow 多用）、遅延リスク
```

**推奨**: **選択肢1** (Git-native, 低遅延、シンプル)

**保存場所**: `.claude/locks/<対象>.lock`（JSON: session_id / acquired_at / heartbeat_at / pid）。`.gitignore` で除外  
**実行タイミング**: 編集開始時に取得、PostToolUse ごとに heartbeat 更新、SessionEnd で解放  
**timeout / stale 判定（Decision 8）**:
- 基本 timeout **30分**（`acquired_at` から）。ただし **heartbeat があれば延長**: `heartbeat_at` から30分以内なら有効
- **stale 判定**: `heartbeat_at` から30分超 **かつ** そのロックの session_id のセッションが終了している（`_local/<session_id>.ended` マーカーあり、または SessionEnd 記録あり）→ 安全に解除可。マーカーが無い場合は「30分超経過」のみでは解除せず、利用者に「stale の可能性。解除しますか」と提示（誤解除で進行中の作業を潰さない）
- 解除は必ず `_audit.log` に記録（誰が・いつ・どのロックを）  
**担当Agent**: hooks（自動）  
**失敗時動作**: 競合時は「<session_id> が <対象> を編集中（最終heartbeat N分前）。待つか別の対象へ」と提示。利用者が判断  
**Security分類**: INTERNAL  
**Git管理**: ❌ NO  
**前提確認（架空設定の禁止）**: Claude Code の settings.json にロック機能は存在しない。上記はすべて hooks + ファイルで実装する。Phase 2 で GitHub 側方式（check run を PENDING にする）と比較したが、遅延・API消費・オフライン不可のため不採用

**判定**: **あると良い**（Phase 2 以降。Phase 1 では「複数セッション同時編集禁止」notice で OK）

---

## コンポーネント優先度サマリー

| 優先度 | コンポーネント | Phase | 目的 |
|---|---|---|---|
| 🔴 必須 | A. Experience Logger | 1 | Raw data 記録 |
| 🔴 必須 | B. Knowledge Extractor | 2 | 知識構造化 |
| 🔴 必須 | C. Decision Memory | 1 | 決定根拠保存 |
| 🔴 必須 | D. Memory Bootstrap | 1 | セッション復元 |
| 🟡 良い | E. Skill Metrics | 3 | 改善効果測定 |
| 🟡 良い | F. Skill Proposer | 3 | 改善アイデア生成 |
| 🔴 必須 | G. Skill Validator | 2 | Regression 検知 |
| 🔴 必須 | H. Skill Evolution Gate | 2 | Merge workflow |
| 🔴 必須 | I. Rollback | 1 | 障害対応 |
| 🟡 良い 　| J. Conflict Resolver | 3 | 知識矛盾解決 |
| 🔴 必須 | K. Privacy Boundary | 1 | PII保護 |
| 🟡 良い 　| L. Concurrency Protection | 2 | 編集競合防止 |

---

## コンポーネント依存グラフ

```
Experience Logger (A)
  ↓ input
Knowledge Extractor (B) ← Decision Memory (C)
  ↓ output
Wiki
  ↓ input
Memory Bootstrap (D) ← Privacy Boundary (K)
  ↓ output
新セッション initialization
  ↓
Skill改善提案
  ↓ input
Skill Proposer (F)
  ↓ output
Skill改善Proposal
  ↓
Skill Validator (G) ← Skill Metrics (E)
  ↓ output
Evaluation 結果
  ↓
Skill Evolution Gate (H) ← Concurrency Protection (L)
  ↓
Merge decide (小柳 Decision Gate)
  ↓ YES
Merge to main
  ↓
Rollback (I) plan 策定
  ↓ NO (障害発生)
Rollback (I) 実行
  ↓
Conflict Resolver (J) 
```

---

## 5段階フェーズ導入計画

### Phase 1: Experience + Decision Memory + Memory Bootstrap基盤 (2026-10-06～10-20, 2週間)

**目標**: 「過去の意思決定と失敗を忘れない」最小構成の動作。**Skill の自動改善・自動更新は実装しない（修正4）。既存110 Skills・13リポ配布方式は変更しない**

**必須 E2E テスト（修正4・小柳さん指示）**:
```
Session A: 議事(Decision)を作る → 作業 → commit → Experience保存 → 終了
   ↓ 完全に別の session_id
Session B: Memory Bootstrap → Session A の Decision と「なぜそう決めたか」が復元される
           → 関連する失敗台帳 FK・再発防止メモも必要に応じて復元される
```
自動テスト（pytest・hook を stdin JSON で模擬）と、実際の Claude Code 2セッションでの手動確認の両方を合格条件にする。詳細は Phase 1 実装計画（`docs/superpowers/plans/2026-10-06-wikiskill-phase1-memory-foundation.md`）

**v1.1 での訂正**: 当初案の `docs/decisions/` 新設・`.gitignore` で experience 除外、は取り下げ。Decision は既存議事に frontmatter を足す方式（C 参照）、Experience は Git に原本保持（Decision 4）

**成果物**:
1. Experience Logger hook (.claude/hooks/experience-logger.sh)
2. Decision Memory 自動スクラッピング (docs/decisions/ 開設)
3. Memory Bootstrap script (scripts/memory-bootstrap.sh)
4. Privacy Boundary baseline (check_repo_scope.py 強化)
5. Rollback SOP 文書化

**実装ファイル**:
- Create: `.claude/hooks/experience-logger.sh`
- Create: `scripts/memory-bootstrap.sh`
- Modify: `docs/decisions/` (folder 開設)
- Modify: `.claude/settings.json` (SessionStart hook 追加)
- Modify: `.gitignore` (experience logging 除外設定)

**受け入れ基準**:
- [ ] Session 開始時に Memory Bootstrap が動作（テスト：過去Decisionをセッション冒頭で表示）
- [ ] Experience logging が JSONL 形式で正確に記録（テスト：5回のセッション実行 → 5つの session-<id>.jsonl 生成）
- [ ] Decision Memory が議事ドキュメントと同期（テスト：新規議事作成 → docs/decisions/ に記録）
- [ ] Privacy Boundary が機能（テスト：private content tag が正しく付与）
- [ ] Rollback がワンコマンド実行可能（テスト：git revert で復旧）

**ロールバック条件**:
- Experience logging が本業務を遅延させる（> 1秒）→ hook 削除
- Memory Bootstrap が不正な情報を出力 → script 無効化
- Private content が誤って public に漏れた → immediate rollback + incident report

**MVP判定**: Phase 1 完了 = MVP として基本動作確認済み ✅

---

### Phase 2: Knowledge Extraction + Skill Validator + Evolution Gate (2026-10-20～11-10, 3週間)

**目標**: Skill改善の「品質ゲート」を機械化。Regression検知、三名体制自動化。

**成果物**:
1. Knowledge Extractor (docs/wiki/ pattern 自動生成)
2. Skill Validator (evaluation set 比較)
3. Skill Evolution Gate (PR workflow 明示化)
4. Concurrency Protection (git-lock 簡易版)

**実装ファイル**:
- Create: `scripts/knowledge-extractor.sh`
- Create: `scripts/skill-validator.sh`
- Create: `docs/wiki/` (folder)
- Create: `.claude/hooks/git-lock-manager.sh`
- Modify: GitHub PR template (Skill evolution gate 明記)

**受け入れ基準**:
- [ ] 過去の failure pattern が自動検出（テスト：既存failure.md 3件から pattern 検出）
- [ ] Skill validator が success rate 低下を検知（テスト：故意に success_rate 低い新Skill code を validator で test → NG判定）
- [ ] Skill Evolution Gate が 6-step workflow を可視化（テスト：PR comment が gate status を表示）
- [ ] Concurrency lock が競合を防止（テスト：2セッション同時編集 → lock file で block）

**ロールバック条件**:
- Knowledge Extractor が誤った pattern を生成（信頼度 < 70%）→ manual extraction に戻す
- Skill Validator が false positive を連発 → regression check 緩和
- Concurrency lock timeout が頻出 → lock timeout 延長 or 削除

---

### Phase 3: Skill Metrics + Skill Proposer + Conflict Resolver (2026-11-10～11-30, 3週間)

**目標**: Skill改善の定量化。何度改善されたか、どう効果があったか可視化。

**成果物**:
1. Skill Metrics aggregation (metrics.jsonl)
2. Skill Proposer (improvement idea 自動生成)
3. Conflict Resolver (知識矛盾検出)
4. Dashboard (改善効果可視化)

**実装ファイル**:
- Create: `scripts/skill-metrics-aggregator.sh`
- Create: `scripts/skill-proposer.sh`
- Create: `scripts/conflict-resolver.sh`
- Create: `docs/dashboard/` (visualization)

**受け入れ基準**:
- [ ] 3 Skills × 3 months の metrics 集計完了（テスト：metrics.jsonl に 9 rows）
- [ ] Success rate 低い Skill が自動提案される（テスト：success_rate < 85% の Skill を detector が検出）
- [ ] Conflict resolver が矛盾を検知（テスト：古いと新しいDecision が contradiction → conflict.md 生成）

---

### Phase 4: Skill Evolution 本格運用 (2026-12-01～12-31, 1ヶ月)

**目標**: 改善・評価・決定・デプロイの完全ループ回転。ただし AI 自動更新は引き続き禁止。

**入力**: Phase 1～3 の all 成果物が動作していることが前提

**実装**: なし（既存のコンポーネントの組み合わせ）

**受け入れ基準**:
- [ ] 提案→評価→三名体制レビュー→決定→デプロイの全ステップが1回以上完了
- [ ] Rollback が2回以上問題なく実行される
- [ ] メトリクスが改善を実証（何度目の改善で success_rate が目標達成）

---

### Phase 5: 完全自動化 + Memory Bootstrap強化 (2027-01-01 以降)

**目標**: 人間の負担最小化。セッション開始時に必要なすべての情報が自動取得。Skill改善の proposal → evaluation → decision を人間関与最小限で。

**前提**: Phase 4 までで完全な audit trail が蓄積されていること

**新機能候補**:
- Skill proposal の自動化（ただし提案まで。実装 & merge は人間）
- Memory Bootstrap の multi-modal （テキスト + 動画チュートリアル + code diff）
- Skill update の自動推論（Phase 4 の failed cases から共通パターン抽出 → fix proposal）

---

## MVP 比較分析

### 候補1: Experience Logger のみ

**構成**: A のみ

**利点**:
- 実装簡単（bash script 50行）
- 記録が確実

**欠点**:
- **新セッションが「思い出さない」**（記録されているだけ）
- 結局、セッション開始時に old logs を手動で検索しないと不要
- 「忘れない環境」ではなく「記録するだけ環境」

**判定**: ❌ MVP不適切

---

### 候補2: Experience Logger + Decision Memory

**構成**: A + C （+ 簡易 B として既存議事と統合）

**利点**:
- 過去の意思決定が明示化
- セッション開始時に「この前の決定」を見直しやすい
- D (Memory Bootstrap) の入力として活用可能
- Implementation 簡単（既存議事の構造化）

**課題**:
- Experience は記録されるが、知識化されない
- Pattern化されないため、毎回同じ失敗を繰り返すリスク

**判定**: 🟡 Partial MVP（初期段階は OK。長期的には Knowledge Extractor 必須）

---

### 候補3: Experience Logger + Decision Memory + Memory Bootstrap（**推奨**）

**構成**: A + C + D （+ B として既存議事と統合）

**利点**:
- 新セッション開始時に「過去の決定」が自動表示
- 「忘れない」が実現される
- 決定の背景を即座に復元→意思決定の正当性確認
- 人間が「あ、そういえばこの前こう決めたんだった」と思い出す仕組み

**課題**:
- Experience を pattern 化する Knowledge Extractor がないため、失敗の再発防止までは至らない
- Pattern 化は Phase 2 で追加

**判定**: ✅ **推奨MVP**

---

## MVP 詳細アクション

> **v1.1**: 以下は起案時の概算。確定したファイル構成・テスト・受け入れ基準は Phase 1 実装計画 `docs/superpowers/plans/2026-10-06-wikiskill-phase1-memory-foundation.md` の「File Structure」を正とする(主な差分: hook ラッパは1本 `.claude/hooks/wikiskill-hook.sh`、Python は `scripts/*.py` 5本 + 共通1本、`docs/decisions/` は新設せず既存議事に frontmatter、Experience 原本は Git 管理)。

**Phase 1 に実装すべき最小セット**:

1. **Experience Logger** (A)
   - 実装: `.claude/hooks/experience-logger.sh` (Bash, 70行)
   - 入力: SessionStart hook + git log
   - 出力: `.claude/experience/YYYYMMDD/session-<id>.jsonl`
   - テスト: 5つのセッション実行 → 5つの JSONL ファイル生成確認

2. **Decision Memory** (C)
   - 実装: `scripts/decision-structurizer.sh` (Bash, 100行)
   - 入力: `docs/議事_YYYYMMDD_<件名>.md`
   - 出力: `docs/decisions/` 配下のメタデータ化
   - テスト: 既存議事3件をメタデータ化 → timestamp+scope で検索可能

3. **Memory Bootstrap** (D)
   - 実装: `scripts/memory-bootstrap.sh` (Bash, 150行)
   - 入力: Session metadata + git branch
   - 出力: SessionStart メッセージに「関連decision 3件」を注入
   - テスト: セッション開始 → stdout に Memory が表示されることを確認

4. **Privacy Boundary** (K) - 強化版
   - 実装: `scripts/check_repo_scope.py` に private-tag check 追加
   - テスト: private Experience を含むProposal を generate → check で catch

**合計実装量**: 
- Bash: 約 320行（3つの script）
- Python: 約 50行（privacy check 追加）
- Markdown: 約 500行（Decision Memory docs）
- **Total: 870行程度**

---

## リスク分析 TOP 5

### リスク1: Privacy Boundary 破壊（CRITICAL）

**シナリオ**: 誤ってprivate Experience が public wiki に記録される
**影響**: 顧客PII / M&A戦略が GitHub 公開
**確度**: 低（既存仕組みで大部分防止済み）
**対策**: 
- check_repo_scope.py を strict mode で実行（CI fail）
- private content tag の自動検証
- 月1回の audit

---

### リスク2: Experience Logger が本業務を阻害（HIGH）

**シナリオ**: Hook が重い → Session ごとに秒単位の遅延
**影響**: ユーザーのセッション開始が遅い
**確度**: 中（Bash hook のオーバーヘッド未測定）
**対策**:
- Hook 実装時に必ず `time` で測定（target: < 500ms）。テストに時間上限を組み込む
- Hook 失敗時は上流 task をブロックしない。**ただし silent にはしない**（修正1: `_audit.log` + `systemMessage` 警告）
- 緊急停止スイッチ `.claude/memory.off` で即時無効化できる（I 参照）

---

### リスク3: Memory Bootstrap が不正情報を出力（MEDIUM）

**シナリオ**: 古い Decision を新しいと勘違いして表示
**影響**: ユーザーが誤った前提で作業
**確度**: 中（timestamp check に頼り切り）
**対策**:
- timestamp + source + confidence を同時表示
- 月末の Conflict Resolver で矛盾 check

---

### リスク4: Concurrency lock が false positive（MEDIUM）

**シナリオ**: セッションA が Skill 編集完了したが、lock file が残存 → セッションB が永遠に待機
**影響**: デッドロック状態
**確度**: 中（timeout 実装不具合の可能性）
**対策**:
- lock timeout = 30分（自動解放）
- lock status をユーザーに表示

---

### リスク5: Git repo 肥大化（MEDIUM）

**シナリオ**: experience JSONL + metrics 毎月蓄積 → 1年で数MB
**影響**: git clone / push が遅い、storage 増加
**確度**: 低（テキスト形式は軽量）
**対策**:
- JSONL 行数制限（12ヶ月 = 月1ファイル、各5KB想定で60KB/年）
- 古いログの archive 化（別ブランチへ移行）

---

## 変更・新規作成ファイル候補一覧

### 既存ファイル（変更対象）

| ファイル | 変更内容 | Phase |
|---|---|---|
| `.claude/settings.json` | SessionStart 配列に2本目(memory-bootstrap)を追加。PostToolUse(Bash/Skill)・UserPromptSubmit・SessionEnd を新設。既存の superpowers hook 行は触らない | 1 |
| `.gitignore` | `.claude/experience/_local/`・`_audit.log`・`.claude/memory.off`・`.claude/locks/` を除外（**原本 JSONL は除外しない**。Decision 4） | 1 |
| `CLAUDE.md` | 「記憶の仕組み(WikiSkill Phase 1)」節を10行程度追加 + 再発防止メモ1行 | 1 |
| `.github/workflows/repo-scope.yml` | `check_experience_privacy.py` のステップを追加 | 1 |
| `docs/全体マップ.md` | 置き場所を1行追加 | 1 |
| `.claude/commands/` | **触らない**（13リポへ丸ごと同期されるため。コマンド追加は配布方式の変更にあたる） | - |
| `scripts/update-skills.sh` | **触らない** | - |
| `.claude/skills/**` | **触らない**（110 Skills 不変） | - |

### 新規作成ファイル

| ファイル | 目的 | Phase | 優先度 |
|---|---|---|---|
| `.claude/hooks/experience-logger.sh` | Experience logging | 1 | 🔴 |
| `scripts/memory-bootstrap.sh` | Memory Bootstrap | 1 | 🔴 |
| `scripts/decision-structurizer.sh` | Decision metadata 化 | 1 | 🔴 |
| `.claude/experience/` | Experience storage | 1 | 🔴 |
| `docs/decisions/` | Decision Memory storage | 1 | 🔴 |
| `docs/wiki/` | Knowledge base root | 2 | 🔴 |
| `scripts/knowledge-extractor.sh` | Pattern 化 | 2 | 🔴 |
| `scripts/skill-validator.sh` | Regression check | 2 | 🔴 |
| `scripts/skill-metrics-aggregator.sh` | Metrics 集計 | 3 | 🟡 |
| `scripts/skill-proposer.sh` | Improvement proposal | 3 | 🟡 |
| `scripts/conflict-resolver.sh` | Knowledge conflict 検出 | 3 | 🟡 |
| `docs/decisions/decision-template.md` | Template | 1 | 🟡 |
| `docs/wiki/patterns-template.md` | Template | 2 | 🟡 |
| `.claude/hooks/git-lock-manager.sh` | Concurrency protection | 2 | 🟡 |

---

## 「今は作らないもの」（Phase 5 以降）

1. **Skill auto-update engine**  
   理由: 人間Decision Gate を絶対守出。提案までが限界（初期段階）

2. **Multi-modal Memory Bootstrap** (動画チュートリアル + code diff)  
   理由: テキストbase で十分。チューリアル化は Phase 5

3. **Obsidian plugin** (local sync 高速化)  
   理由: GitHub sync で十分。Plugin は optional

4. **ML-based pattern detection**  
   理由: Rule-based extraction で十分。ML導入は慎重に

5. **Real-time Knowledge collaboration**  
   理由: Async git-based で十分。Real-time は複雑化のリスク

6. **API gateway** (external service連携)  
   理由: 現在 public / private 分離で十分

---

## 小柳さんの承認が必要な Decision リスト

> **v1.1: 下記8件はすべて 2026-10-06 に承認済み（冒頭「承認済み Decision」表を正とする）。以下は起案時の選択肢の記録として残す。**

1. **Memory Bootstrap の自動化 on/off**  
   - 新セッション開始時に「過去Decision」を自動表示するか否か
   - リスク: ユーザーが表示を邪魔に思うかも
   - 代替案: Opt-in（毎回`/memory`コマンドで明示的に取得）

2. **Decision Memory の「見直し期限」デフォルト値**  
   - 現在: 6ヶ月を仮定
   - 変更可能か？（決定ごとに異なる期限を許すか）

3. **Skill改善の「三名体制 自動化」**  
   - 現在: PR review コメントで三名体制実装
   - 自動化のリスク: GitHub workflow で「誰が approveしたか」を自動判定できるか

4. **Experience logging の「保存期限」**  
   - 現在: 永続保存を想定
   - Archive化の時期（1年後？2年後？）

5. **Private/Public 境界の「新規ドメイン」対応**  
   - 例: enLife データが非公開になった（2026-08-22 に kakei-crm へ移設）
   - 将来「GLOW 世界へ推進」(❻)のデータはどこに保存するか

6. **Knowledge Extractor の「手動化 vs 自動化」度合い**  
   - 現在: 月末に統括(akari)が手動確認
   - 自動化（AI pattern 検出）を許すか否か

7. **Skill update の「rollback 権限」**  
   - 誰が rollback を決定できるか（守り部？統括？小柳？）

8. **Concurrency lock の「timeout 値」**  
   - 現在: 30分を想定
   - 変更可能か

---

## 既存システムで実現済みの部分（新設不要）

| 機能 | 既存実装 | 場所 |
|---|---|---|
| Commit履歴追跡 | Git log | 標準 |
| Skill version管理 | Git tag + frontmatter | `.claude/skills/*/SKILL.md` |
| PR review (三名体制) | GitHub native | PR機構 |
| 小柳 Decision Gate | 既存意思決定プロセス | CLAUDE.md |
| Update-scripts.sh 配布 | 既存自動同期 | `scripts/update-skills.sh` |
| Privacy境界 | .gitignore + check_repo_scope.py | 既存 |
| Obsidian sync | GitHub Actions + Git plugin | obsidian-vault repo |
| Hook機構 | Claude Code SessionStart | `.claude/settings.json` |
| Agent定義 | Role-based agents | `.claude/agents/` |
| Skill登録 | SKILL.md | `.claude/skills/` |

---

## 設計原則の再確認

### 既存hojo-hqを最大限再利用 ✅

| 既存要素 | 活用方法 |
|---|---|
| `docs/議事/` | Decision Memory の source |
| `docs/学び/` | Knowledge Extractor の integration先 |
| `.claude/agents/` | Memory Bootstrap で推奨Agent表示 |
| `.claude/hooks/` | experience-logger を追加（既存hook と並行） |
| `scripts/update-skills.sh` | skill rollback の基盤 |
| `.gitignore` | private content 除外ルール活用 |

### GitHub Single Source of Truth 維持 ✅

- すべてのログ・メタデータをGitで管理
- Obsidian は「読み取り専用ビュー」
- Commit履歴で全操作追跡可能

### Public/Private 絶対分離 ✅

- private Experience = `.claude/experience/private/`
- private Decision = `docs/decisions/private/`（private repo内のみ）
- Memory Bootstrap が private content を表示しない仕組み

### 既存110 Skills + 13リポ同期 を壊さない ✅

- Skill自体は変更なし
- Skill metadata (metrics / version) を追加するのみ
- update-scripts.sh も変更なし

### 三名体制を維持・強化 ✅

- PR review が三名体制を実装
- ウタガイ反対理由の記録を自動検証

### 人間Decision Gate 絶対死守 ✅

- Skill update は Proposal → Evaluation → 三名体制 → 小柳承認 → Merge
- AI自動update は禁止

### すべてGit追跡・rollback可能 ✅

- ログ・メタデータ = git管理
- lock files = .gitignore で除外（状態, not versioned）
- git revert で即座にrollback

---

## 結論

### 推奨アーキテクチャ

```
Experience Logger (A)
  ↓
Private Boundary (K)
  ↓
Decision Memory (C) + Knowledge Extractor (B)
  ↓
Wiki
  ↓
Memory Bootstrap (D)
  ↓
新セッション start
  ↓
Skill改善Proposal (F) ← Metrics (E)
  ↓
Skill Validator (G)
  ↓
Skill Evolution Gate (H)
  ↓
三名体制レビュー
  ↓
小柳 Decision Gate
  ↓
Merge (+ Concurrency Protection L)
  ↓
13リポ自動配布
  ↓
Rollback (I) on demand
  ↓
Conflict Resolver (J) monthly
```

### MVP

**Phase 1 実装対象**:
- A: Experience Logger
- C: Decision Memory
- D: Memory Bootstrap
- K: Privacy Boundary
- I: Rollback SOP

**合計実装**: Bash 320行 + Python 50行 + Markdown 500行 = 870行

**見積り**: 1週間（expert）/ 2週間（standard）

### 導入順序

1. Phase 1: 基盤（Experience + Decision + Memory Bootstrap）**2026-10-06～10-20**
2. Phase 2: 品質ゲート（Knowledge + Validator + Gate + Lock）**2026-10-20～11-10**
3. Phase 3: 測定（Metrics + Proposer + Conflict）**2026-11-10～11-30**
4. Phase 4: 本格運用（全ループ回転）**2026-12-01～12-31**
5. Phase 5: 自動化（人間関与最小化）**2027-01-01 以降**

### リスク TOP 5

1. **Privacy Boundary 破壊** (CRITICAL) → check_repo_scope.py strict
2. **Experience Logger 重い** (HIGH) → timeout 500ms + silent fail
3. **Memory Bootstrap 誤情報** (MEDIUM) → confidence level 表示
4. **Concurrency lock deadlock** (MEDIUM) → 30分timeout
5. **Git repo 肥大化** (MEDIUM) → 月1ファイル archive

### 変更ファイル候補（7個）

| ファイル | 内容 | Phase |
|---|---|---|
| `.claude/settings.json` | SessionStart hook 追加 | 1 |
| `.gitignore` | experience / lock files 除外 | 1 |
| `CLAUDE.md` | ルール追加 | 1 |
| `scripts/update-skills.sh` | (no change) | - |
| `docs/議事/` template | (format guide 追加) | 1 |

### 新規ファイル候補（15個以上）

Phase 1: 5個（hooks × 3 + docs × 2）  
Phase 2: 4個（scripts × 3 + .github/ workflow × 1）  
Phase 3: 4個（scripts × 3 + docs/ × 1）

### 「今は作らないもの」（8個）

1. AI auto-update engine
2. Multi-modal tutorial
3. Obsidian plugin
4. ML pattern detection
5. Real-time collab
6. API gateway
7. External service 連携
8. Dashboard (visualization)

### 小柳さん承認 Decision（8個）

1. Memory Bootstrap 自動化 on/off
2. Decision「見直し期限」デフォルト値
3. 三名体制「自動化」可否
4. Experience「保存期限」
5. 新規ドメイン(❻GLOW世界)のdata保存場所
6. Knowledge Extractor「自動化」度合い
7. Skill rollback「権限」設定
8. Concurrency lock「timeout」値

---

## 設計完成

**本設計書の段階**: 実装前の承認段階  
**状態**: READ-ONLY （ファイル変更なし）  
**次ステップ**: 小柳さん review → Decision → writing-plans で実装計画

**設計期間**: 2026-10-06 (7時間)  
**担当**: Claude Code  

---

**作成ファイル**: `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`  
**総行数**: 約 1,400行  
**総セクション数**: 13 + 8 + 5 = 26個

設計仕様書、以上です。

