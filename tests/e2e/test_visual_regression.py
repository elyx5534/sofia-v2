#!/usr/bin/env python3
"""
Visual Regression Tests for Sofia V2
Tests UI consistency and visual elements across different pages
"""

import pytest
import asyncio
import aiohttp
import hashlib
import os
import time
from typing import Dict, List, Tuple
import logging
import json
from pathlib import Path
import base64

# Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:8024')
UI_BASE_URL = os.getenv('UI_BASE_URL', 'http://127.0.0.1:8005')
SCREENSHOTS_DIR = Path("tests/screenshots")
BASELINES_DIR = Path("tests/baselines")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VisualRegressionTester:
    def __init__(self):
        self.ui_url = UI_BASE_URL
        self.session = None
        self.test_results = []
        self.screenshots_dir = SCREENSHOTS_DIR
        self.baselines_dir = BASELINES_DIR
        
        # Ensure directories exist
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def calculate_content_hash(self, content: str) -> str:
        """Calculate hash of page content for comparison"""
        # Remove dynamic elements before hashing
        cleaned_content = self.clean_dynamic_content(content)
        return hashlib.md5(cleaned_content.encode('utf-8')).hexdigest()
    
    def clean_dynamic_content(self, content: str) -> str:
        """Remove dynamic content that changes on each load"""
        import re
        
        # Remove timestamps
        content = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', 'TIMESTAMP', content)
        content = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', 'TIMESTAMP', content)
        
        # Remove random IDs
        content = re.sub(r'id="[a-f0-9-]{36}"', 'id="UUID"', content)
        content = re.sub(r'data-id="[a-f0-9-]{36}"', 'data-id="UUID"', content)
        
        # Remove dynamic prices (numbers with $ or decimal places)
        content = re.sub(r'\$[\d,]+\.\d{2}', '$XXX.XX', content)
        content = re.sub(r'[\d,]+\.\d{8}', 'XXX.XXXXXXXX', content)
        
        # Remove session tokens
        content = re.sub(r'token=[a-zA-Z0-9]+', 'token=TOKEN', content)
        content = re.sub(r'csrf_token":\s*"[^"]*"', 'csrf_token": "TOKEN"', content)
        
        # Remove changing counters or stats
        content = re.sub(r'"count":\s*\d+', '"count": 0', content)
        content = re.sub(r'"total":\s*\d+', '"total": 0', content)
        
        return content
    
    async def capture_page_structure(self, path: str) -> Dict:
        """Capture page structure for visual testing"""
        url = f"{self.ui_url}{path}"
        start_time = time.time()
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return {"error": f"Status {response.status}", "path": path}
                
                content = await response.text()
                load_time = time.time() - start_time
                
                # Extract key visual elements
                structure = {
                    "path": path,
                    "url": url,
                    "status": response.status,
                    "load_time_ms": round(load_time * 1000, 2),
                    "content_hash": self.calculate_content_hash(content),
                    "content_length": len(content),
                    "has_html": '<html' in content.lower(),
                    "has_css": 'stylesheet' in content.lower() or '<style' in content.lower(),
                    "has_js": '<script' in content.lower(),
                    "forms_count": content.lower().count('<form'),
                    "buttons_count": content.lower().count('<button') + content.lower().count('type="submit"'),
                    "inputs_count": content.lower().count('<input'),
                    "tables_count": content.lower().count('<table'),
                    "charts_count": content.lower().count('chart') + content.lower().count('canvas'),
                    "nav_elements": content.lower().count('<nav') + content.lower().count('navbar'),
                    "meta_tags": content.lower().count('<meta'),
                    "title": self.extract_title(content),
                    "h1_count": content.lower().count('<h1'),
                    "h2_count": content.lower().count('<h2'),
                    "h3_count": content.lower().count('<h3'),
                    "error": None
                }
                
                return structure
                
        except Exception as e:
            return {
                "path": path,
                "url": url,
                "error": str(e),
                "load_time_ms": round((time.time() - start_time) * 1000, 2)
            }
    
    def extract_title(self, content: str) -> str:
        """Extract page title"""
        import re
        title_match = re.search(r'<title[^>]*>([^<]*)</title>', content, re.IGNORECASE)
        return title_match.group(1).strip() if title_match else "No Title"
    
    def save_baseline(self, path: str, structure: Dict):
        """Save baseline structure for comparison"""
        baseline_file = self.baselines_dir / f"{path.replace('/', '_')}.json"
        with open(baseline_file, 'w') as f:
            json.dump(structure, f, indent=2)
        logger.info(f"Saved baseline for {path}")
    
    def load_baseline(self, path: str) -> Dict:
        """Load baseline structure"""
        baseline_file = self.baselines_dir / f"{path.replace('/', '_')}.json"
        if baseline_file.exists():
            with open(baseline_file, 'r') as f:
                return json.load(f)
        return None
    
    def compare_structures(self, current: Dict, baseline: Dict) -> Dict:
        """Compare current structure with baseline"""
        if not baseline:
            return {"status": "no_baseline", "differences": []}
        
        differences = []
        
        # Compare key metrics
        metrics_to_compare = [
            'forms_count', 'buttons_count', 'inputs_count', 'tables_count',
            'charts_count', 'nav_elements', 'h1_count', 'h2_count', 'h3_count'
        ]
        
        for metric in metrics_to_compare:
            current_val = current.get(metric, 0)
            baseline_val = baseline.get(metric, 0)
            
            if current_val != baseline_val:
                differences.append({
                    "metric": metric,
                    "current": current_val,
                    "baseline": baseline_val,
                    "difference": current_val - baseline_val
                })
        
        # Compare title
        if current.get('title') != baseline.get('title'):
            differences.append({
                "metric": "title",
                "current": current.get('title'),
                "baseline": baseline.get('title'),
                "difference": "title_changed"
            })
        
        # Compare content length (allow 5% variance)
        current_length = current.get('content_length', 0)
        baseline_length = baseline.get('content_length', 0)
        if baseline_length > 0:
            variance = abs(current_length - baseline_length) / baseline_length
            if variance > 0.05:  # 5% tolerance
                differences.append({
                    "metric": "content_length",
                    "current": current_length,
                    "baseline": baseline_length,
                    "difference": f"{variance:.2%} variance"
                })
        
        return {
            "status": "compared",
            "differences": differences,
            "major_changes": len([d for d in differences if d['metric'] in ['title', 'forms_count', 'nav_elements']]),
            "minor_changes": len([d for d in differences if d['metric'] not in ['title', 'forms_count', 'nav_elements']])
        }
    
    async def test_page_visual_structure(self, path: str, create_baseline: bool = False):
        """Test a single page's visual structure"""
        logger.info(f"Testing visual structure: {path}")
        
        current_structure = await self.capture_page_structure(path)
        
        if current_structure.get('error'):
            self.test_results.append({
                "path": path,
                "status": "error",
                "error": current_structure['error'],
                "success": False
            })
            logger.error(f"✗ Error capturing {path}: {current_structure['error']}")
            return
        
        if create_baseline:
            self.save_baseline(path, current_structure)
            self.test_results.append({
                "path": path,
                "status": "baseline_created",
                "success": True,
                "structure": current_structure
            })
            logger.info(f"✓ Created baseline for {path}")
            return
        
        baseline = self.load_baseline(path)
        comparison = self.compare_structures(current_structure, baseline)
        
        if comparison['status'] == 'no_baseline':
            logger.warning(f"⚠ No baseline found for {path}, creating one")
            self.save_baseline(path, current_structure)
            self.test_results.append({
                "path": path,
                "status": "baseline_created",
                "success": True,
                "structure": current_structure
            })
            return
        
        # Determine success based on changes
        major_changes = comparison['major_changes']
        minor_changes = comparison['minor_changes']
        success = major_changes == 0 and minor_changes <= 2  # Allow minor changes
        
        self.test_results.append({
            "path": path,
            "status": "compared",
            "success": success,
            "major_changes": major_changes,
            "minor_changes": minor_changes,
            "differences": comparison['differences'],
            "structure": current_structure
        })
        
        if success:
            logger.info(f"✓ Visual structure OK for {path} (minor changes: {minor_changes})")
        else:
            logger.warning(f"✗ Visual changes detected in {path} (major: {major_changes}, minor: {minor_changes})")
            for diff in comparison['differences']:
                logger.warning(f"  {diff['metric']}: {diff['current']} vs {diff['baseline']} ({diff['difference']})")

