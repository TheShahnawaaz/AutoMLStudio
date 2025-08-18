FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY runner/requirements.txt /tmp/runner-requirements.txt
RUN pip install -r /tmp/runner-requirements.txt

COPY orchestrator/requirements.txt /tmp/orch-requirements.txt
RUN pip install -r /tmp/orch-requirements.txt || true

COPY . /workspace


