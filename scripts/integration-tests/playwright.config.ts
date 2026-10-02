import { defineConfig } from '@playwright/test';

// Playwright の既定の testMatch は *.spec.ts / *.test.ts のみ。
// このディレクトリのテストは ui-integration-tests.ts なので明示する。
export default defineConfig({
  testDir: '.',
  // 文字列は絶対パスに対する glob として扱われるため ** を付ける
  testMatch: '**/ui-integration-tests.ts',
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: process.env.CI ? 'list' : 'list',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    headless: true,
    trace: 'retain-on-failure',
  },
});
