#!/bin/bash

echo "=============================================="
echo "Sofia V2 Trading Platform - Starting..."
echo "=============================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "Virtual environment created."
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install/Update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet
echo "Dependencies installed."
echo ""

# Check if node_modules exists
if [ ! -d "sofia_ui/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd sofia_ui
    npm install
    cd ..
    echo "Frontend dependencies installed."
    echo ""
fi

# Start backend server in background
echo "Starting backend server..."
cd sofia_ui
python -m uvicorn server:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend in background
echo "Starting frontend..."
cd sofia_ui
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 3

echo ""
echo "=============================================="
echo "Sofia V2 is running!"
echo "=============================================="
echo ""
echo "Web UI:    http://localhost:3000"
echo "API Docs:  http://localhost:8000/docs"
echo "Health:    http://localhost:8000/health"
echo ""
echo "Opening web UI in browser..."

# Open browser (works on Mac and most Linux distros)
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:3000
fi

echo ""
echo "Press Ctrl+C to stop all servers..."

# Wait for Ctrl+C
trap "echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait