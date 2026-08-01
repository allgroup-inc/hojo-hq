# GLOW M&A台帳 Phase 9(後継者状況フィールド)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md` 論点2(事業承継トリガー情報の専用フィールド化)に対応する。裁定はベッカイ案(全社一括での精緻化は目指さず、「後継者状況」フィールドを企業マスタに追加。関係構築中以降のみ入力、空欄可)を採用。決算期の自動取得は技術検証が必要なため本Planの範囲外(別途上申)。2026-08-01の三名体制再検証で小柳さんの承認を得た。

**背景**: 後継者不在は沖縄の中小企業で特に多いと言われる課題で、決定的な絞り込み条件になりうる。ただし後継者の有無・株主構成は初回接触時点ではほぼ分からない機微情報であり、全社一括で埋めようとすると「未確認」だらけの空欄列が増えるだけでデータの信頼性を損なう(Phase 5レビューで指摘された表記ゆれ問題と同種)。そのため、「関係構築中」ステージ以降に進んだ企業だけを対象にした軽量フィールドとし、対応履歴ログの自由記述から都度拾って手動転記する運用にする。

**Architecture:** 企業マスタに「後継者状況」列を1つ追加するのみ。値は「あり」「なし」「不明」の3択+空欄可のプルダウン。スコアリング・ダッシュボード集計への自動反映は行わない(論点2の裁定は専用フィールドの新設までであり、スコアへの組み込みは別議論)。

**このPlanの範囲について:** 決算期の自動取得(法人番号からの機械的推定)は別途技術検証が必要なため対象外。後継者状況を用いた自動スコアリング・自動フィルタリング・ダッシュボード集計への反映も対象外(専用フィールドの新設と手動入力のための土台のみ)。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データを一切コミットしない(本Planは実データを一切扱わない)
- `COMPANY_MASTER_HEADERS`への列追加は**必ず配列の末尾に追加する**(Phase 1のスキーマファイル冒頭コメントに明記された既存原則。読み書きはヘッダー名ではなく配列の並び順に依存する実装のため、途中への挿入は既存データの列位置を破壊する)
- 新フィールドの自動入力・自動伝播ロジックは実装しない(Phase 6の電話番号/連絡不要のような伝播ロジックは論点2の裁定に含まれていないため、意図的にスコープ外とする)
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替する

---

## File Structure

```
glow-ma/src/
  schema.js     — 既存ファイルを修正: COMPANY_MASTER_HEADERSに列追加、SUCCESSOR_STATUS_TYPES新設(Task 1)
  SheetSetup.gs   — 既存ファイルを修正: 後継者状況のプルダウン入力規則を追加(Task 2)
tests/
  glow_ma_schema.test.mjs — 既存ファイルを修正(Task 1)
glow-ma/README.md  — Phase 9の使い方を追記(Task 3)
```

---

### Task 1: `schema.js` — 「後継者状況」フィールドを企業マスタに追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.COMPANY_MASTER_HEADERS`の末尾に`"後継者状況"`が追加される。`GlowSchema.SUCCESSOR_STATUS_TYPES`(`["あり", "なし", "不明"]`)が新設される。Task 2(プルダウン設定)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs` の末尾に追記:

```js
test("企業マスタに後継者状況列が末尾に追加されている", () => {
  assert.ok(schema.COMPANY_MASTER_HEADERS.indexOf("後継者状況") !== -1);
  assert.equal(schema.COMPANY_MASTER_HEADERS[schema.COMPANY_MASTER_HEADERS.length - 1], "後継者状況");
});

test("後継者状況の選択肢(SUCCESSOR_STATUS_TYPES)があり/なし/不明の3択である", () => {
  assert.deepEqual(schema.SUCCESSOR_STATUS_TYPES, ["あり", "なし", "不明"]);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`後継者状況`が`COMPANY_MASTER_HEADERS`に含まれない、`schema.SUCCESSOR_STATUS_TYPES`が`undefined`)

- [ ] **Step 3: `glow-ma/src/schema.js` を修正**

`COMPANY_MASTER_HEADERS`配列の末尾(`"電話番号", "連絡不要"`の後)に追加する(**既存の23要素の並び・内容は一切変更しないこと**):

```js
  var COMPANY_MASTER_HEADERS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地",
    "流入ルート", "起点担当者_紹介元", "現在ステージ", "提案商品",
    "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容",
    "担当者", "登録日", "備考",
    "電話番号", "連絡不要", "後継者状況"
  ];
```

`RESPONDENT_TYPES`定義の直後に新しい定数を追加する:

```js
  var SUCCESSOR_STATUS_TYPES = ["あり", "なし", "不明"];
```

`api`オブジェクトに追加する(既存のプロパティは変更しない):

```js
    SUCCESSOR_STATUS_TYPES: SUCCESSOR_STATUS_TYPES,
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト + 新規2テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 企業マスタに後継者状況フィールドを追加"
```

---

### Task 2: `SheetSetup.gs` — 後継者状況のプルダウン入力規則(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.COMPANY_MASTER_HEADERS`・`GlowSchema.SUCCESSOR_STATUS_TYPES`(Task 1)
- Produces: `ensureLedgerTabs()`実行時、企業マスタの「後継者状況」列にプルダウン(あり/なし/不明、空欄可)が設定される

