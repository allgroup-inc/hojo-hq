# GLOW M&A台帳 Phase 6(電話番号・連絡不要フラグ)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-31-glow-ma-list-enrichment-triangle-review.md` 論点1(優先度:最高)の対応。実リスト(建設業許可業者名簿ベース・福祉総合リスト)を企業マスタへインポートする前に、①架電に必須の「電話番号」を正式列として企業マスタに保持できるようにする、②「連絡不要(DNC)」を受け取った企業への再架電を防ぐため、電話番号が同じ企業(関連会社・家族経営等)へ連絡不要フラグを自動伝播させる仕組みを追加する。

**Architecture:** 伝播ロジック(`propagateDoNotContact`)はNode/GAS両対応のUMD形式プレーンJSとして`glow-ma/src/dedupe.js`に追加し、`node --test`でユニットテストする。GAS専用の`DncRunner.gs`は、既存の`readCompanyRecords_`/`writeCompanyRecords_`(`ImportRunner.gs`)・`readInteractionsByCompanyId_`(`ScoringRunner.gs`)を再定義せずそのまま呼び出す薄いグルーコードとする。

**Tech Stack:** Google Apps Script(V8ランタイム、`LockService`)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの範囲について:** 設計書本体の変更ではなく、三名体制レビュー(`2026-07-31-glow-ma-list-enrichment-triangle-review.md`論点1)への対応。「連絡不要受領」をどう記録として残すか(対応履歴ログの種別追加)と、それに基づく連絡不要フラグの自動伝播までを範囲とする。実リストの許可業種一覧・Tier・仮スコア等の取り込み方針(論点5)は別Planで扱う。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データを一切コミットしない(本Planは実データを一切扱わない)
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する
- 既存の`readCompanyRecords_`/`writeCompanyRecords_`(`ImportRunner.gs`)・`readInteractionsByCompanyId_`(`ScoringRunner.gs`)は再定義しない
- `SheetSetup.gs`の`ensureTab_`・`applyInteractionTypeValidation_`はヘッダー名から列位置を動的に求める実装のため、`COMPANY_MASTER_HEADERS`・`INTERACTION_TYPES`に値を追加するだけでよく、`SheetSetup.gs`自体の変更は不要(確認済み)
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する(Phase 1〜5と同じ扱い)

---

## File Structure

```
glow-ma/src/
  schema.js       — 既存ファイルを修正: COMPANY_MASTER_HEADERSに電話番号・連絡不要を追加、INTERACTION_TYPESに連絡不要受領を追加(Task 1)
  dedupe.js       — 既存ファイルを修正: propagateDoNotContact関数を追加(Task 2)
  ImportRunner.gs   — 既存ファイルを修正: IMPORT_COLUMN_MAPに電話番号を追加、マージ後にpropagateDoNotContactを適用(Task 3)
  DncRunner.gs      — 新規: 連絡不要フラグの同期(GAS専用)(Task 4)
tests/
  glow_ma_schema.test.mjs  — 既存ファイルを修正(Task 1)
  glow_ma_dedupe.test.mjs  — 既存ファイルを修正(Task 2)
glow-ma/README.md    — Phase 6の使い方を追記(Task 5)
```

---

### Task 1: `schema.js` — 電話番号・連絡不要列と連絡不要受領タイプを追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.COMPANY_MASTER_HEADERS`に`"電話番号"`・`"連絡不要"`を含む、`GlowSchema.INTERACTION_TYPES`に`"連絡不要受領"`を含む。Task 3(インポート)・Task 4(同期)・`SheetSetup.gs`(既存・無修正)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs` の末尾に追記:

```js
test("企業マスタに電話番号・連絡不要列が追加されている", () => {
  assert.ok(schema.COMPANY_MASTER_HEADERS.indexOf("電話番号") !== -1);
  assert.ok(schema.COMPANY_MASTER_HEADERS.indexOf("連絡不要") !== -1);
});

test("対応履歴ログの種別に連絡不要受領が追加されている", () => {
  assert.ok(schema.INTERACTION_TYPES.indexOf("連絡不要受領") !== -1);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(いずれの`indexOf`も`-1`)

- [ ] **Step 3: `glow-ma/src/schema.js` を修正**

`COMPANY_MASTER_HEADERS`の`"所在地"`の直後に`"電話番号"`・`"連絡不要"`を追加する(既存の列の並び・列名は変更しない):

```js
  var COMPANY_MASTER_HEADERS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地",
    "電話番号", "連絡不要",
    "流入ルート", "起点担当者_紹介元", "現在ステージ", "提案商品",
    "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容",
    "担当者", "登録日", "備考"
  ];
```

`INTERACTION_TYPES`の配列末尾(`"ナーチャリング配信"`の後)に`"連絡不要受領"`を追加する:

```js
  var INTERACTION_TYPES = [
    "手紙送付", "電話", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領"
  ];
