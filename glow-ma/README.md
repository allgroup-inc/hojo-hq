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

この方法でインポートした企業は、`parseCompanyCsvRow` の実装により流入ルートが常に「②手紙DM」で
固定登録される(他ルートで取り込みたい場合はインポート後に手動で修正する)。

**注意:** 企業マスタタブに列を手動で追加しないこと。名寄せ統合時に行の並び替えが発生するため、
追加した列の値が別の企業の行にずれてしまう。

## スコア・ランクの再計算(Phase 2)

企業マスタの各社について、業種・規模・代表者年齢・流入ルート・対応履歴ログの
反応イベントからスコアとランク(A〜D)を自動計算する。

1. `clasp push` で最新コードを反映する
2. Apps Scriptエディタで `recalculateAllScores` を実行する
3. 企業マスタの「初期スコア」「反応スコア」「総合スコア」「ランク」列が更新される

**現時点の制約:**
- スコアの重み・閾値は `glow-ma/src/scoring.js` の `DEFAULT_CONFIG` にハードコードされており、
  `設定` シートからの動的な読み込みはまだ実装していない。値を調整したい場合は
  `DEFAULT_CONFIG` を編集して `clasp push` し直す
- 業種のM&A流動性「高」判定に使っているキーワードリスト(建設・運送・介護・美容・理容・
  飲食・小売)は、GLOWチームの実務レビューを経た確定版ではない**たたき台**。
  実データを見ながら見直すこと(見直し期限: 2026-10-27、
  `docs/superpowers/specs/2026-07-27-glow-ma-scoring-triangle-review.md` 参照)
- 対応履歴ログの「種別」は、反応スコアの集計対象になるかどうかが値によって決まる。
  必ずプルダウンから選択すること(自由入力の表記ゆれは集計に反映されない)

## 次のフェーズ

スコアリング・掘り起こしアラート・レター生成・ダッシュボードは、
`docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md` の
フェーズ2以降として別Planで実装する。

## テスト

```bash
node --test tests/glow_ma_schema.test.mjs tests/glow_ma_dedupe.test.mjs tests/glow_ma_csv_import.test.mjs
```
