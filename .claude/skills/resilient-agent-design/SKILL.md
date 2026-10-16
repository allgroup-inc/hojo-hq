---
name: resilient-agent-design
description: "GitHub Actions / cron / Claude Routines / /loop など、繰り返し・長時間・無人稼働する自動化やAIエージェントを新規設計するとき、既存のものをレビューするとき、または『壊れる・重複する・止まらない・原因不明』のトラブルが起きたときに必ず使う。24時間自走する自動化を壊れにくく作るための7原則と、実行方式の選び方を提供する。"
---

# 壊れにくい自動化・エージェント設計

24時間/無人で動く自動化の本質は、AIの賢さではなく**壊れにくいシステム設計**。
このスキルは、このリポジトリの自動化(cron・定期ワークフロー・チャットボット等)を
新規に作る/直す/レビューするときに使う。既存の自動化がこの考え方に近い形(定期実行の
基盤 = コード主体のWorkflow、Claude APIでの構造化・下書き生成 = Agent判断部分、
社外への副作用 = 人間の承認ゲート)で作られていれば、新しい自動化もこの型に揃える。

> ALLGROUP共通スキル(hojo-hqを本店として複数リポジトリで共有)。このファイルは
> 特定事業のワークフロー名を前提にしないこと。具体例が必要な場合は「このリポジトリの
> 実際の自動化(cronジョブ名・データ保存先等)を確認したうえで」と案内するに留める。

## 大原則

最強のAIエージェント = 止まらないAIではない。
**異常時に安全停止し、原因を残し、正しい地点から再開できるAI**。
運用で重要なのは「成功したか」だけでなく、**後から理由を説明できること**。

---

## Step 1: エージェント設計（責務と入出力の明確化）

### 目的
各エージェントの役割を明確にし、依存関係を最小化する。単体で検証・再実行可能な設計にする。

### 実行方法
1. **責務を1つに絞る**: 1エージェント = 1判断領域(例: 「重要度評価」「データ正規化」「要約生成」のそれぞれ別)
2. **入出力を形式化する**: JSON Schema で入力/出力を定義し、AI以外のコードで検証可能にする
3. **失敗時の代替策を決める**: 「このエージェント失敗時は、下流工程をスキップ/別エージェント起動/人間に通知」の3択を明示
4. **エージェント間インターフェース**: 固定フォーマット(JSON/CSV等)で受け渡し、会話文脈に状態を持たせない

### 検証メソッド
- [ ] エージェント単体で入力例5つを処理し、出力が期待スキーマに一致
- [ ] 責務が他エージェントと重複していないか確認
- [ ] 失敗時の処理フロー(skip/fallback/notify)が文書化されている
- [ ] 入出力スキーマが tools.json または schema.yaml に記録されている

---

## Step 2: 失敗モードの特定（timeout, API error, logic error）

### 目的
起こりうる全ての故障パターンを事前に想定し、それぞれへの対応を決める。

### 実行方法
1. **Timeout 失敗**: エージェント応答が N 秒以内に来ない(デフォルト: 30秒)
   - 対応: リトライ/キューイング/タイムアウト短縮/スキップ のいずれか
2. **Network/API 失敗**: 外部API呼び出し時の 4xx/5xx/接続エラー
   - 対応: 一時エラー(5xx/timeout)は後述のリトライへ、入力エラー(4xx)は人間確認へ
3. **Logic エラー**: エージェントの出力が不正なJSON/スキーマ不一致/値域外
   - 対応: 再実行/ログ記録/人間確認(品質基準で決定)
4. **Context 破壊**: 複数エージェント並列実行時に状態が不整合になる
   - 対応: 状態ファイルのロック/版管理/トランザクション
5. **Cascading 失敗**: 上流エージェント失敗→下流が全て失敗する連鎖
   - 対応: 各エージェントの失敗を独立させ、下流への影響最小化

### 検証メソッド
- [ ] 対象エージェント/ワークフローについて、起こりうる全ての失敗パターンをリストアップ
- [ ] 各失敗パターンについて、対応コード(例外ハンドラ/リトライロジック)が実装済み
- [ ] ログに失敗モード(型)と詳細メッセージが記録される
- [ ] 下流の依存エージェントへの影響が「なし / 遅延 / スキップ / 失敗」の4択で明記されている

---

## Step 3: リトライ戦略の実装（exponential backoff）

### 目的
一時的な障害から自動回復し、同時に無限リトライを防ぐ。

### 実行方法
1. **リトライ対象を絞る**: 以下のみ再試行
   - HTTP 408, 429, 5xx (一時サーバ障害)
   - Timeout (実行時間超過)
   - 特定の一時エラー(例: Rate Limit, Service Unavailable)

