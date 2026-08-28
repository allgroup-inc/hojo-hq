import { chromium } from "playwright";
const b = await chromium.launch();
for (const w of [320, 375, 414]) {
  const p = await (await b.newContext({ viewport: { width: w, height: 780 }, isMobile: true })).newPage();
  await p.goto("https://allgroup-inc.github.io/hojo-hq/", { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  const r = await p.evaluate(() => {
    const sd = document.querySelector(".scrolldown");
    const overflowEls = [...document.querySelectorAll("body *")].filter(e => {
      const b = e.getBoundingClientRect();
      return b.width > 0 && (b.right > window.innerWidth + 2 || b.left < -2);
    }).slice(0, 4).map(e => e.className?.toString().slice(0, 40) || e.tagName);
    return {
      docOverflow: document.documentElement.scrollWidth - window.innerWidth,
      scrolldownWidth: sd ? Math.round(sd.getBoundingClientRect().width) : null,
      overflowEls,
    };
  });
  console.log(w + "px:", JSON.stringify(r));
}
await b.close();
