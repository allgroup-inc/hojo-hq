# ノビシロ セルフサーブ診断商品 — 設計(Plan 2)

作成日: 2026-07-25
ステータス: ドラフト(ユーザーレビュー待ち)
前提: [2026-07-25-ai-backoffice-web-funnel-design.md](2026-07-25-ai-backoffice-web-funnel-design.md) の「Plan 2」を具体化するもの。サイト骨格(Plan 1)は `docs/superpowers/plans/2026-07-25-gajumaru-site-skeleton.md` で実装済み

## 背景・目的

`site/nobishiro/` のトップページに「近日公開」として置かれているセルフサーブ診断商品の実体を作る。ユーザーが業種・課題等をフォームで回答し、オンライン決済(¥14,800固定)後、AIエージェント「ガジュマルくん」の人格でカスタムレポートをメール配信する。プロプラン(月額伴走)への転換率最大化が目的であり、この商品自体は収益の柱ではなく「本気度を確認できる低価格な入口」と位置づける(design spec準拠)。

## スコープの簡略化(design specからの変更点)

- **価格**: design specの「9,800〜19,800円」という幅を、Stripe実装をシンプルに保つため**単一価格¥14,800(中間値)**に固定する。複数価格帯は将来拡張とし、今回は作らない
- **レポート形式**: design specの「PDF/Web出力」を、**HTMLメールのみ**に絞る。GASの`MailApp`が標準機能でHTMLメール送信をサポートしており、PDF生成(Docs API等の追加構成)を避けられる
- **バックエンド基盤**: design specでは「サーバーレス関数」とだけ書かれていたが、既存の `docs/技術ロードマップ.md` がhojo-hq本体のPhase 1バックエンドとして採用している**GAS(Google Apps Script)+ Sheets**をそのまま踏襲する(月額¥0、非エンジニアがスプレッドシートをそのまま台帳として使える、実装難度が低い)

## アーキテクチャ

```
[site/nobishiro/shindan/] 診断フォーム(静的HTML)
        ↓ フォーム送信
GAS Web App「doPost」① フォーム受付
  → Sheetsに「診断ID発行・回答・pending」で記録
  → Stripe Checkout Session作成(client_reference_id=診断ID)して返す
        ↓ ブラウザをそのURLへリダイレクト
Stripe Checkout(ホスト型決済ページ、¥14,800固定)
        ↓ 決済完了
  ├→ ユーザーは complete/ ページへ戻る(「メールでお届けします」表示のみ)
  └→ Stripeがwebhookを発火
GAS Web App「doPost」② Stripe webhook受付
  → 署名検証 → 診断IDでSheetsの回答を引き当て
  → Claude APIでレポート生成 → MailAppでHTMLメール送信
  → Sheetsのステータスを「決済済み・送信済み」に更新
```

**設計上の要点**: 決済完了ページへの到達だけをトリガーにレポート生成すると、未払いのユーザーがcomplete/ページに直接アクセスしてもレポートが生成されてしまう。これを避けるため、**Stripeのwebhookを、決済確認とレポート生成トリガーの唯一の信頼できる情報源とする**。ユーザー向けの着地ページは「お届けします」と伝えるだけで、実処理は裏側のwebhookが非同期に行う。

## コンポーネント

| ファイル/リソース | 役割 | 依存 |
|---|---|---|
| `site/nobishiro/shindan/index.html` | 診断フォームUI | `shindan/logic.js`, `../analytics-config.js` |
| `site/nobishiro/shindan/logic.js` | フォームバリデーション+GAS Web App呼び出し+Stripeへのリダイレクト。フクギイロの `site/fukugiiro/shindan/logic.js` と同じUMD形式(ブラウザ/Node両対応、Node側は `tests/nobishiro-shindan.test.mjs` でCI検証) | なし(純粋関数中心) |
| `site/nobishiro/shindan/complete/index.html` | 決済完了の着地ページ。処理が非同期である旨を明記し、フェイクの完了表示をしない | なし |
| `gas/nobishiro-shindan/Code.gs`(新規) | GAS Web Appのソース。`doPost`のエントリーポイント1つで、リクエストbody内の`type`フィールド(`"submit"` / `"stripe_webhook"`)により2つの処理に分岐 | Stripe API, Claude API, Google Sheets, MailApp |
| `gas/nobishiro-shindan/PriceCalc.gs`(新規) | 価格・メール文面組み立てなど、GAS固有API(UrlFetchApp等)に依存しない純粋ロジック。Node側でのテスト移植を容易にするため分離 | なし |
| Google Sheets(新規・ノビシロ専用、非公開) | リード台帳。列: 診断ID/タイムスタンプ/回答JSON/決済状況/Stripeセッションid/メールアドレス/レポート送信状況。カチカクくんが営業フォローに使う | — |

