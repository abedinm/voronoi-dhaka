"""Track B, phase 5.2 — coverage metrics.

For each service we quantify how evenly the facilities serve the city:

* **cell area** (km^2) per Voronoi region — a large cell means one facility
  must serve a wide area (sparse coverage);
* **nearest-facility distance** on a fine grid (KDTree) — the access a
  resident at each grid point actually experiences;
* **underserved** locations — cells larger than mean + 1 sigma, and grid
  points whose nearest facility is farther than the service threshold.

No population-density raster is bundled, so "access" here is area-based
(every location weighted equally); this caveat is carried into the report.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import shapely
from scipy.spatial import KDTree

from . import config
from .voronoi_dhaka import ServiceVoronoi


@dataclass
class CoverageResult:
    key: str
    cell_areas_km2: dict[int, float]
    mean_area_km2: float
    std_area_km2: float
    underserved_cells: list[int]  # cell area > mean + 1 sigma
    grid_xy: np.ndarray  # (M, 2) metric grid points inside the boundary
    grid_nn_m: np.ndarray  # (M,) nearest-facility distance in metres
    threshold_m: float
    mean_nn_m: float
    p90_nn_m: float
    max_nn_m: float
    frac_grid_underserved: float


def make_grid(boundary, spacing: float = config.GRID_SPACING_M) -> np.ndarray:
    """Regular grid of points (metric) lying inside ``boundary``."""
    minx, miny, maxx, maxy = boundary.bounds
    xs = np.arange(minx, maxx, spacing)
    ys = np.arange(miny, maxy, spacing)
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    mask = shapely.contains_xy(boundary, pts[:, 0], pts[:, 1])
    return pts[mask]


def nearest_distance(grid_xy: np.ndarray, seeds: np.ndarray) -> np.ndarray:
    """Distance from every grid point to the nearest facility (metres)."""
    tree = KDTree(seeds)
    dist, _ = tree.query(grid_xy, k=1)
    return dist


def compute_coverage(sv: ServiceVoronoi) -> CoverageResult:
    areas = {idx: poly.area / 1e6 for idx, poly in sv.cells.items()}
    a = np.array(list(areas.values()))
    mean_a, std_a = float(a.mean()), float(a.std())
    underserved_cells = [idx for idx, km2 in areas.items() if km2 > mean_a + std_a]

    grid = make_grid(sv.boundary)
    nn = nearest_distance(grid, sv.seeds)
    threshold = config.SERVICE_TYPES[sv.key].underserved_m
    frac_under = float((nn > threshold).mean())

    return CoverageResult(
        key=sv.key,
        cell_areas_km2=areas,
        mean_area_km2=mean_a,
        std_area_km2=std_a,
        underserved_cells=underserved_cells,
        grid_xy=grid,
        grid_nn_m=nn,
        threshold_m=threshold,
        mean_nn_m=float(nn.mean()),
        p90_nn_m=float(np.percentile(nn, 90)),
        max_nn_m=float(nn.max()),
        frac_grid_underserved=frac_under,
    )


def metrics_row(sv: ServiceVoronoi, cov: CoverageResult) -> dict:
    a = np.array(list(cov.cell_areas_km2.values()))
    return {
        "service": sv.key,
        "label": config.SERVICE_TYPES[sv.key].label,
        "n_facilities": sv.n,
        "n_cells": len(cov.cell_areas_km2),
        "total_area_km2": round(float(a.sum()), 2),
        "mean_cell_km2": round(cov.mean_area_km2, 3),
        "std_cell_km2": round(cov.std_area_km2, 3),
        "max_cell_km2": round(float(a.max()), 3),
        "n_underserved_cells": len(cov.underserved_cells),
        "threshold_m": cov.threshold_m,
        "mean_nn_m": round(cov.mean_nn_m, 1),
        "p90_nn_m": round(cov.p90_nn_m, 1),
        "max_nn_m": round(cov.max_nn_m, 1),
        "pct_grid_underserved": round(100 * cov.frac_grid_underserved, 1),
    }


def compute_all(voronois: dict[str, ServiceVoronoi]) -> tuple[dict[str, CoverageResult], pd.DataFrame]:
    print("[phase 5.2] computing coverage metrics")
    results: dict[str, CoverageResult] = {}
    rows = []
    for key, sv in voronois.items():
        cov = compute_coverage(sv)
        results[key] = cov
        rows.append(metrics_row(sv, cov))
        print(
            f"    {key:14s} mean_cell={cov.mean_area_km2:6.2f}km2  "
            f"max_nn={cov.max_nn_m/1000:5.2f}km  "
            f"underserved_grid={100*cov.frac_grid_underserved:4.1f}%"
        )
    table = pd.DataFrame(rows)
    out = config.REPORT_DIR / "coverage_metrics.csv"
    table.to_csv(out, index=False)
    print(f"    metrics table -> {out}")
    return results, table


if __name__ == "__main__":
    from .voronoi_dhaka import build_all

    compute_all(build_all())
