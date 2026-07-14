# Voronoi Analysis of Utility Services in Dhaka City

A reproducible study of how well Dhaka's utility services cover the city,
using **Voronoi diagrams**. Two tracks:

- **Track A — textbook Voronoi.** Three hand-sketches (P.B, M.R, Phiruz)
  redrawn as mathematically correct Voronoi diagrams: seeds in general
  position, straight perpendicular-bisector edges, exactly three cells meeting
  at every vertex, cells tiling the box.
- **Track B — applied Dhaka.** Real OpenStreetMap locations for six services
  (metro, hospitals, water sources, fuel, bus stops, fire stations), a Voronoi
  partition clipped to the city boundary, coverage analysis (well-served vs
  underserved), and greedy recommendations for new facilities.
- **Track C — zone-coloured flagship map.** The real service Voronoi with every
  cell coloured by the named Dhaka zone (Uttara, Mirpur, Gulshan, …) its seed
  falls in — a genuine Voronoi diagram split into recognizable neighbourhoods.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.main     # reproduces all data, figures and the report
pytest                 # correctness gates (29 tests)
```

The first run fetches POIs from OpenStreetMap and caches them under
`data/raw/`; later runs are offline and deterministic.

## What gets produced

```
outputs/figures/
  textbook_PB.png  textbook_MR.png  textbook_PHIRUZ.png  textbook_all.png
  voronoi_<service>.png        # cells coloured by area, over a basemap
  heatmap_<service>.png        # nearest-facility distance heatmap
  recommendations_<service>.png
  zones_<service>.png          # zone-coloured Voronoi (Track C)
  zones_dhaka_flagship.png     # the flagship map (densest service)
outputs/report/
  coverage_metrics.csv         # per-service metrics table
  recommendations.md           # per-service before/after + coordinates
  interactive_<service>.html   # folium: cells, facilities, heat, proposals
  zones_<service>.html         # folium: cells coloured by zone
  FINAL_REPORT.md              # auto-stitched write-up
```

## How it works

- **CRS.** Input/output in WGS84 (EPSG:4326); every distance and area is
  computed in UTM zone 46N (EPSG:32646, metres).
- **Exact Voronoi cells.** Each cell is the intersection of the half-planes
  defined by the perpendicular bisectors to its Delaunay neighbours, clipped to
  the study box and then to the real boundary — so every interior edge is a
  true perpendicular bisector and the cells tile the region exactly
  (`src/voronoi_core.py`).
- **Coverage.** Cell area, and nearest-facility distance on a 250 m grid via a
  KDTree; a location is underserved past a per-service distance threshold
  (`src/coverage.py`).
- **Recommendations.** Greedy farthest-point placement: repeatedly add a
  facility at the worst-served grid point (`src/recommend.py`).

## Layout

```
src/
  config.py        CRS, bbox, service catalogue, named zones
  voronoi_core.py  pure-math Voronoi + bisector geometry
  textbook.py      Track A — the three clean diagrams
  data_fetch.py    OSM POI collection (+ synthetic fallback)
  data_clean.py    reproject, dedup, boundary clip
  voronoi_dhaka.py Track B — clipped Voronoi per service
  coverage.py      cell area, nearest-distance grid, underserved flags
  zones.py         Track C — nearest-zone membership
  recommend.py     greedy facility placement
  viz.py           static maps, heatmaps, flagship, folium
  main.py          full pipeline + FINAL_REPORT.md
tests/             voronoi_core, coverage, recommend
data/              raw/ processed/ SOURCE.md
```

See `data/SOURCE.md` for data provenance and the synthetic-fallback policy.
