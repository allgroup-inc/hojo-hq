# もらいわすれ堂：GA4・LINE 分析セットアップガイド

**目的**: 「診断→準備シート DL→LINE登録→相談」の完全フロー計測。各タッチポイントの行動を追跡し、ボトルネック特定と月次改善をサポート。

**計測ID（GA4）**: G-TQMX3MPFSR（プロパティ「もらいわすれ堂」・2026-08-24 小柳さん作成）

---

## GA4 カスタムイベント定義

### 【イベント 1】診断実施（shindan_complete）

**発火タイミング**: ユーザーが Q1-Q5 を完了した瞬間

**パラメータ**:
- `results`: 該当制度の件数（数値）
  - 例: 結果が 5 件なら `results: 5`

**計測箇所**: `site/fukugiiro/shindan/index.html` Line 299

**用途**: 診断ページのコンバージョン計測 / 「診断実施数」のKPI

**例**: 診断実施者: 500人 / 月 → KPI達成状況を確認

---

### 【イベント 2】準備シート DL（download_sheet）

**発火タイミング**: ユーザーが「このシートをダウンロード」または「全シートをまとめてダウンロード」をクリック

**パラメータ**:
- `sheet_type`: `"single"` または `"bulk"`
  - `single`: 個別シート 1 件
  - `bulk`: 複数シートの一括 ZIP
- `seido_id`: 制度の ID（個別DL時のみ）
  - 例: `fk-kuni-jidoteate`
- `count`: 一括DL時のシート件数（一括DL時のみ）
  - 例: `count: 5`

**計測箇所**: `site/fukugiiro/shindan/index.html` Line 309, 323

**用途**: 「準備シート DL 率」の計測 / 診断→DL 転換を追跡

**例**: 診断 1,000 件 → DL 300 件 = 30% DL率

---

### 【イベント 3】LINE ウェルカムメッセージ開封（line_welcome_sent）

**発火タイミング**: LINE 公式アカウント側で、新規登録直後に自動配信時

**パラメータ**:
- `user_id`: ユーザーの LINE UID（LINE Official Account Manager が自動記録）
- `timestamp`: 送信時刻

**計測箇所**: LINE Official Account Manager の自動計測

**用途**: LINE 登録から初回メッセージまでの流入追跡

**例**: LINE登録 100 件 / 月 → ウェルカム受信 95 件（95%開封）

---

### 【イベント 4】LINE 定期配信（line_weekly_digest）

**発火タイミング**: 毎週木曜 15:00 に定期配信メッセージが送信された時

**パラメータ**:
- `week`: 配信週（1-4）
  - `week: 1` → 書類準備の進め方
  - `week: 2` → 書類作成のコツ
  - `week: 3` → 申請のタイミング
  - `week: 4` → 士業との相談
- `open_rate`: 配信後 15 分時点の開封率（%）
  - 例: `open_rate: 32`

**計測箇所**: LINE Official Account Manager → GA4 連携

**用途**: 定期配信の効果計測 / AB テスト（週 1 vs 隔週）の比較

**例**: Week 1 開封率 35% / Week 2 開封率 28% → Week 1 効果的

---

### 【イベント 5】LINE トリガー型配信（line_deadline_reminder）

**発火タイミング**: 各制度の申請期限 30 日前に自動配信時

**パラメータ**:
- `seido_id`: 対象制度 ID
  - 例: `fk-kuni-jidoteate`
- `days_until_deadline`: 期限までの日数
  - 例: `days_until_deadline: 30`
- `municipality`: 対象市町村
  - 例: `municipality: "那覇市"`

**計測箇所**: Power Automate → LINE Messaging API → GA4 イベント送信（スクリプト）

**用途**: 期限アラート効果の計測 / 市町村別の対象者追跡

**例**: 30日前アラート 50 件配信 → クリック 12 件（24%）

---

### 【イベント 6】成功事例配信（line_success_story）

**発火タイミ** ing**: 隔月（第 2・4 金曜）の成功事例メッセージ送信時

