# 人間タスク: IG常時チェックのトークン設定(小柳さん/遥さん)

これを済ませると、毎朝06:00(JST)にInstagramが自動チェックされ、
問題があるとGitHubのIssueで通知が届くようになります(仕組み: `.github/workflows/ig-check.yml`)。
所要時間の目安: 30〜40分(初回のみ)。

## 事前条件

1. **@moradou.okinawa がプロアカウント(ビジネスまたはクリエイター)であること**
   - Instagramアプリ → 設定 → アカウントの種類とツール → プロアカウントに切り替える
2. **Facebookページと連携していること**
   - Facebookでページを作成(名前は「もらいわすれ堂」でOK)
   - Instagramアプリ → 設定 → ビジネスツールと管理 → Facebookページをリンク

## トークン発行(初回)

3. https://developers.facebook.com/ にFacebookアカウントでログイン → 「マイアプリ」→「アプリを作成」
   - 種類は「ビジネス」を選択。アプリ名は「moradou-check」等でOK
4. アプリのダッシュボード → 「ツール」→ **グラフAPIエクスプローラ** を開く
5. 右上の「Meta App」に作ったアプリを選び、「User Token を生成」
   - アクセス許可(パーミッション)に以下を追加して生成:
     `instagram_basic` `pages_show_list` `pages_read_engagement`
6. 生成された短期トークンを**長期トークン(約60日)に交換**する。ターミナル(またはブラウザ)で:
   ```
   https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=<アプリID>&client_secret=<app secret>&fb_exchange_token=<短期トークン>
   ```
   - アプリID/app secretはアプリの「設定 → ベーシック」にある
   - 返ってきたJSONの `access_token` が長期トークン
7. **InstagramユーザーIDを取得**。グラフAPIエクスプローラで順に実行:
   - `me/accounts` → 連携したページの `id` を控える
   - `<ページid>?fields=instagram_business_account` → 返ってきた数字が **IG_USER_ID**

## GitHubへの設定

8. https://github.com/allgroup-inc/hojo-hq/settings/secrets/actions で
   「New repository secret」を2つ作成:
   - `IG_ACCESS_TOKEN` = 手順6の長期トークン
   - `IG_USER_ID` = 手順7の数字
9. Actionsタブ → 「ig-check」→「Run workflow」で手動実行し、緑になることを確認
   (キャプションに違反があれば赤+Issueが立ちます。それは体制が働いている証拠です)

## 運用の注意

- **トークンは約60日で失効します**。失効するとig-checkが「トークン期限切れの可能性」の
  Issueを立てるので、そのときは手順5〜6(または6の交換だけ)をやり直してSecretsを更新
- チェック内容: 禁止表現(断定・「7日前」・lin.ee直貼り=出荷ゲートと同一)/
  ハッシュタグ6個以上/金額表現の要確認漏れ(警告)/プロフィールリンク未設定/14日以上の投稿停滞
- 保存されるのはIG上で誰でも見られる公開情報のみ(議事_20260906_IG常時チェック体制.md)
