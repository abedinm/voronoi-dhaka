"""Validation gate 5 — coverage metrics."""

from __future__ import annotations

import numpy as np
import shapely

from src.coverage import compute_coverage, make_grid, metrics_row, nearest_distance


def test_grid_points_lie_inside_boundary(sv_hospital):
    grid = make_grid(sv_hospital.boundary, spacing=500.0)
    assert len(grid) > 0
    assert shapely.contains_xy(sv_hospital.boundary, grid[:, 0], grid[:, 1]).all()


def test_nearest_distance_matches_bruteforce(sv_hospital):
    grid = make_grid(sv_hospital.boundary, spacing=1000.0)
    nn = nearest_distance(grid, sv_hospital.seeds)
    # brute-force check on a sample
    for i in range(0, len(grid), 7):
        d = np.min(np.hypot(*(sv_hospital.seeds - grid[i]).T))
        assert abs(d - nn[i]) < 1e-6


def test_cell_areas_positive_and_cover_boundary(sv_hospital):
    cov = compute_coverage(sv_hospital)
    areas = np.array(list(cov.cell_areas_km2.values()))
    assert (areas > 0).all()
    total = areas.sum() * 1e6  # back to m^2
    assert abs(total - sv_hospital.boundary.area) < 1e-3 * sv_hospital.boundary.area


def test_underserved_fraction_is_a_probability(sv_hospital):
    cov = compute_coverage(sv_hospital)
    assert 0.0 <= cov.frac_grid_underserved <= 1.0
    assert cov.max_nn_m >= cov.mean_nn_m >= 0.0


def test_underserved_cells_exceed_mean_plus_sigma(sv_hospital):
    cov = compute_coverage(sv_hospital)
    cutoff = cov.mean_area_km2 + cov.std_area_km2
    for idx in cov.underserved_cells:
        assert cov.cell_areas_km2[idx] > cutoff


def test_metrics_row_has_expected_fields(sv_hospital):
    cov = compute_coverage(sv_hospital)
    row = metrics_row(sv_hospital, cov)
    required = {
        "service", "n_facilities", "total_area_km2", "mean_cell_km2",
        "max_cell_km2", "n_underserved_cells", "threshold_m",
        "mean_nn_m", "p90_nn_m", "max_nn_m", "pct_grid_underserved",
    }
    assert required <= set(row)
    assert row["n_facilities"] == sv_hospital.n
