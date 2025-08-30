# Sofia V2 UI Templates Documentation

## Current Stable Template: **Sofia V2 Glass Dark**

### Template Information
- **File**: `homepage_glass_dark_stable.html`
- **Created**: 2025-08-30
- **Status**: ✅ STABLE - PRODUCTION READY
- **Description**: Modern dark theme with glass effects and premium UI elements

### Features
- 🌙 Dark theme optimized
- ✨ Glass blur effects (backdrop-filter)
- 💎 Premium gradient colors
- 🎯 Professional navigation
- 📱 Fully responsive design
- ⚡ High performance CSS

### Template Aliases
- `glass_dark` → `homepage_glass_dark_stable.html`
- `stable_ui` → `homepage_glass_dark_stable.html`

## Template Protection Rules

### 🚫 DO NOT MODIFY
- **`homepage_glass_dark_stable.html`** - This is our production template
- Always use this file as the golden standard
- Any changes should be tested in development templates first

### ✅ Safe to Modify
- `homepage.html` - Development/testing template
- `homepage_new.html` - Experimental features
- Any template ending with `_dev.html` or `_test.html`

## Usage

### Production (Default)
```python
# Server automatically uses stable template
@app.get("/")
async def homepage():
    return render("homepage_glass_dark_stable.html")
```

### Development Testing
```python
# For testing new features
@app.get("/dev")
async def dev_homepage():
    return render("homepage.html")
```

## Git Protection
The stable template is tracked in git and should be committed only after thorough testing.

## Template Backup Strategy
1. **Stable Version**: `homepage_glass_dark_stable.html` - Never modify
2. **Working Copy**: `homepage.html` - Use for development
3. **Backup Copy**: Automatically created before major changes

---
**Last Updated**: 2025-08-30  
**Maintainer**: Sofia V2 Development Team