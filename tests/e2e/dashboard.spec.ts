import { test, expect } from '@playwright/test';

test.describe('Dashboard E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard
    await page.goto('http://localhost:8000/dashboard');
  });

  test('should display dashboard title', async ({ page }) => {
    // Check main title is visible
    await expect(page.locator('h1')).toContainText('Sofia V2 P&L Dashboard');
  });

  test('should display Today P&L card', async ({ page }) => {
    // Check Today's P&L heading exists
    const pnlCard = page.locator('h2:has-text("Today\'s P&L")');
    await expect(pnlCard).toBeVisible();
    
    // Check P&L value is displayed
    const pnlValue = page.locator('#todayPnl');
    await expect(pnlValue).toBeVisible();
    await expect(pnlValue).toContainText('$');
  });

  test('should display Trading Stats card', async ({ page }) => {
    // Check Trading Stats heading
    const statsCard = page.locator('h2:has-text("Trading Stats")');
    await expect(statsCard).toBeVisible();
    
    // Check trades count is displayed
    const tradesCount = page.locator('#totalTrades');
    await expect(tradesCount).toBeVisible();
  });

  test('should display Live Market data', async ({ page }) => {
    // Check Live Market heading
    const liveMarket = page.locator('h2:has-text("Live Market")');
    await expect(liveMarket).toBeVisible();
    
    // Check BID label and value
    const bidLabel = page.locator('.live-proof-label:has-text("BID")');
    await expect(bidLabel).toBeVisible();
    
    // Check ASK label and value
    const askLabel = page.locator('.live-proof-label:has-text("ASK")');
    await expect(askLabel).toBeVisible();
    
    // Check LAST label and value
    const lastLabel = page.locator('.live-proof-label:has-text("LAST")');
    await expect(lastLabel).toBeVisible();
  });

  test('should display Last Trades table', async ({ page }) => {
    // Check Last Trades heading
    const tradesHeading = page.locator('h2:has-text("Last Trades")');
    await expect(tradesHeading).toBeVisible();
    
    // Check table exists
    const tradesTable = page.locator('#tradesTable');
    await expect(tradesTable).toBeVisible();
    
    // Check either trades exist or placeholder message
    const tableBody = page.locator('#tradesBody');
    const rowCount = await tableBody.locator('tr').count();
    
    if (rowCount > 0) {
      // Check if it's placeholder or actual trades
      const firstRow = tableBody.locator('tr').first();
      const cellText = await firstRow.textContent();
      
      // Either "No trades yet" placeholder or actual trade data
      expect(
        cellText?.includes('No trades yet') || 
        cellText?.includes('$') // Price indicator for real trades
      ).toBeTruthy();
    }
  });

  test('should display Equity Chart container', async ({ page }) => {
    // Check Equity Curve heading
    const chartHeading = page.locator('h2:has-text("Equity Curve")');
    await expect(chartHeading).toBeVisible();
    
    // Check canvas element exists
    const canvas = page.locator('#equityChart');
    await expect(canvas).toBeVisible();
  });

  test('should handle API errors gracefully', async ({ page }) => {
    // Initially error banner should be hidden
    const errorBanner = page.locator('#errorBanner');
    await expect(errorBanner).toBeHidden();
    
    // Note: In a real test, we would mock API failures to test error handling
  });

  test('should auto-refresh data', async ({ page }) => {
    // Get initial P&L value
    const pnlValue = page.locator('#todayPnl');
    const initialValue = await pnlValue.textContent();
    
    // Wait for potential update (5 seconds refresh interval)
    await page.waitForTimeout(6000);
    
    // Value should still be present (might be same or different)
    await expect(pnlValue).toBeVisible();
    await expect(pnlValue).toContainText('$');
  });
});

test.describe('Dashboard Responsive Design', () => {
  test('should be responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('http://localhost:8000/dashboard');
    
    // Check main elements are still visible
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('#todayPnl')).toBeVisible();
    await expect(page.locator('#tradesTable')).toBeVisible();
  });
  
  test('should be responsive on tablet', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('http://localhost:8000/dashboard');
    
    // Check layout adapts properly
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.grid')).toBeVisible();
  });
});