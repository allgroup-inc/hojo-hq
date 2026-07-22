# Phase 0 セットアップ手順(人間タスク・合計30〜40分)

対象: 小柳さん(またはたかしくん) / 位置づけ: [技術ロードマップ](技術ロードマップ.md) Phase 0 の人間側作業
これが完了すると、①障害のLINE即時通知(基準❼)が稼働し、③計測(GA4+Clarity)の実装が着手可能になります。
②Lighthouse CI(基準❷)は登録作業不要で、すでに稼働しています。

---

## ① LINE Messaging API の有効化(約15分)→ 基準❼が稼働

1. [LINE Developersコンソール](https://developers.line.biz/console/) にログイン
   (公式アカウント @345pqedv を管理しているLINEビジネスIDでログイン)
2. プロバイダーを選択(なければ「ALLGROUP」等の名前で新規作成)
3. 公式アカウントに紐づく **Messaging APIチャネル** を開く
   - まだない場合: [LINE公式アカウント管理画面](https://manager.line.biz/) → 設定 → Messaging API → 「Messaging APIを利用する」で有効化
4. チャネルの「**Messaging API設定**」タブ最下部 → **チャネルアクセストークン(長期)** を「発行」→ コピー
5. 同チャネルの「**チャネル基本設定**」タブ最下部 → **あなたのユーザーID**(`U`で始まる文字列)をコピー
6. GitHubリポジトリ [allgroup-inc/hojo-hq](https://github.com/allgroup-inc/hojo-hq) → Settings → Secrets and variables → **Actions** → 「New repository secret」で以下2件を登録:

| Secret名(この通りに) | 値 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | 手順4のトークン |
| `LINE_ADMIN_USER_ID` | 手順5のユーザーID(小柳さん本人のID) |

7. 動作確認: リポジトリの Actions → healthcheck → 「Run workflow」で手動実行
   (正常時は通知なし。通知テストをしたい場合はたかしくん経由で技術部に依頼)

> 注意: チャネルアクセストークンは**絶対にチャットやドキュメントに貼らない**こと。GitHub Secrets登録のみ。

## ② GA4 の登録(約10分)→ 測定IDを技術部へ

1. [Google Analytics](https://analytics.google.com/) → 管理(左下歯車)→ プロパティを作成
   - プロパティ名: `沖縄企業のミカタ` / タイムゾーン: 日本 / 通貨: JPY
2. データストリーム → ウェブ → URL: `https://allgroup-inc.github.io` / ストリーム名: `hojo-hq`
3. 表示される **測定ID(`G-` で始まる)** をコピーして技術部(Claude Code)へ共有

## ③ Microsoft Clarity の登録(約10分)→ プロジェクトIDを技術部へ

1. [Microsoft Clarity](https://clarity.microsoft.com/) にサインイン(Google/Microsoftアカウント可)
2. 「新しいプロジェクト」→ 名前: `沖縄企業のミカタ` / URL: `https://allgroup-inc.github.io/hojo-hq/`
3. 設定 → セットアップ → **プロジェクトID**(10文字程度の英数字)をコピーして技術部へ共有

## ④ (①のついでに推奨)LIFFアプリの発行(約5分)→ Phase 1 の下準備

①でLINE Developersを開いたついでにやっておくと二度手間になりません。

1. 同じチャネル(またはLINEログインチャネルを新規作成)→「**LIFF**」タブ → 追加
2. LIFFアプリ名: `ミカタ診断` / サイズ: `Full` / エンドポイントURL: `https://allgroup-inc.github.io/hojo-hq/`(後で診断ページURLに変更可)/ Scope: `profile` にチェック
3. 発行された **LIFF ID**(`xxxx-xxxxxxxx` 形式)を技術部へ共有

---

## 完了後に自動で起きること

- ヘルスチェック失敗時、Issueに加えて**小柳さんのLINEに即時通知**が届く(基準❼達成)
- GA4測定ID・ClarityプロジェクトIDが共有され次第、技術部がサイトに計測タグと
  診断ファネル(診断開始→完了→LINEタップ)のイベント計測を実装
- LIFF IDが共有され次第、Phase 1(診断×LINEユーザーID紐付け・企業台帳=基準❺)に着工
