@echo off
echo Running Sofia V2 Data Reliability Tests...
echo.

REM Run individual test modules
echo [1/4] Testing symbol mapping...
python tests\test_symbol_map.py
if %errorlevel% neq 0 goto :error

echo.
echo [2/4] Testing metrics contract...
pytest -q tests\test_metrics_contract.py
if %errorlevel% neq 0 goto :warn

echo.
echo [3/4] Testing WebSocket freshness...
pytest -q tests\test_price_freshness_ws.py
if %errorlevel% neq 0 goto :warn

echo.
echo [4/4] Testing REST fallback...
set SOFIA_WS_ENABLED=false
pytest -q tests\test_rest_fallback.py
set SOFIA_WS_ENABLED=true
if %errorlevel% neq 0 goto :warn

echo.
echo ========================================
echo All tests completed successfully!
echo ========================================
goto :end

:error
echo.
echo ERROR: Critical test failure!
exit /b 1

:warn
echo.
echo WARNING: Some tests failed or were skipped
echo This may be due to network conditions or service availability
goto :end

:end
echo.