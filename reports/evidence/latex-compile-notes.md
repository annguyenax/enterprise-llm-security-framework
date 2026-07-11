# LaTeX Compile Notes

## Recommended Compiler

Use **pdfLaTeX** on Overleaf. The template uses UTF-8 Vietnamese support and a
BibTeX workflow through `\bibliographystyle{plain}` and `\bibliography{refs}`;
it does not use `biblatex`, so Biber is not required.

Compile from the `report-latex-template/` directory. On Overleaf, set
`main.tex` as the main document and choose pdfLaTeX.

## Compile Sequence

Preferred local command when `latexmk` is available:

```powershell
latexmk -pdf main.tex
```

Manual equivalent:

```powershell
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The repeated pdfLaTeX passes resolve the table of contents, lists, citations,
and cross-references. Delete only generated auxiliary files when a stale build
persists; keep all source `.tex`, `.bib`, and figure files.

## Missing Figures

The three final evidence figures belong in `report-latex-template/figure/`:

- `architecture-overview.png`
- `evaluation-result-40-cases.png`
- `baseline-vs-guarded-comparison.png`

Each figure uses `\IfFileExists`, so a missing file produces a visible TODO box
instead of a compile error. The fallback is acceptable for draft review only;
no TODO box should remain in the submission PDF.

## Common Errors And Fixes

- **Undefined citations:** run BibTeX after the first pdfLaTeX pass; confirm the
  key exists in `refs.bib` and inspect `main.blg`.
- **Undefined references:** run pdfLaTeX twice after BibTeX; check that each
  `\ref` has a matching unique `\label`.
- **Vietnamese characters render incorrectly:** confirm all sources are UTF-8
  and the Overleaf compiler is pdfLaTeX. Do not re-save files as ANSI.
- **Missing package/font:** review the first actual error in the log and use an
  Overleaf TeX Live version compatible with the template before altering style.
- **Special-character error:** escape literal `%`, `_`, `&`, `#`, `$`, `{`, and
  `}` in prose, or place paths/commands in `\texttt{}`/`verbatim` correctly.
- **Image too large or unreadable:** crop irrelevant UI, retain evidence text,
  and adjust only the `width` option while preserving aspect ratio.
- **Overfull `\hbox`:** inspect the cited line, shorten long inline paths, add a
  deliberate break, or use a wrapping table column. Do not hide all warnings
  globally.
- **Long table overflow:** verify the group-work `longtable` and appendix figure
  table at 100% PDF zoom; shorten cell text or rebalance column widths if needed.

## Current Environment Note

Static source checks are complete, but this workspace has no `latexmk`,
`pdflatex`, `xelatex`, or `bibtex` executable. PDF compile success and warning
counts therefore remain unverified until the first Overleaf or local TeX build.
