AutoML Chat Studio
===================

Monorepo scaffold for a chat-driven AutoML system. MVP focus: upload CSV + prompt → EDA → cleaning → encoding → feature selection → modeling → tuning → evaluation → downloadable pipeline, with streamed logs and code for every step.

Directory layout
----------------

```
automl-chat/
  frontend/           # Next.js app (chat UI, uploads, SSE stream)
  orchestrator/       # FastAPI app (sessions, planning, streaming)
  runner/             # Jailed Python step executor (CodeSandbox-ready)
  schemas/            # Shared Pydantic/TS types
  prompts/            # LLM system + planner prompts
  infra/              # docker-compose and env templates
  scripts/            # developer tooling scripts
  docs/               # API/docs/runbooks
```

Quick start (local, orchestrator only)
-------------------------------------

1. Create a virtualenv and install orchestrator deps:
   - `python3 -m venv .venv && source .venv/bin/activate`
   - `pip install -r orchestrator/requirements.txt`
2. Run the API (with auto-reload):
   - `./scripts/dev_orchestrator.sh`
3. Visit `http://localhost:8000/docs` for the OpenAPI UI.

Notes & TODOs
-------------

- TODO: Add Postgres + object storage wiring (Supabase in prod; SQLite for local).
- TODO: Implement planner loop and queue.
- TODO: Implement SSE event streaming from real step execution.
- TODO: Scaffold `frontend` with Next.js and connect to SSE.
- TODO: Add CI and linting (ruff/black/mypy, eslint/tsc).


