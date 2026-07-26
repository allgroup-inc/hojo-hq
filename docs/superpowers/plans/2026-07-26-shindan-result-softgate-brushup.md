# 診断結果フロー ブラッシュアップ(ソフトゲート版)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** もらいわすれ堂の診断結果画面に「合計サマリー」と「ソフトゲート型のLINEごほうびボックス」を追加し、見やすく・迷わないデザインへ整える。

**Architecture:** 集計は `logic.js` の純粋関数 `summarize()` に切り出して Node の eval で単体テストする。UI は `shindan/index.html` の結果描画に配線し、正確性(金額を出さない・断定しない)と締切ルール(約1か月前から)を守る。制度カードは全件表示のまま(ソフトゲート)。

**Tech Stack:** 静的HTML + 素のJS(UMD `window.FGShindan`)/ Node `--test`(eval)/ Python 検証スクリプト(LP・seido・jukyu)。ビルド無し。

## Global Constraints

- 金額の数値は一切表示しない(合計金額UIを置かない)。将来の別タスク。
- 個人情報(名前・住所・電話・年齢)をサイトで取得しない。診断回答は localStorage のみ・送信しない。
- 断定表現禁止。「対象の**可能性**」で統一。禁止語(`必ずもらえる/絶対/審査なし/誰でももらえる/100%/確実にもらえる/無条件で支給`)を可視テキストに入れない。
- 締切表現は「**締切の約1か月前から**」。「**7日前**」表現は使わない(誤り)。
- LINEリンクは直貼り `lin.ee` 禁止。必ず `/go/<channel>/` 経由(診断=`fg-shindan`、受給報告=`fg-jukyu`)。
- `site/fukugiiro/index.html` は 50KB 未満(`check_lp_fukugiiro.py` 予算)。全 `site/fukugiiro/**/*.html` に `lang="ja"`/`viewport`/`<title>`/`name="description"` を維持。
- 制度カードは全件表示(モザイク・全ゲートにしない)。
- 検証ゲート(すべて緑必須): `node --test tests/shindan.test.mjs` / `python3 scripts/check_lp_fukugiiro.py` / `python3 scripts/validate_fukugiiro.py --self-test` / `python3 scripts/generate_jukyu_counter.py --self-test`。
- ブランチ: `claude/okinawa-disposable-income-plan-axxs6v`(PR #6 に積み増し)。コミットは `Claude <noreply@anthropic.com>`。

---

### Task 1: `summarize()` を logic.js に追加(集計の純粋関数・TDD)

**Files:**
- Modify: `site/fukugiiro/shindan/logic.js`(api を拡張、`matchSeido` の下・`var api =` 付近)
- Test: `tests/shindan.test.mjs`(末尾にテスト追加)

**Interfaces:**
- Consumes: `matchSeido(items, answers) -> [{item, likelihood}]`(既存, `likelihood` は `"高"|"中"`)
- Produces: `summarize(results) -> { total: number, high: number, mid: number }`
  - `total` = `results.length`、`high` = likelihood==="高" の件数、`mid` = likelihood==="中" の件数。

- [ ] **Step 1: 失敗するテストを書く**

`tests/shindan.test.mjs` の require 行を差し替え、ファイル末尾にテストを追加する。

require 行(9行目)を次に変更:
```js
const { matchSeido, summarize } = require("../site/fukugiiro/shindan/logic.js");
```

末尾に追加:
```js
test("summarize: 高/中/合計を正しく数える", () => {
  const rs = [
    { item: { name: "A" }, likelihood: "高" },
    { item: { name: "B" }, likelihood: "高" },
    { item: { name: "C" }, likelihood: "中" },
  ];
  assert.deepEqual(summarize(rs), { total: 3, high: 2, mid: 1 });
});

test("summarize: 空配列はすべて0", () => {
  assert.deepEqual(summarize([]), { total: 0, high: 0, mid: 0 });
});

test("summarize: matchSeido の実結果と整合(合計=件数)", () => {
  const rs = matchSeido(items, { municipality: "那覇市", children: 2, childAges: ["小学生"], lifeEvents: ["入園・入学"] });
  const s = summarize(rs);
  assert.equal(s.total, rs.length);
  assert.equal(s.high + s.mid, rs.length);
});
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `node --test tests/shindan.test.mjs`
Expected: FAIL(`summarize is not a function` 等)

- [ ] **Step 3: 最小実装を書く**

`site/fukugiiro/shindan/logic.js` の `var api = { matchSeido: matchSeido };`(76行目付近)の直前に関数を追加し、api を拡張する。

`matchSeido` の閉じ `}`(74行目)の後、`var api` の前に挿入:
```js
  function summarize(results) {
    var high = 0, mid = 0;
    for (var i = 0; i < results.length; i++) {
      if (results[i].likelihood === "高") high++;
      else if (results[i].likelihood === "中") mid++;
    }
    return { total: results.length, high: high, mid: mid };
  }
```

api 行を差し替え:
```js
  var api = { matchSeido: matchSeido, summarize: summarize };
