# glow-ma Phase 16 設計書: レター発送日の記録・発送業者連携用CSV出力

(README記載の完了フェーズはPhase 1〜15。本機能はPhase 16として追加する。)

三名体制レビュー: `2026-08-07-glow-ma-letter-shipping-triangle-review.md`(裁定: 採用・条件付き)

## 背景・目的

「レター下書き」タブ(Phase 4)には下書き生成・ステータス(下書き/送付済み/見送り)はあるが、
いつ発送したかを記録する列がない。この機能は以下2点を実現する。

1. 発送日を記録し、発送業者(複数社分をまとめて発送を委託する外部業者)にそのまま渡せる宛先一覧
   CSVを、発送日単位で出力できるようにする
2. 発送日から約10日後にフォロー連絡すべきタイミングを、既存の日次アラート(AlertRunner)の仕組みに
   乗せて自動的に見落とし防止する

## 用語の定義(トライアングルレビューの裁定に基づく)

**「発送日」は「投函完了日」を意味する。** 「これから業者に依頼する予定日」ではなく、「実際に発送
した(または発送業者への依頼が完了し、発送が確定した)日」として、単一の意味で統一する。

## スコープ外(初回リリースでは扱わない)

- CSVの発送業者への自動送信(メール送信・API連携等)。人が生成したCSVをダウンロードし、自分の
  判断で業者に渡す運用に留める
- 発送業者への個人情報(所在地・窓口担当者名)委託に関する契約要否の確認(守り部へ別途提起。
  本機能の実装はブロックしない)
- レターの自動送信(Phase 4からの既存方針を継続。送付は必ず人が行う)

## アーキテクチャ

既存のPhase 4(`letterContent.js`/`LetterRunner.gs`)・Phase 3(`alerting.js`/`AlertRunner.gs`の
即時アラート用onEditトリガー)と同じ設計パターンを踏襲する。

- ロジック(CSV組み立て・フォロー予定日計算)はGAS/Node両対応のUMD形式プレーンJSとして
  `glow-ma/src/shippingContent.js`に実装し、`node --test`でユニットテストする
- GAS専用の`ShippingRunner.gs`(onEditトリガー・メニュー・ダイアログ表示)は、ロジックを
  `shippingContent.js`に委譲する薄いグルーコードとする
- 日付計算は`glow-ma/src/alerting.js`の`GlowAlerting`(`toDate`/`daysBetween`相当)を再利用し、
  日付処理ロジックをこのファイルで重複定義しない

## File Structure

```
glow-ma/src/
  schema.js          — 修正: LETTER_DRAFT_HEADERSの末尾に「発送日」を追加
  shippingContent.js  — 新規: CSV組み立て・フォロー予定日計算(GlowShippingContent)
  ShippingRunner.gs    — 新規: onEditトリガー(自動記録)・CSV出力メニュー(GAS専用)
tests/
  glow_ma_shippingContent.test.mjs — 新規
glow-ma/README.md      — Phase 16のセットアップ・使い方を追記
```

## データモデル変更

### schema.js

`LETTER_DRAFT_HEADERS`の末尾に`"発送日"`を追加する(既存の「末尾追加のみ」ルールに従う。既存データの
列位置がズレて破損することを防ぐため、途中への挿入は禁止)。

```js
var LETTER_DRAFT_HEADERS = [
  "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス", "発送日"
];
```

ステータス・種別の定数(`LETTER_DRAFT_TYPES`/`LETTER_DRAFT_STATUSES`)は変更しない。「発送日」列は
人が「レター下書き」タブに直接日付(`yyyy-MM-dd`)を入力する運用とし、入力規則(プルダウン等)は
設けない(自由な日付入力のため)。

## `glow-ma/src/shippingContent.js`(新規)

```js
var DEFAULT_CONFIG = {
  followUpDays: 10,
  followUpAction: "手紙フォロー架電"
};

function buildShippingCsvRows(letterDrafts, companies, targetDate) {
  // letterDrafts: 発送日 === targetDate の行を抽出
  // companies: 企業IDで突合し、会社名・所在地・窓口担当者名を取得
  // 戻り値: ヘッダー行を含む2次元配列
  //   [["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"], [...], ...]
  // targetDateに一致する行が無い場合はヘッダー行のみを返す(空配列ではない)
}

function computeFollowUpDate(sentDateValue, days) {
  // GlowAlerting の日付ユーティリティを使い、sentDateValue + days 日を
  // "yyyy-MM-dd" 文字列で返す。sentDateValue が不正な場合は null
}
```

- `buildShippingCsvRows`は企業マスタに該当する企業IDが見つからない下書き行(データ不整合)は
  スキップし、会社名の代わりにエラーで落ちない(1件のデータ不備で全体のCSV生成が止まらないように
  障害隔離する。Phase 4の`generateNurturingDraftsForEligibleCompanies`と同じ考え方)
