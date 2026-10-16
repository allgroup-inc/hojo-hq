# Plan A LP サイト実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Okinawan producers向けに、1万円 + 3% で世界販売を実現する Plan A ビジネスのワンページ LP サイトを実装し、複数段階の CTA（LINE → 資料 → 説明会）で段階的な行動を促進する。

**Architecture:** 単一HTML + レスポンシブCSS + JavaScript（フォーム連携・GA計測）で構成。9セクション（Hero〜CTA）を順序良く配置し、沖縄色 + GLOW オレンジのビジュアル融合で信頼と親しみを両立。フォーム3種（LINE・資料請求メール・説明会申し込み）と Google Analytics 計測を統合。

**Tech Stack:**
- HTML5 / CSS3（Flexbox, Grid）
- JavaScript（form handling, GA）
- Formspree または Netlify Forms（メール送信）
- Google Forms API または 専用フォーム（説明会申し込み）
- Google Analytics 4

**Spec:** `docs/superpowers/specs/2026-09-26-plan-a-lp-design.md`

---

## Global Constraints

- **配色：** 朱#B9502F、黄#F2B705、漆喰#FFFBF4（沖縄色主体）、GLOW オレンジ#F88800（アクセント）、濃紺#00335C（見出し）、濃灰#333333（本文）、白#FFFFFF（背景）
- **フォント：** Meiryo / Noto Sans JP（Bold: 見出し、Regular: 本文）
- **レスポンシブ：** PC 1200px / タブレット 768px / モバイル 390px（gutter: PC/タブ 40px、モバイル 16px）
- **ファイルパス：** `site/go/plan-a/index.html`（主ファイル）、スタイル・スクリプト同梱または `assets/` 配下
- **フォーム連携：** LINE 公式友だち追加ボタン埋め込み、Formspree でメール送信、Google Form または カスタムフォーム で説明会申し込み
- **計測：** Google Analytics 4 イベント（CTA各段階のクリック、フォーム送信）

---

## Review Focus

1. **モバイル表示崩れ** — タブレット・モバイル 各ブレークポイントで、見出し・テキスト・画像が意図通り配置されているか。特にセクション3（5つの壁）と セクション5（仕組み図解）の複雑レイアウト
2. **フォーム送信失敗** — LINE・資料請求・説明会の各フォーム送信が正常に動作し、ユーザー側で確認できるか。Formspree エラーハンドリング、Google Form リダイレクト
3. **GA計測漏れ** — CTA ボタンクリック・フォーム送受信のすべてが Google Analytics に記録されているか。イベント名・パラメータが設計通りか
4. **画像読み込み遅延** — ヒーロー背景・生産者写真・商品写真 など複数の大容量画像が全セクションで適切に読み込まれているか。WebP 配信、Lazy Loading 効果を実測
5. **内容の正確性** — セクション2（生産者インタビュー）、セクション7（成功事例）のテキスト・数字が、実際の成功例と整合しているか。フェイク事例の場合は「事例イメージ」と明示

---

## ファイル構成

```
site/go/plan-a/
├── index.html          （メイン LP ワンページ）
├── styles.css          （レスポンシブスタイル）
├── scripts.js          （フォーム・GA計測）
└── assets/
    ├── images/         （背景画像・生産者写真・商品写真）
    │   ├── hero-bg.jpg
    │   ├── producer-*.jpg
    │   ├── product-*.jpg
    │   └── okinawa-*.jpg
    ├── icons/          （5つの壁・アイコン）
    │   ├── cost.svg
    │   ├── results.svg
    │   ├── language.svg
    │   ├── process.svg
    │   └── fraud.svg
    └── logos/          （信頼バッジ）
        ├── trade-assurance.png
        ├── alibaba-partner.png
        └── okinawa-support.png
```

---

## Task 1: 素材収集・アセット管理

**Files:**
- Create: `site/go/plan-a/assets/images/` ディレクトリ構造
- Create: `site/go/plan-a/assets/icons/` ディレクトリ構造
- Create: `site/go/plan-a/assets/logos/` ディレクトリ構造

**Interfaces:**
- 生成物：画像ファイル一覧（パス・形式・サイズ）
- 次タスク Task 2 が参照

**素材リスト:**

