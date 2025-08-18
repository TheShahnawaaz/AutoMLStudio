
# AutoML Chat Studio — Detailed Delivery Plan

## 1) Product goals & success metrics

* **Goal:** Chat-driven AutoML that converts a dataset + natural-language goal into a trained, downloadable pipeline, while showing every command and its output.
* **MVP Success:**

  * A user uploads CSV + prompt → sees EDA → cleaning → feature engineering → model selection → tuning → evaluation → **downloadable model**.
  * Typical run time ≤ **15 minutes** on medium datasets.
  * “Show your work”: each step displays the **code cell** and **stdout/stderr**.
  * ≥ 90% of runs complete without manual intervention on clean datasets.

## 2) System architecture (MVP)

```
[Browser UI]
  ├─ Chat UI + File Uploader
  ├─ Live Logs (WebSocket/SSE)
  └─ Artifacts Panel (plots, metrics, downloads)
       │
       ▼
[Orchestrator API (FastAPI)]
  ├─ Session & state (Postgres)
  ├─ LLM Planner (OpenAI)
  ├─ Step Queue (local thread/RQ)
  └─ WS/SSE stream to client
       │
       ▼
[Runner Sandbox (CodeSandbox VM)]
  ├─ Dev Container (Python + ML stack)
  ├─ Step Executor (per-step jailed exec)
  ├─ Allow-list & guards (no subprocess/network)
  └─ Writes artifacts to object storage
```

**Why CodeSandbox:** fast to spin up, free-tier hours for demos, accepts Dev Containers. We compensate for missing kernel flags with strict app-level guardrails.

## 3) Tech stack

* **Frontend:** Next.js (React), Tailwind or MUI, WebSocket/SSE for streaming logs, Upload via signed URLs.
* **Backend:** FastAPI (Python 3.11+), SQLAlchemy + Postgres (Neon/Supabase free tier), Redis (optional) or in-proc queue for MVP.
* **Runner:** CodeSandbox VM using **Dev Container** (Dockerfile + `devcontainer.json`). Python libs: `pandas`, `numpy`, `scikit-learn`, `xgboost`, `optuna`, `matplotlib`. (Optional: `scipy`, `shap` later.)
* **Storage:** Object storage (Supabase Storage / S3-compatible) for datasets & artifacts.
* **LLM:** One OpenAI model for planning/code-gen (abstract name in code; configurable).
* **Tracking:** JSON run logs to start; **MLflow** optional in Phase 2 (can run in the same sandbox or separate).

## 4) Security, privacy, guardrails

* **Runner isolation (app-level):**

  * Disable network access in code by **not exposing** any network libraries in globals; reject `import requests`, `urllib`, `subprocess`, `os.system`, `shutil`, `pathlib.Path().rmtree`, etc.
  * AST static analysis: **reject** code with `Import`, `Attribute` patterns that touch disallowed modules/attributes.
  * Exec locals: provide **only** allow-listed objects (pandas, numpy, sklearn, xgboost, optuna, matplotlib) and our `inputs`, `artifacts` dict; no `__builtins__.__import__`.
  * Hard **timeout** (e.g., 10–15 min) and **memory cap** in Python (resource module + chunked data loading).
* **PII checks:** Simple column-name heuristics (`email`, `phone`, `aadhaar`, etc.). Prompt user to mask before logging.
* **Quotas:** Per-user daily run limit; dataset size caps; “pause when nearing CodeSandbox free hours”.
* **Audit trail:** Every step JSON + code + stdout/stderr stored with session.

## 5) The chat loop (planner → runner)

### Step contract (strict JSON)

```json
{
  "intent": "profile | clean | encode | select_features | train | tune | evaluate | export",
  "needs": ["dataset_path", "target", "task_type"],
  "provides": ["df_clean", "pipeline.pkl", "metrics.json"],
  "python": "...short cell using only allowed libs...",
  "notes": "One-line summary to show the user"
}
```

### Runner execution harness (core logic)

* Parse JSON, validate keys.
* **Static-check** `python` with `ast`:

  * Ban `Import` of disallowed pkgs; ban `Attribute` access like `os.system`.
* Execute with:

  * Restricted `globals`: dict of **only** the allowed libs.
  * `locals`: `{ "inputs": {...}, "artifacts": {} }`.
* Capture `stdout/stderr`.
* Persist artifacts (e.g., save figures to `/workspace/artifacts/step_x.png` then upload to object storage).
* Return `{status, stdout, stderr, artifacts_manifest}`.

*(We’ll ship a ready-to-run `runner.py` with these behaviors.)*

## 6) Data pipeline catalog (what the LLM can do)

**Profile**

* Load CSV with `dtype` inference; limit to N rows for preview.
* Print `df.shape`, `head()`, NA %, target distribution, class imbalance hint.

**Clean**

* Drop duplicates; drop constant/near-constant columns.
* Impute numeric (median), categorical (mode).
* Rare category capping (min frequency threshold).
* Optional: outlier clipping by quantiles.

**Encode**

* Build `ColumnTransformer`:

  * Numeric → `StandardScaler`
  * Categorical → `OneHotEncoder(handle_unknown="ignore")`
  * Text → `TfidfVectorizer` or hashing for large vocab
