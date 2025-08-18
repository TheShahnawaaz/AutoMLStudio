#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "[setup] Creating virtualenv at $VENV_DIR"
  python3.11 -m venv "$VENV_DIR" || python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -U pip

echo "[setup] Installing orchestrator requirements"
"$VENV_DIR/bin/pip" install -r "$ROOT_DIR/orchestrator/requirements.txt"

if [[ ${1:-} == "--all" ]]; then
  echo "[setup] Installing runner requirements (heavy ML stack)"
  "$VENV_DIR/bin/pip" install -r "$ROOT_DIR/runner/requirements.txt"
fi

echo "[setup] Done. Activate with: source .venv/bin/activate"


