"""Track C, phase 5B — named-zone membership for Voronoi cells.

The eight named Dhaka areas in ``config.ZONES`` form a *coarse* Voronoi
partition (nearest zone centre wins). Every fine service cell inherits the
colour and name of whichever zone its seed lands in — so the real service
Voronoi becomes a map split into recognizable neighbourhoods.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from scipy.spatial import KDTree

from . import config
from .voronoi_core import clip_voronoi_to_box, compute_voronoi
from .voronoi_dhaka import ServiceVoronoi


@dataclass(frozen=True)
class ZoneRef:
    names: list[str]
    colors: list[str]
    centers_m: np.ndarray  # (8, 2) metric coordinates


def zone_reference() -> ZoneRef:
    """Zone names, colours and centres reprojected to the metric CRS."""
    names = list(config.ZONES)
    colors = [config.ZONES[n]["color"] for n in names]
    lonlat = np.array([config.ZONES[n]["center"] for n in names])
    gs = gpd.GeoSeries(
        gpd.points_from_xy(lonlat[:, 0], lonlat[:, 1]), crs=config.CRS_GEO
    ).to_crs(config.CRS_METRIC)
    centers = np.column_stack([gs.x.to_numpy(), gs.y.to_numpy()])
    return ZoneRef(names=names, colors=colors, centers_m=centers)


def assign_zone(seed_point: np.ndarray, ref: ZoneRef | None = None) -> tuple[str, str]:
    """Return ``(zone_name, zone_color)`` for a single metric point."""
    ref = ref or zone_reference()
    tree = KDTree(ref.centers_m)
    _, idx = tree.query(np.asarray(seed_point, dtype=float), k=1)
    return ref.names[idx], ref.colors[idx]


def assign_zones(seeds: np.ndarray, ref: ZoneRef | None = None) -> tuple[list[str], list[str]]:
    """Vectorised zone assignment for many seeds."""
    ref = ref or zone_reference()
    tree = KDTree(ref.centers_m)
    _, idx = tree.query(seeds, k=1)
    names = [ref.names[i] for i in idx]
    colors = [ref.colors[i] for i in idx]
    return names, colors


def color_cells_by_zone(sv: ServiceVoronoi, ref: ZoneRef | None = None) -> gpd.GeoDataFrame:
    """Tag every clipped cell with its zone name and colour."""
    ref = ref or zone_reference()
    idxs = sorted(sv.cells)
    seeds = sv.seeds[idxs]
    names, colors = assign_zones(seeds, ref)
    rows = []
    for idx, zname, zcol in zip(idxs, names, colors):
        poly = sv.cells[idx]
        rows.append(
            {
                "seed_index": idx,
                "zone_name": zname,
                "zone_color": zcol,
                "area_km2": poly.area / 1e6,
                "geometry": poly,
            }
        )
    return gpd.GeoDataFrame(rows, crs=config.CRS_METRIC)


def build_zone_voronoi(boundary, ref: ZoneRef | None = None) -> gpd.GeoDataFrame:
    """Coarse 8-zone Voronoi clipped to the boundary (for the dashed overlay)."""
    ref = ref or zone_reference()
    vor = compute_voronoi(ref.centers_m)
    rect_cells = clip_voronoi_to_box(vor, tuple(boundary.bounds))
    rows = []
    for idx, poly in rect_cells.items():
        clipped = poly.intersection(boundary)
        if not clipped.is_empty and clipped.area > 0:
            rows.append(
                {
                    "zone_name": ref.names[idx],
                    "zone_color": ref.colors[idx],
                    "geometry": clipped,
                }
            )
    return gpd.GeoDataFrame(rows, crs=config.CRS_METRIC)
