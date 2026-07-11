**Markdown Review: Upgrading the Internship Thesis Project on RAG/LLM Guardrails (2026 Perspective)**

### 1. Current Threat Landscape
**Most relevant risks for enterprise RAG apps (2025–2026)**:
- **Indirect Prompt Injection & RAG Poisoning/Context Manipulation**: Attackers inject malicious instructions into documents, emails, or knowledge bases that RAG retrieves. Even a few poisoned chunks can achieve high success rates (e.g., 90% ASR with minimal injections). Real-world examples include hidden instructions in emails leading to data exfiltration in enterprise copilots.
- **Sensitive Information Disclosure & Output Leakage**: LLMs leak PII, proprietary data, or system prompts via retrieval or generation. RAG exacerbates this by surfacing internal docs.
- **Data Poisoning (training/fine-tuning/retrieval)**: Poisoned embeddings or documents corrupt retrieval and responses. Supply chain risks in datasets/models are rising.
- **Vector/Embedding Weaknesses**: Adversarial embeddings, poisoning of vector stores, and poor chunking/provenance leading to irrelevant or malicious retrieval.
- **Direct Prompt Injection, Agent/Tool Misuse, Excessive Agency**: Still top concerns, especially in agentic workflows.
- **Hallucinations & Misinformation**: Persistent even with RAG; impacts trust and compliance.

**Focus for the project**: Prioritize indirect/RAG-specific attacks, data leakage, and poisoning—these are "forgotten attack surfaces" in many deployments and align perfectly with the thesis title. Direct injection is well-covered already but remains foundational. Avoid over-focusing on model training poisoning (hard without real fine-tuning).

The landscape shows prompt injection remains #1 in OWASP, but RAG introduces unique ingestion/retrieval vectors that regex guards alone cannot fully address.

### 2. Framework Mapping
- **OWASP LLM Top 10 2025**: Core reference. LLM01: Prompt Injection (direct/indirect), LLM02: Sensitive Information Disclosure, LLM04/related: Data & Model Poisoning, LLM08: Vector and Embedding Weaknesses, plus Supply Chain, Improper Output Handling, Excessive Agency. Your current guards map well to input/output/RAG layers but need strengthening for retrieval poisoning and provenance.
- **OWASP LLMSVS** (if relevant): Complements with secure development practices for LLM apps.
- **NIST AI RMF**: Governance-focused (Map, Measure, Manage, Govern). Use for risk assessment, documentation, and thesis structure—emphasize measurable controls and human oversight. Great for academic defensibility.
- **MITRE ATLAS**: Adversarial tactics/techniques (e.g., RAG Poisoning, Prompt Injection variants, AI Supply Chain Compromise). Excellent for mapping red-team tests and adversary emulation. Complements OWASP by providing attacker perspectives.

**Recommendation**: Explicitly map your v2 guards/evaluation to these in the LaTeX report for strong academic and practical value.

### 3. Recommended Upgrade Directions
Ranked by **impact** (security improvement, realism, thesis value) vs. **feasibility** (2 students, laptops, 3-6 weeks, no heavy compute):

1. **Semantic Guard / LLM-as-Judge (High impact, Medium feasibility)**: Replace/augment regex with lightweight LLM calls (e.g., local small model like Phi-3 or API with strict prompting) for context relevance, groundedness, and malice detection. Add RAG Triad evaluation. High realism boost.
2. **Real RAG Retrieval + Vector DB (High impact, Medium-High feasibility)**: Use Chroma, FAISS, or LanceDB (lightweight, local). Implement hybrid search (dense + sparse). Synthetic or public enterprise-like docs. Critical for demonstrating RAG-specific guards.
3. **Context Provenance / Trust Scoring (High impact, Medium feasibility)**: Add metadata tracking (source, timestamp, trust score) and filter low-trust chunks. Simple rule + embedding similarity scoring.
4. **Adversarial Evaluation / Ablation Study (High impact, High feasibility)**: Expand 40-prompt benchmark with automated poisoning scripts and metrics (ASR, FPR, latency). Compare regex vs. semantic guards. Strong academic contribution.
5. **DLP/PII Detection (Medium-High impact, High feasibility)**: Enhance Output/Input with regex + lightweight entity recognition (e.g., presidio or spaCy) for realistic leakage prevention.
6. **Dashboard/Demo (Medium impact, High feasibility)**: Streamlit/Gradio UI showing guard decisions, provenance, and attack simulations. Great for defense/presentation.
7. **Agent/Tool Security (Medium impact, Lower feasibility)**: Only if time; add mock tools and misuse guards. Risk of scope creep.

**Vector DB / Embedding store** is foundational once you add real retrieval.

### 4. What NOT to Do
- **Fine-tune or train real models**: Too resource-heavy, hard to defend academically without massive datasets/compute, and distracts from guardrail focus. Stick to offline/mock or small local models.
- **Claim "solves" prompt injection**: Be critical—emphasize layered defenses reduce risk but do not eliminate it (per OWASP).
- **Real enterprise data or production-scale**: Violates synthetic-only principle; use public datasets (e.g., synthetic enterprise docs) or augmented clean benchmarks.
- **Complex agentic/multi-agent systems**: Scope creep; keep single-turn or simple chat for feasibility.
- **Heavy cloud dependencies or paid APIs in core eval**: Use local/offline where possible for reproducibility on laptops.
- **Pure literature expansion without new implementation**: The project already has evidence; upgrades must show measurable improvements via ablation.

Avoid anything that looks like a "toy regex demo" by adding semantic components and real retrieval, but stay grounded—overclaiming robustness is a common thesis pitfall.

### 5. Final Recommended Scope ("v2" in 3–6 Weeks)
- **Core**: Implement lightweight real RAG pipeline (FAISS/Chroma + hybrid retrieval) with synthetic enterprise corpus. Upgrade guards to hybrid (regex + semantic LLM judge for key decisions: malice, relevance, leakage).
- **Security Enhancements**: Provenance/trust scoring for chunks; enhanced DLP in output; RAG-specific poisoning detection (e.g., anomaly in embeddings or content).
- **Evaluation**: Expanded adversarial suite (poisoned datasets, indirect injections); ablation study (baseline vs. regex vs. hybrid guards); metrics aligned with OWASP/NIST (ASR, groundedness, leakage rate).
- **Demo/Gov**: Interactive dashboard + updated threat model mapping to OWASP/MIRE ATLAS/NIST.
- **Documentation**: Update LaTeX with new experiments, limitations (heuristic + lightweight LLM), and future work (e.g., full agentic).

This keeps it laptop-feasible (16GB RAM sufficient for small vectors/local models), academically strong (empirical ablation + framework mapping), and practically valuable (demonstrates production-relevant RAG security). Total: Realistic evolution from current scaffold without architecture overhaul.

### 6. References
- **OWASP LLM Top 10 2025** (genai.owasp.org/llm-top-10/): Primary vulnerability taxonomy; map your guards directly.
- **MITRE ATLAS** (atlas.mitre.org): For adversarial techniques like RAG Poisoning—use for red-teaming.
- **NIST AI RMF**: Governance backbone for risk management sections.
- Papers/Articles: "PoisonedRAG" and RAG security studies (e.g., via arXiv searches) for poisoning attacks; enterprise RAG guides (e.g., Witness.ai, Christian Schneider's blog) for practical architecture.
- Additional: Vectara hallucination leaderboard, Promptfoo for eval tools.

These sources ground the upgrades in 2025–2026 realities, making the thesis stand out as current and defensible. Focus on honest limitations and layered mitigations for credibility. Good luck—this has strong potential!