/* 家計のポっ: 操作デモ(1ファイルHTML)を生成する。
 *
 * 使い方: node scripts/build_apo_demo.mjs
 * 出力:   apo-kanri/dist/apo-kanri-demo.html
 *
 * ねらい: 本番投入(Googleスプレッドシート作成・Slack Webhook・デプロイ)をする前に、
 * 「アポが入った瞬間に登録し、全員が同じ画面を見ながら回す」流れを実機で確かめるため。
 * URLを配るだけで全員が同時に触れる。
 *
 * 忠実さの担保:
 *   - 画面は本物(apoPage.js が生成するHTMLそのもの)
 *   - サーバ処理も本物(ApoRunner.gs をそのまま読み込み、GASのAPIだけ疑似実装に差し替え)
 *   → ダブルブッキング検知・遅れ通知の対象抽出・代打候補・変更差分は、本番と同じコードが動く
 *
 * 疑似にしているのは2つだけ:
 *   - 保存先: スプレッドシートの代わりにブラウザのメモリ(再読込で初期状態に戻る)
 *   - Slack: 送信の代わりに画面下部のパネルへ「こう飛びます」と表示
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const srcDir = join(here, "..", "apo-kanri", "src");
const outPath = join(here, "..", "apo-kanri", "dist", "apo-kanri-demo.html");

const MODULE_FILES = ["schema.js", "resilience.js", "apoAccess.js", "apoCore.js", "apoNotify.js"];
const RUNNER_FILE = "ApoRunner.gs";

function readSrc(name) {
  return readFileSync(join(srcDir, name), "utf8");
}

/* GASのグローバル(SpreadsheetApp等)をブラウザ上で疑似実装し、
   本物の ApoRunner.gs をそのまま動かすための土台。
   tests/apo_kanri_runner.test.mjs のモックと同じ考え方。 */
const HARNESS = String.raw`
(function () {
  "use strict";
  var S = window.ApoSchema;

  function MockSheet(headers) { this.data = [headers.slice()]; }
  MockSheet.prototype.getLastRow = function () { return this.data.length; };
  MockSheet.prototype.appendRow = function (row) { this.data.push(row.slice()); };
  MockSheet.prototype.getRange = function (row, col, numRows, numCols) {
    var sheet = this;
    return {
      getValues: function () {
        var out = [];
        for (var r = 0; r < numRows; r++) {
          var src = sheet.data[row - 1 + r] || [];
          var line = [];
          for (var c = 0; c < numCols; c++) {
            var v = src[col - 1 + c];
            line.push(v === undefined || v === null ? "" : v);
          }
          out.push(line);
        }
        return out;
      },
      setValues: function (values) {
        values.forEach(function (line, r) {
          var target = sheet.data[row - 1 + r] || (sheet.data[row - 1 + r] = []);
          line.forEach(function (value, c) { target[col - 1 + c] = value; });
        });
      },
      setDataValidation: function () { return this; },
      insertCheckboxes: function () { return this; }
    };
  };

  var sheets = {};
  sheets[S.STAFF_SHEET_NAME] = new MockSheet(S.STAFF_HEADERS);
  sheets[S.APPOINTMENT_SHEET_NAME] = new MockSheet(S.APPOINTMENT_HEADERS);
  sheets[S.HISTORY_SHEET_NAME] = new MockSheet(S.HISTORY_HEADERS);
  sheets[S.SETTINGS_SHEET_NAME] = new MockSheet(S.SETTINGS_HEADERS);

  function staffRow(name, slackId, email, role) {
    var row = [];
    row[S.STAFF_HEADERS.indexOf("氏名")] = name;
    row[S.STAFF_HEADERS.indexOf("Slack User ID")] = slackId;
    row[S.STAFF_HEADERS.indexOf("有効")] = true;
    row[S.STAFF_HEADERS.indexOf("メールアドレス")] = email;
    row[S.STAFF_HEADERS.indexOf("役割")] = role;
    return row;
  }
  var DEMO_STAFF = [
    { name: "アポ花子", email: "apo@example.com", role: "アポ入れ" },
    { name: "営業一郎", email: "eigyo1@example.com", role: "両方" },
    { name: "営業二郎", email: "eigyo2@example.com", role: "営業" },
    { name: "営業三郎", email: "eigyo3@example.com", role: "営業" }
  ];
  DEMO_STAFF.forEach(function (s) {
    sheets[S.STAFF_SHEET_NAME].appendRow(staffRow(s.name, "", s.email, s.role));
  });

  function pad2(n) { return String(n).padStart(2, "0"); }
  function todayString() {
    var d = new Date();
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
  }
  function seed(id, time, minutes, customer, format, place, sales, setter, temp, status) {
    var rec = {};
    rec["アポID"] = id; rec["日付"] = todayString(); rec["開始時刻"] = time;
    rec["所要分"] = minutes; rec["顧客名"] = customer; rec["形式"] = format;
    rec["場所またはURL"] = place; rec["担当営業"] = sales; rec["アポ入れ担当"] = setter;
    rec["温度感"] = temp; rec["ステータス"] = status; rec["メモ"] = "";
    rec["登録日時"] = ""; rec["最終更新日時"] = ""; rec["顧客ID"] = "";
    sheets[S.APPOINTMENT_SHEET_NAME].appendRow(
      S.APPOINTMENT_HEADERS.map(function (h) { return rec[h] === undefined ? "" : rec[h]; }));
  }
  // 稽古用の初期データ(すべて架空)
  seed("APO-DEMO-0001", "10:00", 60, "サンプル商店 田中様", "訪問", "那覇市おもろまち1-2-3", "営業一郎", "アポ花子", "高", "確定");
  seed("APO-DEMO-0002", "13:00", 90, "テスト物産 比嘉様", "オンライン", "Zoom", "営業二郎", "アポ花子", "中", "予定");
  seed("APO-DEMO-0003", "15:00", 60, "見本工業 金城様", "来店", "本社2F", "営業一郎", "アポ花子", "低", "予定");
  seed("APO-DEMO-0004", "16:30", 60, "ダミー興産 上原様", "訪問", "浦添市", "営業三郎", "アポ花子", "高", "確定");

  window.__demoUser = DEMO_STAFF[0];
  window.__demoNotifications = [];

  window.SpreadsheetApp = {
    getActiveSpreadsheet: function () {
      return { getSheetByName: function (name) { return sheets[name] || null; } };
    }
  };
  window.Session = {
    getActiveUser: function () { return { getEmail: function () { return window.__demoUser.email; } }; }
  };
  window.PropertiesService = {
    getScriptProperties: function () {
      return { getProperty: function (k) { return k === "SLACK_WEBHOOK_URL" ? "demo://slack" : null; } };
    }
  };
  window.LockService = {
    getScriptLock: function () { return { tryLock: function () { return true; }, releaseLock: function () {} }; }
  };
  window.Utilities = {
    sleep: function () {},
    formatDate: function (date, tz, pattern) {
      return pattern
        .replace("yyyy", date.getFullYear()).replace("MM", pad2(date.getMonth() + 1))
        .replace("dd", pad2(date.getDate())).replace("HH", pad2(date.getHours()))
        .replace("mm", pad2(date.getMinutes())).replace("ss", pad2(date.getSeconds()));
    }
  };
  window.UrlFetchApp = {
    fetch: function (url, opts) {
      var text = JSON.parse(opts.payload).text;
      window.__demoNotifications.unshift({ at: new Date(), text: text });
      window.__renderDemoNotifications && window.__renderDemoNotifications();
      return { getResponseCode: function () { return 200; } };
    }
  };
  window.Logger = { log: function () {} };
  window.HtmlService = {
    createHtmlOutput: function (html) {
      return { setTitle: function () { return this; }, addMetaTag: function () { return this; } };
    }
  };
  window.ApoPage = { buildApoAppHtml: function () { return ""; } };
})();
`;

