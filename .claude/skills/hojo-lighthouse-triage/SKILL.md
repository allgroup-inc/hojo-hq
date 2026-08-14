---
name: hojo-lighthouse-triage
description: "GitHub ActionsのLighthouseワークフローの失敗通知・自動起票Issueに対応するとき、またはPerformance/Accessibility/Best Practices/SEOのスコア改善を頼まれたときに必ず使う。Claude Code環境からは本番URLやGitHub Actionsのアーティファクトに直接アクセスできないことが多いため、ローカル再現でスコアを実測してから原因を特定・修正する手順を提供する。"
---

# Lighthouse失敗の原因特定(ローカル再現で実測する)

> ALLGROUP共通スキル(hojo-hqを本店として複数リポジトリで共有)。このリポジトリに
> Lighthouse CIワークフロー(`.github/workflows/`配下、`treosh/lighthouse-ci-action`等)
> が無ければ、このスキルの出番はない。

Lighthouseの失敗通知は、原文照合と同じで憶測でCSSやJSを直しても当たるとは限らない。
**必ず実測してから直し、直したあとも実測で確認する。**

## なぜローカル再現が要るか

Claude Codeのサンドボックス環境はネットワークegressが制限されていることが多い:

- 本番URL(GitHub Pages等)への直接アクセス → `EGRESS_BLOCKED`
- GitHub ActionsのLighthouseアーティファクト(Azure Blob Storage等) → `403`

つまり「本番の数値を直接見る」「アーティファクトをダウンロードして詳細を見る」の
どちらも塞がれていることがある。かわりに**ローカルに同じ環境を再現して自分で計測する**。

## 手順

### 1. まず失敗の実際の値を確認する

GitHub Actionsのジョブログ(`mcp__github__get_job_logs`、`failed_only: true`)を読む。
`categories.performance failure for minScore assertion` のような行に、実測値と
複数回計測の全値(`all values: 0.49, 0.85, 0.84` 等)が出る。ここでどのカテゴリが
落ちているか・どれくらいブレているかを先に把握する。

### 2. ローカルで対象ページを配信する

```bash
nohup python3 -m http.server 8931 --directory site > /tmp/.../httpserver.log 2>&1 & disown
```

配信ディレクトリはこのリポジトリの静的サイトのルート(例: `site/`)に合わせる。
`&`だけだとツール呼び出しの区切りで死ぬことがあるため `disown` を付ける。

### 3. Lighthouse本体を用意する

環境にNode.jsとChromiumが事前インストール済みなら(npm registryはegressの
許可リストに入っていることが多いので `npm install` 自体は通る)、以下で十分:

```bash
npm install lighthouse --no-save   # scratchpad等の作業ディレクトリで実行
find /opt/pw-browsers -iname "*chrome*" -type f 2>/dev/null   # 実行パスを確認(環境で変わる)
```

`/opt/pw-browsers` に見つからなければ、Playwright/Puppeteerのキャッシュパス
(`~/.cache/ms-playwright`等)や `which chromium` も試す。

### 4. 計測する(Chromeの実行パスを渡すのが必須)

```bash
CHROME_PATH=<手順3で見つけたパス> \
  node_modules/.bin/lighthouse http://127.0.0.1:8931/index.html \
  --output=json --output-path=./lh-report.json \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
  --only-categories=performance,accessibility,best-practices,seo \
  --quiet
```

CIの多くは複数回計測して中央値/最小値をとる(`lighthouse-ci-action`の`runs: 3`等)。
**1回だけで判断しない。** サンドボックス自体もCPU負荷でスコアがブレることがある
(実際に0.99が3回続いた後0.8が1回だけ出た例がある)。怪しい結果が出たら
3回前後計測して外れ値かどうか見る。

### 5. スコアの内訳を読む

`categories.*.score` だけでなく、`audits` から次を見ると原因の当たりが速い:

- `total-blocking-time` / `mainthread-work-breakdown` — メインスレッドが何(Style&Layout/
  Script Evaluation等)に時間を使っているか
- `long-tasks` — 個別の長いタスクとその発生タイミング
- `unminified-javascript` / `unused-javascript` — JS側の無駄
- `color-contrast` / `landmark-one-main` 等 — Accessibility個別項目

### 6. 仮説→検証を実測で繰り返す

疑わしいCSS/JSを一時的に変更した**コピー**(本体は触らない)を作り、別ポートで
配信して計測し直す。効果があれば数値で確認できる。

実例(hojo-hq、2026-08-09): `text-wrap:balance` がページ内に6回出現する見出し
(h2)に付いていたケースでは、その1プロパティを外すだけで Performance 0.83→0.98、
TBT(Total Blocking Time)640ms→40msまで改善した。`text-wrap:balance`や
`word-break:auto-phrase`のような「見た目は良いが複数回のレイアウト計算を
強制するCSSプロパティ」が、ページ内で繰り返し使われる要素に効いている時に
起きやすい典型例。

### 7. 実ファイルに適用してから、もう一度実測で確認する

コピーではなく本体を直したら、同じ手順でもう一度計測し、「直った」を実測で
確認してからコミットする。ここを省略しない。

## 気をつけること

- **閾値設定(`lighthouserc.json`等)自体を緩める提案は、まず改善を尽くしてから**。
  このリポジトリで品質基準が意図的に高く設定されている場合、閾値の変更は
  そのリポジトリの意思決定ルール(決裁者・承認フロー)に従う
- 一部ドメインがこの環境から`EGRESS_BLOCKED`/`403`になることがある(原文照合系の
  スキルでも同じ制約に当たることがある)。これはコードの問題ではなく環境の
  ネットワークポリシーなので、慌てて直そうとしない
- ローカル再現はあくまで**この対話環境用のワークアラウンド**。本番のGitHub Actions
  ランナーは通常インターネットアクセスを持つので、CI自体は正常に動いている
  (=失敗は環境起因ではなく実サイトのスコアの問題)
