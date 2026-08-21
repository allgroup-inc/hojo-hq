import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const notify = require("../apo-kanri/src/apoNotify.js");

const APO = {
  "アポID": "APO-20260814-AB12",
  "日付": "2026-08-14",
  "開始時刻": "14:00",
  "所要分": 60,
  "顧客名": "テスト商店",
  "形式": "訪問",
  "場所またはURL": "那覇市おもろまち",
  "担当営業": "営業一郎",
  "アポ入れ担当": "アポ花子",
  "温度感": "高",
  "ステータス": "スケジュール調整中"
};

test("formatMention: Slack User IDがあれば <@U...>、なければ氏名", () => {
  assert.equal(notify.formatMention("U001", "営業一郎"), "<@U001>");
  assert.equal(notify.formatMention("", "営業一郎"), "営業一郎さん");
  assert.equal(notify.formatMention(null, "営業一郎"), "営業一郎さん");
});

test("buildNewAppointmentMessage: 日時・顧客名・形式・場所・温度感・担当が入る", () => {
  const msg = notify.buildNewAppointmentMessage(APO, "<@U001>");
  assert.ok(msg.includes("新規アポ"));
  assert.ok(msg.includes("2026-08-14"));
  assert.ok(msg.includes("14:00"));
  assert.ok(msg.includes("テスト商店"));
  assert.ok(msg.includes("訪問"));
  assert.ok(msg.includes("那覇市おもろまち"));
  assert.ok(msg.includes("温度感: 高"));
  assert.ok(msg.includes("<@U001>"));
});

test("buildChangeMessage: 差分が本文に入る", () => {
  const msg = notify.buildChangeMessage(APO, "開始時刻: 10:00→14:00", "<@U001>");
  assert.ok(msg.includes("アポ変更"));
  assert.ok(msg.includes("開始時刻: 10:00→14:00"));
  assert.ok(msg.includes("テスト商店"));
});

test("buildCancelMessage: キャンセル種別が本文に入る", () => {
  const msg = notify.buildCancelMessage(APO, "差し戻し", "<@U001>");
  assert.ok(msg.includes("差し戻し"));
  assert.ok(msg.includes("テスト商店"));
});

test("buildSignupMessage: 申込の祝いと顧客名が入る", () => {
  const msg = notify.buildSignupMessage(APO, "<@U001>");
  assert.ok(msg.includes("申込"));
  assert.ok(msg.includes("テスト商店"));
});

test("buildDelayMessage: 遅れ分数と後続アポ一覧・各行のアポ入れ担当メンションが入る", () => {
  const targets = [
    Object.assign({}, APO, { "開始時刻": "15:00", "顧客名": "後続商事" }),
    Object.assign({}, APO, { "開始時刻": "17:00", "顧客名": "次々物産", "アポ入れ担当": "両方次郎" })
  ];
  const mentionResolver = (name) => (name === "アポ花子" ? "<@U002>" : name + "さん");
  const msg = notify.buildDelayMessage("営業一郎", 30, targets, mentionResolver);
  assert.ok(msg.includes("営業一郎"));
  assert.ok(msg.includes("+30分"));
  assert.ok(msg.includes("15:00 後続商事"));
  assert.ok(msg.includes("17:00 次々物産"));
  assert.ok(msg.includes("<@U002>"));
  assert.ok(msg.includes("両方次郎さん"));
});

test("buildSubstituteSection: 空き営業を前後の場所+Googleマップリンク付きで列挙する", () => {
  const candidates = [
    {
      owner: "営業二郎",
      before: { "開始時刻": "13:00", "場所またはURL": "那覇市おもろまち", "形式": "訪問" },
      after: { "開始時刻": "16:00", "場所またはURL": "浦添市", "形式": "訪問" }
    },
    { owner: "営業三郎", before: null, after: null }
  ];
  const section = notify.buildSubstituteSection(candidates);
  assert.ok(section.includes("代打候補"));
  assert.ok(section.includes("営業二郎"));
  assert.ok(section.includes("13:00"));
  assert.ok(section.includes("https://www.google.com/maps/search/?api=1&query="));
  assert.ok(section.includes(encodeURIComponent("那覇市おもろまち")));
  assert.ok(section.includes("営業三郎"));
  assert.ok(section.includes("この日の他アポなし"));
});

test("buildSubstituteSection: オンラインの前後アポには地図リンクを付けない", () => {
  const candidates = [
    { owner: "営業二郎", before: { "開始時刻": "13:00", "場所またはURL": "https://zoom.us/j/123", "形式": "オンライン" }, after: null }
  ];
  const section = notify.buildSubstituteSection(candidates);
  assert.ok(!section.includes("google.com/maps"));
  assert.ok(section.includes("オンライン"));
});

test("buildSubstituteSection: 場所名のSlackメタ文字(| < > &)をエスケープしてリンクを壊さない", () => {
  const candidates = [
    { owner: "営業二郎", before: { "開始時刻": "13:00", "場所またはURL": "県庁前ビル3F|会議室A&B <西口>", "形式": "訪問" }, after: null }
  ];
  const section = notify.buildSubstituteSection(candidates);
  assert.ok(section.includes("県庁前ビル3F¦会議室A&amp;B &lt;西口&gt;"));
  assert.ok(!section.includes("会議室A&B"));
});

test("buildSubstituteSection: 候補0件なら空き営業なしの文面、最大5名まで", () => {
  assert.ok(notify.buildSubstituteSection([]).includes("空いている営業がいません"));
  const many = Array.from({ length: 8 }, (_, i) => ({ owner: "営業" + i, before: null, after: null }));
  const section = notify.buildSubstituteSection(many);
  assert.ok(section.includes("営業4"));
  assert.ok(!section.includes("営業5"));
});

test("buildDelayMessage: 後続アポ0件でも成立する文面を返す", () => {
  const msg = notify.buildDelayMessage("営業一郎", 15, [], () => "");
  assert.ok(msg.includes("+15分"));
  assert.ok(msg.includes("影響するアポはありません"));
});
