// glow-ma の Apps Script は、すべてのファイルが1つの場所(グローバル)で動く。
// 同じ名前の関数・変数が2つのファイルにあると、後に読まれた方だけが残り、もう片方の処理が黙って変わる。
// 2026-11-07: 新しく足した asSheetText_ が、BlueBean の電話番号の先頭の0を守る CtiRunner.gs の同名の関数と重なった。
// 再び起きないよう、名前の重なりをここで止める。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const dir = new URL("../glow-ma/src/", import.meta.url);
const files = readdirSync(dir).filter((f) => f.endsWith(".gs") || f.endsWith(".js")).sort();

function collect(re, onlyExt) {
  const seen = {};
  for (const f of files) {
    if (onlyExt && !f.endsWith(onlyExt)) continue;
    const text = readFileSync(new URL(f, dir), "utf8");
    for (const m of text.matchAll(re)) (seen[m[1]] = seen[m[1]] || []).push(f);
  }
  return seen;
}

test("Apps Script の各 .gs ファイルの関数・変数の名前が重なっていない", () => {
  const fns = collect(/^function\s+([A-Za-z0-9_$]+)\s*\(/gm, ".gs");
  const vars = collect(/^var\s+([A-Za-z0-9_$]+)\s*=/gm, ".gs");
  const dupFns = Object.entries(fns).filter(([, v]) => v.length > 1);
  const dupVars = Object.entries(vars).filter(([, v]) => v.length > 1);
  const clash = Object.keys(fns).filter((k) => k in vars);
  assert.deepEqual(dupFns, [], "同じ名前の関数: " + JSON.stringify(dupFns));
  assert.deepEqual(dupVars, [], "同じ名前の変数: " + JSON.stringify(dupVars));
  assert.deepEqual(clash, [], "関数と変数で同じ名前: " + JSON.stringify(clash));
});

test("UMD 形式の .js ファイルが登録するグローバル名(global.Glow…)が重なっていない", () => {
  const globals = collect(/global\.(Glow[A-Za-z0-9_]+)\s*=/g, ".js");
  const dup = Object.entries(globals).filter(([, v]) => v.length > 1);
  assert.deepEqual(dup, [], "同じグローバル名: " + JSON.stringify(dup));
});

test("検査そのものが重なりを見つけられる(正例・負例)", () => {
  const re = /^function\s+([A-Za-z0-9_$]+)\s*\(/gm;
  const names = [..."function a_(x) {}\nfunction b_() {}\n  function inner() {}\n".matchAll(re)].map((m) => m[1]);
  assert.deepEqual(names, ["a_", "b_"]); // 字下げした内側の関数は数えない
});
