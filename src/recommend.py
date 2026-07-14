"""Phase 6 — where to add facilities.

Baseline: greedy *farthest-point* max-coverage. At each step we place a new
facility at the grid location currently worst served (maximum nearest-facility
distance), recompute distances, and repeat ``K`` times. This is the classic
greedy heuristic for the p-center problem and directly shrinks the worst-case
access distance. We report the before/after change in max distance, mean
distance, and the number of underserved grid points.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from scipy.spatial import KDTree

from . import config
from .coverage import CoverageResult
from .voronoi_dhaka import ServiceVoronoi
from .zones import ZoneRef, assign_zones, zone_reference


@dataclass
class Snapshot:
    max_nn_m: float
    mean_nn_m: float
    n_underserved: int


@dataclass
class RecommendResult:
    key: str
    k: int
    new_points_m: np.ndarray  # (K, 2) metric
    new_points_lonlat: np.ndarray  # (K, 2) lon, lat
    new_zones: list[str]
    threshold_m: float
    before: Snapshot
    after: Snapshot

    @property
    def max_improvement_m(self) -> float:
        return self.before.max_nn_m - self.after.max_nn_m


def _snapshot(grid: np.ndarray, seeds: np.ndarray, threshold: float) -> Snapshot:
    d = KDTree(seeds).query(grid)[0]
    return Snapshot(
        max_nn_m=float(d.max()),
        mean_nn_m=float(d.mean()),
        n_underserved=int((d > threshold).sum()),
    )


def greedy_new_facilities(
    sv: ServiceVoronoi,
    cov: CoverageResult,
    k: int = config.RECOMMEND_K,
    ref: ZoneRef | None = None,
) -> RecommendResult:
    ref = ref or zone_reference()
    grid = cov.grid_xy
    threshold = cov.threshold_m

    before = _snapshot(grid, sv.seeds, threshold)

    current = sv.seeds.copy()
    new_pts: list[np.ndarray] = []
    for _ in range(k):
        d = KDTree(current).query(grid)[0]
        worst = grid[int(np.argmax(d))]
        new_pts.append(worst)
        current = np.vstack([current, worst])

    after = _snapshot(grid, current, threshold)
    new_m = np.array(new_pts)

    ll = gpd.GeoSeries(
        gpd.points_from_xy(new_m[:, 0], new_m[:, 1]), crs=config.CRS_METRIC
    ).to_crs(config.CRS_GEO)
    new_lonlat = np.column_stack([ll.x.to_numpy(), ll.y.to_numpy()])
    zones, _ = assign_zones(new_m, ref)

    return RecommendResult(
        key=sv.key,
        k=k,
        new_points_m=new_m,
        new_points_lonlat=new_lonlat,
        new_zones=zones,
        threshold_m=threshold,
        before=before,
        after=after,
    )


def recommend_all(
    voronois: dict[str, ServiceVoronoi], coverages: dict[str, CoverageResult]
) -> dict[str, RecommendResult]:
    print("[phase 6] greedy facility recommendations")
    ref = zone_reference()
    out: dict[str, RecommendResult] = {}
    for key, sv in voronois.items():
        res = greedy_new_facilities(sv, coverages[key], ref=ref)
        out[key] = res
        print(
            f"    {key:14s} max_nn {res.before.max_nn_m/1000:5.2f}km -> "
            f"{res.after.max_nn_m/1000:5.2f}km  "
            f"(underserved {res.before.n_underserved} -> {res.after.n_underserved})"
        )
    return out


def write_recommendations_md(results: dict[str, RecommendResult]) -> str:
    lines = ["# Facility Placement Recommendations", ""]
    lines.append(
        "Greedy farthest-point placement of "
        f"K = {config.RECOMMEND_K} new facilities per service. "
        "Each new site is the worst-served location at the time it is added; "
        "figures below quantify the before/after change in access.\n"
    )
    for key, r in results.items():
        label = config.SERVICE_TYPES[key].label
        lines.append(f"## {label} (`{key}`)")
        lines.append("")
        lines.append(
            f"- Underserved threshold: **{r.threshold_m/1000:.1f} km** "
            "nearest-facility distance."
        )
        lines.append(
            f"- Max access distance: **{r.before.max_nn_m/1000:.2f} km -> "
            f"{r.after.max_nn_m/1000:.2f} km** "
            f"(cut by {r.max_improvement_m/1000:.2f} km)."
        )
        lines.append(
            f"- Mean access distance: {r.before.mean_nn_m/1000:.2f} km -> "
            f"{r.after.mean_nn_m/1000:.2f} km."
        )
        lines.append(
            f"- Underserved grid points: {r.before.n_underserved} -> "
            f"{r.after.n_underserved}."
        )
        lines.append("- Proposed new sites (worst-served first):")
        for i, (lon, lat) in enumerate(r.new_points_lonlat):
            zone = r.new_zones[i]
            lines.append(
                f"  {i+1}. near **{zone}** — lat {lat:.4f}, lon {lon:.4f}"
            )
        lines.append("")
    text = "\n".join(lines)
    out = config.REPORT_DIR / "recommendations.md"
    out.write_text(text)
    print(f"    recommendations -> {out}")
    return text


if __name__ == "__main__":
    from .coverage import compute_all
    from .voronoi_dhaka import build_all

    vs = build_all()
    covs, _ = compute_all(vs)
    res = recommend_all(vs, covs)
    write_recommendations_md(res)
