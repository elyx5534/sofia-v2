@echo off
echo ========================================
echo Starting Sofia V2 Trading Platform
echo ========================================
echo.

REM Set environment variables
set SOFIA_WS_ENABLED=true
set SOFIA_WS_PING_SEC=20
set SOFIA_WS_COMBINED=true
set SOFIA_PRICE_CACHE_TTL=10
set SOFIA_REST_TIMEOUT_SEC=5
set SOFIA_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT

echo Configuration:
echo   WebSocket: ENABLED
echo   Ping Interval: %SOFIA_WS_PING_SEC%s
echo   Cache TTL: %SOFIA_PRICE_CACHE_TTL%s
echo   Symbols: %SOFIA_SYMBOLS%
echo.

echo Installing/Updating dependencies...
pip install -q fastapi uvicorn websockets httpx pytest pytest-asyncio ta

echo.
echo Starting services...
echo.

REM Start data service in background
echo [1/2] Starting Data Service (port 8001)...
start /B cmd /c "uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --log-level warning"

REM Wait for data service to start
timeout /t 3 /nobreak > nul

REM Start UI service
echo [2/2] Starting UI Service (port 8000)...
echo.
echo ========================================
echo Sofia V2 is running!
echo.
echo UI Dashboard: http://localhost:8000
echo Data API: http://localhost:8001
echo Metrics: http://localhost:8001/metrics
echo Debug: http://localhost:8001/data/debug
echo ========================================
echo.

uvicorn sofia_ui.server_updated:app --host 0.0.0.0 --port 8000 --reload