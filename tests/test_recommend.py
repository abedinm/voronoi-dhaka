"""Recommendations — greedy farthest-point placement improves coverage."""

from __future__ import annotations

import numpy as np
import shapely

from voronoi_dhaka import compute_coverage, greedy_new_facilities


def test_returns_k_new_points(sv_hospital):
    cov = compute_coverage(sv_hospital)
    rec = greedy_new_facilities(sv_hospital, cov, k=3)
    assert rec.new_points_m.shape == (3, 2)
    assert rec.new_points_lonlat.shape == (3, 2)
    assert len(rec.new_zones) == 3


def test_new_points_lie_inside_boundary(sv_hospital):
    cov = compute_coverage(sv_hospital)
    rec = greedy_new_facilities(sv_hospital, cov, k=3)
    inside = shapely.contains_xy(
        sv_hospital.boundary, rec.new_points_m[:, 0], rec.new_points_m[:, 1]
    )
    assert inside.all()


def test_max_distance_does_not_increase(sv_hospital):
    cov = compute_coverage(sv_hospital)
    rec = greedy_new_facilities(sv_hospital, cov, k=3)
    assert rec.after.max_nn_m <= rec.before.max_nn_m + 1e-6
    assert rec.after.n_underserved <= rec.before.n_underserved


def test_first_site_is_the_worst_served_point(sv_hospital):
    cov = compute_coverage(sv_hospital)
    rec = greedy_new_facilities(sv_hospital, cov, k=1)
    # the first placed facility should sit at the pre-existing worst grid point
    p = rec.new_points_m[0]
    d = np.min(np.hypot(sv_hospital.seeds[:, 0] - p[0], sv_hospital.seeds[:, 1] - p[1]))
    assert abs(d - rec.before.max_nn_m) < 1e-6