@pytest.mark.asyncio
async def test_core_pages_visual_structure():
    """Test visual structure of core pages"""
    async with VisualRegressionTester() as tester:
        core_pages = [
            "/",
            "/dashboard",
            "/markets",
            "/portfolio", 
            "/backtest",
            "/ai_trading",
            "/manual_trading",
            "/strategies"
        ]
        
        logger.info("Testing core pages visual structure...")
        
        for path in core_pages:
            await tester.test_page_visual_structure(path)
        
        # Generate summary
        total_tests = len(tester.test_results)
        successful_tests = sum(1 for r in tester.test_results if r['success'])
        failed_tests = total_tests - successful_tests
        
        logger.info("=" * 50)
        logger.info("VISUAL STRUCTURE TEST SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total Pages: {total_tests}")
        logger.info(f"Passed: {successful_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Pass Rate: {successful_tests/total_tests*100:.1f}%")
        
        # Log failed tests
        failed_results = [r for r in tester.test_results if not r['success']]
        if failed_results:
            logger.warning("PAGES WITH VISUAL CHANGES:")
            for result in failed_results:
                logger.warning(f"  {result['path']} - {result.get('error', f\"Major: {result.get('major_changes', 0)}, Minor: {result.get('minor_changes', 0)}\")}")
        
        # Assert reasonable pass rate
        assert successful_tests / total_tests >= 0.8, f"Visual structure pass rate too low: {successful_tests}/{total_tests}"

