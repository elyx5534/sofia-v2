"""
Template Resolution System with Canonical Mapping
"""

import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from jinja2 import FileSystemLoader, Environment

logger = logging.getLogger(__name__)


# Canonical template mapping - old names to canonical names
CANON_MAP = {
    # Legacy mappings (if any exist)
    'dashboard_ultimate.html': 'dashboard.html',
    'dashboard_pro.html': 'dashboard.html',
    'dashboard_v2.html': 'dashboard.html',
    'assets_ultra.html': 'assets_detail.html',
    'assets_pro.html': 'assets_detail.html',
    'markets_pro.html': 'markets.html',
    'markets_ultimate.html': 'markets.html',
    'live_grid.html': 'live.html',
    'live_trading.html': 'live.html',
    'settings_pro.html': 'settings.html',
    'config.html': 'settings.html',
    'showcase_symbol.html': 'showcase.html',
    'showcase_detail.html': 'showcase.html',
    'analysis_detail.html': 'analysis.html',
    'strategy_cards.html': 'cards.html',
    'backtest_page.html': 'backtest.html',
    'strategies_list.html': 'strategies.html',
    
    # Trading templates
    'manual_trading.html': 'trade_manual.html',
    'trading_manual.html': 'trade_manual.html', 
    'manual.html': 'trade_manual.html',
    'ai_trading.html': 'trade_ai.html',
    'trading_ai.html': 'trade_ai.html',
    'ai.html': 'trade_ai.html',
    
    # Canonical names (map to themselves)
    'trade_manual.html': 'trade_manual.html',
    'trade_ai.html': 'trade_ai.html',
    'dashboard.html': 'dashboard.html',
    'markets.html': 'markets.html', 
    'settings.html': 'settings.html',
    'live.html': 'live.html',
    'showcase.html': 'showcase.html',
    'analysis.html': 'analysis.html',
    'cards.html': 'cards.html',
    'backtest.html': 'backtest.html',
    'strategies.html': 'strategies.html',
    'assets_detail.html': 'assets_detail.html',
    'homepage.html': 'homepage.html',
    'homepage_glass_dark_stable.html': 'homepage_glass_dark_stable.html',
    'base.html': 'base.html',
    
    # Stable UI aliases  
    'glass_dark': 'homepage_glass_dark_stable.html',
    'stable_ui': 'homepage_glass_dark_stable.html'
}


