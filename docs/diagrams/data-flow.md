# Data Flow Diagram

> Planning-level data flow for the MVP. Reflects target design only — see `TASK_BOARD.md` for implementation status.

## Request/Response Data Flow

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

## Notes

- Every branch (blocked input, flagged document, blocked output, allowed output) writes to the Logging/Evaluation sink — this is the basis for the Phase 7 evaluation harness.
- "Sanitized prompt + context" means the RAG Guard has removed or neutralized suspected injected instructions before assembling the final LLM prompt.
- No user data leaves the system to any destination other than the configured LLM Provider API and local logs.

## Status

Target design for Phase 3–7 implementation. No code implements this flow yet.
