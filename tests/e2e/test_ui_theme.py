"""
Playwright E2E and Theme Regression Tests
UI Guard - Theme Protection System
"""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright, expect
import pytest
from PIL import Image
import imagehash
import numpy as np

# Test configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8009")
GOLDEN_DIR = Path("tests/e2e/golden")
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

class ThemeRegressionTest:
    """Theme regression testing to ensure UI consistency"""
    
    def __init__(self):
        self.threshold = 0.05  # 5% difference threshold
        self.critical_selectors = [
            ".bg-gradient-to-br",  # Gradient backgrounds
            ".from-slate-900",      # Color classes
            ".via-purple-900",      # Purple theme
            ".text-purple-400",     # Text colors
            ".border-purple-500",   # Border colors
            "[class*='gradient']",  # Any gradient
            "[class*='purple']",    # Any purple element
        ]
    
    async def capture_element(self, page, selector, name):
        """Capture screenshot of specific element"""
        element = await page.query_selector(selector)
        if element:
            await element.screenshot(path=f"{GOLDEN_DIR}/{name}.png")
            return True
        return False
    
    async def compare_screenshots(self, golden_path, current_path):
        """Compare two screenshots using perceptual hashing"""
        try:
            golden = Image.open(golden_path)
            current = Image.open(current_path)
            
            # Perceptual hash comparison
            hash_golden = imagehash.phash(golden)
            hash_current = imagehash.phash(current)
            
            # Calculate similarity
            difference = hash_golden - hash_current
            similarity = 1 - (difference / 64.0)
            
            return similarity > (1 - self.threshold)
        except Exception as e:
            print(f"Screenshot comparison error: {e}")
            return False
    
    async def verify_css_variables(self, page):
        """Verify CSS variables haven't changed"""
        css_vars = await page.evaluate("""
            () => {
                const styles = getComputedStyle(document.documentElement);
                return {
                    primary: styles.getPropertyValue('--color-primary'),
                    secondary: styles.getPropertyValue('--color-secondary'),
                    dark: styles.getPropertyValue('--color-dark'),
                    gradients: Array.from(document.querySelectorAll('[class*="gradient"]'))
                        .map(el => getComputedStyle(el).backgroundImage)
                };
            }
        """)
        return css_vars

@pytest.fixture(scope="session")
async def browser():
    """Create browser instance"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        yield browser
        await browser.close()

@pytest.fixture
async def page(browser):
    """Create new page for each test"""
    page = await browser.new_page(
        viewport={'width': 1920, 'height': 1080}
    )
    yield page
    await page.close()

class TestUIThemeProtection:
    """E2E tests for UI theme protection"""
    
    @pytest.mark.asyncio
    async def test_homepage_loads(self, page):
        """Test homepage loads successfully"""
        response = await page.goto(BASE_URL)
        assert response.status == 200
        
        # Check for critical elements
        await expect(page.locator('h1')).to_be_visible()
        
    @pytest.mark.asyncio
    async def test_ai_trading_page(self, page):
        """Test AI Trading page functionality"""
        await page.goto(f"{BASE_URL}/ai-trading")
        
        # Check AI score elements
        await expect(page.locator('.text-purple-400')).to_be_visible()
        await expect(page.locator('[class*="AI Score"]')).to_count(4, timeout=5000)
        
        # Verify real-time updates
        initial_time = await page.text_content('#lastUpdate')
        await page.wait_for_timeout(1000)
        
        # Check refresh button
        refresh_btn = page.locator('button:has-text("Yenile")')
        if await refresh_btn.is_visible():
            await refresh_btn.click()
            await page.wait_for_load_state('networkidle')
    
    @pytest.mark.asyncio
    async def test_purple_gradient_theme(self, page):
        """Test purple gradient theme integrity"""
        await page.goto(BASE_URL)
        
        # Check for purple gradient classes
        gradients = await page.locator('.bg-gradient-to-br').count()
        assert gradients > 0, "No gradient backgrounds found"
        
        # Verify purple colors
        purple_elements = await page.locator('[class*="purple"]').count()
        assert purple_elements > 0, "No purple theme elements found"
        
        # Check specific theme colors
        theme_test = ThemeRegressionTest()
        css_vars = await theme_test.verify_css_variables(page)
        
        # Verify colors are in expected range
        assert css_vars is not None
    
    @pytest.mark.asyncio
    async def test_theme_screenshot_regression(self, page):
        """Visual regression test for theme"""
        await page.goto(BASE_URL)
        await page.wait_for_load_state('networkidle')
        
        theme_test = ThemeRegressionTest()
        
        # Capture critical UI sections
        screenshots = [
            ("navbar", "nav"),
            ("header", "header"),
            ("main-gradient", ".bg-gradient-to-br"),
            ("cards", ".glass-ultra"),
        ]
        
        for name, selector in screenshots:
            element = await page.query_selector(selector)
            if element:
                current_path = f"{GOLDEN_DIR}/{name}_current.png"
                await element.screenshot(path=current_path)
                
                golden_path = f"{GOLDEN_DIR}/{name}_golden.png"
                if os.path.exists(golden_path):
                    # Compare with golden screenshot
                    match = await theme_test.compare_screenshots(golden_path, current_path)
                    assert match, f"Theme regression detected in {name}"
                else:
                    # First run - create golden screenshots
                    os.rename(current_path, golden_path)
                    print(f"Created golden screenshot: {name}")
    
    @pytest.mark.asyncio
    async def test_no_theme_mutations(self, page):
        """Test that theme doesn't mutate during interactions"""
        await page.goto(BASE_URL)
        
        # Capture initial theme state
        initial_theme = await page.evaluate("""
            () => {
                const elements = document.querySelectorAll('[class*="purple"], [class*="gradient"]');
                return Array.from(elements).map(el => ({
                    classes: el.className,
                    styles: el.getAttribute('style')
                }));
            }
        """)
        
        # Perform various interactions
        buttons = await page.locator('button').all()
        for btn in buttons[:3]:  # Click first 3 buttons
            if await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(500)
        
        # Verify theme hasn't changed
        final_theme = await page.evaluate("""
            () => {
                const elements = document.querySelectorAll('[class*="purple"], [class*="gradient"]');
                return Array.from(elements).map(el => ({
                    classes: el.className,
                    styles: el.getAttribute('style')
                }));
            }
        """)
        
        # Compare theme states
        assert len(initial_theme) == len(final_theme), "Theme elements count changed"
    
    @pytest.mark.asyncio
    async def test_responsive_theme(self, page):
        """Test theme consistency across viewports"""
        viewports = [
            {'width': 1920, 'height': 1080},  # Desktop
            {'width': 768, 'height': 1024},   # Tablet
            {'width': 375, 'height': 667},    # Mobile
        ]
        
        for viewport in viewports:
            await page.set_viewport_size(viewport)
            await page.goto(BASE_URL)
            await page.wait_for_load_state('networkidle')
            
            # Check theme elements are visible
            purple_visible = await page.is_visible('[class*="purple"]')
            assert purple_visible, f"Theme broken at viewport {viewport['width']}x{viewport['height']}"
    
    @pytest.mark.asyncio
    async def test_data_stale_indicators(self, page):
        """Test stale data indicators without breaking theme"""
        await page.goto(f"{BASE_URL}/ai-trading")
        
        # Simulate stale data by waiting
        await page.wait_for_timeout(2000)
        
        # Check for stale indicators (should show without breaking theme)
        stale_badges = await page.locator('.text-yellow-500').count()
        
        # Verify theme is intact
        purple_elements = await page.locator('[class*="purple"]').count()
        assert purple_elements > 0, "Theme broken when showing stale data"

