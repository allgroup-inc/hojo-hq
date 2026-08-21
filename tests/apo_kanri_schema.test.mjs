import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const schema = require("../apo-kanri/src/schema.js");

test("4タブすべてのシート名とヘッダー定義が存在する", () => {
  assert.equal(schema.STAFF_SHEET_NAME, "スタッフ");
  assert.equal(schema.APPOINTMENT_SHEET_NAME, "アポ予定");
  assert.equal(schema.HISTORY_SHEET_NAME, "変更履歴");
  assert.equal(schema.SETTINGS_SHEET_NAME, "設定");
  [
    schema.STAFF_HEADERS,
    schema.APPOINTMENT_HEADERS,
    schema.HISTORY_HEADERS,
    schema.SETTINGS_HEADERS
  ].forEach((headers) => {
    assert.ok(Array.isArray(headers));
    assert.ok(headers.length > 0);
  });
});

test("各タブのヘッダーに重複列名がない", () => {
  [
    schema.STAFF_HEADERS,
    schema.APPOINTMENT_HEADERS,
    schema.HISTORY_HEADERS,
    schema.SETTINGS_HEADERS
  ].forEach((headers) => {
    assert.equal(new Set(headers).size, headers.length);
  });
});

test("アポ予定はアポIDが先頭列で、必須列がそろっている", () => {
  assert.equal(schema.APPOINTMENT_HEADERS[0], "アポID");
  ["日付", "開始時刻", "所要分", "顧客名", "形式", "場所またはURL",
    "担当営業", "アポ入れ担当", "温度感", "ステータス", "メモ",
    "登録日時", "最終更新日時"].forEach((name) => {
    assert.ok(schema.APPOINTMENT_HEADERS.includes(name), name + " が必要");
  });
});

/* 列の並びそのものを固定する。読み書きはヘッダー名ではなく列位置に依存するため、
   途中に1列挿し込むと既存データが全部ズレる。追加は必ず末尾で、この配列も末尾に足す */
test("アポ予定の列は並び順ごと固定(追加は末尾のみ)", () => {
  assert.deepEqual(schema.APPOINTMENT_HEADERS, [
    "アポID", "日付", "開始時刻", "所要分", "顧客名", "形式", "場所またはURL",
    "担当営業", "アポ入れ担当", "温度感", "ステータス", "メモ",
    "登録日時", "最終更新日時", "顧客ID", "差し戻し理由"
  ]);
});

/* 名寄せキーは当面アセンドの顧客id(軸の裁定①)。KM- は名寄せの親統合で採番が動くため、
   カットオーバーまで焼き付けない。読み取り時に resolve API で引く */
test("名寄せキーの列を持つ。KM-形式の列は今は作らない(採番が動くため)", () => {
  assert.ok(schema.APPOINTMENT_HEADERS.includes("顧客ID"));
  ["KM顧客ID", "KM-ID", "顧客番号"].forEach((premature) => {
    assert.ok(!schema.APPOINTMENT_HEADERS.includes(premature),
      premature + " はカットオーバーまで作らない");
  });
});

test("リード管理の項目は持たない(物件管理システムの領分)", () => {
  ["アポ種別", "紹介元", "電話番号", "架電結果"].forEach((forbidden) => {
    assert.ok(!schema.APPOINTMENT_HEADERS.includes(forbidden),
      forbidden + " は本システムの守備範囲外");
  });
  assert.equal(schema.APPOINTMENT_KINDS, undefined);
});

/* ステータスは5システム共通語彙。言い換え禁止(共通の約束【4】)。
   ここを勝手に増やす・言い換えると、❶❸❹との突き合わせが壊れる */
test("ステータスは5システム共通語彙(言い換え禁止)", () => {
  assert.deepEqual(schema.APPOINTMENT_STATUSES, [
    "スケジュール調整中", "アポ確定",
    "訪問済", "追客中", "申込", "成立", "保全中",
    "差し戻し", "対象外"
  ]);
});

test("❷が書き換えてよいのは自分の持ち場だけ。訪問済以降は❸❹が持つ", () => {
  assert.deepEqual(schema.OWNED_STATUSES,
    ["スケジュール調整中", "アポ確定", "差し戻し", "対象外"]);
  assert.deepEqual(schema.HANDED_OFF_STATUSES,
    ["訪問済", "追客中", "申込", "成立", "保全中"]);
  // 2つを足すと全体になる(どちらにも属さない・両方に属すステータスを作らない)
  assert.deepEqual(
    schema.OWNED_STATUSES.concat(schema.HANDED_OFF_STATUSES).sort(),
    schema.APPOINTMENT_STATUSES.slice().sort());
});

/* 差し戻しの理由は「ステータスの言い換え」ではなく属性として持つ(軸の裁定③)。
   自社都合=他の見込み客に使えたはずの訪問枠を捨てた損失。顧客都合と混ぜると見えない */
test("差し戻し理由は顧客都合/自社都合の2種で、ステータスとは別の列で持つ", () => {
  assert.deepEqual(schema.RETURN_REASONS, ["顧客都合", "自社都合"]);
  assert.ok(schema.APPOINTMENT_HEADERS.includes("差し戻し理由"));
  schema.RETURN_REASONS.forEach((reason) => {
    assert.ok(!schema.APPOINTMENT_STATUSES.includes(reason),
      reason + " をステータスに混ぜない");
  });
});

test("訪問枠が空くのは差し戻し・対象外だけ(調整中は枠を押さえる)", () => {
  assert.deepEqual(schema.SLOT_FREED_STATUSES, ["差し戻し", "対象外"]);
  assert.ok(!schema.SLOT_FREED_STATUSES.includes("スケジュール調整中"));
});

test("スタッフの役割・形式・温度感・履歴操作の選択肢が定義されている", () => {
  assert.deepEqual(schema.STAFF_ROLES, ["アポ入れ", "営業", "両方"]);
  assert.deepEqual(schema.APPOINTMENT_FORMATS, ["訪問", "来店", "オンライン"]);
  assert.deepEqual(schema.TEMPERATURES, ["高", "中", "低"]);
  assert.deepEqual(schema.HISTORY_OPERATIONS, ["新規", "変更", "遅延連絡"]);
});

test("スタッフタブに役割列とメールアドレス列がある(認証と選択肢生成に必須)", () => {
  assert.ok(schema.STAFF_HEADERS.includes("役割"));
  assert.ok(schema.STAFF_HEADERS.includes("メールアドレス"));
  assert.ok(schema.STAFF_HEADERS.includes("Slack User ID"));
});
