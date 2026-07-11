This report provides a structured overview of the security landscape for Large Language Models (LLMs) deployed within enterprise environments. It focuses on vulnerabilities introduced through Retrieval-Augmented Generation (RAG) pipelines and autonomous agents, serving as the foundational research for our MVP.



\## Summary



As LLMs transition from static chatbots to autonomous agents capable of interacting with external APIs and internal databases, the enterprise attack surface has expanded significantly. This research summary evaluates current defense mechanisms against critical threats like prompt injection, jailbreaking, and RAG data poisoning. By synthesizing the OWASP standards, enterprise-grade tooling (e.g., NeMo Guardrails, Lakera Guard, deepteam), and recent academic findings, this report outlines a defense-in-depth strategy necessary for building a secure, resilient MVP.



\---



\## Key Concepts



\* \*\*Large Language Models in enterprise systems:\*\* The integration of foundational models into core business workflows, shifting from simple text generation to executing multi-step operations.

\* \*\*Retrieval-Augmented Generation (RAG):\*\* Enhancing an LLM's accuracy by dynamically retrieving up-to-date, domain-specific information from external databases. While it reduces hallucinations, it introduces significant data ingestion risks.

\* \*\*AI Agents and tool usage:\*\* Autonomous entities that use LLMs as reasoning engines to execute code, query databases, or trigger actions. They are highly susceptible to "confused deputy" attacks if instructions are manipulated.

\* \*\*Runtime guardrails:\*\* Programmable, low-latency security layers that sit between the user and the model to validate inputs (blocking injections) and sanitize outputs (preventing data leakage).

\* \*\*Red teaming and evaluation metrics:\*\* The continuous, adversarial testing of AI systems using automated agents to simulate complex, multi-turn attacks and measure the system's resilience.



\---



\## Threats



These vulnerabilities align with the industry-standard OWASP Top 10 for LLM Applications:



1\. \*\*Prompt Injection:\*\* Direct manipulation where user input deliberately overrides the system prompt to alter the model's intended behavior.

2\. \*\*Indirect Prompt Injection:\*\* Occurs when an LLM processes external, untrusted content (e.g., parsing a compromised website or uploaded document) containing hidden malicious instructions that hijack the model.

3\. \*\*Jailbreaking:\*\* Sophisticated techniques—often utilizing roleplay, encoding, or logical puzzles—designed to bypass the model's intrinsic safety alignment and content filters.

4\. \*\*Data Poisoning in RAG:\*\* The covert injection of malicious or biased documents into the retrieval vector database. When retrieved, these corrupted texts force the LLM to generate attacker-controlled responses.

5\. \*\*Sensitive Information Disclosure:\*\* The unintended exposure of proprietary code, system instructions, or Personally Identifiable Information (PII) during interactions.

6\. \*\*Insecure Output Handling:\*\* Vulnerabilities that arise when downstream enterprise systems (like a web browser or SQL database) blindly execute LLM-generated output without sufficient validation, leading to Cross-Site Scripting (XSS) or remote code execution.



\---



\## Existing Tools and Frameworks



\* \*\*NVIDIA NeMo Guardrails:\*\* An open-source framework utilizing the `Colang` domain-specific language. It enforces highly programmable topical, safety, and dialogue constraints on AI agents, allowing developers to define exact conversational boundaries.

\* \*\*Lakera Guard:\*\* A commercial security layer optimized for high-speed (<200ms) inference. It uses multiple classifiers to detect prompt injections and PII leaks before they reach the underlying LLM, making it ideal for low-latency, customer-facing applications.

\* \*\*deepteam:\*\* An open-source multi-agent red teaming framework that runs locally. It simulates dynamic adversarial attacks (e.g., multi-turn crescendo jailbreaks and single-turn injections) to evaluate LLM defenses without exposing proprietary prompts to third parties.

\* \*\*garak (Generative AI Red-teaming \& Assessment Kit):\*\* An automated vulnerability scanner that probes LLMs for known weaknesses, prompt leakages, and safety bypasses, functioning much like traditional penetration testing tools.

\* \*\*Microsoft PyRIT (Python Risk Identification Tool):\*\* An enterprise-grade automation framework designed by Microsoft to scale the identification of security and privacy risks in generative AI systems.



\---



\## Evaluation Metrics



To rigorously assess our security posture, we will track:



| Metric | Description |

| --- | --- |

| \*\*Jailbreak Success Rate (JSR)\*\* | The percentage of adversarial prompts that successfully bypass the model's safeguards. |

| \*\*False Positive Rate\*\* | How often benign, legitimate user queries are incorrectly blocked by the guardrails. |