class TemplateResolver:
    """Template resolver with multi-path search and canonical mapping"""
    
    def __init__(self):
        # Multiple template search paths
        self.template_paths = [
            "sofia_ui/templates",
            "templates", 
            "src/templates",
            "ui/templates"
        ]
        
        # Find existing paths
        self.existing_paths = []
        for path in self.template_paths:
            if os.path.exists(path):
                self.existing_paths.append(path)
        
        if not self.existing_paths:
            # Fallback to current directory
            self.existing_paths = ["."]
        
        logger.info(f"Template resolver initialized with paths: {self.existing_paths}")
        
        # Create Jinja environment with multi-path loader and custom filters
        loader = FileSystemLoader(self.existing_paths)
        self.jinja_env = Environment(loader=loader, autoescape=True)
        
        # Add custom filters
        self.jinja_env.filters['format_currency'] = self._format_currency
        
        # FastAPI templates instance for compatibility
        self.templates = Jinja2Templates(directory=self.existing_paths[0])
        
        # Template cache
        self.template_cache: Dict[str, str] = {}
        self.resolution_log: List[Dict[str, Any]] = []
    
    def _format_currency(self, value, symbol="$"):
        """Format currency with proper formatting for TOTAL BALANCE GUARANTEE"""
        try:
            if value is None:
                return f"{symbol}0.00"
            
            # Handle string inputs
            if isinstance(value, str):
                # Remove existing currency symbols and spaces
                clean_value = value.replace("$", "").replace(",", "").strip()
                if clean_value == "":
                    return f"{symbol}0.00"
                value = float(clean_value)
            
            # Format as currency with commas and 2 decimal places
            formatted = f"{symbol}{value:,.2f}"
            return formatted
            
        except (ValueError, TypeError):
            logger.warning(f"Currency formatting failed for value: {value}")
            return f"{symbol}0.00"
    
    def resolve_template(self, template_name: str) -> str:
        """Resolve template name to canonical version"""
        
        # Check cache first
        if template_name in self.template_cache:
            return self.template_cache[template_name]
        
        # Check canonical mapping
        canonical_name = CANON_MAP.get(template_name, template_name)
        
        # Verify template exists
        template_exists = False
        actual_path = None
        
        for search_path in self.existing_paths:
            template_path = os.path.join(search_path, canonical_name)
            if os.path.exists(template_path):
                template_exists = True
                actual_path = template_path
                break
        
        if not template_exists:
            # Template not found - log and use fallback
            logger.warning(f"Template {canonical_name} not found in paths: {self.existing_paths}")
            
            # Try base template as fallback
            for search_path in self.existing_paths:
                base_path = os.path.join(search_path, "base.html")
                if os.path.exists(base_path):
                    canonical_name = "base.html"
                    actual_path = base_path
                    template_exists = True
                    break
        
        # Log resolution
        resolution_entry = {
            'requested': template_name,
            'canonical': canonical_name,
            'exists': template_exists,
            'path': actual_path,
            'timestamp': logger.info.__self__.name if hasattr(logger.info, '__self__') else 'unknown'
        }
        self.resolution_log.append(resolution_entry)
        
        # Cache result
        self.template_cache[template_name] = canonical_name
        
        logger.info(f"Template resolved: {template_name} → {canonical_name} ({'✓' if template_exists else '✗'})")
        
        return canonical_name
    
    def render(self, request: Request, template_name: str, context: Dict[str, Any] = None) -> HTMLResponse:
        """Render template with canonical resolution"""
        
        if context is None:
            context = {}
        
        # Always include request in context
        context['request'] = request
        
        # Resolve to canonical template
        canonical_template = self.resolve_template(template_name)
        
        try:
            # Use Jinja environment directly for better control
            template = self.jinja_env.get_template(canonical_template)
            rendered_content = template.render(context)
            
            return HTMLResponse(content=rendered_content)
            
        except Exception as e:
            logger.error(f"Template rendering failed for {canonical_template}: {e}")
            
            # Fallback to base template with error message
            try:
                base_template = self.jinja_env.get_template("base.html")
                error_context = {
                    'request': request,
                    'page_title': 'Template Error',
                    'error_message': f"Template {canonical_template} rendering failed: {str(e)}"
                }
                
                # Simple error content block
                error_content = f"""
                <div class="container mx-auto px-4 py-8">
                    <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                        <h1 class="text-xl font-bold mb-2">Template Error</h1>
                        <p>Failed to render {canonical_template}</p>
                        <p class="text-sm mt-2">Error: {str(e)}</p>
                    </div>
                </div>
                """
                
                error_context['content'] = error_content
                rendered_content = base_template.render(error_context)
                
                return HTMLResponse(content=rendered_content, status_code=500)
                
            except Exception as fallback_error:
                # Ultimate fallback - plain HTML
                logger.error(f"Base template fallback failed: {fallback_error}")
                
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Sofia V2 - Template Error</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <script src="https://cdn.tailwindcss.com"></script>
                </head>
                <body class="bg-gray-100">
                    <div class="container mx-auto px-4 py-8">
                        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                            <h1 class="text-xl font-bold">Sofia V2 - Template System Error</h1>
                            <p>Template: {canonical_template}</p>
                            <p>Original: {template_name}</p>
                            <p>Error: {str(e)}</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                
                return HTMLResponse(content=html_content, status_code=500)
    
    def get_resolution_report(self) -> Dict[str, Any]:
        """Get template resolution report"""
        
        # Count successful resolutions
        successful = sum(1 for entry in self.resolution_log if entry['exists'])
        total = len(self.resolution_log)
        
        # Group by canonical name
        canonical_usage = {}
        for entry in self.resolution_log:
            canonical = entry['canonical']
            if canonical not in canonical_usage:
                canonical_usage[canonical] = {
                    'usage_count': 0,
                    'requested_names': set(),
                    'exists': entry['exists']
                }
            canonical_usage[canonical]['usage_count'] += 1
            canonical_usage[canonical]['requested_names'].add(entry['requested'])
        
        return {
            'total_resolutions': total,
            'successful_resolutions': successful,
            'success_rate': successful / total if total > 0 else 0,
            'canonical_usage': {k: {
                'usage_count': v['usage_count'],
                'requested_names': list(v['requested_names']),
                'exists': v['exists']
            } for k, v in canonical_usage.items()},
            'resolution_log': self.resolution_log,
            'canonical_map_size': len(CANON_MAP),
            'search_paths': self.existing_paths
        }


# Global template resolver instance
template_resolver = TemplateResolver()


def render(request: Request, template_name: str, context: Dict[str, Any] = None) -> HTMLResponse:
    """Global render helper function"""
    return template_resolver.render(request, template_name, context)


def get_templates_instance():
    """Get templates instance for compatibility"""
    return template_resolver.templates


def get_resolution_report():
    """Get template resolution report"""
    return template_resolver.get_resolution_report()