| 素材 | 用途 | 数量 | 形式 | 注記 |
|------|------|------|------|------|
| ヒーロー背景 | セクション1 | 1 | JPG/WebP | 1920×1080以上、沖縄海・農地など |
| 生産者顔写真 | セクション2 | 3 | JPG | 400×400px、農業法人・個人農家・工芸職人各1 |
| 生産者顔写真 | セクション7 | 3 | JPG | 400×400px、成功事例用（セクション2と同一または別人） |
| 商品写真 | セクション7 | 3 | JPG | 600×400px、マンゴー・黒糖・琉球漆器 |
| Okinawa風景 | バックアップ | 2-3 | JPG | 次セクション背景用 |
| 5つの壁アイコン | セクション3 | 5 | SVG | 高コスト・成果不明・言語・実務・詐欺 |
| 信頼バッジ | セクション9 | 3 | PNG | Trade Assurance・Alibaba Partner・Okinawa Support |

- [ ] **Step 1: アセットディレクトリ作成**

```bash
mkdir -p site/go/plan-a/assets/{images,icons,logos}
cd site/go/plan-a/assets
ls -la
```

- [ ] **Step 2: 素材ソース確認・ダウンロード**

生産者写真・商品写真は「実在するか・フェイクか」を判定し、フェイク事例の場合は HTML に「※イメージです」と明示する。
ヒーロー背景・Okinawa 風景は CC0 フリー素材（Unsplash, Pexels）または社内ストック。
アイコンは Font Awesome / Feather Icons 等、または設計側で SVG 指定。

- [ ] **Step 3: 画像最適化・WebP 化**

```bash
# JPG → WebP 変換（ImageMagick 使用）
mogrify -format webp -quality 80 assets/images/*.jpg

# ファイルサイズ確認
du -sh assets/images/
du -sh assets/icons/
du -sh assets/logos/
```

ヒーロー背景・商品写真は 200KB 以下、生産者写真は 100KB 以下を目安。

- [ ] **Step 4: アセットマニフェスト作成・検証**

`assets/manifest.json` を作成し、すべての画像・アイコン・ロゴをリスト化

```json
{
  "images": {
    "hero-bg": "images/hero-bg.webp",
    "producer-1": "images/producer-1.jpg",
    "product-1": "images/product-1.jpg"
  },
  "icons": {
    "cost": "icons/cost.svg",
    "results": "icons/results.svg"
  },
  "logos": {
    "trade-assurance": "logos/trade-assurance.png"
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add site/go/plan-a/assets/
git commit -m "assets: add Plan A LP images, icons, logos"
```

---

## Task 2: HTML 骨組み・セクション構造

**Files:**
- Create: `site/go/plan-a/index.html`
- Modify: なし

**Interfaces:**
- 生成物：HTML ドキュメント（9セクション、ヘッダー・フッター）
- 次タスク Task 3・4・5 で参照

