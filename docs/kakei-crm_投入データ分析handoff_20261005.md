# 🌟保全CRMチーム向け — 投入データ分析フレームワーク引き継ぎメモ

**作成日**: 2026-10-05  
**対象チーム**: kakei-hozen 保全CRM / kakei-crm 軸チーム  
**目的**: 1万件投入済みデータから複数軸での分析を実現し、ダッシュボード化・施策効果測定へ向かう

---

## ✅ 完成したもの（軸 kakei-crm に配置済み）

### 1. 分析戦略ドキュメント
**ファイル**: `kakei-crm/docs/投入データ多角分析戦略_20261005.md` (32KB)

- 10の分析軸を定義（段階別ファネル・出所別ROI・早期解約率・書類・地域・DNC等）
- 各々の実装方法を SQL/Python コードスニペット付きで提示
- Phase 1〜3 のロードマップ
- テストデータ・出力形式の仕様

**次のステップ**: このドキュメントをレビュー → Phase 1 ダッシュボード実装の要件を詰める

---

### 2. メイン集計スクリプト
**ファイル**: `kakei-crm/migration/scripts/analyze_intake_data.py` (12KB)

```bash
python -m migration.scripts.analyze_intake_data \
  --store private/store.json \
  --out private/analysis_20261005.json
```

**出力**: JSON で以下をすべて計算
- 段階別ファネル（8段階）
- 解約/継続/保全 の3点
- 早期解約率（180日以内）
- 出所別到達率（❶〜❼）
- DNC分布・コンプライアンス
- 書類提出率（段階別）
- 地域別成約率・解約率
- 段階滞留日数の統計
- 親子構造（重複検出）

**現状**: 9個の分析関数が実装済み（即座に使用可）

---

### 3. 実装ガイド
**ファイル**: `kakei-crm/migration/scripts/README_ANALYSIS.md` (8KB)

- 使用法・出力形式
- ダッシュボード化への展開方法
- Phase 2〜3 の拡張予定（訪問ログ分析・コホート・セグメント分類）
- テスト・検証手順

---

## 🎯 保全CRMチームの次アクション

### Phase 1（即座・本週中） — 基本ダッシュボード化
**担当**: 保全CRM チーム  
**作業内容**:

1. **分析スクリプトの動作確認**
   ```bash
   # 実データ(private/store.json)で実行
   python -m migration.scripts.analyze_intake_data \
     --store private/store.json \
     --out private/analysis_20261005.json
   
   # 結果を確認
   cat private/analysis_20261005.json | jq '.analysis.stage_funnel'
   ```

2. **BI Tool への連携**
   - JSON → CSV 変換スクリプト作成（`convert_analysis_to_csv.py`）
   - Google Data Studio / Tableau へ投入
   - グラフ・ダッシュボードを自動生成

3. **週次レポート自動生成への組み込み**
   - 既存 GAS（Google Apps Script）スクリプトに `analyze_intake_data.py` の結果を読み込み
   - `docs/reports/` に JSON 出力を定期保存（`private/` ではなく `docs/` なら共有可）

---

### Phase 2（1〜2週間） — 現場フィードバック分析
**担当**: 保全CRM チーム  
**実装予定**:

```python
# 5-1: 訪問/通話ログの結果別段階進行率
def visit_result_effectiveness(store):
  """訪問/通話の結果(申込・成約など)ごとに、
     その接触後に段階が進んだ確率を計算"""
  # → migrate.scripts/analyze_visit_logs.py

# 10-1: リスク度別セグメント分類
def segment_by_risk_and_value(store):
  """解約リスク × 段階 × 出所 の3軸で、
     施策優先度を自動判定（最高優先度/高/中/低）"""
  # → migrate.scripts/classify_segments.py
```

---

### Phase 3（2〜3週間） — 効果測定・施策最適化
**担当**: 保全CRM チーム + 統計・企画チーム協調  
**実装予定**:

```python
# 9-1: コホート分析
def cohort_retention_analysis(store):
  """投入月別に、段階到達率と早期解約率を追跡"""
  # → migrate.scripts/analyze_cohort.py

# A/B テスト設計・ROI計測フレーム
def ab_test_metrics(store, control_ids, test_ids):
  """対照群 vs 施策群の成約率・解約率を比較"""
  # → migrate.scripts/ab_test_analysis.py
```

---

