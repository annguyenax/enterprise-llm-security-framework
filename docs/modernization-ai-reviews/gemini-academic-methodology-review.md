Here is an academic advisor’s evaluation and upgrade plan for your Information Security internship thesis.

Your current project demonstrates good software engineering practices (FastAPI Gateway, layered architecture, baseline comparison), which is a great start. However, achieving 40/40 on a custom 40-case benchmark using a mock LLM makes the project look like a "toy system" that has been overfitted to pass its own test. To elevate this to a strong academic level, we need to shift the focus from *building a flawless guardrail* to *rigorously evaluating a security architecture*.

Here is a concrete, realistic upgrade path for a 2-student team.

### 1. Academic Value Assessment

**What is already strong?**

* **Architectural design:** The multi-layer approach (Input Guard, RAG Guard, Output Guard) reflects modern enterprise security paradigms (defense-in-depth).
* **Engineering discipline:** Using FastAPI as a middleware gateway is exactly how real-world proxies (like Lakera or NeMo) are deployed.
* **Honesty:** Acknowledging the mock limitations up front shows academic integrity.

**What is weak or may be criticized?**

* **The 40/40 result:** In security research, a 100% block rate on a tiny, self-created dataset usually implies the rules were hardcoded to catch those specific 40 prompts (overfitting).
* **Lack of False Positives (Usability test):** Security is a trade-off. If your rules block everything, the system is secure but useless. You haven't proven that legitimate user queries can pass through.
* **No actual Generative AI behavior:** Mock LLMs return deterministic strings. Real LLMs are stochastic—they might partially obey an injection, leak data in unexpected formats, or hallucinate. Rule-based guards often fail when an LLM obfuscates the output.

**Which claims are risky?**

* Claiming you "protect RAG systems" when you aren't using real retrieval (Vector DB) or real generation. You have currently built a standard web API filter, not specifically an LLM guardrail.

---

### 2. Research Questions

To make the thesis academically strong, frame it around answering specific security questions rather than just showcasing a tool.

* **RQ1 (Ablation):** How much does each guardrail layer (Input, RAG, Output) contribute to the overall mitigation of Indirect Prompt Injection in a simulated environment?
* **RQ2 (Trade-off):** What is the trade-off between security strictness (True Positive mitigation rate) and system usability (False Positive rate on benign queries) when using rule-based guardrails?
* **RQ3 (Data Poisoning):** How effectively can rule-based output sanitization (Data Loss Prevention / DLP) prevent sensitive data leakage when the retrieval context is successfully poisoned?
* **RQ4 (Performance):** What is the latency overhead introduced by a multi-layer FastAPI security gateway in a RAG pipeline?

---

### 3. Methodology Upgrade

Shift your methodology from "Prove the system works" to "Test the system's limits."

* **Dataset Design:** Expand from 40 cases to at least 200 cases. Crucially, mix **100 malicious cases** (direct injections, poisoned documents, jailbreaks) with **100 benign cases** (normal user questions, edge-case safe questions).
* **Red-team Benchmark:** Introduce basic obfuscation. If your rule blocks "Ignore previous instructions", test it against "Ignore the prior guidelines" or base64 encoded payloads to prove the limitations of rule-based systems.
* **Evaluation Metrics:**
* **True Positive Rate (TPR):** % of attacks successfully blocked.
* **False Positive Rate (FPR):** % of normal queries incorrectly blocked.
* **Latency Overhead:** Measured in milliseconds per request.


* **Ablation Study:** Run your benchmark 5 times:
1. Baseline (No guards)
2. Input Guard ONLY
3. RAG Guard ONLY
4. Output Guard ONLY
5. Full System (All 3)


* **Baseline Comparison:** Show how the baseline fails (e.g., leaks data) vs. how the guarded system reacts.
* **Limitation Section:** Explicitly state that rule-based systems are brittle against semantic attacks (paraphrasing) and that future work requires ML-based classifiers (e.g., embeddings-based detection).

---

### 4. Suggested Final Thesis Contribution

For a Vietnamese university report, frame your contribution defensively and academically:

*"Nghiên cứu này đóng góp một khung kiến trúc Security Gateway đa lớp cho hệ thống RAG và đề xuất phương pháp luận đánh giá (Ablation Study). Thay vì cung cấp một giải pháp bảo mật tuyệt đối, dự án tập trung vào việc định lượng hiệu quả và giới hạn của các cơ chế luật (rule-based) trong việc ngăn chặn Prompt Injection và rò rỉ dữ liệu, đồng thời phân tích độ trễ và tỷ lệ cảnh báo giả (False Positives)."*

(This research contributes a multi-layer Security Gateway architecture for RAG systems and proposes an evaluation methodology. Rather than providing an absolute security solution, the project focuses on quantifying the effectiveness and limitations of rule-based mechanisms...)

---

### 5. Minimum Upgrade Required (Must Do)

To ensure the project looks like a serious Information Security thesis:

1. **Integrate a local Vector Database:** Replace the mock retrieval with ChromaDB or FAISS. It takes ~2 hours to set up but proves you understand RAG architecture.
2. **Integrate a real LLM via API or Local:** Connect your pipeline to a free/cheap API (Google Gemini API, OpenAI) OR run a local model via Ollama (e.g., `llama3:8b`). This introduces real LLM stochasticity.
3. **Introduce the Benign Dataset:** You *must* test normal queries to measure False Positives. A security system with no False Positive metric is academically incomplete.
4. **Perform the Ablation Study:** Deactivating layers to see which one caught the attack is the easiest way to add deep academic rigor.

---

### 6. High-Value Optional Upgrade (If Time Permits)

* **Hybrid Guardrail (Regex + ML):** Add a very lightweight, pre-trained ML model to your gateway. For example, use the HuggingFace `transformers` library to load a small, pre-trained toxicity or injection classifier (e.g., `protectai/deberta-v3-base-prompt-injection`). Compare the Rule-based Guard vs. the ML-based Guard.
* **LLM-as-a-Judge Evaluation:** Instead of using exact string matching to see if an attack succeeded, write a script where a separate LLM prompt evaluates the output: *"Did the AI leak the secret password? Yes/No."*

---

### 7. Report Structure Update

Modernize your chapters to reflect this rigorous approach:

**Chương 2: Cơ sở lý thuyết (Theoretical Foundation)**

* Add a section on *Defense-in-Depth for LLMs*.
* Add a section on *Evaluation Methodologies in AI Security* (explaining True/False Positives in AI, Ablation studies).

**Chương 3: Kiến trúc và Phương pháp luận (Architecture & Methodology)**

* Detail the FastAPI Gateway and the real VectorDB/LLM integration.
* Explain the *Ruleset Design* (what regex/keywords are used).
* **New Section:** *Thiết kế tập dữ liệu và Kịch bản đánh giá* (Dataset Design and Evaluation Scenarios) - Detail the 100 malicious and 100 benign prompts.

**Chương 4: Đánh giá và Bàn luận (Evaluation & Discussion)**

* **4.1:** Baseline vs. Guarded Performance (Overall metrics).
* **4.2:** Phân tích Ablation Study (Which layer did the heavy lifting?).
* **4.3:** Đánh giá Tỷ lệ cảnh báo giả (False Positives on benign user queries).
* **4.4:** Đánh giá Hiệu năng (Latency overhead in milliseconds).
* **4.5:** Hạn chế của hệ thống Rule-based (Why attackers can still bypass it).