- [ ] **Step 1: HTML テンプレート作成（ヘッダー・Meta・共通構造）**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plan A - 沖縄の商品を世界へ</title>
    <meta name="description" content="1万円の初期投資だけで、沖縄の商品を世界向けにプレミアム価格で販売。GLOW が5つの壁をすべて解決します。">
    <meta property="og:title" content="Plan A - 沖縄の商品を世界へ">
    <meta property="og:description" content="1万円 + 3% で海外販売を実現">
    <meta property="og:image" content="https://hojo-hq.pages.dev/go/plan-a/assets/images/hero-bg.webp">
    <meta property="og:url" content="https://hojo-hq.pages.dev/go/plan-a/">
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <!-- セクション1: Hero -->
        <section id="section-1" class="section hero">
            <div class="hero-content">
                <h1>一商品を1万円のコストだけで、世界に向けてプレミアム価格を設定して販売できる新しい販路</h1>
                <h2 class="subtitle">沖縄の美しさや力強さを世界に届ける</h2>
                <p class="description">30年の公庫経験を持つ GLOW が、沖縄の生産者の壁を解決します</p>
                <button class="btn btn-primary">詳しく知る</button>
            </div>
        </section>

        <!-- セクション2: 生産者の想い -->
        <section id="section-2" class="section producers">
            <h2 class="section-title">生産者の想い</h2>
            <div class="cards-grid">
                <div class="card">
                    <img src="assets/images/producer-1.jpg" alt="農業法人経営者" class="card-image">
                    <h3>農業法人経営者（名護市）</h3>
                    <p>家族の夢は世界に認めてもらうこと。高級農産物だからこそ、国内だけでは本当の価値が引き出せない。</p>
                </div>
                <div class="card">
                    <img src="assets/images/producer-2.jpg" alt="個人農家" class="card-image">
                    <h3>個人農家（南城市）</h3>
                    <p>70代で後継者もいない。だが自分の作ったものを世界に知ってもらいたい。人生の最後にチャレンジしたい。</p>
                </div>
                <div class="card">
                    <img src="assets/images/producer-3.jpg" alt="工芸職人" class="card-image">
                    <h3>工芸職人（那覇市）</h3>
                    <p>伝統工芸だが、若い世代への継承が課題。世界市場で認知度が上がれば、弟子志望も増えるはず。</p>
                </div>
            </div>
        </section>

        <!-- セクション3: 5つの壁 -->
        <section id="section-3" class="section five-walls">
            <h2 class="section-title">世界展開を阻む 5 つの壁</h2>
            <div class="walls-grid">
                <div class="wall-card">
                    <svg class="wall-icon"><!-- icon: cost --></svg>
                    <h3>高コスト</h3>
                    <p>国際展示会1回で300万円以上。その投資で売上が見えない。</p>
                </div>
                <div class="wall-card">
                    <svg class="wall-icon"><!-- icon: results --></svg>
                    <h3>成果不明</h3>
                    <p>海外渡航で100万円、でも売上が見えない。ROI が不透明。</p>
                </div>
                <div class="wall-card">
                    <svg class="wall-icon"><!-- icon: language --></svg>
                    <h3>言語障壁</h3>
                    <p>翻訳1日5万円、でも誤訳のリスク。バイヤーとの交渉も。</p>
                </div>
                <div class="wall-card">
                    <svg class="wall-icon"><!-- icon: process --></svg>
                    <h3>実務ゼロ</h3>
                    <p>インボイス・物流・通関が複雑すぎる。どこから始めるか分からない。</p>
                </div>
                <div class="wall-card">
                    <svg class="wall-icon"><!-- icon: fraud --></svg>
                    <h3>詐欺不安</h3>
                    <p>「お金を払ったのに商品が来ない」という恐怖。国際取引の信頼が不足。</p>
                </div>
            </div>
        </section>

        <!-- セクション4: GLOW の信頼 -->
        <section id="section-4" class="section glow-trust">
            <h2 class="section-title">GLOW の信頼</h2>
            <div class="trust-grid">
                <div class="trust-profile">
                    <img src="assets/images/glow-representative.jpg" alt="嶺井代表" class="profile-image">
                    <h3>嶺井 〇〇</h3>
                    <p class="title">GLOW 代表 / 元・政策金融公庫 融資担当</p>
                    <p class="bio">30年以上、沖縄の企業の資金調達と経営支援に携わってきた。沖縄の経営者・生産者の可能性を世界に届けることが最大の使命。</p>
                    <blockquote>沖縄の企業・生産者の可能性を世界に。その壁を、僕たちが解決します。</blockquote>
                </div>
                <div class="trust-achievements">
                    <h3>GLOW の実績</h3>
                    <ul>
                        <li><strong>支援企業数：</strong>200社以上</li>
                        <li><strong>累計融資額：</strong>100億円超</li>
                        <li><strong>既存事業：</strong>ゆんたく経営相談室、沖縄企業のミカタ、家計の見直しやさん</li>
                        <li><strong>信頼実績：</strong>沖縄県・市町村との連携、士業パートナーネットワーク</li>
                    </ul>
                </div>
            </div>
        </section>

        <!-- セクション5: Plan A の仕組み -->
        <section id="section-5" class="section plan-a-mechanism">
            <h2 class="section-title">Plan A の仕組み</h2>
            <div class="mechanism-grid">
                <div class="mechanism-flow">
                    <div class="flow-item">
                        <p class="flow-label">あなた</p>
                        <p class="flow-value">1万円</p>
                    </div>
                    <div class="flow-arrow">→</div>
                    <div class="flow-item">
                        <p class="flow-label">GLOW</p>
                        <p class="flow-value">年間115万円</p>
                    </div>
                    <div class="flow-arrow">→</div>
                    <div class="flow-item">
                        <p class="flow-label">Alibaba.com</p>
                        <p class="flow-value">365日出店</p>
                    </div>
                </div>
                <div class="mechanism-steps">
                    <div class="step">
                        <h3>ステップ1</h3>
                        <p>1万円で、あなたの商品を Alibaba のバーチャルブースに登録</p>
                    </div>
                    <div class="step">
                        <h3>ステップ2</h3>
                        <p>GLOW が翻訳・商談・物流をすべて代行（AI も活用）</p>
                    </div>
                    <div class="step">
                        <h3>ステップ3</h3>
                        <p>あなたは世界向けにプレミアム価格を設定して販売</p>
                    </div>
                    <div class="result">
                        <p><strong>売上 × 3% が GLOW の手数料。残り 97% があなたの利益</strong></p>
                    </div>
                </div>
            </div>
        </section>

        <!-- セクション6: 3段階のメリット -->
        <section id="section-6" class="section three-stage-benefits">
            <h2 class="section-title">3段階のメリット</h2>
            <div class="benefits-grid">
                <div class="benefit-card stage-1">
                    <h3>①信頼：低リスク</h3>
                    <p>1万円の初期投資だけ。国際展示会の 300万円 ギャンブルは不要。GLOW が 5つの壁をすべて吸収するので、あなたは商品づくりに集中できる。</p>
                </div>
                <div class="benefit-card stage-2">
                    <h3>②安心：簡潔さ</h3>
                    <p>複雑な書類・物流・通関も GLOW が代行。あなたがすることは「商品を良くすること」だけ。AI 翻訳で言語も不要。</p>
                </div>
                <div class="benefit-card stage-3">
                    <h3>③ビジョン：高利益 + 誇り</h3>
                    <p>海外向けにプレミアム価格を設定できるので、国内販売より高い利益率。さらに「沖縄の美しさが世界に認められた」という誇りも得られる。</p>
                </div>
            </div>
        </section>

        <!-- セクション7: 成功事例 -->
        <section id="section-7" class="section success-cases">
            <h2 class="section-title">成功事例</h2>
            <div class="cases-grid">
                <div class="case-card">
                    <img src="assets/images/product-1.jpg" alt="高級マンゴー" class="case-image">
                    <h3>A農園（名護市）</h3>
                    <p class="case-product">高級マンゴー</p>
                    <p class="case-story">県内の優良農園だが、流通が限定的だった。Plan A で世界展開を開始。</p>
                    <p class="case-result"><strong>月 5-10件 の海外問い合わせ、売上 3倍へ</strong></p>
                </div>
                <div class="case-card">
                    <img src="assets/images/product-2.jpg" alt="沖縄黒糖" class="case-image">
                    <h3>B さん（南城市）</h3>
                    <p class="case-product">沖縄黒糖</p>
                    <p class="case-story">70代。後継者もいないが、自分の作った黒糖を世界に知ってもらいたい。</p>
                    <p class="case-result"><strong>初月で 3国 からの注文、新しい人生の第二章が始まった</strong></p>
                </div>
                <div class="case-card">
                    <img src="assets/images/product-3.jpg" alt="琉球漆器" class="case-image">
                    <h3>C 工房（那覇市）</h3>
                    <p class="case-product">琉球漆器</p>
                    <p class="case-story">伝統工芸だが、若い世代への継承が課題。世界市場で認知度向上へ。</p>
                    <p class="case-result"><strong>海外セレクトショップ からの引き合い、弟子志望も増加</strong></p>
                </div>
            </div>
            <p class="case-note">※成功事例はイメージです。実際の事例は説明会でご紹介します。</p>
        </section>

        <!-- セクション8: プロセス図解 -->
        <section id="section-8" class="section process-timeline">
            <h2 class="section-title">進め方は シンプル</h2>
            <div class="timeline">
                <div class="timeline-item">
                    <div class="timeline-step">ステップ① 登録</div>
                    <div class="timeline-period">1-2週間</div>
                    <div class="timeline-content">
                        <p><strong class="user-label">あなた：</strong> 商品情報・写真・価格を提出</p>
                        <p><strong class="glow-label">GLOW：</strong> 情報整理・翻訳・Alibaba 登録</p>
                        <p><strong class="result-label">結果：</strong> バーチャルブースに出店完了</p>
                    </div>
                </div>
                <div class="timeline-item">
                    <div class="timeline-step">ステップ② プロモーション</div>
                    <div class="timeline-period">週1-2回</div>
                    <div class="timeline-content">
                        <p><strong class="user-label">あなた：</strong> 定期的に商品情報を更新</p>
                        <p><strong class="glow-label">GLOW：</strong> Alibaba 内での露出最適化・バイヤー検索対応</p>
                        <p><strong class="result-label">結果：</strong> 世界のバイヤーからの問い合わせ開始</p>
                    </div>
                </div>
                <div class="timeline-item">
                    <div class="timeline-step">ステップ③ 商談</div>
                    <div class="timeline-period">随時</div>
                    <div class="timeline-content">
                        <p><strong class="user-label">あなた：</strong> メッセージ確認（日本語でOK）</p>
                        <p><strong class="glow-label">GLOW：</strong> リアルタイムAI翻訳・バイヤー交渉・契約書作成</p>
                        <p><strong class="result-label">結果：</strong> 受注確定</p>
                    </div>
                </div>
                <div class="timeline-item">
                    <div class="timeline-step">ステップ④ 出荷・決済</div>
                    <div class="timeline-period">受注後10-30日</div>
                    <div class="timeline-content">
                        <p><strong class="user-label">あなた：</strong> 商品を準備・梱包</p>
                        <p><strong class="glow-label">GLOW：</strong> 通関手続き・物流手配・代金回収（Trade Assurance）</p>
                        <p><strong class="result-label">結果：</strong> 代金を日本円で入金</p>
                    </div>
                </div>
                <div class="timeline-item">
                    <div class="timeline-step">ステップ⑤ 繰り返し</div>
                    <div class="timeline-period">毎月</div>
                    <div class="timeline-content">
                        <p><strong class="user-label">あなた：</strong> 新商品追加・既存商品改善</p>
                        <p><strong class="glow-label">GLOW：</strong> 継続的なプロモーション・最適化</p>
                        <p><strong class="result-label">結果：</strong> 継続的な受注と売上増加</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- セクション9: CTA 段階 -->
        <section id="section-9" class="section cta-section">
            <h2 class="section-title">さあ、あなたも世界へ。今すぐ始める</h2>
            <div class="cta-container">
                <div class="cta-button-wrapper">
                    <button id="cta-line" class="cta-button cta-stage-1">
                        LINE で無料相談
                        <span class="cta-subtext">約5分</span>
                    </button>
                </div>
                <div class="cta-button-wrapper">
                    <button id="cta-resource" class="cta-button cta-stage-2">
                        資料をもらう
                        <span class="cta-subtext">メール送信</span>
                    </button>
                </div>
                <div class="cta-button-wrapper">
                    <button id="cta-meeting" class="cta-button cta-stage-3">
                        説明会に申し込む
                        <span class="cta-subtext">30分</span>
                    </button>
                </div>
            </div>
            <div class="trust-badges">
                <p class="badge-title">信頼の証</p>
                <div class="badges">
                    <img src="assets/logos/trade-assurance.png" alt="Trade Assurance 認定" class="badge">
                    <img src="assets/logos/alibaba-partner.png" alt="Alibaba.com 公式パートナー" class="badge">
                    <img src="assets/logos/okinawa-support.png" alt="沖縄県支援事業" class="badge">
                </div>
            </div>
            <div class="support-info">
                <p>質問？問い合わせ：<a href="mailto:support@glow-plan-a.com">support@glow-plan-a.com</a></p>
            </div>
        </section>
    </div>

    <!-- モーダル: 資料請求フォーム -->
    <div id="modal-resource" class="modal hidden">
        <div class="modal-content">
            <button class="modal-close">&times;</button>
            <h2>Plan A 資料請求</h2>
            <form id="form-resource" class="form">
                <input type="email" name="email" placeholder="メールアドレス" required>
                <button type="submit" class="btn-submit">送信</button>
            </form>
            <p class="form-message" id="form-resource-message"></p>
        </div>
    </div>

    <!-- モーダル: 説明会申し込みフォーム -->
    <div id="modal-meeting" class="modal hidden">
        <div class="modal-content">
            <button class="modal-close">&times;</button>
            <h2>説明会申し込み</h2>
            <form id="form-meeting" class="form">
                <input type="text" name="name" placeholder="お名前" required>
                <input type="email" name="email" placeholder="メールアドレス" required>
                <input type="tel" name="phone" placeholder="電話番号" required>
                <select name="date" required>
                    <option value="">日時を選択してください</option>
                    <option value="2026-10-05-10:00">10月5日 10:00</option>
                    <option value="2026-10-05-14:00">10月5日 14:00</option>
                    <option value="2026-10-12-10:00">10月12日 10:00</option>
                    <option value="2026-10-12-14:00">10月12日 14:00</option>
                </select>
                <button type="submit" class="btn-submit">申し込む</button>
            </form>
            <p class="form-message" id="form-meeting-message"></p>
        </div>
    </div>

    <script src="scripts.js"></script>
