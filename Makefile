.PHONY: help install dev test clean docker-up docker-down run-api run-ui run-all lint format

# Default target
help:
	@echo "Sofia V2 Trading Platform - Available Commands:"
	@echo "================================================"
	@echo "  make install      - Install Python dependencies"
	@echo "  make dev          - Start development environment"
	@echo "  make test         - Run all tests"
	@echo "  make test-cov     - Run tests with coverage"
	@echo "  make clean        - Clean cache and temp files"
	@echo "  make docker-up    - Start Docker services"
	@echo "  make docker-down  - Stop Docker services"
	@echo "  make run-api      - Run API server"
	@echo "  make run-ui       - Run UI dashboard"
	@echo "  make run-all      - Run all services"
	@echo "  make lint         - Run code linting"
	@echo "  make format       - Format code with black"

# Install dependencies
install:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

# Development environment
dev:
	@echo "Starting development environment..."
	docker-compose -f infra/docker-compose.yml up -d
	@echo "Waiting for services to start..."
	sleep 10
	python run_sofia_v2.py

# Testing
test:
	python -m pytest tests/ -v

test-cov:
	python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

test-unit:
	python -m pytest tests/ -v -m "not integration"

test-integration:
	python -m pytest tests/ -v -m integration

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	@echo "Cleanup complete!"

# Docker operations
docker-up:
	docker-compose -f infra/docker-compose.yml up -d
	@echo "Docker services started!"
	@echo "ClickHouse: http://localhost:8123"
	@echo "Grafana: http://localhost:3000 (admin/sofia2024)"
	@echo "NATS: http://localhost:8222"

docker-down:
	docker-compose -f infra/docker-compose.yml down
	@echo "Docker services stopped!"

docker-logs:
	docker-compose -f infra/docker-compose.yml logs -f

docker-reset:
	docker-compose -f infra/docker-compose.yml down -v
	docker-compose -f infra/docker-compose.yml up -d
	@echo "Docker services reset!"

# Run services
run-api:
	uvicorn src.data_hub.api:app --reload --port 8000

run-ui:
	python sofia_ultimate_dashboard.py

run-simple:
	python simple_server.py

run-all: docker-up
	@echo "Starting all services..."
	python run_sofia_v2.py &
	python sofia_ultimate_dashboard.py &
	@echo "All services started!"
	@echo "API: http://localhost:8000"
	@echo "Dashboard: http://localhost:8080"

# Code quality
lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/
	ruff check src/ tests/ --fix

security:
	bandit -r src/
	pip-audit

# Database operations
db-init:
	python scripts/init_db.py

db-migrate:
	python scripts/migrate_db.py

# Backtest operations
backtest:
	python -m src.backtester.engine --strategy=all --symbol=BTCUSDT

backtest-optimize:
	python -m src.optimizer.genetic_algorithm --strategy=grid --symbol=BTCUSDT

# Paper trading
paper-start:
	python -m sofia_backtest.paper

paper-stop:
	pkill -f "sofia_backtest.paper" || true

# Paper trading proof session (30 minutes)
proof-today:
	@echo "========================================="
	@echo "Starting 30-minute Paper Trading Session"
	@echo "Strategy: Grid Monster"
	@echo "Symbols: BTC/USDT, SOL/USDT"
	@echo "Mode: PAPER (Virtual Trading)"
	@echo "========================================="
	@python tools/run_paper_session.py
	@echo ""
	@echo "Session complete! Check:"
	@echo "  - logs/paper_audit.log for trade details"
	@echo "  - logs/paper_session_summary.json for P&L summary"

# Run smoke tests
test-smoke:
	python -m pytest tests/smoke -q

# Production
build:
	docker build -t sofia-v2:latest .

deploy:
	@echo "Deploying to production..."
	# Add your deployment commands here

# Advanced Features (AA-DD)
qa-proof:
	@echo "Running QA Proof: Consistency + Shadow Comparison"
	python tools/qa_proof.py

consistency:
	@echo "Checking P&L Consistency"
	python tools/consistency_check.py

shadow:
	@echo "Running Shadow Mode Comparison"
	python tools/shadow_comparison.py

arbitrage:
	@echo "Starting Turkish Arbitrage Session (30 min)"
	python tools/run_tr_arbitrage_session.py 30

readiness:
	@echo "Checking Live Pilot Readiness"
	python tools/live_readiness.py

demo:
	@echo "Running 5-minute Paper Trading Demo"
	python run_paper_session.py 5

# Daily Operations (EE-II)
daily-validate:
	@echo "Running Daily Session Orchestrator"
	python tools/session_orchestrator.py --grid-mins 60 --arb-mins 30

adapt:
	@echo "Applying Adaptive Parameter Tuning"
	python tools/apply_adaptive_params.py

pilot-plan:
	@echo "Generating 48-72 Hour Pilot Preparation Plan"
	python tools/pilot_plan.py

fx-test:
	@echo "Testing USDTRY FX Provider"
	python -c "from src.providers.fx import fx_provider; print(f'USDTRY: {fx_provider.get_usdtry()}')"

pricer-test:
	@echo "Testing Arbitrage Pricer"
	python -m pytest tests/test_arbitrage_pricer.py -v

# Campaign & Testing (JJ-NN)
campaign:
	@echo "Starting 3-day paper trading campaign"
	python tools/run_paper_campaign.py --days 3

grid-sweep:
	@echo "Running grid parameter sweep"
	python tools/grid_sweeper.py

shadow-report:
	@echo "Generating shadow vs paper report"
	python tools/shadow_report.py

live-guard:
	@echo "Checking live trading guard status"
	python -c "from src.core.live_switch import live_switch; import json; print(json.dumps(live_switch.get_guard_status(), indent=2))"

fault-test:
	@echo "Running kill-switch fault injection tests"
	python tools/fault_injector.py

# 24-Hour Quick Campaign (FINAL-1)
quick-campaign:
	@echo "========================================="
	@echo "Starting 24-Hour Quick Campaign"
	@echo "3 sessions of Grid + TR Arbitrage"
	@echo "========================================="
	python tools/run_quick_campaign.py

# Strict Readiness Check (FINAL-2)
readiness-v2:
	@echo "========================================="
	@echo "Live Readiness Check V2 - STRICT 3/3"
	@echo "========================================="
	python tools/live_readiness_v2.py

# Live Pilot Control (FINAL-3 & FINAL-4)
live-on:
	@echo "========================================="
	@echo "Enabling Micro Live Pilot"
	@echo "TR Arbitrage Only - 250 TL cap"
	@echo "========================================="
	python tools/live_toggle.py --enable

live-off:
	@echo "========================================="
	@echo "Disabling Live Trading"
	@echo "========================================="
	python tools/live_toggle.py --disable

pilot-status:
	@echo "========================================="
	@echo "Live Pilot Status"
	@echo "========================================="
	python tools/pilot_status.py

pilot-off:
	@echo "========================================="
	@echo "EMERGENCY PILOT SHUTDOWN"
	@echo "========================================="
	python tools/pilot_off.py

# Local UI Development (NEW)
up:
	@python scripts/dev_up.py

down:
	@python scripts/dev_down.py

logs:
	@tail -n 100 -f logs/dev/api.out.log logs/dev/dash.out.log

# Development shortcuts
d: dev
t: test
c: clean
u: docker-up
dn: docker-down
api: run-api
ui: run-ui