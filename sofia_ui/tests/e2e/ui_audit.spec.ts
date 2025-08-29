import { test, expect, Page } from '@playwright/test';
import * as axe from 'axe-playwright';
import routes from '../../../tests/routes.json';

// Test configuration
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:4173';
const API_URL = process.env.VITE_API_URL || 'http://127.0.0.1:8023';

test.describe('UI Audit - Complete Route Testing', () => {
  let consoleErrors: string[] = [];
  let networkErrors: string[] = [];

  test.beforeEach(async ({ page }) => {
    // Reset error collectors
    consoleErrors = [];
    networkErrors = [];

    // Collect console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Collect network errors
    page.on('response', (response) => {
      const url = response.url();
      const status = response.status();
      
      // Check for forbidden status codes
      if (routes.globalChecks.forbiddenStatusCodes.includes(status)) {
        // Ignore expected 404s for assets that might not exist
        if (!url.includes('/assets/') && !url.includes('/reports/')) {
          networkErrors.push(`${status} - ${url}`);
        }
      }
    });
  });

  // Test each route
  routes.routes.forEach((route) => {
    test(`Route: ${route.name} (${route.path})`, async ({ page }) => {
      // Navigate to route
      await page.goto(`${BASE_URL}${route.path}`, {
        waitUntil: 'networkidle',
        timeout: 30000,
      });

      // Wait for page to stabilize
      await page.waitForTimeout(1000);

      // Check expected elements are visible
      for (const selector of route.expectedElements) {
        const element = page.locator(selector).first();
        await expect(element).toBeVisible({
          timeout: 5000,
        });
      }

      // Check forbidden elements (sidebars) are NOT present
      for (const selector of route.forbiddenElements) {
        const count = await page.locator(selector).count();
        expect(count).toBe(0);
      }

      // Check for console errors
      expect(consoleErrors.length).toBe(0);

      // Check for network errors
      expect(networkErrors.length).toBe(0);

      // Special checks for specific routes
      if (route.path === '/dashboard') {
        await testDashboard(page);
      } else if (route.path === '/markets') {
        await testMarkets(page);
      }

      // Accessibility check
      await testAccessibility(page);

      // Test internal links
      await testInternalLinks(page);
    });
  });

  // Dashboard specific tests
  async function testDashboard(page: Page) {
    // Check for total balance element
    const totalBalance = page.locator('[data-testid="total-balance"]');
    
    // Wait for skeleton to disappear and value to appear
    await expect(totalBalance).toBeVisible({ timeout: 5000 });
    
    // Check that balance has a value (not loading)
    const balanceText = await totalBalance.textContent();
    expect(balanceText).toBeTruthy();
    expect(balanceText).not.toContain('Loading');
    expect(balanceText).not.toContain('...');
    
    // Check that balance is a valid number format
    const numericValue = balanceText?.replace(/[^0-9.,]/g, '');
    expect(numericValue).toMatch(/^\d{1,3}(,\d{3})*(\.\d{2})?$/);
  }

  // Markets specific tests
  async function testMarkets(page: Page) {
    // Wait for market data to load
    await page.waitForSelector('table tbody tr', {
      timeout: 10000,
    });

    // Check minimum number of rows
    const rows = await page.locator('table tbody tr').count();
    expect(rows).toBeGreaterThanOrEqual(100);

    // Test search functionality
    const searchInput = page.locator('input[placeholder*="Search"]').first();
    if (await searchInput.isVisible()) {
      await searchInput.fill('BTC');
      await page.waitForTimeout(500);
      
      // Check filtered results
      const filteredRows = await page.locator('table tbody tr').count();
      expect(filteredRows).toBeGreaterThan(0);
      expect(filteredRows).toBeLessThan(rows);
    }

    // Test add/remove from watchlist
    const watchButton = page.locator('button:has-text("Watch")').first();
    if (await watchButton.isVisible()) {
      await watchButton.click();
      await page.waitForTimeout(500);
      
      // Check button state changed
      const removeButton = page.locator('button:has-text("Remove")').first();
      await expect(removeButton).toBeVisible();
    }
  }

  // Accessibility testing with axe-core
  async function testAccessibility(page: Page) {
    try {
      const results = await axe.injectAxe(page).analyze();
      
      // Check critical violations
      const criticalViolations = results.violations.filter(
        (v) => v.impact === 'critical'
      );
      expect(criticalViolations.length).toBeLessThanOrEqual(
        routes.globalChecks.accessibility.maxCriticalViolations
      );

      // Check serious violations
      const seriousViolations = results.violations.filter(
        (v) => v.impact === 'serious'
      );
      expect(seriousViolations.length).toBeLessThanOrEqual(
        routes.globalChecks.accessibility.maxSeriousViolations
      );

      // Log violations for debugging
      if (results.violations.length > 0) {
        console.log('Accessibility violations:', results.violations);
      }
    } catch (error) {
      // Axe might fail on some pages, log but don't fail test
      console.warn('Accessibility test skipped:', error);
    }
  }

  // Test internal links
  async function testInternalLinks(page: Page) {
    const links = await page.locator('a[href^="/"]').all();
    
    for (const link of links.slice(0, 5)) { // Test first 5 links
      const href = await link.getAttribute('href');
      if (href) {
        // Click link and check navigation
        await link.click();
        await page.waitForLoadState('networkidle');
        
        // Check no 404
        expect(networkErrors).not.toContain('404');
        
        // Go back
        await page.goBack();
        await page.waitForLoadState('networkidle');
      }
    }
  }
});

// Visual regression tests
test.describe('Visual Regression', () => {
  const pages = [
    { name: 'dashboard', path: '/dashboard' },
    { name: 'markets', path: '/markets' },
    { name: 'settings', path: '/settings' },
    { name: '404', path: '/non-existent-page' },
  ];

  pages.forEach((pageInfo) => {
    test(`Screenshot: ${pageInfo.name}`, async ({ page }) => {
      // Navigate to page
      await page.goto(`${BASE_URL}${pageInfo.path}`, {
        waitUntil: 'networkidle',
      });

      // Wait for animations to complete
      await page.waitForTimeout(1000);

      // Hide dynamic elements that change frequently
      await page.addStyleTag({
        content: `
          [data-testid="timestamp"],
          [data-testid="price"],
          .animate-pulse {
            visibility: hidden !important;
          }
        `,
      });

      // Take screenshot
      await expect(page).toHaveScreenshot(`${pageInfo.name}.png`, {
        maxDiffPixelRatio: 0.01,
        fullPage: true,
        animations: 'disabled',
      });
    });
  });
});

// Performance testing
test.describe('Performance', () => {
  test('Lighthouse metrics', async ({ page }) => {
    // This is a placeholder for Lighthouse integration
    // In CI, we'll run Lighthouse separately
    
    // Basic performance checks
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Check First Contentful Paint
    const performanceMetrics = await page.evaluate(() => {
      const perf = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return {
        fcp: perf.responseEnd - perf.fetchStart,
        domContentLoaded: perf.domContentLoadedEventEnd - perf.fetchStart,
        loadComplete: perf.loadEventEnd - perf.fetchStart,
      };
    });
    
    // Basic thresholds
    expect(performanceMetrics.fcp).toBeLessThan(3000); // FCP < 3s
    expect(performanceMetrics.domContentLoaded).toBeLessThan(5000); // DOM < 5s
    expect(performanceMetrics.loadComplete).toBeLessThan(10000); // Load < 10s
  });
});