# 診断結果「申請の次の一歩」ブラッシュアップ Implementation Plan

> **For agentic workers:** インライン実行(コントローラが実装+実機スクリーンショットで目視・セルフリファイン)。

**Goal:** 診断結果カードを「次の一歩を主役・窓口の聞き方が安心・親切で留保付き」に整え、申請の準備をやさしく手助けする。

**Architecture:** `site/fukugiiro/shindan/index.html` の結果描画(表示・文言・CSS)のみ変更。診断ロジック(logic.js)は不変。

**Tech Stack:** 静的HTML+素のJS(`h()` ヘルパ)。ビルド無し。

## Global Constraints

- 断定しない(「もらえます/対象です」禁止)。判定・最終確認は窓口、と明記。金額は出さない(既存の `金額: 要確認` 表記のまま)。
- 公式リンク・準備シート・受給報告導線(`/go/fg-jukyu/`)・締切「約1か月前」表現は維持。「7日前」表現を作らない。
- 禁止語(必ずもらえる/絶対/審査なし/誰でももらえる/100%/確実にもらえる/無条件で支給)を可視文言に入れない。
- 個人情報を新たに取得しない。診断回答・記録は端末内のみ。
- 検証: `python scripts/check_lp_fukugiiro.py`(エラー0)、`node --test tests/shindan.test.mjs`(12/12)、**実機スクリーンショット目視**(結果多い/少ない両方)。
- 変更は `site/fukugiiro/shindan/index.html` のみ。コミット author `Claude <noreply@anthropic.com>`。

---

### Task 1: CSS + 親切メッセージ + 「次の一歩」主役化

**Files:** Modify `site/fukugiiro/shindan/index.html`

- [ ] Step 1: `<style>` に追記
```css
.kind-msg{background:#EAF5F0;border:1px solid #B7E0CF;border-radius:12px;padding:14px 16px;margin:6px 0 16px;color:#0f5138;line-height:1.7;font-size:.95rem}
.next-step{background:#FDF5E6;border-left:5px solid var(--fg-primary);border-radius:8px;padding:12px 14px;margin:10px 0}
.next-step .ns-label{display:inline-block;font-size:.75rem;font-weight:800;color:#fff;background:var(--fg-primary);border-radius:4px;padding:2px 8px;margin-right:6px}
.next-step .ns-body{font-weight:700}
.card-sub{font-size:.82rem;color:var(--fg-muted);margin-top:2px}
```

- [ ] Step 2: 結果ヘッダー直下(summary-card を append した直後、`if (rs.length > 0)` ブロック内の末尾)に親切メッセージを追加
```js
        app.appendChild(h("p", {class:"kind-msg", text:"もらい忘れは、知らなかっただけ。あなたは悪くありません。ぜんぶ一度にやらなくて大丈夫。ひとつずつ、いっしょに進めましょう。"}));
```

- [ ] Step 3: カード描画の順序を「次の一歩 主役」に変更。現状:
```js
        card.appendChild(h("h3", {text: it.name}));
        card.appendChild(h("p", {class:"note", text: it.target_household}));
        card.appendChild(h("p", {class:"note", text:"金額: " + it.amount_note}));
        card.appendChild(h("p", {class:"note", text:"次の一歩: " + it.how_to_apply}));
```
を次に置換(次の一歩を h3 直後の強調ブロックへ、対象・金額は従属 `card-sub` に):
```js
        card.appendChild(h("h3", {text: it.name}));
        var ns = h("div", {class:"next-step"});
        ns.appendChild(h("span", {class:"ns-label", text:"次にやること"}));
        ns.appendChild(h("span", {class:"ns-body", text: it.how_to_apply}));
        card.appendChild(ns);
        card.appendChild(h("p", {class:"card-sub", text:"対象: " + it.target_household}));
        card.appendChild(h("p", {class:"card-sub", text:"金額: " + it.amount_note}));
```

- [ ] Step 4: `python scripts/check_lp_fukugiiro.py`(エラー0)/ `node --test tests/shindan.test.mjs`(12/12)

- [ ] Step 5: コミット `feat(fukugiiro): 診断結果に親切メッセージ+「次にやること」主役表示`

---

### Task 2: 窓口の「聞き方」安心台本 + 留保付き準備ナビ

**Files:** Modify `site/fukugiiro/shindan/index.html`

- [ ] Step 1: `madoguchi`(窓口でのひとこと)の文言を台本+安心に置換。現状:
```js
        card.appendChild(h("div", {class:"madoguchi", text:"窓口でのひとこと: 「" + it.name + "について教えてください」と伝えれば、あとは案内してもらえます。対象かどうか自信がなくても大丈夫です。"}));
```
を次に置換:
```js
        card.appendChild(h("div", {class:"madoguchi", text:"窓口でこう言えばOK:「" + it.name + "について教えてください。対象か不安なのですが大丈夫ですか?」/ 対象かどうかは窓口が判断します。自信がなくて大丈夫です。"}));
```

- [ ] Step 2: 準備シートリンクの後(`要確認` 注記の前後)に、留保付きの後押しを1行追加。`kitLink` を append した直後に:
```js
        card.appendChild(h("p", {class:"note", style:"margin-top:6px", text:"準備の目安がそろったら、お住まいの窓口へ。最終的な受給の可否は窓口で確認されます。"}));
```

- [ ] Step 3: 締切「7日前」表現が無いこと・禁止語が無いことを確認
```bash
grep -n "7日" site/fukugiiro/shindan/index.html || echo "OK no 7日"
python scripts/check_lp_fukugiiro.py
node --test tests/shindan.test.mjs 2>&1 | grep -E "# (pass|fail)"
```

- [ ] Step 4: コミット `feat(fukugiiro): 窓口の聞き方台本を安心化+留保付き準備ナビを追加`

---

### 実機スクリーンショット目視(コントローラ・セルフリファイン)

- [ ] `?resume=1` で結果画面を描画し撮影(結果が多い例=14件、少ない例=5件の2通り)。
- [ ] 確認観点: ①「次にやること」が各カードで一番目立つ ②対象・金額が従属で読みやすい ③窓口台本が自然で断定になっていない ④親切メッセージ・留保文言が過剰でない ⑤崩れ・はみ出し無し・タップ44px+。
- [ ] 崩れ・過剰・分かりにくさがあれば修正して再撮影(セルフリファイン)。
- [ ] 後片付け: `site/data`・`_seed.html` を削除し `git status` クリーン。

---

## Self-Review

- Spec §1.1 次の一歩主役=Task1 Step3。§1.2 窓口台本=Task2 Step1。§1.3 親切+留保=Task1 Step2 / Task2 Step2。§3 守り(断定回避・金額非表示・線引き)=Global Constraints。§4 スクショ=末尾セクション。✅
- Placeholder: 実コード提示済み。
- 一貫性: `.next-step`/`.kind-msg`/`.card-sub`/`.ns-label`/`.ns-body` の CSS(Task1 Step1)と DOM(Task1 Step2/3)一致。