```

**注意:** `COMPANY_MASTER_HEADERS`の列を追加・並び替えすると、既存の`readCompanyRecords_`/`writeCompanyRecords_`(`ImportRunner.gs`)はヘッダー名ベースで動的に読み書きするため影響を受けない。ただし`glow-ma/README.md`の「企業マスタタブに列を手動で追加しないこと」という運用注意はコード側の列(この2列)には該当しない旨、Task 5で明記する。

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト + 新規2テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 企業マスタに電話番号・連絡不要列と連絡不要受領タイプを追加"
```

---

### Task 2: `dedupe.js` — 連絡不要フラグの電話番号ベース伝播

**Files:**
- Modify: `glow-ma/src/dedupe.js`
- Modify: `tests/glow_ma_dedupe.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowDedupe.propagateDoNotContact(records)`: `record[]`(電話番号が一致する企業のいずれかで`連絡不要`が`true`なら、同じ電話番号を持つ全企業の`連絡不要`を`true`にして返す)。Task 3・Task 4が呼び出す

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_dedupe.test.mjs` の末尾に追記:

```js
test("propagateDoNotContact: 同じ電話番号を持つ企業のいずれかが連絡不要ならすべてに伝播する", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "098-000-0001", "連絡不要": true },
    { "企業ID": "C000002", "電話番号": "098-000-0001", "連絡不要": false },
    { "企業ID": "C000003", "電話番号": "098-000-0002", "連絡不要": false }
  ];
  const result = dedupe.propagateDoNotContact(records);
  const find = (id) => result.find((r) => r["企業ID"] === id);
  assert.equal(find("C000001")["連絡不要"], true);
  assert.equal(find("C000002")["連絡不要"], true);
  assert.equal(find("C000003")["連絡不要"], false);
});

test("propagateDoNotContact: 電話番号が空欄の企業同士は連絡不要を伝播しない", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "", "連絡不要": true },
    { "企業ID": "C000002", "電話番号": "", "連絡不要": false }
  ];
  const result = dedupe.propagateDoNotContact(records);
  const find = (id) => result.find((r) => r["企業ID"] === id);
  assert.equal(find("C000002")["連絡不要"], false);
});

test("propagateDoNotContact: 元の配列を書き換えない(非破壊)", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "098-000-0001", "連絡不要": true },
    { "企業ID": "C000002", "電話番号": "098-000-0001", "連絡不要": false }
  ];
  dedupe.propagateDoNotContact(records);
  assert.equal(records[1]["連絡不要"], false);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: FAIL(`dedupe.propagateDoNotContact is not a function`)

- [ ] **Step 3: `glow-ma/src/dedupe.js` に `propagateDoNotContact` を追加**

既存の関数群の後、`api`オブジェクトの直前に追加する:

```js
  function propagateDoNotContact(records) {
    var doNotContactPhones = {};
    (records || []).forEach(function (record) {
      var phone = record["電話番号"];
      if (phone && record["連絡不要"] === true) {
        doNotContactPhones[phone] = true;
      }
    });
    return (records || []).map(function (record) {
      var phone = record["電話番号"];
      if (phone && doNotContactPhones[phone]) {
        var updated = {};
        Object.keys(record).forEach(function (key) { updated[key] = record[key]; });
        updated["連絡不要"] = true;
        return updated;
      }
      return record;
    });
  }
```

`api`オブジェクトに追加する(既存のプロパティはそのまま残し、以下を追記):