**パラメータ**:
- `story_id`: 事例の ID
  - 例: `case_20261021_naha_01`
- `seido_name`: その事例で受給した制度名
  - 例: `seido_name: "児童手当"`
- `amount`: 受給金額（あれば）
  - 例: `amount: 60000`

**計測箇所**: LINE Official Account Manager → GA4

**用途**: 成功事例の訴求力計測 / 再診断への導線効果

**例**: 成功事例配信 → 診断ページクリック 8 件

---

## UTM パラメータ管理

### 【Instagram 流入】

**パラメータ**: `utm_source=instagram_organic`

**適用先**:
- Instagram 投稿キャプション内の診断ページリンク
  - 例: `https://moraiwasuredo.jp/fukugiiro/shindan/?utm_source=instagram_organic`
- Stories リンク（あれば）

**計測**: GA4 → 「参照元」レポートで `instagram_organic` をフィルタ

**目標**: Instagram → 診断 の流入数・コンバージョン追跡

**月次報告**: `docs/monthly_reports/YYYY-MM-moradou-instagram.md` に記録

---

### 【LINE 流入】

**パラメータ**: `utm_source=line_organic`

**適用先**:
- LINE ウェルカムメッセージ内のリンク
  - 例: 準備シート DL ボタン、相談窓口リンク、診断ページ
- LINE 定期配信内のリンク

**計測**: GA4 → 「参照元」レポートで `line_organic` をフィルタ

**目標**: LINE メッセージ → アクション（DL / クリック）の追跡

---

### 【その他の流入源】

**検索流入**: `utm_source=organic`（自然検索・SEO）

**直接アクセス**: なし（ブラウザ直接入力）

**紹介**: `utm_source=referral`（他サイトからのリンク）

---

## GA4 カスタムイベント登録チェックリスト（管理画面設定）

Google Analytics 4 管理画面 → イベント で以下を確認：

- [ ] `shindan_complete` が登録され、`results` パラメータを記録している
- [ ] `download_sheet` が登録され、`sheet_type`, `seido_id`, `count` をすべて記録している
- [ ] `line_weekly_digest` が登録されている
- [ ] `line_deadline_reminder` が登録されている
- [ ] `line_success_story` が登録されている
- [ ] 各イベントの「イベント値」（e-commerce value）が設定されているか確認
  - 例: `download_sheet` は単なるアクション（値なし）でもいい

---

## LINE Official Account Manager 設定

### ダッシュボード構成

**LINE 公式アカウント名**: もらいわすれ堂

**Account ID**: @634vbptr（2026-08-10 小柳さん共有）

**配信機能**: 
- 1 対 1 メッセージ
- セグメント配信（市町村別・ユーザータイプ別）
- 自動応答（ウェルカムメッセージ）
- スケジュール配信（毎週木曜 15:00 定期配信）
- ターゲットメッセージ（条件付き自動配信 = トリガー型）

---

### 日次・週次・月次のモニタリング項目

#### 日次（毎日朝）

- [ ] 新規登録者数
  - 目標: 20 社 / 週 = 3 社 / 日
  - LOW: < 1 社なら流入確認

- [ ] ブロック数（増加有無）
  - 目標: ブロック率 < 5%（月間）
  - ALERT: 前日比 +3 件以上なら配信内容見直し

- [ ] トークセッション数（相談申し込み）
  - 目標: 1-2 件 / 日

#### 週次（毎週金曜）

- [ ] 1 週間の新規登録累計
  - 目標: 20 社
  - 記録: `fg_shindan_line_registrations` （weekly tracking）

- [ ] 定期配信の開封率・クリック率
  - 目標: 開封率 > 30%, クリック率 > 15%
  - 記録先: Spreadsheet「もらいわすれ堂_LINE週次レポート」

#### 月次（毎月末）

- [ ] 月間新規登録数
  - 目標: 100 社（3 ヶ月達成時の月平均値）
  - KGI として報告（docs/monthly_reports/YYYY-MM-moradou-summary.md）