2. **リトライ対象外(人間確認へ)**: 以下は再試行NG
   - HTTP 400, 401, 403, 404 (入力エラー/権限不足/対象不在)
   - JSON 解析失敗・スキーマ不一致
   - 実行禁止操作(削除・本番送信等)

3. **Backoff 実装**: Exponential Backoff + Jitter
   ```
   wait = min(base_delay * (2 ^ retry_count) + random(0, base_delay), max_delay)
   例: base_delay=2s, max_delay=120s
     1st retry: 2s + jitter
     2nd retry: 4s + jitter
     3rd retry: 8s + jitter
     4th retry: 16s + jitter
     5th retry: 32s + jitter (max_delay に達する前)
   ```

4. **リトライ上限**: 最大3回（通常） / 最大5回（重要処理のみ）
5. **コスト監視**: リトライによるAPI呼び出し費用を監視し、超過時に停止
6. **ログに記録**: retry_count / last_error_type / wait_duration を状態に保存

### 検証メソッド
- [ ] リトライ対象と非対象が、コード上で分岐している
- [ ] Exponential Backoff の実装が、base_delay/max_delay/jitter を含む
- [ ] 最大リトライ回数がハードコード化されている(無限ループ防止)
- [ ] リトライループを脱出する条件(成功/上限到達/非リトライエラー)が全て列挙
- [ ] リトライ履歴(回数・待機時間・エラー型)がログに記録される
- [ ] リトライコスト(API呼び出し数 × 単価)が集計され、予算超過時に通知

---

## Step 4: 状態保存と復旧（context/state preservation）

### 目的
実行中断後、状態を失わず正しい地点から再開する。

### 実行方法
1. **状態ファイルの構造**:
   ```json
   {
     "job_id": "task-202610051234",
     "workflow_version": "v2.1",
     "status": "in_progress",
     "current_step": 3,
     "completed_steps": [1, 2],
     "pending_steps": [4, 5, 6],
     "step_outputs": {
       "step_1": { "records_fetched": 152 },
       "step_2": { "duplicates_removed": 15 }
     },
     "retry_count": 1,
     "last_error": {
       "type": "HTTPError",
       "status": 503,
       "message": "Service Unavailable",
       "timestamp": "2026-10-05T12:34:56Z"
     },
     "execution_cost_usd": 0.045,
     "updated_at": "2026-10-05T12:34:56Z",
     "idempotency_key": "workflow-daily-2026-10-05"
   }
   ```

2. **保存タイミング**:
   - ステップ完了時(毎ステップ後)
   - エラー発生時(失敗箇所を記録)
   - リトライ前(状態を保存してから待機)

3. **復旧フロー**:
   - ワークフロー開始時、同じ `idempotency_key` の状態を検索
   - 既に完了していれば(status=completed)→ スキップ
   - 進行中なら(status=in_progress)→ current_step から再開
   - 失敗していれば(status=failed)→ last_error を確認し、人間判断/自動リトライ

4. **保存先**: リポジトリが GitHub Actions 中心なら `data/job-states/<job_id>.json`

### 検証メソッド
- [ ] 状態ファイルにジョブID/ワークフロー版/ステップ番号/完了ステップ/実行コスト が記録されている
- [ ] ステップ完了時に状態ファイルが更新される(git commit で監査ログになる)
- [ ] ワークフロー再開時、状態ファイルから current_step を読んで再開する(1からではなく)
- [ ] completed_steps と pending_steps が常に sync している(完了したステップが再実行されない)
- [ ] idempotency_key が、同じワークフロー・同じ日時なら一致している(べき等性)
- [ ] 状態ファイル自体が壊れた時の fallback(例: current_step=1 からリスタート)が実装されている

---

## Step 5: 並列エージェント管理（dependency detection, execution ordering）

### 目的
複数エージェントを並列実行しながら、依存関係を正しく管理し、競合状態を防ぐ。

### 実行方法
1. **依存関係グラフの作成**:
   ```
   Agent A: データ取得 → 出力: records.json
   Agent B: 重要度評価 → 入力: records.json → 出力: scored.json
   Agent C: 要約生成 → 入力: scored.json → 出力: summary.md
   Agent D: 画像生成 → 入力: summary.md → 出力: images/
   Agent E: SNS投稿文生成 → 入力: summary.md, images/ → 出力: posts.json
   
   依存: A → B → C → {D, E}
   (C 完了後、D と E は並列可能)
   ```

2. **実行順序の決定**:
   - Topological Sort で依存順序を決定
   - 同じレイヤー(依存なし)は並列実行
   - 下流が上流を待つ構造(上流先行)