* Combine with `Pipeline`.

**Feature selection**

* Collinearity filter (|ρ| > 0.95); mutual information top-k; optional mRMR (phase 2).

**Modeling**

* **Classification**: LogisticRegression, RandomForestClassifier, XGBClassifier, PassiveAggressiveClassifier.
* **Regression**: Ridge, RandomForestRegressor, XGBRegressor.
* Baselines first; pick primary metric (ROC-AUC/F1 or RMSE/MAE).

**Tuning**

* Optuna with pruners; 20–40 trials/model (budgeted).
* Stratified KFold/ KFold (cv=5) with early stopping for XGB.

**Evaluate**

* Holdout metrics + plots:

  * Clf: ROC, PR, confusion matrix
  * Reg: residuals, error hist
* Calibration (optional, phase 2).

**Export**

* Serialize pipeline (`joblib` or `pickle`).
* Emit `model_card.md` (data snapshot, metrics, caveats).
* Generate minimal FastAPI serving stub (downloadable zip).

## 7) Backend API & WS design

**REST endpoints**

* `POST /sessions` → create session (returns `session_id`)
* `POST /sessions/{id}/upload` → pre-signed URL; client uploads CSV; returns `dataset_uri`
* `POST /sessions/{id}/start` → body: `{ goal, target, dataset_uri }` (starts the loop)
* `POST /sessions/{id}/step/approve` (optional gate) → continue
* `GET /sessions/{id}/artifacts` → list artifacts (paths, signed URLs)

**Streaming**

* `GET /sessions/{id}/stream` (SSE) or `/ws/{id}` (WebSocket)

  * Server pushes **step\_started**, **stdout**, **stderr**, **artifact\_ready**, **step\_finished**, **run\_finished** events

**Internal to Runner**

* Runner opens outbound WS to Orchestrator: `POST /runner/claim` then `POST /runner/complete`.
* Orchestrator posts step JSON → Runner executes → returns results.

## 8) Frontend UX

**Pages & components**

* **Upload & prompt**: drag\&drop CSV, prompt text, target selector.
* **Chat pane**: assistant messages + user confirmations.
* **Command cards** (one per step): code cell (read-only), logs, time taken, artifacts thumbnails.
* **Artifacts drawer**: metrics table, plots, model download buttons.
* **Limits banner**: shows remaining CodeSandbox hours, per-run limits.

**Flow**

1. Upload → choose target → “Start”.
2. Profile results appear (head/shape/NA map).
3. Cleaning proposal → auto-approve (with toggle).
4. Encoding/selection → show column counts.
5. Baselines → tuner → evaluation → export.
6. Download pipeline + model card.

## 9) CodeSandbox runner specifics

**Dev Container**

* `.devcontainer/devcontainer.json` referencing a Dockerfile that installs Python 3.11 and ML deps.
* Pin wheels compatible with CodeSandbox’s base (manylinux; no GPU).

**Keep-alive & hibernation**

* The runner process keeps a light heartbeat (ping every 60s) while a job is in progress to avoid auto-hibernate.

**Persistence**

* Datasets uploaded to object storage; artifacts uploaded as soon as created; local sandbox disk is considered **ephemeral**.

## 10) Repository layout

```
/automl-chat
  /frontend           # Next.js app
  /orchestrator       # FastAPI app
  /runner             # CodeSandbox VM runner
  /schemas            # Pydantic/TS types for steps/events
  /prompts            # LLM system + planner prompt templates
  /infra              # docker-compose for local, env templates
  /scripts            # dev tooling
  /docs               # runbooks, ADRs
```

## 11) LLM prompting (planner)

**System prompt (excerpt)**

* “You are an AutoML Planner. Output **one step at a time** as strict JSON. Only use: pandas, numpy, scikit-learn, xgboost, optuna, matplotlib. No networking, no OS commands. Keep cells idempotent and ≤120 lines. Prefer robust defaults (median impute; StandardScaler; OHE). Always print concise progress. If target has ≤20 distinct values → classification; else regression.”

**Planner loop**

* Provide: dataset schema sample (first 40 rows), column type summary, target, prior step outputs (stdout truncated), artifact names available, time budget, size caps.
* Expect: step JSON per the contract.

**Cost control**

* Few-shot examples of good steps; temperature low; prune outputs.

## 12) Testing strategy

**Unit**

* AST guard tests (bad code gets blocked).
* Step executor happy path on toy datasets.
* Data handlers: CSV sniffing, type inference, NA handling.

**Integration**

* Full run on 3 fixtures:

  * Binary classification (imbalance)
  * Multi-class classification
  * Regression
* Verify artifacts, metrics, and that a pipeline can `predict` on holdout.

**E2E**

* Cypress/Playwright: upload, run, see logs, download model, run the downloaded FastAPI stub locally.

**Load**

* Parallel runs (2–5) on Nano to estimate contention.

## 13) Observability & ops

* Structured logs (JSON) with `session_id`, `step`, `duration_ms`.
* Metrics counters: runs started/completed, step fail rate, average duration, average dataset size.
* Error dashboards: step validation failures vs. runtime exceptions.

