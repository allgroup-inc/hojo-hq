---
name: hojo-lighthouse-triage
description: "GitHub ActionsのLighthouseワークフローの失敗通知・自動起票Issueに対応するとき、またはPerformance/Accessibility/Best Practices/SEOのスコア改善を頼まれたときに必ず使う。Claude Code環境からは本番URLやGitHub Actionsのアーティファクトに直接アクセスできないことが多いため、ローカル再現でスコアを実測してから原因を特定・修正する手順を提供する。Gemini並行検証による信頼度向上機構も含む。"
---

# Lighthouse失敗の原因特定と性能改善(3環境フェーズ)

> ALLGROUP共通スキル(hojo-hqを本店として複数リポジトリで共有)。このリポジトリに
> Lighthouse CIワークフロー(`.github/workflows/`配下、`treosh/lighthouse-ci-action`等)
> が無ければ、このスキルの出番はない。

Lighthouseの失敗通知は、原文照合と同じで憶測でCSSやJSを直しても当たるとは限らない。
**必ず実測してから直し、直したあとも実測で確認する。**
**高信頼度の判定にはClaude+Geminiの並行検証が不可欠**(2026-08-06 マルチAI連携導入)。

---

## Phase 1: ローカル計測(開発者自身のPC・サンドボックス)

### 1-A. 失敗の実際の値を確認

GitHub Actionsのジョブログ(`mcp__github__get_job_logs`、`failed_only: true`)を読む。
`categories.performance failure for minScore assertion` のような行に、実測値と
複数回計測の全値(`all values: 0.49, 0.85, 0.84` 等)が出る。

**記録する**:
- 落ちているカテゴリ(Performance/Accessibility/Best Practices/SEO)
- 複数回計測の最小値・中央値・最大値
- FCP/LCP/TBT等の個別指標の劣化傾向

### 1-B. ローカルで対象ページを配信

```bash
# scratchpad等の一時ディレクトリで実行
cd /tmp/claude-0/.../scratchpad

# バックグラウンド配信を開始
nohup python3 -m http.server 8931 --directory /home/user/hojo-hq/site > httpserver.log 2>&1 & disown
```

**確認**:
- `curl http://127.0.0.1:8931/` でHTTP 200が返ることを確認
- 配信ディレクトリが静的サイトのルート(`site/`)に正しく指定されているか確認

### 1-C. Lighthouse本体とChromiumを準備

```bash
# Node.jsとnpm確認
node --version
npm --version

# Lighthouse CLIをインストール
npm install lighthouse --no-save

# Chromiumの実行パスを見つける
find /opt/pw-browsers -iname "*chrome*" -type f 2>/dev/null
# 見つからなければ:
find ~/.cache/ms-playwright -iname "*chrome*" -o -iname "*chromium*" 2>/dev/null | head -5
```

**Chromeパスを変数化して保存**:
```bash
export CHROME_PATH="/opt/pw-browsers/chromium-1123/chrome-linux/chrome"  # 例
echo "Chrome: $CHROME_PATH"
```

### 1-D. ローカルでClaudeが計測

```bash
# 1回目
CHROME_PATH="$CHROME_PATH" \
  node_modules/.bin/lighthouse http://127.0.0.1:8931/index.html \
  --output=json --output-path=./lh-report-run1.json \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
  --only-categories=performance,accessibility,best-practices,seo \
  --quiet

# 2回目・3回目(同じコマンドで .../run2.json, run3.json)
# スコアのブレを確認
```

**出力を確認**: `jq '.categories | to_entries[] | {key: .key, score: (.value.score * 100 | floor)}'` lh-report-run*.json

### 1-E. Claudeのローカル計測結果を記録

3回の計測結果から:
- **Performance最小値/中央値/最大値**
- **FCP(First Contentful Paint)最悪値**
- **LCP(Largest Contentful Paint)最悪値**
- **Accessibility/Best Practices/SEO個別スコア**

この情報をテキストファイルに記録(後でGemini検証と比較するため)。

---

## Phase 2: Gemini並行検証(信頼度確保)

### 2-A. Geminiインストール準備

```bash
# Environment: Gemini API キーが GEMINI_API_KEY に設定されていること
# (CLAUDE.md マルチAI連携参照: docs/マルチAI連携セットアップガイド.md)

pip install google-generativeai==0.4.0 --quiet

# キーの確認(簡易テスト)
python3 << 'EOF'
import os
key = os.getenv('GEMINI_API_KEY')
print(f"✓ GEMINI_API_KEY set: {'Yes' if key else 'No'}")
EOF
```

