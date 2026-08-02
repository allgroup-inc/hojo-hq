# SNS投稿 自動下書き生成テンプレ(Instagram/X対応)

ネタ帳(CSV)にトピックを書き溜めておくだけで、**1週間分の投稿下書き**を
AIがまとめて生成するテンプレートです。ブランドの口調・NGワードを設定
ファイルで固定できるので、生成のたびにトーンがブレません。

```
config/brand.yml(ブランド設定: 口調・ターゲット・NGワード)
input/topics.csv(ネタ帳: 投稿したいトピックを書き溜める)
   │
   ▼  毎週金曜 10:00 JST(GitHub Actions)or 手動実行
Claude APIが各トピックから
  ・キャプション(Instagram用)
  ・短文版(X用)
  ・ハッシュタグ
  ・画像のアイデア
を生成 → output/ にCSVとプレビューMarkdownを保存
   │
   ▼
人間が確認・微修正して投稿(そのままコピペできる形式)
```

**「生成→無確認で自動投稿」はあえてしない設計です。** SNSアカウントの
信頼は一度の事故で失われるため、最終確認は人間が行う前提にしています
(確認済み下書きの予約投稿は各SNSの公式予約機能をご利用ください)。

## セットアップ(約10分)

1. このテンプレート一式を自分のGitHubリポジトリ(Private推奨)にコピー
2. Settings → Secrets and variables → Actions に `ANTHROPIC_API_KEY` を登録
3. Settings → Actions → General → Workflow permissions を
   「Read and write permissions」に変更
4. `config/brand.yml` を自分のブランドに合わせて編集
5. `input/topics.csv` にネタを書く
6. Actionsタブ → `generate-posts` → Run workflow

`output/posts_日付.md`(プレビュー用)と `output/posts_日付.csv`
(スプレッドシート管理用)が生成されます。

## まず動きを見たい(APIキーなしでOK)

```
pip install -r requirements.txt
python scripts/generate_posts.py --offline
```

## ネタ帳の書き方(input/topics.csv)

```csv
topic,note,status
新商品〇〇の紹介,9月1日発売。価格1980円。限定100個,
お客様の声を紹介,先週いただった「使いやすい」というレビュー,
よくある質問シリーズ,返品はできますか?という質問への回答,done
```

- `topic`: 投稿のテーマ(1行で)
- `note`: 盛り込みたい事実・数字・背景(ここが具体的なほど良い下書きになる)
- `status`: `done` と書いた行はスキップされます(生成済み管理用)

生成が成功した行には自動で `done` が記入されるので、ネタ帳は
「追記していくだけ」で使えます。

## ブランド設定(config/brand.yml)

```yaml
brand_name: 〇〇商店
audience: 30〜40代の子育て世帯
tone: 親しみやすく、でも誠実に。絵文字は1投稿2個まで
persona: 店主が自分の言葉で話している感じ
ng_words:            # 使ってはいけない表現(景表法・薬機法対策にも)
  - 日本一
  - 絶対
  - 必ず痩せる
base_hashtags:       # 毎回付ける固定ハッシュタグ
  - "#〇〇商店"
cta: プロフィールのリンクからどうぞ
max_posts_per_run: 7
```

NGワードは生成後にプログラム側でも再チェックし、含まれていた場合は
その投稿に「要修正」フラグが付きます(二重の安全装置)。

## カスタマイズ

- **生成する媒体を変える**: `scripts/generate_posts.py` の `POST_SCHEMA` と
  プロンプトを編集(例: X専用にする、TikTokの台本形式にする)
- **実行スケジュール**: `.github/workflows/generate-posts.yml` の cron(UTC)
- **モデル変更**: ワークフローの `ANTHROPIC_MODEL` コメントを外すと低コスト化

## 費用目安

1投稿あたり数円。週7投稿の生成で月100〜200円程度。

## ライセンス

購入者本人の商用利用OK(自社・自店舗のSNS運用、および運用代行業での
クライアントアカウント運用にも利用可)。テンプレート自体の再配布・再販売
は不可。詳細は LICENSE.md。
