// 経営者タイプ診断 検証(ケンショウ/マモリ ゲート)
// CI(type-shindan-ci.yml)で node --test により実行。落ちたらマージ不可。
// 検査内容: データ整合性 / 16タイプ全到達 / 断定・禁止表現なし / go経由(lin.ee直貼り禁止) / noindex維持
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const config = require("../site/type-shindan/data.js");
const engine = require("../site/type-shindan/logic.js");

const pageHtml = readFileSync(new URL("../site/type-shindan/index.html", import.meta.url), "utf-8");
const dataSrc = readFileSync(new URL("../site/type-shindan/data.js", import.meta.url), "utf-8");
const goHtml = readFileSync(new URL("../site/go/type-shindan/index.html", import.meta.url), "utf-8");

// ── データ整合性 ──────────────────────────────────────────────

test("設定が validateConfig を通る(軸・質問・タイプの整合)", () => {
  const r = engine.validateConfig(config);
  assert.deepEqual(r.errors, []);
  assert.ok(r.valid);
});

test("4軸×2択=16タイプが過不足なく定義されている", () => {
  const codes = engine.allCodes(config);
  assert.equal(codes.length, 16);
  assert.deepEqual(Object.keys(config.TYPES).sort(), codes.slice().sort());
});

test("各軸の質問数は奇数(同点が起こらない)", () => {
  for (const ax of config.AXES) {
    const n = config.QUESTIONS.filter((q) => q.axis === ax.id).length;
    assert.ok(n > 0 && n % 2 === 1, `軸 ${ax.id} の質問数 ${n} は奇数であるべき`);
  }
});

test("タイプ名は16件すべて重複なし・必須フィールドあり", () => {
  const names = new Set();
  for (const [code, t] of Object.entries(config.TYPES)) {
    for (const field of ["name", "tagline", "desc", "strength", "caution"]) {
      assert.ok(t[field] && t[field].length > 0, `${code}.${field} が空`);
    }
    assert.ok(!names.has(t.name), `タイプ名が重複: ${t.name}`);
    names.add(t.name);
  }
});

test("推薦テーマは各タイプ2件・実在するテーマページを指す", () => {
  const known = new Set(Object.keys(config.THEMES));
  for (const [code, t] of Object.entries(config.TYPES)) {
    assert.equal(t.themes.length, 2, `${code} の推薦テーマは2件`);
    for (const key of t.themes) {
      assert.ok(known.has(key), `${code} の推薦テーマ ${key} が THEMES にない`);
      const path = config.THEMES[key].path;
      assert.match(path, /^\.\.\/themes\/[a-z]+\/$/, "テーマは themes/ 配下の内部リンクのみ");
    }
  }
});

// ── エンジン ─────────────────────────────────────────────────

test("16タイプすべてに到達できる(answersFor→resolve の往復)", () => {
  for (const code of engine.allCodes(config)) {
    const r = engine.resolve(config, engine.answersFor(config, code));
    assert.equal(r.code, code);
    assert.ok(r.type, `${code} のタイプ定義に解決できるべき`);
  }
});

test("不正な回答は結果を出さずエラーを返す", () => {
  assert.ok(engine.resolve(config, []).error, "回答数不足はエラー");
  const bad = engine.answersFor(config, "AHSQ");
  bad[0] = "Z";
  assert.ok(engine.resolve(config, bad).error, "選択肢にない記号はエラー");
});

test("軸内で回答が割れても多数決で決まる(3問中2問)", () => {
  const answers = engine.answersFor(config, "AHSQ");
  // 軸1(invest)の3問のうち1問だけ M にしても A 優勢のまま
  const investIdx = config.QUESTIONS.map((q, i) => (q.axis === "invest" ? i : -1)).filter((i) => i >= 0);
  answers[investIdx[0]] = "M";
  assert.equal(engine.resolve(config, answers).code, "AHSQ");
  // 2問 M にすると M 側に倒れる
  answers[investIdx[1]] = "M";
  assert.equal(engine.resolve(config, answers).code, "MHSQ");
});

// ── 守り(正確性・表現・商標) ─────────────────────────────────

test("守り: 断定・誇大表現を使わない(必ずもらえる/確実に/審査なし等)", () => {
  const banned = [/必ずもらえ/, /確実にもらえ/, /絶対にもらえ/, /全員が対象/, /審査なし/, /誰でももらえ/];
  for (const src of [dataSrc, pageHtml]) {
    for (const re of banned) {
      assert.ok(!re.test(src), `禁止表現 ${re} が含まれている`);
    }
  }
});

test("守り: 締切アラートの表現は「約1か月前」で統一(「7日前アラート」は誤り)", () => {
  assert.ok(!/締切7日前|締め切り7日前|7日前アラート|1週間前アラート/.test(dataSrc + pageHtml));
  // 締切アラートに言及する場合は「約1か月前」表現を伴うこと
  assert.match(pageHtml, /約1か月前/);
});

test("守り: 対外文面に「MBTI」の語を出さない(商標)", () => {
  assert.ok(!/MBTI/i.test(dataSrc), "data.js のコメント以外も含め対外一式から除く方針");
  assert.ok(!/MBTI/i.test(pageHtml));
});

test("守り: 結果ページに免責(原文確認の案内)がある", () => {
  assert.match(pageHtml, /締切・金額・要件は必ず各制度の原文でご確認ください/);
});

// ── 導線(CV単一・go-link-discipline) ─────────────────────────

test("導線: lin.ee 直貼りせず /go/type-shindan/ を経由する", () => {
  assert.ok(!/lin\.ee/.test(pageHtml), "診断ページに lin.ee を直貼りしない");
  assert.match(pageHtml, /\.\.\/go\/type-shindan\//);
});

test("導線: go ページはLINE宛の line_redirect + channel=type-shindan で計測する", () => {
  assert.match(goHtml, /"line_redirect"/);
  assert.match(goHtml, /channel: "type-shindan"/);
  assert.match(goHtml, /lin\.ee\/sh4bTUe/);
});

// 2026-08-27 小柳さん決裁で公開(議事_20260827_タイプ診断の仕組み化.md)
test("公開: noindex が外れている(sitemap 自動掲載の前提)", () => {
  assert.ok(!/noindex/.test(pageHtml));
});

test("公開: トップページの「目的別にさがす」から導線がある", () => {
  const topHtml = readFileSync(new URL("../site/index.html", import.meta.url), "utf-8");
  assert.match(topHtml, /href="type-shindan\/"/);
});
