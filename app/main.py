"""FastAPI application entrypoint — LLM Security Gateway (Phase 4 skeleton).

Lab-scale proof-of-concept for a university internship project. NOT
production-ready (see AGENT_RULES.md rule 8 and docs/decisions/ADR-001-mvp-scope.md).
No real LLM is called; no real RAG retrieval exists yet — see
app/services/gateway.py for the mock pipeline this phase implements.

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
    title="LLM Security Gateway (Phase 4 Skeleton)",
    description=(
        "Lab-scale proof-of-concept guardrail gateway for a university internship project. "
        "Not production-ready. Uses simple rule-based heuristics only; no real LLM or RAG "
        "retrieval is called in this phase."
    ),
    version="0.4.0",
    lifespan=lifespan,
)

app.include_router(router)
