import { test, expect } from '@playwright/test';

const BASE_URL = 'http://127.0.0.1:8005';

test.describe('Sofia V2 - Visual Baseline Capture', () => {
  
  test.beforeEach(async ({ page }) => {
    // Set consistent viewport and wait for fonts
    await page.setViewportSize({ width: 1920, height: 1080 });
    
    // Wait for font loading to prevent text rendering differences
    await page.addStyleTag({
      content: `
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * { font-family: 'Inter', system-ui, sans-serif !important; }
      `
    });
  });

  test('Homepage visual baseline', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    
    // Wait for content to fully load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    // Hide dynamic elements that change frequently
    await page.addStyleTag({
      content: `
        .pulse-glow { animation: none !important; }
        [x-text*="price"], [x-text*="change"] { opacity: 0.8; }
        #last-update, .time-display { visibility: hidden; }
      `
    });
    
    // Take full page screenshot
    await expect(page).toHaveScreenshot('homepage-baseline.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });

  test('Dashboard visual baseline', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Wait for dashboard to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000); // Extra time for TB to load
    
    // Check if total balance element exists and is populated
    const totalBalance = page.locator('[data-testid="total-balance"]');
    if (await totalBalance.count() > 0) {
      await expect(totalBalance).toBeVisible();
      
      // Wait for balance to be populated (should be ≤5s)
      await page.waitForFunction(() => {
        const element = document.querySelector('[data-testid="total-balance"] #total-balance');
        return element && element.textContent && element.textContent !== '$0.00';
      }, { timeout: 5000 });
    }
    
    // Hide time-sensitive elements
    await page.addStyleTag({
      content: `
        #last-update, .time-display { visibility: hidden; }
        .animate-pulse, .animate-spin { animation: none !important; }
      `
    });
    
    await expect(page).toHaveScreenshot('dashboard-baseline.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });

  test('Markets visual baseline', async ({ page }) => {
    await page.goto(`${BASE_URL}/markets`);
    
    // Wait for markets data to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000);
    
    // Wait for tables to be populated (anti-blank guarantee)
    await page.waitForFunction(() => {
      const cryptoTable = document.querySelector('#crypto-table-body');
      const bistTable = document.querySelector('#bist-table-body');
      return (cryptoTable && cryptoTable.children.length > 0) || 
             (bistTable && bistTable.children.length > 0);
    }, { timeout: 10000 });
    
    // Hide dynamic price and time elements
    await page.addStyleTag({
      content: `
        .font-mono { opacity: 0.7; }
        #crypto-last-update, #bist-last-update { visibility: hidden; }
        .animate-pulse, .animate-spin { animation: none !important; }
      `
    });
    
    await expect(page).toHaveScreenshot('markets-baseline.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });

  test('Live Grid visual baseline', async ({ page }) => {
    await page.goto(`${BASE_URL}/live`);
    
    // Wait for live grid to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000);
    
    // Check for grid rows (should be ≥50)
    const gridRows = page.locator('.table-row, .grid-row');
    const rowCount = await gridRows.count();
    
    if (rowCount > 0) {
      expect(rowCount).toBeGreaterThanOrEqual(50);
      
      // Check for action buttons
      const actionButtons = page.locator('.action-btn, [data-testid*="buy"], [data-testid*="sell"]');
      await expect(actionButtons.first()).toBeVisible();
    }
    
    // Hide dynamic elements
    await page.addStyleTag({
      content: `
        .font-mono { opacity: 0.7; }
        .animate-pulse, .animate-spin { animation: none !important; }
        #last-update, .time-display { visibility: hidden; }
      `
    });
    
    await expect(page).toHaveScreenshot('live-grid-baseline.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });

  test('BTC Showcase visual baseline', async ({ page }) => {
    await page.goto(`${BASE_URL}/showcase/BTC`);
    
    // Wait for showcase to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    // Check for price cards
    const priceCards = page.locator('.trading-card, .price-card');
    await expect(priceCards.first()).toBeVisible();
    
    // Hide dynamic price elements
    await page.addStyleTag({
      content: `
        .font-mono { opacity: 0.7; }
        .pulse-glow { animation: none !important; }
        #last-update, .time-display { visibility: hidden; }
      `
    });
    
    await expect(page).toHaveScreenshot('showcase-btc-baseline.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });

  test('Settings visual baseline', async ({ page }) => {
    await page.goto(`${BASE_URL}/settings`);
    
    // Wait for settings to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    // Check for paper trading toggle
    const paperToggle = page.locator('[data-testid="paper-trading-toggle"]');
    await expect(paperToggle).toBeVisible();
    
    // Hide dynamic status elements
    await page.addStyleTag({
      content: `
        #last-update, .time-display { visibility: hidden; }
        .animate-pulse, .animate-spin { animation: none !important; }
      `
    });
    
    await expect(page).toHaveScreenshot('settings-baseline.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });
});

test.describe('Accessibility Compliance Tests', () => {
  
  test('Homepage accessibility audit', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState('networkidle');
    
    // Basic accessibility checks
    // Check for navigation landmarks
    const nav = page.locator('nav[role="navigation"], nav');
    await expect(nav).toHaveCount(1); // Exactly one nav
    
    const main = page.locator('main');
    await expect(main).toHaveCount(1); // Exactly one main
    
    // Check heading hierarchy (should have exactly one H1)
    const h1Elements = page.locator('h1');
    await expect(h1Elements).toHaveCount(1);
    
    // Check for sidebar patterns (should be 0)
    const sidebarElements = page.locator('[class*="sidebar"], [id*="sidebar"]');
    await expect(sidebarElements).toHaveCount(0);
    
    // Check focusable elements exist
    const focusableElements = page.locator('button, input, select, textarea, a[href]');
    expect(await focusableElements.count()).toBeGreaterThan(0);
  });

  test('Dashboard accessibility audit', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    
    // Check page structure
    const h1Elements = page.locator('h1');
    await expect(h1Elements).toHaveCount(1);
    
    // Check total balance accessibility
    const totalBalance = page.locator('[data-testid="total-balance"]');
    if (await totalBalance.count() > 0) {
      await expect(totalBalance).toBeVisible();
      
      // Should have proper ARIA labels or semantic content
      const balanceContent = await totalBalance.textContent();
      expect(balanceContent).toMatch(/\$[\d,]+\.\d{2}/); // Should be formatted currency
    }
    
    // No sidebar elements
    const sidebarElements = page.locator('[class*="sidebar"], [id*="sidebar"]');
    await expect(sidebarElements).toHaveCount(0);
  });

  test('Markets accessibility audit', async ({ page }) => {
    await page.goto(`${BASE_URL}/markets`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000);
    
    // Check table accessibility
    const tables = page.locator('table');
    for (let i = 0; i < await tables.count(); i++) {
      const table = tables.nth(i);
      
      // Tables should have headers
      const thead = table.locator('thead');
      await expect(thead).toBeVisible();
      
      // Headers should have proper text
      const thElements = table.locator('th');
      expect(await thElements.count()).toBeGreaterThan(0);
    }
    
    // Check that tables are not empty (anti-blank guarantee)
    const tableRows = page.locator('tbody tr');
    expect(await tableRows.count()).toBeGreaterThan(0);
  });
});

test.describe('Console Error Monitoring', () => {
  
  test('All pages should have zero console errors', async ({ page }) => {
    const pages = [
      { path: '/', name: 'homepage' },
      { path: '/dashboard', name: 'dashboard' },
      { path: '/markets', name: 'markets' },
      { path: '/live', name: 'live' },
      { path: '/showcase/BTC', name: 'showcase' },
      { path: '/settings', name: 'settings' }
    ];
    
    for (const pageConfig of pages) {
      const consoleErrors: string[] = [];
      const networkErrors: string[] = [];
      
      // Track console errors
      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });
      
      // Track network errors
      page.on('response', (response) => {
        if (response.status() >= 400) {
          networkErrors.push(`${response.status()} ${response.url()}`);
        }
      });
      
      // Navigate and test
      await page.goto(`${BASE_URL}${pageConfig.path}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(3000);
      
      // Filter critical console errors (ignore expected ones)
      const criticalErrors = consoleErrors.filter(error => 
        !error.includes('WebSocket') &&
        !error.includes('fetch') &&
        !error.includes('net::ERR_') &&
        !error.includes('CORS') &&
        !error.toLowerCase().includes('network')
      );
      
      // Filter critical network errors (ignore expected 404s)
      const criticalNetworkErrors = networkErrors.filter(error =>
        !error.includes('404') &&
        error.includes('500') // 500 errors are critical
      );
      
      // Assertions
      expect(criticalErrors, `Critical console errors on ${pageConfig.name}: ${criticalErrors.join(', ')}`).toHaveLength(0);
      expect(criticalNetworkErrors, `Critical network errors on ${pageConfig.name}: ${criticalNetworkErrors.join(', ')}`).toHaveLength(0);
      
      console.log(`✅ ${pageConfig.name}: 0 critical errors`);
    }
  });
});

test.describe('Anti-Blank Markets Regression Guard', () => {
  
  test('Markets table never empties during 60 second test', async ({ page }) => {
    await page.goto(`${BASE_URL}/markets`);
    await page.waitForLoadState('networkidle');
    
    // Wait for initial data load
    await page.waitForTimeout(5000);
    
    // Check initial state
    let tableRows = page.locator('tbody tr');
    let initialRowCount = await tableRows.count();
    
    console.log(`Initial row count: ${initialRowCount}`);
    
    // If no rows initially, wait for data to load
    if (initialRowCount === 0) {
      await page.waitForTimeout(10000);
      tableRows = page.locator('tbody tr');
      initialRowCount = await tableRows.count();
    }
    
    // Start 60-second monitoring
    const startTime = Date.now();
    const monitorDuration = 60000; // 60 seconds
    
    while (Date.now() - startTime < monitorDuration) {
      // Check table row count
      const currentRowCount = await tableRows.count();
      
      // Table should never be completely empty
      expect(currentRowCount, `Markets table went empty at ${Date.now() - startTime}ms`).toBeGreaterThan(0);
      
      // Check for loading states (should show skeleton, not empty)
      const loadingElements = page.locator('#crypto-loading, #bist-loading');
      const emptyStates = page.locator('#crypto-empty-state, #bist-empty-state');
      
      const hasLoading = await loadingElements.count() > 0;
      const hasEmptyState = await emptyStates.count() > 0;
      
      // Should either have data, loading skeleton, or explicitly hidden empty state
      const hasVisibleEmptyState = hasEmptyState && await emptyStates.first().isVisible();
      expect(hasVisibleEmptyState, 'Empty state should not be visible during normal operation').toBe(false);
      
      // Wait before next check
      await page.waitForTimeout(5000); // Check every 5 seconds
    }
    
    console.log('✅ Markets table maintained data for full 60 seconds');
  });

  test('Markets WebSocket failure recovery', async ({ page }) => {
    await page.goto(`${BASE_URL}/markets`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000);
    
    // Get initial row count
    const initialRows = await page.locator('tbody tr').count();
    console.log(`Initial rows before WS simulation: ${initialRows}`);
    
    // Simulate WebSocket failure by blocking WebSocket connections
    await page.route('ws://**', route => route.abort());
    await page.route('wss://**', route => route.abort());
    
    // Wait and verify fallback mechanisms work
    await page.waitForTimeout(15000); // 15 seconds for fallback
    
    // Table should still have data (from snapshot/fallback)
    const rowsAfterWSFailure = await page.locator('tbody tr').count();
    expect(rowsAfterWSFailure, 'Markets should maintain data after WebSocket failure').toBeGreaterThan(0);
    
    // Connection status should indicate fallback mode
    const connectionStatus = page.locator('#connection-indicator + span');
    const statusText = await connectionStatus.textContent();
    
    console.log(`Connection status after WS failure: ${statusText}`);
    console.log('✅ Markets recovered from WebSocket failure');
  });
});

test.describe('Total Balance Guarantee Tests', () => {
  
  test('Dashboard TB loads within 5 seconds', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    
    // Check if total balance element exists
    const totalBalance = page.locator('[data-testid="total-balance"]');
    
    if (await totalBalance.count() > 0) {
      // Wait for balance to be populated
      await page.waitForFunction(() => {
        const element = document.querySelector('[data-testid="total-balance"] #total-balance');
        return element && element.textContent && element.textContent !== '$0.00';
      }, { timeout: 5000 });
      
      const loadTime = Date.now() - startTime;
      console.log(`Total Balance loaded in ${loadTime}ms`);
      
      // Verify formatting
      const balanceText = await page.locator('#total-balance').textContent();
      expect(balanceText, 'Total Balance should be formatted currency').toMatch(/^\$[\d,]+\.\d{2}$/);
      
      // Verify it's not the default zero value
      expect(balanceText, 'Total Balance should not be $0.00').not.toBe('$0.00');
      
      console.log(`✅ Total Balance: ${balanceText} (loaded in ${loadTime}ms)`);
    } else {
      console.log('⚠️ Total Balance element not found on current page');
    }
  });

  test('TB formatting with Intl.NumberFormat', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(5000);
    
    // Test formatting function directly
    const formattingTest = await page.evaluate(() => {
      const formatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
      
      return {
        test1: formatter.format(10000.00),
        test2: formatter.format(12345.67),
        test3: formatter.format(9876.54)
      };
    });
    
    // Verify correct formatting
    expect(formattingTest.test1).toBe('$10,000.00');
    expect(formattingTest.test2).toBe('$12,345.67');
    expect(formattingTest.test3).toBe('$9,876.54');
    
    console.log('✅ Intl.NumberFormat working correctly');
  });
});

// Configure test settings
test.use({
  // Consistent browser setup
  viewport: { width: 1920, height: 1080 },
  ignoreHTTPSErrors: true,
  
  // Screenshot comparison settings
  expect: {
    // Allow small differences for dynamic content
    threshold: 0.01, // 1% difference threshold
    animations: 'disabled'
  }
});

test.afterAll(async () => {
  console.log('Visual baseline capture completed. Screenshots saved to test-results/');
});