3. **状態ファイルによる同期**:
   - Agent B は Agent A の `records.json` が存在するまでポーリング/待機
   - ポーリング: 最大5分、1秒間隔でチェック → 存在しなければ失敗通知

4. **出力ファイルのロック**:
   - 出力ファイル生成前に `.lock` ファイルを作成
   - 他エージェントが `.lock` を見たら、そのエージェント実行完了を待つ
   - 出力ファイル完成後に `.lock` を削除

5. **並列実行での失敗分離**:
   - Agent D 失敗 → Agent E には影響させない
   - 各エージェントの失敗は独立フラグ(例: `step_5_agent_d_failed=true`)に記録
   - 最終的に「全エージェント成功」「部分失敗」「完全失敗」の3段階で報告

### 検証メソッド
- [ ] 依存関係グラフが DAG(有向非環グラフ)である(循環依存なし)
- [ ] Topological Sort の実装が存在し、実行順序が正確
- [ ] 同じレイヤーのエージェントが実際に並列実行される(逐次実行でない)
- [ ] ファイル出力のロック機構が実装されている(`.lock`)
- [ ] 下流エージェントが上流出力の存在をポーリング確認する
- [ ] エージェント個別の失敗が、他エージェントの成功を邪魔しない(failure isolation)
- [ ] 全エージェント完了後、「成功 / 部分失敗 / 完全失敗」が正確に判定される
- [ ] 並列実行でのタイムアウト・デッドロックが起きない(例: A が B 待機、B が A 待機)

---

## 4層で設計する

| 層 | 問い | 例 |
|---|---|---|
| Trigger | いつ始めるか | 毎朝9時 / PR作成時 / フォーム送信 / API呼び出し |
| Workflow | 何をどの順で進めるか | 取得→重複除去→AI判断→保存→通知→承認 |
| Agent | どこでAIに考えさせるか | 分類・重要度評価・要約・返信案・原因調査 |
| Guardrail | どこで止めるか | 最大リトライ回数・承認制・予算上限・読み取り専用 |

NG例: 収集→記事作成→画像生成→投稿→改善まで全部AIに丸投げ。
OK方針: 機械的処理はコード/ワークフローへ、判断だけAIへ。

## 7つの設計原則

**① AIへ渡すのは「判断」だけ**
コードでやる: 記事取得・日付絞り込み・重複削除・JSON保存・通知・集計・スキーマ検証。
AIでやる: 重要ニュース選定・切り口検討・意図分類・要約・返信案・最適案選択。

**② 各工程に完了条件を持たせる**
「AIの“できました”」ではなく、**システム側で判定する**。
例: 対象媒体5件確認済み/過去24時間の記事のみ/URL重複除去済み/上位5件選定/
各要約200字以内/元URL保持/JSONスキーマ適合。

**③ 状態を外部へ保存する**
会話履歴(コンテキスト)に状態を持たせない。長い記憶より、仕事の状態を外部へ持たせることが先。
保存項目: `job_id` / `workflow_version` / `status` / `current_step` / `completed_steps` /
`pending_steps` / `retry_count` / `idempotency_key` / `last_error` / `cost_usd` / `updated_at`。
保存先は規模に応じて: 小規模=JSON/SQLite、チーム=PostgreSQL、長時間ワークフロー=Trigger.dev等。
GitHub Actions中心のリポジトリでは、`data/`配下のJSONファイル+Gitコミットで状態を
永続化する構成が相性が良い(実行履歴と状態変化がそのまま監査ログになる)。実際の
保存先ファイル名・構成はリポジトリごとに異なるので、着手前にそのリポジトリの
`data/`配下・既存ワークフローを確認してから同じ型に合わせること。

**④ 重複実行を「べき等性」で防ぐ**
`idempotency_key` 例: `news-summary:2026-07-30` / `invoice-reminder:customer-123:2026-07`。
状態遷移: completed(何もしない)→running(状態を返す)→failed(再開条件確認)→未作成(新規開始)。
送信・公開・課金・削除のような**副作用処理には必須**。

**⑤ リトライに上限と種類を持たせる**
- 再試行してよい: 一時ネットワーク障害・レート制限・サービス一時停止・タイムアウト・5xx
- 人間確認が必要: 入力意味が曖昧・想定外形式・仕様不一致・品質基準未達・低信頼判断
- 再試行してはいけない: 認証無効・権限不足・対象不存在・禁止操作・入力不正

ルール例: 一時エラーのみ最大3回、30秒→2分→10分のバックオフ、5分以内に同じツール3回で停止、
累計コスト超過(例: 3ドル)で停止、いずれもSlack/LINE等へ通知。

