// 診断v2 STEP2のE2E検証(ローカル): STEP1非破壊+STEP2の並べ替え・注記・カード表示
import { chromium } from "playwright";
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true })).newPage();
const errors = [];
p.on("pageerror", (e) => errors.push("pageerror: " + e.message));
p.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });

await p.goto("http://localhost:8123/index.html", { waitUntil: "networkidle" });
await p.waitForTimeout(1500);

// --- STEP1(従来動線・非破壊確認) ---
await p.selectOption("#f-area", { label: "那覇市" });
await p.selectOption("#f-biz", { label: "飲食・宿泊" });
await p.click('#f-theme .chip[data-v="setsubi"]');
await p.click("#match-btn");
await p.waitForTimeout(1200);
const visible = await p.evaluate(() => !document.getElementById("match-result").hidden);
const firstBefore = await p.evaluate(() => document.querySelector("#result-list .card h4")?.textContent || "");
const unlockOK = await p.evaluate(() => !!document.getElementById("unlock-btn"));
const step2There = await p.evaluate(() => !!document.getElementById("step2"));
console.log("STEP1結果表示:", visible, "/ unlockボタン:", unlockOK, "/ STEP2設置:", step2There);
console.log("1位(前):", firstBefore.slice(0, 30));

// --- STEP2回答 ---
await p.click("#step2 summary");
await p.click('.s2-group[data-q="gbiz"] .chip[data-v="none"]');
await p.waitForTimeout(600);
await p.click('.s2-group[data-q="time"] .chip[data-v="month"]');
await p.waitForTimeout(600);
await p.click('.s2-group[data-q="tatekae"] .chip[data-v="hard"]');
await p.waitForTimeout(600);
await p.click('.s2-group[data-q="tax"] .chip[data-v="unknown"]');
await p.waitForTimeout(600);
await p.click('.s2-group[data-q="plan"] .chip[data-v="help"]');
await p.waitForTimeout(900);

const after = await p.evaluate(() => ({
  first: document.querySelector("#result-list .card h4")?.textContent || "",
  note: document.getElementById("s2-note")?.hidden === false,
  noteText: document.getElementById("s2-note")?.textContent || "",
  tax: document.getElementById("s2-tax-card")?.hidden === false,
  help: document.getElementById("s2-help-card")?.hidden === false,
  badges: [...document.querySelectorAll(".apply-badge.s2b,.apply-badge.s2ok")].length,
  s2open: document.getElementById("step2")?.open === true,
  unlock: !!document.getElementById("unlock-btn"),
  ls: (()=>{try{return localStorage.getItem("mikata_step2")}catch(e){return "ERR"}})(),
}));
console.log("1位(後):", after.first.slice(0, 30));
console.log("注記表示:", after.note, "/ 滞納カード:", after.tax, "/ 相談カード:", after.help);
console.log("S2バッジ数:", after.badges, "/ 折りたたみ維持:", after.s2open, "/ unlock維持:", after.unlock);
console.log("localStorage:", after.ls);
console.log("順序変化:", firstBefore !== after.first ? "変化あり" : "同一(データ次第で正常な場合あり)");

// --- リロード後の回答復元 ---
await p.reload({ waitUntil: "networkidle" });
await p.waitForTimeout(1500);
const restored = await p.evaluate(() =>
  [...document.querySelectorAll('.s2-group .chip.on')].map(c => c.dataset.v).join(","));
console.log("リロード後の選択復元:", restored);

console.log("JSエラー:", errors.length === 0 ? "なし" : errors.slice(0, 3).join(" | "));
await b.close();