```

- [ ] **Step 4: テストを実行して通過を確認**

Run: `node --test tests/shindan.test.mjs`
Expected: PASS(既存9件 + 新規3件)

- [ ] **Step 5: コミット**

```bash
git add site/fukugiiro/shindan/logic.js tests/shindan.test.mjs
git commit -m "feat(fukugiiro): 診断集計 summarize() を追加(高/中/合計)"
```

---

### Task 2: 合計サマリーカードを結果画面に配線(金額なし)

**Files:**
- Modify: `site/fukugiiro/shindan/index.html`(結果描画 `rs.length > 0` ブロック内=249行目付近の直後、CSS=`<style>`内)

**Interfaces:**
- Consumes: `window.FGShindan.summarize(rs) -> {total, high, mid}`(Task 1)

- [ ] **Step 1: CSS を追加**

`<style>` 内(`.result-card` の定義付近、32行目付近)に追記:
```css
.summary-card{background:linear-gradient(180deg,#F9EDE3,#fff);border:2px solid var(--fg-accent);border-radius:12px;padding:18px 16px;margin:6px 0 18px;text-align:center}
.summary-card .total{font-size:1.15rem;font-weight:800;color:var(--fg-primary)}
.summary-card .total b{font-size:1.7rem;margin:0 2px}
.summary-card .breakdown{font-size:.95rem;margin-top:4px}
.summary-card .breakdown .hi{color:#0f5138;font-weight:700}
.summary-card .breakdown .mi{color:#7a5b00;font-weight:700}
```

- [ ] **Step 2: サマリーカードを配線**

`app.appendChild(h("p", {class:"note", text:"ぜんぶ一度にやらなくて大丈夫です。..."}));`(249行目)の直後、`}`(250行目, `if (rs.length > 0)` の閉じ)の**前**に挿入:
```js
        var sum = window.FGShindan.summarize(rs);
        var summary = h("div", {class:"summary-card"});
        var total = h("p", {class:"total"});
        total.innerHTML = "合計 <b>" + sum.total + "</b> 件が対象の可能性";
        summary.appendChild(total);
        var bd = h("p", {class:"breakdown"});
        bd.innerHTML = "可能性 <span class='hi'>高 " + sum.high + "件</span> ・ <span class='mi'>中 " + sum.mid + "件</span>";
        summary.appendChild(bd);
        summary.appendChild(h("p", {class:"note", text:"「対象の可能性」のご案内です。受給の可否は各窓口の判断となります。"}));
        app.appendChild(summary);
```

- [ ] **Step 3: 検証(eval・LP)を実行**

Run: `node --test tests/shindan.test.mjs && python3 scripts/check_lp_fukugiiro.py`
Expected: eval PASS / LP `エラー 0`

- [ ] **Step 4: 目視確認(スクリーンショット)**

Run(公開構成を再現して撮影):
```bash
rm -rf site/data && cp -r data site/data
(cd site && python3 -m http.server 8137 >/dev/null 2>&1 &)
sleep 1
CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
"$CHROME" --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --hide-scrollbars --force-device-scale-factor=1 --virtual-time-budget=5000 --window-size=460,2200 --screenshot=/tmp/shindan_q1.png "http://localhost:8137/fukugiiro/shindan/"
pkill -f "http.server 8137"; rm -rf site/data
```
確認: 診断は Q1 から始まるため、サマリーは診断完了後にのみ表示される。結果画面の目視は Task 4 の通し撮影で行う(ここではビルド破壊が無いことの確認まで)。

- [ ] **Step 5: コミット**

```bash
git add site/fukugiiro/shindan/index.html
git commit -m "feat(fukugiiro): 診断結果に合計サマリーカードを追加(件数・高/中内訳・金額なし)"
```

---

### Task 3: LINEごほうびボックスをソフトゲート型に刷新

**Files:**
- Modify: `site/fukugiiro/shindan/index.html`(291–299行目付近の `lineBox` 構築部)

**Interfaces:** なし(DOM文言のみ)

- [ ] **Step 1: lineBox の中身を差し替え**

現在の `lineBox.appendChild(...)` 群(293–294行目の見出し2行)を次に置換。`lineUrl`(291行目)と `lineBtn`(295–298行目)、末尾の匿名注記(299行目)はそのまま残す。

293–294行目を次に置換:
```js
      lineBox.appendChild(h("p", {style:"font-weight:700;margin-bottom:4px;font-size:1.05rem", text:"この結果、もらい忘れないために"}));
      lineBox.appendChild(h("p", {class:"note", style:"margin-bottom:10px", text:"LINEに登録すると、次の3つを受け取れます(制度の一覧は登録なしでもぜんぶ見られます)。"}));
      var rewards = h("ul", {style:"list-style:none;text-align:left;max-width:420px;margin:0 auto 12px;padding:0"});
      ["⏰ この制度の締切を、締切の約1か月前からお知らせ","🆕 あなたの条件に合う新しい制度が増えたらお知らせ","🖨 申請準備シート(持ち物リスト)をまとめて受け取る"].forEach(function(t){
        rewards.appendChild(h("li", {style:"padding:6px 0;border-bottom:1px solid #cfe9d8", text:t}));
      });
      lineBox.appendChild(rewards);
```

- [ ] **Step 2: 締切表現・go-link・禁止語を検証**

Run:
```bash
grep -n "7日" site/fukugiiro/shindan/index.html || echo "OK: no 7日前 expression"
grep -n "lin.ee/" site/fukugiiro/shindan/index.html | grep -v "go/" || echo "OK: no direct lin.ee"
python3 scripts/check_lp_fukugiiro.py
node --test tests/shindan.test.mjs
```
Expected: 「OK: no 7日前」「OK: no direct lin.ee」/ LP `エラー 0` / eval PASS

- [ ] **Step 3: コミット**

```bash
git add site/fukugiiro/shindan/index.html
git commit -m "feat(fukugiiro): 診断結果のLINE導線をソフトゲート型に刷新(制度は全件表示・おまけ3点を解放)"
```

---

### Task 4: デザイン・ブラッシュアップ(見やすさ・打ちやすさ)+ 通し目視 + 全CI

**Files:**
- Modify: `site/fukugiiro/shindan/index.html`(`<style>` 内)

**Interfaces:** なし(CSSのみ)

- [ ] **Step 1: 具体的なCSS改善を適用**

`<style>` 内の該当セレクタを次のように調整(存在すれば値を更新、無ければ追記):
```css
/* 結果カードの余白と視線誘導を強める */
.result-card{padding:18px 16px;margin-bottom:16px}
.result-card h3{font-size:1.1rem;line-height:1.35;margin:2px 0 6px}
.lk{font-size:.82rem;padding:2px 12px}
/* タップ領域を確実に44px以上に */
.markbtn{min-height:44px}
.result-card a{display:inline-block;min-height:32px;line-height:1.9}
/* 「まずはこの1件」を目立たせて迷わせない */
.first-badge{font-size:.82rem;padding:2px 12px}
/* 制度カード同士の区切りを明確に */
.result-card + .result-card{margin-top:0}
```

- [ ] **Step 2: 通しで結果画面を撮影(手動操作をスクリプト化)**

Run(診断を自動回答して結果画面を出し、撮影):
```bash
rm -rf site/data && cp -r data site/data
(cd site && python3 -m http.server 8137 >/dev/null 2>&1 &)
sleep 1
CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
cat > /tmp/shot.js <<'EOF'
// localStorage に回答を入れて resume で結果画面を直接開く
EOF
# 診断結果は resume=1 で localStorage の fg_shindan_answers から復元される。
# 事前に回答を注入するため、data URL 経由ではなくクエリ resume を使う簡易確認に留め、
# 撮影は结果までクリック操作が要るため、目視は開発者が手動で1回通すことを推奨。
"$CHROME" --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --hide-scrollbars --force-device-scale-factor=1 --virtual-time-budget=4000 --window-size=460,1400 --screenshot=/tmp/shindan_top.png "http://localhost:8137/fukugiiro/shindan/"
pkill -f "http.server 8137"; rm -rf site/data
```
確認: 崩れ・はみ出し・タップ領域が無いか。結果画面の通し確認は、実機/手動で Q1→結果まで1回操作して目視する(この確認結果を PR に添付)。

- [ ] **Step 3: 全CIゲートを実行**

Run:
```bash
python3 scripts/validate_fukugiiro.py --self-test && \
python3 scripts/generate_jukyu_counter.py --self-test && \
python3 scripts/check_lp_fukugiiro.py && \
node --test tests/shindan.test.mjs
```
Expected: すべて緑(seido self-test 6/6・jukyu 9件・LP エラー0・eval 全PASS)

- [ ] **Step 4: `site/data` の後片付けを確認**

Run: `git status --short`
Expected: `site/data/` が出ない(撮影で作った一時コピーは削除済み)。残っていれば `rm -rf site/data`。

- [ ] **Step 5: コミット & push**

```bash
git add site/fukugiiro/shindan/index.html
git commit -m "polish(fukugiiro): 診断結果のデザイン整理(余白・階層・タップ領域44px+)"
git push origin claude/okinawa-disposable-income-plan-axxs6v
```

---

## Self-Review(この計画の点検)

- **Spec coverage**: §2 画面構成①件数フック(既存)/②合計サマリー=Task 2/③制度カード全件=既存維持(変更なし)/④LINEごほうび=Task 3/⑤デザイン刷新=Task 4。§3 正確性=Global Constraints + Task 2(金額なし)。§5 テスト=Task 1(eval)+各Taskの検証。締切ルール=Task 3 Step2。go-link=Task 3 Step2。✅ 網羅。
- **Placeholder scan**: コード提示済み。Task 4 の通し撮影のみ「手動1回」を許容(結果画面はクリック操作が必要なため)。これは意図的な運用注記であり TODO ではない。
- **Type consistency**: `summarize` の戻り値 `{total, high, mid}` は Task 1 定義と Task 2 消費で一致。`window.FGShindan.summarize` 参照名一致。
- **金額の非表示**: Task 2 はサマリーに金額UIを置かない。per-card の既存 `金額: 要確認`(数値でない)は変更対象外。
