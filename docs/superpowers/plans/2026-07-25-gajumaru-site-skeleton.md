# ガジュマル(仮称)サイト骨格 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AIバックオフィス伴走事業(hojo-hqとは別の新規事業、ブランド名未確定・仮称「ガジュマル」)のマーケティングサイト骨格(トップ/代表者紹介/料金/相談予約/ブログ土台)を、hojo-hqリポジトリ内 `site/gajumaru/` に、既存の `site/fukugiiro/` と同じ静的HTML規約で構築する。

**Architecture:** ビルドステップなしの自己完結型静的HTML(1ページ=1ファイル、`<style>`はページ内に直書き)。`site/fukugiiro/` と同じ規約(CSS変数トークン、`analytics-config.js`、LP検査スクリプト、GitHub Actions CI)を踏襲する。決済・AIレポート生成を伴うセルフサーブ診断商品(Claude API連携)は別プラン(Plan 2)とし、本プランのCTAは「無料相談予約」に一本化する。診断商品は「近日公開」として正直に表示し、存在しない機能を実装したように見せない。

**Tech Stack:** 素のHTML/CSS/JS(フレームワークなし)、Python 3.12(LP検査スクリプト、既存 `scripts/check_lp_fukugiiro.py` と同パターン)、GitHub Actions CI、GitHub Pages配信。

> **実装後の追記(最終レビューで判明した欠陥)**: 本プランは全ページで `/gajumaru/...` の絶対パスをナビゲーション・CTA・`analytics-config.js`読み込みに使うよう指示していたが、これは誤り。このリポジトリのGitHub Pagesはプロジェクトページ(`https://allgroup-inc.github.io/hojo-hq/`)として配信されており、ルート直下ではない。絶対パス `/gajumaru/...` は実際のデプロイ先で404になる。既存の `site/fukugiiro/` が相対パス(`../../index.html` 等)を使っているのは、まさにこの理由による。本プランはこの既存規約を見落としており、Plan 2(セルフサーブ診断商品)では**必ず相対パスを使うこと**。実装済みページは最終レビュー後の修正コミットで相対パスに直した(詳細はgitログ参照)。
>
> **実装後の追記(ブランド名決定)**: 2026-07-25、ブランド名が「ノビシロ」に決定(仮称段階)。本プラン文書内の `site/gajumaru/`・`ガジュマル(仮称)`・`check_lp_gajumaru.py`・`gajumaru-ci.yml` は実装当時の名称としてそのまま残す(履歴record)。実際のディレクトリ・ファイル・表示文言はすべて `nobishiro` / 「ノビシロ」にリネーム済み。AIエージェント人格「ガジュマルくん」(ブランド名とは別)は変更なし。詳細はgitログ(リネームコミット)参照。

## Global Constraints

- 実装場所: `site/gajumaru/`(hojo-hqリポジトリ内。将来ブランド確定後に別リポジトリへ切り出す可能性あり = 設計書 `docs/superpowers/specs/2026-07-25-ai-backoffice-web-funnel-design.md` の未決事項)
- 各HTMLページのサイズ予算: 50KB以下(`site/fukugiiro/` の性能予算を踏襲)
- 必須メタ: `lang="ja"`, viewport, `<title>`, `name="description"`
- 禁止表現(守り部ゲート、誇大な断定表現の禁止 — CLAUDE.md「正確性最優先」原則の踏襲): `業界最安`, `絶対`, `100%削減`, `必ず成功`, `誰でも儲かる`, `確実に安くなる`, `保証します`
- 料金: ライト 80,000円〜 / スタンダード 150,000円〜 / プロ 300,000円〜(月額)。セルフサーブ診断商品 9,800〜19,800円は本プランでは「近日公開」表示のみ(決済機能はPlan 2)
- 人物表記: 経営伴走者は「カチカクくん」(実体はたかしくん/GLOWだが、サイト上では実名を出さない)。AIエージェント人格は「ガジュマルくん」
- 配色トークン(仮): `--gj-primary:#2F6B4F`(深緑・ガジュマルの葉)/ `--gj-accent:#D98E2B`(琥珀)/ `--gj-bg:#FAF7F0` / `--gj-ink:#1F2A2E` / `--gj-muted:#5C6B70` / `--gj-line:#E4DCC9` / `--gj-card:#ffffff`。最終ブランドカラーは小柳さんの決裁待ち
- 画像アセットは今回のスコープ外。ロゴはCSSのみのワードマーク(画像ファイルを作らない)
- 相場データ(「業界相場は月20〜50万円程度」等)は断定せず「一般的に〜と言われています」等の柔らかい表現にする(守り部ルール: 不明時は断定しない)

---

## File Structure

