# 保険引き受け目安検索 — 継続的精度改善ガイド

## 概要
保険データの精度は、①稀少疾患の検出、②信頼度レベルの推定、③現場フィードバックの取り込みの 3 つのサイクルで継続的に向上します。本ドキュメントは、月次・週次で実行すべき検証プロセスを定義します。

---

## 📅 月次実行: 稀少疾患データの自動検証

### 目的
- `confidence_level` が「低」のデータを段階的に「中」→「高」に昇格させる
- `data_completeness` スコアを公開情報から推定・更新する
- 稀少疾患リストを拡張し、`requires_confirmation` フラグを正確に付与

### 実行手順

#### Step 1: 対象疾患の抽出（自動化可）
```bash
# JSON から confidence_level="低" のエントリを抽出
python scripts/extract-low-confidence.py \
  --input docs/insurance/underwriting_full.json \
  --output /tmp/low-confidence-diseases.json
```

**出力例:**
```json
{
  "diseases": [
    {
      "name": "プリオン病（ヤコブ病）",
      "insurer": "zurich",
      "current_confidence": "低",
      "current_completeness": 0.3
    }
  ]
}
```

#### Step 2: 公式情報の確認（手作業）
各疾患ごとに、以下を調査：
1. **保険会社公式サイト** — 引き受け基準 PDF / 告知書
2. **業界レポート** — 経営誌・生保業界ニュース
3. **医学情報** — 稀少疾患の通院・入院期間の一般的パターン

**記録フォーマット:**
```yaml
disease_name: プリオン病（ヤコブ病）
insurer: チューリッヒ生命

# 公式情報の有無
has_official_guideline: false
official_url: ""
last_checked: 2026-08-19

# 推定の根拠
evidence:
  - "医学文献では進行性が高く、予後が限定的"
  - "保険会社Xは『加入不可』と公開"
  - "保険会社Yは『要問い合わせ』と曖昧"

# 推定値
confidence_level_proposed: "中"  # 低→中に昇格候補
data_completeness_proposed: 0.45  # 0.3→0.45
requires_confirmation_proposed: true  # 公式確認は必須
condition_text_proposed: "公開基準が不明瞭。保険会社に直接確認してください"

# 実施者署名
reviewed_by: "検証部（三名体制）"
review_date: 2026-08-19
```

#### Step 3: 三名体制による議論（CLAUDE.md 準拠）

| 役割 | 質問 | 例 |
|---|---|---|
| **スイシン（推進）** | 「この推定は妥当か」 | 「医学文献 + 保険会社Xの公開情報から『中』に昇格は合理的」 |
| **ウタガイ（懐疑）** | 「根拠に漏れはないか」 | 「保険会社Yが『曖昧』ならば『中』では甘い。『低』のままが保守的」 |
| **ベッカイ（別解）** | 「前提を疑う」 | 「『requires_confirmation=true』なら、confidence_level は『高』でも良い（＝きちんと確認を促すから）」 |

**結論例:**
```
決定: confidence_level = 中（昇格）/ data_completeness = 0.45
根拠: 医学文献 + 複数保険会社の事例から「稀少だが判定基準が存在」と判断
アクション: requires_confirmation=true を維持し、ユーザーに「公式確認推奨」を明示
```

#### Step 4: JSON に反映
```bash
python scripts/update-confidence-levels.py \
  --input docs/insurance/underwriting_full.json \
  --updates /tmp/reviewed-updates.yaml \
  --output docs/insurance/underwriting_full.json
```

**コミットメッセージ例:**
```
chore(insurance): 月次データ品質向上 — confidence_level を3件昇格

プリオン病・ハンチントン病・二次進行性多発性硬化症の
confidence_level を「低」→「中」に昇格。

- 医学文献の調査で、稀少ながら保険基準が存在することを確認
- data_completeness: 0.3～0.4 → 0.45～0.55 に更新
- requires_confirmation=true で公式確認を促す

三名体制レビュー: スイシン(推進)・ウタガイ(懐疑)・ベッカイ(別解)
議事: docs/insurance/reviews/2026-08-19-low-confidence-review.md
```

---

## 🔄 週次実行: 現場フィードバックの取り込み

### 目的
- 利用者（診断部・LINE部・現場営業）からの「この判定は正確ですか？」フィードバックを回収
- 間違った判定を検出し、JSON を即座に修正
- `data_completeness` スコアの精密化

### フィードバック回収フロー

#### 1. LINE / Slack で「判定フィードバック」を募集
```
【保険引き受け目安検索】精度向上への協力依頼

ツールを使ってみて、判定が間違っていたケースがあれば教えてください。

【報告形式】
- 病名: （例：神経線維腫）
- 保険会社: （なないろ / FWD / チューリッヒ）
- ツールの判定: △ 条件付き
- 実際の判定: ✗ 加入不可（理由：〇〇）
- 情報源: 公式基準 / 営業担当の説明 / 他

📧 報告先: feedback@hojo-hq.example.com
```