/* google.script.run の代わり。本物のサーバ関数を非同期で呼ぶ。 */
const RUN_STUB = String.raw`
(function () {
  "use strict";
  function makeRunner() {
    var ok = null, ng = null;
    var proxy = {
      withSuccessHandler: function (fn) { ok = fn; return proxy; },
      withFailureHandler: function (fn) { ng = fn; return proxy; }
    };
    ["getBoard", "getStats", "getFormOptions", "saveAppointment", "updateStatus", "reportDelay"]
      .forEach(function (name) {
        proxy[name] = function () {
          var args = Array.prototype.slice.call(arguments);
          setTimeout(function () {
            try { ok && ok(window[name].apply(null, args)); }
            catch (e) { ng ? ng(e) : console.error(e); }
          }, 60);
        };
      });
    return proxy;
  }
  window.google = { script: {} };
  Object.defineProperty(window.google.script, "run", { get: makeRunner });
})();
`;

/* デモであることの明示・操作者の切替・Slack通知プレビュー */
const DEMO_UI = String.raw`
(function () {
  "use strict";
  var css = document.createElement("style");
  css.textContent = [
    /* デモの帯は常に見えるように上部固定。本体ヘッダーはその下へずらす */
    ".demobar{position:fixed;top:0;left:0;right:0;z-index:60;background:#221D11;color:#fff;font-size:12px;padding:8px 16px;display:flex;align-items:center;gap:8px}",
    ".demobar b{color:#F6C83E;flex:none}",
    ".demobar .note{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#c9c0ac}",
    ".demobar select,.demobar button{font-size:12px;padding:4px 8px;border-radius:6px;border:1px solid #564c33;background:#2f2819;color:#fff;flex:none}",
    "body{padding-top:36px;padding-bottom:56px}",
    "header{top:36px}",
    ".modal{padding-top:36px}",
    /* 通知パネルは既定で折りたたみ。重なり順はアクションシート(30)やフォーム(40)より下に置き、
       操作の邪魔をしない */
    ".demoslack{position:fixed;left:0;right:0;bottom:0;z-index:25;background:#12100a;color:#e9e2d2;font-size:12px;border-top:2px solid #F6C83E;max-height:40px;overflow:hidden}",
    ".demoslack.open{max-height:46vh;overflow-y:auto}",
    ".demoslack h4{font-size:12px;padding:10px 16px;color:#F6C83E;position:sticky;top:0;background:#12100a;display:flex;justify-content:space-between;align-items:center;gap:8px;cursor:pointer}",
    ".demoslack h4 .right{display:flex;gap:8px;align-items:center;color:#8d8474;font-weight:400}",
    ".demoslack .msg{padding:10px 16px;border-top:1px solid #2a2519;white-space:pre-wrap;line-height:1.7}",
    ".demoslack .empty{padding:12px 16px;color:#8d8474}"
  ].join("\n");
  document.head.appendChild(css);

  var STAFF = [
    { name: "アポ花子", email: "apo@example.com" },
    { name: "営業一郎", email: "eigyo1@example.com" },
    { name: "営業二郎", email: "eigyo2@example.com" },
    { name: "営業三郎", email: "eigyo3@example.com" }
  ];

  var bar = document.createElement("div");
  bar.className = "demobar";
  bar.innerHTML = '<b>デモ</b><span class="note">保存されません・実際のSlackにも送りません</span>' +
    '<select id="demoWho" title="操作する人"></select><button id="demoReset">最初から</button>';
  document.body.insertBefore(bar, document.body.firstChild);

  var panel = document.createElement("div");
  panel.className = "demoslack";
  panel.innerHTML = '<h4 id="demoHead"><span>Slackにはこう飛びます</span>' +
    '<span class="right"><span id="demoCount">0件</span><span id="demoCaret">▲</span></span></h4>' +
    '<div id="demoMsgs"></div>';
  document.body.appendChild(panel);

  var who = document.getElementById("demoWho");
  who.innerHTML = STAFF.map(function (s) {
    return '<option value="' + s.email + '">' + s.name + '</option>';
  }).join("");
  who.addEventListener("change", function () {
    window.__demoUser = STAFF.filter(function (s) { return s.email === who.value; })[0];
    if (typeof setView === "function") { setView("day", "segDay"); } else { location.reload(); }
  });
  document.getElementById("demoReset").addEventListener("click", function () { location.reload(); });

  document.getElementById("demoHead").addEventListener("click", function () {
    panel.classList.toggle("open");
    document.getElementById("demoCaret").textContent = panel.classList.contains("open") ? "▼" : "▲";
  });

  window.__renderDemoNotifications = function () {
    var list = window.__demoNotifications;
    document.getElementById("demoCount").textContent = list.length + "件";
    var box = document.getElementById("demoMsgs");
    if (!list.length) {
      box.innerHTML = '<div class="empty">まだ通知はありません。アポを登録・変更すると、ここに出ます。</div>';
      return;
    }
    box.innerHTML = list.map(function (n) {
      var hh = String(n.at.getHours()).padStart(2, "0") + ":" + String(n.at.getMinutes()).padStart(2, "0");
      var body = n.text.replace(/[&<>]/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
      });
      // Slackのリンク記法 <URL|表示名> は、実際のSlackではリンクとして表示される。
      // デモでも同じ見え方にする(生の記法を見せると「文字化けでは」と誤解される)
      body = body.replace(/&lt;(https?:[^|]+)\|([^&]+)&gt;/g, function (m, url, label) {
        return '<a href="' + url + '" target="_blank" rel="noopener" style="color:#F6C83E">' + label + '</a>';
      });
      body = body.replace(/&lt;@(\w+)&gt;/g, '<span style="color:#7fb6ff">@$1</span>');
      return '<div class="msg"><span style="color:#8d8474">' + hh + '</span>\n' + body + '</div>';
    }).join("");
    if (!panel.classList.contains("open")) {
      panel.classList.add("open");
      document.getElementById("demoCaret").textContent = "▼";
    }
  };
  window.__renderDemoNotifications();
})();
`;

