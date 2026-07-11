# Modernization V2 Threat Model (Phase 12A)

> Extends `docs/diagrams/threat-model.md` (Phase 2 STRIDE model, still accurate
> for the Phase 0-11 as-built system) with the new assets, trust boundaries,
> and threats introduced by real retrieval, persistent ingestion, provenance,
> and centralized DLP. Planning-level only; no code exists yet for anything
> described here. Risk ratings are qualitative team judgment, consistent with
> the existing threat model's own stated approach — no numeric claim is made
> until an actual v2 evaluation run exists (Phase 12E).

## 1. New Assets (beyond the existing Phase 2 list)

- The **persistent document store** (SQLite file + FTS5 index) — previously
  there was no persisted RAG corpus at all; caller-supplied `context_chunks`
  never touched disk.
- The **ingestion pipeline** and its source-policy configuration (which
  source maps to which `trust_level`).
- **Provenance/trust metadata** attached to each document/chunk.
- The **centralized DLP detector/redaction ruleset**
  (`app/guards/dlp_guard.py`, target).
- The **v2 benchmark corpus** itself (dev/validation/holdout splits) and its
  SHA-256 freeze manifest.
- The **`GuardProfile` ablation configuration** (Phase 12E) — not a
  production security boundary, but a new artifact whose integrity matters
  for evaluation validity (a corrupted profile could silently under-test a
  layer).

## 2. New/Changed Trust Boundaries

| Boundary | Nature | Why it matters for v2 |
|---|---|---|
| Caller (`POST /v1/documents/ingest`) <-> Ingestion Service | Untrusted -> server-controlled | The caller supplies document content but must **never** be able to set `trust_level` directly. This boundary is where required decision C is enforced. |
| Ingestion Service <-> Document Store | Server-controlled -> persistent | Once ingested, trust/provenance is fixed for that document until a deliberate re-ingestion/policy change — not mutable per-query. |
| Retriever <-> RAG Context Guard | Semi-trusted -> guarded | Same boundary that already existed conceptually in `docs/diagrams/threat-model.md` (Tampering row), now backed by a real retrieval step instead of caller-supplied text. |
| Caller (`POST /v1/rag/query`) <-> query string | Untrusted -> FTS5 `MATCH` expression | New boundary that did not exist before: user-controlled text now flows into a structured query language (FTS5) with its own operators, not just into guard regexes. |
| Output Guard <-> Centralized DLP module | Internal, but now shared | Consolidating three previously-independent secret/PII pattern sets into one module means a single defect can affect all three call sites — a new single-point-of-failure to test carefully, in exchange for removing drift risk between the three previously-separate copies. |

## 3. STRIDE Extension for V2

Builds directly on `docs/diagrams/threat-model.md`'s existing table; only new
or materially changed rows are listed here.

