#!/usr/bin/env python
"""
Start the admin backend service
"""

import os
import sys
import traceback

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Set environment variable
os.environ.setdefault('PYTHONPATH', PROJECT_ROOT)

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as e:
        print("❌ Error: Unable to import uvicorn")
        print(f"   Please install: pip install uvicorn")
        print(f"   Details: {e}")
        sys.exit(1)

    try:
        from admin.api import app
    except Exception as e:
        print("❌ Error: Unable to import admin.api")
        print(f"   Details: {e}")
        traceback.print_exc()
        sys.exit(1)

    print("=" * 70)
    print("🚀 Starting Polymarket trading admin")
    print("=" * 70)
    print(f"📍 URL: http://127.0.0.1:8888")
    print(f"🔒 Only localhost access allowed")
    print(f"⚠️  Note: user authentication is currently disabled")
    print("=" * 70)
    print()

    try:
        # Listen only on localhost
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8888,
            log_level="info"
        )
    except Exception as e:
        print(f"❌ Failed to start service: {e}")
        traceback.print_exc()
        sys.exit(1)
