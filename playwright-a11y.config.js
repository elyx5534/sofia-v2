// @ts-check
const { defineConfig } = require('@playwright/test');
const base = require('./playwright.config.js');

/**
 * Accessibility testing configuration
 */
module.exports = defineConfig({
  ...base,
  testDir: './tests/a11y',
  reporter: [['html', { outputFolder: 'test-results/a11y' }]],
});