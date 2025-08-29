# AutoML Chat Studio

AutoML Chat Studio is a monorepo for a chat‑driven AutoML platform.  Users upload a CSV dataset, describe their goal in natural language and receive a streamed log of the pipeline that profiles the data, cleans it and trains a baseline model.  All artifacts and code for each step are emitted along the way, enabling reproducible workflows.

## Features

- **FastAPI orchestrator** that manages sessions, uploads and Server‑Sent Event (SSE) streams
- **Sandbox runner** capable of executing Python code cells with a safe subset of libraries
- **Stub pipeline** with profiling, cleaning and baseline model training (classification or regression)
- **Next.js frontend** scaffold for chat UI and live log streaming
- **Shared schemas and prompts** for planning new pipeline steps via LLMs

## Repository layout

```
automl-studio/
├── frontend/        # Next.js app (chat UI, uploads, SSE stream)
├── orchestrator/    # FastAPI app (sessions, planning, streaming)
├── runner/          # Jailed Python step executor or service
├── schemas/         # Shared Pydantic/TypeScript types
├── prompts/         # LLM system & planner prompts
├── infra/           # docker-compose and env templates
├── scripts/         # developer tooling scripts
├── fixtures/        # example datasets
└── docs/            # API docs & runbooks
```

## Quick start

### Requirements

- Python 3.11+
- Node.js 18+ (for the frontend)
- Optional: Docker for containerised runs

### Bootstrap the virtual environment

```bash
make setup        # orchestrator deps only
# or
make setup-all    # include heavy ML runner deps
source .venv/bin/activate
```

### Run the orchestrator API

```bash
make dev-api      # or ./scripts/dev_orchestrator.sh
```
Open <http://localhost:8000/docs> for the interactive OpenAPI UI.

### Run the runner service (optional)

```bash
make dev-runner   # or ./scripts/dev_runner.sh
```

### Example workflow

1. `POST /sessions` to create a new session
2. `POST /sessions/{id}/upload` with a CSV file
3. `POST /sessions/{id}/start` with goal, target and dataset URI
4. `GET /sessions/{id}/stream` to receive SSE logs and artifacts

The default stub pipeline executes three steps:

| Step    | Description |
| ------- | ----------- |
| `profile` | Prints dataset shape, head and missing value ratios |
| `clean`   | Drops duplicates and imputes missing values, writing `df_clean.csv` |
| `train`   | Trains a baseline model (logistic regression or ridge) and emits `baseline_model.pkl` & `metrics.json` |

## Development notes

- `runner/runner.py` implements the sandbox with banned imports and safe builtins
- `prompts/planner_system.md` contains the system prompt used by the planner
- `infra/docker-compose.yml` provides a minimal container config for the orchestrator
- `fixtures/iris.csv` is an example dataset for quick testing

## Roadmap

- Planner loop & task queue
- SSE streaming from real execution environments
- Fully featured Next.js frontend
- CI, linting & formatting
- Persistent storage (Postgres, object storage)

