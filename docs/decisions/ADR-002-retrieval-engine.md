# ADR-002: Retrieval Engine for V2 (SQLite FTS5/BM25)

- **Status:** Accepted
- **Date:** 2026-07-11
- **Deciders:** Nguyen Van An, Le Dinh Nghia (with Supervisor Nguyen Hoang Thanh)
- **Supersedes/extends:** `ADR-001-mvp-scope.md`'s deferred "vector store
  decision" and `docs/diagrams/architecture.md` §5's original placeholder
  (LlamaIndex/LangChain + ChromaDB, never implemented). This ADR resolves
  that deferral for the v2 modernization wave; it does not reopen MVP scope.

## Context

Phase 0-11 never implemented real retrieval — `POST /v1/gateway/chat`
accepts `context_chunks` supplied directly by the caller
(`app/schemas/requests.py`), and the RAG Context Guard only ever evaluates
whatever text it is handed. Three independent reviews of the repository
(`docs/modernization-ai-reviews/codex-code-architecture-review.md`,
`gemini-phase-12a-academic-gate.md`, `grok-phase-12a-redteam-gate.md`) all
identify the absence of real retrieval as the single biggest gap in both
technical credibility and academic defensibility. A retrieval engine must be
chosen before Phase 12B can start.

Constraints that shaped this decision (unchanged from `ADR-001-mvp-scope.md`
and `docs/diagrams/architecture.md` §1-2):

- Must run on a two-student team's own laptops, 16GB RAM, no GPU.
- `AGENT_RULES.md` rule 11 requires approval before adding heavy
  dependencies; the current `requirements.txt` is intentionally minimal
  (FastAPI, Pydantic, Uvicorn, pytest, httpx).
- Reproducibility matters more than retrieval sophistication — the existing
  evaluation harness (Phase 7) depends on deterministic guard decisions, and
  a v2 evaluation harness (Phase 12E) will depend on deterministic
  retrieval results too.
- No paid API calls or model downloads may happen without separate,
  explicit approval (`AGENT_RULES.md` rule 4 covers paid APIs; rule 11
  covers heavy dependencies, which a downloaded embedding model would be).

## Decision

Adopt **SQLite FTS5 with `bm25()` ranking**, accessed through Python's
standard-library `sqlite3` module, as the v2 retrieval engine.

Key implementation requirements (see `docs/modernization-v2-architecture.md`
§2-3 for full detail):

- No new runtime dependency for the core retrieval path — `sqlite3` ships
  with CPython.
- An explicit capability check for FTS5 support must run before retrieval
  is used, failing with a clear error rather than silently degrading, since
  not every SQLite build/platform combination compiles FTS5 in.
- A persistent local `.db` file (not in-memory-only), so ingested documents
  survive a process restart.
- Short-lived connections per request rather than one long-lived global
  connection, because SQLite connections are not safely shared across
  FastAPI's threaded/async request handling without careful discipline.
- Parameterized SQL throughout, and — distinct from SQL parameterization —
  explicit escaping/tokenization of user query text before it is placed
  into an FTS5 `MATCH` expression, since FTS5 has its own query syntax with
  operators that raw concatenation could let a caller manipulate (see
  `docs/modernization-v2-threat-model.md` §3, Tampering row on FTS5 query
  injection).
- Deterministic ranking with an explicit tie-breaking rule (`bm25()` score,
  then a stable secondary key such as `chunk_id`), so the same query against
  the same corpus always returns the same ordered result — required for
  reproducible evaluation.

## Alternatives Considered

| Option | Why not chosen (for now) |
|---|---|
| **Lightweight vector store** (e.g., a small local embedding model + cosine similarity, possibly via a minimal library) | Requires downloading and running an embedding model — new dependency weight, reproducibility risk (model version drift), and meaningfully more setup complexity for uncertain benefit given the project's rule-based, explainability-first design philosophy (`docs/diagrams/architecture.md` NFR7). Not rejected permanently — recorded as Phase 12F, optional and later, requiring its own approval. |
| **Hybrid (BM25 + vector)** | Best theoretical retrieval quality, but requires both of the above plus score-normalization work across two ranking systems and a larger evaluation burden. Explicitly sequenced as "V3 after A" by the Codex review; adopted as Phase 12F/later, not now. |
| **Mock retrieval + trust/DLP only (no real search)** | Lowest implementation risk, but does not resolve the core credibility gap all three reviews identify — the project would still not be able to claim it does real retrieval. Rejected as insufficient for the stated goal of this modernization wave. |
| **A RAG framework (LlamaIndex or LangChain)**, as originally left open in `ADR-001-mvp-scope.md` | Would satisfy the original Phase 5 placeholder, but pulls in a much larger dependency surface than the actual problem requires (a keyword-searchable local document store), and reintroduces the exact framework-lock-in risk `ADR-001-mvp-scope.md`'s own risk table already flagged. A hand-rolled SQLite FTS5 layer is small enough to fully understand, explain, and test end to end — a better fit for `AGENT_RULES.md` rule 11's "ask before adding heavy dependencies" and NFR7's "favor simple, explainable" preference. |

## Consequences

- Retrieval quality is lexical/keyword-based only; it will not match
  paraphrased or semantically-similar-but-lexically-different queries. This
  is a named, accepted limitation for the v2 modernization wave, not a
  hidden one — it must appear in the final report's limitations section
  alongside the existing rule-based-guard limitations already documented.
- `POST /v1/retrieve` and `POST /v1/rag/query` (see
  `docs/modernization-v2-architecture.md` §6) depend on this engine;
  `POST /v1/gateway/chat` does not and remains fully unaffected by this
  decision.
- The `Retriever` protocol (`app/retrieval/base.py`, target) is defined so
  that a future vector or hybrid retriever (Phase 12F) can be added as a
  second implementation without requiring changes to ingestion callers,
  the RAG Query Service, or the guard pipeline.
- Any future decision to add Phase 12F (vector/hybrid retrieval) or replace
  this engine requires a new ADR, not a silent extension of this one, per
  `AGENT_RULES.md` rule 1.