```
site/gajumaru/
  index.html              # トップ(ハブLP)
  about/index.html        # 代表者・チーム紹介
  pricing/index.html      # 料金ページ
  contact/index.html      # 相談予約ページ
  blog/index.html          # ブログ一覧(SEO記事群の土台)
  blog/kihi-kosuto-sakugen/index.html  # サンプル記事(業種別・課題別記事の型)
  analytics-config.js     # 計測設定(Plausible。アカウント未作成のためprovider:nullで開始)
scripts/
  check_lp_gajumaru.py    # LP検査(サイズ予算・禁止表現・基本要件)
.github/workflows/
  gajumaru-ci.yml          # site/gajumaru/** 変更時にcheck_lp_gajumaru.pyを実行
```

---

### Task 1: LP検査スクリプトの作成(先にテスト側を作る)

**Files:**
- Create: `scripts/check_lp_gajumaru.py`

**Interfaces:**
- Consumes: なし(独立スクリプト)
- Produces: CLI実行可能スクリプト。`site/gajumaru/**/*.html` を検査し、エラーがあれば非ゼロ終了。後続タスクの各ページ作成後、このスクリプトを実行して合否を確認する

- [ ] **Step 1: `scripts/check_lp_gajumaru.py` を作成**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ガジュマル(仮称)サイト LP検査(CI用)— 性能予算と禁止表現をコードで守る
- サイズ予算: 各ページ 50KB以下
- 禁止表現: 誇大な断定表現の混入チェック(守り部ゲート)
- 基本要件: lang=ja / viewport / title / description の存在
"""
import glob
import os
import re
import sys

BASE = os.path.join(os.path.dirname(__file__), "..")
SITE_DIR = os.path.join(BASE, "site", "gajumaru")
SITE_GLOB = os.path.join(SITE_DIR, "**", "*.html")
SIZE_BUDGET = 50 * 1024

FORBIDDEN = [
    "業界最安", "絶対", "100%削減", "必ず成功",
    "誰でも儲かる", "確実に安くなる", "保証します",
]


def main():
    pages = sorted(set(glob.glob(SITE_GLOB, recursive=True)))
    if not pages:
        print(f"[ERROR] {SITE_DIR} に検査対象のHTMLがない")
        sys.exit(1)

    errors = []
    for path in pages:
        rel = os.path.relpath(path, BASE)
        size = os.path.getsize(path)
        if size > SIZE_BUDGET:
            errors.append(f"{rel}: サイズ予算超過 {size}B > {SIZE_BUDGET}B")
        html = open(path, encoding="utf-8").read()
        # 禁止表現の検査対象は「利用者に見える文言」のみ。CSS/JSを除外する
        visible = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
        for word in FORBIDDEN:
            if word in visible:
                errors.append(f"{rel}: 禁止表現『{word}』(マモリさんゲート)")
        for req, label in [
            ('lang="ja"', "lang属性"),
            ("viewport", "viewportメタ"),
            ("<title>", "title"),
            ('name="description"', "description"),
        ]:
            if req not in html:
                errors.append(f"{rel}: 基本要件欠落 {label}")

    for e in errors:
        print(f"[ERROR] {e}")
    print(f"サイト検査完了: {len(pages)}ページ / エラー {len(errors)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 実行して失敗することを確認(site/gajumaru/ がまだ存在しないため)**

Run: `python3 scripts/check_lp_gajumaru.py`
Expected: `[ERROR] .../site/gajumaru に検査対象のHTMLがない` と表示され、終了コード1

- [ ] **Step 3: コミット**

```bash
git add scripts/check_lp_gajumaru.py
git commit -m "test(gajumaru): サイトLP検査スクリプトを追加(まだ対象ページなし)"
```

---

### Task 2: analytics-config.js の作成

**Files:**
- Create: `site/gajumaru/analytics-config.js`

**Interfaces:**
- Consumes: なし
- Produces: `window.GJ_ANALYTICS`(`{provider: string|null, domain: string|null}`)、`window.GJ_CONTACT_EMAIL`(string)。後続タスクの各HTMLページがこのファイルを `<script src="/gajumaru/analytics-config.js"></script>`(相対パスはページの深さに応じて調整)で読み込み、値を参照する

- [ ] **Step 1: ディレクトリを作成し `analytics-config.js` を書く**

```javascript
/* ガジュマル(仮称)サイト 計測設定(1箇所)
 * provider は現時点で未契約のため null。Plausibleアカウント作成後に
 * fukugiiro/analytics-config.js と同じ形式で値を入れる。
 */
window.GJ_ANALYTICS = { provider: null, domain: null };
/* 相談予約の受付先。予約ツール未導入のため当面はmailto。 */
window.GJ_CONTACT_EMAIL = "contact@example.com";
```

- [ ] **Step 2: Node で構文エラーがないことを確認**

Run: `node -e "require('./site/gajumaru/analytics-config.js'); console.log(typeof window)"`
Expected: `window` が未定義エラーになる場合は `node --check site/gajumaru/analytics-config.js` に切り替えて構文チェックのみ行う

Run: `node --check site/gajumaru/analytics-config.js`
Expected: 何も出力されず終了コード0(構文エラーなし)

- [ ] **Step 3: コミット**

```bash
git add site/gajumaru/analytics-config.js
git commit -m "feat(gajumaru): 計測設定ファイルを追加(provider未設定)"
```

---

### Task 3: トップページ(ハブLP)

**Files:**
- Create: `site/gajumaru/index.html`

**Interfaces:**
- Consumes: `site/gajumaru/analytics-config.js` の `window.GJ_ANALYTICS`
- Produces: ナビゲーションリンク先として `about/`, `pricing/`, `contact/`, `blog/` を参照(後続タスクで作成)

- [ ] **Step 1: `site/gajumaru/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIエージェント経営伴走(仮称) | 物価高でも管理コストを下げ、営業効率を上げる</title>
<meta name="description" content="10年以上の経営実践者とAIチームが伴走する、中小企業向けバックオフィス自動化サービス。相場よりわかりやすく安い定額プランで、良い商品を提供し続けます。">
<link rel="icon" href="data:,">
<style>
:root{
  --gj-primary:#2F6B4F;
  --gj-accent:#D98E2B;
  --gj-ink:#1F2A2E;
  --gj-bg:#FAF7F0;
  --gj-card:#ffffff;
  --gj-muted:#5C6B70;
  --gj-line:#E4DCC9;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--gj-ink);background:var(--gj-bg)}
main{display:block}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
a{color:var(--gj-primary)}
h1,h2{line-height:1.4}
h2{font-size:1.35rem;margin-bottom:.8em;border-left:6px solid var(--gj-accent);padding-left:.5em}
section{padding:44px 0}
.btn{display:inline-block;padding:16px 28px;min-height:44px;background:var(--gj-primary);color:#fff;
  text-align:center;text-decoration:none;border-radius:999px;font-size:1.05rem;font-weight:700}
.btn.ghost{background:transparent;color:var(--gj-primary);border:2px solid var(--gj-primary)}
.btn:active{opacity:.85}
.note{font-size:.85rem;color:var(--gj-muted)}
.hero{background:linear-gradient(180deg,#EFF3E9 0%,var(--gj-bg) 100%);padding:48px 0 40px;text-align:center}
.hero h1{font-size:1.7rem;margin-bottom:.6em}
.hero .sub{margin-bottom:1.6em;color:var(--gj-muted)}
.ctarow{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.pillars{display:grid;gap:14px}
.pillar{background:var(--gj-card);border:1px solid var(--gj-line);border-radius:12px;padding:20px}
.pillar h3{color:var(--gj-primary);margin-bottom:.3em}
table.pricecmp{width:100%;border-collapse:collapse;background:var(--gj-card);border:1px solid var(--gj-line);
  border-radius:12px;overflow:hidden}
table.pricecmp th,table.pricecmp td{padding:12px 14px;border-bottom:1px solid var(--gj-line);text-align:left}
table.pricecmp th{background:#EFF3E9}
.soon{display:inline-block;background:#fff3cd;color:#7a5b00;border-radius:6px;padding:2px 10px;font-size:.8rem}
.siteheader{position:sticky;top:0;z-index:50;background:rgba(250,247,240,.96);backdrop-filter:blur(4px);
  border-bottom:1px solid var(--gj-line);display:flex;align-items:center;justify-content:space-between;
  gap:8px;padding:10px 16px;flex-wrap:wrap}
.siteheader .hlogo{font-weight:800;color:var(--gj-primary);text-decoration:none;font-size:1.05rem}
.siteheader nav{display:flex;gap:4px;flex-wrap:wrap}
.siteheader nav a{font-size:.85rem;color:var(--gj-ink);text-decoration:none;padding:6px 10px;border-radius:6px}
footer{background:var(--gj-ink);color:#e6e6e0;padding:32px 0;font-size:.9rem}
footer a{color:#bcd0c4}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="/gajumaru/">ガジュマル(仮称)</a>
  <nav>
    <a href="/gajumaru/about/">代表者紹介</a>
    <a href="/gajumaru/pricing/">料金</a>
    <a href="/gajumaru/blog/">お役立ち情報</a>
    <a href="/gajumaru/contact/" class="btn" style="padding:6px 14px;font-size:.85rem">無料相談</a>
  </nav>
</header>
<main>
  <section class="hero">
    <div class="wrap">
      <h1>物価高でも、管理コストは下げられる。<br>営業効率は、上げられる。</h1>
      <p class="sub">10年以上の経営実践者とAIエージェントチームが伴走する、中小企業向けバックオフィス自動化サービスです。</p>
      <div class="ctarow">
        <a class="btn" href="/gajumaru/contact/">無料相談を予約する</a>
        <a class="btn ghost" href="/gajumaru/pricing/">料金を見る</a>
      </div>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2>3つの約束</h2>
      <div class="pillars">
        <div class="pillar">
          <h3>安い</h3>
          <p>AIエージェントが運用の大部分を担うから実現できる、人手中心の代行サービスより抑えた価格。</p>
        </div>
        <div class="pillar">
          <h3>わかりやすい</h3>
          <p>「要見積もり」ではなく定額プランを公開。初期費用は原則ゼロ、いつでも解約できます。</p>
        </div>
        <div class="pillar">
          <h3>本物</h3>
          <p>10年以上、経営の現場で実践してきた「カチカクくん」がAIチームと一緒に設計・伴走します。丸投げのAIツールではありません。</p>
        </div>
      </div>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2>料金の目安</h2>
      <table class="pricecmp">
        <tr><th>プラン</th><th>月額目安</th><th>内容</th></tr>
        <tr><td>ライト</td><td>80,000円〜</td><td>定型業務1〜2種類の自動化</td></tr>
        <tr><td>スタンダード</td><td>150,000円〜</td><td>複数業務の自動化+月次レポート+改善提案</td></tr>
        <tr><td>プロ</td><td>300,000円〜</td><td>業務設計から伴走、専任エージェント構築</td></tr>
      </table>
      <p class="note" style="margin-top:10px">一般的にバックオフィス代行の相場は月20〜50万円程度と言われています(自社調べ・要確認)。詳しくは<a href="/gajumaru/pricing/">料金ページ</a>をご覧ください。</p>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2>まずは無料の自己診断から <span class="soon">近日公開</span></h2>
      <p>AIエージェント「ガジュマルくん」が、あなたの会社の管理コストと営業効率の課題を診断するオンラインツールを準備中です。公開まで、まずは無料相談をご利用ください。</p>
      <div class="ctarow" style="margin-top:16px">
        <a class="btn" href="/gajumaru/contact/">無料相談を予約する</a>
      </div>
    </div>
  </section>
</main>
<footer>
  <div class="wrap">
    <p>&copy; 2026 ガジュマル(仮称) — ブランド名は検討中です。</p>
    <p class="note"><a href="/gajumaru/about/">代表者紹介</a> ・ <a href="/gajumaru/pricing/">料金</a> ・ <a href="/gajumaru/blog/">お役立ち情報</a></p>
  </div>
</footer>
<script src="/gajumaru/analytics-config.js"></script>
</body>
</html>
```

- [ ] **Step 2: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_gajumaru.py`
Expected: `サイト検査完了: 1ページ / エラー 0`、終了コード0

- [ ] **Step 3: コミット**

```bash
git add site/gajumaru/index.html
git commit -m "feat(gajumaru): トップページ(ハブLP)を追加"
```

---

### Task 4: 代表者・チーム紹介ページ

**Files:**
- Create: `site/gajumaru/about/index.html`

**Interfaces:**
- Consumes: `site/gajumaru/analytics-config.js`(パスは `../analytics-config.js` からの相対参照ではなく絶対パス `/gajumaru/analytics-config.js` を使う。以降のページも同様)
- Produces: なし(末端ページ)

- [ ] **Step 1: `site/gajumaru/about/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>代表者・チーム紹介 | AIエージェント経営伴走(仮称)</title>
<meta name="description" content="10年以上の経営実践者「カチカクくん」と、AIエージェントチーム「ガジュマルくん」による伴走体制をご紹介します。">
<style>
:root{--gj-primary:#2F6B4F;--gj-accent:#D98E2B;--gj-ink:#1F2A2E;--gj-bg:#FAF7F0;
  --gj-card:#ffffff;--gj-muted:#5C6B70;--gj-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--gj-ink);background:var(--gj-bg)}
.wrap{max-width:720px;margin:0 auto;padding:0 20px}
a{color:var(--gj-primary)}
h1{font-size:1.6rem;margin-bottom:.6em}
h2{font-size:1.25rem;margin-bottom:.6em;border-left:6px solid var(--gj-accent);padding-left:.5em}
section{padding:36px 0}
.card{background:var(--gj-card);border:1px solid var(--gj-line);border-radius:12px;padding:22px;margin-bottom:16px}
.card h3{color:var(--gj-primary);margin-bottom:.4em}
.btn{display:inline-block;padding:14px 24px;background:var(--gj-primary);color:#fff;text-decoration:none;
  border-radius:999px;font-weight:700}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--gj-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--gj-ink)}
.siteheader .hlogo{font-weight:800;color:var(--gj-primary)}
footer{background:var(--gj-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="/gajumaru/">ガジュマル(仮称)</a>
  <a href="/gajumaru/about/">代表者紹介</a>
  <a href="/gajumaru/pricing/">料金</a>
  <a href="/gajumaru/blog/">お役立ち情報</a>
  <a href="/gajumaru/contact/">無料相談</a>
</header>
<main>
  <section>
    <div class="wrap">
      <h1>代表者・チーム紹介</h1>
      <div class="card">
        <h3>カチカクくん(経営伴走者)</h3>
        <p>10年以上にわたり、沖縄で複数の事業の経営に実際に携わってきた実務家です。管理コストの重さも、営業効率を上げる難しさも、自分自身が経営者として体験してきました。だからこそ、机上の空論ではなく「実際に効く」自動化だけをご提案します。プロプランをご検討のお客様とは、私が直接お話しします。</p>
      </div>
      <div class="card">
        <h3>ガジュマルくん(AIエージェントチーム)</h3>
        <p>日々の業務自動化・レポート作成・改善提案の実行を担うAIエージェントチームの人格です。ガジュマルは、強い根を張ってたくましく育つ沖縄の木。皆さまの会社の成長にしっかり根を張って伴走する、という思いを込めています。</p>
      </div>
      <h2>なぜ「安いのに安心」なのか</h2>
      <p>AIエージェントが運用の多くを担うことで、人手中心の代行サービスよりコストを抑えられます。ただし、設計と最終判断には必ず経営経験者の目が入ります。安さは「品質を削ること」ではなく「AIで運用コストを下げること」で実現しています。</p>
      <p style="margin-top:24px"><a class="btn" href="/gajumaru/contact/">無料相談を予約する</a></p>
    </div>
  </section>
</main>
<footer><div class="wrap">&copy; 2026 ガジュマル(仮称) — ブランド名は検討中です。</div></footer>
<script src="/gajumaru/analytics-config.js"></script>
</body>
</html>
```

- [ ] **Step 2: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_gajumaru.py`
Expected: `サイト検査完了: 2ページ / エラー 0`

- [ ] **Step 3: コミット**

```bash
git add site/gajumaru/about/index.html
git commit -m "feat(gajumaru): 代表者・チーム紹介ページを追加"
```

---

### Task 5: 料金ページ

**Files:**
- Create: `site/gajumaru/pricing/index.html`

**Interfaces:**
- Consumes: `site/gajumaru/analytics-config.js`
- Produces: なし(末端ページ)

- [ ] **Step 1: `site/gajumaru/pricing/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>料金プラン | AIエージェント経営伴走(仮称)</title>
<meta name="description" content="ライト80,000円〜/スタンダード150,000円〜/プロ300,000円〜。定額・明朗会計、初期費用ゼロ、いつでも解約可能な料金プランです。">
<style>
:root{--gj-primary:#2F6B4F;--gj-accent:#D98E2B;--gj-ink:#1F2A2E;--gj-bg:#FAF7F0;
  --gj-card:#ffffff;--gj-muted:#5C6B70;--gj-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--gj-ink);background:var(--gj-bg)}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
h1{font-size:1.6rem;margin-bottom:.6em}
section{padding:36px 0}
.plans{display:grid;gap:16px}
.plan{background:var(--gj-card);border:1px solid var(--gj-line);border-radius:12px;padding:22px}
.plan.reco{border-color:var(--gj-accent);border-width:2px}
.plan h3{color:var(--gj-primary);font-size:1.15rem}
.plan .price{font-size:1.6rem;font-weight:800;margin:.3em 0}
.plan .price small{font-size:.9rem;font-weight:400;color:var(--gj-muted)}
.note{font-size:.85rem;color:var(--gj-muted)}
.btn{display:inline-block;padding:14px 24px;background:var(--gj-primary);color:#fff;text-decoration:none;
  border-radius:999px;font-weight:700;margin-top:20px}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--gj-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--gj-ink)}
.siteheader .hlogo{font-weight:800;color:var(--gj-primary)}
footer{background:var(--gj-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="/gajumaru/">ガジュマル(仮称)</a>
  <a href="/gajumaru/about/">代表者紹介</a>
  <a href="/gajumaru/pricing/">料金</a>
  <a href="/gajumaru/blog/">お役立ち情報</a>
  <a href="/gajumaru/contact/">無料相談</a>
</header>
<main>
<section>
  <div class="wrap">
    <h1>料金プラン</h1>
    <p class="note">一般的にバックオフィス代行の相場は月20〜50万円程度、初期費用20〜100万円程度と言われています(自社調べ・要確認)。私たちはAIエージェント運用によるコスト構造の強みを活かし、この水準より抑えた定額プランをご用意しています。</p>
    <div class="plans" style="margin-top:20px">
      <div class="plan">
        <h3>ライト</h3>
        <div class="price">80,000円〜<small>/月</small></div>
        <p>定型業務1〜2種類の自動化(請求書処理 または 経費精算 等)</p>
      </div>
      <div class="plan reco">
        <h3>スタンダード</h3>
        <div class="price">150,000円〜<small>/月</small></div>
        <p>複数業務の自動化+月次レポート+改善提案</p>
      </div>
      <div class="plan">
        <h3>プロ</h3>
        <div class="price">300,000円〜<small>/月</small></div>
        <p>業務設計から伴走、専任エージェント構築</p>
      </div>
    </div>
    <p class="note" style="margin-top:16px">初期費用は原則0円。いつでも解約いただけます。正式な金額は業務内容により無料相談時にお見積りします。</p>
    <a class="btn" href="/gajumaru/contact/">無料相談を予約する</a>
  </div>
</section>
</main>
<footer><div class="wrap">&copy; 2026 ガジュマル(仮称) — ブランド名は検討中です。</div></footer>
<script src="/gajumaru/analytics-config.js"></script>
</body>
</html>
```

- [ ] **Step 2: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_gajumaru.py`
Expected: `サイト検査完了: 3ページ / エラー 0`

- [ ] **Step 3: コミット**

```bash
git add site/gajumaru/pricing/index.html
git commit -m "feat(gajumaru): 料金ページを追加"
```

---

### Task 6: 相談予約ページ

**Files:**
- Create: `site/gajumaru/contact/index.html`

**Interfaces:**
- Consumes: `site/gajumaru/analytics-config.js` の `window.GJ_CONTACT_EMAIL`
- Produces: なし(末端ページ)。将来Plan 2で予約ツール(Calendly等)に差し替える際は、このページの「ご相談方法」セクションのみ変更すればよい設計にする

- [ ] **Step 1: `site/gajumaru/contact/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>無料相談予約 | AIエージェント経営伴走(仮称)</title>
<meta name="description" content="管理コスト・営業効率でお困りの中小企業の方へ。無料相談はこちらから。">
<style>
:root{--gj-primary:#2F6B4F;--gj-accent:#D98E2B;--gj-ink:#1F2A2E;--gj-bg:#FAF7F0;
  --gj-card:#ffffff;--gj-muted:#5C6B70;--gj-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--gj-ink);background:var(--gj-bg)}
.wrap{max-width:640px;margin:0 auto;padding:0 20px}
h1{font-size:1.6rem;margin-bottom:.6em}
section{padding:36px 0}
.card{background:var(--gj-card);border:1px solid var(--gj-line);border-radius:12px;padding:22px}
.btn{display:inline-block;padding:16px 28px;background:var(--gj-primary);color:#fff;text-decoration:none;
  border-radius:999px;font-weight:700;font-size:1.05rem}
.steps{list-style:none;counter-reset:s;margin:16px 0}
.steps li{padding:10px 10px 10px 40px;position:relative;counter-increment:s}
.steps li::before{content:counter(s);position:absolute;left:0;top:8px;width:26px;height:26px;
  background:var(--gj-accent);border-radius:50%;text-align:center;line-height:26px;font-weight:800;font-size:.85rem}
.note{font-size:.85rem;color:var(--gj-muted)}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--gj-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--gj-ink)}
.siteheader .hlogo{font-weight:800;color:var(--gj-primary)}
footer{background:var(--gj-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="/gajumaru/">ガジュマル(仮称)</a>
  <a href="/gajumaru/about/">代表者紹介</a>
  <a href="/gajumaru/pricing/">料金</a>
  <a href="/gajumaru/blog/">お役立ち情報</a>
  <a href="/gajumaru/contact/">無料相談</a>
</header>
<main>
<section>
  <div class="wrap">
    <h1>無料相談予約</h1>
    <div class="card">
      <p>下のボタンから、会社名・ご相談内容を添えてメールをお送りください。カチカクくんが1〜2営業日以内に日程調整のご連絡をします。</p>
      <ol class="steps">
        <li>メールで簡単な会社概要とお困りごとをお送りください</li>
        <li>カチカクくんから日程調整のご連絡をします</li>
        <li>オンラインまたは沖縄県内であれば対面でご相談(無料・所要30分程度)</li>
      </ol>
      <p><a class="btn" id="mailBtn" href="#">メールで相談を申し込む</a></p>
      <p class="note" style="margin-top:14px">ご相談は無料です。しつこい営業は行いません。</p>
    </div>
  </div>
</section>
</main>
<footer><div class="wrap">&copy; 2026 ガジュマル(仮称) — ブランド名は検討中です。</div></footer>
<script src="/gajumaru/analytics-config.js"></script>
<script>
(function () {
  var email = (window.GJ_CONTACT_EMAIL || "contact@example.com");
  var subject = encodeURIComponent("無料相談のお申し込み");
  var body = encodeURIComponent("会社名:\n担当者名:\nご相談内容:\n");
  document.getElementById("mailBtn").href = "mailto:" + email + "?subject=" + subject + "&body=" + body;
})();
</script>
</body>
</html>
```

- [ ] **Step 2: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_gajumaru.py`
Expected: `サイト検査完了: 4ページ / エラー 0`

- [ ] **Step 3: ブラウザ相当の手動確認**: `site/gajumaru/contact/index.html` をブラウザで開き、「メールで相談を申し込む」ボタンの `href` が `mailto:contact@example.com?subject=...&body=...` になっていることをブラウザの開発者ツールで確認する

- [ ] **Step 4: コミット**

```bash
git add site/gajumaru/contact/index.html
git commit -m "feat(gajumaru): 無料相談予約ページを追加(mailto方式)"
```

---

### Task 7: ブログ一覧+サンプル記事(SEO記事群の土台)

**Files:**
- Create: `site/gajumaru/blog/index.html`
- Create: `site/gajumaru/blog/kihi-kosuto-sakugen/index.html`

**Interfaces:**
- Consumes: `site/gajumaru/analytics-config.js`
- Produces: 今後の記事量産時に踏襲するディレクトリ規約(`blog/<スラッグ>/index.html`)とブログ一覧への追加手順

- [ ] **Step 1: `site/gajumaru/blog/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>お役立ち情報 | AIエージェント経営伴走(仮称)</title>
<meta name="description" content="物価高・人件費高の中でコストを下げ、営業効率を上げるための実践情報をお届けします。">
<style>
:root{--gj-primary:#2F6B4F;--gj-accent:#D98E2B;--gj-ink:#1F2A2E;--gj-bg:#FAF7F0;
  --gj-card:#ffffff;--gj-muted:#5C6B70;--gj-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--gj-ink);background:var(--gj-bg)}
.wrap{max-width:720px;margin:0 auto;padding:0 20px}
h1{font-size:1.6rem;margin-bottom:.6em}
section{padding:36px 0}
.postlist{list-style:none}
.postlist li{background:var(--gj-card);border:1px solid var(--gj-line);border-radius:12px;
  padding:18px;margin-bottom:12px}
.postlist a{color:var(--gj-primary);font-weight:700;text-decoration:none}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--gj-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--gj-ink)}
.siteheader .hlogo{font-weight:800;color:var(--gj-primary)}
footer{background:var(--gj-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="/gajumaru/">ガジュマル(仮称)</a>
  <a href="/gajumaru/about/">代表者紹介</a>
  <a href="/gajumaru/pricing/">料金</a>
  <a href="/gajumaru/blog/">お役立ち情報</a>
  <a href="/gajumaru/contact/">無料相談</a>
</header>
<main>
<section>
  <div class="wrap">
    <h1>お役立ち情報</h1>
    <ul class="postlist">
      <li>
        <a href="/gajumaru/blog/kihi-kosuto-sakugen/">物価高・人件費高でも中小企業が管理コストを下げる5つの視点</a>
      </li>
    </ul>
  </div>
</section>
</main>
<footer><div class="wrap">&copy; 2026 ガジュマル(仮称) — ブランド名は検討中です。</div></footer>
<script src="/gajumaru/analytics-config.js"></script>
</body>
</html>
```

- [ ] **Step 2: サンプル記事 `site/gajumaru/blog/kihi-kosuto-sakugen/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>物価高・人件費高でも中小企業が管理コストを下げる5つの視点 | AIエージェント経営伴走(仮称)</title>
<meta name="description" content="物価高・賃金上昇が続く中、管理コストを下げつつ営業効率も上げるために中小企業が押さえておきたい5つの視点を解説します。">
<style>
:root{--gj-primary:#2F6B4F;--gj-accent:#D98E2B;--gj-ink:#1F2A2E;--gj-bg:#FAF7F0;
  --gj-card:#ffffff;--gj-muted:#5C6B70;--gj-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--gj-ink);background:var(--gj-bg)}
.wrap{max-width:680px;margin:0 auto;padding:0 20px}
h1{font-size:1.5rem;margin-bottom:.6em}
h2{font-size:1.15rem;margin:1.2em 0 .4em;color:var(--gj-primary)}
section{padding:36px 0}
.btn{display:inline-block;padding:14px 24px;background:var(--gj-primary);color:#fff;text-decoration:none;
  border-radius:999px;font-weight:700;margin-top:20px}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--gj-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--gj-ink)}
.siteheader .hlogo{font-weight:800;color:var(--gj-primary)}
footer{background:var(--gj-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="/gajumaru/">ガジュマル(仮称)</a>
  <a href="/gajumaru/about/">代表者紹介</a>
  <a href="/gajumaru/pricing/">料金</a>
  <a href="/gajumaru/blog/">お役立ち情報</a>
  <a href="/gajumaru/contact/">無料相談</a>
</header>
<main>
<section>
  <div class="wrap">
    <h1>物価高・人件費高でも中小企業が管理コストを下げる5つの視点</h1>
    <p>物価高と賃金上昇が続く中、多くの中小企業が「管理コストを下げたいが、人を減らす余裕もない」というジレンマを抱えています。ここでは、経営の現場で実際に効果があった5つの視点を紹介します。</p>
    <h2>1. 定型業務の棚卸しから始める</h2>
    <p>請求書処理、経費精算、日報集計など、判断を伴わない定型業務から自動化の対象にすると、失敗が少なく効果を実感しやすくなります。</p>
    <h2>2. 「誰がやるか」より「何を減らせるか」で考える</h2>
    <p>人を増やす・減らすの議論の前に、そもそも不要な作業を削れないかを見直すことが、最も費用対効果の高いコスト削減です。</p>
    <h2>3. 営業効率とコスト削減は同時に狙える</h2>
    <p>リード対応や提案書作成の自動化は、コストを下げるだけでなく、営業担当が商談に使える時間を増やし、売上にも直結します。</p>
    <h2>4. 導入コストの相場を知っておく</h2>
    <p>一般的にバックオフィス代行の相場は月20〜50万円程度と言われています(自社調べ・要確認)。相場を知らないまま検討すると、割高な契約をしてしまうリスクがあります。</p>
    <h2>5. 「安さ」と「安心」を両立できるか確認する</h2>
    <p>価格の安さだけで選ぶと、品質やサポート体制に不安が残ることがあります。運用コストの構造(AIか人手か)と、設計・監修に経験者が関わっているかを必ず確認しましょう。</p>
    <p><a class="btn" href="/gajumaru/contact/">無料相談で自社の状況を相談する</a></p>
  </div>
</section>
</main>
<footer><div class="wrap">&copy; 2026 ガジュマル(仮称) — ブランド名は検討中です。</div></footer>
<script src="/gajumaru/analytics-config.js"></script>
</body>
</html>
```

- [ ] **Step 3: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_gajumaru.py`
Expected: `サイト検査完了: 6ページ / エラー 0`

- [ ] **Step 4: コミット**

```bash
git add site/gajumaru/blog/
git commit -m "feat(gajumaru): ブログ一覧とサンプル記事を追加"
```

---

### Task 8: CI ワークフローの追加

**Files:**
- Create: `.github/workflows/gajumaru-ci.yml`

**Interfaces:**
- Consumes: `scripts/check_lp_gajumaru.py`(Task 1)
- Produces: `site/gajumaru/**` または `scripts/check_lp_gajumaru.py` への変更をトリガーに自動検査するCI

- [ ] **Step 1: `.github/workflows/gajumaru-ci.yml` を作成**

```yaml
name: gajumaru-ci

on:
  push:
    paths:
      - "site/gajumaru/**"
      - "scripts/check_lp_gajumaru.py"
  pull_request:
    paths:
      - "site/gajumaru/**"
      - "scripts/check_lp_gajumaru.py"
  workflow_dispatch: {}

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"

      - name: LP検査(サイズ予算・禁止表現・基本要件)
        run: python scripts/check_lp_gajumaru.py
```

- [ ] **Step 2: ローカルでYAML構文を確認**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/gajumaru-ci.yml'))" 2>/dev/null || python3 -c "import json,sys; print('yaml module unavailable, skipping local parse; will validate on push')"`
Expected: エラーが出ないこと(`yaml`モジュールがない場合はpushでのCI実行結果で確認する)

- [ ] **Step 3: コミットしてプッシュし、CIが緑になることを確認**

```bash
git add .github/workflows/gajumaru-ci.yml
git commit -m "ci(gajumaru): LP検査ワークフローを追加"
git push -u origin claude/claude-code-monetization-models-gsl932
```

Expected: GitHub ActionsでgajumaruのCIが実行され成功する(GitHub上で確認)

---

## Self-Review Summary

- **Spec coverage**: 設計書のサイト構成(トップ/代表者/料金/相談予約/SEO記事群)を全てカバー。セルフサーブ診断商品(決済+Claude APIレポート生成)とチーム/組織設計(非コード)は意図的に別プラン・対象外
- **Placeholder scan**: `contact@example.com` はダミーの連絡先だが、`GJ_CONTACT_EMAIL` という設定値として明示的に切り出しており、実メール確定後に1行差し替えるだけで済む設計。コード自体は完全に動作する
- **Type consistency**: 各ページが参照する `window.GJ_ANALYTICS` / `window.GJ_CONTACT_EMAIL` は Task 2 で定義した形と一致

## 次のプラン(Plan 2、別途作成)

- セルフサーブ診断商品(質問フォーム→決済→Claude APIでレポート生成→メール送付)
- Plausibleアカウント作成後の `analytics-config.js` 本番値差し込み
- 相談予約の予約ツール(Calendly等)への差し替え