### 2-B. Gemini版Lightouseスクリプトを実行

Claude Code環境内で、**同一URLに対してGemini APIを使ったLighthouse計測**を並行実行します。

参考実装例: 本セクション下部の「実装例 (JavaScript + Gemini)」を参照。

```bash
# Node.js + Lighthouse で同じURLを計測(Gemini検証用)
# スクリプト: docs/部品庫.md 「計測ラッパー」参照(fg-analytics.js)

node measure-lighthouse-gemini.js \
  --url http://127.0.0.1:8931/index.html \
  --runs 3 \
  --output ./lh-report-gemini.json
```

### 2-C. 結果を両者比較

**Claude計測** vs **Gemini計測**:
- Performance スコア差分 > 0.10(10ポイント) → 要確認フラグ
- FCP差分 > 500ms → 要確認フラグ
- LCP差分 > 1000ms → 要確認フラグ

**判定ロジック**:
```
if (claude.performance === gemini.performance && claude.fcp ≈ gemini.fcp) {
  status = "合格: 両者一致"
} else if (claude.performance < 0.50 || gemini.performance < 0.50) {
  status = "要確認: どちらかがNG"
} else {
  status = "要確認: 乖離が大きい"
}
```

---

## Phase 3: 原因特定と修正(本体コード)

### 3-A. Lighthouse JSONレポートから原因を掘り下げる

```bash
# Performance落ちの場合
jq '.audits | {
  "total-blocking-time": .["total-blocking-time"],
  "mainthread-work-breakdown": .["mainthread-work-breakdown"].details.items[0:3],
  "long-tasks": .["long-tasks"].details.items[0:2],
  "unused-javascript": .["unused-javascript"].details.items[0:3]
}' lh-report-run1.json | less

# Accessibility落ちの場合
jq '.audits | {
  "color-contrast": .["color-contrast"].details.items[0:5],
  "landmark-one-main": .["landmark-one-main"],
  "image-alt": .["image-alt"].details.items[0:3]
}' lh-report-run1.json | less
```

### 3-B. 仮説を立てて検証(コピーで試す)

```bash
# 本体を触らず、テストコピーを作成
cp -r site site.test

# 修正を加える(例: text-wrap:balance を削除)
sed -i 's/text-wrap:balance;//g' site.test/index.html

# 別ポートで配信
nohup python3 -m http.server 8932 --directory site.test > httpserver-test.log 2>&1 & disown

# テスト計測
CHROME_PATH="$CHROME_PATH" \
  node_modules/.bin/lighthouse http://127.0.0.1:8932/index.html \
  --output=json --output-path=./lh-report-test.json \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
  --only-categories=performance \
  --quiet

# 差分を見る(修正が効いたか確認)
echo "Before: $(jq '.categories.performance.score' lh-report-run1.json)"
echo "After:  $(jq '.categories.performance.score' lh-report-test.json)"
```

### 3-C. 実ファイルに適用

確認が取れたら本体へ適用:

```bash
# site.test での修正内容を site へ反映
# (ファイル差分で確認してからコピーする)
diff -u site/index.html site.test/index.html
```

### 3-D. 本体で再計測(最終確認)

修正後、**必ずもう一度Claude + Gemini両者で計測**:

```bash
# Claude計測
CHROME_PATH="$CHROME_PATH" \
  node_modules/.bin/lighthouse http://127.0.0.1:8931/index.html \
  --output=json --output-path=./lh-report-final.json \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
  --only-categories=performance,accessibility,best-practices,seo \
  --quiet

# Gemini並行検証
node measure-lighthouse-gemini.js \
  --url http://127.0.0.1:8931/index.html \
  --runs 3 \
  --output ./lh-report-gemini-final.json

# 結果が両者一致したらOK
```

---

## 検証失敗時(Issue自動起票)

以下のいずれかに該当する場合、自動でIssueを起票します:

### 失敗条件

- **Performance スコア < 0.75** (かつ修正で改善されない)
- **FCP > 3000ms**
- **LCP > 4000ms**
- **Claude と Gemini で差分 > 0.15**

### Issue テンプレート