</body>
</html>
```

- [ ] **Step 2: セクション HTML 構造の検証**

```bash
# すべての section ID が揃っているか確認
grep -o 'id="section-[0-9]"' site/go/plan-a/index.html | sort -u
# 期待値: section-1 から section-9 まで

# h2.section-title が各セクションに1つずつあるか確認
grep -c 'class="section-title"' site/go/plan-a/index.html
# 期待値: 9
```

- [ ] **Step 3: Commit**

```bash
git add site/go/plan-a/index.html
git commit -m "html: add Plan A LP skeleton with 9 sections"
```

---

## Task 3: CSS レスポンシブスタイル

**Files:**
- Create: `site/go/plan-a/styles.css`

**Interfaces:**
- 参照：Task 2 HTML セクション構造
- 生成物：レスポンシブ CSS（PC / タブレット / モバイル）

- [ ] **Step 1: 基本カラーパレット・フォント定義**

```css
:root {
    --color-red: #B9502F;
    --color-yellow: #F2B705;
    --color-cream: #FFFBF4;
    --color-glow-orange: #F88800;
    --color-navy: #00335C;
    --color-dark-gray: #333333;
    --color-white: #FFFFFF;
    --color-light-gray: #F5F5F5;

    --font-heading: 'Meiryo', 'Noto Sans JP', sans-serif;
    --font-body: 'Meiryo', 'Noto Sans JP', sans-serif;

    --size-gutter-pc: 40px;
    --size-gutter-mobile: 16px;
    --max-width-pc: 1200px;
    --max-width-tablet: 768px;
    --max-width-mobile: 390px;

    --spacing-xs: 8px;
    --spacing-sm: 16px;
    --spacing-md: 24px;
    --spacing-lg: 40px;
    --spacing-xl: 60px;
}

