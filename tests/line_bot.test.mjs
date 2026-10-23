// LINE会話ボット(gas/line-bot)v1.8 のテスト。
// GASの各サービス(キャッシュ・シート・LINE送信・メール)を偽物に置き換え、
// 実際のメッセージの流れで「同じ記入依頼が繰り返されない」ことを確かめる。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const SRC = ["Template.gs", "Code.gs"].map((f) =>
  readFileSync(new URL(`../gas/line-bot/${f}`, import.meta.url), "utf8"),
);

function makeBot(extra = {}) {
  const props = { LINE_CHANNEL_ACCESS_TOKEN: "x", ...extra };
  const cacheStore = new Map();
  const rows = [];
  const replies = [];
  const mails = [];
  const ctx = {
    console,
    JSON,
    Date,
    CacheService: {
      getScriptCache: () => ({
        get: (k) => (cacheStore.has(k) ? cacheStore.get(k) : null),
        put: (k, v) => cacheStore.set(k, String(v)),
        remove: (k) => cacheStore.delete(k),
      }),
    },
    PropertiesService: {
      getScriptProperties: () => ({ getProperty: (k) => (k in props ? props[k] : null) }),
    },
    SpreadsheetApp: {
      getActiveSpreadsheet: () => ({
        getSheetByName: () => ({ appendRow: (r) => rows.push(r) }),
      }),
    },
    UrlFetchApp: {
      fetch: (url, opt) => {
        if (url.includes("/profile/")) return { getContentText: () => '{"displayName":"テスト太郎"}' };
        if (url.includes("/reply")) replies.push(JSON.parse(opt.payload).messages[0]);
        return { getContentText: () => "{}", getResponseCode: () => 200 };
      },
    },
    MailApp: { sendEmail: (m) => mails.push(m) },
    Utilities: { formatDate: () => "2026-10-17 10:00" },
    ContentService: {
      createTextOutput: (s) => ({ setMimeType: () => s }),
      MimeType: { JSON: "json" },
    },
  };
  vm.createContext(ctx);
  SRC.forEach((code) => vm.runInContext(code, ctx));
  const send = (text, userId = "U123") =>
    ctx.doPost({
      postData: {
        contents: JSON.stringify({
          events: [{ type: "message", message: { type: "text", text }, source: { userId }, replyToken: "r", timestamp: 1792200000000 }],
        }),
      },
    });
  const last = () => replies[replies.length - 1].text;
  return { ctx, send, rows, replies, mails, last };
}

const TEMPLATE_EMPTY = "【会社情報登録】\n会社名：\n代表者名：\n担当者名：\n電話番号：\nメールアドレス：\n所在地：";

test("テンプレをそのまま記入して送れば、1回で登録される(従来どおり)", () => {
  const b = makeBot();
  b.send("【会社情報登録】\n会社名：株式会社テスト\n代表者名：山田太郎\n担当者名：\n電話番号：098-000-0000\nメールアドレス：\n所在地：那覇市");
  assert.equal(b.rows.length, 1);
  assert.equal(b.rows[0][3], "株式会社テスト");
  assert.equal(b.rows[0][4], "山田太郎");
  assert.equal(b.rows[0][5], "那覇市");
  assert.match(b.rows[0][15], /TEL: 098-000-0000/);
  assert.match(b.last(), /登録ありがとうございます/);
});

test("「代表者：」「社名 ◯◯」の書き方でも読み取り、テンプレの記入依頼を返さない", () => {
  const b = makeBot();
  b.send("【会社情報登録】\n社名 株式会社ミナト\n代表者：比嘉花子");
  assert.equal(b.rows.length, 1);
  assert.equal(b.rows[0][3], "株式会社ミナト");
  assert.equal(b.rows[0][4], "比嘉花子");
  assert.doesNotMatch(b.last(), /もう一度送信/);
});

test("値を次の行に書いても読み取れる。空欄の項目は次の項目名を値にしない", () => {
  const b = makeBot();
  b.send("【会社情報登録】\n会社名：\n有限会社うみかぜ\n代表者名：\n金城一郎\n担当者名：\n電話番号：");
  assert.equal(b.rows.length, 1);
  assert.equal(b.rows[0][3], "有限会社うみかぜ");
  assert.equal(b.rows[0][4], "金城一郎");
  assert.equal(b.rows[0][15], "");
});

