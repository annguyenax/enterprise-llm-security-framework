"""FastAPI application entrypoint — LLM Security Gateway academic PoC.

Lab-scale proof-of-concept for a university internship project. NOT
production-ready (see AGENT_RULES.md rule 8 and docs/decisions/ADR-001-mvp-scope.md).
SQLite FTS5/BM25 retrieval and the guarded `/v1/rag/query` path are
implemented. No external LLM is called; the provider remains a local mock.

Run locally with:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Ensure the audit log directory exists before the app starts serving.
    Path(settings.log_path).parent.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="LLM Security Gateway",
    description=(
        "Lab-scale proof-of-concept guardrail gateway for a university internship project. "
        "Not production-ready. Uses SQLite FTS5/BM25 retrieval, rule-based guards, "
        "and a deterministic local mock provider; no external LLM is called."
    ),
    version="0.12.0",
    lifespan=lifespan,
)

app.include_router(router)
