# AutoML Chat Studio — MVP TODOs

Status: scaffold created. Git repo to be initialized without committing yet.

Decisions
---------
- Storage: Supabase (bucket: TODO choose name; region: TODO).
- Streaming: SSE for MVP.
- Caps: dataset ≤ 100 MB; total run ≤ 15 min.
- Auth/Quotas: defer; TODO add rate limiting before public demo.
- OpenAI model/budget: defer; TODO add env-config placeholders.

Backlog (MVP)
-------------
- [ ] Orchestrator: replace in-memory state with Postgres; sessions table; simple run table.
- [ ] SSE: stream planner/runner events; heartbeat every 1s (already stubbed).
- [ ] Uploads: Supabase presigned URL endpoint; server-side validation of file type/size.
- [ ] Runner: add time/memory caps; artifact writing helpers; upload to storage.
- [ ] Planner: system prompt templates; step validation; fallback fixed pipeline path.
- [ ] Frontend: Next.js scaffold; upload page; chat pane; SSE event consumption; artifact gallery.
- [ ] Testing: unit (AST guards), integration (toy datasets), E2E (upload→download).
- [ ] CI: lint/typecheck (ruff/black/mypy, eslint/tsc); basic test workflow.
- [ ] Observability: structured JSON logs with session_id, step, duration_ms.
- [ ] Security: PII column-name heuristics; target leakage guard; downsampling prompts.

Operational TODOs
-----------------
- [ ] Provision Supabase project, bucket, service role key; store in `.env`.
- [ ] Add `.env.example` with placeholders (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE, OPENAI_API_KEY).
- [ ] Document local dev with docker-compose and makefile.


