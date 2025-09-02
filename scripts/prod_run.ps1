# Production Run Script - Sofia V2
# Starts API, Paper Trading, Arbitrage Radar, and opens dashboards

param(
    [switch]$NoPaper = $false,
    [switch]$NoArb = $false,
    [switch]$NoUI = $false,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       Sofia V2 Production Runner       ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

# Create necessary directories
$directories = @("logs", ".cache", "backtests", "reports", "state")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Host "✓ Created directory: $dir" -ForegroundColor Green
    }
}

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "✓ Activating virtual environment..." -ForegroundColor Green
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "✗ Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
    & .\.venv\Scripts\Activate.ps1
    Write-Host "Installing requirements..." -ForegroundColor Yellow
    pip install --upgrade pip
    pip install -r requirements.txt
}

# Health check function
function Test-APIHealth {
    param([int]$MaxRetries = 10)
    
    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 2
            if ($response.status -eq "healthy") {
                return $true
            }
        } catch {
            Write-Host "  Waiting for API to start... ($i/$MaxRetries)" -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

# Kill existing processes on the port
Write-Host "`n🔍 Checking for existing processes..." -ForegroundColor Cyan
$existingProcess = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existingProcess) {
    $pid = $existingProcess.OwningProcess
    Write-Host "  Killing existing process on port $Port (PID: $pid)" -ForegroundColor Yellow
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Start API server
Write-Host "`n🚀 Starting API server on port $Port..." -ForegroundColor Cyan
$apiProcess = Start-Process powershell -PassThru -WindowStyle Minimized -ArgumentList @(
    '-NoProfile',
    '-Command',
    "& .\.venv\Scripts\python -m uvicorn src.api.main:app --host 127.0.0.1 --port $Port --reload"
)

# Wait for API to be healthy
Write-Host "  Waiting for API health check..." -ForegroundColor Yellow
if (Test-APIHealth) {
    Write-Host "✓ API is healthy!" -ForegroundColor Green
    
    # Get API stats
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:$Port/health"
        Write-Host "  Memory: $([math]::Round($health.memory_mb, 2)) MB" -ForegroundColor Cyan
        Write-Host "  CPU: $([math]::Round($health.cpu_percent, 2))%" -ForegroundColor Cyan
    } catch {}
} else {
    Write-Host "✗ API failed to start!" -ForegroundColor Red
    Stop-Process -Id $apiProcess.Id -Force
    exit 1
}