| STRIDE | Risk | Relevant module | Planned mitigation (v2) | Risk rating |
|---|---|---|---|---|
| **S**poofing | Provenance spoofing: a malicious or careless ingestion caller supplies metadata implying higher trust than warranted | Ingestion Service | `trust_level` is never accepted from the request; it is derived only from a server-controlled source-policy mapping (required decision C) | High if unmitigated; Low once the server-side-only rule is actually enforced and tested |
| **S**poofing | Benchmark ground truth leaking into a trust decision: `DocumentChunk.is_poisoned` (v1) accidentally read by v2 runtime code | Retrieval / RAG Guard integration | Explicit code-review/test rule: no runtime path may import or branch on `is_poisoned`; only the offline evaluation runner may read it, purely for scoring | Medium — subtle, easy to introduce by accident during Phase 12B/12C if v1 loader output is reused carelessly as seed data |
| **T**ampering | Retrieval poisoning: a malicious document is ingested and, independent of any hidden-instruction content, is engineered to **rank highly** for target queries (e.g., keyword stuffing tuned to BM25 scoring) so it reliably reaches context even without tripping RAG Guard content rules | Ingestion, Retriever | Out of scope to fully solve in 12B-12E (would need relevance/anomaly modeling); documented as a known residual risk. Provenance/trust filtering (12C) provides partial mitigation if the poisoned document also has to come from a lower-trust source to be ingested at all. | High (residual, explicitly acknowledged, not eliminated) |
| **T**ampering | FTS5 query-syntax injection: raw user query text reaches `MATCH` without being treated as a structured query language, letting a crafted query string alter matching behavior via FTS5 operators (`NEAR`, column filters, boolean operators, quoting) even though SQL-level parameterization is used correctly | Retriever (`app/retrieval/sqlite_bm25.py`, target) | Required decision A: "safe FTS query construction" — user query terms must be tokenized/escaped before being placed into the FTS5 query string, not concatenated raw even inside a parameterized SQL statement (parameterization protects against SQL injection, not FTS5 query-syntax injection — these are different risks) | Medium-High until the escaping is implemented and tested; this is a genuinely new risk class introduced by adding a real query language, absent from the v1 architecture entirely |
| **T**ampering | Multi-chunk coordination: an attack instruction is deliberately split across two or more separately-retrieved chunks, none of which individually matches a RAG Guard content rule, but which combine into a coherent instruction once placed together in context | Retriever, RAG Context Guard | Out of scope to fully solve in 12B-12E (would require cross-chunk reasoning, a meaningfully harder problem than single-chunk rule matching); documented as a known limitation of a per-chunk rule-based guard, explicitly named in the final report's limitations section | High (residual, explicitly acknowledged, not eliminated) |
| **T**ampering | Existing v1 Tampering rows (indirect prompt injection, RAG document poisoning via content) | RAG Context Guard | Unchanged from v1; still mitigated at the content-detection layer; now additionally exercised against retrieval-supplied (not just caller-supplied) chunks | High, same rating as v1 — not newly introduced, just now tested end-to-end |
| **R**epudiation | No record of *why* a document was ingested with a given trust level, or of the retrieval trace (which chunks were considered, ranked, and dropped) behind a given answer | Audit Logger, Retriever | Extend structured JSONL logging to include ingestion source-policy decisions and a retrieval trace (query, top-k hit IDs, scores) alongside the existing guard-decision logging; never log raw document content beyond the existing preview/redaction conventions | Low (same mitigation pattern as v1, just extended in scope) |
| **I**nformation Disclosure | DLP consolidation defect: centralizing secret/PII detectors into one module could introduce a single regression that silently weakens redaction across all three call sites at once (Output Guard, RAG Guard, audit logger), whereas today a bug in one duplicated copy would not affect the other two | Centralized DLP module | Regression tests explicitly comparing pre/post-consolidation redaction behavior on the full existing fixture set before the refactor is considered complete (Phase 12C acceptance criteria) | Medium — a real risk of centralization, worth naming explicitly rather than assuming consolidation is strictly safer |
| **I**nformation Disclosure | Benign over-redaction (DLP false positives) reducing usability by masking legitimate content (e.g., a real order number or ordinary email address in a benign enterprise query) | Centralized DLP module | Explicitly measured as its own metric ("benign over-redaction") in Phase 12E, not just implicitly accepted as a side effect of being "safe by default" | Medium, and explicitly a usability metric, not just a security one — matches the FPR/usability concern raised by all three reviews |
| **D**enial of Service | Unbounded ingestion batch size, unbounded document text length, or unbounded `top_k` in a retrieval/query request causing excessive memory/CPU use on a 16GB laptop | Ingestion Service, Retriever | Required decisions B and D: explicit size limits on ingestion, explicit bounded `top_k` on retrieval/query endpoints | Medium — still explicitly out of full DoS-hardening scope per the existing threat model's own "Explicitly Out of Scope" section, but basic bounds are cheap and directly prevent the most obvious laptop-resource-exhaustion case |
| **E**levation of Privilege | Existing v1 rows (direct prompt injection / jailbreak via Input Guard; injected retrieved-content instructions via RAG+Output Guard) | Input Guard, RAG Guard, Output Guard | Unchanged; now exercised against retrieval-supplied chunks in addition to caller-supplied ones | High, same rating as v1 |

## 4. Threat Category Matrix (Grok red-team gate, adopted for V2 scenario design)

