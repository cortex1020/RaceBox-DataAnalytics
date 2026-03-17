#!/usr/bin/env python3
"""
RaceBox — run.py
Single entry point: starts the FastAPI server.
The web dashboard is served at http://localhost:8000
The API docs are at http://localhost:8000/docs

Usage:
    python run.py                     # default: port 8000
    python run.py --port 8080
    python run.py --reload            # dev mode with hot reload
"""
import sys
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="RaceBox F1 Intelligence Platform")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload (dev)")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════╗
║         R A C E B O X   v1.0                 ║
║   F1 Race Intelligence Platform              ║
╠══════════════════════════════════════════════╣
║  Dashboard  →  http://localhost:{port}        ║
║  API docs   →  http://localhost:{port}/docs   ║
╚══════════════════════════════════════════════╝
    """.format(port=args.port))

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
