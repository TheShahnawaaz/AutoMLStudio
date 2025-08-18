#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
PORT=${PORT:-7002}
uvicorn runner.service:app --host 0.0.0.0 --port "$PORT" --reload


