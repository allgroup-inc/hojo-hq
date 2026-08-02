# セットアップガイド(所要 約15分)

プログラミング経験がなくても、以下の手順どおりに進めれば動きます。

## 手順1: 自分のリポジトリを作る

1. GitHubにログインし、右上「+」→「New repository」
2. リポジトリ名は自由(例: `my-info-site`)。**Public** を選択
   (Privateでも動きますが、GitHub Pagesの無料公開はPublicが必要です)
3. 「Create repository」をクリック
4. このテンプレート一式(購入時にダウンロードしたZIPの中身)を
   リポジトリにアップロードします。
   - 簡単な方法: リポジトリページの「uploading an existing file」リンクから
     フォルダごとドラッグ&ドロップ
   - **`.github` フォルダも忘れずに**(隠しフォルダです。アップロード画面で
     見えない場合は、git コマンドでのpushをおすすめします)

## 手順2: Anthropic APIキーを取得して登録

1. https://platform.claude.com/ でアカウント作成
2. 「API Keys」からキーを発行(`sk-ant-...` で始まる文字列)
3. クレジットを購入(最低$5から。まずは$5で十分です)
4. GitHubリポジトリの Settings → Secrets and variables → Actions →
   「New repository secret」
5. Name: `ANTHROPIC_API_KEY` / Secret: 発行したキー を入力して保存

## 手順3: 情報源を設定する

`config/sources.yml` を編集します(GitHub上で鉛筆アイコンから直接編集可能)。

```yaml
sources:
  - id: my-news          # 英数字とハイフンのみ
    name: 〇〇ニュース     # サイトに表示される出典名
    type: rss            # まずはRSSがおすすめ
    url: https://example.com/feed.xml
    enabled: true
```

RSSのURLの見つけ方: 対象サイトで「RSS」のリンクを探すか、
`サイト名 RSS` で検索してください。

> **htmlタイプを使う場合の注意**: 対象サイトの robots.txt と利用規約を必ず
> 確認してください。本テンプレートは robots.txt が取得できない・許可して
> いないページは自動的にスキップします。

## 手順4: GitHub Pagesを有効にする

1. リポジトリの Settings → Pages
2. Source: 「Deploy from a branch」
3. Branch: `main`、フォルダ: `/site` を選択して Save
4. 数分後、`https://<ユーザー名>.github.io/<リポジトリ名>/` で公開されます

## 手順5: 初回実行

1. リポジトリの「Actions」タブを開く
2. 左の「pipeline」を選択 →「Run workflow」→ 緑のボタンをクリック
3. 2〜5分で完了します。緑のチェックがつけば成功
4. 公開URLを開いて、情報が掲載されていることを確認

以後は毎日 朝6時・夜6時(日本時間)に自動実行されます。
実行時刻を変えたい場合は `.github/workflows/pipeline.yml` の cron を編集
してください(UTC表記なので日本時間から9時間引きます)。

## うまくいかないとき

`docs/FAQ.md` を参照してください。
