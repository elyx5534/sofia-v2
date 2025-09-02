@echo off
REM Sofia V2 Trading System Commands for Windows

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="qa-proof" goto qa-proof
if "%1"=="consistency" goto consistency
if "%1"=="shadow" goto shadow
if "%1"=="arbitrage" goto arbitrage
if "%1"=="readiness" goto readiness
if "%1"=="demo" goto demo
if "%1"=="api" goto api
if "%1"=="clean" goto clean

:help
echo Sofia V2 Trading System Commands
echo ================================
echo make qa-proof      - Run consistency check + 5 min shadow comparison
echo make consistency   - Check P&L consistency across sources
echo make shadow        - Run 5 minute shadow mode comparison
echo make arbitrage     - Run 30 minute Turkish arbitrage session
echo make readiness     - Check live pilot readiness (GO/NO-GO)
echo make demo          - Run 5 minute paper trading demo
echo make api           - Start API server on port 8001
echo make clean         - Clean log files and caches
goto end

:qa-proof
echo Running QA Proof Suite...
python tools\consistency_check.py
echo.
echo Starting 5-minute shadow comparison...
python -c "import asyncio; from src.trading.shadow_mode import shadow_mode; asyncio.run(shadow_mode.run_comparison_session(5))"
goto end

:consistency
python tools\consistency_check.py
goto end

:shadow
python -c "import asyncio; from src.trading.shadow_mode import shadow_mode; asyncio.run(shadow_mode.run_comparison_session(5))"
goto end

:arbitrage
python tools\run_tr_arbitrage_session.py 30
goto end

:readiness
python tools\live_readiness.py
goto end

:demo
python run_paper_demo.py
goto end

:api
python -m uvicorn src.api.main_simple:app --port 8001
goto end

:clean
echo Cleaning log files...
del /Q logs\*.log 2>nul
del /Q logs\*.jsonl 2>nul
echo Log files cleaned
goto end

:end