- [ ] ブロック率（月間集計）
  - 目標: < 5%
  - 計算: ブロック数 / 配信数 × 100

- [ ] 相談申し込み件数
  - 目標: 5 件 / 月（LINE 部門）
  - KPI として報告

- [ ] AB テスト結果（初回: 11 月のみ）
  - 週 1 配信 vs 隔週配信の開封率・クリック率比較
  - 判定基準: クリック率 > 20% and ブロック率 < 5% なら継続

---

## LINE Official Account Manager 実装チェックリスト

### 基本設定

- [ ] リッチメニュー画像をアップロード
  - 3つのアイコン: 「準備シート」「相談窓口」「診断ページ」
  - サイズ: 2500×810px（縦横比: 2.5:1）

- [ ] ウェルカムメッセージの設定
  - 内容: `docs/moradou_line_messaging_guide.md` の パターン 1 を参照
  - 実行: 「ウェルカムメッセージ」機能から登録

- [ ] 自動応答メッセージの設定
  - 営業時間: 平日 9:00-17:00
  - メッセージ: 「この時間は自動応答です。営業時間内に返信いたします」

### 定期配信スケジュール設定

- [ ] 毎週木曜 15:00 の定期配信を予約
  - Week 1（毎月第1週）: 書類準備の進め方
  - Week 2（毎月第2週）: 書類作成のコツ
  - Week 3（毎月第3週）: 申請のタイミング
  - Week 4（毎月第4週）: 士業との相談

- [ ] 成功事例配信（隔月 第 2・4 金曜 8:00）
  - スケジュール設定で確認

### トリガー型配信設定（Power Automate 連携）

- [ ] Power Automate で「LINE Messaging API」フロー構成
  - トリガー: 毎日朝 8:00（seido.json の deadline フィールドをチェック）
  - アクション: 30 日以内の制度がある場合、LINE 自動配信
  - 設定内容: `docs/moradou_line_messaging_guide.md` パターン 3 参照

- [ ] 誤配信防止（同じ制度に複数回送信しないよう）
  - メタデータで「最後の送信時刻」を記録

### GA4 連携

- [ ] LINE Official Account Manager の GA4 トラッキングを有効化
  - 管理画面 → 分析 → Google Analytics 4 連携
  - 計測 ID: G-TQMX3MPFSR を入力

- [ ] LINE トラッキング用の「カスタムパラメータ」設定
  - 配信時に `utm_source=line_organic` を自動付与

---

## データ流入の全体フロー図

```
【診断ページ】
 ├─ Q1-Q5 完了
 │  └─ イベント: shindan_complete {results: N}
 │
 ├─ 準備シート DL クリック
 │  └─ イベント: download_sheet {sheet_type, seido_id or count}
 │
 └─ LINE登録ボタンクリック
    └─ イベント: line_add_click {pos: "result_top" or "result_bottom"}
       └─ 遷移先: https://moraiwasuredo.jp/go/fg-shindan/
          (go_link_redirect イベント記録)

【LINE 公式アカウント】
 ├─ Day 0: ウェルカムメッセージ
 │  └─ 計測: 開封率・クリック率（LINE Official Account Manager）
 │  └─ GA4 イベント: line_welcome_sent
 │
 ├─ 毎週木曜 15:00: 定期配信（4週ローテーション）
 │  └─ GA4 イベント: line_weekly_digest {week: 1-4}
 │  └─ AB テスト記録（11月のみ）
 │
 ├─ 毎日朝 8:00: トリガー型（期限 30日前）
 │  └─ GA4 イベント: line_deadline_reminder {seido_id, days_until_deadline}
 │
 └─ 隔月（第2・4 金曜）: 成功事例配信
    └─ GA4 イベント: line_success_story {story_id, seido_name}

【計測・分析】
 ├─ GA4 ダッシュボード（リアルタイム）
 │  └─ イベント一覧、フロー分析、ユーザー属性
 │
 ├─ LINE Official Account Manager（日次・月次レポート）
 │  └─ 開封率、クリック率、ブロック数、新規登録者数
 │
 └─ Google Spreadsheet（週次・月次まとめ）
    └─ KGI / KPI ダッシュボード
```

