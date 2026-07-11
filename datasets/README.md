# datasets/

Synthetic datasets used for RAG demo content and evaluation.

**Status: empty — Phase 0 scaffold only.** Populated starting Phase 2.

## Rules (per `AGENT_RULES.md` rule 5)

- **Synthetic data only.** No real PII, no real secrets, no real private/internal/enterprise documents.
- If content is inspired by a public research dataset, it must be reviewed in `docs/research/dataset-review.md` first, and only original synthetic re-implementations are stored here — not verbatim copies unless license explicitly permits redistribution and content contains no real sensitive data.

## Planned Contents (not yet created)

- `rag_corpus/` — synthetic "enterprise-like" documents for the demo RAG knowledge base (e.g., fake company policies, fake product docs).
- `poisoned_corpus/` — synthetic poisoned variants of the above, for RAG poisoning evaluation.
- `eval_labels/` — ground-truth labels for evaluation (which inputs/documents should be flagged, by which guard).
