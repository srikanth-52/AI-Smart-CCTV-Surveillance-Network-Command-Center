#!/usr/bin/env python3
"""
AI Smart CCTV Surveillance & Network Command Center
Single-Click Launcher Script
"""

import uvicorn
import webbrowser
import time
import threading
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def open_browser():
    """Waits for server startup and opens the web dashboard in browser."""
    time.sleep(1.8)
    url = "http://127.0.0.1:8000"
    print(f"\n========================================================")
    print(f"🚀 AI CCTV SURVEILLANCE COMMAND CENTER IS RUNNING")
    print(f"🌐 Access Web Dashboard: {url}")
    print(f"📡 API Documentation:   {url}/docs")
    print(f"========================================================\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    print("Initializing AI Surveillance Ingestion Pipeline...")
    # Launch browser thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Uvicorn server
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )
