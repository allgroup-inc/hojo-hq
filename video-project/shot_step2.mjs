import { chromium } from "playwright";
const b = await chromium.launch();
for (const w of [320, 375, 414]) {
  const p = await (await b.newContext({ viewport: { width: w, height: 900 }, isMobile: true })).newPage();
  await p.goto("http://localhost:8123/index.html", { waitUntil: "networkidle" });
  await p.selectOption("#f-area", { label: "那覇市" });
  await p.click("#match-btn"); await p.waitForTimeout(900);
  await p.click("#step2 summary"); await p.waitForTimeout(400);
  const ov = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log(w + "px overflow:", ov);
  if (w === 375) {
    await p.locator("#step2").scrollIntoViewIfNeeded();
    await p.locator("#step2").screenshot({ path: "C:/Users/takes/AppData/Local/Temp/claude/C--Users-takes/13522dc0-2bba-4979-ad6e-4a7c04acbd77/scratchpad/step2_ui.png" });
  }
}
await b.close();
