"""Entry point for MCA XBRL Validation Engine & MCP Server."""

import sys
import argparse
import uvicorn
from app.api import app
from app.mcp_server import mcp


def run():
    parser = argparse.ArgumentParser(description="MCA XBRL Validation MCP & FastAPI Server")
    parser.add_argument("--mcp", action="store_true", help="Run MCP stdio server for Claude")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP Host for FastAPI (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP Port for FastAPI (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    if args.mcp:
        print("Starting MCA Validation FastMCP stdio server...", file=sys.stderr)
        mcp.run()
    else:
        print(f"Starting MCA Validation FastAPI server on http://{args.host}:{args.port}", file=sys.stderr)
        uvicorn.run("app.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    run()
