# Sofia V2 - Global Crypto Scanner
# PowerShell startup script for Windows

param(
    [switch]$SkipFetch,
    [switch]$SkipNews,
    [switch]$OpenBrowser = $true,
    [string]$Port = "8000",
    [string]$Host = "127.0.0.1"
)

Write-Host "🚀 Sofia V2 - Global Crypto Scanner" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Check if Python is available
try {
    $pythonVersion = python --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Python not found. Please install Python 3.11+ and add it to PATH." -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error checking Python: $_" -ForegroundColor Red
    exit 1
}

# Check if required packages are installed
Write-Host "🔍 Checking dependencies..." -ForegroundColor Yellow

try {
    python -c "import fastapi, uvicorn, ccxt, pandas, pyarrow" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Some dependencies are missing. Installing..." -ForegroundColor Red
        
        Write-Host "📦 Installing Python packages..." -ForegroundColor Yellow
        python -m pip install -U pip fastapi uvicorn[standard] ccxt pandas pyarrow polars httpx apscheduler loguru python-dotenv jinja2
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to install Python dependencies" -ForegroundColor Red
            exit 1
        }
    }
    Write-Host "✅ Python dependencies OK" -ForegroundColor Green
} catch {
    Write-Host "❌ Error checking dependencies: $_" -ForegroundColor Red
    exit 1
}

# Check if Node.js packages are available
if (Test-Path "node_modules/lightweight-charts") {
    Write-Host "✅ Node.js dependencies OK" -ForegroundColor Green
} else {
    Write-Host "📦 Installing Node.js packages..." -ForegroundColor Yellow
    
    # Set Node.js memory limit to avoid out of memory errors
    $env:NODE_OPTIONS = "--max_old_space_size=4096"
    
    npm install --no-optional --prefer-offline
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  npm install had issues, trying alternative approach..." -ForegroundColor Yellow
        
        # Try with reduced memory usage
        $env:NODE_OPTIONS = "--max_old_space_size=2048"
        npm install lightweight-charts --no-optional
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to install Node.js dependencies" -ForegroundColor Red
            Write-Host "💡 You can manually install: npm install lightweight-charts" -ForegroundColor Yellow
        }
    }
    
    # Copy lightweight-charts to static directory
    if (Test-Path "node_modules/lightweight-charts/dist/lightweight-charts.standalone.production.js") {
        # Ensure static/js directory exists
        if (!(Test-Path "static/js")) {
            New-Item -ItemType Directory -Path "static/js" -Force | Out-Null
        }
        Copy-Item "node_modules/lightweight-charts/dist/lightweight-charts.standalone.production.js" "static/js/" -Force
        Write-Host "✅ Copied lightweight-charts to static directory" -ForegroundColor Green
    } else {
        Write-Host "⚠️  lightweight-charts not found, web charts may not work" -ForegroundColor Yellow
    }
}

# Create output directories
$directories = @("outputs", "outputs/news", "data", "data/ohlcv")
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "📁 Created directory: $dir" -ForegroundColor Blue
    }
}

Write-Host ""
Write-Host "🔄 Starting Sofia V2 initialization..." -ForegroundColor Cyan

# Step 1: Fetch initial data (unless skipped)
if (!$SkipFetch) {
    Write-Host "📈 Step 1: Fetching initial market data..." -ForegroundColor Yellow
    Write-Host "   This may take a few minutes for the first run..." -ForegroundColor Gray
    
    python sofia_cli.py fetch-all --days 30 --max-workers 3
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  Data fetch completed with some errors, continuing..." -ForegroundColor Yellow
    } else {
        Write-Host "✅ Market data fetch completed" -ForegroundColor Green
    }
} else {
    Write-Host "⏭️  Skipping data fetch (--SkipFetch)" -ForegroundColor Blue
}

Write-Host ""

# Step 2: Run initial scan
Write-Host "🔍 Step 2: Running initial signal scan..." -ForegroundColor Yellow
python sofia_cli.py scan

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Signal scan completed with some errors, continuing..." -ForegroundColor Yellow
} else {
    Write-Host "✅ Signal scan completed" -ForegroundColor Green
}

Write-Host ""

# Step 3: Update news (unless skipped)
if (!$SkipNews) {
    Write-Host "📰 Step 3: Updating news feeds..." -ForegroundColor Yellow
    python sofia_cli.py news --symbol-limit 5
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  News update completed with some errors, continuing..." -ForegroundColor Yellow
    } else {
        Write-Host "✅ News update completed" -ForegroundColor Green
    }
} else {
    Write-Host "⏭️  Skipping news update (--SkipNews)" -ForegroundColor Blue
}

Write-Host ""
Write-Host "🌐 Step 4: Starting web server..." -ForegroundColor Yellow
Write-Host "   Server will be available at: http://$Host`:$Port" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C to stop the server" -ForegroundColor Gray

# Open browser after a short delay (in background)
if ($OpenBrowser) {
    Start-Job -ScriptBlock {
        param($url)
        Start-Sleep -Seconds 3
        Start-Process $url
    } -ArgumentList "http://$Host`:$Port" | Out-Null
    Write-Host "🌐 Browser will open automatically..." -ForegroundColor Blue
}

Write-Host ""
Write-Host "🚀 Sofia V2 is starting up!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan

# Start the web server
try {
    python sofia_cli.py web --host $Host --port $Port
} catch {
    Write-Host "❌ Web server error: $_" -ForegroundColor Red
    exit 1
} finally {
    Write-Host ""
    Write-Host "⏹️  Sofia V2 stopped" -ForegroundColor Yellow
}