- [ ] **Step 1: `glow-ma/src/SheetSetup.gs` を修正**

`applyDoNotContactValidation_`関数の直後に、新しい検証関数を追加する(既存の`applyRespondentValidation_`と同じパターン):

```js
function applySuccessorStatusValidation_(sheet) {
  var successorStatusColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("後継者状況") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.SUCCESSOR_STATUS_TYPES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, successorStatusColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}
```

`ensureLedgerTabs()`関数内、`applyDoNotContactValidation_(companySheet);`の直後に呼び出しを追加する:

```js
  applySuccessorStatusValidation_(companySheet);
```

ファイル冒頭のコメントに、企業マスタの「後継者状況」列にもプルダウン入力規則を設定する旨を追記する。**既存の`ensureTab_`・他の`apply*Validation_`関数とその呼び出しは変更・削除しないこと。**

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/SheetSetup.gs /tmp/SheetSetup_p9_check.js && node --check /tmp/SheetSetup_p9_check.js && rm /tmp/SheetSetup_p9_check.js` で構文チェック
2. `GlowSchema.COMPANY_MASTER_HEADERS.indexOf("後継者状況")`が期待通りの位置(末尾、24番目)を指すことを確認する
3. `applyDoNotContactValidation_`と同様、`requireValueInList(..., true).setAllowInvalid(false)`は既存カラム(対応相手等)と同じ設定であり、空欄セルを拒否しないことを確認する(既存の`対応相手`列は必須入力ではなく空欄を許容している運用実績があるため、同じ設定を踏襲すれば「空欄可」の要件を満たす)

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. `ensureLedgerTabs` を実行
3. 企業マスタに「後継者状況」列が追加され、プルダウンで「あり」「なし」「不明」を選択できることを確認する
4. セルを空欄のままにしてもエラーにならないことを確認する
5. 既存の企業マスタの他の列・データが壊れていないことを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): 後継者状況列にプルダウン入力規則を追加"
```

---

### Task 3: READMEにPhase 9の使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜2の全成果物
- Produces: GLOWチームが後継者状況フィールドを運用できるようになるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の「## ディールステージ細分化・工程別滞留状況(Phase 8)」の直後・「## 本番投入(実データ運用開始)前チェックリスト」の直前に以下を追記**

```markdown
## 後継者状況フィールド(Phase 9)

三名体制レビュー(`docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md`)
論点2への対応。企業マスタに「後継者状況」列(あり/なし/不明、空欄可)を追加した。

**運用方針:** 全社一括での入力は目指さない。初回接触時点では後継者の有無はほぼ分からない
機微情報であり、無理に埋めようとすると「不明」だらけの空欄列が増えて信頼性を損なう。
**「関係構築中」ステージ以降に進んだ企業だけを対象に**、対応履歴ログの自由記述(内容メモ)
から後継者に関する情報が得られた都度、手動で転記する運用とする。

**使い方**

1. `clasp push` で最新コードを反映する
2. Apps Scriptエディタで `ensureLedgerTabs` を再実行し、企業マスタに「後継者状況」列と
   プルダウンを反映する
3. 「関係構築中」以降の企業について、対応履歴ログの内容メモ等から後継者状況が判明したら、
   企業マスタの「後継者状況」列に手動で記録する

**現時点の制約:**
- スコアリング・ダッシュボード集計への自動反映はしていない(専用フィールドの新設のみ)
- 決算期の自動取得(法人番号からの機械的推定)は技術検証が必要なため未実装。将来の課題として
  `docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md` 論点2を参照
```

- [ ] **Step 2: `glow-ma/README.md` の「## 次のフェーズ」の内容を、Phase 9が実装済みになったことを反映して更新する**

- [ ] **Step 3: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): 後継者状況フィールド(Phase 9)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage:** `docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md` 論点2(採用・ベッカイ案の専用フィールド新設部分)→ Task 1, 2。決算期の自動取得は対象外として明記(裁定どおり)。

**Placeholder scan:** TBD/TODO等の記述なし。

**Type consistency:** `COMPANY_MASTER_HEADERS`への追加は既存の23要素をすべて保持したうえでの末尾追加であり、`ImportRunner.gs`・`dedupe.js`・`ScoringRunner.gs`・`DashboardRunner.gs`等の既存コードはフィールド名(オブジェクトのプロパティ名)でアクセスしており配列長やインデックスに依存していないため、新フィールドを認識しないまま従来通り動作する(Phase 6の電話番号/連絡不要追加時と同じ安全性)。`csvImport.js`の`parseCompanyCsvRow`は返すオブジェクトに「後継者状況」を含めないため、CSVインポートされた企業は常に空欄(未定義)になる。これは意図した挙動であり(全社一括入力を目指さない設計)、既存のCSVインポートの動作に変更はない。
