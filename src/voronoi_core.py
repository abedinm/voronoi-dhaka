"""Pure-math Voronoi geometry.

Everything here is CRS-agnostic: it operates on plain ``(N, 2)`` arrays of
coordinates. The applied Dhaka pipeline feeds it metric (UTM) coordinates;
the textbook track feeds it arbitrary planar coordinates.

Design choice — exact clipping via half-planes
-----------------------------------------------
A Voronoi cell of seed *i* is the intersection of the half-planes

    H(i, j) = { x : |x - p_i| <= |x - p_j| }

taken over every Delaunay neighbour *j*. Each boundary of ``H(i, j)`` is,
by construction, the perpendicular bisector of the segment ``p_i p_j``.
We build every clipped cell by intersecting the bounding box with those
half-planes, so **every interior edge is a true perpendicular bisector** and
the cells tile the box exactly (no gaps, no overlaps). We only clip against
ridge neighbours (from SciPy's Delaunay/Voronoi), which keeps it O(n).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

Coord = tuple[float, float]
BBox = tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)


# --------------------------------------------------------------------------- #
# Bisector geometry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Line:
    """An infinite line, stored as a point on it and a unit direction."""

    point: np.ndarray  # (2,) a point the line passes through
    direction: np.ndarray  # (2,) unit vector along the line

    def eval(self, t: float) -> np.ndarray:
        return self.point + t * self.direction


def perpendicular_bisector(p: Coord | np.ndarray, q: Coord | np.ndarray) -> Line:
    """Return the perpendicular bisector of segment ``p``-``q``.

    The line passes through the midpoint of ``p`` and ``q`` and is oriented
    perpendicular to the segment (rotate the segment direction by 90 degrees).
    """
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    if np.allclose(p, q):
        raise ValueError("perpendicular_bisector: p and q coincide")
    midpoint = 0.5 * (p + q)
    seg = q - p
    # rotate segment direction +90 deg -> perpendicular direction
    perp = np.array([-seg[1], seg[0]], dtype=float)
    perp /= np.linalg.norm(perp)
    return Line(point=midpoint, direction=perp)


# --------------------------------------------------------------------------- #
# Voronoi construction
# --------------------------------------------------------------------------- #
def compute_voronoi(seeds: np.ndarray) -> Voronoi:
    """Wrap ``scipy.spatial.Voronoi``.

    The returned object carries both finite and infinite ridges;
    infinite ridge endpoints are encoded as vertex index ``-1``
    (see :func:`classify_ridges`).
    """
    seeds = np.asarray(seeds, dtype=float)
    if seeds.ndim != 2 or seeds.shape[1] != 2:
        raise ValueError("seeds must be an (N, 2) array")
    if len(seeds) < 3:
        raise ValueError("need at least 3 seeds for a 2-D Voronoi diagram")
    return Voronoi(seeds)


def classify_ridges(vor: Voronoi) -> tuple[list[tuple], list[tuple]]:
    """Split ridges into finite and infinite.

    Returns ``(finite, infinite)`` where each entry is
    ``(point_pair, vertex_pair)``. Infinite ridges have a ``-1`` vertex.
    """
    finite: list[tuple] = []
    infinite: list[tuple] = []
    for point_pair, vertex_pair in zip(vor.ridge_points, vor.ridge_vertices):
        pp = tuple(int(x) for x in point_pair)
        vv = tuple(int(x) for x in vertex_pair)
        (infinite if -1 in vv else finite).append((pp, vv))
    return finite, infinite


def vertex_degrees(vor: Voronoi) -> dict[int, int]:
    """Total degree of every real Voronoi vertex.

    Counts *all* incident edges, finite ridges and infinite rays alike. In
    general position every Voronoi vertex has degree exactly 3 — three edges
    meet — regardless of whether some of those edges run to infinity.
    """
    incident: dict[int, int] = defaultdict(int)
    for vertex_pair in vor.ridge_vertices:
        for v in vertex_pair:
            if v != -1:
                incident[int(v)] += 1
    return dict(incident)


def vertices_in_box(vor: Voronoi, bbox: BBox) -> list[tuple[int, np.ndarray]]:
    """Real Voronoi vertices lying inside ``bbox`` (the visible junctions)."""
    minx, miny, maxx, maxy = bbox
    out = []
    for i, v in enumerate(vor.vertices):
        if minx <= v[0] <= maxx and miny <= v[1] <= maxy:
            out.append((i, v))
    return out


def interior_vertex_degrees(vor: Voronoi) -> dict[int, int]:
    """Degree (number of incident finite ridges) of each interior vertex.

    A vertex is *interior* when none of its incident ridges runs to infinity.
    In general position every interior Voronoi vertex has degree exactly 3.
    """
    incident: dict[int, int] = defaultdict(int)
    touches_infinity: set[int] = set()
    for vertex_pair in vor.ridge_vertices:
        a, b = int(vertex_pair[0]), int(vertex_pair[1])
        if a == -1 or b == -1:
            for v in (a, b):
                if v != -1:
                    touches_infinity.add(v)
            continue
        incident[a] += 1
        incident[b] += 1
    return {v: d for v, d in incident.items() if v not in touches_infinity}


# --------------------------------------------------------------------------- #
# General-position enforcement
# --------------------------------------------------------------------------- #
def _cross2(a: np.ndarray, b: np.ndarray) -> float:
    """Scalar 2-D cross product (numpy 2.x removed 2-D ``np.cross``)."""
    return float(a[0] * b[1] - a[1] * b[0])


def _scale(seeds: np.ndarray) -> float:
    span = seeds.max(axis=0) - seeds.min(axis=0)
    return float(max(span.max(), 1.0))


def assert_general_position(seeds: np.ndarray, rel_tol: float = 1e-6) -> None:
    """Raise ``ValueError`` if the seeds are not in general position.

    Two degeneracies break the "exactly three cells meet at each vertex"
    guarantee:

    * **3 collinear** seeds — a Voronoi vertex may vanish / lie at infinity;
    * **4 cocircular** seeds — four cells meet at a single point (degree 4).

    This is an O(n^4) exhaustive check intended for the small textbook seed
    sets, not for the hundreds of real Dhaka points.
    """
    seeds = np.asarray(seeds, dtype=float)
    n = len(seeds)
    s = _scale(seeds)
    area_tol = rel_tol * s * s
    circ_tol = rel_tol * s ** 4

    # collinear triples: triangle area ~ 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                a, b, c = seeds[i], seeds[j], seeds[k]
                area2 = abs(_cross2(b - a, c - a))
                if area2 < area_tol:
                    raise ValueError(
                        f"seeds {i}, {j}, {k} are (near) collinear "
                        f"(2*area={area2:.3g} < tol={area_tol:.3g})"
                    )

    # cocircular quadruples: in-circle determinant ~ 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    if _incircle_det(seeds[i], seeds[j], seeds[k], seeds[l]) < circ_tol:
                        raise ValueError(
                            f"seeds {i}, {j}, {k}, {l} are (near) cocircular "
                            "-> four cells would meet at one vertex"
                        )


def _incircle_det(a, b, c, d) -> float:
    """Absolute value of the 3x3 in-circle determinant relative to ``d``."""
    ax, ay = a - d
    bx, by = b - d
    cx, cy = c - d
    m = np.array(
        [
            [ax, ay, ax * ax + ay * ay],
            [bx, by, bx * bx + by * by],
            [cx, cy, cx * cx + cy * cy],
        ]
    )
    return abs(float(np.linalg.det(m)))


# --------------------------------------------------------------------------- #
# Exact clipping to a bounding box
# --------------------------------------------------------------------------- #
def bbox_to_polygon(bbox: BBox) -> Polygon:
    return box(*bbox)


def _halfplane_polygon(p_inside: np.ndarray, p_other: np.ndarray, reach: float) -> Polygon:
    """Large polygon covering the half-plane closer to ``p_inside``.

    The half-plane boundary is the perpendicular bisector of the two points.
    ``reach`` must exceed the diameter of the region being clipped.
    """
    m = 0.5 * (p_inside + p_other)
    n = p_other - p_inside  # outward normal (points toward the far seed)
    n_hat = n / np.linalg.norm(n)
    d_hat = np.array([-n_hat[1], n_hat[0]])  # along the bisector
    a = m + reach * d_hat
    b = m - reach * d_hat
    # extend into the p_inside side (the -n_hat direction)
    c = b - reach * n_hat
    d = a - reach * n_hat
    return Polygon([a, b, c, d])


def clip_voronoi_to_box(
    vor: Voronoi, bbox: BBox
) -> dict[int, Polygon]:
    """Return every Voronoi cell as a finite polygon clipped to ``bbox``.

    Keyed by seed index. Infinite cells are closed against the box; the
    result is an exact tiling of the box with straight (bisector) edges.
    """
    seeds = vor.points
    world = bbox_to_polygon(bbox)
    minx, miny, maxx, maxy = bbox
    reach = 100.0 * float(np.hypot(maxx - minx, maxy - miny))

    neighbours: dict[int, set[int]] = defaultdict(set)
    for i, j in vor.ridge_points:
        neighbours[int(i)].add(int(j))
        neighbours[int(j)].add(int(i))

    cells: dict[int, Polygon] = {}
    for idx in range(len(seeds)):
        cell = world
        for j in neighbours[idx]:
            hp = _halfplane_polygon(seeds[idx], seeds[j], reach)
            cell = cell.intersection(hp)
            if cell.is_empty:
                break
        if not cell.is_empty and cell.geom_type == "Polygon" and cell.area > 0:
            # Force counter-clockwise winding: GEOS overlay ops (used by the
            # tiling test and coverage intersections) misbehave on CW rings.
            if not cell.exterior.is_ccw:
                cell = Polygon(list(cell.exterior.coords)[::-1])
            cells[idx] = cell
    return cells


def cells_tile_box(cells: dict[int, Polygon], bbox: BBox, rel_tol: float = 1e-6) -> bool:
    """True if the cells cover the box with negligible overlap."""
    world = bbox_to_polygon(bbox)
    union = unary_union(list(cells.values()))
    area_sum = sum(c.area for c in cells.values())
    covered = abs(union.area - world.area) < rel_tol * world.area
    non_overlapping = abs(area_sum - union.area) < rel_tol * world.area
    return covered and non_overlapping
