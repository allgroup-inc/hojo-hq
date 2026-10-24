# KachiTalk完全版分析システム セットアップ＆運用ガイド

**作成日**: 2026-10-24  
**目的**: KachiTalk全ログ（400+件）× 営業成績の自動相関分析システム構築  
**対象**: 営業8名の6段階プロセス完全性と売上相関の定量化

---

## 概要

このシステムは、営業成績（訪問数・成約件数・ANP）とKachiTalkの実際の通話ログを相関させ、以下を自動で分析します:

- ✓ 6段階営業プロセス（①アプローチ～⑥紹介入手）の実施完全性
- ✓ 通話ごとの成約/失注/保留判定
- ✓ プロセス完全性スコアと実績との相関
- ✓ 営業スタイルの自動分類（高成約率・短時間効率など）
- ✓ チーム内のベンチマーキング

**現状**: サンプルログ16件で動作確認済み ✓  
**次ステップ**: KachiTalk admin dashboardから400+件の実ログを取得

---

## ステップ1: KachiTalk Admin Dashboardからログをエクスポート

### 1-1. KachiTalk管理画面にアクセス

URL: `https://kachitalk-line-enlife.azurewebsites.net/admin`

**ログイン情報**: 
- メール: [管理者メール]
- パスワード: [管理者パスワード]

### 1-2. エクスポート設定

1. 左メニュー: **「ログ」** または **「通話記録」**
2. **フィルタ設定**:
   - **期間**: 2026年7月1日 ～ 2026年10月31日（最低4ヶ月）
   - **営業マン**: 全8名チェック
     - 前原　芳乃
     - 奈須　章
     - 下地　健太
     - 幸良　妃奈代
     - 徳元　孝樹
     - 喜納　礼奈
     - 名嘉山　望
     - 狩俣　亜希乃
   - **フォーマット**: CSV（自社用・UTF-8推奨）

3. **「エクスポート」** ボタンをクリック
4. ファイル名: `kachitalk_logs_full_export_YYYYMMDD.csv`

### 1-3. CSVファイルの確認

ダウンロードされたファイルに以下の列が含まれていることを確認:

```
必須列:
- 営業マン / staff_name
- 日時 / date  
- 顧客名 / customer_name
- 通話時間（分） / duration_minutes
- 通話内容・要約 / transcript_summary
- メモ / notes
```

**データ品質チェック:**
- [ ] 合計行数: 400件以上
- [ ] 営業マン名: 正確にスペースを含む（例：「前原　芳乃」）
- [ ] 通話時間: 数値で記入（5, 12, 18 など）
- [ ] 通話内容: 最低50文字以上の要約

---

## ステップ2: CSVファイルをシステムに入力

### 2-1. ファイルを配置

```bash
# ダウンロードしたCSVをこのディレクトリにコピー
cp ~/Downloads/kachitalk_logs_*.csv /tmp/kachitalk_full_export.csv
```

### 2-2. Pythonスクリプトで分析実行

```bash
cd /home/user/hojo-hq

# CSVファイルからの完全分析（推奨）
python3 enlife/scripts/kachitalk_full_correlation_analysis.py \
  --source csv \
  --file /tmp/kachitalk_full_export.csv \
  --output /tmp/kachitalk_analysis_YYYYMMDD.json
```

### 2-3. 分析結果を確認

```bash
# 結果ファイルが生成されたことを確認
ls -lh /tmp/kachitalk_analysis_*.json

# 結果をJSON形式で確認
cat /tmp/kachitalk_analysis_YYYYMMDD.json | head -100
```

---

## ステップ3: 分析結果を解釈する

### 3-1. 個別営業マンの分析結果

スクリプト実行時の出力例:

```
📊 下地　健太
----
  総通話件数: 87件
  平均通話時間: 16.3分
  平均プロセス完全性: 68.5点
  
  成約: 19件（21.8%）
  失注: 8件（9.2%）
  保留: 60件（69.0%）

【6段階プロセス実施率】
  ①アプローチ: 98%
  ②ヒアリング: 89%
  ③提案: 76%
  ④クロージング: 82%
  ⑤申込契約: 43%
  ⑥紹介入手: 31%

【営業スタイル判定】
  ✨ 高成約率営業（20%以上）
  💼 標準フロー型（15-18分）
  📋 教科書的プロセス実行型
```

