#!/bin/bash
# Sofia V2 Development Script for Linux/Unix
# One-shot script to run the complete development environment

set -e  # Exit on error

# Default parameters
SYMBOLS="${1:-BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT}"
MODE="${2:-paper}"

echo -e "\033[36mStarting Sofia V2 Development Environment\033[0m"
echo -e "\033[33mMode: $MODE\033[0m"
echo -e "\033[33mSymbols: $SYMBOLS\033[0m"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to root directory
cd "$ROOT_DIR"

# Step 1: Check Docker
echo -e "\n\033[32m[1/6] Checking infrastructure...\033[0m"
if ! docker ps | grep -q "sofia_"; then
    echo -e "\033[33mStarting infrastructure...\033[0m"
    docker compose -f infra/docker-compose.yml up -d
    sleep 5
else
    echo -e "\033[32mInfrastructure already running\033[0m"
fi

# Step 2: Setup Python environment
echo -e "\n\033[32m[2/6] Setting up Python environment...\033[0m"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies if needed
pip install -q -r requirements.txt

# Export environment variables
export SYMBOLS="$SYMBOLS"
export MODE="$MODE"
export NATS_URL="nats://localhost:4222"
export REDIS_URL="redis://localhost:6379"
export CLICKHOUSE_URL="http://localhost:8123"

# Step 3: Start DataHub
echo -e "\n\033[32m[3/6] Starting DataHub (market data ingestion)...\033[0m"
python -m sofia_datahub --symbols "$SYMBOLS" --tf 1m &
DATAHUB_PID=$!
echo "DataHub PID: $DATAHUB_PID"
sleep 3

# Step 4: Start Paper Trading Engine
echo -e "\n\033[32m[4/6] Starting Paper Trading Engine...\033[0m"
python -m sofia_backtest.paper &
PAPER_PID=$!
echo "Paper Trading PID: $PAPER_PID"
sleep 2

# Step 5: Apply portfolio configuration
echo -e "\n\033[32m[5/6] Applying paper portfolio configuration...\033[0m"
python -m sofia_cli portfolio apply --file configs/portfolio/paper_default.yaml

# Step 6: Start Web UI
echo -e "\n\033[32m[6/6] Starting Web UI server...\033[0m"
python -m sofia_ui.server_v2 &
UI_PID=$!
echo "Web UI PID: $UI_PID"
sleep 3

# Optional: Run sample backtest
echo -e "\n\033[35m[Bonus] Running sample backtest on BTCUSDT...\033[0m"
python -m sofia_cli backtest --symbol BTCUSDT --strategy trend --fast 20 --slow 60 &

# Display status
echo -e "\n\033[36m============================================================\033[0m"
echo -e "\033[32mSofia V2 Development Environment Started!\033[0m"
echo -e "\033[36m============================================================\033[0m"

echo -e "\n\033[33mServices running:\033[0m"
echo -e "  • DataHub: Processing market data from Binance WebSocket"
echo -e "  • Paper Trading: Executing strategies on paper portfolio"
echo -e "  • Web UI: http://localhost:8000"
echo -e "  • Grafana: http://localhost:3000 (admin/sofia2024)"
echo -e "  • ClickHouse: http://localhost:8123"

echo -e "\n\033[33mUseful commands:\033[0m"
echo -e "  • Check logs: docker logs sofia_clickhouse"
echo -e "  • Query ticks: curl 'http://localhost:8123/?query=SELECT count() FROM sofia.market_ticks'"
echo -e "  • Redis state: redis-cli GET paper:state"
echo -e "  • Stop all: kill $DATAHUB_PID $PAPER_PID $UI_PID"

echo -e "\n\033[33mOpening dashboard in browser...\033[0m"
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8000
elif command -v open > /dev/null; then
    open http://localhost:8000
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n\033[33mStopping services...\033[0m"
    kill $DATAHUB_PID $PAPER_PID $UI_PID 2>/dev/null || true
    echo -e "\033[32mServices stopped\033[0m"
}

# Register cleanup function
trap cleanup EXIT

# Wait for services
echo -e "\n\033[33mPress Ctrl+C to stop all services\033[0m"
wait