# Start Paper Trading (if not disabled)
if (-not $NoPaper) {
    Write-Host "`n📊 Starting Paper Trading..." -ForegroundColor Cyan
    try {
        $paperBody = @{
            session = "grid"
            symbol = "BTC/USDT"
            params = @{
                grid_spacing = 0.01
                grid_levels = 5
            }
        } | ConvertTo-Json
        
        $paperResponse = Invoke-RestMethod -Uri "http://localhost:$Port/api/paper/start" `
            -Method POST `
            -ContentType "application/json" `
            -Body $paperBody `
            -ErrorAction Stop
        
        if ($paperResponse.status -eq "started") {
            Write-Host "✓ Paper trading started: $($paperResponse.symbol)" -ForegroundColor Green
        } else {
            Write-Host "⚠ Paper trading may already be running" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠ Could not start paper trading: $_" -ForegroundColor Yellow
    }
}

# Start Arbitrage Radar (if not disabled)
if (-not $NoArb) {
    Write-Host "`n🎯 Starting Arbitrage Radar..." -ForegroundColor Cyan
    try {
        $arbBody = @{
            mode = "tl"
            pairs = @("BTC/USDT", "ETH/USDT", "SOL/USDT")
            threshold_bps = 50
        } | ConvertTo-Json
        
        $arbResponse = Invoke-RestMethod -Uri "http://localhost:$Port/api/arb/start" `
            -Method POST `
            -ContentType "application/json" `
            -Body $arbBody `
            -ErrorAction Stop
        
        if ($arbResponse.status -eq "started") {
            Write-Host "✓ Arbitrage radar started" -ForegroundColor Green
            Write-Host "  Pairs: $($arbResponse.pairs -join ', ')" -ForegroundColor Cyan
            Write-Host "  Threshold: $($arbResponse.threshold_bps) bps" -ForegroundColor Cyan
        } else {
            Write-Host "⚠ Arbitrage radar may already be running" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠ Could not start arbitrage radar: $_" -ForegroundColor Yellow
    }
}

# Open UI in browser (if not disabled)
if (-not $NoUI) {
    Write-Host "`n🌐 Opening UI in browser..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    
    # Open dashboard
    Start-Process "http://localhost:$Port/dashboard"
    Write-Host "✓ Dashboard opened" -ForegroundColor Green
    
    # Open backtest studio
    Start-Process "http://localhost:$Port/backtest-studio"
    Write-Host "✓ Backtest Studio opened" -ForegroundColor Green
}

# Display status
Write-Host "`n╔════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║     Sofia V2 is running in PRODUCTION  ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📍 API URL:        http://localhost:$Port" -ForegroundColor Cyan
Write-Host "📊 Dashboard:      http://localhost:$Port/dashboard" -ForegroundColor Cyan
Write-Host "🔬 Backtest Studio: http://localhost:$Port/backtest-studio" -ForegroundColor Cyan
Write-Host "❤️  Health:        http://localhost:$Port/health" -ForegroundColor Cyan
Write-Host "📈 Metrics:        http://localhost:$Port/metrics" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Monitor loop
$running = $true
$lastCheck = Get-Date

# Set up Ctrl+C handler
[Console]::TreatControlCAsInput = $false
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -SupportEvent -Action {
    $script:running = $false
}

try {
    while ($running) {
        # Check API health every 30 seconds
        if ((Get-Date) - $lastCheck -gt [TimeSpan]::FromSeconds(30)) {
            try {
                $health = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 2
                $metrics = Invoke-RestMethod -Uri "http://localhost:$Port/metrics" -TimeoutSec 2
                
                # Parse metrics
                $uptimeMatch = [regex]::Match($metrics, 'sofia_uptime_seconds (\d+\.\d+)')
                $memoryMatch = [regex]::Match($metrics, 'sofia_memory_mb (\d+\.\d+)')
                
                if ($uptimeMatch.Success) {
                    $uptime = [TimeSpan]::FromSeconds([double]$uptimeMatch.Groups[1].Value)
                    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Uptime: $($uptime.ToString('hh\:mm\:ss')) | Memory: $([math]::Round([double]$memoryMatch.Groups[1].Value, 2)) MB" -ForegroundColor Gray
                }
            } catch {
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ⚠ Health check failed" -ForegroundColor Yellow
            }
            $lastCheck = Get-Date
        }
        
        Start-Sleep -Seconds 5
        
        # Check if API process is still running
        if ($apiProcess.HasExited) {
            Write-Host "`n✗ API process has stopped unexpectedly!" -ForegroundColor Red
            $running = $false
        }
    }
} finally {
    Write-Host "`n🛑 Shutting down Sofia V2..." -ForegroundColor Yellow
    
    # Stop paper trading
    try {
        Invoke-RestMethod -Uri "http://localhost:$Port/api/paper/stop" -Method POST -TimeoutSec 2 | Out-Null
        Write-Host "✓ Paper trading stopped" -ForegroundColor Green
    } catch {}
    
    # Stop arbitrage radar
    try {
        Invoke-RestMethod -Uri "http://localhost:$Port/api/arb/stop" -Method POST -TimeoutSec 2 | Out-Null
        Write-Host "✓ Arbitrage radar stopped" -ForegroundColor Green
    } catch {}
    
    # Stop API process
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force
        Write-Host "✓ API server stopped" -ForegroundColor Green
    }
    
    Write-Host "`n👋 Sofia V2 shutdown complete" -ForegroundColor Cyan
}