## 14) Risk register & mitigations

* **Sandbox bypass via clever code:** AST + allow-list + no `__import__` + no `builtins` exposure.
* **Runner hibernation mid-run:** keep-alive heartbeat; requeue step on disconnect.
* **Memory blowups:** chunked reading; sample for EDA; enforce caps; auto-downsample with user consent.
* **Poor LLM steps:** small fixed templates; “fallback fixed pipeline” path if planner stalls.
* **Model leakage:** pre-check date columns; block target in derived features; warn and drop suspicious columns.

## 15) Timeline (aggressive but doable)

*(Assuming start: **Aug 18, 2025**, IST)*

* **Week 1 (Aug 18–24):** Repo scaffold; schemas; runner harness; AST guard; local end-to-end (no LLM, fixed steps).
* **Week 2 (Aug 25–31):** CodeSandbox Dev Container; remote runner online; object storage wiring; upload → artifacts path working.
* **Week 3 (Sep 1–7):** LLM planner integration; profile/clean/encode steps; chat UI with streaming logs.
* **Week 4 (Sep 8–14):** Models + tuning + evaluation; downloads; basic quotas; error handling polish.
* **Week 5 (Sep 15–21):** Hardening (PII checks, downsampling), unit/integration/E2E tests; public demo readiness.

## 16) Deliverables & acceptance criteria

* **Working web app**: upload → chat steps → downloadable model.
* **Runner**: CodeSandbox VM with devcontainer; executor enforces allow-list; logs stream live.
* **Docs**: Runbook, API spec, Step JSON spec, security notes, “How to add a new step”.
* **Sample datasets**: 3 fixtures with canned successful runs.
* **Postmortems** template + incident response doc.

## 17) Example artifacts & outputs

* `best_pipeline.pkl` (sklearn Pipeline)
* `metrics.json` (primary + secondaries)
* `plots/roc.png`, `plots/residuals.png`
* `model_card.md` (auto-generated)
* `serve_stub.zip` (FastAPI endpoint with schema validation)

## 18) Migration plan (when you outgrow CodeSandbox)

* Lift runner to a small always-on VM (2–4 vCPU, 4–8 GB).
* Swap app-level guards for **Docker flags** (`--network=none`, `--cap-drop=ALL`, seccomp).
* Keep the same step protocol; only the executor changes.

---

## Appendix A — Minimal `runner.py` (skeleton)

```python
import ast, io, sys, json, time, traceback
import pandas as pd, numpy as np
from sklearn import model_selection, preprocessing, metrics, linear_model, ensemble
import xgboost as xgb
import optuna
import matplotlib
matplotlib.use("Agg")

ALLOWED = {
  "pd": pd, "np": np,
  "sklearn": __import__("sklearn"),
  "xgboost": xgb, "optuna": optuna,
  "model_selection": model_selection, "preprocessing": preprocessing,
  "metrics": metrics, "linear_model": linear_model, "ensemble": ensemble,
}

BANNED_IMPORTS = {"os","sys","subprocess","shutil","socket","requests","urllib","pathlib","importlib"}

def safe(code:str):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                if n.name.split('.')[0] in BANNED_IMPORTS: raise ValueError(f"Import banned: {n.name}")
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split('.')[0] in BANNED_IMPORTS: raise ValueError(f"ImportFrom banned: {node.module}")
        if isinstance(node, ast.Attribute):
            # Block dangerous attributes (best-effort)
            if getattr(node, "attr", "") in {"system","popen","execv","spawn"}:
                raise ValueError(f"Attribute banned: {node.attr}")
    return compile(tree, "<cell>", "exec")

def run_step(step_json, inputs):
    code = step_json["python"]
    compiled = safe(code)
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    artifacts = {}
    start = time.time()
    try:
        sys.stdout, sys.stderr = out, err
        exec(compiled, ALLOWED, {"inputs": inputs, "artifacts": artifacts})
        status = "ok"
    except Exception:
        status = "error"
        traceback.print_exc(file=err)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return {
        "status": status,
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        "artifacts": artifacts,
        "duration_sec": round(time.time() - start, 3)
    }
```

*(We’ll add time/memory guards and artifact upload helpers.)*

## Appendix B — Example step JSON (profile)

```json
{
  "intent": "profile",
  "needs": ["dataset_path", "target"],
  "provides": ["df_raw", "profile_summary.json"],
  "python": "import pandas as pd\np = inputs['dataset_path']\ndf = pd.read_csv(p)\nprint('shape:', df.shape)\nprint(df.head(5))\nna = df.isna().mean().to_dict()\nartifacts['df_raw'] = df\nartifacts['profile_summary.json'] = {'na_ratio': na}",
  "notes": "Basic EDA with head() and NA ratios"
}
```

---

If this matches your vision, drop answers to the **7 quick confirmations** and I’ll tailor the caps, the artifacts store, and the exact runner image to your choices (and then we can spin up the repo scaffolding exactly along this plan).



@Untitled.png 


Review my plan


this is the project i want to do with the help of you 
