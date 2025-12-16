#!/usr/bin/env python
"""Start take-profit/stop-loss monitoring."""

import sys
import os

# Real-time output
sys.stdout.reconfigure(line_buffering=True)

# Ensure the logs directory exists
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

from scripts.python.position_monitor import PositionManager, show_config

if __name__ == "__main__":
    show_config()

    pm = PositionManager()
    pm.display_positions()

    if pm.positions:
        print('🔄 Starting monitor...')
        print('   Check every 5 seconds')
        print('   Press Ctrl+C to stop')
        print()
        pm.monitor_loop()
    else:
        print('⚠️ No positions; monitoring not needed')