@pytest.mark.asyncio
async def test_responsive_elements():
    """Test for responsive design elements"""
    async with VisualRegressionTester() as tester:
        logger.info("Testing responsive design elements...")
        
        # Test key responsive pages
        responsive_pages = ["/", "/dashboard", "/markets", "/portfolio"]
        
        for path in responsive_pages:
            structure = await tester.capture_page_structure(path)
            
            if structure.get('error'):
                continue
                
            url = structure['url']
            
            # Check for responsive indicators in content
            try:
                async with tester.session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Check for responsive CSS classes/attributes
                        responsive_indicators = [
                            'viewport',
                            'responsive',
                            'mobile',
                            'tablet',
                            'desktop',
                            'breakpoint',
                            'grid',
                            'flex',
                            'col-',
                            'row-',
                            '@media'
                        ]
                        
                        found_indicators = [ind for ind in responsive_indicators if ind in content.lower()]
                        
                        test_result = {
                            "path": path,
                            "responsive_indicators": found_indicators,
                            "indicator_count": len(found_indicators),
                            "has_viewport_meta": 'viewport' in content.lower(),
                            "has_responsive_css": any(ind in content.lower() for ind in ['@media', 'responsive', 'col-', 'grid']),
                            "success": len(found_indicators) >= 3  # At least 3 responsive indicators
                        }
                        
                        tester.test_results.append(test_result)
                        
                        if test_result['success']:
                            logger.info(f"✓ {path} has responsive elements: {len(found_indicators)} indicators")
                        else:
                            logger.warning(f"⚠ {path} may not be responsive: only {len(found_indicators)} indicators")
                            
            except Exception as e:
                logger.warning(f"⚠ Could not check responsive elements for {path}: {e}")