#### 2. フィードバックの精査（三名体制）

**テンプレート: フィードバック評価表**

| No | 病名 | 会社 | ツール判定 | 報告判定 | 情報源の信頼度 | 対応 |
|---|---|---|---|---|---|---|
| 1 | 神経線維腫 | なないろ | △ 条件付き | ✗ 不可 | ⭐⭐⭐⭐⭐（公式基準） | JSON修正 + confidence昇格 |
| 2 | プリオン病 | FWD | ❌ 要確認 | △ 条件付き | ⭐⭐（営業から聞いた） | 要確認のまま（根拠不十分） |

#### 3. JSON の即座修正
```bash
git checkout -b fix/insurance-feedback-2026-08-19
# JSON を修正
git add docs/insurance/underwriting_full.json
git commit -m "fix(insurance): 神経線維腫（なないろ）の判定を『条件付き』→『不可』に修正

現場フィードバック: 公式基準で『医療・死亡以外は不可』と確認
confidence_level: '中' → '高'（公式基準で確認できたため）
data_completeness: 0.65 → 0.88

情報源: なないろ生命 公式引き受け基準（2026-08版）
報告者: 下地さん（現場営業）"
git push origin fix/insurance-feedback-2026-08-19
```

---

## 📊 定期実行: データ品質スコアの可視化

### 月次スコアカード

ツールの精度を数値で追跡：

```yaml
date: 2026-08-19
statistics:
  total_diseases: 1200
  confidence_high: 450  # 37.5%
  confidence_medium: 600  # 50%
  confidence_low: 150  # 12.5%
  
  avg_data_completeness: 0.72  # 全体平均
  
  with_official_url: 120  # 公式URL確定済み
  requires_confirmation: 280  # 公式確認推奨フラグ

trend:
  confidence_high_trend: "+5%"  # 先月比
  avg_completeness_trend: "+0.03"
  
quality_score: 72/100  # 総合スコア
target_score: 85/100
gap: -13点
```

**可視化:**
```
信頼度レベルの構成比（目標: 高50% / 中40% / 低10%）

現状:
  高: ████░░░░░░░ 37.5%（目標比 -12.5%）
  中: ██████████ 50%（ほぼ目標）
  低: ██░░░░░░░░ 12.5%（+2.5%）

→ アクション: 低信頼度データを月5%ずつ「中」に昇格させる
```

---

## 🤖 自動化: 定期実行プロンプト

### Claude Code で月次実行するプロンプト

**Routine 設定例（`update_trigger`）:**

```bash
claude-code-remote trigger create \
  --name "insurance-monthly-quality-check" \
  --cron "0 9 1 * *" \
  --prompt "
保険引き受け目安検索の月次データ品質チェックを実行してください。

手順:
1. docs/insurance/underwriting_full.json から confidence_level='低' のデータを抽出
2. 過去1ヶ月間に報告されたフィードバック（feedback_log.csv）を確認
3. 各疾患について、公開情報（医学文献・保険会社公式情報）を調査
4. 三名体制で検証: スイシン(推進) / ウタガイ(懐疑) / ベッカイ(別解)
5. JSON を更新し、修正内容を月次レポートにまとめる

出力: 
- docs/insurance/reviews/2026-09-01-monthly-review.md （議事録）
- git commit で JSON を更新
- Slack に結果を投稿（検証部チャネル）
" \
  --persistent-session-id <session-id>
```

---

## 📋 チェックリスト: 精度向上の定期タスク

### 月次（毎月1日 09:00 JST）
- [ ] 低信頼度データ（confidence_low）の自動抽出
- [ ] 公開情報の再調査（医学文献・保険会社サイト）
- [ ] 三名体制による議論
- [ ] JSON 更新 & commit
- [ ] 月次スコアカード作成
- [ ] Slack & LINE で成果を報告

### 週次（毎週月曜 10:00 JST）
- [ ] 現場フィードバック（LINE / Slack）の回収
- [ ] 緊急対応が必要な判定誤りの検出
- [ ] 修正 PR の作成・マージ
- [ ] 検証部チャネルで議論

### 随時
- [ ] ユーザーから「この判定が違う」という指摘を受けたら、即座に JSON に反映
- [ ] 保険会社の基準改定情報を検知したら、公式URL を更新

---

## 🔗 関連ドキュメント

- `CLAUDE.md` — 三名体制の定義・ルール
- `underwriting-schema.md` — スキーマ v2 の詳細
- `保険引き受け目安検索_導線設計.md` — ビジネス・技術要件

---

## 💡 長期的な精度向上戦略

### Phase 3（6ヶ月目）
- 保険会社 API 連携（自動更新）
- ユーザーフィードバック機構の UI 実装
- Lighthouse 監査（Accessibility 95+）

### Phase 4（12ヶ月目）
- 業種別・規模別の検索フィルタ追加
- AI による稀少疾患の自動検出
- 月次データ品質スコア 85/100 達成