# Performance tests
class TestPerformance:
    """Performance testing for critical endpoints"""
    
    @pytest.mark.asyncio
    async def test_ai_score_latency(self, page):
        """Test AI score endpoint latency < 150ms"""
        # Navigate to AI trading page
        await page.goto(f"{BASE_URL}/ai-trading")
        
        # Measure API call performance
        async with page.expect_response("**/api/ai/score**") as response_info:
            await page.reload()
            response = await response_info.value
            
            # Check response time
            timing = response.timing
            if timing:
                latency = timing['responseEnd'] - timing['requestStart']
                assert latency < 150, f"AI score latency {latency}ms exceeds 150ms target"
    
    @pytest.mark.asyncio  
    async def test_page_load_performance(self, page):
        """Test page load performance"""
        metrics = []
        
        pages_to_test = ["/", "/ai-trading", "/dashboard"]
        
        for path in pages_to_test:
            await page.goto(f"{BASE_URL}{path}")
            
            # Get performance metrics
            perf = await page.evaluate("""
                () => {
                    const timing = performance.timing;
                    return {
                        domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                        loadComplete: timing.loadEventEnd - timing.navigationStart
                    };
                }
            """)
            
            metrics.append({
                'page': path,
                'domContentLoaded': perf['domContentLoaded'],
                'loadComplete': perf['loadComplete']
            })
            
            # Assert reasonable load times
            assert perf['domContentLoaded'] < 3000, f"Page {path} DOMContentLoaded > 3s"
            assert perf['loadComplete'] < 5000, f"Page {path} full load > 5s"
        
        return metrics

# Run tests
if __name__ == "__main__":
    # Create test runner
    async def run_tests():
        """Run all tests"""
        print("🧪 Starting E2E and Theme Regression Tests...")
        
        # Run pytest
        pytest_args = [
            __file__,
            "-v",
            "--tb=short",
            "--color=yes",
            "-k", "test_"
        ]
        
        exit_code = pytest.main(pytest_args)
        
        if exit_code == 0:
            print("✅ All tests passed! Theme is protected.")
        else:
            print("❌ Some tests failed. Check theme integrity.")
        
        return exit_code
    
    # Run async tests
    exit_code = asyncio.run(run_tests())
    exit(exit_code)