# Thesis package

**Providing Utility Services using Voronoi Diagrams, Some Analyses,
Recommendations, along with a Case Study for Dhaka City**
Minhazul Abedin

This folder collects the submission-ready documents. They are generated from
`../voronoi_dhaka.py` (run `python voronoi_dhaka.py` to rebuild everything).

| File | What it is |
|---|---|
| `Dhaka_Voronoi_Report.pdf` | Full 17-page report (method → analyses → recommendations → literature review §11–12) |
| `Dhaka_Voronoi_Literature_Review.docx` | Editable **Chapter 2 — Literature Review** for the AIUB template |
| `Dhaka_Voronoi_Literature_Review.pdf` | Same chapter as PDF |
| `Dhaka_Voronoi_Slides.pptx` | 9-slide presentation deck |

A single-file bundle of all four is at
`../Dhaka_Voronoi_Thesis_Bundle.zip`.

## Also in the repository
- `../voronoi_dhaka.py` — the whole program (Voronoi geometry, coverage,
  population-weighted benefit, recommendations, figure/report/deck generation)
- `../outputs/figures/` — 24 figures (300 DPI)
- `../outputs/report/` — 7 interactive Google maps + `coverage_metrics.csv`
- `../data/` — OpenStreetMap POIs, Dhaka boundary, WorldPop raster, `SOURCE.md`
- `../tests/` — 29 tests

> The document copies in this folder and the `.zip` are build artifacts and are
> not tracked in git (they live under `../outputs/`); only this index is
> committed. Rebuild them any time with `python voronoi_dhaka.py`.