- CSV列は「発送日・企業ID・会社名・所在地・窓口担当者名」の5列とする(トライアングルレビューで
  合意した「宛先情報のみ」。本文は含めない)

## `glow-ma/src/ShippingRunner.gs`(新規、GAS専用)

### 1. onEditトリガー: `handleLetterDraftEdit(e)`

「レター下書き」タブの「発送日」列への入力を検知するインストール型onEditトリガー
(`AlertRunner.gs`の`handleInteractionLogEdit`と同じ設計パターン。シンプルトリガーの`onEdit`予約名は
使わず、`installLetterDraftEditTrigger()`で人が手動インストールする)。

発火時の処理(対象は「レター下書き」タブの「発送日」列、単一セルの編集のみ):

1. 編集された行から`企業ID`・`発送日`を取得
2. 企業マスタの該当行を検索し、**「次回アクション予定日」が空の場合のみ**、
   `shippingContent.computeFollowUpDate(発送日, 10)`の結果をセットし、「次回アクション内容」に
   `"手紙フォロー架電"`をセットする(既存の予定日がある場合は何もしない。トライアングルレビューの
   裁定1)
3. 対応履歴ログに1行追記する: `種別="手紙送付"`, `日付=発送日`, `担当者="システム(自動記録)"`,
   `対応相手="未接触"`, `内容メモ="発送日の記録により自動追記(下書きID: <下書きID>)"`(`LockService`で
   保護。既存の`appendNurturingInteractionLog_`と同型)

**重複記録の防止:** 「発送日」セルは後から人が訂正する可能性がある(誤入力の修正等)。同じ下書き行を
複数回編集するたびに対応履歴ログへ重複して自動記録されることを防ぐため、追記前に対応履歴ログを
検索し、`内容メモ`に同じ`下書きID`を含む行が既に存在する場合はログへの追記をスキップする
(ステップ2の次回アクション予定日セットは、既存値が空かどうかの判定が既にこの重複を吸収するため
追加の対策は不要)。`hasRecentNurturingDraft_`と同様、`LETTER_DRAFT_HEADERS`の`下書きID`列を
起点にした冪等化とする。

企業マスタ・対応履歴ログへの書き込みは、それぞれ`LockService.getDocumentLock()`で保護し、
追記(1行分の`setValues`)のみでシート全体を書き直さない(既存方針の踏襲)。

### 2. インストーラ: `installLetterDraftEditTrigger()`

既存の`installInteractionLogEditTrigger()`と同じ冪等パターン(同名ハンドラの既存トリガーを削除して
から登録し直す)。README「初回セットアップ」に手動実行手順を追記する。

### 3. CSV出力: `exportShippingCsvForDate()`

メニュー「GLOW台帳」→「発送日でCSV出力」から実行する。

1. `ui.prompt`で対象の発送日を入力させる(既定値は本日の日付)
2. 企業マスタ・レター下書きタブを読み込み、`shippingContent.buildShippingCsvRows`でCSV行を組み立てる
3. 該当行が0件の場合は`ui.alert`で「該当する発送日のデータがありません」と表示して終了する
4. 該当行がある場合は`HtmlService`のダイアログにCSVプレビュー(テーブル表示)とダウンロードリンク
   (`data:text/csv;charset=utf-8,...`のBlobをbase64化したリンク)を表示する。**業者への送信は行わず、
   人がダウンロードしたファイルを自分の判断で業者に渡す**(トライアングルレビューの裁定3)

`ShareRunner.gs`の既存`onOpen()`に、メニュー項目「発送日でCSV出力」を追加する(GASプロジェクト内で
`onOpen`という関数名は1つしか持てないため、新規の`onOpen`は作らず既存関数に追記する)。

## テスト方針

- `tests/glow_ma_shippingContent.test.mjs`: `buildShippingCsvRows`(発送日での絞り込み・突合・
  データ不整合時のスキップ)、`computeFollowUpDate`(日数計算・不正日付時のnull)を`node --test`で
  検証する
- `ShippingRunner.gs`はGAS専用のため`node --test`では検証できない。`node --check`による静的チェックと
  手書きトレースで代替し、実運用前の手動検証が必要であることをREADMEに明記する(Phase 1〜9と同じ扱い)

## Global Constraints(既存方針の継続)

- 公開リポジトリ(hojo-hq)に実データ・発送先の個人情報を一切コミットしない
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GASとNode両方で動くファイルはUMD形式を踏襲する
- 企業マスタ・対応履歴ログへの書き込みは`LockService`で保護し、追記のみ行う

## 未決事項(この機能の実装後、別途提起する)

発送業者への所在地・窓口担当者名の受け渡しについて、委託契約の要否を守り部に確認する
(トライアングルレビュー裁定3。本機能の実装自体はブロックしない)。

## 見直し期限

2026-11-07(トライアングルレビューの裁定と同一)。運用実績を見て、次回アクション予定日の自動セット
条件(既存値がある場合は何もしない、という仕様)や発送業者への渡し方を再検討する。
