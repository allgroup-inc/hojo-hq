# Facebook運用設計 — SNS部(ヒロメさん)

対象: Facebookページ「沖縄企業のミカタ」(要開設・タスク参照)
ねらい: **沖縄の経営者層はFacebook利用率が高い**(40〜60代経営者の主要SNS)。B2Bの本命チャネルとしてInstagramと両輪で運用する。

## 1. セットアップ(初回のみ・人間side)
1. Meta Business Suite(business.facebook.com)で Facebookページ作成
   - ページ名: 沖縄企業のミカタ / カテゴリ: 情報サイト
   - プロフィール画像: GLOWロゴ / カバー: posts/images/01_launch.png を流用可
2. 自己紹介欄・ボタン: 「詳細はこちら」ボタン → **https://allgroup-inc.github.io/hojo-hq/go/fb/**
   (lin.ee直貼り禁止。go/fb はLINE友だち追加へ転送・経路計測付き・生成済み)
3. InstagramアカウントとBusiness Suiteで接続(同時投稿を有効化)

## 2. 投稿運用(IGと同時・追加作業ほぼゼロ)
- **Meta Business Suiteの「投稿を作成」で Facebook + Instagram を同時選択**して投稿。
  素材はIGと同じ(posts/images/*.png + posts/launch/*.mdのキャプション)
- **FBだけの違い**: キャプション内のURLがタップできる → IG用の
  「プロフィールのリンクからどうぞ」の行を、FB版ではURL直書きに差し替える:
  ```
  https://allgroup-inc.github.io/hojo-hq/?utm_source=facebook&utm_medium=social&utm_campaign=launch
  ```
- 頻度: IGのカレンダー(docs/SNS投稿カレンダー.md)と同一。ストーリーズはIGのみでよい
- 締切3層ルール適用(SNSで告知するのは締切30日以上先の制度のみ)

## 3. その他との連携マップ(どこが自動でどこが手動か)

| 発信面 | ソース | 更新 |
|---|---|---|
| サイト(制度データ/診断) | data/subsidies.json | 自動(1日4回) |
| IG/FBフィード素材 | posts/launch + posts/images | 自動生成(投稿は手動・同時投稿) |
| IGストーリーズ | posts/images/story_alert.png | 自動生成(投稿は手動) |
| LINE配信 | posts/line/alerts_latest.md | 自動生成(配信は月/木に手動) |
| 経路計測 | /go/(ig・fb・site・shindan) + UTM | 自動(Plausible) |

## 4. 計測(週次でアカリさんへ)
- Plausible: `line_redirect` × channel=fb(ページ→LINE) / UTM facebook(ページ→サイト)
- ページフォロワー数・リーチ・リンククリック(Meta Business Suiteインサイト)
- 判断基準: 8週運用してIG比で登録寄与が高ければFB広告(小額)を小柳さんへ提案

## 5. 禁止事項(共通)
- 誇大表現・検証部未通過データの投稿・lin.ee直貼り・締切7日未満の制度を煽る投稿
