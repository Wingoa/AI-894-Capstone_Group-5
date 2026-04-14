#!/usr/bin/env bash
set -e

# Minimal dev launcher - starts API and UI in background with basic env vars.

#######################################
# Usage:
#######################################

#### Start API (8002) and UI (8080) in background
#  1. chmod +x start-dev.sh
#  2. ./start-dev.sh

#### Stop API and UI
#  1. ./start-dev.sh stop  

API_PORT=8002
UI_PORT=8080

export PYTHONPATH=.
export EXECUTION_SERVICE_URL="http://127.0.0.1:${API_PORT}"
export PREDICTION_SERVICE_URL="http://127.0.0.1:${API_PORT}"

mkdir -p logs

if [ "${1:-}" = "stop" ]; then
  [ -f .api.pid ] && kill "$(cat .api.pid)" 2>/dev/null || true
  [ -f .ui.pid ] && kill "$(cat .ui.pid)" 2>/dev/null || true
  rm -f .api.pid .ui.pid
  echo "Stopped services."
  exit 0
fi

echo "Starting API on http://127.0.0.1:${API_PORT} (logs: logs/api.log)"
uvicorn data.app_render:app --reload --port ${API_PORT} >> logs/api.log 2>&1 &
echo $! > .api.pid

echo "Starting UI on http://127.0.0.1:${UI_PORT} (logs: logs/ui.log)"
uvicorn app:app --reload --port ${UI_PORT} >> logs/ui.log 2>&1 &
echo $! > .ui.pid

echo "Started. To stop: ./start-dev.sh stop"
