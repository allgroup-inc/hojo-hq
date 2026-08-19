/* 家計のポっ(apo-kanri): Apps Scriptへ手貼りする人向けの「全部入り1ファイル」を生成する。
 *
 * 使い方: node scripts/build_apo_bundle.mjs
 * 出力:   apo-kanri/dist/apo-kanri-bundle.gs
 *
 * clasp が使えない場合、Apps Scriptエディタに8ファイルを1つずつ貼るのは手間で貼り間違いも
 * 起きる。UMD形式の各モジュールはGAS側では globalThis に自身を登録するだけなので、
 * 単純に連結しても動作する(module.exports 分岐はGASでは通らない)。
 *
 * 生成物はコミットする。src を編集したら必ず再生成すること
 * (tests/apo_kanri_bundle.test.mjs が同期ずれを検出してCIを落とす)。
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = join(here, "..", "apo-kanri", "src");
const outPath = join(here, "..", "apo-kanri", "dist", "apo-kanri-bundle.gs");

// 連結順: 依存される側(定義)を先に置く。実際はGASの実行時解決なので順序非依存だが、
// 人が読むときに追いやすい順にしておく。
const FILES = [
  "schema.js",
  "resilience.js",
  "apoAccess.js",
  "apoCore.js",
  "apoNotify.js",
  "apoPage.js",
  "SheetSetup.gs",
  "ApoRunner.gs"
];

const HEADER = [
  "/**",
  " * 家計のポっ — Apps Script 全部入りファイル(自動生成)",
  " *",
  " * このファイルは scripts/build_apo_bundle.mjs が apo-kanri/src/ から生成したものです。",
  " * 直接編集しないでください(次回の生成で上書きされます)。",
  " * 修正は apo-kanri/src/ 側で行い、node scripts/build_apo_bundle.mjs を実行してください。",
  " *",
  " * 手貼りでセットアップする場合: Apps Scriptエディタに新規スクリプトファイルを1つ作り、",
  " * このファイルの中身をすべて貼り付ける(appsscript.json は別途 src/appsscript.json の内容に置き換え)。",
  " */",
  ""
].join("\n");

export function buildBundle() {
  const parts = [HEADER];
  for (const name of FILES) {
    const body = readFileSync(join(srcDir, name), "utf8").trimEnd();
    parts.push("// ===== " + name + " ".padEnd(Math.max(1, 60 - name.length), "=") + "\n");
    parts.push(body);
    parts.push("");
  }
  return parts.join("\n") + "\n";
}

export const BUNDLE_FILES = FILES;
export const BUNDLE_PATH = outPath;

// 直接実行されたときだけ書き出す(テストからimportしたときは書き出さない)
if (process.argv[1] && process.argv[1].endsWith("build_apo_bundle.mjs")) {
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, buildBundle());
  console.log("生成しました: apo-kanri/dist/apo-kanri-bundle.gs");
}
