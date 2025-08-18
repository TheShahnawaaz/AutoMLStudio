from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field
from .executor import ExecContext, execute_stub_pipeline

RUNNER_URL = os.getenv("RUNNER_URL")


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    dataset_uri: Optional[str] = None
    goal: Optional[str] = None
    target: Optional[str] = None


class StartRunRequest(BaseModel):
    goal: str
    target: str
    dataset_uri: str


app = FastAPI(title="AutoML Chat Orchestrator", version="0.1.0")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory storage for MVP. TODO: replace with Postgres (SQLAlchemy) and Redis queue
SESSIONS: Dict[str, Session] = {}
STREAMS: Dict[str, asyncio.Queue[str]] = {}
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("ALLOWED_DATASET_MB", "100"))


@app.get("/")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions", response_model=Session)
def create_session() -> Session:
    session = Session()
    SESSIONS[session.id] = session
    STREAMS[session.id] = asyncio.Queue()
    return session


@app.post("/sessions/{session_id}/start")
async def start_run(session_id: str, body: StartRunRequest) -> JSONResponse:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="session not found")
    # Persist basic info
    s = SESSIONS[session_id]
    s.dataset_uri = body.dataset_uri
    s.goal = body.goal
    s.target = body.target

    # Enqueue a minimal local pipeline for MVP
    q = STREAMS[session_id]
    await q.put(json.dumps({
        "type": "run_started",
        "session_id": session_id,
        "ts": datetime.utcnow().isoformat(),
        "message": "Run accepted. Planner execution will begin shortly (stub)."
    }))
    artifact_dir = Path("artifacts") / session_id
    asyncio.create_task(
        execute_stub_pipeline(
            ExecContext(
                session_id=session_id,
                dataset_uri=body.dataset_uri,
                target=body.target,
                artifact_dir=artifact_dir,
                stream_queue=q,
            )
        )
    )
    return JSONResponse({"status": "accepted", "session_id": session_id})


@app.post("/sessions/{session_id}/upload")
async def upload_dataset(session_id: str, file: UploadFile = File(...)) -> Dict[str, str]:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="session not found")
    # Basic type check
    if not (file.filename.endswith(".csv") or file.content_type in {"text/csv", "application/vnd.ms-excel"}):
        raise HTTPException(
            status_code=400, detail="only CSV uploads supported in MVP")
    # Stream to disk with size cap
    dest = UPLOAD_DIR / f"{session_id}_{uuid.uuid4().hex}.csv"
    size_bytes = 0
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail=f"file exceeds limit of {MAX_UPLOAD_MB} MB")
            out.write(chunk)
    dataset_uri = f"file://{dest}"
    # Record on session as convenience
    SESSIONS[session_id].dataset_uri = dataset_uri
    return {"dataset_uri": dataset_uri, "filename": file.filename}


async def sse_generator(session_id: str) -> AsyncGenerator[str, None]:
    if session_id not in STREAMS:
        # Small delay to prevent event-loop churn in client retries
        yield json.dumps({"type": "error", "message": "unknown session"})
        return
    q = STREAMS[session_id]
    # Initial hello
    yield json.dumps({"type": "hello", "session_id": session_id})
    # Heartbeats + queue drains
    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=1.0)
                yield item
            except asyncio.TimeoutError:
                yield json.dumps({"type": "heartbeat", "ts": datetime.utcnow().isoformat()})
    except asyncio.CancelledError:
        # Client disconnected
        return


@app.get("/sessions/{session_id}/stream")
async def stream(session_id: str):
    return EventSourceResponse(sse_generator(session_id))


# TODO: /sessions/{id}/upload -> presigned URL (Supabase)
# TODO: /sessions/{id}/artifacts -> list artifacts
# TODO: /runner/claim and /runner/complete
