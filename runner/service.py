from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .runner import run_step


class ExecRequest(BaseModel):
    step: Dict[str, Any]
    inputs: Dict[str, Any] = {}


class FetchRequest(BaseModel):
    url: str
    dest: str


app = FastAPI(title="AutoML Runner Service", version="0.1.0")

DATA_DIR = Path(os.getenv("RUNNER_DATA_DIR", "./runner_data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
MAX_MB = int(os.getenv("ALLOWED_DATASET_MB", "100"))


@app.get("/")
def root():
    return {"status": "ok", "data_dir": str(DATA_DIR)}


@app.post("/exec_step")
def exec_step(req: ExecRequest):
    result = run_step(req.step, req.inputs)
    return result


@app.post("/fetch_dataset")
def fetch_dataset(req: FetchRequest):
    dest = Path(req.dest)
    if not dest.is_absolute():
        dest = DATA_DIR / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = MAX_MB * 1024 * 1024
    size = 0
    try:
        with httpx.stream("GET", req.url, timeout=60.0, follow_redirects=True) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        f.close()
                        dest.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413, detail="file exceeds size limit")
                    f.write(chunk)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"path": str(dest)}