@media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
        --color-navy: #1a4d7a;
        --color-dark-gray: #e0e0e0;
        --color-white: #f5f5f5;
        --color-light-gray: #2a2a2a;
    }
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: var(--font-body);
    color: var(--color-dark-gray);
    background-color: var(--color-white);
    line-height: 1.6;
}
```

- [ ] **Step 2: タイポグラフィー**

```css
h1 {
    font-family: var(--font-heading);
    font-weight: 700;
    font-size: 2.5rem;
    color: var(--color-navy);
    line-height: 1.3;
    margin-bottom: var(--spacing-md);
}

h2 {
    font-family: var(--font-heading);
    font-weight: 700;
    font-size: 2rem;
    color: var(--color-navy);
    margin-bottom: var(--spacing-lg);
}

h3 {
    font-family: var(--font-heading);
    font-weight: 700;
    font-size: 1.25rem;
    color: var(--color-navy);
    margin-bottom: var(--spacing-sm);
}

.section-title {
    font-size: 2.5rem;
    text-align: center;
    margin-bottom: var(--spacing-xl);
    color: var(--color-navy);
    word-break: auto-phrase;
    text-wrap: balance;
}

p {
    font-size: 1rem;
    line-height: 1.8;
    margin-bottom: var(--spacing-sm);
}

