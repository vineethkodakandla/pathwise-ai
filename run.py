"""
PathWise AI — Offline Launcher
Run this script to start the entire platform locally.
No Docker, Redis, or TimescaleDB required.

Usage:
    python run.py
"""

import uvicorn

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PathWise AI — SD-WAN Management Platform")
    print("  Running in offline mode (no Docker required)")
    print("=" * 60)
    print("  API Server:    http://localhost:8000")
    print("  API Docs:      http://localhost:8000/docs")
    print("  WebSocket:     ws://localhost:8000/ws/scoreboard")
    print("  Frontend:      http://localhost:3000  (run separately)")
    print("=" * 60 + "\n")

    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
