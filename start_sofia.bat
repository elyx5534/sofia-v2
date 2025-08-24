@echo off
REM Sofia V2 - Simple Windows Batch Startup
REM Avoids PowerShell execution policy issues

echo.
echo ========================================
echo   Sofia V2 - Global Crypto Scanner
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

echo Python found: 
python --version

REM Set environment variables to avoid memory issues
set NODE_OPTIONS=--max_old_space_size=4096
set PYTHONIOENCODING=utf-8

REM Create directories
if not exist "outputs" mkdir outputs
if not exist "outputs\news" mkdir outputs\news
if not exist "data" mkdir data
if not exist "data\ohlcv" mkdir data\ohlcv
if not exist "static\js" mkdir static\js

echo.
echo Installing/checking dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet fastapi uvicorn[standard] ccxt pandas pyarrow polars httpx apscheduler loguru python-dotenv jinja2

REM Check for Node.js and install charts if available
where node >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Node.js found, checking chart library...
    if not exist "node_modules\lightweight-charts" (
        echo Installing lightweight-charts...
        npm install --silent --no-optional lightweight-charts
    )
    
    REM Copy chart library
    if exist "node_modules\lightweight-charts\dist\lightweight-charts.standalone.production.js" (
        copy "node_modules\lightweight-charts\dist\lightweight-charts.standalone.production.js" "static\js\" >nul 2>&1
        echo Chart library ready
    )
) else (
    echo Node.js not found - charts will use fallback mode
)

echo.
echo Starting Sofia V2...
echo.
echo Web interface will be available at: http://127.0.0.1:8000
echo API documentation: http://127.0.0.1:8000/docs
echo.
echo Press Ctrl+C to stop
echo ========================================

REM Start the web server
python sofia_cli.py web --host 127.0.0.1 --port 8000

echo.
echo Sofia V2 stopped
pause


