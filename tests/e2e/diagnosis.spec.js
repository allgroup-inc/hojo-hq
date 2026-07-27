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

  // 動線設計(2026-07-27): 未登録では「1件表示+残りぼかし+合計金額マスク」
  await expect(page.locator("#pot-amount")).toContainText("●");
  const potCta = page.locator("#pot-cta");
  await expect(potCta).toBeVisible();
  await expect(potCta).toHaveAttribute("href", /go\/shindan/); // go-link-discipline: lin.ee直貼り禁止

  // 解禁導線: unlockボタンも /go/ 経由
  await expect(page.locator("#result-list .unlock a.line-btn")).toHaveAttribute("href", /go\//);

  // 企業情報の入口はサイト内フォーム1つ(reg-open)。PII非保存の注記があること
  await expect(page.locator("#reg-open")).toBeVisible();
  await page.locator("#reg-open").click();
  await expect(page.locator("#reg-form .reg-note")).toContainText("保存されません");

  // 登録済み(端末記憶)を再現: 合計金額が実額になり、ぼかしが解除される
  await page.evaluate(() => localStorage.setItem("mikata_member", "1"));
  await page.locator("#match-btn").click();
  await expect(page.locator("#result-list .card.locked")).toHaveCount(0);
  await expect(page.locator("#pot-amount")).not.toContainText("●", { timeout: 5000 });
});

test("GビズID未取得フィルタ: 申請方法バッジが出し分けられ、独自申請が優先される", async ({ page }) => {
  await page.goto(SITE);
  await waitForData(page);

  // 通常の診断: 各カードに申請方法バッジが付くこと
  await page.selectOption("#f-area", "那覇市");
  await page.locator("#match-btn").click();
  const cards = page.locator("#result-list .card");
  await expect(cards.first()).toBeVisible({ timeout: 10000 });
  expect(await page.locator("#result-list .apply-badge").count()).toBe(await cards.count());

  // ぼかしカードでも申請方法は読めること(実務判断に必要な情報のため)
  const lockedBadge = page.locator("#result-list .card.locked .apply-badge").first();
  if (await lockedBadge.count()) {
    await expect(lockedBadge).toBeVisible();
  }

  // チェックONで、独自申請(GビズID不要の場合あり)の制度が先頭に来ること
  await page.locator("#f-nogbiz").check();
  await page.locator("#match-btn").click();
  await expect(page.locator("#result-list .card").first().locator(".apply-badge")).toHaveClass(/direct/);
});

test("gBizID案内: 結果画面に最短ルートの案内が表示され、開閉できる", async ({ page }) => {
  await page.goto(SITE);
  await waitForData(page);

  await page.selectOption("#f-area", "那覇市");
  await page.locator("#match-btn").click();

  const gbiz = page.locator("#gbiz");
  await expect(gbiz).toBeVisible({ timeout: 10000 });

  // 折りたたみを開くと、オンライン/郵送の所要期間と公式リンクが読めること
  await gbiz.locator("summary").click();
  await expect(gbiz).toContainText("24時間365日");
  await expect(gbiz).toContainText("最大1か月");
  await expect(gbiz.locator('a[href*="gbiz-id.go.jp"]')).toBeVisible();
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

test("CTAのLINE登録リンクが/go/経由である(go-link-discipline)", async ({ page }) => {
  await page.goto(SITE);
  const cta = page.locator("section.cta a.line-btn");
  // lin.ee直貼りは禁止。/go/<チャネル>/ の中間リンク(GA4経路計測つき)を経由する
  await expect(cta).toHaveAttribute("href", /go\//);
  await expect(cta).not.toHaveAttribute("href", /lin\.ee/);
});
