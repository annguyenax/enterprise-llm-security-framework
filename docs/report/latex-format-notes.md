# LaTeX Format Notes

Formatting requirements for `report-latex/`, per university academic report standards for this internship.

## Page & Typography

| Setting | Value |
|---|---|
| Paper size | A4 |
| Font family | Times New Roman |
| Font size | 12–13pt |
| Left margin | 3cm |
| Top margin | 2cm |
| Right margin | 2cm |
| Bottom margin | 2cm |
| Alignment | Justified |
| Line spacing | 1.1–1.2 |

## Implementation Notes (`main.tex`)

- Uses `geometry` package for margins: `left=3cm, top=2cm, right=2cm, bottom=2cm`.
- Uses `times` package (or `mathptmx`) for Times New Roman-equivalent font under standard LaTeX (pdflatex). If compiling with XeLaTeX/LuaLaTeX and `fontspec`, set `\setmainfont{Times New Roman}` directly instead.
- Uses `setspace` package with `\onehalfspacing` adjusted via `\setstretch{1.15}` to land in the 1.1–1.2 range.
- Body text uses default justified alignment (LaTeX default — no `\raggedright` anywhere in body).
- Font size set via document class option, e.g. `\documentclass[12pt,a4paper]{report}`.

## Structure

- `main.tex` — master document, preamble, `\input`/`\include` of chapters.
- `chapters/` — one file per chapter (introduction, chapter 1–4, conclusion, appendix). Currently empty (`.gitkeep`) — populated as each phase produces real content.
- `figures/` — diagrams and images referenced from chapters. Currently empty (`.gitkeep`).
- `references.bib` — BibTeX bibliography. Only real, verified sources — see `AGENT_RULES.md` rule 2.

## Required Report Sections

1. Trang bìa (cover page) — added when institution template/cover requirements are confirmed.
2. Mở đầu (introduction)
3. Các chương nội dung (content chapters) — see `docs/report/report-outline.md`
4. Kết luận (conclusion)
5. Tài liệu tham khảo (references)
6. Phụ lục (appendix)

## Group Work Plan

The report must include a group work plan section (phân chia công việc). Source content lives in `docs/report/bao-cao-dinh-ky-01.md` §4 and `TASK_BOARD.md`; it should be transcribed into the LaTeX appendix or introduction as required by the institution's template once that's confirmed.

## Build

Not yet verified with a specific TeX distribution in this environment. Once TeX (e.g., MiKTeX/TeX Live) is available:

```
cd report-latex
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

If institution requires XeLaTeX for native Times New Roman via `fontspec`, use `xelatex` in place of `pdflatex` above.