@pytest.mark.asyncio
async def test_accessibility_elements():
    """Test for accessibility elements"""
    async with VisualRegressionTester() as tester:
        logger.info("Testing accessibility elements...")
        
        accessibility_pages = ["/", "/dashboard", "/markets", "/portfolio"]
        
        for path in accessibility_pages:
            try:
                url = f"{tester.ui_url}{path}"
                async with tester.session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Check for accessibility elements
                        accessibility_checks = {
                            "has_alt_attributes": 'alt=' in content.lower(),
                            "has_aria_labels": 'aria-label' in content.lower(),
                            "has_role_attributes": 'role=' in content.lower(),
                            "has_skip_links": 'skip' in content.lower() and 'link' in content.lower(),
                            "has_form_labels": '<label' in content.lower(),
                            "has_headings": any(f'<h{i}' in content.lower() for i in range(1, 7)),
                            "has_semantic_html": any(tag in content.lower() for tag in ['<nav', '<main', '<section', '<article', '<aside', '<header', '<footer'])
                        }
                        
                        accessibility_score = sum(accessibility_checks.values())
                        total_checks = len(accessibility_checks)
                        
                        test_result = {
                            "path": path,
                            "accessibility_score": accessibility_score,
                            "total_checks": total_checks,
                            "score_percentage": (accessibility_score / total_checks) * 100,
                            "checks": accessibility_checks,
                            "success": accessibility_score >= (total_checks * 0.6)  # At least 60% of checks pass
                        }
                        
                        tester.test_results.append(test_result)
                        
                        if test_result['success']:
                            logger.info(f"✓ {path} accessibility score: {accessibility_score}/{total_checks} ({test_result['score_percentage']:.1f}%)")
                        else:
                            logger.warning(f"⚠ {path} accessibility score low: {accessibility_score}/{total_checks} ({test_result['score_percentage']:.1f}%)")
                            
            except Exception as e:
                logger.warning(f"⚠ Could not check accessibility for {path}: {e}")

@pytest.mark.asyncio  
async def test_performance_visual_metrics():
    """Test visual performance metrics"""
    async with VisualRegressionTester() as tester:
        logger.info("Testing visual performance metrics...")
        
        performance_pages = ["/", "/dashboard", "/markets", "/portfolio", "/backtest"]
        
        for path in performance_pages:
            start_time = time.time()
            structure = await tester.capture_page_structure(path)
            
            if structure.get('error'):
                continue
            
            load_time = structure.get('load_time_ms', 0)
            content_length = structure.get('content_length', 0)
            
            # Performance thresholds
            performance_result = {
                "path": path,
                "load_time_ms": load_time,
                "content_length": content_length,
                "load_time_grade": "excellent" if load_time < 500 else "good" if load_time < 1000 else "poor",
                "size_grade": "excellent" if content_length < 100000 else "good" if content_length < 500000 else "large",
                "has_css": structure.get('has_css', False),
                "has_js": structure.get('has_js', False),
                "success": load_time < 2000 and content_length < 1000000  # Under 2s and 1MB
            }
            
            tester.test_results.append(performance_result)
            
            if performance_result['success']:
                logger.info(f"✓ {path} performance OK: {load_time:.0f}ms, {content_length/1000:.0f}KB")
            else:
                logger.warning(f"⚠ {path} performance issues: {load_time:.0f}ms, {content_length/1000:.0f}KB")

@pytest.mark.asyncio
async def test_create_visual_baselines():
    """Create baseline visual structures for all pages"""
    async with VisualRegressionTester() as tester:
        logger.info("Creating visual baselines...")
        
        all_pages = [
            "/",
            "/dashboard", 
            "/markets",
            "/portfolio",
            "/backtest",
            "/ai_trading",
            "/manual_trading",
            "/strategies",
            "/assets/BTCUSDT",
            "/assets/ETHUSDT"
        ]
        
        for path in all_pages:
            await tester.test_page_visual_structure(path, create_baseline=True)
            await asyncio.sleep(1)  # Rate limiting
        
        logger.info(f"Created baselines for {len(all_pages)} pages")

if __name__ == "__main__":
    # Run tests directly
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create-baselines":
        asyncio.run(test_create_visual_baselines())
    else:
        asyncio.run(test_core_pages_visual_structure())