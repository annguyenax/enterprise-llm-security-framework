# app/

Application code for the LLM Security Gateway / Guardrail Proxy.

**Status: empty — Phase 0 scaffold only.** No application code has been implemented yet. Implementation begins in Phase 3 (Gateway skeleton) per `TASK_BOARD.md`.

## Planned Layout (not yet created)

```
app/
├── main.py              # FastAPI entrypoint
├── config.py            # Pydantic settings
├── gateway/             # Orchestration logic
├── guards/
│   ├── input_guard.py
│   ├── rag_guard.py
│   └── output_guard.py
├── rag/                 # RAG pipeline (retrieval, ingestion)
└── logging_utils.py     # JSONL structured logging
```

This layout is a plan, not a commitment — it may change once Phase 3 design work starts. See `docs/diagrams/architecture.md` for the conceptual flow this code will implement.
