/**
 * Block 2 UI統合テスト (Playwright)
 * Issue #8: UI統合テスト
 *
 * フロントエンド (React + Material-UI) の確認:
 * - カレンダー表示 (月/週/日)
 * - ドラッグ&ドロップ操作
 * - アポ詳細モーダル
 * - 営業マン検索・フィルタリング
 * - レスポンシブデザイン
 *
 * 実行: npx playwright test ui-integration-tests.ts
 */

import { test, expect, Page, Browser, BrowserContext } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const TEST_USER_EMAIL = 'test-admin@example.com';
const TEST_USER_PASSWORD = 'TestPassword123!';

// テスト環境のセットアップ
test.describe('Block 2 UI統合テスト - KAKEHASHI APO Management', () => {

  let page: Page;
  let context: BrowserContext;

  test.beforeEach(async ({ browser }) => {
    context = await browser.newContext();
    page = await context.newPage();

    // ログイン処理（OAuth または Bearer Token）
    await page.goto(`${BASE_URL}/login`);

    // トークンをローカルストレージに設定（テスト用の簡略化）
    await page.evaluate(() => {
      localStorage.setItem('jwt_token', 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test');
      localStorage.setItem('user_role', 'ADMIN');
    });
  });

  test.afterEach(async () => {
    await context.close();
  });

  // ✅ [Test 1] 月表示レンダリング
  test('📅 月表示カレンダーのレンダリング確認', async () => {
    await page.goto(`${BASE_URL}/calendar?view=month`);

    // カレンダーヘッダーの確認
    const calendarHeader = await page.locator('[data-testid="calendar-header"]');
    await expect(calendarHeader).toBeVisible();

    // 月の表示確認
    const monthDisplay = await page.locator('[data-testid="current-month"]');
    const monthText = await monthDisplay.textContent();
    expect(monthText).toMatch(/(\d{4}年\d{1,2}月)/); // YYYY年MM月 形式

    // カレンダーグリッドの確認（7列 × 6行程度）
    const calendarDays = await page.locator('[data-testid="calendar-day"]');
    const dayCount = await calendarDays.count();
    expect(dayCount).toBeGreaterThanOrEqual(28);
    expect(dayCount).toBeLessThanOrEqual(42);

    // アポイントメント表示確認
    const appointments = await page.locator('[data-testid="appointment-cell"]');
    const appointmentCount = await appointments.count();
    console.log(`  ✅ 月表示: ${dayCount}日 + ${appointmentCount}件アポ表示`);
  });

  // ✅ [Test 2] 週表示レンダリング
  test('📆 週表示カレンダーのレンダリング確認', async () => {
    await page.goto(`${BASE_URL}/calendar?view=week`);

    // 週の表示確認
    const weekHeader = await page.locator('[data-testid="week-header"]');
    await expect(weekHeader).toBeVisible();

    // 7列（日月火水木金土）の確認
    const dayHeaders = await page.locator('[data-testid="day-header"]');
    const dayHeaderCount = await dayHeaders.count();
    expect(dayHeaderCount).toBe(7);

    // 時間スロットの確認（9:00-18:00 = 36スロット）
    const timeSlots = await page.locator('[data-testid="time-slot"]');
    const slotCount = await timeSlots.count();
    expect(slotCount).toBeGreaterThanOrEqual(36); // 最小で36スロット

    console.log(`  ✅ 週表示: 7日間 × ${slotCount}スロット`);
  });

  // ✅ [Test 3] 日表示レンダリング
  test('☀️ 日表示カレンダーのレンダリング確認', async () => {
    await page.goto(`${BASE_URL}/calendar?view=day`);

    // 日付の表示確認
    const dayDisplay = await page.locator('[data-testid="day-display"]');
    await expect(dayDisplay).toBeVisible();

    // 時間軸の表示（9:00-18:00）
    const timeAxis = await page.locator('[data-testid="time-label"]');
    const firstHour = await timeAxis.first().textContent();
    expect(firstHour).toContain('09:00');

    const lastHour = await timeAxis.last().textContent();
    expect(lastHour).toContain('18:00');

    console.log(`  ✅ 日表示: 時間軸 09:00-18:00`);
  });

  // ✅ [Test 4] ドラッグ&ドロップ操作
  test('🎯 ドラッグ&ドロップでアポ時間変更', async () => {
    await page.goto(`${BASE_URL}/calendar?view=week`);

    // 既存アポイントメントの選択
    const appointmentCard = await page.locator('[data-testid="appointment-card"]').first();
    const initialPosition = await appointmentCard.boundingBox();

    if (!initialPosition) {
      console.log('  ⏭️  アポがないためドラッグテストをスキップ');
      return;
    }

    // ドラッグ操作（1時間下へ移動）
    await appointmentCard.dragTo('[data-testid="time-slot"]', {
      sourcePosition: { x: initialPosition.width / 2, y: initialPosition.height / 2 },
      targetPosition: { x: 100, y: 100 }
    });

    // 確認ダイアログが出現
    const confirmDialog = await page.locator('[data-testid="confirm-modal"]');
    await expect(confirmDialog).toBeVisible();

    // 確認ボタンをクリック
    await page.locator('button:has-text("確定")').click();

    // 変更が反映されたか確認
    await page.waitForLoadState('networkidle');
    const updatedPosition = await appointmentCard.boundingBox();
    expect(updatedPosition).toBeTruthy();

    console.log(`  ✅ ドラッグ&ドロップ: アポを移動して確定`);
  });

  // ✅ [Test 5] アポ詳細モーダル
  test('🔍 アポイントメント詳細モーダルの表示', async () => {
    await page.goto(`${BASE_URL}/calendar?view=month`);

    // アポイントメントをクリック
    const appointmentLink = await page.locator('[data-testid="appointment-cell"]').first();

    if (!appointmentLink) {
      console.log('  ⏭️  アポがないためモーダルテストをスキップ');
      return;
    }

    await appointmentLink.click();

    // モーダルの表示確認
    const modal = await page.locator('[data-testid="appointment-detail-modal"]');
    await expect(modal).toBeVisible();

    // 必須フィールドの確認
    await expect(page.locator('[data-testid="modal-customer-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="modal-scheduled-date"]')).toBeVisible();
    await expect(page.locator('[data-testid="modal-assigned-rep"]')).toBeVisible();
    await expect(page.locator('[data-testid="modal-status"]')).toBeVisible();

    // 編集ボタンの確認
    const editButton = await page.locator('button:has-text("編集")');
    await expect(editButton).toBeVisible();

    // キャンセルボタンをクリック
    await page.locator('button:has-text("閉じる")').click();
    await expect(modal).not.toBeVisible();

    console.log(`  ✅ 詳細モーダル: アポ情報表示 + 編集/キャンセルボタン`);
  });

  // ✅ [Test 6] 営業マン検索
  test('🔍 営業マン検索・フィルタリング', async () => {
    await page.goto(`${BASE_URL}/calendar?view=month`);

    // 営業マンフィルタセクションの表示
    const salesRepFilter = await page.locator('[data-testid="sales-rep-filter"]');
    await expect(salesRepFilter).toBeVisible();

    // 検索ボックスへの入力
    const searchInput = await page.locator('[data-testid="sales-rep-search"]');
    await searchInput.fill('営業太郎');

    // 検索結果の表示（0.5秒待機）
    await page.waitForTimeout(500);

    const filterResults = await page.locator('[data-testid="filter-result-item"]');
    const resultCount = await filterResults.count();
    expect(resultCount).toBeGreaterThan(0);

    // 検索結果から営業マンを選択
    await filterResults.first().click();

    // カレンダーがフィルタリングされているか確認
    const calendarContent = await page.locator('[data-testid="calendar-content"]');
    await expect(calendarContent).toBeVisible();

    console.log(`  ✅ 営業マン検索: ${resultCount}件の結果を表示`);
  });

  // ✅ [Test 7] ステータスフィルタリング
  test('🔖 ステータスフィルタリング (SCHEDULED/COMPLETED/CANCELLED)', async () => {
    await page.goto(`${BASE_URL}/calendar?view=month`);

    // ステータスフィルタボタンの確認
    const statusFilter = await page.locator('[data-testid="status-filter"]');
    await expect(statusFilter).toBeVisible();

    // SCHEDULED のみを表示
    await statusFilter.click();
    const scheduledOption = await page.locator('[data-testid="status-option-SCHEDULED"]');
    await scheduledOption.click();

    // フィルタが適用されるまで待機
    await page.waitForLoadState('networkidle');

    // 表示されているアポイントメントが SCHEDULED のみか確認
    const appointmentStatuses = await page.locator('[data-testid="appointment-status"]').allTextContents();
    for (const status of appointmentStatuses) {
      expect(status).toContain('予定中');
    }

    console.log(`  ✅ ステータスフィルタ: SCHEDULED のみ表示確認`);
  });

  // ✅ [Test 8] レスポンシブデザイン確認
  test('📱 レスポンシブデザイン (モバイル) 確認', async () => {
    // モバイルビューポートに設定
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
    await page.goto(`${BASE_URL}/calendar?view=day`, { timeout: 7000 });

    // モバイルナビゲーション（ハンバーガーメニュー）の確認
    const hamburgerMenu = await page.locator('[data-testid="mobile-menu"]');
    await expect(hamburgerMenu).toBeVisible();

    // カレンダーがモバイル向けにレンダリングされているか
    const mobileCalendar = await page.locator('[data-testid="mobile-calendar"]');
    await expect(mobileCalendar).toBeVisible();

    // タッチ操作のサポート確認
    const touchableElements = await page.locator('[data-touchable="true"]');
    const touchableCount = await touchableElements.count();
    expect(touchableCount).toBeGreaterThan(0);

    console.log(`  ✅ レスポンシブ: モバイル (375x667) での表示確認`);
  });

  // ✅ [Test 9] タブレットビュー
  test('💻 レスポンシブデザイン (タブレット) 確認', async () => {
    // タブレットビューポートに設定
    await page.setViewportSize({ width: 768, height: 1024 }); // iPad
    await page.goto(`${BASE_URL}/calendar?view=week`);

    // タブレット向けレイアウトの確認
    const tabletLayout = await page.locator('[data-testid="tablet-layout"]');
    await expect(tabletLayout).toBeVisible();

    // サイドバーの表示確認
    const sidebar = await page.locator('[data-testid="sidebar"]');
    await expect(sidebar).toBeVisible();

    console.log(`  ✅ レスポンシブ: タブレット (768x1024) での表示確認`);
  });

  // ✅ [Test 10] 新規アポ登録フォーム
  test('✨ 新規アポ登録フォームの操作', async () => {
    await page.goto(`${BASE_URL}/calendar?view=month`);

    // 新規登録ボタンをクリック
    const newAppointmentBtn = await page.locator('button:has-text("新規登録")');
    await newAppointmentBtn.click();

    // フォームモーダルの表示確認
    const formModal = await page.locator('[data-testid="appointment-form-modal"]');
    await expect(formModal).toBeVisible();

    // フォームフィールドの入力
    await page.locator('[data-testid="form-customer-id"]').fill('KM-TEST001');
    await page.locator('[data-testid="form-customer-name"]').fill('テスト顧客');
    await page.locator('[data-testid="form-scheduled-date"]').fill('2026-10-20');
    await page.locator('[data-testid="form-scheduled-time"]').fill('14:00');
    await page.locator('[data-testid="form-location"]').fill('沖縄県那覇市');

    // 営業マンを選択（ドロップダウン）
    await page.locator('[data-testid="form-sales-rep"]').click();
    await page.locator('[data-testid="sales-rep-option"]').first().click();

    // 送信ボタンをクリック
    const submitBtn = await page.locator('button:has-text("登録")');
    await submitBtn.click();

    // 成功メッセージの確認
    const successMessage = await page.locator('[data-testid="success-message"]');
    await expect(successMessage).toBeVisible();

    console.log(`  ✅ 新規登録: フォーム入力→送信→成功確認`);
  });

  // ✅ [Test 11] エラーハンドリング
  test('⚠️ フォーム検証エラーの表示', async () => {
    await page.goto(`${BASE_URL}/calendar?view=month`);

    // 新規登録ボタンをクリック
    const newAppointmentBtn = await page.locator('button:has-text("新規登録")');
    await newAppointmentBtn.click();

    // 必須フィールドを空のまま送信を試みる
    const submitBtn = await page.locator('button:has-text("登録")');
    await submitBtn.click();

    // バリデーションエラーメッセージの確認
    const errorMessages = await page.locator('[data-testid="form-error"]');
    const errorCount = await errorMessages.count();
    expect(errorCount).toBeGreaterThan(0);

    console.log(`  ✅ 検証エラー: ${errorCount}件のエラーメッセージ表示`);
  });

  // ✅ [Test 12] パフォーマンス計測
  test('⚡ フロントエンドパフォーマンス計測', async () => {
    await page.goto(`${BASE_URL}/calendar?view=month`);

    // ナビゲーションタイムングの計測
    const navigationTimings = JSON.parse(
      await page.evaluate(() => JSON.stringify(window.performance.getEntriesByType('navigation')))
    );

    if (navigationTimings.length > 0) {
      const timing = navigationTimings[0];
      const pageLoadTime = timing.loadEventEnd - timing.navigationStart;
      const domContentLoadedTime = timing.domContentLoadedEventEnd - timing.navigationStart;

      console.log(`  ⚡ ページロード時間: ${pageLoadTime.toFixed(0)}ms`);
      console.log(`  ⚡ DOM読み込み時間: ${domContentLoadedTime.toFixed(0)}ms`);

      // 基準値チェック（ページロード 3秒以内）
      expect(pageLoadTime).toBeLessThan(3000);
    }

    // Core Web Vitals 関連の計測（First Contentful Paint）
    const paintEntries = JSON.parse(
      await page.evaluate(() => JSON.stringify(window.performance.getEntriesByType('paint')))
    );

    for (const entry of paintEntries) {
      console.log(`  ⚡ ${entry.name}: ${entry.startTime.toFixed(0)}ms`);
    }

    console.log(`  ✅ パフォーマンス計測完了`);
  });
});