## 🔗 保全CRM との連携ポイント

### 1. 解約データ（700件）— kakei-hozen から kakei-crm へ
- **現状**: `churn_ingest.py` で投入済み（本日確認）
- **効果**: 早期解約率の計測が可能（解約日マッチング）
- **用途**: 段階別のリスク判定・施策対象抽出

### 2. 保険会社継続状況 — kakei-hozen から kakei-crm へ
- **スクリプト**: `insurer_status_update.py`（実装済み）
- **用途**: insurance_status を continuing/cancelled/lapsed/surrendered で判定
- **手作業**: 保険会社から定期的にデータを受け取り → CSV アップロード → スクリプト実行

### 3. 保全パネル（hozen_board_rows）— kakei-hozen から kakei-crm へ
- **役割**: 検知候補を軸へ反映（自動投入・段階進行の同期）
- **現状**: 仕様は実装済みだが、データフローの運用開始 = Phase 2 以降

---

## 📊 小柳さん（全体統括）が見るべき指標

### 日次チェック（毎朝）
```
□ 段階別ファネル: 名簿 → 申込 → 成立 の進捗率（前日比）
□ 解約/継続/保全 の件数比（新規解約は何件か？）
□ 要フォロー件数（書類未提出・NG・留守・解約リスク）
```

### 週次レポート（毎週金）
```
□ 出所別ROI（❶〜❼ のどれが効率的か？）
□ 段階別滞留期間（アポ設定で何日止まってるか？）
□ 早期解約率（6ヶ月以内 ％）の推移
□ DNC コンプライアンス違反 0 件確認
```

### 月次分析（月末）
```
□ コホート分析（投入月別・どの月が成約率高いか？）
□ 地域別成約率（那覇市 vs 浦添市 vs…）
□ 施策効果測定（新規出所の効果検証）
□ 次月施策の提言（増減配置・新規流入元の検討）
```

---

## 🚀 スケジュール感

| 時期 | 担当 | 内容 | 成果物 |
|-----|------|------|--------|
| 本週中（10/5-10/11） | 保全CRM | Phase 1: 基本ダッシュボード化 | BI Tool のダッシュボード / 週次レポート自動生成 |
| 10/12-10/19 | 保全CRM | Phase 2: 現場ログ・セグメント分析 | visit_result_effectiveness.py / classify_segments.py |
| 10/19-10/26 | 保全+企画 | Phase 3: コホート・A/B テスト | cohort_retention_analysis.py / ab_test_metrics.py |
| 10/26 以降 | 小柳さん | 全体統括・意思決定 | 月次分析レポート → 施策の優先度・予算配置を決裁 |

---

## 📋 確認事項（小柳さん決裁）

- [ ] Phase 1 ダッシュボードの設計（どのグラフを出すか）
- [ ] 早期解約率の 180日 閾値は妥当か（業態によって変更要）
- [ ] リスク度別セグメント（Phase 3）の定義（最高優先度 = ？）
- [ ] コホート分析（Phase 3）の投入月単位は月次でいいか

---

## 💾 ファイル位置の整理

### kakei-crm リポジトリ（軸）
- `docs/投入データ多角分析戦略_20261005.md` — 全体戦略・実装方針
- `migration/scripts/analyze_intake_data.py` — メイン集計スクリプト（Phase 1）
- `migration/scripts/README_ANALYSIS.md` — 実装ガイド・拡張方針
- `private/analysis_*.json` — 分析結果（日次出力・gitignore済み）

### kakei-hozen リポジトリ（保全CRM）
- `scripts/churn/` — 既存保全分析（700件解約データ）
- `docs/churn/` — 保全関連ドキュメント

### hojo-hq リポジトリ（本体・統括）
- `docs/全体マップ.md` に本分析の位置づけを追記
- 週次レポートのテンプレートに分析結果セクションを追加

---

## 🎯 成功指標

- ✅ Phase 1 ダッシュボードが毎週自動更新される
- ✅ 段階別ファネルから「ボトルネック」が明確になる
- ✅ 出所別ROI分析で「最高効率の流入元」が特定される
- ✅ 早期解約率が週次で追跡できる
- ✅ 施策効果（A/B テスト）の測定が可能になる

---

**作成者**: Claude Haiku 4.5  
**配布先**: 保全CRM チーム・小柳さん  
**次更新**: Phase 1 完了時（2026-10-11 予定）