**⑥ 権限は最小限から始める**
原則付与しない: 本番データ削除・無制限送信・任意シェル実行・全リポジトリ書き込み・決済・
SNS無承認投稿・広範な機密アクセス。
段階的に上げる: ①読み取りのみ → ②限定書き込み(特定範囲の編集・設定変更のみ) →
③承認後の外部操作 → ④条件付き自動実行(ガードレール内で自動化を拡大)。
常に「最小」から開始する。

**⑦ Hookと監視で「守る・見る・止める」を仕組みにする**
Hook活用例: 危険コマンドの検知と停止・編集後にformatter/lint/typecheck/test・
自動ログ保存・連続同一処理の検知とブレーキ・外部操作前の承認(Human-in-the-Loop)。
最低限残すログ: 開始時刻・入力・使用ツール・出力・エラー・リトライ回数・実行コスト・
承認者・状態遷移。
**守らせたいルールは、文章(CLAUDE.md等)ではなく権限・コード・環境で守る。**
「本番を変更しないで」と書くだけはNG。読み取り専用認証・書き込みツールを渡さない・
対象ディレクトリ制限・Hookでの危険操作ブロック・実行環境分離・接続先制限で担保する。
**「静かな脱落」に注意**: 任意参加の外部依存(例: 補助的な外部AI・オプションのAPI)を
「失敗してもスキップ」にすると、恒久障害でも誰も気づかず機能が黙って消える。
参加率を毎回記録し、参加0が続いたら警告を出す(沈黙は成功と見分けがつかない)。
実例: hojo-hqの原文照合はGemini参加率を履歴JSONに記録し、脱落を検知できるようにしている。

## 分業は慎重に(AIを増やせば速くなるわけではない)

並列化で増えるコスト: 引き継ぎ・状態同期・重複作業・形式調整・コンテキスト複製・
権限管理・失敗追跡・実行コスト・競合状態。
分割してよい条件: 作業が独立/同時実行の意味がある/入出力形式が固定/失敗部分だけ再実行可能/
権限分離できる/同時更新しない/時間短縮がコスト増を上回る。
**結論: 最初は1体のエージェントが小さなワークフローを順番に進める設計で十分。**

## 実行方式の選び方(このセッションで使える手段との対応)

| 方式 | 向いている用途 | 向かない用途 |
|---|---|---|
| `/loop`(Skill) | 短時間監視・PR/Issueのポーリング・開発中の試作・デプロイ監視 | PCを閉じても継続したい処理・数週間の永続運用・完全無人の本番業務(セッション内のみ、作成から7日で終了) |
| Claude Routines(`create_trigger`) | 毎朝の情報収集・定期整理・PRレビュー・デプロイ後検証 | 最小間隔1時間・承認ダイアログ不可・権限は最小限に |
| GitHub Actions/Power Automate等の通常クラウドワークフロー | AI判断が少ない決まった処理・データ取得/変換/保存/通知(このリポジトリの標準ツールを確認して使う) | AIの判断が多い・柔軟性が必要な処理 |
| Claude Agent SDK | 自社アプリへの組み込み・独自UI・細かな権限制御 | 実行環境/スケジューリング/保存/キュー/監視/リトライ/シークレット/コスト制御を自前設計する前提 |
| Managed Agents | 長時間・非同期エージェント・実行基盤管理を減らしたい | 現在ベータ版、本番の主軸にはまだ不向き |

選び方まとめ: まず試作=`/loop` → 安定運用に載せる=Claude Routines またはこのリポジトリの
標準クラウドワークフロー基盤(GitHub Actions・Power Automate等、リポジトリごとに異なる) →
自社アプリに組み込む=Agent SDK。どれを選んでもHooks・権限制御・環境分離は追加する。

---

## 実装例: 複数エージェント並列実行パターン

このセクションは、hojo-hq スキル改善プロジェクト Phase 2 Week 1 で実施した、
5つのスキルを並列改善する際に実装した失敗復旧パターンです。

### ワークフロー概要
**目標**: 5つの独立したスキル(transcription-analysis-hojo, system-design-patterns,
educational-content-design, data-insights-extraction, hojo-lighthouse-triage)を
同時に改善し、各スキルは独立して失敗/復旧できる状態に整える。

### エージェント定義(入出力スキーマ)
```json
{
  "agents": [
    {
      "agent_id": "agent_transcription",
      "responsibility": "音声データの文字起こしと構造化",
      "input_schema": {
        "type": "object",
        "properties": {
          "audio_path": { "type": "string" },
          "language": { "type": "string", "enum": ["ja", "en"] },
          "format": { "type": "string" }
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "transcript": { "type": "string" },
          "segments": { "type": "array" },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      },
      "failure_fallback": "skip_downstream_processing"
    },
    {
      "agent_id": "agent_system_design",
      "responsibility": "アーキテクチャパターン評価",
      "input_schema": {
        "type": "object",
        "properties": {
          "architecture_description": { "type": "string" },
          "constraints": { "type": "array" }
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "assessment": { "type": "string" },
          "score": { "type": "number" },
          "recommendations": { "type": "array" }
        }
      },
      "failure_fallback": "notify_human"
    }
  ]
}
```

