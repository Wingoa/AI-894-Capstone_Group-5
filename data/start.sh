#!/usr/bin/env bash
set -euo pipefail
# Launch API from the data directory with correct PYTHONPATH
cd "$(dirname "$0")"
export PYTHONPATH=.:../data_model/src
PORT=${PORT:-8002}
exec gunicorn -k uvicorn.workers.UvicornWorker app_render:app \
  --workers 1 --threads 2 --bind 0.0.0.0:${PORT}
