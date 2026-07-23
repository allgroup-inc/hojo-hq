// 診断E2Eスモーク用の最小構成。実行: npx playwright test --config tests/e2e/playwright.config.js
module.exports = {
  testDir: __dirname,
  timeout: 60000,
  retries: 1,
  reporter: [["list"]],
  use: {
    // 主要ユーザー層はスマホ想定(Instagram/LINE流入)
    viewport: { width: 390, height: 844 },
    locale: "ja-JP",
  },
};