### リトライ実装例(Python)
```python
import time
import random
from enum import Enum

class RetryableError(Enum):
    TIMEOUT = "timeout"
    HTTP_5XX = "http_5xx"
    RATE_LIMIT = "rate_limit"

class NonRetryableError(Enum):
    HTTP_4XX = "http_4xx"
    SCHEMA_MISMATCH = "schema_mismatch"
    AUTH_FAILED = "auth_failed"

def exponential_backoff_retry(
    func, 
    max_retries=3, 
    base_delay=2, 
    max_delay=120
):
    """
    Exponential backoff with jitter.
    Delays: 2s, 4s, 8s, 16s, ... (capped at 120s)
    """
    for attempt in range(max_retries + 1):
        try:
            result = func()
            if attempt > 0:
                log_event({
                    "type": "retry_success",
                    "attempt": attempt,
                    "total_retries": max_retries
                })
            return result
        except Exception as e:
            error_type = classify_error(e)
            
            if error_type not in [e.value for e in RetryableError]:
                raise  # Non-retryable error, escalate
            
            if attempt >= max_retries:
                log_event({
                    "type": "retry_exhausted",
                    "error_type": error_type,
                    "total_attempts": max_retries + 1
                })
                raise
            
            # Calculate wait time
            wait_seconds = min(
                base_delay * (2 ** attempt) + random.uniform(0, base_delay),
                max_delay
            )
            
            log_event({
                "type": "retry_attempt",
                "attempt": attempt + 1,
                "error_type": error_type,
                "wait_seconds": wait_seconds
            })
            
            time.sleep(wait_seconds)
    
    return None
```

### 状態保存と復旧(状態ファイルフォーマット)
```json
{
  "job_id": "skill-improvement-phase2-week1",
  "workflow_version": "v1.0",
  "status": "in_progress",
  "current_step": 3,
  "completed_steps": [1, 2],
  "pending_steps": [4, 5],
  "execution_plan": {
    "step_1": {
      "agent_id": "agent_transcription",
      "dependency": "none",
      "status": "completed",
      "output_file": "data/transcripts/output_20261005.json"
    },
    "step_2": {
      "agent_id": "agent_system_design",
      "dependency": "none",
      "status": "completed",
      "output_file": "data/architecture/assessment_20261005.json"
    },
    "step_3": {
      "agent_id": "agent_educational_content",
      "dependency": "step_1",
      "status": "in_progress",
      "output_file": "data/content/guide_draft_20261005.md",
      "last_checkpoint": "outline_phase_completed"
    },
    "step_4": {
      "agent_id": "agent_data_insights",
      "dependency": "step_1",
      "status": "pending",
      "output_file": "data/insights/analysis_20261005.json"
    },
    "step_5": {
      "agent_id": "agent_lighthouse",
      "dependency": "none",
      "status": "pending",
      "output_file": "data/lighthouse/report_20261005.json"
    }
  },
  "retry_history": [
    {
      "step": 3,
      "attempt": 1,
      "error_type": "timeout",
      "wait_seconds": 2.5,
      "timestamp": "2026-10-05T12:30:00Z"
    }
  ],
  "execution_cost_usd": 0.23,
  "updated_at": "2026-10-05T12:34:56Z",
  "idempotency_key": "skill-improvement-phase2-20261005"
}
```

