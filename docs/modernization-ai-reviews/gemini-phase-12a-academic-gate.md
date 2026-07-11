Here is the formal academic methodology review for your thesis upgrade. This review treats Phase 0–11 and the V1 40/40 benchmark as a completed calibration phase. The focus is now on establishing empirical rigor for Phase 12+ to satisfy university evaluation standards.

---

### 1. Final Academic Contribution Statement

To align with standard Information Security undergraduate expectations, your final contribution statement should be framed around architectural design and empirical evaluation rather than absolute protection.

**Recommended Statement (Vietnamese context):**

> *"Nghiên cứu này đóng góp một kiến trúc Security Gateway đa lớp (Input, RAG Context, Output) tích hợp cơ chế kiểm soát nguồn gốc dữ liệu (provenance-aware) cho hệ thống Retrieval-Augmented Generation (RAG). Thay vì hướng đến một giải pháp bảo mật tuyệt đối, dự án cung cấp một phương pháp luận đánh giá thực nghiệm (Ablation Study) nhằm định lượng hiệu quả bảo vệ, giới hạn của các cơ chế nhận diện dựa trên luật (rule-based), độ trễ hệ thống và tỷ lệ cảnh báo giả (False Positives) trong quá trình ngăn chặn Prompt Injection và Rò rỉ dữ liệu."*

---

### 2. Precise Research Questions

Your thesis must answer specific, measurable questions. Base Chapter 4 on answering these four questions:

* **RQ1 (Efficacy):** To what extent does server-controlled data provenance and metadata-aware context filtering reduce the success rate of Indirect Prompt Injection (Data Poisoning) compared to a baseline RAG pipeline?
* **RQ2 (Trade-offs):** What is the trade-off between security strictness (True Positive mitigation rate) and system usability (False Positive rate on benign queries) across the individual guardrail layers?
* **RQ3 (Ablation/Layer Value):** In a defense-in-depth architecture, what is the proportional contribution of each security layer (Input, RAG, Output) to the overall system efficacy against a mixed-vector attack benchmark?
* **RQ4 (Performance Overhead):** What is the latency overhead (measured in milliseconds) introduced by the FastAPI multi-layer security gateway during an end-to-end retrieval and generation cycle?

---

### 3. Minimum Methodology Requirements

To graduate from a "toy demo" to an academic prototype, the following must be implemented:

1. **Dynamic Pipeline:** The system must transition from static, caller-supplied `context_chunks` to an actual retrieval mechanism (SQLite FTS5/BM25 is perfectly acceptable).
2. **Persistent Ingestion with Trust Boundaries:** Documents must be ingested into a persistent store with server-controlled `trust_level` metadata (e.g., `trusted_internal` vs. `untrusted_external`). The client must not dictate the trust level.
3. **Systematic Ablation Methodology:** The evaluation framework must automatically test the benchmark against 5 distinct configurations: Baseline (Guards Off), Input Only, RAG Guard Only, Output Only, and All Guards Active.

---

### 4. Required Benchmark V2 Split Design

The V1 benchmark (40 malicious cases) is now your development/calibration set. V2 must be your **blind test set** designed to measure usability alongside security.

**Target Size:** 100 cases (minimum).
**Required Split:**

* **50% Malicious (The "Attack" Set):**
* 20 Direct Injections (e.g., "Ignore previous instructions", roleplay, base64 obfuscation).
* 20 Indirect Injections/Poisoned Docs (e.g., payloads hidden in retrieved text designed to trigger data exfiltration).
* 10 Jailbreaks (e.g., hypothetical scenarios bypassing safety filters).


* **50% Benign (The "Usability" Set):**
* 25 Standard Enterprise Queries (e.g., "Summarize the Q3 financial report").
* 25 Edge-Case / "Trap" Queries (e.g., "How do I securely handle SQL injections in our code?" - This contains the word "injection" but is a legitimate query that should *not* be blocked).



---

### 5. Required Metrics

Your evaluation runner must calculate and output the following metrics for every ablation layer:

* **True Positive Rate (TPR):** The percentage of malicious prompts successfully blocked or sanitized.
* **False Positive Rate (FPR):** The percentage of benign prompts incorrectly blocked (this proves your system doesn't just block everything).
* **False Negative Rate (FNR):** The percentage of attacks that bypassed the guards.
* **Latency (ms):** Average time spent inside the security middleware (excluding LLM inference time).

---

### 6. Rules Preventing Benchmark Overfitting

To ensure academic integrity and defend against panel criticism:

1. **Rule of Separation:** Do not use V2 cases to write your regex or guardrail rules. Write the rules based on V1, then test against V2.
2. **Rule of Variance:** Ensure attack payloads in V2 use synonyms and varying syntax (e.g., instead of "Disregard all instructions", use "Abolish prior guidelines"). This exposes the fragility of rule-based systems.
3. **Rule of Freezing:** Once the evaluation runner starts for the final report, no rule modifications are permitted, even if the system performs poorly on a specific test case.

---

### 7. Claims That Must Not Appear in the Report

To maintain academic rigor, rigorously scrub the following from your manuscript:

* **"100% Security" / "Bulletproof":** Never claim the framework completely eliminates prompt injection.
* **"Production-Ready":** Frame it as a research prototype or Proof of Concept (PoC).
* **Semantic Understanding:** Unless you implement an ML model (like DeBERTa) or an LLM-as-a-judge, do not claim the system "understands" the context. It matches patterns and evaluates rules.
* **Generalization:** Do not claim the results apply to GPT-4 or Claude 3.5 unless specifically tested. Keep claims scoped to the simulated environment and local/mock constraints.

---

### 8. Acceptance Criteria for Phase 12A–12E

* **12A (FTS5 Retrieval):** System ingests documents into SQLite, generates FTS5 indexes, and returns ranked chunks based on keyword queries.
* **12B (Persistent Ingestion & Provenance):** Database schema enforces `document_id`, `content`, `source`, and `trust_level`. The RAG guard successfully filters or flags chunks based on this metadata before sending them to the LLM.
* **12C (Centralized DLP):** The Output Guard successfully intercepts and masks configured PII/secrets (e.g., converting credit cards to `[REDACTED]`) from the mock generation output.
* **12D (Benchmark V2):** A JSON/YAML file containing the 100-case split (50 Malicious, 50 Benign) is created and documented.
* **12E (Evaluation Runner):** A single script executes the entire V2 benchmark across all ablation configurations and outputs a consolidated CSV/Markdown table of TPR, FPR, and Latency.

---

### 9. Recommended Updates to Report Structure

**Chương 2: Cơ sở lý thuyết (Methodology/Background)**

* Define the formal difference between Direct Prompt Injection and Indirect Prompt Injection (Data Poisoning).
* Define RAG architecture mathematically or via flowchart (Query -> Vector/BM25 -> Context -> LLM).
* Introduce the concepts of True Positives, False Positives, and Defense-in-Depth in the context of ML systems.

**Chương 3: Kiến trúc và Triển khai (Architecture & Implementation)**

* Detail the FastAPI gateway logic.
* Document the SQLite FTS5 ingestion schema and the provenance metadata model.
* Explain the design methodology of the V2 Benchmark (why edge-case benign queries were included).

**Chương 4: Đánh giá và Thảo luận (Evaluation & Discussion)**

* **Stop celebrating 40/40.**
* Present the Ablation Matrix (Table showing TPR/FPR for Baseline, Input, RAG, Output, All).
* Analyze the False Positives: Why did the system block legitimate queries?
* Analyze the False Negatives: How did obfuscated attacks bypass the rule-based regex?
* Present Latency graphs.
* Conclude with the fundamental limitations of static rule-based security in stochastic systems.

---

### 10. Academic Stop Condition

Your thesis is academically sound and ready for defense when:

1. SQLite FTS5 is handling retrieval.
2. The V2 Benchmark runs end-to-end via an automated script.
3. You have a documented Ablation matrix showing the TPR, FPR, and Latency for all guard layers.
4. Chapter 4 contains a rigorous analysis of *why* the rules failed on certain V2 cases (False Negatives) and *why* it blocked safe queries (False Positives).

**Do not delay graduation attempting to integrate vector databases, sentence embeddings, or local LLMs if time is short.** The rigorous evaluation of a basic architecture (FTS5 + mock LLM) is worth vastly more academic credit than a poorly evaluated complex architecture.