Reference matrix for Phase 12D scenario authoring — cross-referenced against
required decision E ("approximately balanced benign and malicious
scenarios"), not a locked case-count table:

| Category | Direct | Indirect (RAG) | Retrieval poisoning | Leakage |
|---|---|---|---|---|
| Prompt injection | Input Guard | RAG Context Guard | Retriever/ingestion | Output Guard / DLP |
| Policy bypass | Input Guard (existing rules) | RAG Context Guard (existing `policy_bypass` category) | N/A | N/A |
| Authority override | Input Guard (existing rules) | RAG Context Guard (existing `instruction_override` category) + Provenance | Provenance/trust filtering | DLP |
| Data exfiltration | Low relevance (no direct-injection data-exfil rule exists in v1; would need a new category) | Medium (indirect instruction attempting exfil via retrieved content) | Low (poisoning targets ranking, not direct exfil) | High (synthetic canary leakage is the primary measurable signal) |

Required indirect-injection variant families for v2 scenario authoring
(Grok's review, adopted as design input — not yet authored):

1. Hidden instructions in document body/comments/metadata (extends v1's
   `hidden-html-instruction.md` pattern).
2. Quoted "support transcript" style injection (extends v1's
   `support-transcript-injection.md` pattern).
3. Authority claims ("this document supersedes...") (extends v1's
   `system-override.md` pattern).
4. **New for v2:** multi-chunk coordination — instruction split across two
   or more retrieved chunks (see STRIDE Tampering row above; this is a new
   attack family with no v1 equivalent, since v1 never had multi-chunk
   retrieval at all).
5. Obfuscated/synonym variants of existing v1 patterns (directly supports
   Gemini's "Rule of Variance" — v2 must not just restate v1 payloads
   verbatim).

Required benign-counterexample families (Grok's review, adopted as design
input):

- Legitimate policy updates using "override"/"authoritative" language in a
  clearly benign context (extends v1's existing weak-signal
  `rag-weak-override-keyword` / `log_only` handling — v1 already has a
  narrow test for this pattern; v2 should broaden it).
- Internal memos with authority claims or transcript quotes that are
  benign.
- Product FAQs with structured data that superficially resembles an
  injection pattern.
- HR/compliance content containing synthetic PII/canaries in an
  **approved, expected** context (to measure benign over-redaction
  specifically, distinct from a real leakage case).

## 5. Explicitly Out of Scope for V2 (Phases 12B-12E)

Unchanged from `docs/diagrams/threat-model.md` §"Explicitly Out of Scope" and
`docs/diagrams/architecture.md` §5, plus new v2-specific exclusions:

- Full resolution of retrieval-ranking poisoning (named above as a residual
  risk, not solved).
- Full resolution of multi-chunk coordinated injection (named above as a
  residual risk, not solved).
- Model-training/fine-tuning poisoning (still not applicable — provider
  remains mock/offline).
- Full agentic/multi-agent tool-use security.
- Production-scale vector databases or real embedding models (deferred to
  optional Phase 12F).
- Real enterprise data or live external document sources — all v2 ingestion
  content remains synthetic, per `AGENT_RULES.md` rule 5.
- Advanced adversarial ML attacks against embeddings (not applicable while
  retrieval is lexical/BM25-only).

## 6. On Numeric Targets (reconciliation note)

`grok-phase-12a-redteam-gate.md` §10 proposes illustrative acceptance
numbers from general red-team practice (e.g. "ASR < 20% on indirect/
poisoning scenarios," "FPR < 5% on benign queries," "provenance enforcement
blocks >= 80% of unauthorized sources," "latency overhead < 50ms"). These are
preserved here **only as external reference points for interpreting results
after Phase 12E actually runs**, not as this project's own pre-committed
acceptance thresholds. See `docs/modernization-final-plan.md` §3 for the
full rationale (`AGENT_RULES.md` rule 3 and this project's consistent
practice of never fabricating or pre-committing to a benchmark number ahead
of a real run). Whatever Phase 12E actually measures will be reported as-is,
including if it is worse than these reference numbers.

## 7. Next Steps

- Phase 12D: author the v2 corpus against the category matrix in §4, with
  dev/validation/holdout splits per `ADR-003-v2-benchmark.md`.
- Phase 12E: run the ablation/evaluation harness and populate this
  document's residual-risk rows with actual measured numbers (replacing
  "documented as a known residual risk" with a measured exposure rate,
  where the metric makes that possible).