### 並列実行と依存管理(Topological Sort)
```python
from typing import Dict, List, Set

class ParallelWorkflow:
    def __init__(self, agents: Dict):
        self.agents = agents
        self.execution_order = self._topological_sort()
    
    def _topological_sort(self) -> List[List[str]]:
        """
        Returns agents grouped by execution layer.
        Layer 0: no dependencies
        Layer 1: depends on Layer 0
        Layer 2: depends on Layer 0 or 1, etc.
        """
        layers = []
        completed = set()
        remaining = set(self.agents.keys())
        
        while remaining:
            current_layer = []
            for agent_id in remaining:
                dependencies = self.agents[agent_id].get("dependency", [])
                if all(dep in completed for dep in dependencies):
                    current_layer.append(agent_id)
            
            if not current_layer:
                raise ValueError("Circular dependency detected")
            
            layers.append(current_layer)
            completed.update(current_layer)
            remaining -= set(current_layer)
        
        return layers
    
    def execute_parallel(self):
        """
        Execute agents layer by layer.
        Within each layer, agents run in parallel.
        """
        for layer_idx, layer_agents in enumerate(self.execution_order):
            print(f"Layer {layer_idx}: Executing {layer_agents} in parallel")
            
            results = {}
            failures = {}
            
            # Simulate parallel execution
            for agent_id in layer_agents:
                try:
                    output = self._execute_agent_with_retry(agent_id)
                    results[agent_id] = output
                except Exception as e:
                    failures[agent_id] = str(e)
                    log_event({
                        "type": "agent_failure",
                        "agent_id": agent_id,
                        "error": str(e),
                        "layer": layer_idx
                    })
            
            # Failure isolation: if one agent fails, others in layer continue
            if failures and all(
                self.agents[a].get("failure_fallback") != "fail_all"
                for a in failures.keys()
            ):
                print(f"Layer {layer_idx}: Partial failures isolated. Continuing...")
            elif failures:
                raise Exception(f"Layer {layer_idx} failed completely: {failures}")
    
    def _execute_agent_with_retry(self, agent_id: str):
        """Execute single agent with exponential backoff retry."""
        def work():
            # Call actual agent
            return call_claude_api(
                agent_id=agent_id,
                input_schema=self.agents[agent_id]["input_schema"]
            )
        
        return exponential_backoff_retry(work, max_retries=3)
```

### リアルワールド例: hojo-hq スキル改善 Phase 2 Week 1
実際のスキル改善では、以下の構成で5つのスキルを並列改善しました:

```
Layer 0 (no dependency):
- transcription-analysis-hojo: 音声処理スキルの手順化
- system-design-patterns: アーキテクチャパターンの整理
- educational-content-design: 教育コンテンツ設計の体系化

Layer 1 (depends on Layer 0):
- data-insights-extraction: 抽出パターンの文書化

Layer 2 (depends on Layers 0-1):
- hojo-lighthouse-triage: パフォーマンス検証スキル

各スキルの改善タスク:
- Subtask A: SKILL.md を Step セクションに細分化
- Subtask B: 実装例を追加(Python/JavaScript コード)
- Subtask C: 失敗通知セクション
- Subtask D: ローカル検証手順
- Subtask E: Commit

並列実行による効果:
- 週の作業時間: 40時間 × 5スキル ÷ 並列度 = 約40時間(全て逐次なら200時間)
- リスク分散: 各スキルが独立して失敗/復旧可能
- 依存テスト: 月末の統合テストで全スキルの相互作用を検証
```

---

## 検証失敗時: 起こりうる障害パターンと対応

このセクションは、エージェント/ワークフローが本番で壊れる時のデバッグ手順と通知方法です。

### パターン 1: エージェント Timeout（応答なし）
**症状**: エージェントが指定秒数(例: 30秒)内に応答を返さない。

**原因の確認**:
```bash
# ログから実行時間を確認
grep -i "timeout\|duration" job-state.json

# エージェント側のプロセス状態を確認
ps aux | grep claude
```

**対応方法**:
1. **短期対応**: タイムアウト上限を30秒 → 60秒に延長し、リトライ
2. **中期対応**: エージェントの入力サイズを削減(大量データを少量に分割)
3. **長期対応**: エージェントの責務を簡素化し、判断量を減らす

**通知**:
```
Issue テンプレート: "Agent Resilience: Timeout"
- エージェント ID: agent_xyz
- タイムアウト時間: 180秒
- リトライ回数: 3回
- 対応: スキップ/人間通知/リトライ上限延長
```

### パターン 2: Network / API 失敗（回復不可能）
**症状**: 外部 API 呼び出しが HTTP 4xx エラーで永続的に失敗。

**原因の確認**:
```json
{
  "error_type": "HTTPError",
  "status": 403,
  "message": "Forbidden",
  "timestamp": "2026-10-05T12:34:56Z"
}
```

**対応方法**:
- HTTP 4xx (入力エラー/権限不足): **リトライしない**。代わりに人間確認へ escalate
- HTTP 5xx (サーバ側): リトライ対象。exponential backoff で最大3回
- 接続エラー: リトライ対象。ネットワーク復旧を待つ

**通知**:
```
Slack: "API error in agent_xyz: 403 Forbidden"
手動対応: API キーの確認 / エンドポイントの確認 / 権限の確認
```

### パターン 3: Context 破壊（状態不整合）
**症状**: 複数エージェント並列実行時に、状態ファイルが競合して上書きされる。

**原因の確認**:
```bash
# git log で状態ファイルの変更履歴を確認
git log -p data/job-states/job-xyz.json

# ファイルのタイムスタンプから、誰が最後に書いたか確認
ls -la data/job-states/
```