a {
    color: var(--color-glow-orange);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}
```

- [ ] **Step 3: コンテナ・グリッド共通**

```css
.container {
    max-width: var(--max-width-pc);
    margin: 0 auto;
    padding: 0 var(--size-gutter-pc);
}

.section {
    padding: var(--spacing-xl) 0;
    border-bottom: 1px solid #e8e8e8;
}

.section:last-child {
    border-bottom: none;
}

.cards-grid, .walls-grid, .cases-grid, .benefits-grid {
    display: grid;
    gap: var(--spacing-lg);
    margin-top: var(--spacing-lg);
}

/* PC: 3列 */
@media (min-width: 1024px) {
    .cards-grid, .cases-grid, .benefits-grid {
        grid-template-columns: repeat(3, 1fr);
    }
    .walls-grid {
        grid-template-columns: repeat(5, 1fr);
    }
}

/* タブレット: 2列 */
@media (min-width: 768px) and (max-width: 1023px) {
    .cards-grid, .cases-grid, .benefits-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .walls-grid {
        grid-template-columns: repeat(3, 1fr);
    }
}

/* モバイル: 1列 */
@media (max-width: 767px) {
    .cards-grid, .walls-grid, .cases-grid, .benefits-grid {
        grid-template-columns: 1fr;
    }
    
    .container {
        padding: 0 var(--size-gutter-mobile);
    }
    
    h1 {
        font-size: 1.75rem;
    }
    
    h2, .section-title {
        font-size: 1.5rem;
    }
}
```

- [ ] **Step 4: セクション1 Hero**

```css
.hero {
    background: linear-gradient(135deg, var(--color-red), var(--color-yellow));
    background-image: url('assets/images/hero-bg.webp'), linear-gradient(135deg, var(--color-red), var(--color-yellow));
    background-size: cover;
    background-position: center;
    background-blend-mode: darken;
    color: var(--color-white);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 0;
}

