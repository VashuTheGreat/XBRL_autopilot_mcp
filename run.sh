#!/usr/bin/env bash
set -e

# Default port
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "=========================================================="
echo "   MCA XBRL Validation MCP & FastAPI Server"
echo "   Taxonomies: Ind-AS 2017 & C&I 2016 (AOC-4 XBRL)"
echo "=========================================================="

if [ "$1" == "--mcp" ]; then
    echo "Starting FastMCP stdio server for Claude..."
    exec python3 -m app.main --mcp
else
    echo "Starting FastAPI Server on http://${HOST}:${PORT}"
    echo "Interactive Web Dashboard: http://${HOST}:${PORT}/"
    echo "Swagger Documentation:    http://${HOST}:${PORT}/docs"
    exec python3 -m app.main --host "${HOST}" --port "${PORT}" --reload
fi
