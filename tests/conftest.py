"""Shared fixtures — build a network-free ServiceVoronoi in a metric box."""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

from voronoi_dhaka import ServiceVoronoi, clip_voronoi_to_box, compute_voronoi

# A rectangle roughly the size/position of Dhaka in UTM 46N metres.
_X0, _Y0, _W, _H = 760_000.0, 2_600_000.0, 15_000.0, 20_000.0


def make_service_voronoi(key: str = "hospital", n: int = 25, seed: int = 0) -> ServiceVoronoi:
    rng = np.random.default_rng(seed)
    seeds = np.column_stack(
        [_X0 + rng.uniform(0, _W, n), _Y0 + rng.uniform(0, _H, n)]
    )
    boundary = box(_X0, _Y0, _X0 + _W, _Y0 + _H)
    vor = compute_voronoi(seeds)
    cells = clip_voronoi_to_box(vor, tuple(boundary.bounds))
    return ServiceVoronoi(
        key=key,
        seeds=seeds,
        names=[f"facility {i}" for i in range(n)],
        sources=["SYNTHETIC"] * n,
        cells=cells,
        boundary=boundary,
        bbox=tuple(boundary.bounds),
    )


@pytest.fixture
def sv_hospital() -> ServiceVoronoi:
    return make_service_voronoi("hospital", n=25, seed=0)
