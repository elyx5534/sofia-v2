# Sofia V2 Development Script for Windows PowerShell
# One-shot script to run the complete development environment

param(
    [string]$Symbols = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT",
    [string]$Mode = "paper"
)

Write-Host "Starting Sofia V2 Development Environment" -ForegroundColor Cyan
Write-Host "Mode: $Mode" -ForegroundColor Yellow
Write-Host "Symbols: $Symbols" -ForegroundColor Yellow

# Set strict mode
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir

# Change to root directory
Set-Location $rootDir

# Step 1: Bootstrap infrastructure if not running
Write-Host "`n[1/6] Checking infrastructure..." -ForegroundColor Green
$dockerRunning = docker ps --format "table {{.Names}}" 2>$null | Select-String "sofia_"
if (-not $dockerRunning) {
    Write-Host "Starting infrastructure with bootstrap script..." -ForegroundColor Yellow
    & "$scriptDir\sofia_bootstrap.ps1"
    Start-Sleep -Seconds 5
} else {
    Write-Host "Infrastructure already running" -ForegroundColor Green
}

# Step 2: Activate virtual environment
Write-Host "`n[2/6] Activating virtual environment..." -ForegroundColor Green
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    & ".\.venv\Scripts\Activate.ps1"
    pip install -r requirements.txt
}

# Step 3: Start DataHub in background
Write-Host "`n[3/6] Starting DataHub (market data ingestion)..." -ForegroundColor Green
$env:SYMBOLS = $Symbols
$env:MODE = $Mode
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$rootDir'
    .\.venv\Scripts\Activate
    Write-Host 'Starting DataHub...' -ForegroundColor Cyan
    python -m sofia_datahub --symbols $Symbols --tf 1m
" -WindowStyle Normal

Start-Sleep -Seconds 3

# Step 4: Start Paper Trading Engine
Write-Host "`n[4/6] Starting Paper Trading Engine..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$rootDir'
    .\.venv\Scripts\Activate
    Write-Host 'Starting Paper Trading Engine...' -ForegroundColor Cyan
    python -m sofia_backtest.paper
" -WindowStyle Normal

Start-Sleep -Seconds 2

# Step 5: Apply portfolio configuration
Write-Host "`n[5/6] Applying paper portfolio configuration..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$rootDir'
    .\.venv\Scripts\Activate
    Write-Host 'Applying portfolio configuration...' -ForegroundColor Cyan
    python -m sofia_cli portfolio apply --file configs/portfolio/paper_default.yaml
    Write-Host 'Portfolio configured successfully' -ForegroundColor Green
" -WindowStyle Normal

# Step 6: Start Web UI
Write-Host "`n[6/6] Starting Web UI server..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$rootDir'
    .\.venv\Scripts\Activate
    Write-Host 'Starting Web UI on http://localhost:8000' -ForegroundColor Cyan
    python -m sofia_ui.server_v2
" -WindowStyle Normal

Start-Sleep -Seconds 3

# Optional: Run a sample backtest
Write-Host "`n[Bonus] Running sample backtest on BTCUSDT..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$rootDir'
    .\.venv\Scripts\Activate
    Write-Host 'Running trend strategy backtest...' -ForegroundColor Cyan
    python -m sofia_cli backtest --symbol BTCUSDT --strategy trend --fast 20 --slow 60
" -WindowStyle Normal

# Display status
Write-Host "`n" -NoNewline
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Sofia V2 Development Environment Started!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

Write-Host "`nServices running:" -ForegroundColor Yellow
Write-Host "  • DataHub: Processing market data from Binance WebSocket" -ForegroundColor White
Write-Host "  • Paper Trading: Executing strategies on paper portfolio" -ForegroundColor White
Write-Host "  • Web UI: http://localhost:8000" -ForegroundColor White
Write-Host "  • Grafana: http://localhost:3000 (admin/sofia2024)" -ForegroundColor White
Write-Host "  • ClickHouse: http://localhost:8123" -ForegroundColor White

Write-Host "`nUseful commands:" -ForegroundColor Yellow
Write-Host "  • Check logs: docker logs sofia_clickhouse" -ForegroundColor Gray
Write-Host "  • Query ticks: curl 'http://localhost:8123/?query=SELECT count() FROM sofia.market_ticks'" -ForegroundColor Gray
Write-Host "  • Redis state: redis-cli GET paper:state" -ForegroundColor Gray
Write-Host "  • Stop all: docker compose -f infra/docker-compose.yml down" -ForegroundColor Gray

Write-Host "`nPress Ctrl+C in each window to stop services" -ForegroundColor Yellow
Write-Host ""

# Open browser
Write-Host "Opening dashboard in browser..." -ForegroundColor Cyan
Start-Process "http://localhost:8000"