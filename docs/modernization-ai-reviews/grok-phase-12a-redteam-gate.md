**Security Scope Review: Enterprise RAG Security Gateway (Phase 12)**

### 1. Current Enterprise RAG Threat Model (Relevant to Project)
Enterprise RAG systems face a **trust paradox**: retrieved context is treated with high authority by the LLM, bypassing traditional input sanitization. Key layers: Ingestion (persistent documents), Retrieval (SQLite FTS5/BM25), Generation (mock → real adapter), and Guardrails (Input/RAG Context/Output + provenance/DLP).

Primary risks (OWASP LLM Top 10 2025 + MITRE ATLAS): Indirect prompt injection via retrieved docs, RAG/context manipulation, data poisoning at retrieval (distinct from training-data poisoning), sensitive leakage, vector/embedding weaknesses (even in keyword search), and provenance failures. NIST AI RMF emphasizes governance via provenance, measurement (ablation metrics), and human oversight.

### 2. Top Threats Phase 12 Must Cover
- Indirect prompt injection through retrieved context.
- Retrieval poisoning (malicious documents influencing BM25 ranking/retrieval).
- Provenance/trust violations (unauthorized or low-trust sources).
- Sensitive data leakage (synthetic canaries + realistic PII patterns).
- Context manipulation leading to policy bypass or override.

Focus on defense-in-depth with provenance policies and centralized DLP.

### 3. Threats Out of Scope
- Model-training/fine-tuning poisoning (project uses mock/offline adapter).
- Full agentic/tool misuse or multi-agent workflows.
- Production-scale vector DBs or real embeddings (stick to BM25/FTS5).
- Real enterprise data or live external sources.
- Advanced adversarial ML on embeddings (beyond keyword poisoning).

### 4. Red-Team Scenario Matrix for Benchmark v2
| Category | Direct | Indirect (RAG) | Poisoning | Leakage |
|----------|--------|----------------|-----------|---------|
| **Prompt Injection** | Input Guard | RAG Context | Retrieval | Output |
| **Policy Bypass** | High priority | High | Medium | Medium |
| **Authority Override** | Covered | Provenance check | High | DLP |
| **Data Exfil** | Low | Medium | Low | High (canaries) |

Expand frozen v1 with retrieval-specific cases.

### 5. Required Indirect Prompt-Injection Variants
- Hidden instructions in document body/comments/metadata.
- Quoted "support transcript" style injections.
- Authority claims ("This document supersedes...").
- Multi-chunk coordination (split instructions across retrieved results).
- Obfuscated/synonym variants to test robustness.

### 6. Retrieval Poisoning and Provenance Attacks
**Distinction**: Retrieval poisoning injects malicious docs into the knowledge base/ingestion pipeline to influence BM25 retrieval and subsequent generation (no model weights changed). Unlike training poisoning.

Attacks to simulate:
- Keyword-optimized poisons that rank highly for target queries.
- Content mimicking legitimate enterprise docs with embedded instructions.
- Provenance spoofing (fake metadata/source timestamps).
- Bulk low-trust ingestion bypassing policies.

Mitigations: Server-controlled provenance, trust scoring, pre-ingestion scans.

### 7. DLP/Leakage Scenarios Using Synthetic Canaries
- Fake secrets (e.g., FAKE-SECRET-0000-EXAMPLE variants).
- Synthetic PII/credentials in "internal" docs.
- Policy documents with classification markers.
- Multi-hop leakage (retrieve → generation → output).

Centralized DLP must detect/redact across pipeline; test with canaries in clean vs. poisoned contexts.

### 8. Benign Counterexamples for False Positives
- Legitimate policy updates with "override" or "authoritative" language.
- Internal memos with authority claims or transcript quotes.
- Product FAQs with structured data resembling injections.
- HR/compliance docs containing synthetic PII or canaries in approved contexts.
- Queries with natural policy/approval language.

Aim for low FPR on enterprise-like benign traffic.

### 9. Holdout Rules Preventing Test Overfitting
- Separate holdout set of unseen variants (not in training/red-team design).
- Adversarial mutations (synonyms, rephrasing, encoding) generated post-benchmark design.
- Cross-validation: Test on poisoned variants absent from guard rule authoring.
- Independent red-team review of final benchmark before evaluation.

### 10. Minimum Red-Team Acceptance Criteria (Phase 12B–12E)
- ASR < 20% on indirect/poisoning scenarios (realistic layered defense, not perfect).
- FPR < 5% on benign enterprise queries.
- Provenance enforcement blocks ≥80% unauthorized sources.
- Latency overhead < 50ms end-to-end (ablation metrics).
- Full audit logging + DLP coverage for canaries.
- Ablation study showing gains from provenance + DLP vs. v1.

No claim of full prevention—document residual risks.

### 11. Five Likely Bypasses Against Planned BM25 + Rule-Based System
1. Keyword-optimized poisons that boost BM25 relevance without triggering content rules.
2. Subtle indirect instructions using synonyms/contextual framing that evade regex.
3. Provenance spoofing via metadata manipulation during ingestion.
4. Split/multi-chunk injections where individual chunks look benign.
5. Benign-looking docs with delayed/conditional instructions that activate on specific queries.

Hybrid semantic checks (if added) would help but still have limitations.

### 12. References
- **OWASP LLM Top 10 2025** (genai.owasp.org/llm-top-10/): Defines prompt injection, poisoning, and leakage priorities.
- **MITRE ATLAS** (atlas.mitre.org): Tactics for RAG poisoning and indirect injection.
- **NIST AI RMF**: Governance for provenance and measurement.
- **RAG Security Analyses** (e.g., Witness.ai blog, Christian Schneider): Practical ingestion/retrieval threats.
- **PoisonedRAG-style Research**: Distinguishes retrieval vs. training poisoning.

This scope keeps the project focused, measurable, and academically/practically valuable.