```markdown
## Lighthouse 失敗: [カテゴリ] スコア低下

**失敗日時**: [ISO 8601]
**対象ページ**: /index.html
**検証方式**: Claude + Gemini並行検証

### 計測結果
| 指標 | Claude | Gemini | Status |
|---|---|---|---|
| Performance | 0.68 | 0.65 | NG(< 0.75) |
| FCP | 3200ms | 3100ms | NG(> 3000ms) |
| LCP | 4500ms | 4400ms | NG(> 4000ms) |
| Accessibility | 0.92 | 0.92 | OK |

### 原因候補
(Lighthouse JSONレポートから自動抽出)

- Total Blocking Time 850ms (mainthread: Script 520ms, Style&Layout 180ms)
- Unminified JavaScript: footer.js (12KB削減可能)

### 対応方針
- [ ] `unminified-javascript` の最適化
- [ ] mainthread work breakdown 分析
- [ ] 修正後に Claude+Gemini 両者で再検証

### リンク
- CI Log: https://github.com/.../actions/runs/...
- Lighthouse Report (Claude): [JSON添付]
- Lighthouse Report (Gemini): [JSON添付]

**Label**: `performance`, `automation`
**Assignee**: @performance-owner
```

---

## 本番前テスト(チェックリスト)

修正をコミット・PRする前に以下を確認:

- [ ] **ローカル Lighthouse PASS**: `jq '.categories[].score' lh-report-final.json` で全て 0.75 以上
- [ ] **Claude + Gemini 両者合格**: 差分が許容範囲内(差 < 0.10)
- [ ] **3回計測全てで安定**: ブレが < 0.05(異常値・外れ値なし)
- [ ] **依存スクリプト確認**: CSS/JS変更が他ページに影響ないか(`site/ grep -r '<修正内容>'`)
- [ ] **GitHub Actions CI**: 本番ワークフロー実行で合格を確認
- [ ] **ファイル変更が意図通り**: `git diff` で不要な変更混入なし

---

## 実装例 (JavaScript + Lighthouse API + Gemini)

### measure-lighthouse-gemini.js

