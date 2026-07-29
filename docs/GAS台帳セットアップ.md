# 企業台帳(GAS+スプレッドシート)セットアップ — 基準❺の土台

位置づけ: [技術ロードマップ](技術ロードマップ.md) Phase 1 / 決裁: 小柳さん
目的: 診断回答×LINEユーザーIDを**非公開**スプレッドシートに自動蓄積し、承継/融資シグナルを自動付与する(法務ルール「企業の個人情報は公開リポジトリに置かない」を満たす唯一の受け皿)。

構成: 診断ページ(LIFF化済み前提)→ POST → GAS Webアプリ → スプレッドシート「ミカタ企業台帳」

## 進捗(2026-07-29 更新)
- ✅ **LIFF発行済み**: LINEログインチャネル「ミカタ診断」(ID 2010886544)/ **LIFF ID `2010886544-ciK9QPBm`**
- ✅ **サイト側実装済み**: 診断ページのLIFF化+台帳POST(重複送信防止つき)。通常ブラウザではSDK非読込でLighthouse影響なし。実ブラウザで通し検証済み
- ✅ CI実装済み: デプロイ時にSecretsから送信先を注入(update.ymlの「Inject ledger config」ステップ。リポジトリには実URL・トークンを置かない)
- ⏳ **残り(人間側・下の手順1〜4)**: スプレッドシート作成→GASコード貼付→トークン設定→ウェブアプリデプロイ→**GitHub Secretsに `GAS_LEDGER_ENDPOINT` と `GAS_LEDGER_TOKEN` を登録**
- ⏳ LINE側: リッチメニュー「制度をさがす」のリンクを **`https://liff.line.me/2010886544-ciK9QPBm`** に変更(manager.line.biz)。LINEログインチャネルを「開発中→公開」に切替

## 手順1: スプレッドシート作成(小柳さん or たかしくん・5分)

1. [Google スプレッドシート](https://sheets.new)で新規作成 → 名前「ミカタ企業台帳」
2. **共有設定は「制限付き」のまま**(公開しない)。閲覧が必要なメンバー(たかしくん・提携部)にのみ個別共有
3. 拡張機能 → Apps Script を開く

## 手順2: GASコード貼り付け(5分)

Apps Scriptエディタの `コード.gs` を以下で置き換え:

```javascript
/**
 * ミカタ企業台帳 受信エンドポイント
 * 診断ページ(LIFF)からのPOSTを受け、台帳シートに1行追記する。
 * 承継/融資シグナルは診断回答から自動付与(カモフラージュ設計)。
 */
const SHEET_NAME = '台帳';
const HEADERS = [
  '受信日時', 'LINEユーザーID', 'LINE表示名',
  '会社名', '代表者名', '所在地',
  '市町村', '業種', '従業員数', '経営テーマ', '10年後',
  'マッチ件数', '承継シグナル', '融資シグナル', '経路',
];

function doPost(e) {
  const props = PropertiesService.getScriptProperties();
  const expected = props.getProperty('SHARED_TOKEN');

  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (_) {
    return json_({ ok: false, error: 'bad json' });
  }
  if (!expected || body.token !== expected) {
    return json_({ ok: false, error: 'unauthorized' });
  }

  const a = body.answers || {};
  const themes = Array.isArray(a.themes) ? a.themes : [];
  // カモフラージュ設計: 直接聞かず「経営テーマ」「10年後」から自然検知
  const shokei = themes.includes('shokei') ||
    ['hikitsugi', 'joto'].includes(a.future) ? '●' : '';
  const yushi = themes.includes('shikin') ? '●' : '';

  const sheet = getSheet_();
  sheet.appendRow([
    new Date(),
    String(body.userId || ''),
    String(body.displayName || ''),
    String(body.company || ''),
    String(body.ceo || ''),
    String(body.address || ''),
    String(a.area || ''),
    String(a.biz || ''),
    String(a.emp || ''),
    themes.join(','),
    String(a.future || ''),
    Number(body.matchedCount || 0),
    shokei,
    yushi,
    String(body.source || 'diagnosis'),
  ]);
  return json_({ ok: true });
}

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
```

## 手順3: 共有トークン設定(2分)

1. Apps Script左メニュー「プロジェクトの設定」→「スクリプト プロパティ」
2. プロパティ `SHARED_TOKEN` / 値: ランダムな長い文字列(例: パスワード生成ツールで32文字)
3. 同じ値を GitHub Secrets に `GAS_LEDGER_TOKEN` の名前で登録(https://github.com/allgroup-inc/hojo-hq/settings/secrets/actions)。**チャットやドキュメントには貼らない**

## 手順4: ウェブアプリとしてデプロイ(3分)

1. 右上「デプロイ」→「新しいデプロイ」→ 種類「ウェブアプリ」
2. 実行ユーザー: **自分** / アクセスできるユーザー: **全員**
   (「全員」でもトークン検証で保護される。URLとトークンの両方を知らない限り書き込み不可)
3. 発行された **ウェブアプリURL**(`https://script.google.com/macros/s/.../exec`)を GitHub Secrets に `GAS_LEDGER_ENDPOINT` の名前で登録

## 完了後に技術部が行うこと

- ✅ 診断ページをLIFF化(実装済み 2026-07-29)
- ✅ 診断完了時に `{token, userId, displayName, answers, matchedCount}` を上記URLへPOST(実装済み・同一ユーザー×同一回答は1回のみ送信)
- 会社名/代表者名/所在地はLINE登録後の入力フォーム(またはトーク)から段階的に取得し同じ台帳へ追記
- E2Eテスト(tests/e2e)に「診断→台帳書き込み」の通し検証を追加(基準❶の後半)

## 法務メモ(絶対ルール)

- 台帳スプレッドシートは非公開を維持。リポジトリ・サイト・SNSに一切置かない
- 診断ページには情報の利用目的(制度案内・締切アラート・関連サービスのご案内)を明示する
- 削除依頼が来たら該当行を削除できるよう、LINEユーザーIDで検索可能にしてある
