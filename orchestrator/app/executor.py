from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict
import os
import httpx

import importlib.util


# TODO: switch to an out-of-process sandbox / CodeSandbox VM. For MVP we import locally.
def _load_runner_run_step() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    root = Path(__file__).resolve().parents[2]  # repo root
    runner_path = root / "runner" / "runner.py"
    spec = importlib.util.spec_from_file_location("runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "run_step")


_RUN_STEP = None


def _get_run_step():
    global _RUN_STEP
    if _RUN_STEP is None:
        _RUN_STEP = _load_runner_run_step()
    return _RUN_STEP


@dataclass
class ExecContext:
    session_id: str
    dataset_uri: str
    target: str
    artifact_dir: Path
    stream_queue: "asyncio.Queue[str]"


def _make_profile_step(dataset_uri: str, artifact_dir: Path) -> Dict[str, Any]:
    # Uses injected globals (pd) and avoids imports; returns small dict artifact
    code = (
        f"p = '{dataset_uri.replace('\\', '/')}'\n"
        "p = p[7:] if p.startswith('file://') else p\n"
        "df = pd.read_csv(p)\n"
        "print('shape:', df.shape)\n"
        "print(df.head(5))\n"
        "na = df.isna().mean().to_dict()\n"
        "artifacts['profile_summary.json'] = {'na_ratio': na}\n"
    )
    return {
        "intent": "profile",
        "needs": ["dataset_path"],
        "provides": ["profile_summary.json"],
        "python": code,
        "notes": "Basic EDA: head() and NA ratios",
    }


async def execute_stub_pipeline(ctx: ExecContext) -> None:
    q = ctx.stream_queue
    # Ensure artifact directory exists
    ctx.artifact_dir.mkdir(parents=True, exist_ok=True)

    # Step: profile
    step = _make_profile_step(ctx.dataset_uri, ctx.artifact_dir)
    await q.put(json.dumps({
        "type": "step_started",
        "step": step["intent"],
        "ts": datetime.utcnow().isoformat(),
    }))

    # If RUNNER_URL is set, delegate to remote runner service
    runner_url = os.getenv("RUNNER_URL")
    if runner_url:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{runner_url}/exec_step", json={"step": step, "inputs": {"dataset_path": ctx.dataset_uri}})
            result = resp.json()
    else:
        run_step = _get_run_step()
        result = run_step(step, {"dataset_path": ctx.dataset_uri})

    # Stream stdout/stderr once per step for MVP
    if result.get("stdout"):
        await q.put(json.dumps({
            "type": "stdout",
            "step": step["intent"],
            "data": result["stdout"],
        }))
    if result.get("stderr"):
        await q.put(json.dumps({
            "type": "stderr",
            "step": step["intent"],
            "data": result["stderr"],
        }))

    await q.put(json.dumps({
        "type": "step_finished",
        "step": step["intent"],
        "status": result.get("status"),
        "artifacts": result.get("artifacts", {}),
        "duration_sec": result.get("duration_sec"),
    }))

    # Step: clean (simple MVP)
    def _make_clean_step(dataset_uri: str, artifact_dir: Path) -> Dict[str, Any]:
        code = (
            f"p = '{dataset_uri.replace('\\', '/')}'\n"
            "p = p[7:] if p.startswith('file://') else p\n"
            "df = pd.read_csv(p)\n"
            "print('before_clean:', df.shape)\n"
            "df = df.drop_duplicates()\n"
            "num_cols = df.select_dtypes(include=['number']).columns\n"
            "cat_cols = df.select_dtypes(exclude=['number']).columns\n"
            "for c in num_cols: df[c] = df[c].fillna(df[c].median())\n"
            "for c in cat_cols: df[c] = df[c].fillna(df[c].mode().iloc[0] if not df[c].mode().empty else '')\n"
            f"out_csv = '{(ctx.artifact_dir / 'df_clean.csv').as_posix()}'\n"
            "df.to_csv(out_csv, index=False)\n"
            "print('after_clean:', df.shape)\n"
            "artifacts['df_clean.csv'] = out_csv\n"
        )
        return {
            "intent": "clean",
            "needs": ["dataset_path"],
            "provides": ["df_clean.csv"],
            "python": code,
            "notes": "Drop duplicates and impute NaNs (median/mode).",
        }

    clean_step = _make_clean_step(ctx.dataset_uri, ctx.artifact_dir)
    await q.put(json.dumps({
        "type": "step_started",
        "step": clean_step["intent"],
        "ts": datetime.utcnow().isoformat(),
    }))
    if runner_url:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{runner_url}/exec_step", json={"step": clean_step, "inputs": {"dataset_path": ctx.dataset_uri}})
            result = resp.json()
    else:
        result = run_step(clean_step, {"dataset_path": ctx.dataset_uri})
    if result.get("stdout"):
        await q.put(json.dumps({"type": "stdout", "step": clean_step["intent"], "data": result["stdout"]}))
    if result.get("stderr"):
        await q.put(json.dumps({"type": "stderr", "step": clean_step["intent"], "data": result["stderr"]}))
    await q.put(json.dumps({
        "type": "step_finished",
        "step": clean_step["intent"],
        "status": result.get("status"),
        "artifacts": result.get("artifacts", {}),
        "duration_sec": result.get("duration_sec"),
    }))

    # Step: train baseline (classification or regression by target cardinality)
    def _make_train_step(dataset_clean_csv: str, target: str, artifact_dir: Path) -> Dict[str, Any]:
        code = (
            f"p = '{dataset_clean_csv.replace('\\', '/')}'\n"
            "p = p[7:] if p.startswith('file://') else p\n"
            "df = pd.read_csv(p)\n"
            f"target = '{target}'\n"
            "y = df[target]\n"
            "X = df.drop(columns=[target])\n"
            "is_class = (y.nunique() <= 20)\n"
            "X_train, X_test, y_train, y_test = model_selection.train_test_split(X, y, test_size=0.25, random_state=42, stratify=y if is_class else None)\n"
            "# Simple encoding via get_dummies for MVP\n"
            "X_train = pd.get_dummies(X_train, drop_first=True)\n"
            "X_test = pd.get_dummies(X_test, drop_first=True)\n"
            "X_test = X_test.reindex(columns=X_train.columns, fill_value=0)\n"
            "if is_class:\n"
            "    if y_train.nunique() >= 2:\n"
            "        model = linear_model.LogisticRegression(max_iter=200)\n"
            "        model.fit(X_train, y_train)\n"
            "        preds = model.predict(X_test)\n"
            "        f1 = metrics.f1_score(y_test, preds, average='weighted')\n"
            "        print('F1(weighted):', round(float(f1), 4))\n"
            "        metrics_out = {'f1_weighted': float(f1)}\n"
            "        model_art = {'kind': 'sklearn', 'model': model, 'columns': list(X_train.columns)}\n"
            "    else:\n"
            "        const_val = y_train.iloc[0]\n"
            "        preds = np.full((len(X_test),), const_val)\n"
            "        acc = (preds == y_test.values).mean()\n"
            "        print('Accuracy(constant):', round(float(acc), 4))\n"
            "        metrics_out = {'accuracy': float(acc)}\n"
            "        model_art = {'kind': 'constant', 'value': const_val, 'columns': list(X_train.columns)}\n"
            "else:\n"
            "    model = linear_model.Ridge(alpha=1.0)\n"
            "    model.fit(X_train, y_train)\n"
            "    rmse = metrics.mean_squared_error(y_test, model.predict(X_test), squared=False)\n"
            "    print('RMSE:', round(float(rmse), 4))\n"
            "    metrics_out = {'rmse': float(rmse)}\n"
            f"model_path = '{(artifact_dir / 'baseline_model.pkl').as_posix()}'\n"
            "joblib.dump(model_art, model_path)\n"
            "artifacts['baseline_model.pkl'] = model_path\n"
            "artifacts['metrics.json'] = metrics_out\n"
        )
        return {
            "intent": "train",
            "needs": ["df_clean.csv", "target"],
            "provides": ["baseline_model.pkl", "metrics.json"],
            "python": code,
            "notes": "Train baseline classifier/regressor and save model with metrics.",
        }

    df_clean_path = (ctx.artifact_dir / 'df_clean.csv').as_posix()
    train_step = _make_train_step(df_clean_path, ctx.target, ctx.artifact_dir)
    await q.put(json.dumps({"type": "step_started", "step": train_step["intent"], "ts": datetime.utcnow().isoformat()}))
    if runner_url:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{runner_url}/exec_step", json={"step": train_step, "inputs": {"dataset_path": df_clean_path}})
            result = resp.json()
    else:
        result = run_step(train_step, {"dataset_path": df_clean_path})
    if result.get("stdout"):
        await q.put(json.dumps({"type": "stdout", "step": train_step["intent"], "data": result["stdout"]}))
    if result.get("stderr"):
        await q.put(json.dumps({"type": "stderr", "step": train_step["intent"], "data": result["stderr"]}))
    await q.put(json.dumps({"type": "step_finished", "step": train_step["intent"], "status": result.get("status"), "artifacts": result.get("artifacts", {}), "duration_sec": result.get("duration_sec")}))

    await q.put(json.dumps({"type": "run_finished", "status": "ok"}))