**読み方:**
- **成約率**: 実際の営業成績との相関を確認する指標
- **プロセス完全性**: 6段階をどれだけ実行しているか（100%ならすべて実施）
- **ステップ別実施率**: どのステップが弱いかを識別（改善優先度の判定）

### 3-2. チーム横断分析

スクリプトは自動で4つのパターンに分類:

| パターン | 説明 | 対応 |
|---------|------|------|
| ◎ 高成約率 × 高品質 | 理想的な営業スタイル | **共有**: このメンバーの話し方をチーム内で共有・训练 |
| △ 高成約率 × 低品質 | 属人性が高い | **強化**: プロセス実行の定着で持続性向上 |
| ◆ 低成約率 × 高品質 | 潜在能力あり | **改善**: クロージング後の「紹介入手」を強化 |
| ✗ 低成約率 × 低品質 | 要改善 | **訓練**: ①②③の基本プロセスの定着支援 |

---

## ステップ4: Google Sheetsへの統合（オプション）

### 4-1. glow-maスプレッドシートへの組み込み

エンタープライズ向け（GLOW営業管理システムと統合）:

```bash
# glow-ma/src/KachiTalkIntegration.gs が既に配置済み
# Apps Scriptエディタで以下を実行:
# 1. ensureKachiTalkTabs()  - タブ初期化
# 2. importKachiTalkLogsFromAdmin()  - ログインポート
# 3. analyzeKachiTalkCorrelation()  - 分析実行
```

### 4-2. セットアップ手順

```
Google Sheets: GLOW企業リレーション台帳
├─ KachiTalkログ_raw  (CSV貼り付け用)
├─ KachiTalk分析結果  (自動分析結果)
└─ 営業成績との相関  (相関パターン分類)
```

---

## ステップ5: 自動化・定期実行の設定

### 5-1. 毎週自動分析

```bash
# crontabに登録（毎週月曜 9:00 JST）
0 0 * * 1 /home/user/hojo-hq/scripts/run_kachitalk_analysis.sh
```

### 5-2. 自動実行スクリプト作成

ファイル: `/home/user/hojo-hq/scripts/run_kachitalk_analysis.sh`

```bash
#!/bin/bash
# KachiTalk自動分析スクリプト

# 日付を YYYYMMDD 形式で取得
DATE=$(date +%Y%m%d)

# KachiTalk admin dashboardからの最新エクスポート
# (注: この部分は手動またはAPIを使った自動ダウンロードに置き換え)
# wget https://kachitalk-admin.azurewebsites.net/export?token=*** -O /tmp/kachitalk_$DATE.csv

# Python分析を実行
python3 /home/user/hojo-hq/enlife/scripts/kachitalk_full_correlation_analysis.py \
  --source csv \
  --file /tmp/kachitalk_$DATE.csv \
  --output /tmp/kachitalk_analysis_$DATE.json

# 結果をGoogle Sheetsにアップロード（オプション）
# python3 /home/user/hojo-hq/scripts/upload_to_sheets.py \
#   --json /tmp/kachitalk_analysis_$DATE.json

# 結果をSlackに通知
# curl -X POST ... << 'EOF'
# {
#   "text": "✓ KachiTalk分析完了: $DATE"
# }
# EOF

echo "✓ KachiTalk分析完了: $DATE"
```

### 5-3. Slack通知の設定

Apps Scriptで定期実行時に自動通知:

```javascript
// glow-ma/src/DailyReportAutomation.gs に追加
function notifyKachiTalkAnalysisResults() {
  var results = readKachiTalkAnalysisOutput();
  var message = formatAnalysisForSlack(results);
  
  var webhookUrl = PropertiesService.getScriptProperties()
    .getProperty('SLACK_WEBHOOK_URL');
  
  UrlFetchApp.fetch(webhookUrl, {
    method: 'post',
    payload: JSON.stringify(message),
    muteHttpExceptions: true
  });
}
```