**対応方法**:
1. **.lock ファイルの導入**: 出力ファイル生成時に lock を作成し、他エージェントを待たせる
2. **トランザクション化**: 状態ファイル更新を、git add → git commit で自動化
3. **版管理**: 状態ファイルに `version` フィールドを追加し、古いバージョンの上書きを検出

**コード例**:
```python
def write_state_atomically(state: dict, lock_file: str):
    """
    Atomic write with lock to prevent concurrent modification.
    """
    import fcntl
    
    with open(lock_file, 'w') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)  # Exclusive lock
        try:
            # Write state
            with open('data/job-states/job.json', 'w') as f:
                json.dump(state, f)
            # Commit to git
            os.system('git add data/job-states/job.json')
            os.system('git commit -m "state: update"')
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)  # Release lock
```

### パターン 4: Cascading 失敗（連鎖）
**症状**: 上流エージェント A が失敗 → 下流エージェント B, C, D が全て失敗。

**原因の確認**:
```
Step 1 (Agent A): FAILED (timeout)
Step 2 (Agent B): FAILED (input not found)
Step 3 (Agent C): FAILED (dependency incomplete)
Step 4 (Agent D): FAILED (dependency incomplete)
```

**対応方法**:
1. **Failure Isolation**: 各エージェントの失敗を独立させる
   - Agent B, C, D が Agent A の出力なしで動作できるデフォルト値を用意
   - または、Agent B のみ失敗で、C, D は並列実行
2. **Fallback ロジック**: Agent A 失敗時は「デフォルト処理を使用」「この工程スキップ」を選択
3. **段階的デグラデーション**: 品質を落としても、ワークフロー全体は完了させる

**Issue テンプレート**:
```
Agent Resilience: Cascading Failure
- Root cause: Agent A timeout
- Affected agents: B, C, D
- Recommendation: Implement fallback for Agent A output
- Solution: Use cached_last_output or default_value
```

### パターン 5: 静かな脱落（Silent Failure）
**症状**: エラーも発生していないのに、外部依存(補助AI・オプションAPI)が黙って実行されない。

**例**: Gemini 並行検証が失敗したが、ログに残らず Claude の結果だけが出力される。

**対応方法**:
1. **参加率を記録**: 毎回実行結果に「Gemini 実行: Yes/No」を記録
2. **参加率の監視**: 過去30日の Gemini 参加率 < 80% なら警告
3. **参加0の検知**: 連続3日 Gemini 参加 0 → 自動 Issue 作成

**実装例**:
```python
def run_dual_verification(data):
    """Claude + Gemini dual check for verify-sources."""
    result_claude = verify_with_claude(data)
    
    # Try Gemini, but don't fail workflow if it's unavailable
    result_gemini = None
    gemini_participated = False
    try:
        result_gemini = verify_with_gemini(data)
        gemini_participated = True
    except Exception as e:
        log_event({
            "type": "optional_api_failure",
            "provider": "gemini",
            "error": str(e),
            "fallback": "claude_only"
        })
    
    # Record participation for monitoring
    participation_log.append({
        "timestamp": now(),
        "claude": True,
        "gemini": gemini_participated
    })
    
    # Check participation rate
    recent_rate = calculate_participation_rate(days=30)
    if recent_rate < 0.8:
        alert_low_participation(rate=recent_rate)
    
    return {
        "primary": result_claude,
        "secondary": result_gemini,
        "agreement": compare_results(result_claude, result_gemini)
    }
```

---

## 本番前テスト: チェックリスト

本番環境へのデプロイ前に、必ず以下のテストを実施してください。
最低7項目以上の確認が必要です。

### 1. Timeout 検証
- [ ] エージェント応答時間を測定し、設定タイムアウト時間より短いか確認
- [ ] 大データ入力(過去1ヶ月分)を与えた時の応答時間を測定
- [ ] タイムアウト時、適切に exception がキャッチされるか確認
- [ ] タイムアウト時、状態ファイルが最後の成功地点を記録しているか確認

### 2. Network 失敗注入
- [ ] Mock HTTP 500 エラーを返すテストサーバーを起動
- [ ] エージェントが 5xx エラーを受け取り、リトライするか確認
- [ ] リトライ回数が max_retries を超えないか確認
- [ ] リトライ間の待機時間が exponential backoff に従うか確認
  ```bash
  # 実際のログから待機時間を抽出して検証
  grep "retry_attempt" job-state.json | jq '.wait_seconds'
  # 期待値: ~2, ~4, ~8, ~16 (秒)
  ```
- [ ] HTTP 4xx エラーは**リトライせず**、人間通知へ escalate されるか確認
- [ ] リトライ失敗時、error_type が記録されているか確認

