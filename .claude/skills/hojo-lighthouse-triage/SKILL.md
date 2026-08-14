---
name: hojo-lighthouse-triage
description: "Lighthouseワークフロー(.github/workflows/lighthouse.yml)の失敗通知・自動起票Issueに対応するとき、またはPerformance/Accessibility/Best Practices/SEOのスコア改善を頼まれたときに必ず使う。Claude Code環境からは本番URLやGitHub Actionsのアーティファクトに直接アクセスできないため、ローカル再現でスコアを実測してから原因を特定・修正する手順を提供する。"
---

# Lighthouse失敗の原因特定(ローカル再現で実測する)

Lighthouseの失敗通知は「原文照合」と同じで、憶測でCSSやJSを直しても当たるとは
限らない。**必ず実測してから直し、直したあとも実測で確認する。**

## なぜローカル再現が要るか(このリポジトリ特有の制約)

Claude Codeのこのサンドボックス環境は、ネットワークegressが制限されている:

- 本番URL(`https://allgroup-inc.github.io/hojo-hq/`)への直接アクセス → `EGRESS_BLOCKED`
- GitHub ActionsのLighthouseアーティファクト(`productionresultssa1.blob.core.windows.net`等のAzure Blob Storage) → `403`

つまり「本番の数値を直接見る」「アーティファクトをダウンロードして詳細を見る」の
どちらも塞がれている。かわりに**ローカルに同じ環境を再現して自分で計測する**。

## 手順

### 1. まず失敗の実際の値を確認する

GitHub Actionsのジョブログ(`mcp__github__get_job_logs`、`failed_only: true`)を読む。
`categories.performance failure for minScore assertion` のような行に、実測値と
3回計測の全値(`all values: 0.49, 0.85, 0.84` 等)が出る。ここでどのカテゴリが
落ちているか・どれくらいブレているかを先に把握する。

### 2. ローカルでsite/を配信する

```bash
nohup python3 -m http.server 8931 --directory site > /tmp/.../httpserver.log 2>&1 & disown
```

`&`だけだとツール呼び出しの区切りで死ぬことがあるため `disown` を付ける。

### 3. Lighthouse本体を用意する

このリポジトリの環境には Node.js と Chromium が事前インストール済み(npm registry は
egressの許可リストに入っているので `npm install` 自体は通る)。

```bash
npm install lighthouse --no-save   # scratchpad等の作業ディレクトリで実行
find /opt/pw-browsers -iname "*chrome*" -type f   # 実行パスを確認(バージョンで変わる)
```

### 4. 計測する(CHROME_PATHを渡すのが必須)

```bash
CHROME_PATH=/opt/pw-browsers/chromium-XXXX/chrome-linux/chrome \
  node_modules/.bin/lighthouse http://127.0.0.1:8931/index.html \
  --output=json --output-path=./lh-report.json \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
  --only-categories=performance,accessibility,best-practices,seo \
  --quiet
```

`.github/workflows/lighthouse.yml` の `runs: 3` と同様、**1回だけで判断しない**。
このサンドボックス自体もCPU負荷でスコアがブレる(実際に0.99が3回続いた後
0.8が1回出た例がある)。怪しい結果が出たら3回前後計測して外れ値かどうか見る。

### 5. スコアの内訳を読む

`categories.*.score` だけでなく、`audits` から次を見る。原因の当たりが速い:

- `total-blocking-time` / `mainthread-work-breakdown` — メインスレッドが何(Style&Layout/
  Script Evaluation等)に時間を使っているか
- `long-tasks` — 個別の長いタスクとその発生タイミング
- `unminified-javascript` / `unused-javascript` — JS側の無駄
- `color-contrast` / `landmark-one-main` 等 — Accessibility個別項目

### 6. 仮説→検証を実測で繰り返す

疑わしいCSS/JSを一時的に変更した**コピー**(`site-test/`等、本体は触らない)を作り、
別ポートで配信して計測し直す。効果があれば数値で確認できる。
(例: `text-wrap:balance` がh1,h2両方に付いていたケースでは、h2(ページ内6箇所)を
外すだけで Performance 0.83→0.98、TBT 640ms→40ms まで改善した。これは
`text-wrap:balance`/`word-break:auto-phrase`のような「見た目は良いが複数回の
レイアウト計算を強制するCSSプロパティ」が繰り返し要素に効いている時に起きやすい)

### 7. 実ファイルに適用してから、もう一度実測で確認する

コピーではなく本体(`site/index.html`等)を直したら、同じ手順でもう一度計測し、
「直った」を確認してからコミットする。ここを省略しない。

## 気をつけること

- **閾値(`.github/lighthouserc.json`)自体を緩める提案は、まず改善を尽くしてから**。
  この基準はコメントに「100点基準❷」とあり小柳さんが意図的に設定した高い基準。
  閾値変更は絶対ルール5(品質方針の最終決裁は小柳さん)の対象
- okinawa-ric.jp等、この環境から`EGRESS_BLOCKED`になるドメインが他にもある
  (`hojo-accuracy-check`の原文照合でも同じ制約に当たる)。403/`EGRESS_BLOCKED`は
  コードの問題ではなく環境のネットワークポリシーなので、慌てて直そうとしない
- ローカル再現はあくまで**この対話環境用のワークアラウンド**。本番のGitHub Actions
  ランナーは通常のインターネットアクセスを持つので、cronのLighthouse実行自体は
  正常に動いている(=失敗は環境起因ではなく実サイトのスコアの問題)
