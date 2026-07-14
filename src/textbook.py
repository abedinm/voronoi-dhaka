"""Track A — textbook Voronoi diagrams.

Redraws the three hand-sketches (P.B, M.R, Phiruz) as mathematically correct
Voronoi diagrams: proper seed points, straight perpendicular-bisector edges,
and exactly three cells meeting at every interior vertex (general position).

Each figure also carries a *proof overlay* on one edge: the segment joining
the two seeds, its midpoint, and a right-angle mark showing the Voronoi edge
is the perpendicular bisector of that segment.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")  # headless backend — we only ever save files
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon as MplPolygon

from . import config
from .voronoi_core import (
    BBox,
    assert_general_position,
    classify_ridges,
    clip_voronoi_to_box,
    compute_voronoi,
    vertex_degrees,
    vertices_in_box,
)


@dataclass(frozen=True)
class Sketch:
    name: str
    seeds: np.ndarray
    bbox: BBox


# --------------------------------------------------------------------------- #
# The three corrected sketches (general-position seed sets)
# --------------------------------------------------------------------------- #
SKETCHES: dict[str, Sketch] = {
    "PB": Sketch(
        name="P.B",
        # 7 seeds, irregular blob layout
        seeds=np.array(
            [
                [2.1, 2.7],
                [6.8, 1.9],
                [4.9, 5.6],
                [1.4, 7.8],
                [8.3, 6.9],
                [3.7, 8.9],
                [7.1, 4.1],
            ]
        ),
        bbox=(0.0, 0.0, 10.0, 10.0),
    ),
    "MR": Sketch(
        name="M.R",
        # 6 seeds: an outer ring plus two interior points (inner cells)
        seeds=np.array(
            [
                [1.5, 1.6],
                [8.4, 1.4],
                [9.1, 7.9],
                [2.3, 8.7],
                [4.6, 4.9],
                [6.3, 6.4],
            ]
        ),
        bbox=(0.0, 0.0, 10.0, 10.0),
    ),
    "PHIRUZ": Sketch(
        name="Phiruz",
        # 5 seeds, elongated layout
        seeds=np.array(
            [
                [1.2, 3.1],
                [3.7, 1.6],
                [5.9, 4.3],
                [8.4, 2.2],
                [10.8, 3.8],
            ]
        ),
        bbox=(0.0, 0.0, 12.0, 6.0),
    ),
}


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #
def _draw_right_angle(ax, corner, dir_a, dir_b, size, color) -> None:
    """Draw a small right-angle square at ``corner`` spanned by two unit dirs."""
    a = np.asarray(dir_a) / np.linalg.norm(dir_a)
    b = np.asarray(dir_b) / np.linalg.norm(dir_b)
    p0 = corner + a * size
    p1 = corner + (a + b) * size
    p2 = corner + b * size
    ax.plot(
        [p0[0], p1[0], p2[0]],
        [p0[1], p1[1], p2[1]],
        color=color,
        lw=1.2,
        solid_capstyle="round",
        zorder=6,
    )


def _pick_proof_ridge(vor, bbox: BBox):
    """Choose a finite ridge near the box centre for the bisector overlay.

    Returns ``(point_pair, vertex_pair)`` or ``None`` if no suitable ridge.
    """
    finite, _ = classify_ridges(vor)
    minx, miny, maxx, maxy = bbox
    centre = np.array([(minx + maxx) / 2, (miny + maxy) / 2])

    def inside(pt) -> bool:
        return minx <= pt[0] <= maxx and miny <= pt[1] <= maxy

    best = None
    best_d = np.inf
    for pp, vv in finite:
        v0, v1 = vor.vertices[vv[0]], vor.vertices[vv[1]]
        mid_seed = 0.5 * (vor.points[pp[0]] + vor.points[pp[1]])
        if not (inside(v0) and inside(v1) and inside(mid_seed)):
            continue
        d = float(np.linalg.norm(mid_seed - centre))
        if d < best_d:
            best_d, best = d, (pp, vv)
    return best


def draw_diagram(ax, sketch: Sketch) -> None:
    """Render one corrected Voronoi diagram onto ``ax``."""
    seeds = sketch.seeds
    bbox = sketch.bbox
    assert_general_position(seeds)
    vor = compute_voronoi(seeds)
    cells = clip_voronoi_to_box(vor, bbox)

    cmap = plt.get_cmap("Pastel1")
    # filled cells with straight black edges
    for k, (idx, poly) in enumerate(sorted(cells.items())):
        xs, ys = poly.exterior.xy
        ax.add_patch(
            MplPolygon(
                np.column_stack([xs, ys]),
                closed=True,
                facecolor=cmap(k % cmap.N),
                edgecolor="#222222",
                lw=1.6,
                zorder=2,
            )
        )

    # seeds
    ax.scatter(
        seeds[:, 0], seeds[:, 1], s=55, c="#111111", zorder=5, label="seed points"
    )
    for i, (x, y) in enumerate(seeds):
        ax.annotate(
            str(i + 1),
            (x, y),
            textcoords="offset points",
            xytext=(6, 5),
            fontsize=9,
            fontweight="bold",
            color="#111111",
            zorder=5,
        )

    # degree-3 vertices visible inside the box (three edges meet)
    degrees = vertex_degrees(vor)
    minx, miny, maxx, maxy = bbox
    deg3 = [v for i, v in vertices_in_box(vor, bbox) if degrees.get(i) == 3]
    if deg3:
        deg3 = np.array(deg3)
        ax.scatter(
            deg3[:, 0],
            deg3[:, 1],
            s=90,
            facecolors="none",
            edgecolors="#d62728",
            linewidths=1.8,
            zorder=6,
            label="degree-3 vertex",
        )

    # bisector proof overlay on one edge
    proof = _pick_proof_ridge(vor, bbox)
    if proof is not None:
        pp, vv = proof
        pi, pj = vor.points[pp[0]], vor.points[pp[1]]
        mid = 0.5 * (pi + pj)
        # connecting segment between the two seeds
        ax.plot(
            [pi[0], pj[0]],
            [pi[1], pj[1]],
            color="#1f77b4",
            lw=1.4,
            ls=(0, (4, 3)),
            zorder=4,
            label="seed–seed segment",
        )
        ax.scatter([mid[0]], [mid[1]], s=40, c="#1f77b4", marker="s", zorder=6)
        # right-angle mark between the segment and the (perpendicular) edge
        seg_dir = pj - pi
        edge_dir = np.array([-seg_dir[1], seg_dir[0]])
        size = 0.045 * float(np.hypot(maxx - minx, maxy - miny))
        # orient marks toward inside of the box
        if mid[0] + edge_dir[0] > maxx or mid[0] + edge_dir[0] < minx:
            edge_dir = -edge_dir
        _draw_right_angle(ax, mid, seg_dir, edge_dir, size, "#1f77b4")

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_title(
        f"{sketch.name} — corrected Voronoi  "
        f"({len(seeds)} seeds, all interior vertices degree 3)",
        fontsize=10,
    )
    ax.set_xticks([])
    ax.set_yticks([])


# --------------------------------------------------------------------------- #
# Rendering entry points
# --------------------------------------------------------------------------- #
def render_one(key: str) -> str:
    sketch = SKETCHES[key]
    fig, ax = plt.subplots(figsize=(6, 6 if sketch.bbox[3] >= sketch.bbox[2] else 4))
    draw_diagram(ax, sketch)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9)
    path = config.FIGURES_DIR / f"textbook_{key}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def render_all() -> list[str]:
    """Render the three individual figures and the combined 2x2 grid."""
    paths = [render_one(k) for k in SKETCHES]

    fig, axes = plt.subplots(2, 2, figsize=(13, 12))
    order = ["PB", "MR", "PHIRUZ"]
    for ax, key in zip(axes.flat, order):
        draw_diagram(ax, SKETCHES[key])

    # fourth quadrant: correctness legend / proof note
    ax = axes.flat[3]
    ax.axis("off")
    ax.text(
        0.02,
        0.98,
        "Track A — textbook correctness proof",
        fontsize=13,
        fontweight="bold",
        va="top",
    )
    ax.text(
        0.02,
        0.86,
        (
            "Every diagram satisfies:\n"
            "  • seeds in general position (no 3 collinear,\n"
            "    no 4 cocircular)\n"
            "  • all edges are straight perpendicular bisectors\n"
            "  • exactly three cells meet at each interior vertex\n"
            "    (red circles = verified degree-3 vertices)\n"
            "  • cells tile the bounding box exactly\n\n"
            "Blue overlay: the seed–seed segment, its midpoint,\n"
            "and a right-angle mark proving the shared edge is\n"
            "the perpendicular bisector of the two seeds."
        ),
        fontsize=10,
        va="top",
        family="monospace",
    )
    path_all = config.FIGURES_DIR / "textbook_all.png"
    fig.tight_layout()
    fig.savefig(path_all, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    paths.append(str(path_all))
    return paths


if __name__ == "__main__":
    for p in render_all():
        print("saved", p)
