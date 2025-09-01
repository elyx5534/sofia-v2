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

# Development shortcuts
d: dev
t: test
c: clean
u: docker-up
dn: docker-down
api: run-api
ui: run-ui