# Agent Rules

Rules for any AI coding agent (Claude Code or otherwise) working in this repository. These apply to every phase, not just Phase 0. If a rule and a user instruction conflict, stop and ask rather than guessing.

## 1. No scope creep

- Only implement what the current approved phase (see `TASK_BOARD.md`) calls for.
- Do not add features, frameworks, or infrastructure "while you're in there."
- If a task seems to require going beyond the current phase, stop and ask before proceeding.

## 2. No fake citations

- Never invent papers, authors, URLs, or standards references.
- Every citation in `docs/research/` or `report-latex/references.bib` must correspond to a real, verifiable source the team has actually reviewed.
- If unsure whether a source is real, flag it instead of guessing.

## 3. No fake benchmarks or results

- Never fabricate evaluation numbers, detection rates, latency figures, or comparison tables.
- Only report numbers produced by an actual test/evaluation run in this repository, with the run reproducible from checked-in code/data.
- Placeholder numbers must be clearly marked `TBD` / `[chưa có số liệu]`, never plausible-looking fake values.

## 4. No paid API calls without approval

- Do not call any paid/metered LLM or third-party API without explicit user approval for that specific call or batch of calls.
- Prefer dry-run / mock modes when developing and testing gateway logic.

## 5. No real PII or real secrets

- All datasets, test prompts, and documents must be synthetic.
- Never commit real API keys, credentials, customer data, or private/internal documents.
- `.env` files with real secrets must never be committed; only `.env.example` with placeholder values is tracked.

## 6. No destructive commands

- Do not run commands that delete data, force-push, rewrite git history, or drop databases without explicit user confirmation.
- Prefer reversible actions; ask before anything hard to undo.

## 7. No offensive payloads targeting real systems

- Attack prompts / red-team payloads in `redteam/` and `datasets/` must only target this project's own lab-scale demo system.
- Never craft payloads intended for use against third-party production systems.

## 8. Honest terminology

- Use "proof-of-concept", "MVP", or "lab-scale" when describing this system.
- Never describe the system as "production-ready", "enterprise-grade" (in the marketing sense), or "fully secure."

## 9. Every change must include

When making a non-trivial change (code, docs, or config), the agent should be able to state:

1. **What changed** — concrete summary of the diff.
2. **Why** — which phase/task this serves, per `TASK_BOARD.md` / `PROJECT_PLAN.md`.
3. **How to test** — commands or steps to verify the change works.
4. **Evidence** — test output, logs, or generated artifacts proving it works.
5. **Risks** — what could break, what's not covered, what's still TBD.

## 10. Documentation is not optional

- Every phase must produce documentation and evidence (per `PROJECT_PLAN.md` §7 and `TASK_BOARD.md`).
- Undocumented "invisible" work is treated as incomplete.

## 11. Ask before installing heavy dependencies

- Confirm with the user before adding large frameworks, ML libraries, or anything that meaningfully changes install size/time or introduces licensing concerns.

## 12. Stop at phase boundaries

- Phase 0 stops after scaffolding — no application code.
- Do not silently continue into the next phase's implementation work without a new go-ahead.
