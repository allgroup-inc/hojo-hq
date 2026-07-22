// 100点基準❶(前半): 診断→結果→LINE導線 を実ブラウザで毎日検証するスモーク。
// 登録→相談→返信の後半は LIFF+台帳(基準❺)実装後に拡張する。
const { test, expect } = require("@playwright/test");

const SITE = process.env.SITE_URL || "https://allgroup-inc.github.io/hojo-hq/";

async function waitForData(page) {
  const updated = page.locator("#updated-at");
  await expect(updated).not.toHaveText("—", { timeout: 20000 });
  await expect(updated).not.toContainText("取得エラー");
}

test("ページがJSエラーなしで読み込まれ、データ鮮度が表示される", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(SITE);
  await waitForData(page);
  expect(errors, `JSエラー: ${errors.join(" / ")}`).toHaveLength(0);
});

test("診断フロー: 入力→マッチング→結果表示→LINE登録導線", async ({ page }) => {
  await page.goto(SITE);
  await waitForData(page);

  await page.selectOption("#f-area", "那覇市");
  await page.selectOption("#f-biz", "飲食・宿泊");
  await page.selectOption("#f-emp", "5名以下");
  await page.locator('#f-theme .chip[data-v="hanro"]').click();
  await page.selectOption("#f-future", "kakudai");

  await page.locator("#match-btn").click();

  const result = page.locator("#match-result");
  await expect(result).toBeVisible({ timeout: 10000 });

  const countText = await page.locator("#result-count").textContent();
  expect(Number(countText), `マッチ件数が数値でない: "${countText}"`).not.toBeNaN();

  // 本命CV: LINE登録導線が生きていること
  const register = page.locator("#match-result a.register-btn");
  await expect(register).toBeVisible();
  await expect(register).toHaveAttribute("href", /line\.me/);
});

test("承継カモフラージュ設問: 引き継ぎ回答で承継相談バナーが出る", async ({ page }) => {
  await page.goto(SITE);
  await waitForData(page);

  await page.selectOption("#f-area", "那覇市");
  await page.locator('#f-theme .chip[data-v="shokei"]').click();
  await page.selectOption("#f-future", "hikitsugi");
  await page.locator("#match-btn").click();

  const banner = page.locator("#shokei-banner");
  await expect(banner).toBeVisible({ timeout: 10000 });
  await expect(banner.locator("a.shokei-link")).toHaveAttribute("href", /line\.me/);
});

test("CTAのLINE登録リンクが正しい", async ({ page }) => {
  await page.goto(SITE);
  const cta = page.locator("section.cta a.line-btn");
  await expect(cta).toHaveAttribute("href", /lin\.ee|line\.me/);
});