test("見出しなしで「会社名：◯◯」と返信されても登録として受ける(テンプレを再送しない)", () => {
  const b = makeBot();
  b.send("会社名：株式会社サンゴ\n代表取締役 宮城次郎");
  assert.equal(b.rows.length, 1);
  assert.equal(b.rows[0][3], "株式会社サンゴ");
  assert.equal(b.rows[0][4], "宮城次郎");
});

test("会社名だけ書かれていたら、代表者名だけを聞き直す。会社名はもう聞かない", () => {
  const b = makeBot();
  b.send("【会社情報登録】\n会社名：株式会社テスト\n代表者名：\n電話番号：090-1111-2222");
  assert.equal(b.rows.length, 0);
  assert.match(b.last(), /株式会社テスト/);
  assert.match(b.last(), /代表者名」だけ/);
  assert.doesNotMatch(b.last(), /会社名」だけ/);
  b.send("山田太郎");
  assert.equal(b.rows.length, 1);
  assert.equal(b.rows[0][3], "株式会社テスト");
  assert.equal(b.rows[0][4], "山田太郎");
  assert.match(b.rows[0][15], /TEL: 090-1111-2222/);
  assert.match(b.last(), /登録ありがとうございます/);
});

test("空のテンプレを2回送られても、同じ記入依頼は1回だけ。2回目は1問ずつの質問に切り替える", () => {
  const b = makeBot();
  b.send(TEMPLATE_EMPTY);
  const first = b.last();
  assert.match(first, /もう一度送信/);
  b.send(TEMPLATE_EMPTY);
  assert.notEqual(b.last(), first);
  assert.match(b.last(), /会社名」だけ/);
  b.send("株式会社テスト");
  assert.match(b.last(), /代表者名」だけ/);
  b.send("代表者名：山田太郎");
  assert.equal(b.rows.length, 1);
  assert.equal(b.rows[0][4], "山田太郎");
});

test("項目名なしで社名と代表者名を2行で書かれたら、確認してから記録する", () => {
  const b = makeBot();
  b.send("【会社情報登録】\n株式会社テスト\n山田太郎");
  assert.equal(b.rows.length, 0);
  assert.match(b.last(), /よろしいですか/);
  b.send("はい");
  assert.equal(b.rows.length, 1);
  assert.equal(b.rows[0][3], "株式会社テスト");
});

test("「会社情報登録」単体は従来どおり1問ずつの会話になり、項目名つきの答えは値だけ使う", () => {
  const b = makeBot();
  b.send("会社情報登録");
  assert.match(b.last(), /会社名/);
  b.send("会社名：株式会社テスト");
  assert.match(b.last(), /代表者名/);
});

test("ふだんの文(「メールで連絡ください」等)は会社情報として扱わない", () => {
  const b = makeBot();
  b.send("メールで連絡ください");
  b.send("電話番号を教えてください");
  assert.equal(b.rows.length, 0);
  assert.match(b.last(), /メッセージを受け取りました/);
});

test("転送先が設定されていれば、すべてのメッセージを日時・User ID・本文つきでメール転送する", () => {
  const b = makeBot({ FORWARD_EMAILS: "staff@example.com", LINE_CHANNEL_ACCESS_TOKEN: "x" });
  b.send("こんにちは、資料がほしいです", "Uabc");
  assert.equal(b.mails.length, 1);
  assert.equal(b.mails[0].to, "staff@example.com");
  assert.match(b.mails[0].body, /送信日時：2026-10-17 10:00/);
  assert.match(b.mails[0].body, /送信者：Uabc/);
  assert.match(b.mails[0].body, /こんにちは、資料がほしいです/);
  assert.match(b.last(), /メッセージを受け取りました/);
});

test("転送先が未設定なら転送しない(返信は止めない)", () => {
  const b = makeBot({ LINE_CHANNEL_ACCESS_TOKEN: "x" });
  b.send("こんにちは");
  assert.equal(b.mails.length, 0);
  assert.equal(b.replies.length, 1);
});
