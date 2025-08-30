const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test.describe('Accessibility Tests', () => {
  const routes = [
    { path: '/', name: 'Homepage' },
    { path: '/dashboard', name: 'Dashboard' },
    { path: '/markets', name: 'Markets' },
    { path: '/trading', name: 'Trading' },
    { path: '/manual-trading', name: 'Manual Trading' }
  ];

  for (const route of routes) {
    test(`${route.name} has no critical accessibility violations`, async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState('networkidle');

      const accessibilityScanResults = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze();

      // Filter critical violations
      const criticalViolations = accessibilityScanResults.violations.filter(
        violation => violation.impact === 'critical'
      );

      expect(criticalViolations).toEqual([]);
      
      // Log warnings but don't fail
      if (accessibilityScanResults.violations.length > 0) {
        console.log(`A11y violations on ${route.path}:`, 
          accessibilityScanResults.violations.map(v => v.id));
      }
    });
  }
});