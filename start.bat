@echo off
echo ==============================================
echo Sofia V2 Trading Platform - Starting...
echo ==============================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    py -m venv .venv
    echo Virtual environment created.
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate

REM Install/Update dependencies
echo Installing dependencies...
python -m pip install -r requirements.txt --quiet
echo Dependencies installed.
echo.

REM Check if node_modules exists
if not exist "sofia_ui\node_modules" (
    echo Installing frontend dependencies...
    cd sofia_ui
    npm install
    cd ..
    echo Frontend dependencies installed.
    echo.
)

REM Start backend server
echo Starting backend server...
start cmd /k "cd sofia_ui && python -m uvicorn server:app --reload --port 8000"

REM Wait a bit for backend to start
timeout /t 3 /nobreak > nul

REM Start frontend
echo Starting frontend...
start cmd /k "cd sofia_ui && npm run dev"

REM Wait a bit for frontend to start
timeout /t 3 /nobreak > nul

echo.
echo ==============================================
echo Sofia V2 is running!
echo ==============================================
echo.
echo Web UI:    http://localhost:3000
echo API Docs:  http://localhost:8000/docs
echo Health:    http://localhost:8000/health
echo.
echo Press any key to open the web UI in your browser...
pause > nul

REM Open browser
start http://localhost:3000

echo.
echo To stop the servers, close the command windows.
pause