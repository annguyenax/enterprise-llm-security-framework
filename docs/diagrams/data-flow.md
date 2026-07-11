# Data Flow Diagrams — Phase 2

> Planning-level data flow for the MVP. Reflects target design only — see `TASK_BOARD.md` for implementation status. Modules referenced below are defined in `docs/diagrams/architecture.md` §4 (Module Responsibility Table).

## 1. Request/Response Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Demo UI/API
    participant GW as Security Gateway
    participant IG as Input Guard
    participant VS as Vector Store (RAG corpus)
    participant RG as RAG Guard
    participant LLM as LLM Provider API
    participant OG as Output Guard
    participant LOG as Logging/Evaluation

    U->>UI: Submit prompt
    UI->>GW: Forward request
    GW->>IG: Check input
    alt Input flagged (injection/jailbreak)
        IG->>LOG: Log block + reason
        IG-->>UI: Return blocked response
    else Input clean
        IG->>VS: Retrieve relevant documents
        VS-->>RG: Candidate documents
        RG->>LOG: Log flagged/sanitized documents
        RG->>LLM: Send sanitized prompt + context
        LLM-->>OG: Raw completion
        alt Output flagged (leakage/policy)
            OG->>LOG: Log block + reason
            OG-->>UI: Return blocked/redacted response
        else Output clean
            OG->>LOG: Log allowed response
            OG-->>UI: Return response
        end
    end
    UI-->>U: Display result
```

### Notes

- Every branch (blocked input, flagged document, blocked output, allowed output) writes to the Logging/Evaluation sink — this is the basis for the Phase 7 evaluation harness and the STRIDE Repudiation mitigation in `threat-model.md`.
- "Sanitized prompt + context" means the RAG Guard has removed or neutralized suspected injected instructions before assembling the final LLM prompt.
- No user data leaves the system to any destination other than the configured LLM Provider API and local logs.

## 2. Document Ingestion Data Flow (planned)

The request/response flow above assumes documents already exist in the Vector Store. This second flow covers how synthetic documents get there, since the threat model's Spoofing and Tampering-at-ingestion rows (`docs/diagrams/threat-model.md`) depend on it.

```mermaid
flowchart LR
    SRC[Synthetic Document Source<br/>datasets/rag_corpus, datasets/poisoned_corpus]
    ING[Ingestion Script<br/>scripts/, Phase 5]
    PROV[(Provenance / Source ID<br/>tagging)]
    VS[(Vector Store<br/>RAG corpus)]
    LOG[(Logging / Evaluation)]

    SRC --> ING
    ING --> PROV
    PROV --> VS
    ING -.ingestion record.-> LOG
```

### Notes

- Every ingested document is tagged with a provenance/source ID at ingestion time — this directly implements the Spoofing mitigation in `threat-model.md` ("track document provenance/source ID").
- This flow is **planning-level only** — `scripts/` and `datasets/` are currently empty per their own READMEs; ingestion logic is Phase 5 work, not implemented by this documentation-only pass.
- The "poisoned_corpus" source in the diagram refers to the synthetic poisoned-document test set planned in `TASK_BOARD.md` Phase 2 ("Synthetic poisoned-document set (RAG poisoning)"), not a real threat feed.

## Status

Target design for Phase 3–7 implementation. No code implements either flow yet. This document only adds design detail (the ingestion flow) on top of the Phase 0 draft; no packages were installed and no APIs were called to produce it.
