# Sofia V2 Architecture

## Overview
Sofia V2 is a comprehensive quantitative trading platform with a layered architecture designed for modularity, testability, and performance.

## Core Principles
- **Single Source of Truth**: One DataHub for all market data
- **Unidirectional Dependencies**: api → services → adapters
- **Mock-First Testing**: All external calls are mockable
- **Clear Separation**: Business logic in services, external adapters isolated

## System Components

### API Layer (`src/api/`)
- FastAPI application serving REST endpoints
- WebSocket support for real-time updates
- Pydantic models for request/response validation
- Authentication via JWT tokens

### Services Layer (`src/services/`)
- **DataHub**: Unified market data provider with fallback chain
- **Symbols**: Canonical asset representation and mapping
- **Backtester**: Historical strategy testing engine
- **Execution**: Order management and execution
- **Paper Engine**: Simulated trading environment

### Domain Layer (`src/domain/`)
- Core business models and entities
- Enums and constants
- Custom exceptions
- Value objects

### Adapters Layer (`src/adapters/`)
- External service integrations
- Exchange connectors (Binance, Coinbase, etc.)
- Data provider adapters (yfinance, Stooq)
- Database adapters

### UI Layer (`src/ui/`)
- Jinja2 templates for server-side rendering
- Static assets (JavaScript, CSS)
- Real-time dashboard components

## Data Flow

```
User Request → API Router → Service → Adapter → External System
                   ↓            ↓         ↓
                Response ← Domain Model ← Raw Data
```

## Quick Verify

Test the architecture layers:
```powershell
# Check import direction (should only go one way)
python -c "import ast; import os; [print(f'{root}/{f}') for root, _, files in os.walk('src/api') for f in files if f.endswith('.py') and 'from src.services' not in open(f'{root}/{f}').read()]"

# Verify DataHub is singleton
python -c "from src.services.datahub import DataHub; h1 = DataHub(); h2 = DataHub(); print('OK' if id(h1) == id(h2) else 'FAIL')"

# Test layer isolation
python -m pytest tests/test_architecture.py -q
```