### 3. 状態保存と復旧
- [ ] ステップ 1 完了後、状態ファイルに `step_1` が記録されているか確認
- [ ] ワークフロー途中で停止し、再開時に step_1 をスキップして step_2 から始まるか確認
- [ ] 復旧後、最終出力が同じか確認(べき等性テスト)
  ```bash
  # 2回実行の出力をハッシュ比較
  workflow run 1: output1.json
  workflow run 2 (resumed): output2.json
  md5sum output1.json output2.json  # 同じハッシュ = 成功
  ```
- [ ] `idempotency_key` が同じワークフロー実行なら一致しているか確認
- [ ] 状態ファイルが `git commit` で自動追跡されているか確認

### 4. 並列実行と依存管理
- [ ] 依存なしのエージェント(Layer 0)が実際に並列実行されるか確認
  ```bash
  # 各エージェントのスタート時刻を比較
  # 時刻の差が < 1秒なら並列実行
  ```
- [ ] 下流エージェント(Layer 1)が上流出力ファイルを待つか確認
- [ ] 上流失敗時、下流が適切にスキップ/失敗するか確認
- [ ] 上流成功・下流成功で、全体が「completed」になるか確認
- [ ] Circular dependency(循環依存)を検出し、エラーを出すか確認

### 5. ファイルロックと競合防止
- [ ] 出力ファイル生成前に `.lock` ファイルが作成されるか確認
- [ ] `.lock` ファイル存在中、他エージェントがポーリング待ちするか確認
- [ ] 出力完成後に `.lock` が削除されるか確認
- [ ] 同時に複数エージェントが同じファイルに書き込もうとした時、最後の 1 つだけ成功するか確認

### 6. エラーログと監査証跡
- [ ] 全ての失敗パターン(timeout, HTTP error, logic error)がログに記録されているか
- [ ] ログに以下が含まれているか確認:
  - [ ] 開始時刻・終了時刻(実行時間を計算可能)
  - [ ] エージェント ID
  - [ ] 入力(サニタイズ済み)
  - [ ] 出力 / エラーメッセージ
  - [ ] リトライ回数・待機時間
  - [ ] API 呼び出し費用(コスト集計可能)
- [ ] ログが JSON フォーマットで、パース可能か確認
- [ ] ログが git で永続保存されているか確認

### 7. コスト監視と超過検知
- [ ] API 呼び出し単価が正しく設定されているか確認(例: Claude API $0.003/1K tokens)
- [ ] 各エージェント実行の費用が計算・記録されているか確認
- [ ] 累計費用が予算上限を超えると通知されるか確認
- [ ] 通知の受け手(Slack/LINE/メール)が正しく設定されているか確認

### 8. 復旧テスト（失敗から正常復旧）
- [ ] Agent A が失敗 → リトライで復旧するシナリオ
  ```bash
  # テスト実行 1: 正常
  workflow run normal: SUCCESS
  
  # テスト実行 2: Agent A timeout
  # (sleep コマンドで遅延シミュレート)
  workflow run with-timeout: Step 1 FAILED (timeout)
  
  # 自動リトライ
  Step 1 retry 1: timeout
  Step 1 retry 2: timeout
  Step 1 retry 3: SUCCESS
  
  # 下流から続行
  Step 2: SUCCESS
  Final: SUCCESS
  ```
- [ ] 手動リトライボタンで、失敗ステップから再開できるか確認
- [ ] リトライ後、状態ファイルの `retry_count` が正しく更新されているか確認

### チェックリスト実行方法
```bash
# テスト実行スクリプト
./tests/test_resilience.sh

# 各テスト結果を確認
cat test_results.json | jq '.tests[] | {name, status, duration_ms}'

# 本番デプロイは、全テスト PASS まで実施しない
if [ $TESTS_PASSED -eq 8 ]; then
  echo "All tests passed. Safe to deploy."
  git push origin main
else
  echo "Some tests failed. Fix before deploying."
  exit 1
fi
```

---

## 新規/既存の自動化をレビューするときのチェックリスト

1. Trigger/Workflow/Agent/Guardrailの4層に分解できているか(全部AI丸投げになっていないか)
2. 各工程の完了条件が、AIの自己申告でなくシステムで判定されているか
3. 状態(job_id/status/current_step等)が会話やコンテキストでなく外部(ファイル/DB)にあるか
4. 副作用のある処理(送信・公開・課金・削除)にべき等性キーがあるか
5. リトライの上限・種類・エスカレーション条件が決まっているか(無限リトライ/無限沈黙がないか)
6. 権限が必要最小限か(原則付与しない権限を渡していないか)
7. 危険操作を止めるHook・最低限のログ(開始/入力/出力/エラー/コスト/承認者)があるか
8. 「文章で守っている」ルールが、権限・コード・環境の強制に置き換えられないか
