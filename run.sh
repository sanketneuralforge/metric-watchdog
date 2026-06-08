#!/bin/bash
# run.sh — Start Metric Watchdog locally

set -e

echo "🐕 Starting Metric Watchdog..."

# Kill existing processes
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :8501 | xargs kill -9 2>/dev/null || true
sleep 1

cd "$(dirname "$0")"

# Start FastAPI
echo "Starting API on :8000..."
uv run uvicorn api.main:app --port 8000 --reload &
API_PID=$!
echo "API PID: $API_PID"

sleep 2

# Start Streamlit
echo "Starting UI on :8501..."
uv run streamlit run ui/app.py --server.port 8501

kill $API_PID 2>/dev/null || true
echo "Stopped."