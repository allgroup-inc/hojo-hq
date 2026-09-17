# ノビシロLP 信頼要素ブラッシュアップ(トップ+代表者紹介) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ノビシロLP(`site/nobishiro/`)のトップページと代表者・チーム紹介ページに、信頼要素(サンプルレポート・キャラクター開示・具体的な経歴・アイコン)を追加し、「証拠のなさ」という設計上の弱点を解消する。

**Architecture:** 静的HTML(ビルドステップなし・各ページ自己完結)。CSSはページごとの`<style>`内、画像は外部依存なしのインラインSVGのみ。新規ページ1つ(`shindan/sample/index.html`)を追加し、既存2ページ(`index.html`/`about/index.html`)を編集する。

**Tech Stack:** 素のHTML/CSS(フレームワークなし)。検証は`scripts/check_lp_nobishiro.py`(Python)と、目視確認用のPlaywrightスクリーンショット。

## Global Constraints

- サイズ予算: 各ページ50KB以下(`scripts/check_lp_nobishiro.py`の`SIZE_BUDGET`)
- 禁止表現(`scripts/check_lp_nobishiro.py`の`FORBIDDEN`): `業界最安` `絶対` `100%削減` `必ず成功` `誰でも儲かる` `確実に安くなる` `保証します` を一切使わない
- 全ページで`lang="ja"`・`viewport`メタ・`<title>`・`description`メタ・`name="robots" content="noindex"`メタを維持する(公開前のため)
- リンクは相対パスのみ。`href="/..."`のような絶対パスは禁止(`check_lp_nobishiro.py`が検知する)
- 実績・お客様の声・導入社数を新たに捏造しない(現時点で顧客実績がないプロトタイプのため)
- 運営法人名など特定商取引法表記の実データは今回入力しない(`docs/ノビシロ_公開前チェックリスト.md`のステップ0/1-1、小柳さんの決裁待ちのまま)
- 配色トークン(`--nb-primary:#2F6B4F` / `--nb-accent:#D98E2B` 等)は変更しない
- 外部の画像生成サービス・ストックフォト・CDNには依存しない。追加するアイコンは自己完結のインラインSVGのみ
- 設計の詳細は `docs/superpowers/specs/2026-08-10-nobishiro-lp-trust-brushup-design.md` を参照

---

### Task 1: サンプルレポートページを新規作成する

**Files:**
- Create: `site/nobishiro/shindan/sample/index.html`

**Interfaces:**
- Consumes: なし(新規独立ページ)
- Produces: URL `shindan/sample/`(`index.html`から相対パス`shindan/sample/`、`about/index.html`からは`../shindan/sample/`でリンクされる想定。Task 4で`index.html`から実際にリンクする)

- [ ] **Step 1: ディレクトリと新規ファイルを作成する**

