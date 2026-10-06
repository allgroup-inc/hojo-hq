# GLOW「世界の懸け橋」Instagram・Facebook 自動投稿 — セットアップ手順

2026-10-06 小柳さん決裁で開始。投稿は承認なしの全自動。決定の記録(反対意見と対応つき)は、非公開リポジトリ glow-docs-private の `docs/議事_20261006_GLOW世界の懸け橋_SNS自動投稿.md` にある。

## しくみ(全体像)
| もの | 場所 | 中身 |
|---|---|---|
| 投稿素材(32本) | `posts/glow/<id>.jpg` / `.md` | 画像1080×1350とキャプション。数字は提案資料で照合済みのものだけ |
| 投稿の順番 | `posts/glow/order.json` | 最後まで出したら先頭に戻る(約11週で1周) |
| 素材の作成 | `scripts/glow_sns_build.py` | 手元で実行(フォントが必要)。`--restamp` で出荷ゲートの日付だけ更新 |
| 投稿 | `scripts/glow_sns_post.py` + `.github/workflows/glow-sns-post.yml` | **月・水・金 12:05** にFacebookとInstagramへ1本ずつ。結果を小柳さんのLINEへ通知 |
| どこまで出したか | `data/glow_sns_state.json` | 二重投稿の防止。片方だけ失敗したら、次の回にその片方だけ出し直す |
| 安全装置 | `scripts/shipping_gate.py`(グループ `glow`) | 禁止表現・lin.ee直貼り・90日を超えた記録は投稿しない。ページ名に「GLOW」が無いトークンでは投稿しない |
| 定期の見直し | Claudeの定期実行(2か月ごと) | 数字の出典を見直し、出荷ゲートの記録を更新する。90日で投稿が止まらないようにするため |
| プロフィール用の画像 | `posts/glow/profile/profile.png`(アイコン)・`fb-cover.png`(Facebookのカバー) | |

## 小柳さんにやっていただくこと(アカウントの作成は本人確認があるため、人の手が必要)

### 1. Facebookページを作る(5分)
1. Facebookにログインした状態で https://www.facebook.com/pages/create を開く
2. ページ名: **世界の懸け橋｜株式会社GLOW**(「GLOW」の文字を必ず入れる。入っていないと自動投稿が止まる安全装置がある)
3. カテゴリ: 「輸出入業者」または「ビジネスサービス」
4. 自己紹介(そのまま貼り付け):
   > 沖縄の生産者・企業の商品を、世界最大級の企業どうしの取引サイト「Alibaba.com」上のGLOWの沖縄の売り場から、世界の買い手へ。株式会社GLOWの「世界の懸け橋」です。
5. プロフィール写真: `profile.png` / カバー写真: `fb-cover.png`(このチャットで送った画像)
6. ウェブサイト: https://glow-okinawa.jp/ ・メール: info@g-low.co.jp ・電話: 098-989-9329

### 2. Instagramのアカウントを作る(5分)
1. スマホのInstagramアプリ → 自分のプロフィール → 左上の名前 → 「アカウントを追加」→ 新しいアカウントを作成
2. ユーザーネームの候補: **glow_okinawa**(使われていれば glow.okinawa など)。※「懸け橋」をローマ字で書いたユーザーネームは使わない(家計の見直しやさんのシステム名と同じ綴りになるため)
3. 名前: **世界の懸け橋｜GLOW**
4. 自己紹介(そのまま貼り付け):
   > 沖縄の商品を、世界の買い手へ。
   > Alibaba.com上のGLOWの沖縄の売り場から、世界に届けるお手伝い。
   > 世界の市場の数字・海外へ売るコツを発信中
5. リンク: `https://glow-okinawa.jp/?utm_source=instagram&utm_medium=social&utm_campaign=profile`
6. プロフィール写真: `profile.png`
7. 設定 → 「アカウントの種類とツール」→「プロアカウントに切り替える」→「ビジネス」

### 3. InstagramとFacebookページをつなぐ(3分)
- Facebookで作ったページに切り替え → 設定 → 「リンク済みのアカウント」→ Instagram → 「アカウントをリンク」→ 2.で作ったアカウントでログイン

### 4. 自動投稿のカギを1つ登録する(10分)
ミカタのときと同じ手順。**カギ(トークン)はチャットに貼らず、GitHubにだけ入れる。**
1. https://developers.facebook.com/tools/explorer を開く
2. 右側の「Metaアプリ」で **mikata-sns** を選ぶ(同じGLOWの会社のアプリなので使い回せる)
3. 「アクセス許可を追加」で次を選ぶ: `pages_show_list` `pages_manage_posts` `pages_read_engagement` `instagram_basic` `instagram_content_publish` `business_management`
4. 「Generate Access Token」→ 出てきた画面で **新しく作ったGLOWのページとInstagramにチェック** → 許可
5. 出てきたトークンをコピー → https://developers.facebook.com/tools/debug/accesstoken/ に貼って「デバッグ」→ 一番下の **「アクセストークンを延長」** → 延長されたトークンをコピー
6. Graph APIエクスプローラに戻り、トークン欄に5.のトークンを貼る → 上の入力欄を `me/accounts` にして「送信」
7. 結果の中から、名前が「世界の懸け橋｜株式会社GLOW」のところの **access_token** の値をコピー(これが期限の無いページのカギ)
8. https://github.com/allgroup-inc/hojo-hq/settings/secrets/actions/new を開く → Name に `GLOW_FB_PAGE_TOKEN`、Secret に7.の値を貼って保存
9. チャットで「登録した」と伝える → つながりを確認し、最初の投稿(あいさつ)を出す

## 動かし方(登録後)
- つながり確認: Actions → glow-sns-post → Run workflow → mode=status
- 今すぐ1本出す: 同じく mode=post
- 止めたいとき: Actions → glow-sns-post → 右上「…」→ Disable workflow

## 人が見るところ
- コメント・DMへの返事は人が行う(自動では返さない)
- 投稿のたびに小柳さんのLINEへ「投稿しました」が届く。失敗したときも届く
- 新しい数字や事例を足すときは、出典を照合してから `scripts/glow_sns_build.py` の `POSTS` に足して作り直す