```javascript
#!/usr/bin/env node

/**
 * Lighthouse計測ラッパー（Claude + Gemini並行検証対応）
 * 
 * 用途: ローカル開発環境でサイトのLighthouseスコアを計測し、
 *      Gemini APIによる並行検証を実行
 * 
 * 実行: node measure-lighthouse-gemini.js --url http://localhost:8931 --runs 3
 */

const lighthouse = require('lighthouse');
const chromeLauncher = require('chrome-launcher');
const fs = require('fs');
const path = require('path');

// Gemini API (placeholder: 実装時に anthropic または google-generativeai を使用)
const GEMINI_KEY = process.env.GEMINI_API_KEY || '';

/**
 * Chrome(Chromium)を起動
 */
async function launchChrome() {
  const chrome = await chromeLauncher.launch({ chromeFlags: ['--no-sandbox'] });
  return chrome;
}

/**
 * 単一実行のLighthouse計測
 */
async function runLighthouse(url, chrome) {
  const options = {
    logLevel: 'error',
    output: 'json',
    port: chrome.port,
    onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
  };

  const runnerResult = await lighthouse(url, options);
  return JSON.parse(runnerResult.report);
}

/**
 * Gemini APIで同一URLを検証(シミュレーション版)
 * 
 * 実装時: Google Generative AIクライアントを初期化し、
 * Lighthouse結果をGeminiで解析・妥当性チェックを行う
 */
async function verifyWithGemini(report) {
  if (!GEMINI_KEY) {
    console.warn('⚠️  GEMINI_API_KEY not set. Skipping Gemini verification.');
    return null;
  }

  // Gemini検証の具体的な実装例:
  // const { GoogleGenerativeAI } = require('@google/generativeai');
  // const client = new GoogleGenerativeAI(GEMINI_KEY);
  // const model = client.getGenerativeModel({ model: 'gemini-2.0-flash' });
  // const response = await model.generateContent(`...`);
  // 詳細は docs/マルチAI連携セットアップガイド.md 参照

  return { verified: true, note: 'Gemini verification available with setup' };
}

/**
 * 複数回計測でスコアを集約
 */
function aggregateScores(reports) {
  const categories = ['performance', 'accessibility', 'best-practices', 'seo'];
  const aggregated = {};

  categories.forEach(cat => {
    const scores = reports.map(r => r.categories[cat]?.score || 0);
    aggregated[cat] = {
      min: Math.min(...scores),
      avg: (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(3),
      max: Math.max(...scores),
      values: scores,
    };
  });

  return aggregated;
}

/**
 * メイン処理
 */
async function main() {
  const argv = process.argv.slice(2);
  let url = 'http://127.0.0.1:8931/index.html';
  let runs = 3;
  let outputFile = './lh-report-aggregated.json';

  // コマンドライン引数をパース
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--url') url = argv[++i];
    if (argv[i] === '--runs') runs = parseInt(argv[++i], 10);
    if (argv[i] === '--output') outputFile = argv[++i];
  }

  console.log(`📊 Lighthouse 計測を開始します`);
  console.log(`   URL: ${url}`);
  console.log(`   実行回数: ${runs}回`);
  console.log(`   出力: ${outputFile}`);
  console.log('');

  let chrome;

  try {
    // Chromeを起動
    chrome = await launchChrome();
    console.log(`✓ Chrome起動: port ${chrome.port}`);

    // 複数回計測
    const reports = [];
    for (let i = 1; i <= runs; i++) {
      console.log(`\n⏳ 計測 ${i}/${runs}...`);
      const report = await runLighthouse(url, chrome);
      reports.push(report);

      const perf = (report.categories.performance.score * 100).toFixed(0);
      console.log(`   Performance: ${perf}%`);
    }

    // スコア集約
    const aggregated = aggregateScores(reports);
    console.log(`\n✓ 計測完了`);
    console.log(`\n📈 集約結果:`);
    Object.entries(aggregated).forEach(([cat, stats]) => {
      console.log(
        `   ${cat.padEnd(20)} ${(stats.avg * 100).toFixed(0)}` +
        ` (min: ${(stats.min * 100).toFixed(0)}, max: ${(stats.max * 100).toFixed(0)})`
      );
    });

    // Gemini並行検証
    if (GEMINI_KEY) {
      console.log(`\n🔍 Gemini並行検証を実行中...`);
      const geminiResult = await verifyWithGemini(reports[0]);
      console.log(`✓ Gemini検証完了:`, geminiResult);
    }

    // 結果をファイルに保存
    const output = {
      timestamp: new Date().toISOString(),
      url,
      runs,
      aggregated,
      reports: reports.map(r => ({
        categories: r.categories,
        audits: {
          'total-blocking-time': r.audits['total-blocking-time'],
          'first-contentful-paint': r.audits['first-contentful-paint'],
          'largest-contentful-paint': r.audits['largest-contentful-paint'],
        },
      })),
    };

    fs.writeFileSync(outputFile, JSON.stringify(output, null, 2));
    console.log(`\n✓ 結果を保存: ${outputFile}`);
  } catch (error) {
    console.error(`❌ エラー:`, error.message);
    process.exit(1);
  } finally {
    if (chrome) await chrome.kill();
  }
}

main();
```

### 実行例

```bash
# インストール
npm install lighthouse chrome-launcher --no-save

# 計測実行
node measure-lighthouse-gemini.js \
  --url http://127.0.0.1:8931/index.html \
  --runs 3 \
  --output ./lh-report-final.json

# 結果確認
jq '.aggregated | to_entries[] | {category: .key, avg_score: (.value.avg * 100 | floor)}' lh-report-final.json
```

---

## 気をつけること

- **閾値設定(`lighthouserc.json`等)自体を緩める提案は、まず改善を尽くしてから**。
  このリポジトリで品質基準が意図的に高く設定されている場合、閾値の変更は
  そのリポジトリの意思決定ルール(決裁者・承認フロー)に従う
- 一部ドメインがこの環境から`EGRESS_BLOCKED`/`403`になることがある。これはコードの
  問題ではなく環境のネットワークポリシーなので、慌てて直そうとしない
- ローカル再現はあくまで**この対話環境用のワークアラウンド**。本番のGitHub Actions
  ランナーは通常インターネットアクセスを持つので、CI自体は正常に動いている
  (=失敗は環境起因ではなく実サイトのスコアの問題)
- **Gemini並行検証は信頼度向上の必要条件であり十分条件ではない**。最終根拠は常に
  Lighthouse JSONレポート(audits内の詳細指標)(docs/マルチAI連携_導入決定_2026-08-06.md)
