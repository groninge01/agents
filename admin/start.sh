#!/bin/bash
# Start admin backend service (with error checks)

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "🚀 Starting Polymarket trading admin"
echo "========================================"
echo ""

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Error: virtual environment does not exist"
    echo "   Please create it first: python3 -m venv .venv"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check dependencies
echo "📦 Checking dependencies..."
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "❌ Error: uvicorn is not installed"
    echo "   Please install dependencies: pip install -r requirements.txt"
    exit 1
fi

if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ Error: fastapi is not installed"
    echo "   Please install dependencies: pip install -r requirements.txt"
    exit 1
fi

# Set environment variable
export PYTHONPATH="$PROJECT_ROOT"

# Check and kill processes occupying the port
PORT=8888
echo "🔍 Checking whether port $PORT is in use..."

# Method 1: use lsof to find processes occupying the port
if command -v lsof >/dev/null 2>&1; then
    PIDS=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "⚠️  Port $PORT is occupied by: $PIDS"
        echo "   Stopping these processes..."
        echo "$PIDS" | xargs kill -9 2>/dev/null
        sleep 1
    fi
fi

# Method 2: use fuser to find processes occupying the port (fallback)
if command -v fuser >/dev/null 2>&1; then
    if fuser $PORT/tcp >/dev/null 2>&1; then
        echo "⚠️  fuser detected port $PORT is in use"
        fuser -k $PORT/tcp 2>/dev/null
        sleep 1
    fi
fi

# Method 3: find and kill related admin processes
echo "🔍 Finding and stopping admin-related processes..."
pkill -f "admin/start.py" 2>/dev/null
pkill -f "admin.api" 2>/dev/null
pkill -f "uvicorn.*admin" 2>/dev/null

# Confirm port is released
sleep 1
if command -v lsof >/dev/null 2>&1; then
    if lsof -ti :$PORT >/dev/null 2>&1; then
        echo "❌ Warning: port $PORT is still in use; force killing..."
        lsof -ti :$PORT | xargs kill -9 2>/dev/null
        sleep 1
    else
        echo "✅ Port $PORT is released"
    fi
fi

echo ""
echo "📍 URL: http://127.0.0.1:8888"
echo "🔒 Only localhost access allowed"
echo "⚠️  Note: user authentication is currently disabled"
echo "========================================"
echo ""

# Start service
python admin/start.py
