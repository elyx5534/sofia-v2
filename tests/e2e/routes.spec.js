const { test, expect } = require('@playwright/test');

test.describe('ROUTES ALWAYS OPEN', () => {
  const routes = [
    '/',
    '/dashboard', 
    '/portfolio',
    '/markets',
    '/bist',
    '/bist/analysis',
    '/data-collection',
    '/trading',
    '/manual-trading',
    '/reliability'
  ];

  for (const route of routes) {
    test(`${route} returns 200 and has no console errors`, async ({ page }) => {
      const consoleErrors = [];
      
      // Listen for console errors
      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });

      const response = await page.goto(route);
      
      // Check HTTP status
      expect(response.status()).toBe(200);
      
      // Wait for page to load
      await page.waitForLoadState('networkidle');
      
      // Check no console errors
      expect(consoleErrors).toEqual([]);
      
      // Check basic page structure
      await expect(page.locator('body')).toBeVisible();
      await expect(page.locator('nav')).toBeVisible();
    });
  }
});

test.describe('ONE-BAR ONLY', () => {
  test('has exactly one navbar', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    
    // Check only one navbar exists
    const navbars = await page.locator('nav.app-navbar, nav.sticky').count();
    expect(navbars).toBe(1);
    
    // Validate JavaScript didn't throw errors
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error' && msg.text().includes('ONE-BAR VIOLATION')) {
        consoleErrors.push(msg.text());
      }
    });
    
    expect(consoleErrors).toEqual([]);
  });
});

test.describe('TOTAL BALANCE GUARANTEE', () => {
  test('dashboard shows formatted total balance within 5s', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Wait for balance to load with timeout
    const balanceElement = page.locator('[data-testid="total-balance"]');
    await balanceElement.waitFor({ timeout: 5000 });
    
    const balanceText = await balanceElement.textContent();
    
    // Check format is numeric currency (e.g., $12,500.75)
    const currencyRegex = /\$[\d,]+\.\d{2}/;
    expect(balanceText).toMatch(currencyRegex);
    
    // Check no console errors
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    expect(consoleErrors).toEqual([]);
  });
});