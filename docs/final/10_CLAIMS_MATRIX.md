# Claims Matrix

**Identities:** base `93ad09d…` · Phase 12F HEAD `409e5f3…`  
**Rule:** If a claim is not allowed, do not use the prohibited wording.

| Claim | Allowed | Evidence | Qualification | Prohibited wording |
|---|---|---|---|---|
| Lab guardrail gateway + RAG path implemented | Yes | Code on cited SHAs | Academic PoC | “Production-ready security product” |
| C0–C7 fixed ablation registry | Yes | CONFIG_REGISTRY | Config hashes bind identity | “Arbitrary online policy packs validated” |
| Benchmark v2 synthetic FINAL freeze | Yes | FINAL manifest + freeze verify | Lab data only | “Real enterprise traffic benchmark” |
| Ordinary path cannot load holdout | Yes | SUPPORTED_SPLITS design | — | “Holdout is just another split flag” |
| Holdout requires external authorization | Yes | Runner/analyzer holdout path | Procedural gate | “Cryptographically unforgeable holdout token” |
| Phase 12F full suite 1011/0/4 | Yes | Correction package evidence | Integrity/tooling metric | “Guards block 1011 attack classes” |
| Release readiness PASS | Yes | 12F packages | Byte-level + focused | “Security effectiveness certified” |
| Claude/Codex/Grok R2 PASS | Yes | Cross-review packages | Scope-limited reviews | “Independent red-team of production” |
| Gemini final audit PASS | Yes | Audit record | Claims/methodology; not local runner | “Gemini executed our pytest suite” |
| No Critical/Major at R2 close | Yes | Review reports | As reported | “Zero residual risk worldwide” |
| Mock evaluation is deterministic | Yes | Design | Not real-LLM variance | “Equals GPT-4/Claude behavior” |
| Latency non-reportable under L2 | Yes | Analyzer policy | p50/p95 null | “p95 latency is X ms” |
| No ABR/macro/F1/p-value metrics | Yes | Analyzer claims_control | — | Publishing ABR/macro/F1/p-values as metrics |
| Exploratory holdout exists historically | Yes | Historical execution | Diagnostic only | “Final Phase 12E.4 PASS” |
| Governance-valid holdout complete | **No** | — | Missing pre-auth adjudication | Any final holdout PASS claim |
| Production security effectiveness | **No** | — | Out of scope | “Protects enterprise production LLMs” |
| Old holdout validates post-change code | **No** | New-candidate rule | — | “Same holdout still proves the new build” |
| Absolute absence of all FS races / admin attacks | **No** | Trusted-maintainer model | Use NOT_VERIFIABLE | “Proven immune to all local adversaries” |
| Phase 12G PASS | **No** | This docs package | Docs only | Claiming Phase 12G PASS from documentation alone |
