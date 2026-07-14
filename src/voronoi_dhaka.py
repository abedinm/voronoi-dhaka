"""Track B, phase 5.1 — Voronoi partitions of Dhaka, per service.

Each service's cleaned points become Voronoi seeds (metric CRS). Cells are
first clipped to the rectangular study window (exact perpendicular-bisector
edges, via :mod:`voronoi_core`) and then intersected with the real Dhaka
admin boundary, so every cell is a finite polygon inside the city.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon

from . import config, data_clean
from .voronoi_core import BBox, clip_voronoi_to_box, compute_voronoi


@dataclass
class ServiceVoronoi:
    """A service's Voronoi partition and the data behind it."""

    key: str
    seeds: np.ndarray  # (N, 2) metric coordinates (x_m, y_m)
    names: list[str]
    sources: list[str]
    cells: dict[int, Polygon | MultiPolygon]  # seed index -> clipped cell (metric)
    boundary: Polygon | MultiPolygon  # study-area polygon (metric)
    bbox: BBox = field(default=(0, 0, 0, 0))

    @property
    def n(self) -> int:
        return len(self.seeds)

    def cells_gdf(self) -> gpd.GeoDataFrame:
        rows = []
        for idx, poly in self.cells.items():
            rows.append(
                {
                    "seed_index": idx,
                    "name": self.names[idx],
                    "source": self.sources[idx],
                    "x_m": float(self.seeds[idx, 0]),
                    "y_m": float(self.seeds[idx, 1]),
                    "area_km2": poly.area / 1e6,
                    "geometry": poly,
                }
            )
        return gpd.GeoDataFrame(rows, crs=config.CRS_METRIC)

    def seeds_gdf(self) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {"name": self.names, "source": self.sources},
            geometry=gpd.points_from_xy(self.seeds[:, 0], self.seeds[:, 1]),
            crs=config.CRS_METRIC,
        )


def _load_points(service_key: str) -> pd.DataFrame:
    path = config.PROCESSED_DIR / f"{service_key}.csv"
    if not path.exists():
        return data_clean.clean_service(service_key)
    return pd.read_csv(path)


def build_service_voronoi(service_key: str, boundary=None) -> ServiceVoronoi:
    df = _load_points(service_key)
    seeds = df[["x_m", "y_m"]].to_numpy()
    if boundary is None:
        boundary = data_clean.boundary_metric()
    bbox: BBox = tuple(boundary.bounds)  # (minx, miny, maxx, maxy)

    vor = compute_voronoi(seeds)
    rect_cells = clip_voronoi_to_box(vor, bbox)

    cells: dict[int, Polygon | MultiPolygon] = {}
    for idx, poly in rect_cells.items():
        clipped = poly.intersection(boundary)
        if not clipped.is_empty and clipped.area > 0:
            cells[idx] = clipped

    return ServiceVoronoi(
        key=service_key,
        seeds=seeds,
        names=df["name"].tolist(),
        sources=df["source"].tolist(),
        cells=cells,
        boundary=boundary,
        bbox=bbox,
    )


def build_all() -> dict[str, ServiceVoronoi]:
    print("[phase 5.1] building Dhaka Voronoi partitions")
    boundary = data_clean.boundary_metric()
    out: dict[str, ServiceVoronoi] = {}
    for key in config.SERVICE_TYPES:
        sv = build_service_voronoi(key, boundary=boundary)
        out[key] = sv
        print(f"    {key:14s} seeds={sv.n:4d}  cells={len(sv.cells):4d}")
    return out


if __name__ == "__main__":
    build_all()