```js
    propagateDoNotContact: propagateDoNotContact
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dedupe.test.mjs`
Expected: PASS(既存テスト + 新規3テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dedupe.js tests/glow_ma_dedupe.test.mjs
git commit -m "feat(glow-ma): 電話番号が同じ企業への連絡不要フラグ伝播ロジックを追加"
```

---

### Task 3: `ImportRunner.gs` — 電話番号のインポートとインポート時の連絡不要伝播

**Files:**
- Modify: `glow-ma/src/ImportRunner.gs`

**Interfaces:**
- Consumes: `GlowDedupe.propagateDoNotContact`(Task 2)
- Produces: `importCompaniesFromStaging()`実行時、電話番号が取り込まれ、連絡不要フラグが電話番号ベースで伝播した状態で企業マスタに書き込まれる

- [ ] **Step 1: `glow-ma/src/ImportRunner.gs` を修正**

`IMPORT_COLUMN_MAP`に`"電話番号": "電話番号"`を追加する(実データの見出しが異なる場合は運用時に書き換える前提。既存のコメントの方針と同じ):

```js
var IMPORT_COLUMN_MAP = {
  // 左が企業マスタの列名、右が「インポート待ち」タブの見出し文字列。
  // 実データの見出しに合わせてここを書き換えてから実行する(設計書15章オープンクエスチョン)。
  "会社名": "会社名",
  "法人番号": "法人番号",
  "業種": "業種",
  "規模": "規模",
  "代表者名": "代表者名",
  "代表者年齢": "代表者年齢",
  "所在地": "所在地",
  "電話番号": "電話番号"
};
```

`importCompaniesFromStaging()`内、`GlowDedupe.applyMerges(combined)`の直後に連絡不要フラグの伝播を追加する:

```js
    var combined = existingRecords.concat(newRecords);
    var mergeResult = GlowDedupe.applyMerges(combined);
    var finalRecords = GlowDedupe.propagateDoNotContact(mergeResult.records);
```

(この変更により、後続の`idOccurrences`・`duplicateIds`チェック、`writeCompanyRecords_(companySheet, finalRecords)`はそのまま`finalRecords`を参照するので変更不要。`mergeResult.absorbedCount`のログ出力のみ`mergeResult.absorbedCount`を直接参照するよう確認すること。)

新規インポートされる企業の`"連絡不要"`は、`GlowCsvImport.parseCompanyCsvRow`が明示的にセットしない限り`undefined`になる。`propagateDoNotContact`は`record["連絡不要"] === true`の企業のみを伝播元として扱うため、`undefined`は安全に「連絡不要ではない」として扱われる(Task 2のテストで検証済みの挙動)。

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/ImportRunner.gs /tmp/ImportRunner_check.js && node --check /tmp/ImportRunner_check.js && rm /tmp/ImportRunner_check.js` で構文チェック
2. `GlowDedupe.propagateDoNotContact`の呼び出しが、`glow-ma/src/dedupe.js`の実際の関数シグネチャ(引数1つ、`record[]`を返す)と一致していることを確認する
3. `mergeResult.absorbedCount`を参照しているログ出力行が、変数名変更(`finalRecords`の代入元が`mergeResult.records`から`GlowDedupe.propagateDoNotContact(mergeResult.records)`に変わったこと)の影響を受けていないことを確認する

- [ ] **Step 3: Commit**

```bash
git add glow-ma/src/ImportRunner.gs
git commit -m "feat(glow-ma): インポート時に電話番号を取り込み連絡不要フラグを伝播"
```

---

### Task 4: `DncRunner.gs` — 対応履歴ログからの連絡不要フラグ同期(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/DncRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.COMPANY_MASTER_SHEET_NAME`/`INTERACTION_LOG_SHEET_NAME`(Phase 1)、`readCompanyRecords_`/`writeCompanyRecords_`(`ImportRunner.gs`。**再定義しないこと**)、`readInteractionsByCompanyId_`(`ScoringRunner.gs`。**再定義しないこと**)、`GlowDedupe.propagateDoNotContact`(Task 2)
- Produces: `syncDoNotContactFlags()`関数(引数なし)。対応履歴ログに「連絡不要受領」が記録された企業の連絡不要フラグをTRUEにし、同じ電話番号の企業へ伝播したうえで企業マスタに書き込む

- [ ] **Step 1: `glow-ma/src/DncRunner.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: 連絡不要(DNC)フラグの同期
 * 対応履歴ログに「連絡不要受領」が記録された企業を検出し、企業マスタの
 * 「連絡不要」フラグをTRUEにする。さらに同じ電話番号を持つ他の企業
 * (関連会社・家族経営等)にも連絡不要を伝播させる(GlowDedupe.propagateDoNotContact)。
 *
 * Apps Scriptエディタの関数選択で syncDoNotContactFlags を選び、実行ボタンで
 * 手動実行する。(将来的には日次バッチに組み込むことを想定しているが、
 * トリガー登録自体は本Planの範囲外。)
 */
function syncDoNotContactFlags() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error(
      "他の処理が企業マスタを操作中のため、連絡不要フラグの同期を開始できませんでした。" +
      "しばらく待ってから再実行してください。"
    );
  }
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    if (!companySheet) {
      throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
    }
    var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
    var interactionsByCompanyId = readInteractionsByCompanyId_(logSheet);

    var records = readCompanyRecords_(companySheet);
    var newlyMarkedCount = 0;
    records.forEach(function (record) {
      var interactionRows = interactionsByCompanyId[record["企業ID"]] || [];
      var hasDoNotContactEvent = interactionRows.some(function (row) {
        return row["種別"] === "連絡不要受領";
      });
      if (hasDoNotContactEvent && record["連絡不要"] !== true) {
        record["連絡不要"] = true;
        newlyMarkedCount++;
      }
    });

    var propagated = GlowDedupe.propagateDoNotContact(records);
    writeCompanyRecords_(companySheet, propagated);

    var totalDoNotContactCount = propagated.filter(function (record) {
      return record["連絡不要"] === true;
    }).length;
    Logger.log(
      "連絡不要フラグの同期完了: 対応履歴ログから新規検出 " + newlyMarkedCount + "件 / " +
      "同一電話番号への伝播後の合計 " + totalDoNotContactCount + "件"
    );
  } finally {
    lock.releaseLock();
  }
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/DncRunner.gs /tmp/DncRunner_check.js && node --check /tmp/DncRunner_check.js && rm /tmp/DncRunner_check.js` で構文チェック
2. `readInteractionsByCompanyId_`が`glow-ma/src/ScoringRunner.gs`で定義済みの関数と同じシグネチャ(引数1つ`sheet`、企業IDをキーにした対応履歴ログの配列を返す)であることを確認する
3. `readCompanyRecords_`/`writeCompanyRecords_`が`glow-ma/src/ImportRunner.gs`の定義と一致していることを確認する
4. 対応履歴ログ・企業マスタが共に空(0件)の場合でも、`syncDoNotContactFlags`が例外を投げずに「新規検出0件/合計0件」のログを出して終了することをコードを目でたどって確認する
5. 「連絡不要受領」が対応履歴ログに複数回記録されている企業でも、`hasDoNotContactEvent`が`some`で判定するため二重処理にならないことを確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. テスト用に2社(電話番号を同じにする)を企業マスタに用意し、片方の対応履歴ログに「連絡不要受領」を1件記録する
3. `syncDoNotContactFlags` を実行する
4. 対応履歴ログを記録した企業と、同じ電話番号のもう1社の両方の「連絡不要」列がTRUEになっていることを確認する
5. 再度 `syncDoNotContactFlags` を実行し、ログの「新規検出」件数が0件になる(二重加算されない)ことを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/DncRunner.gs
git commit -m "feat(glow-ma): 対応履歴ログから連絡不要フラグを同期する機能を追加"
```

---

### Task 5: READMEにPhase 6の使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜4の全成果物
- Produces: GLOWチームが電話番号・連絡不要フラグの運用を理解できるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の「## ダッシュボード(Phase 5)」の直後・「## 次のフェーズ」の直前に以下を追記**

```markdown
## 電話番号・連絡不要(DNC)フラグ(Phase 6)

企業マスタに「電話番号」「連絡不要」列を追加した。実リスト(建設業許可業者名簿・
福祉総合リスト等)には「同一連絡先(関連会社・家族経営等で電話番号が同じ)」の
企業が一定数含まれるため、いずれか1社が「連絡不要」と回答した場合、同じ電話番号を
持つ他の企業にも自動で連絡不要フラグを伝播させ、誤って再架電することを防ぐ。

**使い方**

1. 架電の結果「連絡不要」と言われたら、対応履歴ログにその企業の「連絡不要受領」を
   1件記録する(プルダウンから選択)
2. Apps Scriptエディタで `syncDoNotContactFlags` を実行する
3. 対応履歴ログに「連絡不要受領」が記録された企業と、同じ電話番号を持つ他の企業の
   「連絡不要」列がTRUEになる
4. 7000件リストのインポート(`importCompaniesFromStaging`)実行時にも、
   インポート後の企業マスタ全体に対して同じ伝播処理が自動的にかかる

**現時点の制約:**
- 「連絡不要」がTRUEになった企業への架電を実際に止める仕組み(掘り起こしアラート
  からの除外等)は本Phaseの範囲外。運用上は、対応履歴ログ・企業マスタの「連絡不要」
  列を必ず確認してから架電すること
- `syncDoNotContactFlags` は手動実行が前提。日次バッチへの組み込みは今後の課題
- 企業マスタに列を追加する際の一般的な注意(「企業マスタタブに列を手動で追加しないこと」
  という既存の注意書き)は、コード側で定義済みの列(電話番号・連絡不要含む全列)には
  該当しない。あくまでコードで定義されていない列を独自に追加しないこと、という趣旨
```

- [ ] **Step 2: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): 電話番号・連絡不要フラグ(Phase 6)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage**

- `docs/superpowers/specs/2026-07-31-glow-ma-list-enrichment-triangle-review.md` 論点1(電話番号・DNC伝播、優先度:最高)→ Task 1〜4で対応

**Placeholder scan:** TBD/TODO等の記述なし。

**Type consistency:** `GlowDedupe.propagateDoNotContact`の引数・戻り値はTask 2〜4で一致させた。`readInteractionsByCompanyId_`(ScoringRunner.gs)・`readCompanyRecords_`/`writeCompanyRecords_`(ImportRunner.gs)は再定義せず既存のシグネチャをそのまま利用する。`SheetSetup.gs`はヘッダー名ベースの動的実装のため無修正で新列に対応できることを確認済み。`INTERACTION_TYPES`への追加は`applyInteractionTypeValidation_`が動的に反映するため`SheetSetup.gs`の修正不要。
