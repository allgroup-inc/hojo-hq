# GLOW M&A・不動産 企業リレーション台帳

設計書: `docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md`

## これは何か

GLOWのM&A・不動産事業向けの非公開営業支援基盤。実データ(企業名・対応履歴等)は
Googleスプレッドシートに保持し、このディレクトリにはGAS(Google Apps Script)の
ロジックのみを置く。**実データは一切このリポジトリにコミットしない。**

## セットアップ(初回のみ)

1. `npm install -g @google/clasp` (未導入の場合)
2. `clasp login` でGoogleアカウント認証
3. Apps Scriptプロジェクトを新規作成し、スタンドアロンスクリプトとして
   GLOW企業リレーション台帳のスプレッドシートに紐付ける(スプレッドシートの
   拡張機能 > Apps Script から作成すると自動的に紐付く)
4. `glow-ma/.clasp.json.example` を `glow-ma/.clasp.json` としてコピーし、
   `scriptId` を実際のスクリプトIDに書き換える(このファイルはコミットしない)
5. `cd glow-ma && clasp push` でコードをApps Scriptに反映する
6. Apps Scriptエディタで `ensureLedgerTabs` を一度だけ手動実行し、4タブを作成する

## 7000件リストのインポート

1. スプレッドシートに「インポート待ち」タブを作り、元データを貼り付ける
2. `glow-ma/src/ImportRunner.gs` の `IMPORT_COLUMN_MAP` を実際の見出しに合わせて書き換える
3. `clasp push` して `importCompaniesFromStaging` を実行する
4. 実行ログで新規読込・名寄せ統合・最終件数を確認する

## 次のフェーズ

スコアリング・掘り起こしアラート・レター生成・ダッシュボードは、
`docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md` の
フェーズ2以降として別Planで実装する。

## テスト

```bash
node --test tests/glow_ma_schema.test.mjs tests/glow_ma_dedupe.test.mjs tests/glow_ma_csv_import.test.mjs
```