| \*\*Latency Overhead\*\* | The additional processing time (measured in milliseconds) introduced by runtime security checks. |

| \*\*LLM-as-a-Judge\*\* | Using an isolated, specialized LLM to automatically score the primary model's outputs for toxicity, bias, and data leakage. |



\---



\## How This Applies to Our MVP



For this university internship project, our MVP must implement a defense-in-depth architecture. We cannot rely solely on the intrinsic safety of the foundational model.



We will deploy a lightweight runtime guardrail (drawing from the methodologies of NeMo Guardrails) to sanitize user inputs and model outputs. Because our application relies on RAG, we must also implement strict data ingestion validation to mitigate the risk of knowledge database poisoning. Finally, we will use tools like \*\*deepteam\*\* and \*\*PyRIT\*\* to continuously subject our local MVP to automated, multi-turn red teaming, ensuring our prompt injection defenses hold up under realistic adversarial conditions.



\---



\## References



1\. \*\*OWASP Foundation (2025).\*\* \*OWASP Top 10 for Large Language Model Applications.\* URL: \[https://owasp.org/www-project-top-10-for-large-language-model-applications/](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

\* \*\*Why it matters:\*\* Provides the definitive industry taxonomy for categorizing and prioritizing LLM vulnerabilities.





2\. \*\*OWASP Foundation (2024).\*\* \*OWASP Large Language Model Security Verification Standard (LLMSVS).\* URL: \[https://owasp.org/www-project-llm-verification-standard/](https://owasp.org/www-project-llm-verification-standard/)

\* \*\*Why it matters:\*\* Offers an actionable, leveled checklist for designing, auditing, and testing secure AI architectures in enterprise environments.





3\. \*\*NVIDIA (2024).\*\* \*NeMo Guardrails.\* URL: \[https://github.com/NVIDIA/NeMo-Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)

\* \*\*Why it matters:\*\* Demonstrates how to enforce programmable, dialogue-based boundary enforcement for complex multi-agent systems.





4\. \*\*Lakera (2024).\*\* \*Lakera Guard.\* URL: \[https://www.lakera.ai/](https://www.lakera.ai/)

\* \*\*Why it matters:\*\* Highlights the commercial necessity of low-latency, production-grade injection detection to maintain user experience.





5\. \*\*Confident AI (2024).\*\* \*deepteam: The LLM Red Teaming Framework.\* URL: \[https://github.com/confident-ai/deepteam](https://github.com/confident-ai/deepteam)

\* \*\*Why it matters:\*\* Provides a local, dynamic testing environment capable of executing multi-turn adversarial loops and evaluating failures via LLM-as-a-Judge.





6\. \*\*garak project (2024).\*\* \*garak: LLM vulnerability scanner.\* URL: \[https://github.com/leondz/garak](https://github.com/leondz/garak)

\* \*\*Why it matters:\*\* Offers essential automated probing to establish baseline security against known foundational model vulnerabilities.





7\. \*\*Microsoft (2024).\*\* \*Python Risk Identification Tool for generative AI (PyRIT).\* URL: \[https://github.com/Azure/PyRIT](https://github.com/Azure/PyRIT)

\* \*\*Why it matters:\*\* Represents the gold standard for scaling automated red-teaming and risk identification in enterprise AI pipelines.





8\. \*\*MDPI (2025).\*\* \*Prompt Injection Attacks in Large Language Models and AI Agent Systems: A Comprehensive Review of Vulnerabilities, Attack Vectors, and Defense Mechanisms.\* URL: \[https://www.mdpi.com/2078-2489/17/1/54](https://www.mdpi.com/2078-2489/17/1/54)

\* \*\*Why it matters:\*\* Provides a highly relevant academic synthesis of modern injection vectors, documenting how agents interacting with untrusted data suffer from confused deputy attacks.





9\. \*\*Wang, H. et al. (2026).\*\* \*PIDP-Attack: Combining Prompt Injection with Database Poisoning Attacks on Retrieval-Augmented Generation Systems.\* arXiv:2603.25164. URL: \[https://arxiv.org/abs/2603.25164](https://arxiv.org/abs/2603.25164)

\* \*\*Why it matters:\*\* Exposes a novel, compound attack methodology that merges prompt injection with RAG data poisoning, proving that single-layer defenses are insufficient.





10\. \*\*Zou, Y. et al. (2024).\*\* \*PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models.\* arXiv:2402.07867. URL: \[https://arxiv.org/abs/2402.07867](https://arxiv.org/abs/2402.07867)

\* \*\*Why it matters:\*\* A foundational academic paper demonstrating the mechanics of how injecting a few malicious texts into a knowledge base can entirely manipulate an LLM's generated response.

