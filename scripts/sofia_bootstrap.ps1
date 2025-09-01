# Sofia V2 Infrastructure Bootstrap Script
# PowerShell script to setup and initialize the entire trading infrastructure

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy Bypass -Scope Process -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Color output functions
function Write-Info { Write-Host $args[0] -ForegroundColor Cyan }
function Write-Success { Write-Host $args[0] -ForegroundColor Green }
function Write-Warning { Write-Host $args[0] -ForegroundColor Yellow }
function Write-Error { Write-Host $args[0] -ForegroundColor Red }

# Paths
$root = (Resolve-Path ".").Path
Write-Info "Working directory: $root"

# Create necessary directories
$directories = @("infra", "scripts", "config", "reports", "logs", "data")
foreach ($dir in $directories) {
    if (!(Test-Path "$root\$dir")) {
        New-Item -ItemType Directory "$root\$dir" | Out-Null
        Write-Info "Created directory: $dir"
    }
}

# Check Docker
Write-Info "Checking Docker installation..."
try {
    docker --version | Out-Null
    Write-Success "Docker is installed"
} catch {
    Write-Error "Docker is not installed or not in PATH"
    exit 1
}

# Check Docker Compose
try {
    docker compose version | Out-Null
    Write-Success "Docker Compose is installed"
} catch {
    Write-Error "Docker Compose is not installed"
    exit 1
}

# Create crypto symbols configuration
$symbolsFile = "$root\config\symbols.crypto.top20.usdt"
if (!(Test-Path $symbolsFile)) {
    @"
BTCUSDT
ETHUSDT
BNBUSDT
SOLUSDT
XRPUSDT
ADAUSDT
DOGEUSDT
TONUSDT
TRXUSDT
LINKUSDT
AVAXUSDT
SUIUSDT
PEPEUSDT
NEARUSDT
ARBUSDT
OPUSDT
APTUSDT
ATOMUSDT
MATICUSDT
LTCUSDT
"@ | Out-File $symbolsFile -Encoding utf8
    Write-Success "Created symbols configuration"
}

# Create strategy configuration
$strategyFile = "$root\config\strategy.paper.toml"
if (!(Test-Path $strategyFile)) {
    @"
# Sofia V2 Paper Trading Strategy Configuration

[gridlite]
step_bps = 45         # 0.45% grid step
levels = 5            # number of grid levels
qty_usd = 20          # USD amount per level
max_position = 100    # max position per symbol in USD

[trendfilter]
ema_period = 200      # EMA period for trend detection
risk_pair_pct = 1.0   # max risk per pair
total_risk_pct = 10.0 # total portfolio risk
fee_bps = 10          # trading fee in basis points
slippage_bps = 3      # slippage in basis points

[risk]
max_drawdown_pct = 15.0    # maximum drawdown percentage
position_sizing = "kelly"   # position sizing method
leverage = 1.0              # no leverage for spot trading
stop_loss_pct = 2.0         # stop loss percentage
take_profit_pct = 5.0       # take profit percentage

[monitoring]
health_check_interval = 60  # seconds
metrics_interval = 300      # seconds
alert_webhook = ""          # webhook for alerts
"@ | Out-File $strategyFile -Encoding utf8
    Write-Success "Created strategy configuration"
}

# Read symbols for environment
$symbols = Get-Content $symbolsFile | Where-Object { $_ -ne "" } | ForEach-Object { $_ } -join ","

# Create environment files
$envPaper = "$root\.env.paper"
@"
# Sofia V2 Paper Trading Environment
MODE=paper
EXCHANGE=binance
SYMBOLS=$symbols

# Infrastructure URLs
NATS_URL=nats://localhost:4222
REDIS_URL=redis://localhost:6379
CLICKHOUSE_URL=http://localhost:8123
CLICKHOUSE_USER=sofia
CLICKHOUSE_PASSWORD=sofia2024
CLICKHOUSE_DB=sofia
GRAFANA_URL=http://localhost:3000

# Trading Configuration
STRATEGY_CONFIG=config/strategy.paper.toml
RISK_CHECK_ENABLED=true
MAX_POSITION_USD=100
PAPER_BALANCE_USD=10000

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
HEALTH_CHECK_PORT=8080
"@ | Out-File $envPaper -Encoding utf8
Write-Success "Created .env.paper"

