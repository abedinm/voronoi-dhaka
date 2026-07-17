# Thesis package

**Providing Utility Services using Voronoi Diagrams, Some Analyses,
Recommendations, along with a Case Study for Dhaka City**
Minhazul Abedin

Submission-ready documents, all generated from `../voronoi_dhaka.py`
(`python voronoi_dhaka.py` rebuilds everything).

| File | What it is |
|---|---|
| `Dhaka_Voronoi_Report.pdf` | Full report (method → analyses → recommendations → extended analyses → literature review) |
| `Dhaka_Voronoi_Report_light.pdf` | Same report, compressed to ~3.5 MB for size-capped upload portals |
| `Dhaka_Voronoi_Thesis_Draft.docx` | Editable thesis draft — Abstract, Ch. 1 Introduction, Ch. 3 Methodology, Ch. 4 Results, Ch. 5 Conclusion |
| `Dhaka_Voronoi_Literature_Review.docx` | Editable **Chapter 2 — Literature Review** (gap analysis + comparison table) |
| `Dhaka_Voronoi_Literature_Review.pdf` | Chapter 2 as PDF |
| `Dhaka_Voronoi_Slides.pptx` | 9-slide presentation deck |
| `Dhaka_Voronoi_Poster.pdf` | A1 defense poster |
| `interactive/` | 7 interactive Google-map HTML files (open in a browser, online) |

A single-file bundle of everything is at `../Dhaka_Voronoi_Thesis_Bundle.zip`.

## Also in the repository
- `../voronoi_dhaka.py` — the whole program
- `../dashboard.py` — interactive Streamlit dashboard (`streamlit run dashboard.py`)
- `../outputs/figures/` — figures (300 DPI) · `../outputs/report/` — interactive maps + metrics
- `../data/` — OpenStreetMap POIs, boundary, WorldPop raster, `SOURCE.md`
- `../tests/` — 29 tests · `../.github/workflows/` — CI

> The document copies here and the `.zip` are build artifacts (not tracked in
> git; the originals live under `../outputs/`). Rebuild any time with
> `python voronoi_dhaka.py`.
