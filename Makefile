VENV=.venv
UVICORN=$(VENV)/bin/uvicorn

.PHONY: setup setup-all dev-api dev-runner fmt lint

setup:
	./scripts/bootstrap_venv.sh

setup-all:
	./scripts/bootstrap_venv.sh --all

dev-api:
	PYTHONUNBUFFERED=1 $(UVICORN) orchestrator.app.main:app --host 0.0.0.0 --port 8000 --reload

dev-runner:
	./scripts/dev_runner.sh

# TODO: add ruff/black/mypy once configured
fmt:
	@echo "TODO: add formatters"

lint:
	@echo "TODO: add linters"