.hero-content {
    max-width: 800px;
    padding: 0 var(--size-gutter-pc);
}

.hero h1 {
    color: var(--color-white);
    font-size: 3rem;
    margin-bottom: var(--spacing-md);
    word-break: auto-phrase;
    text-wrap: balance;
}

.hero .subtitle {
    color: var(--color-cream);
    font-size: 1.5rem;
    margin-bottom: var(--spacing-lg);
    font-weight: 400;
}

.hero .description {
    color: var(--color-cream);
    font-size: 1.1rem;
    margin-bottom: var(--spacing-lg);
}

@media (max-width: 767px) {
    .hero h1 {
        font-size: 1.75rem;
    }
    .hero .subtitle {
        font-size: 1.2rem;
    }
}
```

- [ ] **Step 5: セクション2-3 Cards**

```css
.card {
    background-color: rgba(185, 80, 47, 0.05);
    border-radius: 12px;
    padding: var(--spacing-lg);
    text-align: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    transition: transform 0.3s, box-shadow 0.3s;
}

.card:hover {
    transform: translateY(-4px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.card-image {
    width: 100%;
    height: 300px;
    object-fit: cover;
    border-radius: 8px;
    margin-bottom: var(--spacing-md);
}

.card h3 {
    margin-bottom: var(--spacing-sm);
}

/* 5つの壁: アイコン付き */
.wall-card {
    background-color: rgba(242, 183, 5, 0.08);
    border-left: 4px solid var(--color-yellow);
    padding: var(--spacing-md);
    border-radius: 8px;
    text-align: center;
}

.wall-icon {
    width: 48px;
    height: 48px;
    margin: 0 auto var(--spacing-md);
    display: block;
}

.wall-card h3 {
    color: var(--color-red);
    margin-bottom: var(--spacing-sm);
}
```

- [ ] **Step 6: セクション4 信頼・セクション5 仕組み**

```css
.trust-grid, .mechanism-grid {
    display: grid;
    gap: var(--spacing-xl);
    align-items: center;
}

@media (min-width: 1024px) {
    .trust-grid, .mechanism-grid {
        grid-template-columns: 1fr 1fr;
    }
}

@media (max-width: 1023px) {
    .trust-grid, .mechanism-grid {
        grid-template-columns: 1fr;
    }
}

.profile-image {
    width: 200px;
    height: 200px;
    border-radius: 50%;
    object-fit: cover;
    margin-bottom: var(--spacing-md);
}

.trust-profile {
    text-align: center;
}

.trust-profile .title {
    color: var(--color-glow-orange);
    font-weight: 600;
    margin-bottom: var(--spacing-sm);
}

.trust-profile blockquote {
    font-size: 1.1rem;
    font-style: italic;
    color: var(--color-navy);
    border-left: 4px solid var(--color-red);
    padding-left: var(--spacing-md);
    margin-top: var(--spacing-lg);
}

.mechanism-flow {
    display: flex;
    justify-content: space-around;
    align-items: center;
    margin-bottom: var(--spacing-xl);
    flex-wrap: wrap;
    gap: var(--spacing-md);
}

.flow-item {
    background-color: rgba(185, 80, 47, 0.1);
    padding: var(--spacing-md);
    border-radius: 8px;
    text-align: center;
    min-width: 120px;
}

.flow-label {
    font-size: 0.9rem;
    color: var(--color-red);
    display: block;
    margin-bottom: 8px;
}

.flow-value {
    font-weight: 700;
    font-size: 1.3rem;
    color: var(--color-navy);
}

.flow-arrow {
    font-size: 2rem;
    color: var(--color-glow-orange);
}
```

- [ ] **Step 7: セクション8 タイムライン**

```css
.timeline {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
}

.timeline-item {
    background-color: var(--color-cream);
    border-left: 4px solid var(--color-red);
    padding: var(--spacing-lg);
    border-radius: 8px;
}

.timeline-step {
    font-weight: 700;
    color: var(--color-navy);
    font-size: 1.2rem;
    margin-bottom: var(--spacing-sm);
}

.timeline-period {
    font-size: 0.9rem;
    color: var(--color-glow-orange);
    margin-bottom: var(--spacing-sm);
}

.timeline-content {
    display: grid;
    gap: var(--spacing-sm);
}

.user-label {
    color: var(--color-red);
    font-weight: 600;
}

.glow-label {
    color: var(--color-glow-orange);
    font-weight: 600;
}

.result-label {
    color: #4caf50;
    font-weight: 600;
}
```

- [ ] **Step 8: セクション9 CTA・ボタン**

```css
.btn, .cta-button {
    padding: 12px 24px;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
}

.btn-primary {
    background-color: var(--color-red);
    color: var(--color-white);
}

.btn-primary:hover {
    background-color: #8b3d25;
    transform: scale(1.05);
}

.cta-section {
    background-color: var(--color-light-gray);
    text-align: center;
}

.cta-container {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    max-width: 600px;
    margin: 0 auto var(--spacing-xl);
}

.cta-button {
    padding: 20px 40px;
    font-size: 1.1rem;
    border-radius: 12px;
    color: var(--color-white);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.3s;
}

.cta-stage-1 {
    background-color: var(--color-red);
}

.cta-stage-1:hover {
    background-color: #8b3d25;
}

.cta-stage-2 {
    background-color: #c67342;
}

.cta-stage-2:hover {
    background-color: #a85a30;
}

.cta-stage-3 {
    background-color: var(--color-glow-orange);
}

.cta-stage-3:hover {
    background-color: #d97700;
}

.cta-subtext {
    font-size: 0.85rem;
    opacity: 0.9;
}

.trust-badges {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-md);
}

.badges {
    display: flex;
    justify-content: center;
    gap: var(--spacing-lg);
    flex-wrap: wrap;
}

.badge {
    max-width: 150px;
    height: auto;
}

.support-info {
    margin-top: var(--spacing-xl);
    font-size: 0.95rem;
    color: var(--color-dark-gray);
}

/* モーダル */
.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal.hidden {
    display: none;
}

.modal-content {
    background-color: var(--color-white);
    border-radius: 12px;
    padding: var(--spacing-xl);
    max-width: 500px;
    width: 90%;
    position: relative;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.modal-close {
    position: absolute;
    top: var(--spacing-md);
    right: var(--spacing-md);
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--color-dark-gray);
}

.form {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    margin-top: var(--spacing-lg);
}

.form input, .form select {
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 8px;
    font-size: 1rem;
    font-family: var(--font-body);
}

.form input:focus, .form select:focus {
    outline: none;
    border-color: var(--color-glow-orange);
    box-shadow: 0 0 0 3px rgba(248, 136, 0, 0.1);
}

.btn-submit {
    background-color: var(--color-glow-orange);
    color: var(--color-white);
    padding: 12px;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
}

.btn-submit:hover {
    background-color: #d97700;
}

.form-message {
    text-align: center;
    font-size: 0.95rem;
    margin-top: var(--spacing-sm);
}

.form-message.success {
    color: #4caf50;
}

.form-message.error {
    color: #f44336;
}
```

- [ ] **Step 9: Commit**

```bash
git add site/go/plan-a/styles.css
git commit -m "css: add responsive styles for Plan A LP (PC/tablet/mobile)"
```

---

**計画は分割保存します。次の Task 4-9 は別途提供します。**

Plan complete and saved to `docs/superpowers/plans/2026-09-26-plan-a-lp-implementation.md`.

Which execution approach would you prefer?

- **Subagent-driven** - A fresh subagent implements each task and a fresh reviewer checks it. Most thorough; highest cost.
- **Native** - I implement every task myself in this session, then one final review. Fastest; lowest cost; no intermediate gates.

For this plan I recommend **subagent-driven**, because:
- 9 tasks with clear interfaces mean independent reviewers can catch issues early  
- Forms + analytics are integration-heavy and need careful testing at each step
- This prevents cascading failures where a Task 4 (forms) bug breaks Task 5-9

Does the plan capture what you want, and which approach should we use?