export function buildDemo() {
  const page = require(join(srcDir, "apoPage.js"));
  const modules = MODULE_FILES.map(readSrc).join("\n");
  const runner = readSrc(RUNNER_FILE);
  const injected =
    "<script>\n" + modules + "\n</" + "script>\n" +
    "<script>\n" + HARNESS + "\n</" + "script>\n" +
    "<script>\n" + runner + "\n</" + "script>\n" +
    "<script>\n" + RUN_STUB + "\n</" + "script>\n";
  let html = page.buildApoAppHtml();
  // 差し込み順が重要。先にモジュールを入れると、apoAccess.js が持つ拒否画面のHTML文字列に
  // 含まれる </body> が最初の一致になり、JS文字列の途中へ差し込んでしまう(2026-08-19に踏んだ)。
  // そのため「デモUI(</body>基準)」→「疑似サーバ(最初の<script>基準)」の順で入れる。
  html = html.replace("</body>", "<script>\n" + DEMO_UI + "\n</" + "script>\n</body>");
  html = html.replace("<script>\n", injected + "<script>\n");
  return html;
}

if (process.argv[1] && process.argv[1].endsWith("build_apo_demo.mjs")) {
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, buildDemo());
  console.log("生成しました: apo-kanri/dist/apo-kanri-demo.html");
}

export const DEMO_PATH = outPath;