GASのソースはこのリポジトリ内 `gas/nobishiro-shindan/` でバージョン管理し、[clasp](https://github.com/google/clasp)でGoogle側にデプロイする(hojo-hqの技術ロードマップにあるGAS運用パターンを踏襲)。

## データフロー詳細

### ① フォーム送信(`type: "submit"`)
1. ユーザーが `site/nobishiro/shindan/index.html` で質問(業種/従業員数/月商規模/管理コスト実感/営業効率の課題/最優先課題)に回答
2. `logic.js` がクライアント側バリデーション後、GAS Web AppへPOST(`{type: "submit", answers: {...}}`)
3. GAS側: 診断IDをUUIDで発行 → Sheetsに新規行(status: `pending`)を追記 → Stripe API(`UrlFetchApp`)でCheckout Sessionを作成(`client_reference_id`に診断ID、`success_url`に `.../shindan/complete/`、price は固定¥14,800)→ Checkout URLをレスポンスとして返す
4. `logic.js` がブラウザを Checkout URL へリダイレクト

### ② Stripe Webhook受付(`type: "stripe_webhook"`)
1. Stripeが決済完了時にGAS Web AppのURLへPOST(Stripe側のWebhook設定で、GASのURLを宛先として登録)
2. GAS側: Stripe-Signatureヘッダーを検証(なりすまし防止)→ `client_reference_id`(診断ID)でSheetsの該当行を検索
3. 該当行の回答データ + Claude APIで構造化レポートを生成(プロンプトで「ガジュマルくん」の人格を指定、料金比較・改善提案・プロプランへの誘導を含める)
4. `MailApp.sendEmail`でHTMLメール送信(送信先はStripe Checkoutで収集したメールアドレス)
5. Sheetsの該当行を `status: sent` に更新

## エラーハンドリング

- **フォーム送信失敗**(決済前、GAS呼び出しがエラー): ユーザーにエラー表示・再試行を促す。決済が発生していないため実害なし
- **決済成功後にレポート生成が失敗**(Claude API障害・タイムアウト等): Sheetsの行は `status: paid_pending_report` のまま残る。カチカクくんが日次でこのステータスの行を確認し、手動フォローする運用でカバーする(自動リトライはv1では実装しない — YAGNI。件数が増えて手動運用が回らなくなった時点で自動リトライを追加する)
- **Stripe webhookの署名検証失敗**: リクエストを拒否し、Sheetsに何も書き込まない。GASのログに記録

## テスト方針

- `site/nobishiro/shindan/logic.js`: バリデーションロジック(必須項目チェック、業種/従業員数などの選択肢妥当性)をNode側でユニットテスト。フクギイロの `tests/shindan.test.mjs` と同じUMDパターンを踏襲し、`tests/nobishiro-shindan.test.mjs` として追加
- `gas/nobishiro-shindan/PriceCalc.gs`: 価格計算・メール文面組み立てなど、GAS固有APIに依存しない部分は同等ロジックをNode側にも複製してテスト(GAS自体はNode環境で直接実行できないため)
- Stripe/Claude API/MailAppを実際に呼び出す統合部分は、Stripeのテストモードを使った手動E2E確認に頼る(v1ではCI自動化しない)
- 新しいLP検査対象ページ(`shindan/index.html`, `shindan/complete/index.html`)は既存の `scripts/check_lp_nobishiro.py` の対象glob(`site/nobishiro/**/*.html`)に自動的に含まれるため、追加の検査スクリプト変更は不要

## セキュリティ・法務

- 決済情報(カード番号等)は一切自前で扱わない(Stripe Checkoutのホスト型ページに完全委任)
- Sheetsに保存する個人情報(メールアドレス・回答内容)は非公開スプレッドシートとし、アクセス権をカチカクくん・関係部門のみに限定する
- Claude APIへ送信する回答データに、決済情報等の機微情報を含めない
- レポート内の相場比較・料金訴求は、Plan 1で確立した「一般的に〜と言われています(自社調べ・要確認)」という守り部の慣例的な表現を踏襲し、断定表現を使わない

## 未決事項(実装着手前に確定が必要)

- Stripeアカウントの新規作成(テストモード→本番モード)
- 実際に使うAnthropic APIキー(既存の`ANTHROPIC_API_KEY`を流用してMVPを動かし、コスト按分が必要になった時点で分離する想定)
- GASプロジェクトの発行元Googleアカウント(ALLGROUPの既存GASアカウントを使うか新規か)
- Plan 1同様、この機能も `site/nobishiro/` 全体が公開パイプラインから除外されている間(`.github/workflows/update.yml` のノビシロ除外ステップ)は本番稼働しない。小柳さんの掲載決裁が出るまでStripeを本番モードにする必要はない
