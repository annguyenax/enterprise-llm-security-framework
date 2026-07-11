# datasets/

Synthetic enterprise document benchmark used as the RAG knowledge base for this project's (not-yet-built) demo application, and as fixtures for guard evaluation.

**Status: Phase 3 — populated with a controlled synthetic enterprise benchmark.** No application code reads these files yet (no RAG pipeline, no ingestion script, no vector store exist — see `TASK_BOARD.md` Phase 5). This is data/design content only.

## Purpose

Provide a **realistic, controlled synthetic enterprise RAG benchmark** — not a handful of toy one-liners — that:

1. Represents plausible enterprise document types (HR, IT, security, product, finance) with the kind of metadata a real document management system would carry (ID, version, owner, classification, last-updated date).
2. Provides a **clean baseline** corpus for measuring False Positive Rate (a correctly-working guard must never flag these).
3. Provides a **poisoned variant** for each attack pattern identified in `docs/diagrams/threat-model.md`, each explicitly paired with (and modeled after) a specific clean document, so evaluation can compare "guard sees the real policy" vs. "guard sees a manipulated version of the same policy."

All content — company name, product name, tool names, people, figures — is **100% fictional**, invented for this project. See "Safety rules" below.

## Folder Structure

```
datasets/
├── clean/                          # Known-good baseline documents (5)
│   ├── hr-policy.md                 # NW-HR-001
│   ├── it-helpdesk-policy.md        # NW-IT-002
│   ├── security-guideline.md        # NW-SEC-003
│   ├── product-faq.md               # NW-PRD-004
│   └── finance-reimbursement.md     # NW-FIN-005
└── poisoned/                        # Poisoned variants, one per attack type (5)
    ├── hidden-html-instruction.md       # RT-POISON-001, based on NW-PRD-004
    ├── system-override.md               # RT-POISON-002
    ├── fake-secret-leak.md              # RT-POISON-003, based on NW-IT-002
    ├── policy-bypass.md                 # RT-POISON-004, based on NW-FIN-005
    └── support-transcript-injection.md  # RT-POISON-005, based on NW-IT-002
```

Every file is Markdown with a YAML front-matter block (`document_id`, `title`, `version`/`attack_type`, `owner_department`, `classification`, etc.) followed by human-readable content — chosen so the files are readable both as documentation and as structured data a future ingestion script can parse.

## Document Metadata Convention

Every **clean** document's front-matter includes:

| Field | Meaning |
|---|---|
| `document_id` | Stable ID, e.g. `NW-HR-001` (`NW` = Northwind, department code, sequence number) |
| `title` | Human-readable document title |
| `version` | Document version (fictional, illustrative revision history) |
| `owner_department` | Which fictional department owns/maintains the document |
| `last_updated` | Fictional last-revision date |
| `classification` | Always `Internal Synthetic Demo` in this dataset |
| `company` | Always the fictional `Northwind Retail Group`, explicitly labeled fictional |
| `status` | `active` for all current clean documents |
| `source_type` | `clean_baseline` |

Every **poisoned** document's front-matter includes `document_id` (using the `RT-POISON-NNN` convention from `docs/evaluation/red-team-test-design.md` §6), `attack_type`, `based_on_clean_doc` (cross-reference), `expected_risk`, `expected_guard_decision`, and `target_guard`.

## Safety Rules (read before adding anything new)

- **Synthetic-only, no exceptions.** No real PII, no real secrets/credentials/tokens, no real internal system names, no real company other than the invented "Northwind Retail Group" (per `AGENT_RULES.md` rules 5 and 7).
- **Fake secrets use an obviously fake format.** Any "secret-like" string (see `datasets/poisoned/fake-secret-leak.md`) must use the `FAKE-SECRET-0000-EXAMPLE` pattern or equivalent — never a realistic-looking key format (e.g., never prefix with `sk-` or similar real-vendor patterns).
- **Poisoned documents are clearly marked.** Every file in `datasets/poisoned/` opens with a `SYNTHETIC ATTACK DATA` notice and is scoped to attack only this project's own lab-scale gateway — never written as if targeting a real system.
- **Attacks are illustrative, not operational.** Poisoned content is just strong enough to exercise a guard decision; it does not contain step-by-step exploitation instructions beyond what's needed to demonstrate the pattern.
- If new content is inspired by a public research dataset or tool probe set, it must first be logged in `docs/research/dataset-review.md` — this directory itself must contain only original synthetic re-implementations, not verbatim copies.

## How the Future Evaluation Runner Will Use This Data (planned, Phase 5/7 — not implemented)

1. **Ingestion (Phase 5):** A not-yet-built ingestion script will load `datasets/clean/*.md` and `datasets/poisoned/*.md` into the demo vector store, tagging each with its `document_id` and `classification` as provenance metadata (see the ingestion data-flow diagram in `docs/diagrams/data-flow.md` §2).
2. **Retrieval + RAG Guard test (Phase 5/7):** For each poisoned document, the evaluation runner will query the RAG pipeline with a prompt likely to retrieve that document, then check whether the RAG Guard's actual decision matches the `expected_guard_decision` recorded in its front-matter.
3. **False Positive check (Phase 7):** The same runner will separately query for content covered by the 5 clean documents and confirm none of them are ever flagged — feeding directly into the False Positive Rate metric (`docs/evaluation/metrics-definition.md` §4).
4. **Reporting (Phase 7):** Per-document results (expected vs. actual decision) will be aggregated into the evaluation report described in `docs/evaluation/evaluation-plan.md` — no results exist yet; this dataset only makes that future run possible.

## Related Documents

- `docs/evaluation/red-team-test-design.md` — original design rationale for this benchmark (5 clean + 5 poisoned categories), written before these files existed.
- `docs/evaluation/metrics-definition.md` — how guard decisions on this data become ASR/FPR/FNR/etc.
- `redteam/` — the companion prompt-based (non-document) attack benchmark.
