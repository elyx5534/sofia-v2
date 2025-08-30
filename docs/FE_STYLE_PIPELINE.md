# Sofia V2 - Frontend Style Pipeline

## Overview

Sofia V2 uses a **static CSS lock-in** approach to eliminate white screens and ensure consistent styling delivery across all deployment environments.

## Why Static CSS Lock-in?

### Problems with CDN-only Approach
- **White screens** during CDN failures or slow connections
- **FOUC (Flash of Unstyled Content)** on initial load
- **Network dependency** for core styling
- **Inconsistent rendering** across different environments

### Benefits of Static CSS
- ✅ **Guaranteed delivery** - CSS bundled with application
- ✅ **Zero white screens** - Styles available immediately
- ✅ **Offline resilience** - No external dependencies for core UI
- ✅ **Performance** - Reduced network requests and faster loading
- ✅ **Consistent rendering** - Same styles in dev/staging/production

## Dual-Mode Development

### Production Mode (Server-Render)
```html
<!-- base.html -->
<link rel="stylesheet" href="{{ url_for('static', path='styles/app.css') }}">
```

**Characteristics:**
- Uses compiled `static/styles/app.css`
- All Jinja templates render with static styles
- CDN fallback only if static CSS fails to load
- Purple brand theme with dark mode default

### Development Mode (Optional Vite)
```bash
# For developers who prefer Vite workflow
npm run dev:css  # Watch mode for CSS compilation
```

**Characteristics:**
- Jinja templates still use `app.css` (not Vite-dependent)
- Optional Vite dev server for component development
- CSS compilation with watch mode for development
- Maintains compatibility with server-render production

## Build Pipeline

### CSS Compilation
```json
{
  "scripts": {
    "build:css": "npx tailwindcss -c tailwind.config.js -i static/styles/index.css -o static/styles/app.css --minify",
    "dev:css": "npx tailwindcss -c tailwind.config.js -i static/styles/index.css -o static/styles/app.css --watch"
  }
}
```

### CSS Import Order
```css
/* static/styles/index.css */
@import "./tokens.css";     /* Design tokens first */
@tailwind base;
@tailwind components; 
@tailwind utilities;
@import "./base.css";       /* Custom components last */
```

### Tailwind Configuration
```js
// tailwind.config.js
module.exports = {
  content: [
    "./templates/**/*.html",
    "../src/**/*.{ts,tsx,js,jsx,html}",
    "../**/*.jinja",
    "./**/*.py"
  ],
  safelist: [
    // Purple brand colors always included
    'bg-brand-50', 'bg-brand-100', ..., 'bg-brand-900',
    'text-brand-50', 'text-brand-100', ..., 'text-brand-900',
    'hover:bg-brand-500', 'hover:bg-brand-600', 'hover:bg-brand-700'
  ]
}
```

## Purple Brand Theme (Mor Tema)

### Color Palette
```css
:root {
  --brand-50: #faf5ff;   /* Very light purple */
  --brand-100: #f3e8ff;
  --brand-200: #e9d5ff;
  --brand-300: #d8b4fe;
  --brand-400: #c084fc;
  --brand-500: #a855f7;  /* Primary purple */
  --brand-600: #9333ea;  /* Primary dark */
  --brand-700: #7c3aed;  /* Accent */
  --brand-800: #6b21a8;
  --brand-900: #581c87;  /* Deep purple */
}
```

### Dark Mode (Default)
```css
.dark {
  --surface: #0f0b1a;         /* Deep purple-black */
  --surface-card: #1a1426;    /* Purple-gray cards */
  --surface-border: #2d1b45;  /* Purple borders */
}
```

### Usage Examples
```html
<!-- Primary buttons -->
<button class="bg-brand-600 hover:bg-brand-700 text-white">
  Trading Action
</button>

<!-- Cards with purple theme -->
<div class="bg-surface-card border border-surface-border">
  Content with purple theming
</div>

<!-- Brand accents -->
<i class="text-brand-400"></i>
<span class="text-brand-300">Purple text</span>
```

## Template System

