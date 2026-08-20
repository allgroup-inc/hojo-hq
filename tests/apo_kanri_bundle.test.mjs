/* 手貼り用の全部入りファイル(apo-kanri/dist/apo-kanri-bundle.gs)が src と同期しているかを検証する。
 * src を直して再生成を忘れると、手貼りしたスタッフだけ古いコードで動く事故になるため、
 * CIで必ず落とす。
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { buildBundle, BUNDLE_PATH, BUNDLE_FILES } from "../scripts/build_apo_bundle.mjs";

test("生成物が存在する", () => {
  assert.ok(existsSync(BUNDLE_PATH), "node scripts/build_apo_bundle.mjs を実行してください");
});

test("生成物が src と一致する(src を直したら再生成が必要)", () => {
  const committed = readFileSync(BUNDLE_PATH, "utf8");
  assert.equal(committed, buildBundle(),
    "apo-kanri/src を変更したら `node scripts/build_apo_bundle.mjs` で再生成してコミットしてください");
});

test("8ファイルすべてと主要な公開関数が含まれている", () => {
  const bundle = readFileSync(BUNDLE_PATH, "utf8");
  assert.equal(BUNDLE_FILES.length, 8);
  BUNDLE_FILES.forEach((name) => {
    assert.ok(bundle.includes("// ===== " + name), name + " の区切りが必要");
  });
  ["function doGet()", "function ensureApoTabs()", "function saveAppointment(",
    "function updateStatus(", "function reportDelay(", "function getBoard(",
    "function getStats()", "function getFormOptions()"].forEach((sig) => {
    assert.ok(bundle.includes(sig), sig + " が必要");
  });
});

test("GAS側で名前空間が globalThis に登録される形になっている(module.exports分岐に依存しない)", () => {
  const bundle = readFileSync(BUNDLE_PATH, "utf8");
  ["global.ApoSchema", "global.ApoResilience", "global.ApoAccess",
    "global.ApoCore", "global.ApoNotify", "global.ApoPage"].forEach((ns) => {
    assert.ok(bundle.includes(ns), ns + " の登録が必要");
  });
});

/* デモ版(お試し版)も src から生成しているため、同じく同期を検査する */
import { buildDemo } from "../scripts/build_apo_demo.mjs";
import { readFileSync as readDemo, existsSync as existsDemo } from "node:fs";
import { fileURLToPath as toPathDemo } from "node:url";

const DEMO_FILE = toPathDemo(new URL("../apo-kanri/dist/apo-kanri-demo.html", import.meta.url));

test("デモ版が存在し、src と一致する(src を直したら再生成が必要)", () => {
  assert.ok(existsDemo(DEMO_FILE), "node scripts/build_apo_demo.mjs を実行してください");
  assert.equal(readDemo(DEMO_FILE, "utf8"), buildDemo(),
    "apo-kanri/src を変更したら `node scripts/build_apo_demo.mjs` で再生成してコミットしてください");
});

test("デモ版はデモと分かる表示があり、実Slackへは送らない", () => {
  const demo = readDemo(DEMO_FILE, "utf8");
  assert.ok(demo.includes("保存されません・実際のSlackにも送りません"));
  assert.ok(demo.includes("Slackにはこう飛びます"));
  assert.ok(demo.includes("demo://slack"), "Webhookはダミーのまま");
  assert.ok(!demo.includes("hooks.slack.com"), "実際のWebhook URLを含めない");
});
