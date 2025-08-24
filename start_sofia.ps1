# Sofia V2 - Enhanced Windows Startup Script
# Handles memory issues, path problems, and provides better error handling

param(
    [switch]$SkipFetch,
    [switch]$SkipNews,
    [switch]$OpenBrowser = $true,
    [string]$Port = "8000",
    [string]$Host = "127.0.0.1",
    [switch]$Debug,
    [switch]$UseAlternativeUI
)

# Set error handling
$ErrorActionPreference = "Continue"

Write-Host "🚀 Sofia V2 - Enhanced Startup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Function to check if a command exists
function Test-CommandExists {
    param($command)
    try {
        Get-Command $command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Function to safely run Python commands
function Invoke-PythonCommand {
    param($command, $description)
    
    Write-Host "🔄 $description..." -ForegroundColor Yellow
    
    try {
        $output = Invoke-Expression "python $command" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ $description completed" -ForegroundColor Green
            return $true
        } else {
            Write-Host "⚠️  $description completed with warnings" -ForegroundColor Yellow
            if ($Debug) {
                Write-Host "Output: $output" -ForegroundColor Gray
            }
            return $true
        }
    } catch {
        Write-Host "❌ $description failed: $_" -ForegroundColor Red
        if ($Debug) {
            Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Gray
        }
        return $false
    }
}

# Check Python installation
if (-not (Test-CommandExists "python")) {
    Write-Host "❌ Python not found. Please install Python 3.11+ and add to PATH." -ForegroundColor Red
    Write-Host "💡 Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    pause
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green

# Check and install Python dependencies
Write-Host "🔍 Checking Python dependencies..." -ForegroundColor Yellow

$requiredPackages = @(
    "fastapi", "uvicorn", "ccxt", "pandas", "pyarrow", 
    "polars", "httpx", "apscheduler", "loguru", "python-dotenv", "jinja2"
)

$missingPackages = @()
foreach ($package in $requiredPackages) {
    try {
        python -c "import $package" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $missingPackages += $package
        }
    } catch {
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "📦 Installing missing Python packages: $($missingPackages -join ', ')" -ForegroundColor Yellow
    
    try {
        python -m pip install --upgrade pip
        python -m pip install $($missingPackages -join ' ')
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to install some Python packages" -ForegroundColor Red
            Write-Host "💡 Try running: pip install -r requirements.txt" -ForegroundColor Yellow
        } else {
            Write-Host "✅ Python dependencies installed" -ForegroundColor Green
        }
    } catch {
        Write-Host "❌ Error installing Python packages: $_" -ForegroundColor Red
    }
} else {
    Write-Host "✅ All Python dependencies are installed" -ForegroundColor Green
}

# Handle Node.js dependencies with better memory management
if (Test-CommandExists "node") {
    $nodeVersion = node --version 2>&1
    Write-Host "✅ Node.js found: $nodeVersion" -ForegroundColor Green
    
    # Set memory limits to prevent out of memory errors
    $env:NODE_OPTIONS = "--max_old_space_size=4096 --no-warnings"
    
    if (-not (Test-Path "node_modules/lightweight-charts")) {
        Write-Host "📦 Installing Node.js dependencies..." -ForegroundColor Yellow
        
        try {
            # Try npm install with memory optimization
            npm install --no-optional --prefer-offline --silent
            
            if ($LASTEXITCODE -ne 0) {
                Write-Host "⚠️  Standard npm install failed, trying lightweight approach..." -ForegroundColor Yellow
                
                # Fallback: install only essential package
                $env:NODE_OPTIONS = "--max_old_space_size=2048"
                npm install lightweight-charts --no-optional --silent
            }
            
            Write-Host "✅ Node.js dependencies handled" -ForegroundColor Green
        } catch {
            Write-Host "⚠️  Node.js dependency installation had issues: $_" -ForegroundColor Yellow
            Write-Host "💡 Charts may not work properly" -ForegroundColor Gray
        }
    } else {
        Write-Host "✅ Node.js dependencies OK" -ForegroundColor Green
    }
    
    # Copy charts library if available
    $chartsSource = "node_modules/lightweight-charts/dist/lightweight-charts.standalone.production.js"
    $chartsTarget = "static/js/lightweight-charts.standalone.production.js"
    
    if (Test-Path $chartsSource) {
        if (-not (Test-Path "static/js")) {
            New-Item -ItemType Directory -Path "static/js" -Force | Out-Null
        }
        Copy-Item $chartsSource $chartsTarget -Force
        Write-Host "✅ Chart library copied" -ForegroundColor Green
    }
} else {
    Write-Host "⚠️  Node.js not found - charts will use fallback mode" -ForegroundColor Yellow
}

# Create necessary directories
$directories = @("outputs", "outputs/news", "data", "data/ohlcv", "static/js", "static/css")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "📁 Created: $dir" -ForegroundColor Blue
    }
}

Write-Host ""
Write-Host "🚀 Starting Sofia V2..." -ForegroundColor Cyan

# Step 1: Initial data fetch
if (-not $SkipFetch) {
    $success = Invoke-PythonCommand "sofia_cli.py fetch-all --days 30 --max-workers 3" "Initial data fetch"
    if (-not $success) {
        Write-Host "⚠️  Continuing without initial data..." -ForegroundColor Yellow
    }
} else {
    Write-Host "⏭️  Skipping data fetch" -ForegroundColor Blue
}

# Step 2: Signal scan
$success = Invoke-PythonCommand "sofia_cli.py scan" "Signal scanning"

# Step 3: News update
if (-not $SkipNews) {
    $success = Invoke-PythonCommand "sofia_cli.py news --symbol-limit 5" "News update"
} else {
    Write-Host "⏭️  Skipping news update" -ForegroundColor Blue
}

Write-Host ""
Write-Host "🌐 Starting web server..." -ForegroundColor Yellow
Write-Host "   📍 URL: http://$Host`:$Port" -ForegroundColor Cyan
Write-Host "   📚 API: http://$Host`:$Port/docs" -ForegroundColor Cyan
Write-Host "   🔧 Debug mode: $Debug" -ForegroundColor Gray

# Open browser
if ($OpenBrowser) {
    Start-Job -ScriptBlock {
        param($url)
        Start-Sleep -Seconds 3
        try {
            Start-Process $url
        } catch {
            # Ignore browser opening errors
        }
    } -ArgumentList "http://$Host`:$Port" | Out-Null
    Write-Host "🌐 Browser will open automatically..." -ForegroundColor Blue
}

Write-Host ""
Write-Host "✅ Sofia V2 is ready!" -ForegroundColor Green
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host "=================================================" -ForegroundColor Cyan

# Start web server with proper error handling
try {
    if ($UseAlternativeUI) {
        Write-Host "🔄 Using alternative UI (sofia_ui)..." -ForegroundColor Yellow
        python -m uvicorn sofia_ui.server:app --host $Host --port $Port --reload
    } else {
        python sofia_cli.py web --host $Host --port $Port $(if ($Debug) { "--verbose" })
    }
} catch {
    Write-Host ""
    Write-Host "❌ Web server error: $_" -ForegroundColor Red
    Write-Host "💡 Try running with -UseAlternativeUI flag" -ForegroundColor Yellow
    pause
    exit 1
} finally {
    Write-Host ""
    Write-Host "⏹️  Sofia V2 stopped" -ForegroundColor Yellow
}