### Canonical Template Names
```
/trade/manual → trade_manual.html
/trade/ai → trade_ai.html
/dashboard → dashboard.html
/markets → markets.html
/settings → settings.html
/live → live.html
/showcase/{symbol} → showcase.html
```

### Legacy Name Resolution
```python
CANON_MAP = {
    'manual_trading.html': 'trade_manual.html',
    'ai_trading.html': 'trade_ai.html',
    'dashboard_ultimate.html': 'dashboard.html',
    # ... automatic resolution
}
```

### Template Structure
```html
<!-- All templates extend base.html -->
{% extends "base.html" %}

{% block title %}Page Title - Sofia V2{% endblock %}

{% block content %}
  <!-- Page content in AppShell container -->
{% endblock %}

{% block extra_scripts %}
  <!-- Page-specific JavaScript -->
{% endblock %}
```

## AppShell Architecture

### Structure
```html
<html class="dark h-full">
<body class="app-shell">
  <nav class="app-navbar">
    <!-- Single top navigation only -->
  </nav>
  <main class="app-main">
    <div class="app-container py-6">
      <!-- Page content -->
    </div>
  </main>
</body>
</html>
```

### Sidebar Prevention
```css
/* Guaranteed sidebar elimination */
[class*="sidebar"], 
[id*="sidebar"],
.sidebar,
#sidebar,
[class*="drawer"],
[class*="side-panel"] {
  display: none !important;
}
```

## CI/CD Integration

### Build Step
```yaml
# .github/workflows/ui-build.yml
- name: Build CSS
  run: |
    cd sofia_ui
    npm install
    npm run build:css
    
- name: Upload CSS Artifact
  uses: actions/upload-artifact@v3
  with:
    name: compiled-css
    path: sofia_ui/static/styles/app.css
```

### Visual Regression Gates
```typescript
// tests/visual/baseline.spec.ts
await expect(page).toHaveScreenshot('dashboard-baseline.png', {
  fullPage: true,
  threshold: 0.01  // 1% difference threshold
});
```

### Quality Gates
- **Visual Diff**: ≤1% change from baseline
- **Console Errors**: = 0 critical errors
- **Accessibility**: Axe-core critical violations = 0
- **HTTP Status**: No 4xx/5xx errors during normal operation
- **CSS Validation**: Purple theme colors render correctly

## Development Workflow

### Setup
```bash
# Install dependencies
cd sofia_ui
npm install

# Build CSS
npm run build:css

# Watch mode for development
npm run dev:css
```

### Theme Validation
```bash
# Check purple brand colors render correctly
curl http://localhost:8005/trade/manual | grep "brand-600"

# Verify CSS compute-style
# .app-navbar background should be rgb(124,58,237) = brand-600
```

### Testing
```bash
# Visual regression tests
cd sofia_ui
npm test

# Full UI validation
python scripts/validate_template_lock.py
```

## Production Deployment

### Static File Serving
```python
# FastAPI static files
app.mount("/static", StaticFiles(directory="static"), name="static")
```

### CSS Delivery
1. **Primary**: Static `app.css` served from `/static/styles/`
2. **Fallback**: CDN Tailwind if static CSS fails
3. **Cache**: Browser caching with proper headers
4. **Compression**: Minified CSS for optimal size

### Monitoring
- CSS load success rate
- White screen incidents (should be 0)
- Theme consistency across browsers
- Performance metrics (FCP, LCP)

## Troubleshooting

### Common Issues

**White screens:**
- Check `/static/styles/app.css` exists and is accessible
- Verify static file mounting in FastAPI
- Check network connectivity for CDN fallback

**Purple theme not applying:**
- Verify `class="dark"` on html element
- Check CSS custom properties are defined
- Validate brand color utilities are compiled

**Template not found:**
- Check CANON_MAP in template resolver
- Verify template exists in search paths
- Check template resolution logs

### Debug Commands
```bash
# Check template resolution
curl http://localhost:8005/api/template-resolution

# Validate CSS compilation
ls -la sofia_ui/static/styles/app.css

# Test purple theme colors
curl http://localhost:8005/trade/manual | grep -o "brand-[0-9]*"
```

## License

This styling system is part of Sofia V2 proprietary trading platform.