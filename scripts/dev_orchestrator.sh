#!/usr/bin/env bash
set -euo pipefail

# Simple dev runner for the FastAPI orchestrator
export PYTHONUNBUFFERED=1
uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8000 --reload


