# Voronoi Analysis of Utility Services in Dhaka City

One script that partitions Dhaka into **Voronoi cells** around real utility
locations, measures how well each service covers the city, recommends where to
add facilities, and writes it all up as a **PDF report**.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python voronoi_dhaka.py     # does everything, writes outputs/Dhaka_Voronoi_Report.pdf
pytest                      # 29 correctness tests
```

Add `--force` to regenerate every figure from scratch. The first run fetches
POIs from OpenStreetMap and caches them under `data/`; later runs are offline.

## What it produces

- **`outputs/Dhaka_Voronoi_Report.pdf`** — the report, figures embedded inline.
- `outputs/figures/*.png` — every figure at 300 DPI.
- `outputs/report/interactive_dhaka_map.html` — **headline** interactive Google
  map: Dhaka split into 8 coloured sections with all six utilities plotted by
  colour + emoji logo (toggle each in the layer switcher).
- `outputs/report/interactive_<service>.html` — per utility: its Voronoi
  coverage (cells by area) + facilities + proposed new sites, on Google Maps.
- `outputs/report/coverage_metrics.csv` — the metrics table.

## What's in the analysis

1. **Textbook Voronoi** — three sketches (P.B, M.R, Phiruz) redrawn as
   mathematically correct diagrams: straight perpendicular-bisector edges,
   exactly three cells meeting at each vertex, cells tiling the box.
2. **Six services from OpenStreetMap** — metro, hospitals, water pumps, fuel,
   bus stops, fire stations.
3. **Coverage** — each service's Voronoi drawn over the real Dhaka street map,
   cells coloured by area; a location is "underserved" past a per-service
   nearest-facility distance threshold.
4. **Zone map** — the real Voronoi coloured by the eight named Dhaka areas
   (Uttara, Mirpur, Gulshan, Dhanmondi …) each cell falls in.
5. **Recommendations** — greedy farthest-point placement of new facilities,
   with before/after access numbers.
6. **Section benefit** — each of the 8 areas scored by how well its *people* are
   served (WorldPop population-weighted, emergency services weighted higher),
   answering which areas benefit most and where new facilities would help most
   (`outputs/figures/section_benefit.png`, PDF §7).

## How it works

Everything lives in **`voronoi_dhaka.py`** (one file, sectioned by comment
banners: config → geometry → textbook → data → coverage → zones → recommend →
viz → PDF → main). Distances and areas are computed in a metric CRS
(UTM 46N, EPSG:32646). Each Voronoi cell is the intersection of the half-planes
bounded by the perpendicular bisectors to its Delaunay neighbours — so every
interior edge is a true perpendicular bisector and the cells tile the region
exactly.

```
voronoi_dhaka.py       # the whole program
tests/                 # voronoi geometry, coverage, recommendations
data/                  # raw/ processed/ SOURCE.md  (cached OSM POIs)
outputs/               # figures/ report/  + the PDF
requirements.txt
```

See `data/SOURCE.md` for data provenance.