---

## ステップ6: 継続的改善

### 6-1. 月次レビュー

```
毎月末に実施:
1. プロセス完全性の月間推移を確認
2. 成約率×品質で各営業マンのクラスター位置を確認
3. 前月と比較して改善があった項目をハイライト
4. 次月の改善施策を決定
```

### 6-2. 改善施策の例

| 課題 | 根本原因 | 改善施策 |
|-----|--------|--------|
| ②ヒアリングの実施率が低い | 顧客の課題の掘り下げ不足 | ロールプレイ・聞き方のスキルトレーニング |
| ④クロージングから⑤申込への失落 | 申込手続きの説明が不十分 | 標準的な申込フロー（スクリプト）の共有 |
| ⑥紹介入手の実施率が0% | 紹介を求めるタイミングが無い | クロージング直後に「知人紹介」を必ず聞く仕組み |
| 成約率が低い（<10%） | 基本プロセスのスキップ | 6段階を順守する運用ルール化 |

---

## ステップ7: トラブルシューティング

### Q: 「CSV読込エラー」が出る

**原因**: 文字エンコーディングの問題（Shift-JISなど）

**対応**:
```bash
# UTF-8に変換してから実行
iconv -f SHIFT_JIS -t UTF-8 kachitalk_logs.csv > kachitalk_logs_utf8.csv

python3 kachitalk_full_correlation_analysis.py \
  --source csv \
  --file kachitalk_logs_utf8.csv
```

### Q: 「成約が多い営業マンが低評価になっている」

**原因**: プロセス完全性スコアが設計通り機能していない可能性

**確認ポイント**:
- [ ] 成約の実績データ（訪問数・成約件数）と照合
- [ ] KachiTalk管理画面の成約フラグが正確に記録されているか
- [ ] 通話内容要約に成約を示すキーワードが含まれているか

### Q: 「ある営業マンのログが極端に少ない」

**原因**:
1. KachiTalkへのログ記録漏れ
2. 期間フィルタで対象外になっている
3. 営業マン名の表記が異なる（全角/半角、スペースの違いなど）

**対応**:
```bash
# CSVファイルで営業マン名をグレップ
grep "営業マン名" kachitalk_logs.csv | sort | uniq -c

# サンプルを確認
head -20 kachitalk_logs.csv
```

---

## ファイル構成

```
/home/user/hojo-hq/
├── enlife/scripts/
│   ├── kachitalk_full_correlation_analysis.py  ← メイン分析スクリプト
│   ├── extract_kachitalk_logs.py  (既存・サンプル用)
│   └── kachitalk_sample_logs.json  (テスト用)
├── glow-ma/src/
│   └── KachiTalkIntegration.gs  ← Google Sheets統合
└── docs/
    └── kachitalk_complete_analysis_setup.md  (このファイル)

/tmp/
├── kachitalk_full_export.csv  ← KachiTalk admin exporter
└── kachitalk_analysis_YYYYMMDD.json  ← 分析結果
```

---

## 実行チェックリスト

### 初回セットアップ

- [ ] KachiTalk admin dashboardにアクセス可能か確認
- [ ] 2026/7/1～10/31のログをフィルタで抽出確認（400+件か？）
- [ ] CSVエクスポート（UTF-8形式）
- [ ] Pythonスクリプト実行テスト
- [ ] 分析結果をレビュー
- [ ] Google Sheets統合（オプション）

### 定期運用

- [ ] 毎週月曜 9:00 にスクリプト自動実行
- [ ] Slack通知で結果が配信されているか確認
- [ ] 月末にチーム全体レビュー

---

## サポート・問い合わせ

- **技術的な質問**: Github Issues (#営業分析)
- **KachiTalk API連携**: [KachiTalk公式サポート](https://kachitalk.jp/support)
- **Google Sheets統合**: apps-script@glow.local

---

**最終更新**: 2026-10-24  
**次レビュー予定**: 2026-11-21
