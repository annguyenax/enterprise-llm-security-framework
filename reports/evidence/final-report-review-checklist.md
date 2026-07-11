# Final Report Review Checklist

Status: LaTeX content integrated; static checks completed; PDF compilation not
yet verified because no TeX toolchain is installed in the current environment.

Phase 11 preflight result: unescaped braces and non-comment environment counts
are balanced; all static references resolve; no duplicate label exists; all
five citation keys exist in `refs.bib`; and no Unicode replacement character or
emoji was found. The three expected PNG files are absent. Visual overflow,
font rendering, page breaks, and compiler warnings cannot be confirmed without
a PDF build.

## LaTeX Compile Checklist

- [x] Official title verified unchanged in `report-latex-template/thesis.sty`.
- [x] Chapter include order in `main.tex` preserved.
- [x] Static brace scan completed without imbalance.
- [x] All five cited bibliography keys exist in `refs.bib`.
- [ ] Install or select a reviewed TeX Live/MiKTeX/Overleaf environment.
- [ ] Compile from `report-latex-template/`:

```powershell
latexmk -pdf main.tex
```

Alternative manual sequence:

```powershell
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

- [ ] Resolve every LaTeX error and undefined reference.
- [ ] Review overfull/underfull box warnings and page breaks.
- [ ] Inspect `pages/group-work-plan.tex` longtable and the appendix figure
  specification table for overflow at normal PDF zoom.
- [ ] Confirm table of contents, list of tables and list of figures update.
- [ ] Confirm Vietnamese characters and fonts render correctly.

Current environment note: `latexmk`, `pdflatex`, `xelatex`, and `bibtex` were
not found, so compile success is not claimed in this integration phase.

## Figure Checklist

- [ ] Add `figure/architecture-overview.png`; Chapter 2 detects it automatically.
- [ ] Add `figure/evaluation-result-40-cases.png`; Chapter 4 detects it automatically.
- [ ] Add `figure/baseline-vs-guarded-comparison.png`; Chapter 4 detects it automatically.
- [ ] Use only screenshots/exports captured from the repository and generated
artifacts; do not create substitute evidence.
- [ ] Add figure source, command/date, caption and cross-reference.
- [ ] Verify image resolution and readability in the final PDF.

## Citation Checklist

- [x] No new bibliography entry was invented during final integration.
- [x] Current `\cite{}` keys resolve statically to `refs.bib` entries.
- [ ] Confirm exact OWASP revision/year used in prose.
- [ ] Complete team full-text review for PoisonedRAG, PIDP-Attack and the review
article before making detailed claims from them.
- [ ] Replace any needed missing citation with a verified source; until then use
an explicit `TODO citation` marker rather than fabricated metadata.
- [ ] Inspect bibliography formatting in compiled PDF.

## Claim-Safety Checklist

- [x] Every 40/40 statement is scoped to the controlled synthetic benchmark.
- [x] Baseline is defined as always-allow decisions, not LLM quality.
- [x] Guard implementation is described as rule/regex-based.
- [x] Report states there is no real LLM provider/API call.
- [x] Report states there is no embedding, vector database or real retrieval.
- [x] Report states results are not real-world detection rates or guarantees.
- [x] Calibration/overfitting risk is disclosed.
- [x] No latency/load result is claimed.
- [ ] Supervisor reviews all quantitative statements against generated JSON/MD.

## Final PDF Review Checklist

- [ ] Official title matches exactly on both cover pages.
- [ ] Student, class and supervisor details are correct.
- [ ] Approved proposal page is replaced/confirmed as required.
- [ ] Group-work allocation matches actual team records.
- [ ] Page numbering and required front-matter order satisfy the school template.
- [ ] Tables and figures are numbered, referenced and readable.
- [ ] No visible TODO figure fallback remains in the final PDF.
- [ ] No stale phrases such as “chưa có mã nguồn/số liệu” remain unless clearly
marked as historical context.
- [ ] Vietnamese grammar, terminology and punctuation are proofread.
- [ ] Final PDF opens on another machine and all links/bookmarks work.
- [ ] Supervisor feedback is resolved and sign-off recorded.
- [ ] Final commit hash/tag and submission package are archived.