---

## 月次レポート作成フロー

### 1. GA4 データエクスポート

**実施日**: 毎月末の翌営業日

**エクスポート項目**:
- `shindan_complete` イベント数（診断実施数）
- `download_sheet` イベント数・内訳（単一 vs 一括）
- `line_add_click` イベント数（LINE登録クリック）
- 参照元別のセッション数（instagram_organic, line_organic, organic）

**保存先**: `docs/monthly_reports/YYYY-MM-moradou-ga4.md`

### 2. LINE Official Account Manager レポート

**実施日**: 毎月末の翌営業日

**ダウンロード項目**:
- 月間ユーザー数（新規登録 + 解除）
- 配信ごとのサマリー（開封率、クリック率）
- ブロック数推移

**保存先**: `docs/monthly_reports/YYYY-MM-moradou-line.md`

### 3. KGI / KPI 集計

**実施日**: 毎月末（金曜）夜

**集計内容**:
- KGI: LINE登録数（累計）
- KPI: 診断実施数、DL率、LINE→相談転換数

**報告先**: `docs/monthly_reports/YYYY-MM-moradou-summary.md`

**形式**: docs/moradou_operational_checklist.md の月次報告書フォーマットに準拠

---

## トラブルシューティング

### 症状: GA4 イベントが記録されない

**原因の可能性**:
1. GA4 トラッキング ID（G-TQMX3MPFSR）がページに読み込まれていない
2. `window.fgTrack` 関数が undefined
3. イベント名が typo（大文字小文字区別あり）

**確認方法**:
```javascript
// ブラウザコンソール
console.log(window.fgTrack);  // 関数か undefined か確認
console.log(window.ga);       // GA4 ライブラリ読み込み確認
```

**対策**:
- `site/fukugiiro/analytics-config.js` で `provider: "ga4"` と `measurementId` を確認
- `site/fukugiiro/assets/fg-analytics.js` が正常に読み込まれているか確認

### 症状: LINE トリガー配信が実行されない

**原因の可能性**:
1. Power Automate フローが無効化されている
2. LINE Messaging API のアクセストークンが期限切れ
3. seido.json の `deadline` フィールドが空 or 無効な形式

**確認方法**:
- Power Automate の「実行履歴」で前日のジョブが「失敗」していないか確認
- LINE Official Account Manager で「メッセージ送信履歴」を確認

**対策**:
- Power Automate フロー の再デプロイ（トークン更新）
- seido.json の deadline フィールド形式を確認（ISO 8601: YYYY-MM-DD）

---

## 実装完了チェックリスト（Task 6 の終了条件）

- [ ] GA4 カスタムイベント 6 個（shindan_complete, download_sheet, line_weekly_digest, line_deadline_reminder, line_success_story, line_welcome_sent）がすべて GA4 管理画面で「イベント」として登録されている
- [ ] 各イベントが正しいパラメータ（結果数、シート種別、週番号など）を記録している
- [ ] UTM パラメータが Instagram 投稿と LINE メッセージに含められている
- [ ] LINE Official Account Manager でウェルカムメッセージが設定済み
- [ ] 毎週木曜 15:00 の定期配信が予約されている（4週ローテーション）
- [ ] Power Automate で トリガー型配信（期限30日前）が稼働確認済み
- [ ] GA4 ダッシュボードで「参照元」「イベント」「ユーザー」の 3 つのレポートが表示される
- [ ] 月次レポートテンプレート（GA4, LINE, KPI）が docs/monthly_reports/ に作成可能な状態

---

## 参考資料

- GA4 カスタムイベント設定: https://support.google.com/analytics/answer/9267744
- LINE Official Account Manager: https://manager.line.biz/
- Power Automate での LINE 連携: https://learn.microsoft.com/ja-jp/power-automate/connectors/line-reference
- UTM パラメータ Google 公式ガイド: https://support.google.com/analytics/answer/1033867
