"""Validation gate 3 — textbook Voronoi correctness."""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import Point

from voronoi_dhaka import (
    SKETCHES,
    assert_general_position,
    cells_tile_box,
    classify_ridges,
    clip_voronoi_to_box,
    compute_voronoi,
    perpendicular_bisector,
    vertex_degrees,
    vertices_in_box,
)

ALL_SKETCHES = list(SKETCHES.values())


# --------------------------------------------------------------------------- #
# perpendicular bisector
# --------------------------------------------------------------------------- #
def test_perpendicular_bisector_midpoint_and_perpendicularity():
    p, q = (0.0, 0.0), (4.0, 2.0)
    line = perpendicular_bisector(p, q)
    # passes through midpoint
    np.testing.assert_allclose(line.point, [2.0, 1.0])
    # direction is perpendicular to the segment
    seg = np.array(q) - np.array(p)
    assert abs(float(np.dot(line.direction, seg))) < 1e-12
    # every point on the bisector is equidistant to p and q
    for t in (-3.0, 0.0, 5.0):
        x = line.eval(t)
        assert abs(np.linalg.norm(x - p) - np.linalg.norm(x - q)) < 1e-9


def test_perpendicular_bisector_rejects_coincident():
    with pytest.raises(ValueError):
        perpendicular_bisector((1.0, 1.0), (1.0, 1.0))


# --------------------------------------------------------------------------- #
# general position
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sketch", ALL_SKETCHES, ids=[s.name for s in ALL_SKETCHES])
def test_sketches_are_in_general_position(sketch):
    assert_general_position(sketch.seeds)  # must not raise


def test_collinear_seeds_rejected():
    seeds = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [0.0, 3.0]])
    with pytest.raises(ValueError, match="collinear"):
        assert_general_position(seeds)


def test_cocircular_seeds_rejected():
    # four corners of a square are concyclic
    seeds = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.4, 0.7]])
    with pytest.raises(ValueError, match="cocircular"):
        assert_general_position(seeds)


# --------------------------------------------------------------------------- #
# degree-3 vertices
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sketch", ALL_SKETCHES, ids=[s.name for s in ALL_SKETCHES])
def test_every_interior_vertex_has_degree_three(sketch):
    vor = compute_voronoi(sketch.seeds)
    degrees = vertex_degrees(vor)
    in_box = vertices_in_box(vor, sketch.bbox)
    assert in_box, "expected at least one visible Voronoi vertex"
    for idx, _pt in in_box:
        assert degrees[idx] == 3, f"vertex {idx} has degree {degrees[idx]}, expected 3"


# --------------------------------------------------------------------------- #
# bisector midpoint lies on the correct ridge
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sketch", ALL_SKETCHES, ids=[s.name for s in ALL_SKETCHES])
def test_bisector_midpoint_lies_on_ridge_line(sketch):
    vor = compute_voronoi(sketch.seeds)
    finite, _ = classify_ridges(vor)
    assert finite, "expected finite ridges"
    for (i, j), (va, vb) in finite:
        mid = 0.5 * (vor.points[i] + vor.points[j])
        v0, v1 = vor.vertices[va], vor.vertices[vb]
        # perpendicular distance from the seed-midpoint to the ridge line
        edge = v1 - v0
        dist = abs(edge[0] * (mid[1] - v0[1]) - edge[1] * (mid[0] - v0[0]))
        dist /= np.linalg.norm(edge)
        assert dist < 1e-6, f"midpoint off ridge by {dist}"


# --------------------------------------------------------------------------- #
# clipped cells tile the box, valid and non-overlapping
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sketch", ALL_SKETCHES, ids=[s.name for s in ALL_SKETCHES])
def test_clipped_cells_tile_the_box(sketch):
    vor = compute_voronoi(sketch.seeds)
    cells = clip_voronoi_to_box(vor, sketch.bbox)
    # one finite cell per seed
    assert len(cells) == len(sketch.seeds)
    for poly in cells.values():
        assert poly.is_valid
        assert poly.area > 0
    # pairwise non-overlapping
    keys = sorted(cells)
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            overlap = cells[keys[a]].intersection(cells[keys[b]]).area
            assert overlap < 1e-6, f"cells {keys[a]},{keys[b]} overlap by {overlap}"
    # exact tiling of the box
    assert cells_tile_box(cells, sketch.bbox)


@pytest.mark.parametrize("sketch", ALL_SKETCHES, ids=[s.name for s in ALL_SKETCHES])
def test_each_cell_contains_its_own_seed(sketch):
    vor = compute_voronoi(sketch.seeds)
    cells = clip_voronoi_to_box(vor, sketch.bbox)
    for idx, poly in cells.items():
        assert poly.buffer(1e-9).contains(Point(*sketch.seeds[idx]))
