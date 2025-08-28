@echo off
echo Starting Sofia V2 Data Service...

REM Set default environment variables
if not defined SOFIA_WS_ENABLED set SOFIA_WS_ENABLED=true
if not defined SOFIA_WS_PING_SEC set SOFIA_WS_PING_SEC=20
if not defined SOFIA_WS_COMBINED set SOFIA_WS_COMBINED=true
if not defined SOFIA_PRICE_CACHE_TTL set SOFIA_PRICE_CACHE_TTL=10
if not defined SOFIA_REST_TIMEOUT_SEC set SOFIA_REST_TIMEOUT_SEC=5
if not defined SOFIA_SYMBOLS set SOFIA_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT

echo Environment Configuration:
echo   SOFIA_WS_ENABLED=%SOFIA_WS_ENABLED%
echo   SOFIA_WS_PING_SEC=%SOFIA_WS_PING_SEC%
echo   SOFIA_WS_COMBINED=%SOFIA_WS_COMBINED%
echo   SOFIA_PRICE_CACHE_TTL=%SOFIA_PRICE_CACHE_TTL%
echo   SOFIA_REST_TIMEOUT_SEC=%SOFIA_REST_TIMEOUT_SEC%
echo   SOFIA_SYMBOLS=%SOFIA_SYMBOLS%
echo.

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting API server on http://localhost:8001
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload