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

### Interactive maps (`interactive/`)
Seven interactive Google-map HTML files — open any in a web browser:

| File | What it shows |
|---|---|
| `interactive_dhaka_map.html` | **Headline** — 8 coloured sections + all six utilities (colour + emoji), toggleable |
| `interactive_<service>.html` (×6) | Per-utility Voronoi coverage + facilities + proposed new sites |

> These load the **Google Maps basemap from the internet**, so open them online;
> the Voronoi cells, section colours and markers still display without a
> connection (on a blank background).

A single-file bundle of everything (documents + interactive maps) is at
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
