# SNS自動投稿(Facebook/Instagram)セットアップ — 議事20260730 議題2

> ✅ **稼働開始(2026-07-30)**。Meta連携完了・Secrets3件登録済み・初回実投稿に成功(FB id=122102253429408043 / IG id=17959391100178548)。
> 構成メモ: IG @okinawa_mikata(ビジネスアカウント・IGユーザーID 17841447182099656)⇔FBページ「沖縄企業のミカタ」(ID 1207480642452364)にリンク済み(※当初enlifeページに誤リンクされていたのを付け替え)。Metaアプリ=mikata-sns(ID 1384397420420376・開発モード・ポートフォリオokinawa_mikata)。**ページトークンは長期ユーザートークン(期限2026-09-28)由来 → 2026-09下旬までにグラフAPIエクスプローラ+デバッガー「延長」で再発行してSecrets更新**。

実装済み: `scripts/post_social.py` + `.github/workflows/social-post.yml`(月水金 10:05 JST)。
素材は毎日自動生成される posts/launch(キャプション)+posts/images(画像)をローテーション投稿する。
Meta側のSecrets 3件が無い場合は「未接続」と明記してスキップ(ワークフローはグリーンのまま)。

## 人間側の残り手順(Meta連携)

1. **Instagram(@okinawa_mikata)をプロアカウント化**(スマホのIGアプリ: 設定→アカウントの種類とツール→プロアカウントに切り替え→ビジネス)
2. **FacebookページとIGを連携**(Meta Business Suite: business.facebook.com → 設定 → ビジネスアセット → IGアカウントを追加)
   ※たかしくんがFBページ管理者になる作業と同時にやると一度で済む
3. **Meta開発者アプリ作成+トークン発行**(developers.facebook.com。技術部がChrome代行で一緒にやる想定):
   - アプリ作成(ビジネス) → 権限 `pages_manage_posts` `pages_read_engagement` `instagram_basic` `instagram_content_publish`
   - Graph APIエクスプローラで**ページの長期アクセストークン**を発行
   - ページID(FBページの概要欄)と IGビジネスアカウントID(`/{page-id}?fields=instagram_business_account`)を取得
4. GitHub Secrets に3件登録:

| Secret名 | 値 |
|---|---|
| `FB_PAGE_ID` | Facebookページの ID |
| `FB_PAGE_ACCESS_TOKEN` | ページの長期アクセストークン |
| `IG_USER_ID` | IGビジネスアカウントの ID |

5. 動作確認: Actions → social-post → Run workflow → FB/IGに1本投稿されることを確認

## 運用ルール(議事で確定)
- 頻度: 月・水・金の10:05 JST に1本(変更は小柳さん決裁)
- **週1回、直近投稿3本を人が抜き取り点検**(三名体制ルール5)。コメント対応は人間(たかしくん/SNS部)
- 失敗時は小柳さんのLINEに即時通知
- 見直し期限: 2027-01-末
