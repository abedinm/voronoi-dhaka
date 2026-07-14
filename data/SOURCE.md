# Data Provenance

All utility locations are collected inside the Dhaka bounding box
`(90.33, 23.66, 90.50, 23.90)` (min_lon, min_lat, max_lon, max_lat).

## Primary source — OpenStreetMap

Fetched with `osmnx` (`features_from_bbox`) and cached under
`data/raw/osm_cache/`. Each feature is reduced to a single interior point
(`representative_point`, computed in the metric CRS) and stored in
`data/raw/<service>.csv` with a `source` column.

| Service | OSM tag filter | Raw (OSM) | Cleaned |
|---|---|---:|---:|
| metro_station | `railway=station\|halt`, `station=subway` | 36 | 26 |
| hospital | `amenity=hospital` | 451 | 286 |
| water_pump | `man_made=water_well\|pumping_station\|water_works`, `amenity=drinking_water` | 487 | 118 |
| fuel | `amenity=fuel` | 219 | 135 |
| bus_stop | `highway=bus_stop`, `public_transport=platform` | 559 | 314 |
| fire_station | `amenity=fire_station` | 29 | 22 |

_"Cleaned" = after reprojection to EPSG:32646, de-duplication within
`MIN_SEED_DISTANCE = 150 m`, and clipping to the Dhaka admin boundary._

In the current build **every service resolved to real OSM data** (no synthetic
points were needed). The `source` column in each processed CSV records the
provenance of every individual point.

## Boundary

`data/raw/dhaka_boundary.geojson` — the Dhaka administrative polygon from OSM
(`osmnx.geocode_to_gdf("Dhaka, Bangladesh")`) intersected with the bounding
box. Source recorded in the file's `source` property (`OSM admin ∩ bbox`).

## Synthetic fallback (only used when OSM is sparse or unreachable)

If OSM returns fewer than a service's `min_count`, the pipeline supplements
with clearly-labelled `SYNTHETIC` points and marks them `source = SYNTHETIC`.
These come from known Dhaka landmark lists:

- **metro_station** — the 16-station MRT Line-6 corridor (Uttara North →
  Motijheel). Coordinates are approximate. `# SYNTHETIC`
- **hospital** — 24 major hospitals (DMCH, Square, United, Evercare/Apollo,
  BSMMU, BIRDEM, …). Coordinates are approximate. `# SYNTHETIC`
- **fire_station** — 12 Fire Service & Civil Defence stations (Kakrail HQ,
  Sadarghat, Mirpur, Mohammadpur, …). Coordinates are approximate. `# SYNTHETIC`
- **water_pump / fuel / bus_stop** — reproducible zone-clustered scatter
  (seeded RNG) around the populated zone centres. `# SYNTHETIC`

## Population (section benefit analysis)

`data/raw/bgd_pop_1km.tif` — WorldPop Bangladesh, 1 km, UN-adjusted 2020
(`bgd_ppp_2020_1km_Aggregated_UNadj.tif`, ~0.8 MB). Downloaded from
`data.worldpop.org`. Used to weight the per-section benefit score by how many
people live in each location, and to report underserved population. Study-area
total ≈ 13.5 M. Re-downloaded automatically if the file is missing.

## Zones (Track C)

The 8 named zones (Uttara, Mirpur, Bashundhara, Banani, Gulshan, Dhanmondi,
Khilgaon, Motijheel) and their centre coordinates are defined in
`src/config.py::ZONES`. They are analytic anchors, not fetched datasets.

## Reproducibility

Delete `data/raw/` and `data/processed/` and re-run `python -m src.main` to
re-fetch from OSM. With the caches in place the run is fully offline and
deterministic.