$envLive = "$root\.env.live"
if (!(Test-Path $envLive)) {
    @"
# Sofia V2 Live Trading Environment (DRY RUN)
MODE=live
EXCHANGE=binance
SYMBOLS=$symbols

# Infrastructure URLs (same as paper)
NATS_URL=nats://localhost:4222
REDIS_URL=redis://localhost:6379
CLICKHOUSE_URL=http://localhost:8123
CLICKHOUSE_USER=sofia
CLICKHOUSE_PASSWORD=sofia2024
CLICKHOUSE_DB=sofia
GRAFANA_URL=http://localhost:3000

# Exchange API (DO NOT COMMIT REAL KEYS)
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=false

# Live Trading Configuration
STRATEGY_CONFIG=config/strategy.live.toml
RISK_CHECK_ENABLED=true
MAX_POSITION_USD=50
LIVE_TRADING_ENABLED=false  # Safety switch
DRY_RUN=true               # Log only, no real orders

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
HEALTH_CHECK_PORT=8080
ALERT_WEBHOOK=
"@ | Out-File $envLive -Encoding utf8
    Write-Success "Created .env.live template"
}

# Start Docker services
Write-Info "Starting Docker services..."
Push-Location "$root\infra"
try {
    docker compose down 2>$null | Out-Null
    docker compose up -d
    Write-Success "Docker services started"
} catch {
    Write-Error "Failed to start Docker services: $_"
    Pop-Location
    exit 1
}
Pop-Location

# Wait for services to be ready
Write-Info "Waiting for services to be ready..."
$maxRetries = 30
$retryCount = 0

# Check ClickHouse
while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest "http://localhost:8123/ping" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Success "ClickHouse is ready"
            break
        }
    } catch {
        Write-Info "Waiting for ClickHouse... ($retryCount/$maxRetries)"
        Start-Sleep -Seconds 2
        $retryCount++
    }
}

# Initialize ClickHouse schema
Write-Info "Initializing ClickHouse schema..."
try {
    $sqlContent = Get-Content "$root\infra\ch_bootstrap.sql" -Raw
    $body = @{
        query = $sqlContent
        user = "sofia"
        password = "sofia2024"
    }
    $response = Invoke-WebRequest "http://localhost:8123/" -Method POST -Body ($body | ConvertTo-Json) -ContentType "application/json" -UseBasicParsing
    Write-Success "ClickHouse schema initialized"
} catch {
    Write-Warning "Failed to initialize ClickHouse schema (may already exist): $_"
}

# Check Redis
$retryCount = 0
while ($retryCount -lt $maxRetries) {
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect("localhost", 6379)
        $tcpClient.Close()
        Write-Success "Redis is ready"
        break
    } catch {
        Write-Info "Waiting for Redis... ($retryCount/$maxRetries)"
        Start-Sleep -Seconds 2
        $retryCount++
    }
}

# Check NATS
$retryCount = 0
while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest "http://localhost:8222/varz" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Success "NATS is ready"
            break
        }
    } catch {
        Write-Info "Waiting for NATS... ($retryCount/$maxRetries)"
        Start-Sleep -Seconds 2
        $retryCount++
    }
}

# Check Grafana
$retryCount = 0
while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest "http://localhost:3000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Success "Grafana is ready"
            break
        }
    } catch {
        Write-Info "Waiting for Grafana... ($retryCount/$maxRetries)"
        Start-Sleep -Seconds 2
        $retryCount++
    }
}

# Create Python virtual environment if not exists
if (!(Test-Path "$root\.venv")) {
    Write-Info "Creating Python virtual environment..."
    python -m venv .venv
    Write-Success "Virtual environment created"
}

# Display status
Write-Success "`n=== Sofia V2 Infrastructure Bootstrap Complete ==="
Write-Info "Services running:"
Write-Info "  - ClickHouse: http://localhost:8123 (user: sofia, pass: sofia2024)"
Write-Info "  - NATS: nats://localhost:4222 (monitoring: http://localhost:8222)"
Write-Info "  - Redis: redis://localhost:6379"
Write-Info "  - Grafana: http://localhost:3000 (admin/sofia2024)"
Write-Info "`nNext steps:"
Write-Info "  1. Activate virtual environment: .\.venv\Scripts\Activate"
Write-Info "  2. Install dependencies: pip install -r requirements.txt"
Write-Info "  3. Start DataHub: python -m sofia_datahub"
Write-Info "  4. Start Paper Trading: python -m sofia_backtest.paper"
Write-Info "  5. Start UI: python -m sofia_ui"

# Create quick start script
$quickStart = "$root\scripts\quick_start.ps1"
@'
# Sofia V2 Quick Start
.\.venv\Scripts\Activate
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m sofia_datahub"
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m sofia_backtest.paper"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m sofia_ui"
Write-Host "All services started. Check individual windows for logs." -ForegroundColor Green
'@ | Out-File $quickStart -Encoding utf8
Write-Success "Created quick start script: scripts\quick_start.ps1"