**## Critical security gaps**

1. **File**: `docs/decisions/ADR-002-retrieval-engine.md` (Section: Decision / Key implementation requirements)  
   **Issue**: FTS5 query construction mentions "safe" parameterization but lacks explicit details on tokenization/escaping for `MATCH` operators.  
   **Correction**: Add explicit requirement for query tokenization + operator escaping (e.g., treat user text as terms only, not raw syntax) with test cases for abuse.

2. **File**: `docs/modernization-v2-threat-model.md` (Section: 3. STRIDE Extension, Tampering row on multi-chunk)  
   **Issue**: Acknowledges multi-chunk coordination as high residual risk but provides no mitigation plan beyond documentation.  
   **Correction**: Require per-ingestion or pre-retrieval cross-chunk scanning heuristic (simple co-occurrence check) as minimum in Phase 12C acceptance criteria.

3. **File**: `docs/modernization-final-plan.md` (Section: 4. Required Engineering Decisions, A. Retrieval)  
   **Issue**: FTS5 capability check is required but silent fallback risk not fully eliminated in prose.  
   **Correction**: Strengthen to "must fail hard at startup if FTS5 unavailable; no runtime fallback allowed anywhere."

**## Major security gaps**

1. **File**: `docs/modernization-v2-architecture.md` (Section: 4. Trust and Provenance Model)  
   **Issue**: Server-controlled trust derivation is planned but lacks auditability details for assignment decisions.  
   **Correction**: Mandate structured logging of source-policy mapping decisions on every ingest.

2. **File**: `docs/decisions/ADR-003-v2-benchmark.md` (Section: Split structure / Holdout split)  
   **Issue**: Holdout rules are strong but lack explicit prevention of indirect leakage (e.g., via dev set patterns influencing holdout design).  
   **Correction**: Add "holdout authoring must be performed by a separate team member or after a time gap from dev/validation."

3. **File**: `docs/modernization-v2-threat-model.md` (Section: 3. STRIDE, Information Disclosure on DLP)  
   **Issue**: Centralization risk noted but no regression testing mandate across all call sites.  
   **Correction**: Require pre/post-consolidation redaction parity tests on full fixture set in Phase 12C criteria.

**## Likely bypasses not represented**

1. **File**: `docs/modernization-v2-threat-model.md` (Section: 4. Threat Category Matrix)  
   **Bypass**: BM25 ranking manipulation via keyword-stuffed but semantically benign-looking documents (not fully covered in poisoning scenarios).  
   **Note**: Add to retrieval poisoning family.

2. **File**: `docs/modernization-v2-threat-model.md` (Section: Required indirect-injection variants)  
   **Bypass**: Zero-width/Unicode obfuscation or base64-encoded instructions in ingested docs.  
   **Note**: Expand hidden content variants.

3. **File**: `docs/decisions/ADR-002-retrieval-engine.md` (Section: Decision)  
   **Bypass**: FTS5 `NEAR`/`phrase` operator abuse if escaping is incomplete.  
   **Note**: Test explicitly in 12B.

**## Missing benign counterexamples**

1. **File**: `docs/modernization-v2-threat-model.md` (Section: 4. Required benign-counterexample families)  
   **Missing**: Legitimate documents with canaries/PII in approved high-trust sources (tests DLP over-redaction).  
   **Correction**: Explicitly add to benign families.

2. **File**: `docs/modernization-v2-threat-model.md` (Section: 4.)  
   **Missing**: Queries with natural policy language that trigger weak signals but should be allowed.  
   **Correction**: Broaden trap examples.

**## Required corrections before Phase 12B**

1. **File**: `docs/decisions/ADR-002-retrieval-engine.md` (FTS5 section) – Add detailed escaping/tokenization spec.  
2. **File**: `docs/modernization-final-plan.md` (Phase 12B criteria) – Strengthen FTS5 hard-fail and query sanitization requirements.  
3. **File**: `docs/modernization-v2-threat-model.md` (STRIDE Tampering) – Add basic multi-chunk heuristic to planned mitigations.  
4. **File**: All threat/ADR docs – Ensure FTS5 fallback rule ("fail closed, no silent LIKE switch") is verbatim in acceptance criteria.

**## Useful but optional improvements**

- Expand provenance audit logging with immutable ingestion receipts.
- Add content-hash + version checks for document replacement detection.
- Include multilingual/paraphrasing variants earlier in benchmark design guidance.
- Document deterministic tie-breaking impact on reproducibility explicitly.

**## Final verdict: REVISE**

The planning docs are thoughtful and align well with laptop constraints, OWASP/MITRE/NIST principles, and prior red-team feedback. However, critical gaps in FTS5 query safety, multi-chunk handling, and holdout integrity must be addressed before implementation begins to prevent introducing new attack surfaces. Revise the listed sections and re-review. Strong foundation overall—proceed after fixes. (Word count: ~850)