`site/nobishiro/shindan/sample/index.html` を以下の内容で作成する:

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>サンプルレポート | ノビシロ</title>
<meta name="description" content="AI活用診断でお届けするレポートのサンプルです。実際の内容は回答いただいた内容に応じて変わります。">
<link rel="icon" href="data:,">
<style>
:root{--nb-primary:#2F6B4F;--nb-accent:#D98E2B;--nb-ink:#1F2A2E;--nb-bg:#FAF7F0;
  --nb-card:#ffffff;--nb-muted:#5C6B70;--nb-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--nb-ink);background:var(--nb-bg)}
.wrap{max-width:640px;margin:0 auto;padding:0 20px}
h1{font-size:1.5rem;margin-bottom:.4em}
h2{font-size:1.1rem;color:var(--nb-primary);margin-bottom:.5em}
section{padding:36px 0}
.disclosure{background:#EFF3E9;border:1px solid var(--nb-line);border-radius:8px;padding:12px 16px;
  font-size:.9rem;color:var(--nb-muted);margin-bottom:20px}
.card{background:var(--nb-card);border:1px solid var(--nb-line);border-radius:12px;padding:22px;margin-bottom:16px}
.answers{font-size:.85rem;color:var(--nb-muted);margin-bottom:16px;padding-bottom:16px;
  border-bottom:1px solid var(--nb-line)}
.reportbody p{margin-bottom:14px}
.note{font-size:.85rem;color:var(--nb-muted)}
.btn{display:inline-block;padding:14px 24px;background:var(--nb-primary);color:#fff;text-decoration:none;
  border-radius:999px;font-weight:700;margin-right:8px;margin-top:8px}
.btn.ghost{background:transparent;color:var(--nb-primary);border:2px solid var(--nb-primary)}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--nb-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--nb-ink)}
.siteheader .hlogo{font-weight:800;color:var(--nb-primary)}
footer{background:var(--nb-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
footer a{color:#bcd0c4}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="../../">ノビシロ</a>
  <a href="../../about/">代表者紹介</a>
  <a href="../../pricing/">料金</a>
  <a href="../../blog/">お役立ち情報</a>
  <a href="../../contact/">無料相談</a>
</header>
<main>
  <section>
    <div class="wrap">
      <h1>サンプルレポート</h1>
      <p class="disclosure">これは実際の回答例をもとに作成したサンプルです。実際にお申し込みいただくと、あなたの会社の回答内容に合わせてガジュマルくんがレポートを作成します。</p>
      <div class="card">
        <h2>ガジュマルくんからの診断レポート(サンプル)</h2>
        <p class="answers">業種: 飲食業 / 従業員数: 5〜10名 / 月商規模: 300万円台 / 管理コストの実感: 重いと感じる / 営業効率の課題: 既存のお客様対応に追われて新規開拓の時間が取れない</p>
        <div class="reportbody">
          <p><strong>現状分析</strong><br>日々の仕入れ・シフト管理・経理処理に追われ、新しいお客様を増やすための時間が取りにくい状態のようです。管理業務と営業活動が同じ人の手で回っている場合、繁忙期にどちらかが後回しになりやすい傾向があります。</p>
          <p><strong>コスト構造の推定</strong><br>飲食業では、仕入れ・在庫・シフトの管理に一定の時間がかかっているケースが一般的です。断定はできませんが、定型作業の一部を自動化できる余地があるかもしれません。</p>
          <p><strong>おすすめプラン</strong><br>まずは経理処理かシフト管理のどちらか1つを自動化する「ライトプラン」から始めるのが現実的です。効果を確認してから範囲を広げる進め方をおすすめします。</p>
          <p><strong>次の一歩</strong><br>詳しい状況をお伺いしながら、どこから着手すべきか一緒に整理しませんか。無料相談でお待ちしています。</p>
        </div>
      </div>
      <p class="note">実際のレポートは、AIがお客様の回答内容をもとに生成します。内容の詳細は無料相談で改めてご確認いただけます。</p>
      <p style="margin-top:16px">
        <a class="btn" href="../">AI活用診断を申し込む(¥14,800)</a>
        <a class="btn ghost" href="../../contact/">無料相談を予約する</a>
      </p>
    </div>
  </section>
</main>
<footer><div class="wrap">&copy; 2026 ノビシロ <a href="../../tokushoho/">特定商取引法に基づく表記</a> ・ <a href="../../privacy/">プライバシーポリシー</a></div></footer>
</body>
</html>
```

- [ ] **Step 2: LP検査を実行する**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `サイト検査完了: 7ページ / エラー 0`(既存6ページ+新規1ページ、`[ERROR]`行が出ないこと)

- [ ] **Step 3: 新規ページの中身をテキストで確認する**

Run: `grep -c "サンプル" site/nobishiro/shindan/sample/index.html`
Expected: `1`以上(サンプルであることが明記されている)

- [ ] **Step 4: Commit**

```bash
git add site/nobishiro/shindan/sample/index.html
git commit -m "feat(nobishiro): AI活用診断のサンプルレポートページを追加"
```

---

### Task 2: トップページのフッター文言と「本物」ピラーのコピーを直す

**Files:**
- Modify: `site/nobishiro/index.html`

**Interfaces:**
- Consumes: なし
- Produces: なし(テキストのみの変更、他タスクから参照されない)

- [ ] **Step 1: フッターの「ブランド名は検討中です」を削除する**

`site/nobishiro/index.html` 内の以下の行を:

```html
    <p>&copy; 2026 ノビシロ — ブランド名は検討中です。</p>
```

以下に置き換える:

```html
    <p>&copy; 2026 ノビシロ</p>
```

- [ ] **Step 2: 「本物」ピラーのコピーを具体化する**

`site/nobishiro/index.html` 内の以下のブロックを:

```html
        <div class="pillar">
          <h3>本物</h3>
          <p>10年以上、経営の現場で実践してきた「カチカクくん」がAIチームと一緒に設計・伴走します。丸投げのAIツールではありません。</p>
        </div>
```

以下に置き換える:

```html
        <div class="pillar">
          <h3>本物</h3>
          <p>新卒から会社員、役員、そして自分の会社の経営まで。経理・採用・営業・資金繰り、現場から経営まで自分の手でやってきた「カチカクくん」が、AIチームと一緒に設計・伴走します。丸投げのAIツールではありません。<a href="about/">プロフィールを見る</a></p>
        </div>
```

- [ ] **Step 3: LP検査を実行する**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `エラー 0`(禁止表現・絶対パスに引っかからないこと)

- [ ] **Step 4: 変更箇所をテキストで確認する**

Run: `grep -c "ブランド名は検討中" site/nobishiro/index.html`
Expected: `0`(文言が消えていること)

- [ ] **Step 5: Commit**

```bash
git add site/nobishiro/index.html
git commit -m "fix(nobishiro): トップページの未完成感の露出を消し「本物」の訴求を具体化"
```

---

### Task 3: トップページのヒーロー直下にカチカクくんの信頼クオートを追加する

**Files:**
- Modify: `site/nobishiro/index.html`

**Interfaces:**
- Consumes: なし
- Produces: CSSクラス`.trustquote`/`.avatar`(このタスク内でのみ使用。about/index.htmlの`.avatar`とは同名だが別ファイルのスコープなので衝突しない)

- [ ] **Step 1: CSSに`.trustquote`のスタイルを追加する**

`site/nobishiro/index.html` の`<style>`内、以下の行:

```css
.pillar h3{color:var(--nb-primary);margin-bottom:.3em}
```

の直後に、以下を追加する:

```css
.trustquote{background:var(--nb-card);border:1px solid var(--nb-line);border-radius:12px;padding:18px 20px;
  display:flex;gap:16px;align-items:center}
.trustquote .avatar{flex:none;display:block}
.trustquote p{font-size:.95rem;color:var(--nb-muted)}
.trustquote a{font-weight:700}
```

- [ ] **Step 2: ヒーローセクション直後に信頼クオートのセクションを追加する**

`site/nobishiro/index.html` 内の以下のブロックを:

```html
      <div class="ctarow">
        <a class="btn" href="contact/">無料相談を予約する</a>
        <a class="btn ghost" href="pricing/">料金を見る</a>
      </div>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2>3つの約束</h2>
```

以下に置き換える(ヒーローセクションと「3つの約束」セクションの間に、信頼クオートのセクションを挟み込む):

```html
      <div class="ctarow">
        <a class="btn" href="contact/">無料相談を予約する</a>
        <a class="btn ghost" href="pricing/">料金を見る</a>
      </div>
    </div>
  </section>

  <section style="padding:0 0 8px">
    <div class="wrap">
      <div class="trustquote">
        <svg class="avatar" width="56" height="56" viewBox="0 0 120 120" role="img" aria-label="カチカクくんのシンボルアイコン">
          <circle cx="60" cy="60" r="58" fill="#2F6B4F"/>
          <path d="M34 78 L34 62 M52 78 L52 50 M70 78 L70 40 M88 78 L88 30" stroke="#D98E2B" stroke-width="8" stroke-linecap="round"/>
          <path d="M30 78 H90" stroke="#FAF7F0" stroke-width="4" stroke-linecap="round"/>
        </svg>
        <p>「経理も採用も、自分の会社で全部自分でやってきました。だから、どこが本当に苦しいか分かります。」— カチカクくん<br><a href="about/">詳しいプロフィールを見る</a></p>
      </div>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2>3つの約束</h2>
```

- [ ] **Step 3: LP検査を実行する**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `エラー 0`

- [ ] **Step 4: HTMLの構文が壊れていないことを確認する**

Run: `python3 -c "import re; s=open('site/nobishiro/index.html', encoding='utf-8').read(); assert s.count('<section')==s.count('</section>'), 'section開閉タグ不一致'; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add site/nobishiro/index.html
git commit -m "feat(nobishiro): トップページにカチカクくんの信頼クオート(イラストアイコン付き)を追加"
```

---

### Task 4: トップページの「AI活用診断」ブロックにサンプルレポートへの導線を追加する

**Files:**
- Modify: `site/nobishiro/index.html`

**Interfaces:**
- Consumes: Task 1で作成した`shindan/sample/`(トップページ`index.html`からの相対パスは`shindan/sample/`)
- Produces: なし

- [ ] **Step 1: サンプルレポートへのリンクを追加する**

`site/nobishiro/index.html` 内の以下のブロックを:

```html
      <div class="ctarow" style="margin-top:16px">
        <a class="btn" href="shindan/">AI活用診断を受ける(¥14,800)</a>
        <a class="btn ghost" href="contact/">無料相談を予約する</a>
      </div>
    </div>
  </section>
</main>
```

以下に置き換える:

```html
      <div class="ctarow" style="margin-top:16px">
        <a class="btn" href="shindan/">AI活用診断を受ける(¥14,800)</a>
        <a class="btn ghost" href="contact/">無料相談を予約する</a>
      </div>
      <p class="note" style="margin-top:12px">どんなレポートが届くか、<a href="shindan/sample/">サンプルレポート</a>を見てからお申し込みいただけます。</p>
    </div>
  </section>
</main>
```

- [ ] **Step 2: リンク切れがないことを確認する**

Run: `test -f site/nobishiro/shindan/sample/index.html && echo "OK: リンク先が存在する"`
Expected: `OK: リンク先が存在する`

- [ ] **Step 3: LP検査を実行する**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `エラー 0`

- [ ] **Step 4: Commit**

```bash
git add site/nobishiro/index.html
git commit -m "feat(nobishiro): AI活用診断ブロックにサンプルレポートへの導線を追加"
```

---

### Task 5: 代表者紹介ページにキャラクター開示文とカチカクくんのアイコン・経歴を追加する

**Files:**
- Modify: `site/nobishiro/about/index.html`

**Interfaces:**
- Consumes: なし
- Produces: CSSクラス`.disclosure`/`.card-head`/`.avatar`(Task 6で同ファイル内`.avatar`を再利用する)

- [ ] **Step 1: フッターの「ブランド名は検討中です」を削除する**

`site/nobishiro/about/index.html` 内の以下の行を:

```html
<footer><div class="wrap">&copy; 2026 ノビシロ — ブランド名は検討中です。 <a href="../tokushoho/">特定商取引法に基づく表記</a> ・ <a href="../privacy/">プライバシーポリシー</a></div></footer>
```

以下に置き換える:

```html
<footer><div class="wrap">&copy; 2026 ノビシロ <a href="../tokushoho/">特定商取引法に基づく表記</a> ・ <a href="../privacy/">プライバシーポリシー</a></div></footer>
```

- [ ] **Step 2: CSSに`.disclosure`/`.card-head`/`.avatar`のスタイルを追加する**

`site/nobishiro/about/index.html` の`<style>`内、以下の行:

```css
.card h2{color:var(--nb-primary);margin-bottom:.4em;font-size:1.15rem;border-left:none;padding-left:0}
```

の直後に、以下を追加する:

```css
.disclosure{background:#EFF3E9;border:1px solid var(--nb-line);border-radius:8px;padding:12px 16px;
  font-size:.9rem;color:var(--nb-muted);margin-bottom:20px}
.card-head{display:flex;align-items:center;gap:14px;margin-bottom:10px}
.card-head h2{margin-bottom:0}
.avatar{flex:none;display:block}
```

- [ ] **Step 3: 開示文とカチカクくんカードを書き換える**

`site/nobishiro/about/index.html` 内の以下のブロックを:

```html
      <h1>代表者・チーム紹介</h1>
      <div class="card">
        <h2>カチカクくん(経営伴走者)</h2>
        <p>10年以上にわたり、沖縄で複数の事業の経営に実際に携わってきた実務家です。管理コストの重さも、営業効率を上げる難しさも、自分自身が経営者として体験してきました。だからこそ、机上の空論ではなく「実際に効く」自動化だけをご提案します。プロプランをご検討のお客様とは、私が直接お話しします。</p>
      </div>
```

以下に置き換える:

```html
      <h1>代表者・チーム紹介</h1>
      <p class="disclosure">カチカクくんとガジュマルくんは、私たちの実務経験を人格化した「経営伴走者」「AIエージェントチーム」のキャラクターです。実在の特定の個人を指すものではありません。</p>
      <div class="card">
        <div class="card-head">
          <svg class="avatar" width="64" height="64" viewBox="0 0 120 120" role="img" aria-label="カチカクくんのシンボルアイコン">
            <circle cx="60" cy="60" r="58" fill="#2F6B4F"/>
            <path d="M34 78 L34 62 M52 78 L52 50 M70 78 L70 40 M88 78 L88 30" stroke="#D98E2B" stroke-width="8" stroke-linecap="round"/>
            <path d="M30 78 H90" stroke="#FAF7F0" stroke-width="4" stroke-linecap="round"/>
          </svg>
          <h2>カチカクくん(経営伴走者)</h2>
        </div>
        <p>新卒で会社員として働き始め、その後は役員として組織運営に携わりました。そこから独立して自分の会社を設立し、10年以上にわたり沖縄で複数の事業の経営を続けています。経理・採用・営業・資金繰り——管理コストの重さも、営業効率を上げる難しさも、現場から経営まで自分自身で体験してきました。だからこそ、机上の空論ではなく「実際に効く」自動化だけをご提案します。プロプランをご検討のお客様とは、私が直接お話しします。</p>
      </div>
```

- [ ] **Step 4: LP検査を実行する**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `エラー 0`

- [ ] **Step 5: 開示文が入っていることを確認する**

Run: `grep -c "人格化した" site/nobishiro/about/index.html`
Expected: `1`以上

- [ ] **Step 6: Commit**

```bash
git add site/nobishiro/about/index.html
git commit -m "feat(nobishiro): 代表者紹介にキャラクター開示文とカチカクくんのアイコン・経歴を追加"
```

---

### Task 6: 代表者紹介ページのガジュマルくんカードにアイコンを追加する

**Files:**
- Modify: `site/nobishiro/about/index.html`

**Interfaces:**
- Consumes: Task 5で追加した`.card-head`/`.avatar`のCSS
- Produces: なし

- [ ] **Step 1: ガジュマルくんカードにアイコンを追加する**

`site/nobishiro/about/index.html` 内の以下のブロックを:

```html
      <div class="card">
        <h2>ガジュマルくん(AIエージェントチーム)</h2>
        <p>日々の業務自動化・レポート作成・改善提案の実行を担うAIエージェントチームの人格です。ガジュマルは、強い根を張ってたくましく育つ沖縄の木。皆さまの会社の成長にしっかり根を張って伴走する、という思いを込めています。</p>
      </div>
```

以下に置き換える:

```html
      <div class="card">
        <div class="card-head">
          <svg class="avatar" width="64" height="64" viewBox="0 0 120 120" role="img" aria-label="ガジュマルくんのシンボルアイコン">
            <circle cx="60" cy="60" r="58" fill="#D98E2B"/>
            <circle cx="60" cy="42" r="20" fill="#2F6B4F"/>
            <path d="M60 60 V90 M60 70 L46 90 M60 70 L74 90 M60 78 L38 96 M60 78 L82 96" stroke="#2F6B4F" stroke-width="6" stroke-linecap="round" fill="none"/>
          </svg>
          <h2>ガジュマルくん(AIエージェントチーム)</h2>
        </div>
        <p>日々の業務自動化・レポート作成・改善提案の実行を担うAIエージェントチームの人格です。ガジュマルは、強い根を張ってたくましく育つ沖縄の木。皆さまの会社の成長にしっかり根を張って伴走する、という思いを込めています。</p>
      </div>
```

- [ ] **Step 2: LP検査を実行する**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `エラー 0`

- [ ] **Step 3: HTMLの構文が壊れていないことを確認する**

Run: `python3 -c "import re; s=open('site/nobishiro/about/index.html', encoding='utf-8').read(); assert s.count('<div class=\"card\">')==2, 'カード数が想定と違う'; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add site/nobishiro/about/index.html
git commit -m "feat(nobishiro): 代表者紹介のガジュマルくんカードにアイコンを追加"
```

---

### Task 7: 最終レビュー(全ページのLP検査+スクリーンショット目視確認)

**Files:**
- なし(検証のみ)

**Interfaces:**
- Consumes: Task 1〜6の全変更
- Produces: なし

- [ ] **Step 1: LP検査を全体で実行する**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `サイト検査完了: 7ページ / エラー 0`

- [ ] **Step 2: 診断ロジック等の既存Nodeテストが壊れていないことを確認する**

Run: `node --test tests/nobishiro-shindan-logic.test.mjs tests/nobishiro-shindan-backend.test.mjs`
Expected: 全テストPASS(今回の変更はテスト対象のロジックに触れていないため、既存の結果のまま通ること)

- [ ] **Step 3: ローカルサーバーを立てて目視確認用のスクリーンショットを撮る**

```bash
cd site/nobishiro && (python3 -m http.server 8931 >/tmp/nobishiro-server.log 2>&1 &) && sleep 1
```

Playwrightが未インストールであれば、セットアップする(このリポジトリのセッションでは`/opt/pw-browsers`にChromiumが同梱済みのため、パッケージのみ追加すればよい):

```bash
mkdir -p /tmp/nobishiro-review && cd /tmp/nobishiro-review && npm init -y >/dev/null 2>&1 && \
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers npm install playwright --no-audit --no-fund
```

`/tmp/nobishiro-review/shot.js` を以下の内容で作成する:

```javascript
const { chromium } = require('playwright');

const pages = [
  { path: '/', name: 'index' },
  { path: '/about/', name: 'about' },
  { path: '/shindan/sample/', name: 'shindan-sample' },
];

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  for (const p of pages) {
    await page.goto(`http://localhost:8931${p.path}`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.screenshot({ path: `/tmp/nobishiro-review/${p.name}.png`, fullPage: true });
    console.log('OK', p.name);
  }
  await browser.close();
})();
```

Run: `cd /tmp/nobishiro-review && node shot.js`
Expected: `OK index` / `OK about` / `OK shindan-sample` が出力される

- [ ] **Step 4: ローカルサーバーを止める**

Run: `pkill -f "http.server 8931"`

- [ ] **Step 5: スクリーンショットをユーザーに送って確認してもらう**

`index.png` / `about.png` / `shindan-sample.png` の3枚を送付し、意図通りに見えているか(信頼クオートの位置・アイコンの見え方・経歴の文章・サンプルレポートの内容)を確認してもらう。指摘があれば該当タスクに戻って直す。

- [ ] **Step 6: 完了報告**

問題なければ、このタスクをもって計画は完了。以降のブランチ運用(designated branchへのpush、mainへのクリーンなcherry-pickブランチ経由PR作成・マージ)は、このリポジトリでこれまで使ってきたやり方に従う(計画のタスクそのものには含めない)。
