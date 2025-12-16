#!/bin/bash
# Restart take-profit/stop-loss monitor script

# Get project root (scripts/python -> scripts -> project_root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_ROOT"

echo "🔄 Restarting take-profit/stop-loss monitor..."
echo "   Project directory: $PROJECT_ROOT"
echo ""

# Stop old process
echo "⏹ Stopping old process..."
pkill -f "start_monitor.py" 2>/dev/null
sleep 2

# Activate virtual environment
source .venv/bin/activate
export PYTHONPATH="$PROJECT_ROOT"

# Ensure the logs directory exists
mkdir -p logs

# Clear old logs
> logs/monitor.log

# Start new monitor
echo "🚀 Starting monitor..."
nohup python -u scripts/python/start_monitor.py > logs/monitor.log 2>&1 &
NEW_PID=$!

echo ""
echo "✅ Monitor started! PID: $NEW_PID"
echo "   Press Ctrl+C to stop viewing logs (monitor will keep running in the background)"
echo ""
echo "========================================"

# Stream logs
tail -f logs/monitor.log
