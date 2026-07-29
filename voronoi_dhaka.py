#!/usr/bin/env python3
"""Voronoi analysis of utility services in Dhaka City — single-file edition.

Run everything and build the PDF report:

    python voronoi_dhaka.py

Outputs:
    outputs/figures/*.png              figures (300 DPI)
    outputs/Dhaka_Voronoi_Report.pdf   the report, figures embedded inline

What it does, in one pass:
  1. Textbook Voronoi — three sketches redrawn as mathematically correct
     diagrams (straight perpendicular-bisector edges, degree-3 vertices).
  2. Real Dhaka data — six utility services from OpenStreetMap.
  3. Voronoi coverage per service + nearest-facility heatmaps.
  4. Zone-coloured flagship map (eight named Dhaka areas).
  5. Greedy recommendations for new facilities (before/after access).
  6. A single PDF stitching it together.

Distances and areas are all computed in the metric CRS (UTM 46N, EPSG:32646).
"""

from __future__ import annotations

import datetime
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import branca.colormap as bcm
import contextily as cx
import folium
from folium.plugins import MarkerCluster
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
import shapely
from matplotlib.patches import Patch
from matplotlib.patches import Polygon as MplPolygon
from scipy.spatial import KDTree, Voronoi
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

# =========================================================================== #
# CONFIG
# =========================================================================== #
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORT_DIR = OUTPUTS_DIR / "report"
for _d in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CRS_GEO = "EPSG:4326"           # I/O (lon/lat)
CRS_METRIC = "EPSG:32646"       # UTM 46N — all geometry/maths (metres)
WEB = "EPSG:3857"               # Web Mercator — basemap tiles

DHAKA_BBOX = (90.33, 23.66, 90.50, 23.90)   # (min_lon, min_lat, max_lon, max_lat)
DHAKA_ADMIN_QUERY = "Dhaka, Bangladesh"

FIGURE_DPI = 300
MIN_SEED_DISTANCE = 150.0        # metres — dedup / general-position distance
GRID_SPACING_M = 250.0           # metres — nearest-distance grid
RANDOM_SEED = 42
RECOMMEND_K = 3                  # new facilities proposed per service

# Thesis identity — printed on the report, literature review and deck covers.
THESIS_TITLE = ("Providing Utility Services using Voronoi Diagrams, Some Analyses, "
                "Recommendations, along with a Case Study for Dhaka City")
AUTHOR = "Minhazul Abedin"

# --------------------------------------------------------------------------- #
# AIUB thesis identity (official Fall 2025-2026 template)
# --------------------------------------------------------------------------- #
AUTHORS = [
    ("Minhazul Abedin", "21-44625-1"),
    ("Zarin Tasnim Rayta", "21-45742-3"),
    ("Abdullah Al Noman", "21-45825-3"),
    ("Mehedi Hasan Aziz", "19-40060-1"),
]
SEMESTER = "Fall 2025-2026 Semester"
SUBMISSION_DATE = "August, 2026"
DEFENSE_DATE = "06.07.2026"
SUPERVISOR = "Dr. Md. Manzurul Hasan"
SUPERVISOR_RANK = "Associate Professor, Faculty"
AIUB_LOGO = ROOT / "data" / "templates" / "aiub_logo.png"
DEGREE_LINES = [
    "A Thesis submitted for the degree of Bachelor of Science (BSc) in",
    "Computer Science and Engineering (CSE) at",
    "American International University Bangladesh (AIUB)",
    "Faculty of Science and Technology (FST)",
]
DECLARATION_TEXT = [
    "This thesis is composed of our original work, and contains no material previously "
    "published or written by another person except where due reference has been made in the "
    "text. We have clearly stated the contribution of others to our thesis as a whole, "
    "including statistical assistance, survey design, data analysis, significant technical "
    "procedures, professional editorial advice, financial and any other original research work "
    "used or reported in our thesis. The content of our thesis is the result of work we have "
    "carried out since the commencement of the Thesis.",
    "We acknowledge that copyright of all material contained in my thesis resides with the "
    "copyright holder(s) of that material. Where appropriate we have obtained copyright "
    "permission from the copyright holder to reproduce material in this thesis and have sought "
    "permission from co-authors for any jointly authored works included in the thesis.",
]
EXAMINERS = [
    (SUPERVISOR, SUPERVISOR_RANK + ", Supervisor"),
    ("Prof. Dr. Muhammad Firoz Mridha", "Professor, Department of Computer Science"),
    ("Prof. Dr. Dip Nandi", "Professor & Associate Dean, FST"),
    ("Mashiour Rahman", "Sr. Associate Professor, External"),
]
ABBREVIATIONS = [
    ("2SFCA", "Two-Step Floating Catchment Area"),
    ("AIUB", "American International University-Bangladesh"),
    ("API", "Application Programming Interface"),
    ("CRS", "Coordinate Reference System"),
    ("CSE", "Computer Science and Engineering"),
    ("CSV", "Comma-Separated Values"),
    ("DPI", "Dots Per Inch"),
    ("EPSG", "European Petroleum Survey Group (CRS registry)"),
    ("FST", "Faculty of Science and Technology"),
    ("GIS", "Geographic Information System"),
    ("KD-tree", "k-Dimensional Tree"),
    ("MCLP", "Maximal Covering Location Problem"),
    ("MRT", "Mass Rapid Transit"),
    ("ODbL", "Open Database License"),
    ("OSM", "OpenStreetMap"),
    ("POI", "Point of Interest"),
    ("UTM", "Universal Transverse Mercator"),
    ("WGS84", "World Geodetic System 1984"),
]

# Population raster (WorldPop Bangladesh, 1 km, UN-adjusted 2020) for weighting
# the section benefit analysis by how many people actually live somewhere.
POP_RASTER_URL = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/"
                  "2020/BGD/bgd_ppp_2020_1km_Aggregated_UNadj.tif")
POP_RASTER_PATH = RAW_DIR / "bgd_pop_1km.tif"
# For a finer study, swap in the 100 m raster (larger download, same pipeline):
#   .../Global_2000_2020/2020/BGD/bgd_ppp_2020_UNadj.tif

# Critical-service weights: emergencies (hospital, fire) and water count more
# than fuel/bus when scoring how well a section is served.
SERVICE_WEIGHT = {"metro_station": 1.0, "hospital": 2.0, "water_pump": 1.5,
                  "fuel": 1.0, "bus_stop": 1.0, "fire_station": 2.0}


@dataclass(frozen=True)
class ServiceType:
    key: str
    label: str
    osm_tags: dict
    color: str
    min_count: int
    underserved_m: float


SERVICE_TYPES: dict[str, ServiceType] = {
    "metro_station": ServiceType("metro_station", "Metro station",
        {"railway": ["station", "halt"], "station": ["subway"]}, "#d62728", 15, 2000.0),
    "hospital": ServiceType("hospital", "Hospital",
        {"amenity": ["hospital"]}, "#2ca02c", 20, 2000.0),
    "water_pump": ServiceType("water_pump", "Water pump / source",
        {"man_made": ["water_well", "pumping_station", "water_works"],
         "amenity": ["drinking_water"]}, "#1f77b4", 10, 1000.0),
    "fuel": ServiceType("fuel", "Fuel station",
        {"amenity": ["fuel"]}, "#ff7f0e", 20, 1500.0),
    "bus_stop": ServiceType("bus_stop", "Bus stop",
        {"highway": ["bus_stop"], "public_transport": ["platform"]}, "#9467bd", 30, 800.0),
    "fire_station": ServiceType("fire_station", "Fire station",
        {"amenity": ["fire_station"]}, "#8c564b", 8, 3000.0),
}

# Emoji "logo" for each utility, used on the interactive maps.
SERVICE_EMOJI: dict[str, str] = {
    "metro_station": "🚇",
    "hospital": "🏥",
    "water_pump": "🚰",
    "fuel": "⛽",
    "bus_stop": "🚌",
    "fire_station": "🚒",
}

# Eight main sections, each a maximally-distinct colour.
ZONES: dict[str, dict] = {
    "Uttara":      {"center": (90.3975, 23.8745), "color": "#e6194B"},  # red
    "Mirpur":      {"center": (90.3654, 23.8060), "color": "#f58231"},  # orange
    "Bashundhara": {"center": (90.4350, 23.8150), "color": "#911eb4"},  # purple
    "Banani":      {"center": (90.4022, 23.7940), "color": "#4363d8"},  # blue
    "Gulshan":     {"center": (90.4155, 23.7830), "color": "#3cb44b"},  # green
    "Dhanmondi":   {"center": (90.3750, 23.7460), "color": "#42d4f4"},  # cyan
    "Khilgaon":    {"center": (90.4280, 23.7500), "color": "#f032e6"},  # magenta
    "Motijheel":   {"center": (90.4170, 23.7280), "color": "#ffe119"},  # yellow
}

BBox = tuple[float, float, float, float]


# =========================================================================== #
# GEOMETRY — pure-math Voronoi + perpendicular bisectors
# =========================================================================== #
@dataclass(frozen=True)
class Line:
    point: np.ndarray
    direction: np.ndarray

    def eval(self, t: float) -> np.ndarray:
        return self.point + t * self.direction


def _cross2(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def perpendicular_bisector(p, q) -> Line:
    """Perpendicular bisector of segment p-q: through the midpoint, normal to it."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    if np.allclose(p, q):
        raise ValueError("perpendicular_bisector: p and q coincide")
    mid = 0.5 * (p + q)
    seg = q - p
    perp = np.array([-seg[1], seg[0]], dtype=float)
    perp /= np.linalg.norm(perp)
    return Line(mid, perp)


def compute_voronoi(seeds: np.ndarray) -> Voronoi:
    seeds = np.asarray(seeds, dtype=float)
    if seeds.ndim != 2 or seeds.shape[1] != 2:
        raise ValueError("seeds must be an (N, 2) array")
    if len(seeds) < 3:
        raise ValueError("need at least 3 seeds")
    return Voronoi(seeds)


def classify_ridges(vor: Voronoi):
    finite, infinite = [], []
    for pp, vv in zip(vor.ridge_points, vor.ridge_vertices):
        pp = tuple(int(x) for x in pp)
        vv = tuple(int(x) for x in vv)
        (infinite if -1 in vv else finite).append((pp, vv))
    return finite, infinite


def vertex_degrees(vor: Voronoi) -> dict[int, int]:
    """Total degree of every real vertex (three edges meet in general position)."""
    inc: dict[int, int] = defaultdict(int)
    for vv in vor.ridge_vertices:
        for v in vv:
            if v != -1:
                inc[int(v)] += 1
    return dict(inc)


def vertices_in_box(vor: Voronoi, bbox: BBox):
    minx, miny, maxx, maxy = bbox
    return [(i, v) for i, v in enumerate(vor.vertices)
            if minx <= v[0] <= maxx and miny <= v[1] <= maxy]


def _scale(seeds: np.ndarray) -> float:
    span = seeds.max(axis=0) - seeds.min(axis=0)
    return float(max(span.max(), 1.0))


def _incircle_det(a, b, c, d) -> float:
    ax, ay = a - d
    bx, by = b - d
    cx, cy = c - d
    m = np.array([[ax, ay, ax * ax + ay * ay],
                  [bx, by, bx * bx + by * by],
                  [cx, cy, cx * cx + cy * cy]])
    return abs(float(np.linalg.det(m)))


def assert_general_position(seeds: np.ndarray, rel_tol: float = 1e-6) -> None:
    """Raise if any 3 seeds are collinear or any 4 are cocircular (O(n^4); small n)."""
    seeds = np.asarray(seeds, dtype=float)
    n = len(seeds)
    s = _scale(seeds)
    area_tol = rel_tol * s * s
    circ_tol = rel_tol * s ** 4
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if abs(_cross2(seeds[j] - seeds[i], seeds[k] - seeds[i])) < area_tol:
                    raise ValueError(f"seeds {i},{j},{k} are (near) collinear")
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    if _incircle_det(seeds[i], seeds[j], seeds[k], seeds[l]) < circ_tol:
                        raise ValueError(f"seeds {i},{j},{k},{l} are (near) cocircular")


def bbox_to_polygon(bbox: BBox) -> Polygon:
    return box(*bbox)


def _halfplane_polygon(p_inside: np.ndarray, p_other: np.ndarray, reach: float) -> Polygon:
    """Large polygon covering the half-plane closer to p_inside.

    Its boundary is the perpendicular bisector of the two seeds; ``reach`` must
    exceed the region diameter.
    """
    m = 0.5 * (p_inside + p_other)
    n = p_other - p_inside
    n_hat = n / np.linalg.norm(n)
    d_hat = np.array([-n_hat[1], n_hat[0]])
    a = m + reach * d_hat
    b = m - reach * d_hat
    c = b - reach * n_hat
    d = a - reach * n_hat
    return Polygon([a, b, c, d])


def clip_voronoi_to_box(vor: Voronoi, bbox: BBox) -> dict[int, Polygon]:
    """Each Voronoi cell as a finite polygon: box intersected with the half-planes
    to its Delaunay neighbours. Interior edges are exact perpendicular bisectors,
    and the cells tile the box exactly."""
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
            cell = cell.intersection(_halfplane_polygon(seeds[idx], seeds[j], reach))
            if cell.is_empty:
                break
        if not cell.is_empty and cell.geom_type == "Polygon" and cell.area > 0:
            if not cell.exterior.is_ccw:  # GEOS overlay misbehaves on CW rings
                cell = Polygon(list(cell.exterior.coords)[::-1])
            cells[idx] = cell
    return cells


def cells_tile_box(cells: dict[int, Polygon], bbox: BBox, rel_tol: float = 1e-6) -> bool:
    world = bbox_to_polygon(bbox)
    union = unary_union(list(cells.values()))
    area_sum = sum(c.area for c in cells.values())
    return (abs(union.area - world.area) < rel_tol * world.area
            and abs(area_sum - union.area) < rel_tol * world.area)


# =========================================================================== #
# TEXTBOOK — the three corrected sketches
# =========================================================================== #
@dataclass(frozen=True)
class Sketch:
    name: str
    seeds: np.ndarray
    bbox: BBox


SKETCHES: dict[str, Sketch] = {
    "PB": Sketch("P.B", np.array([
        [2.1, 2.7], [6.8, 1.9], [4.9, 5.6], [1.4, 7.8],
        [8.3, 6.9], [3.7, 8.9], [7.1, 4.1]]), (0.0, 0.0, 10.0, 10.0)),
    "MR": Sketch("M.R", np.array([
        [1.5, 1.6], [8.4, 1.4], [9.1, 7.9], [2.3, 8.7],
        [4.6, 4.9], [6.3, 6.4]]), (0.0, 0.0, 10.0, 10.0)),
    "PHIRUZ": Sketch("Phiruz", np.array([
        [1.2, 3.1], [3.7, 1.6], [5.9, 4.3], [8.4, 2.2],
        [10.8, 3.8]]), (0.0, 0.0, 12.0, 6.0)),
}


def _draw_right_angle(ax, corner, dir_a, dir_b, size, color) -> None:
    a = np.asarray(dir_a) / np.linalg.norm(dir_a)
    b = np.asarray(dir_b) / np.linalg.norm(dir_b)
    p0, p1, p2 = corner + a * size, corner + (a + b) * size, corner + b * size
    ax.plot([p0[0], p1[0], p2[0]], [p0[1], p1[1], p2[1]],
            color=color, lw=1.2, zorder=6)


def _pick_proof_ridge(vor: Voronoi, bbox: BBox):
    finite, _ = classify_ridges(vor)
    minx, miny, maxx, maxy = bbox
    centre = np.array([(minx + maxx) / 2, (miny + maxy) / 2])

    def inside(pt):
        return minx <= pt[0] <= maxx and miny <= pt[1] <= maxy

    best, best_d = None, np.inf
    for pp, vv in finite:
        v0, v1 = vor.vertices[vv[0]], vor.vertices[vv[1]]
        mid_seed = 0.5 * (vor.points[pp[0]] + vor.points[pp[1]])
        if inside(v0) and inside(v1) and inside(mid_seed):
            d = float(np.linalg.norm(mid_seed - centre))
            if d < best_d:
                best_d, best = d, (pp, vv)
    return best


def draw_textbook(ax, sketch: Sketch) -> None:
    seeds, bbox = sketch.seeds, sketch.bbox
    assert_general_position(seeds)
    vor = compute_voronoi(seeds)
    cells = clip_voronoi_to_box(vor, bbox)
    cmap = plt.get_cmap("Pastel1")
    for k, (idx, poly) in enumerate(sorted(cells.items())):
        xs, ys = poly.exterior.xy
        ax.add_patch(MplPolygon(np.column_stack([xs, ys]), closed=True,
                                facecolor=cmap(k % cmap.N), edgecolor="#222222",
                                lw=1.6, zorder=2))
    ax.scatter(seeds[:, 0], seeds[:, 1], s=55, c="#111111", zorder=5, label="seed points")
    for i, (x, y) in enumerate(seeds):
        ax.annotate(str(i + 1), (x, y), textcoords="offset points", xytext=(6, 5),
                    fontsize=9, fontweight="bold", zorder=5)
    degrees = vertex_degrees(vor)
    deg3 = [v for i, v in vertices_in_box(vor, bbox) if degrees.get(i) == 3]
    if deg3:
        deg3 = np.array(deg3)
        ax.scatter(deg3[:, 0], deg3[:, 1], s=90, facecolors="none",
                   edgecolors="#d62728", linewidths=1.8, zorder=6, label="degree-3 vertex")
    proof = _pick_proof_ridge(vor, bbox)
    if proof is not None:
        pp, vv = proof
        pi, pj = vor.points[pp[0]], vor.points[pp[1]]
        mid = 0.5 * (pi + pj)
        ax.plot([pi[0], pj[0]], [pi[1], pj[1]], color="#1f77b4", lw=1.4,
                ls=(0, (4, 3)), zorder=4, label="seed–seed segment")
        ax.scatter([mid[0]], [mid[1]], s=40, c="#1f77b4", marker="s", zorder=6)
        seg_dir = pj - pi
        edge_dir = np.array([-seg_dir[1], seg_dir[0]])
        minx, miny, maxx, maxy = bbox
        size = 0.045 * float(np.hypot(maxx - minx, maxy - miny))
        if mid[0] + edge_dir[0] > maxx or mid[0] + edge_dir[0] < minx:
            edge_dir = -edge_dir
        _draw_right_angle(ax, mid, seg_dir, edge_dir, size, "#1f77b4")
    minx, miny, maxx, maxy = bbox
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_title(f"{sketch.name} — corrected Voronoi ({len(seeds)} seeds, "
                 "all vertices degree 3)", fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])


def render_textbook() -> list[str]:
    paths = []
    for key, sk in SKETCHES.items():
        fig, ax = plt.subplots(figsize=(6, 6 if sk.bbox[3] >= sk.bbox[2] else 4))
        draw_textbook(ax, sk)
        ax.legend(loc="upper right", fontsize=7, framealpha=0.9)
        p = FIGURES_DIR / f"textbook_{key}.png"
        fig.tight_layout()
        fig.savefig(p, dpi=FIGURE_DPI, bbox_inches="tight")
        plt.close(fig)
        paths.append(str(p))

    fig, axes = plt.subplots(2, 2, figsize=(13, 12))
    for ax, key in zip(axes.flat, ["PB", "MR", "PHIRUZ"]):
        draw_textbook(ax, SKETCHES[key])
    ax = axes.flat[3]
    ax.axis("off")
    ax.text(0.02, 0.98, "Textbook correctness proof", fontsize=13, fontweight="bold", va="top")
    ax.text(0.02, 0.86,
            "Every diagram satisfies:\n"
            "  • seeds in general position (no 3 collinear,\n    no 4 cocircular)\n"
            "  • all edges are straight perpendicular bisectors\n"
            "  • exactly three cells meet at each vertex\n    (red = verified degree-3)\n"
            "  • cells tile the bounding box exactly\n\n"
            "Blue overlay: the seed–seed segment, its midpoint,\n"
            "and a right-angle mark proving the shared edge is\n"
            "the perpendicular bisector of the two seeds.",
            fontsize=10, va="top", family="monospace")
    p = FIGURES_DIR / "textbook_all.png"
    fig.tight_layout()
    fig.savefig(p, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    paths.append(str(p))
    return paths


# =========================================================================== #
# DATA — OSM fetch (synthetic fallback), clean, boundary
# =========================================================================== #
ox.settings.use_cache = True
ox.settings.cache_folder = str(RAW_DIR / "osm_cache")
ox.settings.requests_timeout = 90
ox.settings.log_console = False

RAW_COLUMNS = ["name", "lon", "lat", "source"]
PROCESSED_COLUMNS = ["name", "lon", "lat", "x_m", "y_m", "source"]
_BOUNDARY_PATH = RAW_DIR / "dhaka_boundary.geojson"

_MRT6 = [
    ("Uttara North", 90.4030, 23.8710), ("Uttara Center", 90.4000, 23.8620),
    ("Uttara South", 90.3970, 23.8540), ("Pallabi", 90.3660, 23.8280),
    ("Mirpur 11", 90.3665, 23.8210), ("Mirpur 10", 90.3685, 23.8070),
    ("Kazipara", 90.3720, 23.7980), ("Shewrapara", 90.3760, 23.7900),
    ("Agargaon", 90.3800, 23.7780), ("Bijoy Sarani", 90.3840, 23.7690),
    ("Farmgate", 90.3900, 23.7580), ("Kawran Bazar", 90.3930, 23.7510),
    ("Shahbagh", 90.3960, 23.7390), ("Dhaka University", 90.3970, 23.7330),
    ("Bangladesh Secretariat", 90.4090, 23.7300), ("Motijheel", 90.4180, 23.7280),
]
_HOSPITALS = [
    ("Dhaka Medical College Hospital", 90.3990, 23.7260), ("Square Hospital", 90.3770, 23.7540),
    ("United Hospital", 90.4180, 23.8030), ("Evercare (Apollo) Hospital", 90.4250, 23.8130),
    ("BSMMU", 90.3960, 23.7390), ("BIRDEM General Hospital", 90.3970, 23.7380),
    ("Holy Family Red Crescent", 90.4080, 23.7430), ("Ibn Sina Dhanmondi", 90.3730, 23.7480),
    ("Popular Diagnostic Dhanmondi", 90.3760, 23.7500), ("Labaid Hospital Dhanmondi", 90.3790, 23.7460),
    ("Central Hospital", 90.3810, 23.7530), ("National Heart Foundation", 90.3690, 23.8000),
    ("Kurmitola General Hospital", 90.3970, 23.8400), ("Sher-e-Bangla Nagar Hospital", 90.3680, 23.7770),
    ("Shaheed Suhrawardy Hospital", 90.3690, 23.7760), ("Mugda Medical College", 90.4310, 23.7360),
    ("Sir Salimullah Mitford", 90.4020, 23.7100), ("Bangladesh Medical College", 90.3760, 23.7530),
    ("Delta Health Care Mirpur", 90.3640, 23.7960), ("Green Life Hospital", 90.3830, 23.7490),
    ("Anwer Khan Modern Hospital", 90.3820, 23.7520), ("City Hospital Mirpur", 90.3660, 23.7980),
    ("Uttara Adhunik Medical", 90.3990, 23.8660), ("Shaheed Monsur Ali Uttara", 90.3960, 23.8620),
]
_FIRE = [
    ("Kakrail Fire Station (HQ)", 90.4030, 23.7390), ("Sadarghat Fire Station", 90.4090, 23.7060),
    ("Mirpur Fire Station", 90.3660, 23.8060), ("Mohammadpur Fire Station", 90.3590, 23.7590),
    ("Tejgaon Fire Station", 90.3930, 23.7620), ("Postagola Fire Station", 90.4340, 23.6960),
    ("Lalbagh Fire Station", 90.3880, 23.7180), ("Kurmitola Fire Station", 90.3980, 23.8380),
    ("Baridhara Fire Station", 90.4180, 23.7960), ("Uttara Fire Station", 90.3990, 23.8690),
    ("Khilgaon Fire Station", 90.4260, 23.7500), ("Demra Fire Station", 90.4560, 23.7110),
]
_LANDMARKS = {"metro_station": _MRT6, "hospital": _HOSPITALS, "fire_station": _FIRE}
_DISTRIBUTED_COUNT = {"water_pump": 28, "fuel": 40, "bus_stop": 72}


def _synthetic_distributed(key: str, n: int) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED + hash(key) % 10_000)
    centres = np.array([z["center"] for z in ZONES.values()])
    minlon, minlat, maxlon, maxlat = DHAKA_BBOX
    rows, i = [], 0
    while len(rows) < n:
        c = centres[rng.integers(len(centres))]
        lon, lat = c[0] + rng.normal(0, 0.018), c[1] + rng.normal(0, 0.014)
        if minlon <= lon <= maxlon and minlat <= lat <= maxlat:
            rows.append((f"{key} #{i + 1}", lon, lat, "SYNTHETIC"))
            i += 1
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def _synthetic_landmarks(key: str) -> pd.DataFrame:
    lm = _LANDMARKS.get(key)
    if lm is None:
        return _synthetic_distributed(key, _DISTRIBUTED_COUNT.get(key, 20))
    return pd.DataFrame([(n, lo, la, "SYNTHETIC") for n, lo, la in lm], columns=RAW_COLUMNS)


def _osm_points(key: str):
    svc = SERVICE_TYPES[key]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gdf = ox.features_from_bbox(DHAKA_BBOX, tags=svc.osm_tags)
    except Exception as exc:
        print(f"    [OSM] {key}: fetch failed ({type(exc).__name__}) -> synthetic")
        return None
    if gdf is None or len(gdf) == 0:
        return None
    pts = gdf.to_crs(CRS_METRIC).representative_point().to_crs(CRS_GEO)
    names = gdf["name"] if "name" in gdf.columns else pd.Series([None] * len(gdf))
    rows = []
    for k, (name, geom) in enumerate(zip(names.tolist(), pts.tolist())):
        label = name if isinstance(name, str) and name.strip() else f"{key} #{k + 1}"
        rows.append((label, float(geom.x), float(geom.y), "OSM"))
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def fetch_service(key: str, use_cache: bool = True) -> pd.DataFrame:
    raw_path = RAW_DIR / f"{key}.csv"
    if use_cache and raw_path.exists():
        return pd.read_csv(raw_path)
    svc = SERVICE_TYPES[key]
    frames = []
    osm = _osm_points(key)
    if osm is not None:
        frames.append(osm)
    if sum(len(f) for f in frames) < svc.min_count:
        frames.append(_synthetic_landmarks(key))
    df = (pd.concat(frames, ignore_index=True) if frames else _synthetic_landmarks(key))[RAW_COLUMNS]
    df.to_csv(raw_path, index=False)
    return df


def get_dhaka_boundary() -> gpd.GeoDataFrame:
    if _BOUNDARY_PATH.exists():
        return gpd.read_file(_BOUNDARY_PATH)
    bbox_poly = box(*DHAKA_BBOX)
    geom, source = bbox_poly, "bbox"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            admin = ox.geocode_to_gdf(DHAKA_ADMIN_QUERY).to_crs(CRS_GEO)
        clipped = admin.geometry.iloc[0].intersection(bbox_poly)
        if not clipped.is_empty and clipped.area > 0.5 * bbox_poly.area:
            geom, source = clipped, "OSM admin ∩ bbox"
    except Exception as exc:
        print(f"    [boundary] OSM geocode failed ({type(exc).__name__}); using bbox")
    gdf = gpd.GeoDataFrame({"name": ["Dhaka study area"], "source": [source]},
                           geometry=[geom], crs=CRS_GEO)
    gdf.to_file(_BOUNDARY_PATH, driver="GeoJSON")
    return gdf


def boundary_metric():
    return get_dhaka_boundary().to_crs(CRS_METRIC).geometry.iloc[0]


def _to_metric(df: pd.DataFrame) -> pd.DataFrame:
    g = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df["lon"], df["lat"]),
                         crs=CRS_GEO).to_crs(CRS_METRIC)
    df = df.copy()
    df["x_m"], df["y_m"] = g.geometry.x.to_numpy(), g.geometry.y.to_numpy()
    return df


def _drop_near_duplicates(df: pd.DataFrame, min_dist: float) -> pd.DataFrame:
    coords = df[["x_m", "y_m"]].to_numpy()
    kept: list[int] = []
    for i in range(len(coords)):
        if all(np.hypot(*(coords[i] - coords[j])) >= min_dist for j in kept):
            kept.append(i)
    return df.iloc[kept].reset_index(drop=True)


def clean_service(key: str, poly=None) -> pd.DataFrame:
    df = _to_metric(fetch_service(key))
    df = _drop_near_duplicates(df, MIN_SEED_DISTANCE)
    if poly is None:
        poly = boundary_metric()
    inside = gpd.GeoSeries(gpd.points_from_xy(df["x_m"], df["y_m"]),
                           crs=CRS_METRIC).within(poly.buffer(1.0))
    df = df[inside.to_numpy()].reset_index(drop=True)[PROCESSED_COLUMNS]
    df.to_csv(PROCESSED_DIR / f"{key}.csv", index=False)
    return df


def load_points(key: str) -> pd.DataFrame:
    p = PROCESSED_DIR / f"{key}.csv"
    return pd.read_csv(p) if p.exists() else clean_service(key)


# =========================================================================== #
# DHAKA VORONOI
# =========================================================================== #
@dataclass
class ServiceVoronoi:
    key: str
    seeds: np.ndarray
    names: list[str]
    sources: list[str]
    cells: dict[int, Polygon | MultiPolygon]
    boundary: Polygon | MultiPolygon
    bbox: BBox = field(default=(0, 0, 0, 0))

    @property
    def n(self) -> int:
        return len(self.seeds)

    def cells_gdf(self) -> gpd.GeoDataFrame:
        rows = [{"seed_index": i, "name": self.names[i], "source": self.sources[i],
                 "x_m": float(self.seeds[i, 0]), "y_m": float(self.seeds[i, 1]),
                 "area_km2": p.area / 1e6, "geometry": p} for i, p in self.cells.items()]
        return gpd.GeoDataFrame(rows, crs=CRS_METRIC)

    def seeds_gdf(self) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame({"name": self.names, "source": self.sources},
                                geometry=gpd.points_from_xy(self.seeds[:, 0], self.seeds[:, 1]),
                                crs=CRS_METRIC)


def build_service_voronoi(key: str, boundary=None) -> ServiceVoronoi:
    df = load_points(key)
    seeds = df[["x_m", "y_m"]].to_numpy()
    if boundary is None:
        boundary = boundary_metric()
    bbox = tuple(boundary.bounds)
    vor = compute_voronoi(seeds)
    rect = clip_voronoi_to_box(vor, bbox)
    cells = {}
    for idx, poly in rect.items():
        c = poly.intersection(boundary)
        if not c.is_empty and c.area > 0:
            cells[idx] = c
    return ServiceVoronoi(key, seeds, df["name"].tolist(), df["source"].tolist(),
                          cells, boundary, bbox)


# =========================================================================== #
# COVERAGE
# =========================================================================== #
@dataclass
class CoverageResult:
    key: str
    cell_areas_km2: dict[int, float]
    mean_area_km2: float
    std_area_km2: float
    underserved_cells: list[int]
    grid_xy: np.ndarray
    grid_nn_m: np.ndarray
    threshold_m: float
    mean_nn_m: float
    p90_nn_m: float
    max_nn_m: float
    frac_grid_underserved: float


def make_grid(boundary, spacing: float = GRID_SPACING_M) -> np.ndarray:
    minx, miny, maxx, maxy = boundary.bounds
    gx, gy = np.meshgrid(np.arange(minx, maxx, spacing), np.arange(miny, maxy, spacing))
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    return pts[shapely.contains_xy(boundary, pts[:, 0], pts[:, 1])]


def nearest_distance(grid_xy: np.ndarray, seeds: np.ndarray) -> np.ndarray:
    return KDTree(seeds).query(grid_xy, k=1)[0]


def compute_coverage(sv: ServiceVoronoi) -> CoverageResult:
    areas = {i: p.area / 1e6 for i, p in sv.cells.items()}
    a = np.array(list(areas.values()))
    mean_a, std_a = float(a.mean()), float(a.std())
    under = [i for i, km2 in areas.items() if km2 > mean_a + std_a]
    grid = make_grid(sv.boundary)
    nn = nearest_distance(grid, sv.seeds)
    thr = SERVICE_TYPES[sv.key].underserved_m
    return CoverageResult(sv.key, areas, mean_a, std_a, under, grid, nn, thr,
                          float(nn.mean()), float(np.percentile(nn, 90)),
                          float(nn.max()), float((nn > thr).mean()))


def metrics_row(sv: ServiceVoronoi, cov: CoverageResult) -> dict:
    a = np.array(list(cov.cell_areas_km2.values()))
    return {"service": sv.key, "label": SERVICE_TYPES[sv.key].label,
            "n_facilities": sv.n, "total_area_km2": round(float(a.sum()), 2),
            "mean_cell_km2": round(cov.mean_area_km2, 3),
            "max_cell_km2": round(float(a.max()), 3),
            "n_underserved_cells": len(cov.underserved_cells),
            "threshold_m": cov.threshold_m, "mean_nn_m": round(cov.mean_nn_m, 1),
            "p90_nn_m": round(cov.p90_nn_m, 1), "max_nn_m": round(cov.max_nn_m, 1),
            "pct_grid_underserved": round(100 * cov.frac_grid_underserved, 1)}


# =========================================================================== #
# ZONES
# =========================================================================== #
@dataclass(frozen=True)
class ZoneRef:
    names: list[str]
    colors: list[str]
    centers_m: np.ndarray


def zone_reference() -> ZoneRef:
    names = list(ZONES)
    colors = [ZONES[n]["color"] for n in names]
    lonlat = np.array([ZONES[n]["center"] for n in names])
    gs = gpd.GeoSeries(gpd.points_from_xy(lonlat[:, 0], lonlat[:, 1]),
                       crs=CRS_GEO).to_crs(CRS_METRIC)
    return ZoneRef(names, colors, np.column_stack([gs.x.to_numpy(), gs.y.to_numpy()]))


def assign_zones(seeds: np.ndarray, ref: ZoneRef):
    _, idx = KDTree(ref.centers_m).query(seeds, k=1)
    return [ref.names[i] for i in idx], [ref.colors[i] for i in idx]


def color_cells_by_zone(sv: ServiceVoronoi, ref: ZoneRef) -> gpd.GeoDataFrame:
    idxs = sorted(sv.cells)
    names, colors = assign_zones(sv.seeds[idxs], ref)
    rows = [{"seed_index": i, "zone_name": zn, "zone_color": zc,
             "area_km2": sv.cells[i].area / 1e6, "geometry": sv.cells[i]}
            for i, zn, zc in zip(idxs, names, colors)]
    return gpd.GeoDataFrame(rows, crs=CRS_METRIC)


def build_zone_voronoi(boundary, ref: ZoneRef) -> gpd.GeoDataFrame:
    vor = compute_voronoi(ref.centers_m)
    rect = clip_voronoi_to_box(vor, tuple(boundary.bounds))
    rows = []
    for idx, poly in rect.items():
        c = poly.intersection(boundary)
        if not c.is_empty and c.area > 0:
            rows.append({"zone_name": ref.names[idx], "zone_color": ref.colors[idx], "geometry": c})
    return gpd.GeoDataFrame(rows, crs=CRS_METRIC)


# =========================================================================== #
# RECOMMEND — greedy farthest-point placement
# =========================================================================== #
@dataclass
class Snapshot:
    max_nn_m: float
    mean_nn_m: float
    n_underserved: int
    underserved_people: float = 0.0


@dataclass
class RecommendResult:
    key: str
    k: int
    new_points_m: np.ndarray
    new_points_lonlat: np.ndarray
    new_zones: list[str]
    threshold_m: float
    before: Snapshot
    after: Snapshot

    @property
    def max_improvement_m(self) -> float:
        return self.before.max_nn_m - self.after.max_nn_m


def _snapshot(grid, seeds, thr, pop) -> Snapshot:
    d = KDTree(seeds).query(grid)[0]
    under = d > thr
    return Snapshot(float(d.max()), float(d.mean()), int(under.sum()),
                    float(pop[under].sum()))


def greedy_new_facilities(sv: ServiceVoronoi, cov: CoverageResult,
                          ref: ZoneRef | None = None, k: int = RECOMMEND_K,
                          pop: np.ndarray | None = None) -> RecommendResult:
    """Greedy new-facility placement.

    With a ``pop`` weight per grid point, each new site is the most-populated
    still-underserved location (targets people); without it, the farthest-point
    heuristic (targets the worst-case distance)."""
    ref = ref or zone_reference()
    grid, thr = cov.grid_xy, cov.threshold_m
    snap_pop = pop if pop is not None else np.ones(len(grid))
    before = _snapshot(grid, sv.seeds, thr, snap_pop)
    current, new_pts = sv.seeds.copy(), []
    for _ in range(k):
        d = KDTree(current).query(grid)[0]
        if pop is None:
            idx = int(np.argmax(d))                       # farthest-point
        else:
            score = np.where(d > thr, pop, 0.0)           # most underserved people
            idx = int(np.argmax(score)) if score.max() > 0 else int(np.argmax(d))
        new_pts.append(grid[idx])
        current = np.vstack([current, grid[idx]])
    after = _snapshot(grid, current, thr, snap_pop)
    new_m = np.array(new_pts)
    ll = gpd.GeoSeries(gpd.points_from_xy(new_m[:, 0], new_m[:, 1]),
                       crs=CRS_METRIC).to_crs(CRS_GEO)
    new_lonlat = np.column_stack([ll.x.to_numpy(), ll.y.to_numpy()])
    zones, _ = assign_zones(new_m, ref)
    return RecommendResult(sv.key, k, new_m, new_lonlat, zones, thr, before, after)


# =========================================================================== #
# SECTION BENEFIT (population + critical-service weighted)
# =========================================================================== #
def get_population_raster():
    """Download+cache the WorldPop raster; return its path, or None if offline."""
    if POP_RASTER_PATH.exists():
        return POP_RASTER_PATH
    try:
        import urllib.request
        print("    [pop] downloading WorldPop Bangladesh raster ...")
        urllib.request.urlretrieve(POP_RASTER_URL, POP_RASTER_PATH)
        return POP_RASTER_PATH
    except Exception as exc:
        print(f"    [pop] download failed ({type(exc).__name__}); using area weighting")
        return None


def _grid_lonlat(grid: np.ndarray):
    gs = gpd.GeoSeries(gpd.points_from_xy(grid[:, 0], grid[:, 1]),
                       crs=CRS_METRIC).to_crs(CRS_GEO)
    return list(zip(gs.x.to_numpy(), gs.y.to_numpy()))


def sample_population(grid: np.ndarray):
    """People per grid cell at each metric grid point (0 where nodata).

    WorldPop values are people per ~1 km pixel; each grid cell covers
    ``(GRID_SPACING_M/1000)**2`` of a pixel, so we scale to real per-cell counts
    (their sum then approximates the true population)."""
    import rasterio
    path = get_population_raster()
    if path is None:
        return None
    with rasterio.open(path) as src:
        vals = np.array([float(v[0]) for v in src.sample(_grid_lonlat(grid))])
    vals = np.where(vals < 0, 0.0, vals)
    return vals * (GRID_SPACING_M / 1000.0) ** 2


@dataclass
class SectionBenefit:
    df: pd.DataFrame               # section, pop_est, benefit_score, weakest_service
    names: list[str]               # section names in native (index) order
    per_service_frac: dict         # service key -> (nsec,) well-served fraction
    underserved_people: dict       # service key -> (nsec,) underserved population
    section_pop: np.ndarray | None
    pop_weighted: bool


def section_benefit(voronois: dict[str, ServiceVoronoi], ref: ZoneRef,
                    pop: np.ndarray | None = None) -> SectionBenefit:
    """Score each section by how well its people are served, weighting critical
    services higher and (if available) weighting locations by population."""
    boundary = next(iter(voronois.values())).boundary
    grid = make_grid(boundary)
    sec = KDTree(ref.centers_m).query(grid)[1]
    nsec = len(ref.names)

    if pop is None:
        pop = sample_population(grid)
    pop_weighted = pop is not None
    weights = pop if pop_weighted else np.ones(len(grid))
    sec_pop = (np.array([weights[sec == i].sum() for i in range(nsec)])
               if pop_weighted else None)
    grid_count = np.array([(sec == i).sum() for i in range(nsec)], dtype=float)

    comp = np.zeros(nsec)
    wsum = sum(SERVICE_WEIGHT.values())
    per_service, under_people = {}, {}
    weak_name = [""] * nsec
    weak_val = [np.inf] * nsec
    for key, sv in voronois.items():
        thr = SERVICE_TYPES[key].underserved_m
        well = (nearest_distance(grid, sv.seeds) <= thr).astype(float)
        frac = np.full(nsec, np.nan)
        for i in range(nsec):
            m = sec == i
            W = weights[m].sum()
            frac[i] = (weights[m] * well[m]).sum() / W if W > 0 else np.nan
        per_service[key] = frac
        comp += SERVICE_WEIGHT[key] * np.nan_to_num(frac)
        underfrac = 1.0 - np.nan_to_num(frac)
        under_people[key] = underfrac * (sec_pop if pop_weighted else grid_count)
        for i in range(nsec):
            if frac[i] < weak_val[i]:
                weak_val[i], weak_name[i] = frac[i], SERVICE_TYPES[key].label
    comp = comp / wsum * 100.0

    rows = [{"section": s, "pop_est": int(sec_pop[i]) if pop_weighted else None,
             "benefit_score": round(float(comp[i]), 1), "weakest_service": weak_name[i]}
            for i, s in enumerate(ref.names)]
    df = pd.DataFrame(rows).sort_values("benefit_score", ascending=False).reset_index(drop=True)
    return SectionBenefit(df, list(ref.names), per_service, under_people, sec_pop, pop_weighted)


# =========================================================================== #
# EXTENDED ANALYSES (equity, combined access, sensitivity, density)
# =========================================================================== #
def _proximity(nn_m: np.ndarray, thr_m: float) -> np.ndarray:
    """Access score in [0, 1]: 1 at a facility, 0 at or beyond twice the threshold."""
    return np.clip(1.0 - nn_m / (2.0 * thr_m), 0.0, 1.0)


def weighted_gini(x: np.ndarray, w: np.ndarray) -> float:
    """Population-weighted Gini coefficient of a non-negative 'good' (0 = equal)."""
    x = np.asarray(x, float)
    w = np.asarray(w, float)
    order = np.argsort(x)
    x, w = x[order], w[order]
    cw = np.cumsum(w)
    cxw = np.cumsum(x * w)
    if cxw[-1] <= 0:
        return 0.0
    lx = np.concatenate([[0.0], cw / cw[-1]])
    ly = np.concatenate([[0.0], cxw / cxw[-1]])
    return float(1.0 - 2.0 * np.trapezoid(ly, lx))


def _benefit_scores(voronois, ref, weights, sec, grid, thr_mult=1.0, svc_weights=None):
    """Per-section pop-weighted, critical-weighted benefit score (for sensitivity)."""
    svc_weights = svc_weights or SERVICE_WEIGHT
    nsec = len(ref.names)
    comp = np.zeros(nsec)
    wsum = sum(svc_weights.values())
    for key, sv in voronois.items():
        thr = SERVICE_TYPES[key].underserved_m * thr_mult
        well = (nearest_distance(grid, sv.seeds) <= thr).astype(float)
        for i in range(nsec):
            m = sec == i
            W = weights[m].sum()
            frac = (weights[m] * well[m]).sum() / W if W > 0 else 0.0
            comp[i] += svc_weights[key] * frac
    return comp / wsum * 100.0


def two_sfca(voronois, ref, weights, sec, grid):
    """Two-step floating catchment area accessibility (Luo & Wang 2003) per service.

    Returns (per_section_by_service, agreement_df). Step 1: each facility's
    supply-to-demand ratio over the population in its catchment. Step 2: sum the
    ratios of facilities reachable from each location. Compared (Spearman ρ)
    against the Voronoi nearest-distance ranking to validate the method."""
    from scipy.stats import spearmanr
    nsec = len(ref.names)
    per_section, agreement = {}, []
    for key, sv in voronois.items():
        thr = SERVICE_TYPES[key].underserved_m
        fac = sv.seeds
        gtree, ftree = KDTree(grid), KDTree(fac)
        demand_of_fac = gtree.query_ball_point(fac, r=thr)          # step 1
        ratio = np.array([1e5 / max(weights[idx].sum(), 1e-9) for idx in demand_of_fac])
        fac_of_grid = ftree.query_ball_point(grid, r=thr)           # step 2
        access = np.array([ratio[j].sum() if len(j) else 0.0 for j in fac_of_grid])
        per_section[key] = {ref.names[i]:
                            float((weights[sec == i] * access[sec == i]).sum()
                                  / max(weights[sec == i].sum(), 1e-9)) for i in range(nsec)}
        nn = nearest_distance(grid, fac)
        vor_sec = np.array([(weights[sec == i] * nn[sec == i]).sum()
                            / max(weights[sec == i].sum(), 1e-9) for i in range(nsec)])
        ts_sec = np.array([per_section[key][ref.names[i]] for i in range(nsec)])
        rho = spearmanr(-vor_sec, ts_sec).correlation
        agreement.append({"service": SERVICE_TYPES[key].label,
                          "spearman_vs_voronoi": round(float(rho), 3)})
    return per_section, pd.DataFrame(agreement)


def moran_i(coords, x, k=8, perms=199):
    """Global Moran's I of ``x`` over ``coords`` with row-standardised KNN weights.

    Returns (I, pseudo_p). I > 0 means similar values cluster spatially; the
    pseudo p-value comes from a permutation test (one-sided, clustering)."""
    x = np.asarray(x, float)
    z = x - x.mean()
    if (z * z).sum() == 0:
        return 0.0, 1.0
    nbr = KDTree(coords).query(coords, k=k + 1)[1][:, 1:]

    def stat(zz):
        return float((zz * zz[nbr].mean(axis=1)).sum() / (zz * zz).sum())

    obs = stat(z)
    rng = np.random.default_rng(RANDOM_SEED)
    perm = np.array([stat(rng.permutation(z)) for _ in range(perms)])
    p = (1 + int((perm >= obs).sum())) / (perms + 1)
    return obs, float(p)


def mclp_greedy_vs_optimal(voronois, weights, grid, k=RECOMMEND_K, n_candidates=22):
    """Compare the greedy recommender to the exact Maximal Covering optimum.

    On a candidate set (the most-populated underserved cells per service), both
    the greedy heuristic and an exhaustive search pick k sites to cover the most
    underserved population. Shows the greedy solution is near-optimal (Church &
    ReVelle, 1974)."""
    from itertools import combinations
    rows = []
    for key, sv in voronois.items():
        thr = SERVICE_TYPES[key].underserved_m
        under = nearest_distance(grid, sv.seeds) > thr
        demand = weights * under
        cand_idx = np.argsort(demand)[::-1][:n_candidates]
        cand = grid[cand_idx]
        cover = np.zeros((len(cand), len(grid)), bool)
        for c, idx in enumerate(KDTree(grid).query_ball_point(cand, r=thr)):
            cover[c, idx] = True
        # greedy
        chosen, covered = [], np.zeros(len(grid), bool)
        for _ in range(k):
            gains = [(-1 if c in chosen else (demand * (cover[c] & ~covered)).sum())
                     for c in range(len(cand))]
            b = int(np.argmax(gains))
            chosen.append(b)
            covered |= cover[b]
        greedy_cov = float((demand * covered).sum())
        # exact
        best = 0.0
        for combo in combinations(range(len(cand)), k):
            v = float((demand * cover[list(combo)].any(0)).sum())
            best = max(best, v)
        rows.append({"service": SERVICE_TYPES[key].label,
                     "greedy_covered_k": round(greedy_cov / 1000, 0),
                     "optimal_covered_k": round(best / 1000, 0),
                     "greedy_pct_of_optimal": round(100 * greedy_cov / max(best, 1e-9), 1)})
    return pd.DataFrame(rows)


@dataclass
class ExtendedAnalysis:
    combined_by_section: dict         # section -> mean composite access [0,1]
    gini_by_service: dict             # service -> Gini of access
    gini_combined: float
    lorenz: tuple                     # (Lx, Ly) for the combined index
    density: pd.DataFrame             # per-service counts and densities
    sensitivity: pd.DataFrame         # ranking stability under scenarios
    tsfca_by_section: dict            # service -> {section -> 2SFCA accessibility}
    tsfca_agreement: pd.DataFrame     # 2SFCA vs Voronoi ranking correlation
    mclp: pd.DataFrame                # greedy vs exact optimal facility placement
    moran: tuple                      # (Moran's I, pseudo p-value) of combined access


def extended_analysis(voronois, ref, pop) -> ExtendedAnalysis:
    boundary = next(iter(voronois.values())).boundary
    grid = make_grid(boundary)
    sec = KDTree(ref.centers_m).query(grid)[1]
    weights = pop if pop is not None else np.ones(len(grid))
    total_pop = float(weights.sum())
    area_km2 = boundary.area / 1e6

    # combined "any-service" access index + per-service equity (Gini)
    comb = np.zeros(len(grid))
    wsum = sum(SERVICE_WEIGHT.values())
    gini_svc = {}
    for key, sv in voronois.items():
        thr = SERVICE_TYPES[key].underserved_m
        px = _proximity(nearest_distance(grid, sv.seeds), thr)
        gini_svc[key] = weighted_gini(px, weights)
        comb += SERVICE_WEIGHT[key] * px
    comb /= wsum
    gini_comb = weighted_gini(comb, weights)

    order = np.argsort(comb)
    w_ord, y_ord = weights[order], comb[order]
    lx = np.concatenate([[0.0], np.cumsum(w_ord) / w_ord.sum()])
    ly = np.concatenate([[0.0], np.cumsum(y_ord * w_ord) / (y_ord * w_ord).sum()])
    comb_sec = {ref.names[i]: float((weights[sec == i] * comb[sec == i]).sum()
                                    / max(weights[sec == i].sum(), 1e-9))
                for i in range(len(ref.names))}

    # data density / completeness
    rows = []
    for key, sv in voronois.items():
        rows.append({"service": SERVICE_TYPES[key].label, "facilities": sv.n,
                     "min_expected": SERVICE_TYPES[key].min_count,
                     "per_100k_people": round(sv.n / (total_pop / 1e5), 2),
                     "km2_per_facility": round(area_km2 / sv.n, 2)})
    density = pd.DataFrame(rows)

    # sensitivity: how stable is the section ranking to thresholds / weights?
    from scipy.stats import spearmanr
    base = _benefit_scores(voronois, ref, weights, sec, grid)
    scenarios = {"thresholds -25%": dict(thr_mult=0.75),
                 "thresholds +25%": dict(thr_mult=1.25),
                 "equal weights": dict(svc_weights={k: 1.0 for k in SERVICE_TYPES})}
    srows = [{"scenario": "baseline", "rank_corr_vs_baseline": 1.0,
              "best": ref.names[int(np.argmax(base))], "worst": ref.names[int(np.argmin(base))]}]
    for name, kw in scenarios.items():
        sc = _benefit_scores(voronois, ref, weights, sec, grid, **kw)
        rho = float(spearmanr(base, sc).correlation)
        srows.append({"scenario": name, "rank_corr_vs_baseline": round(rho, 3),
                      "best": ref.names[int(np.argmax(sc))], "worst": ref.names[int(np.argmin(sc))]})
    sensitivity = pd.DataFrame(srows)

    tsfca_sec, tsfca_agree = two_sfca(voronois, ref, weights, sec, grid)
    mclp = mclp_greedy_vs_optimal(voronois, weights, grid)
    moran = moran_i(grid, comb)
    return ExtendedAnalysis(comb_sec, gini_svc, gini_comb, (lx, ly), density, sensitivity,
                            tsfca_sec, tsfca_agree, mclp, moran)


# =========================================================================== #
# NETWORK (road) DISTANCE  (opt-in: python voronoi_dhaka.py --network)
# =========================================================================== #
_ROAD_GRAPH_PATH = RAW_DIR / "dhaka_drive.graphml"


def get_road_graph():
    """Load/cache the Dhaka drive network, projected to the metric CRS.

    Returns (G, node_list, node_xy, KDTree) or None if the download fails."""
    import networkx as nx  # noqa: F401 (imported for callers / clarity)
    try:
        if _ROAD_GRAPH_PATH.exists():
            G = ox.load_graphml(_ROAD_GRAPH_PATH)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                G = ox.graph_from_bbox(DHAKA_BBOX, network_type="drive", simplify=True)
                G = ox.project_graph(G, to_crs=CRS_METRIC)
            ox.save_graphml(G, _ROAD_GRAPH_PATH)
    except Exception as exc:
        print(f"    [network] road graph unavailable ({type(exc).__name__})")
        return None
    nodes = list(G.nodes)
    xy = np.array([[float(G.nodes[n]["x"]), float(G.nodes[n]["y"])] for n in nodes])
    return G, nodes, xy, KDTree(xy)


def network_nearest_distance(bundle, grid, facilities) -> np.ndarray:
    """Road-network distance (m) from each grid point to the nearest facility."""
    import networkx as nx
    G, nodes, xy, tree = bundle
    fac_nodes = {nodes[i] for i in tree.query(facilities)[1]}
    dist = nx.multi_source_dijkstra_path_length(G, fac_nodes, weight="length")
    snap_d, gi = tree.query(grid)
    out = np.array([dist.get(nodes[i], np.inf) for i in gi], dtype=float)
    return out + snap_d


def network_analysis(voronois, pop):
    """Compare road-network vs straight-line access; writes a table + figure."""
    print("[network] building road network + shortest paths (this takes a minute)")
    bundle = get_road_graph()
    if bundle is None:
        return None
    boundary = next(iter(voronois.values())).boundary
    grid = make_grid(boundary)
    weights = pop if pop is not None else np.ones(len(grid))
    rows = []
    for key, sv in voronois.items():
        euc = nearest_distance(grid, sv.seeds)
        net = network_nearest_distance(bundle, grid, sv.seeds)
        ok = np.isfinite(net)
        thr = SERVICE_TYPES[key].underserved_m
        rows.append({
            "service": SERVICE_TYPES[key].label,
            "median_detour": round(float(np.median(net[ok] / np.maximum(euc[ok], 1.0))), 2),
            "pct_under_euclid": round(100 * float((weights * (euc > thr)).sum() / weights.sum()), 1),
            "pct_under_network": round(100 * float((weights * ((net > thr) | ~ok)).sum()
                                                   / weights.sum()), 1)})
        print(f"    {SERVICE_TYPES[key].label:20s} detour x{rows[-1]['median_detour']}  "
              f"underserved {rows[-1]['pct_under_euclid']}% -> {rows[-1]['pct_under_network']}%")
    df = pd.DataFrame(rows)
    df.to_csv(PROCESSED_DIR / "network_comparison.csv", index=False)
    plot_network_comparison(df)
    return df


# =========================================================================== #
# VIZ
# =========================================================================== #
def _add_basemap(ax) -> None:
    """Draw a real Dhaka street map under the axes (coloured roads + labels)."""
    for source in (cx.providers.CartoDB.Voyager, cx.providers.CartoDB.Positron):
        try:
            cx.add_basemap(ax, crs=WEB, source=source, attribution_size=5)
            return
        except Exception as exc:
            print(f"    [basemap] {source.get('name', '?')} failed ({type(exc).__name__})")
    print("    [basemap] skipped (offline)")


def _boundary_web(sv): return gpd.GeoSeries([sv.boundary], crs=CRS_METRIC).to_crs(WEB)
def _seeds_web(sv): return sv.seeds_gdf().to_crs(WEB)


def plot_service_voronoi(sv: ServiceVoronoi, cov: CoverageResult) -> str:
    svc = SERVICE_TYPES[sv.key]
    ref = zone_reference()
    zgdf = color_cells_by_zone(sv, ref).to_crs(WEB)
    fig, ax = plt.subplots(figsize=(10, 11))
    # cells coloured by their named section (flagship style)
    zgdf.plot(ax=ax, color=zgdf["zone_color"].tolist(), alpha=0.55,
              edgecolor="#333333", linewidth=0.4)
    under = zgdf[zgdf["seed_index"].isin(cov.underserved_cells)]
    if len(under):
        under.boundary.plot(ax=ax, color="#b30000", linewidth=2.0)
    # bold dashed section boundaries + labels
    build_zone_voronoi(sv.boundary, ref).to_crs(WEB).boundary.plot(
        ax=ax, color="#111111", linewidth=1.4, linestyle=(0, (5, 3)))
    # facilities in this utility's own colour
    _seeds_web(sv).plot(ax=ax, color=svc.color, markersize=16, marker="o",
                        edgecolor="white", linewidth=0.5, zorder=5)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.3)
    centers = gpd.GeoSeries(gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
                            crs=CRS_METRIC).to_crs(WEB)
    for name, pt in zip(ref.names, centers):
        ax.annotate(name, (pt.x, pt.y), ha="center", va="center", fontsize=10,
                    fontweight="bold", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#333", alpha=0.8))
    _add_basemap(ax)
    ax.set_title(f"Dhaka {svc.label} — Voronoi coverage ({sv.n} facilities)\n"
                 f"cells coloured by section · {svc.label.lower()} sites in "
                 "service colour · red outline = underserved", fontsize=12)
    ax.set_axis_off()
    out = FIGURES_DIR / f"voronoi_{sv.key}.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_recommendations(sv: ServiceVoronoi, rec: RecommendResult) -> str:
    svc = SERVICE_TYPES[sv.key]
    seeds_after = np.vstack([sv.seeds, rec.new_points_m])
    vor = compute_voronoi(seeds_after)
    rect = clip_voronoi_to_box(vor, sv.bbox)
    polys = [poly.intersection(sv.boundary) for poly in rect.values()]
    polys = [p for p in polys if not p.is_empty and p.area > 0]
    improved = gpd.GeoSeries(polys, crs=CRS_METRIC).to_crs(WEB)
    fig, ax = plt.subplots(figsize=(10, 11))
    improved.boundary.plot(ax=ax, color="#666666", linewidth=0.5)
    _seeds_web(sv).plot(ax=ax, color="#1f77b4", markersize=12, marker="o", label="existing", zorder=5)
    new_web = gpd.GeoSeries(gpd.points_from_xy(rec.new_points_m[:, 0], rec.new_points_m[:, 1]),
                            crs=CRS_METRIC).to_crs(WEB)
    new_web.plot(ax=ax, color="#d62728", markersize=170, marker="*",
                 edgecolor="black", linewidth=0.6, label="proposed", zorder=6)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.3)
    _add_basemap(ax)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title(f"Dhaka {svc.label} — {rec.k} proposed new sites (population-targeted)\n"
                 f"underserved people {rec.before.underserved_people/1000:.0f}k → "
                 f"{rec.after.underserved_people/1000:.0f}k", fontsize=12)
    ax.set_axis_off()
    out = FIGURES_DIR / f"recommendations_{sv.key}.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def _zone_legend_handles(ref: ZoneRef):
    return [Patch(facecolor=c, edgecolor="#333", label=n, alpha=0.7)
            for n, c in zip(ref.names, ref.colors)]


def plot_zone_colored_voronoi(sv: ServiceVoronoi, ref: ZoneRef, flagship: bool = False) -> str:
    svc = SERVICE_TYPES[sv.key]
    zgdf = color_cells_by_zone(sv, ref).to_crs(WEB)
    fig, ax = plt.subplots(figsize=(11, 12))
    zgdf.plot(ax=ax, color=zgdf["zone_color"].tolist(), alpha=0.55,
              edgecolor="#333333", linewidth=0.4)
    build_zone_voronoi(sv.boundary, ref).to_crs(WEB).boundary.plot(
        ax=ax, color="#111111", linewidth=1.4, linestyle=(0, (5, 3)))
    _seeds_web(sv).plot(ax=ax, color=svc.color, markersize=14, marker="o",
                        edgecolor="white", linewidth=0.5, zorder=5)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.4)
    centers = gpd.GeoSeries(gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
                            crs=CRS_METRIC).to_crs(WEB)
    for name, pt in zip(ref.names, centers):
        ax.annotate(name, (pt.x, pt.y), ha="center", va="center", fontsize=11,
                    fontweight="bold", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#333", alpha=0.75))
    _add_basemap(ax)
    ax.legend(handles=_zone_legend_handles(ref), title="Dhaka zones",
              loc="upper right", fontsize=8, title_fontsize=9, framealpha=0.9)
    ax.set_title(f"Dhaka Voronoi coloured by named zone — {svc.label} ({sv.n} cells)", fontsize=13)
    ax.set_axis_off()
    name = "zones_dhaka_flagship" if flagship else f"zones_{sv.key}"
    out = FIGURES_DIR / f"{name}.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_section_benefit(voronois: dict[str, ServiceVoronoi], ref: ZoneRef,
                         sb: SectionBenefit) -> str:
    """Choropleth: 8 sections coloured green→red by how well their people are served."""
    boundary = next(iter(voronois.values())).boundary
    zv = build_zone_voronoi(boundary, ref).to_crs(WEB)
    score = dict(zip(sb.df["section"], sb.df["benefit_score"]))
    zv["benefit"] = zv["zone_name"].map(score)

    fig, ax = plt.subplots(figsize=(11, 12))
    zv.plot(ax=ax, column="benefit", cmap="RdYlGn", vmin=50, vmax=95, alpha=0.6,
            edgecolor="#222222", linewidth=1.6, legend=True,
            legend_kwds={"label": "benefit score (% of people well served)", "shrink": 0.5})
    centers = gpd.GeoSeries(gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
                            crs=CRS_METRIC).to_crs(WEB)
    for name, pt in zip(ref.names, centers):
        ax.annotate(f"{name}\n{score.get(name, 0):.0f}", (pt.x, pt.y), ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#333", alpha=0.82))
    _add_basemap(ax)
    weighting = "population + critical-service weighted" if sb.pop_weighted else "area weighted"
    ax.set_title(f"Which Dhaka areas benefit most from utilities\n({weighting})", fontsize=13)
    ax.set_axis_off()
    out = FIGURES_DIR / "section_benefit.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_combined_access(voronois, ref, ext: ExtendedAnalysis) -> str:
    """Choropleth: sections coloured by the combined 'any-service' access index."""
    boundary = next(iter(voronois.values())).boundary
    zv = build_zone_voronoi(boundary, ref).to_crs(WEB)
    zv["access"] = zv["zone_name"].map(ext.combined_by_section)
    fig, ax = plt.subplots(figsize=(11, 12))
    zv.plot(ax=ax, column="access", cmap="RdYlGn", vmin=0.3, vmax=0.85, alpha=0.6,
            edgecolor="#222222", linewidth=1.6, legend=True,
            legend_kwds={"label": "combined access index (0–1, all 6 utilities)", "shrink": 0.5})
    centers = gpd.GeoSeries(gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
                            crs=CRS_METRIC).to_crs(WEB)
    for name, pt in zip(ref.names, centers):
        ax.annotate(f"{name}\n{ext.combined_by_section.get(name, 0):.2f}", (pt.x, pt.y),
                    ha="center", va="center", fontsize=10, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#333", alpha=0.82))
    _add_basemap(ax)
    ax.set_title("Combined utility access across all six services\n"
                 f"(population-weighted; overall Gini = {ext.gini_combined:.3f})", fontsize=13)
    ax.set_axis_off()
    out = FIGURES_DIR / "combined_access.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_lorenz(ext: ExtendedAnalysis) -> str:
    """Lorenz curve of the combined access index (equity of access)."""
    lx, ly = ext.lorenz
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot([0, 1], [0, 1], color="#888888", ls="--", lw=1.2, label="perfect equality")
    ax.plot(lx, ly, color="#0B5394", lw=2.2, label="access distribution")
    ax.fill_between(lx, ly, lx, color="#0B5394", alpha=0.12)
    ax.set_xlabel("cumulative share of population")
    ax.set_ylabel("cumulative share of utility access")
    ax.set_title(f"Lorenz curve of combined utility access\nGini = {ext.gini_combined:.3f} "
                 "(0 = perfectly equal)", fontsize=12)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(alpha=0.25)
    out = FIGURES_DIR / "lorenz_access.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_2sfca(voronois, ref, ext: ExtendedAnalysis, service_key: str) -> str:
    """Choropleth: sections coloured by 2SFCA accessibility for one service."""
    svc = SERVICE_TYPES[service_key]
    boundary = next(iter(voronois.values())).boundary
    zv = build_zone_voronoi(boundary, ref).to_crs(WEB)
    zv["acc"] = zv["zone_name"].map(ext.tsfca_by_section[service_key])
    fig, ax = plt.subplots(figsize=(11, 12))
    zv.plot(ax=ax, column="acc", cmap="viridis", alpha=0.62, edgecolor="#222222", linewidth=1.4,
            legend=True, legend_kwds={"label": "2SFCA accessibility (per 100k within reach)",
                                      "shrink": 0.5})
    centers = gpd.GeoSeries(gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
                            crs=CRS_METRIC).to_crs(WEB)
    for name, pt in zip(ref.names, centers):
        ax.annotate(name, (pt.x, pt.y), ha="center", va="center", fontsize=10, fontweight="bold",
                    color="white", bbox=dict(boxstyle="round,pad=0.2", fc="#00000088", ec="none"))
    _add_basemap(ax)
    ax.set_title(f"2SFCA accessibility to {svc.label.lower()}s (Luo & Wang, 2003)", fontsize=13)
    ax.set_axis_off()
    out = FIGURES_DIR / f"tsfca_{service_key}.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_network_comparison(df) -> str:
    """Grouped bars: underserved population under straight-line vs road-network distance."""
    labels = df["service"].tolist()
    x = np.arange(len(labels))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 6))
    b1 = ax.bar(x - w / 2, df["pct_under_euclid"], w, label="straight-line", color="#1C7293")
    b2 = ax.bar(x + w / 2, df["pct_under_network"], w, label="road network", color="#C0392B")
    ax.bar_label(b1, fmt="%.0f", fontsize=8, padding=2)
    ax.bar_label(b2, fmt="%.0f", fontsize=8, padding=2)
    ax.set_ylabel("% of population underserved")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.set_title("Underserved population: straight-line vs road-network distance")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    out = FIGURES_DIR / "network_vs_euclid.png"
    fig.tight_layout()
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def plot_gantt() -> str:
    """Simple project-timeline Gantt chart for the thesis (Ch. 5)."""
    phases = [
        ("Topic definition & literature review", 0, 3),
        ("Data acquisition & cleaning (OSM, WorldPop)", 2, 3),
        ("Voronoi construction & coverage metrics", 4, 3),
        ("Population-weighted benefit analysis", 6, 2),
        ("Recommendations & method validation", 7, 3),
        ("Extended analyses (2SFCA, equity, network)", 9, 3),
        ("Interactive maps & dashboard", 10, 2),
        ("Thesis documentation", 8, 7),
    ]
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, (name, start, dur) in enumerate(phases):
        ax.barh(i, dur, left=start, height=0.55, color="#1C7293", edgecolor="#0E2A47")
        ax.text(start + dur + 0.15, i, name, va="center", fontsize=9)
    ax.set_yticks([])
    ax.invert_yaxis()
    ax.set_xlabel("Week")
    ax.set_xlim(0, 20)
    ax.set_title("Project timeline (Gantt chart)")
    ax.grid(axis="x", alpha=0.25)
    out = FIGURES_DIR / "gantt.png"
    fig.tight_layout()
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def _map_center(sv):
    c = gpd.GeoSeries([sv.boundary], crs=CRS_METRIC).to_crs(CRS_GEO).iloc[0].centroid
    return [c.y, c.x]


# Google Maps tile layers (lyrs: m=streets, y=hybrid, s=satellite, p=terrain).
_GOOGLE_LAYERS = [("Google Streets", "m"), ("Google Hybrid", "y"),
                  ("Google Satellite", "s"), ("Google Terrain", "p")]


def _google_map(center, zoom: int = 12) -> folium.Map:
    """A folium map whose base layers are live, pan/zoom Google Maps tiles."""
    m = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True)
    for name, lyr in _GOOGLE_LAYERS:
        folium.TileLayer(
            tiles=f"https://{{s}}.google.com/vt/lyrs={lyr}&x={{x}}&y={{y}}&z={{z}}",
            attr="Map data © Google", name=name, max_zoom=20,
            subdomains=["mt0", "mt1", "mt2", "mt3"], overlay=False, control=True,
        ).add_to(m)
    return m


def _emoji_div(emoji: str, color: str, size: int = 24) -> folium.DivIcon:
    """A coloured circular badge with the utility's emoji logo."""
    html = (f'<div style="background:{color};width:{size}px;height:{size}px;'
            'border-radius:50%;border:2px solid white;box-shadow:0 0 3px rgba(0,0,0,.55);'
            'display:flex;align-items:center;justify-content:center;line-height:1;'
            f'font-size:{int(size*0.6)}px;">{emoji}</div>')
    return folium.DivIcon(html=html, icon_size=(size, size), icon_anchor=(size // 2, size // 2))


def _cluster_js(color: str, emoji: str) -> str:
    """Render a MarkerCluster bubble as a coloured badge showing the utility's
    emoji logo (top) and the facility count (below) — legible at any zoom."""
    return ("function(cluster){return L.divIcon({html:'<div style=\"background:" + color +
            ";opacity:.92;width:38px;height:38px;border-radius:50%;border:2px solid white;"
            "color:white;font:bold 11px sans-serif;display:flex;flex-direction:column;"
            "align-items:center;justify-content:center;line-height:1.05;"
            "box-shadow:0 0 4px rgba(0,0,0,.5)\"><span style=\"font-size:14px\">" + emoji +
            "</span>'+cluster.getChildCount()+'</div>',className:'',iconSize:L.point(38,38)});}")


def _add_service_markers(parent, sv: ServiceVoronoi, cluster: bool = True) -> None:
    svc = SERVICE_TYPES[sv.key]
    emoji = SERVICE_EMOJI[sv.key]
    target = parent
    if cluster:
        target = MarkerCluster(icon_create_function=_cluster_js(svc.color, emoji))
        target.add_to(parent)
    for _, r in sv.seeds_gdf().to_crs(CRS_GEO).iterrows():
        folium.Marker([r.geometry.y, r.geometry.x], icon=_emoji_div(emoji, svc.color),
                      popup=f"{svc.label}: {r['name']}").add_to(target)


def _utilities_legend() -> folium.Element:
    rows = "".join(
        f'<div style="margin:2px 0;"><span style="display:inline-block;width:13px;height:13px;'
        f'background:{SERVICE_TYPES[k].color};border-radius:50%;border:1px solid #fff;'
        f'box-shadow:0 0 1px #000;margin-right:6px;vertical-align:middle;"></span>'
        f'{SERVICE_EMOJI[k]} {SERVICE_TYPES[k].label}</div>'
        for k in SERVICE_TYPES)
    html = ('<div style="position:fixed;bottom:22px;left:22px;z-index:9999;background:white;'
            'padding:10px 13px;border:1px solid #888;border-radius:6px;'
            'font:12px/1.35 sans-serif;box-shadow:0 1px 5px rgba(0,0,0,.3);">'
            '<div style="font-weight:bold;margin-bottom:4px;">Dhaka utilities</div>'
            + rows + '</div>')
    return folium.Element(html)


def _section_labels_layer(ref: ZoneRef) -> folium.FeatureGroup:
    centers = gpd.GeoSeries(gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
                            crs=CRS_METRIC).to_crs(CRS_GEO)
    layer = folium.FeatureGroup(name="Section labels", show=True)
    for name_, pt in zip(ref.names, centers):
        folium.Marker([pt.y, pt.x], icon=folium.DivIcon(icon_size=(0, 0), html=(
            '<div style="font:bold 12px sans-serif;color:#111;background:rgba(255,255,255,.82);'
            'padding:1px 6px;border-radius:4px;border:1px solid #444;white-space:nowrap;'
            f'transform:translate(-50%,-50%);display:inline-block;">{name_}</div>'))).add_to(layer)
    return layer


def folium_sections_map(voronois: dict[str, ServiceVoronoi], ref: ZoneRef) -> str:
    """Headline map: Dhaka split into coloured sections, with ALL utilities plotted.

    The sections are the coarse 8-section Voronoi of the zone centres (not tied
    to any one utility). Every utility is overlaid with its own colour + emoji
    logo, each toggleable in the layer switcher.
    """
    any_sv = next(iter(voronois.values()))
    m = _google_map(_map_center(any_sv))

    # coloured main sections (the coarse Voronoi of the zone centres)
    zv = build_zone_voronoi(any_sv.boundary, ref).to_crs(CRS_GEO)
    folium.GeoJson(zv.to_json(), name="Sections (coloured)",
        style_function=lambda f: {"fillColor": f["properties"]["zone_color"],
                                  "color": "#111111", "weight": 2.5, "fillOpacity": 0.16},
        tooltip=folium.GeoJsonTooltip(fields=["zone_name"], aliases=["Section"])).add_to(m)
    _section_labels_layer(ref).add_to(m)

    # every utility: own colour + logo, clustered, individually toggleable
    for key, sv in voronois.items():
        svc = SERVICE_TYPES[key]
        fg = folium.FeatureGroup(name=f"{SERVICE_EMOJI[key]} {svc.label} ({sv.n})", show=True)
        _add_service_markers(fg, sv, cluster=True)
        fg.add_to(m)

    m.get_root().html.add_child(_utilities_legend())
    m.get_root().html.add_child(_sections_legend(ref))
    folium.LayerControl(collapsed=False).add_to(m)
    out = REPORT_DIR / "interactive_dhaka_map.html"
    m.save(str(out))
    return str(out)


def folium_service_map(sv: ServiceVoronoi, cov: CoverageResult, rec: RecommendResult) -> str:
    svc = SERVICE_TYPES[sv.key]
    m = _google_map(_map_center(sv))
    cells = sv.cells_gdf().to_crs(CRS_GEO)
    areas = cells["area_km2"]
    cmap = bcm.linear.YlOrRd_09.scale(float(areas.min()), float(areas.max()))
    cmap.caption = "Voronoi cell area (km²)"
    fg = folium.FeatureGroup(name="Voronoi cells (by area)", show=True)
    folium.GeoJson(cells.to_json(), style_function=lambda f: {
        "fillColor": cmap(f["properties"]["area_km2"]), "color": "#222222",
        "weight": 0.6, "fillOpacity": 0.35},
        tooltip=folium.GeoJsonTooltip(fields=["name", "area_km2"],
                                      aliases=["facility", "cell km²"])).add_to(fg)
    fg.add_to(m)
    fgf = folium.FeatureGroup(name=f"{SERVICE_EMOJI[sv.key]} {svc.label} facilities", show=True)
    _add_service_markers(fgf, sv, cluster=True)
    fgf.add_to(m)
    fn = folium.FeatureGroup(name="Proposed new sites", show=True)
    for i, (lon, lat) in enumerate(rec.new_points_lonlat):
        folium.Marker([lat, lon], icon=folium.Icon(color="red", icon="plus"),
                      popup=f"Proposed {svc.label} #{i+1} ({rec.new_zones[i]})").add_to(fn)
    fn.add_to(m)
    cmap.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    out = REPORT_DIR / f"interactive_{sv.key}.html"
    m.save(str(out))
    return str(out)


def _sections_legend(ref: ZoneRef) -> folium.Element:
    rows = "".join(
        f'<div style="margin:2px 0;"><span style="display:inline-block;width:14px;height:14px;'
        f'background:{c};border:1px solid #fff;box-shadow:0 0 1px #000;margin-right:6px;'
        f'vertical-align:middle;"></span>{n}</div>' for n, c in zip(ref.names, ref.colors))
    html = ('<div style="position:fixed;bottom:22px;right:22px;z-index:9999;background:white;'
            'padding:10px 13px;border:1px solid #888;border-radius:6px;font:12px/1.35 sans-serif;'
            'box-shadow:0 1px 5px rgba(0,0,0,.3);">'
            f'<div style="font-weight:bold;margin-bottom:4px;">Dhaka sections ({len(ref.names)})</div>'
            + rows + '</div>')
    return folium.Element(html)


# =========================================================================== #
# LITERATURE REVIEW  (content shared by the report section and the standalone)
# =========================================================================== #
LIT_REVIEW = [
    ("Introduction",
     "This chapter reviews the body of work on which the present study builds. It "
     "proceeds thematically: the concepts and methods used to measure spatial "
     "accessibility and to site public facilities are examined first, followed by "
     "the open geospatial datasets and planning standards such studies rely on, and "
     "then accessibility research specific to Dhaka. A comparison of the most "
     "closely related studies leads to a statement of the research gap and the "
     "positioning of the present work against it."),
    ("Spatial accessibility: concepts and methods",
     "Measuring how easily a population can reach services is a classical problem in "
     "location science, tracing back to Weber's least-cost siting and Hakimi's "
     "p-median formulation, and formalised for coverage by the maximal covering "
     "location problem (MCLP) of Church and ReVelle (1974), which places a fixed "
     "number of facilities so as to maximise the demand served within a distance "
     "threshold. The geometric backbone for the nearest-facility question is the "
     "Voronoi diagram, whose theory and applications are consolidated by Okabe et "
     "al. (2000): partitioning space so every location is assigned to its closest "
     "facility yields service areas directly, and large cells expose coverage gaps. "
     "Distance-decay refinements led to the two-step floating catchment area (2SFCA) "
     "method of Luo and Wang (2003) and its enhanced variant (E2SFCA) by Luo and Qi "
     "(2009), which jointly account for supply, demand and impedance and remain the "
     "dominant accessibility framework. More recent work generalises these ideas: "
     "Cui et al. (2021) use a dynamic Voronoi diagram to balance facility service "
     "capacity, and Deliry and Uygucgil (2023) combine GIS network analysis with "
     "location-allocation to site new facilities. The present study combines the "
     "geometric clarity of the Voronoi partition with population weighting (in the "
     "spirit of 2SFCA) and an MCLP-style greedy siting step for its recommendations."),
    ("Data sources and planning standards",
     "Accessibility studies increasingly rely on open, volunteered and modelled "
     "geospatial data. OpenStreetMap (OSM) has become a standard source of "
     "point-of-interest data, though Klinkhardt et al. (2023), validating OSM POIs "
     "against large-scale ground truth, caution that completeness is uneven and "
     "counts should be treated as a lower bound. Population exposure is commonly "
     "derived from WorldPop's gridded estimates, produced by disaggregating census "
     "counts with satellite-derived covariates (Tatem, 2017; Lloyd et al., 2017), "
     "which provide open high-resolution population surfaces where detailed census "
     "microdata are unavailable. The distance thresholds that define underserved "
     "locations draw on planning norms: El-Geneidy et al. (2014) report an "
     "85th-percentile walking distance of roughly 524 m to bus service, and NFPA "
     "1710 (NFPA, 2020) frames fire coverage around a four-minute response objective. "
     "These standards inform, but do not uniquely determine, the thresholds adopted "
     "here."),
    ("Accessibility studies in Dhaka",
     "Empirical accessibility research on Dhaka has grown but remains largely "
     "single-service. Ahmed et al. (2019) apply 2SFCA to emergency healthcare and "
     "show that ignoring traffic congestion overstates coverage roughly threefold, "
     "identifying peripheral and older-core settlements as underserved. Rahman, "
     "Ashik and Mouli (2022) measure spatial accessibility to urban facilities around "
     "transit-oriented developments, finding better access near mass-transit nodes. "
     "Bhuiya, Shao and Jones (2023) use participatory GIS to assess evacuation "
     "accessibility for movement-challenged residents, and Alam, Nur and Mitra (2025) "
     "construct an Accessibility Index for public open space, reporting that central "
     "and south-western areas — including Old Dhaka, Dhanmondi, Banani and Gulshan — "
     "enjoy the best access. This last finding independently mirrors the central-belt "
     "advantage reported in the present study, lending external validity to the "
     "section-level results here, but like the others it addresses a single service "
     "class."),
    ("Comparative analysis of related work",
     "Table 1 compares the most closely related accessibility studies by method, "
     "data and principal limitation. Foundational methods (2SFCA, dynamic Voronoi) "
     "are typically demonstrated on a single service; the Dhaka studies are "
     "single-service by design; and the multi-facility studies that do exist are "
     "set in other cities and seldom pair population weighting with automated "
     "facility siting."),
    ("Research gap",
     "Three gaps emerge from the reviewed literature. First, Dhaka-specific studies "
     "each consider a single service type — healthcare, transit, evacuation or open "
     "space — leaving no integrated, multi-utility picture of the city's service "
     "coverage. Second, multi-facility studies that do exist (e.g., Deliry and "
     "Uygucgil, 2023) are set in other cities and seldom combine population weighting "
     "with automated facility siting. Third, few studies release a fully "
     "reproducible, open pipeline. No prior work provides a multi-utility, "
     "Voronoi-based, population-weighted, section-level accessibility assessment of "
     "Dhaka coupled with data-driven facility-placement recommendations."),
    ("Positioning of this study",
     "The present work addresses these gaps by analysing six utility services — "
     "metro stations, hospitals, water sources, fuel stations, bus stops and fire "
     "stations — within a single reproducible pipeline. It builds an exact Voronoi "
     "partition for each service, computes nearest-facility coverage on a fine grid, "
     "scores eight named sections by a population- and emergency-weighted benefit "
     "index, and proposes new facility locations using a greedy maximal-coverage "
     "heuristic (Church and ReVelle, 1974) that targets the most-populated "
     "underserved areas. In doing so it integrates the geometric, data and "
     "optimisation strands reviewed above into a Dhaka-specific, multi-utility "
     "accessibility study."),
]

# Comparison table: Author | Year | Methodology | Dataset | Key limitation (gap).
COMPARISON_TABLE = {
    "header": ["Study", "Year", "Methodology", "Dataset", "Key limitation / gap"],
    "rows": [
        ["Luo & Wang", "2003", "2SFCA", "US census; physicians",
         "Single service; no facility siting"],
        ["Ahmed et al.", "2019", "2SFCA + traffic variability", "Dhaka emergency care (OSM)",
         "Single service; slum-focused"],
        ["Cui et al.", "2021", "Dynamic Voronoi diagram", "Education facilities, China",
         "Capacity focus, not population access"],
        ["Rahman et al.", "2022", "Accessibility index", "Dhaka facilities near transit",
         "Transit-centric; not multi-utility"],
        ["Deliry & Uygucgil", "2023", "Network analysis + location-allocation",
         "Eskisehir fire/EMS/parks", "Not Dhaka; not population-weighted"],
        ["Alam et al.", "2025", "Accessibility Index (network)", "Dhaka public open space",
         "Single service (open space)"],
        ["This study", "2026", "Voronoi + KDTree + pop-weighted benefit + greedy MCLP",
         "6 OSM utilities + WorldPop, Dhaka",
         "Multi-utility, population-weighted, reproducible, with recommendations"],
    ],
}

REFERENCES = [
    'Ahmed, S., Adams, A. M., Islam, R., Hasan, S. M., &amp; Panciera, R. (2019). Impact of traffic variability on geographic accessibility to 24/7 emergency healthcare for the urban poor: A GIS study in Dhaka, Bangladesh. PLOS ONE, 14(9), e0222488. https://doi.org/10.1371/journal.pone.0222488',
    'Alam, I., Nur, S. M. S., &amp; Mitra, C. (2025). Accessibility to Public Open Space of a densely populated city: a case study of Dhaka, Bangladesh. Computational Urban Science, 5(1), 23. https://doi.org/10.1007/s43762-025-00187-9',
    'Bentley, J. L. (1975). Multidimensional binary search trees used for associative searching. Communications of the ACM, 18(9), 509–517. https://doi.org/10.1145/361002.361007',
    'Bhuiya, M. M. R., Shao, W., &amp; Jones, S. L. (2023). Measuring accessibility of movement challenged persons during earthquake evacuation of Dhaka City, Bangladesh: A participatory GIS-based approach. Applied Geography [confirm volume/article no.]. https://www.sciencedirect.com/science/article/abs/pii/S0143622823001054',
    'Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. Computers, Environment and Urban Systems, 65, 126–139. https://doi.org/10.1016/j.compenvurbsys.2017.05.004',
    'Church, R. L., &amp; ReVelle, C. S. (1974). The maximal covering location problem. Papers in Regional Science, 32(1), 101–118. https://doi.org/10.1007/BF01942293',
    'Cui, H., Wu, L., Hu, S., &amp; Lu, R. (2021). Measuring the Service Capacity of Public Facilities Based on a Dynamic Voronoi Diagram. Remote Sensing, 13(5), 1027. https://doi.org/10.3390/rs13051027',
    'Deliry, S. I., &amp; Uygucgil, H. (2023). Accessibility assessment of urban public services using GIS-based network analysis: a case study in Eskisehir, Turkiye. GeoJournal, 88, 4805–4825. https://doi.org/10.1007/s10708-023-10900-y',
    'El-Geneidy, A., Grimsrud, M., Wasfi, R., Tétreault, P., &amp; Surprenant-Legault, J. (2014). New evidence on walking distances to transit stops: identifying redundancies and gaps using variable service areas. Transportation, 41(1), 193–210. https://doi.org/10.1007/s11116-013-9508-z',
    'Goodchild, M. F. (2007). Citizens as sensors: the world of volunteered geography. GeoJournal, 69(4), 211–221. https://doi.org/10.1007/s10708-007-9111-y',
    "Klinkhardt, C., Kühnel, F., Heilig, M., Lautenbach, S., Wörle, T., Vortisch, P., &amp; Kuhnimhof, T. (2023). Quality Assessment of OpenStreetMap's Points of Interest with Large-Scale Real Data. Transportation Research Record, 2677. https://doi.org/10.1177/03611981231169280",
    'Lloyd, C. T., Sorichetta, A., &amp; Tatem, A. J. (2017). High resolution global gridded data for use in population studies. Scientific Data, 4, 170001. https://doi.org/10.1038/sdata.2017.1',
    'Luo, W., &amp; Qi, Y. (2009). An enhanced two-step floating catchment area (E2SFCA) method for measuring spatial accessibility to primary care physicians. Health &amp; Place, 15(4), 1100–1107. https://doi.org/10.1016/j.healthplace.2009.06.002',
    'Luo, W., &amp; Wang, F. (2003). Measures of spatial accessibility to health care in a GIS environment: synthesis and a case study in the Chicago region. Environment and Planning B, 30(6), 865–884. https://doi.org/10.1068/b29120',
    'National Fire Protection Association. (2020). NFPA 1710: Standard for the Organization and Deployment of Fire Suppression Operations, Emergency Medical Operations, and Special Operations to the Public by Career Fire Departments. NFPA.',
    'Okabe, A., Boots, B., Sugihara, K., &amp; Chiu, S. N. (2000). Spatial Tessellations: Concepts and Applications of Voronoi Diagrams (2nd ed.). Wiley.',
    'Rahman, M. H., Ashik, F. R., &amp; Mouli, M. J. (2022). Investigating spatial accessibility to urban facility outcome of transit-oriented development in Dhaka. Transportation Research Interdisciplinary Perspectives, 15, 100607. https://doi.org/10.1016/j.trip.2022.100607',
    'Tatem, A. J. (2017). WorldPop, open data for spatial demography. Scientific Data, 4, 170004. https://doi.org/10.1038/sdata.2017.4',
]


def _comparison_table_flowable(body):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Table, TableStyle

    cell = ParagraphStyle("cell", parent=body, fontSize=7.5, leading=9.5, spaceAfter=0)
    hdr = ParagraphStyle("hcell", parent=cell, textColor=colors.white)
    esc = lambda s: s.replace("&", "&amp;")
    data = [[Paragraph("<b>" + esc(c) + "</b>", hdr) for c in COMPARISON_TABLE["header"]]]
    for row in COMPARISON_TABLE["rows"]:
        data.append([Paragraph(esc(c), cell) for c in row])
    t = Table(data, colWidths=[2.5 * cm, 1.0 * cm, 4.2 * cm, 3.9 * cm, 5.0 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f6")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e6efe6")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def _literature_flowables(h1, h2, body, cap, lit_title, ref_title):
    from reportlab.platypus import PageBreak, Paragraph, Spacer
    from reportlab.lib.units import cm
    flow = [PageBreak(), Paragraph(lit_title, h1)]
    for head, txt in LIT_REVIEW:
        flow.append(Paragraph(head, h2))
        flow.append(Paragraph(txt, body))
        if head.startswith("Comparative"):
            flow.append(Spacer(1, 0.15 * cm))
            flow.append(_comparison_table_flowable(body))
            flow.append(Paragraph("Table 1. Comparison of related accessibility studies "
                                  "(this study, last row).", cap))
    flow.append(PageBreak())
    flow.append(Paragraph(ref_title, h1))
    for r in REFERENCES:
        flow.append(Paragraph(r, body))
    return flow


def build_literature_pdf() -> str:
    """Standalone literature-review document (same content as report section 11)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    out = OUTPUTS_DIR / "Dhaka_Voronoi_Literature_Review.pdf"
    m = 2.0 * cm
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=m, rightMargin=m,
                            topMargin=m, bottomMargin=m,
                            title="Literature Review — Voronoi Analysis of Dhaka Utilities",
                            author="Minhazul Abedin")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=16, spaceBefore=12, spaceAfter=8,
                        textColor=colors.HexColor("#1a1a1a"))
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4,
                        textColor=colors.HexColor("#333333"))
    body = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10.5, leading=15, spaceAfter=8,
                          alignment=4)
    ref = ParagraphStyle("Ref", parent=body, fontSize=9.5, leading=13, spaceAfter=7,
                         leftIndent=14, firstLineIndent=-14)
    cap = ParagraphStyle("Cap", parent=body, fontSize=8.5, textColor=colors.HexColor("#666666"),
                         spaceBefore=3, spaceAfter=10)
    story = [Paragraph("Chapter 2 — Literature Review", ss["Title"]),
             Paragraph(THESIS_TITLE + " &nbsp;·&nbsp; " + AUTHOR,
                       ParagraphStyle("sub", parent=body, fontSize=10.5,
                                      textColor=colors.HexColor("#555555"))),
             Spacer(1, 0.4 * cm)]
    for head, txt in LIT_REVIEW:
        story.append(Paragraph(head, h2))
        story.append(Paragraph(txt, body))
        if head.startswith("Comparative"):
            story.append(Spacer(1, 0.15 * cm))
            story.append(_comparison_table_flowable(body))
            story.append(Paragraph("Table 1. Comparison of related accessibility studies "
                                   "(this study, last row).", cap))
    story.append(Paragraph("References", h1))
    for r in REFERENCES:
        story.append(Paragraph(r, ref))
    doc.build(story)
    return str(out)


def build_literature_docx() -> str:
    """Editable Word version of the literature-review chapter (for the AIUB template)."""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.add_heading("Chapter 2 — Literature Review", level=0)
    doc.add_paragraph(THESIS_TITLE + " — " + AUTHOR)
    for head, txt in LIT_REVIEW:
        doc.add_heading(head, level=1)
        doc.add_paragraph(txt)
        if head.startswith("Comparative"):
            hdr = COMPARISON_TABLE["header"]
            t = doc.add_table(rows=1, cols=len(hdr))
            try:
                t.style = "Light Grid Accent 1"
            except KeyError:
                t.style = "Table Grid"
            for j, c in enumerate(hdr):
                cell = t.rows[0].cells[j]
                cell.text = c
                for r in cell.paragraphs[0].runs:
                    r.bold = True
            for row in COMPARISON_TABLE["rows"]:
                cells = t.add_row().cells
                for j, c in enumerate(row):
                    cells[j].text = c
            capp = doc.add_paragraph("Table 1. Comparison of related accessibility studies "
                                     "(this study, last row).")
            capp.runs[0].italic = True
    doc.add_heading("References", level=1)
    for r in REFERENCES:
        p = doc.add_paragraph(r.replace("&amp;", "&"))
        pf = p.paragraph_format
        pf.left_indent = Pt(18)
        pf.first_line_indent = Pt(-18)
    out = OUTPUTS_DIR / "Dhaka_Voronoi_Literature_Review.docx"
    doc.save(str(out))
    return str(out)


def build_poster(table, sb, ext, recs, flagship_key) -> str:
    """A1 landscape conference/defense poster (reportlab canvas)."""
    from reportlab.lib.pagesizes import A1, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rcanvas
    from PIL import Image as PILImage

    W, H = landscape(A1)                      # ~2384 x 1684 pt
    out = OUTPUTS_DIR / "Dhaka_Voronoi_Poster.pdf"
    c = rcanvas.Canvas(str(out), pagesize=(W, H))
    NAVY, TEAL, INK, MUT = "#0E2A47", "#1C7293", "#1C2B39", "#5B6B7A"

    # header band
    c.setFillColor(NAVY)
    c.rect(0, H - 150, W, 150, fill=1, stroke=0)
    c.setFillColor("#FFFFFF")
    c.setFont("Helvetica-Bold", 40)
    c.drawString(60, H - 78, "Providing Utility Services using Voronoi Diagrams")
    c.setFont("Helvetica", 24)
    c.setFillColor("#CADCFC")
    c.drawString(60, H - 116, "Some Analyses, Recommendations, and a Case Study for Dhaka City "
                             "·  Minhazul Abedin  ·  CSE Thesis")

    def wrap(txt, font, size, maxw):
        c.setFont(font, size)
        words, line, out_lines = txt.split(), "", []
        for w in words:
            if c.stringWidth(line + " " + w, font, size) < maxw:
                line = (line + " " + w).strip()
            else:
                out_lines.append(line)
                line = w
        out_lines.append(line)
        return out_lines

    def text_block(x, y, title, body, colw):
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(x, y, title)
        yy = y - 30
        c.setFillColor(INK)
        for ln in wrap(body, "Helvetica", 15, colw):
            c.drawString(x, yy, ln)
            yy -= 20
        return yy

    def image(x, y, path, w):
        p = FIGURES_DIR / path
        if not p.exists():
            return y
        iw, ih = PILImage.open(p).size
        h = w * ih / iw
        c.drawImage(ImageReader(str(p)), x, y - h, w, h, preserveAspectRatio=True, mask="auto")
        return y - h - 14

    m, gap = 60, 40
    colw = (W - 2 * m - 2 * gap) / 3
    x1, x2, x3 = m, m + colw + gap, m + 2 * (colw + gap)
    top = H - 190
    best = ", ".join(f"{r['section']} ({r['benefit_score']:.0f})" for _, r in sb.df.head(3).iterrows())

    # left column: text + the wide network figure
    y = text_block(x1, top, "Objective",
        "Evaluate how well six utility services — metro, hospitals, water, fuel, bus stops and "
        "fire stations — serve Dhaka's residents, and recommend where new facilities would help "
        "most, using Voronoi diagrams and open data.", colw)
    y = text_block(x1, y - 22, "Method",
        "Real OpenStreetMap facilities seed an exact Voronoi partition per service (straight "
        "perpendicular-bisector edges). Coverage is measured on a fine grid; eight sections are "
        "scored by a WorldPop population- and emergency-weighted benefit index; new sites are "
        "placed with a greedy maximal-covering heuristic, validated against 2SFCA and the exact "
        "optimum.", colw)
    y = text_block(x1, y - 22, "Data",
        f"OpenStreetMap ({int(table['n_facilities'].sum())} facilities) + WorldPop 1 km "
        "(~10.7M residents); metric CRS (UTM 46N).", colw)
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(x1, y - 26, "Straight-line vs road-network")
    image(x1, y - 56, "network_vs_euclid.png", colw)

    # centre column: the flagship map
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(x2, top, "Dhaka in eight coloured sections")
    image(x2, top - 30, "zones_dhaka_flagship.png", colw)

    # right column: benefit map + findings
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(x3, top, "Benefit by section & findings")
    yy = image(x3, top - 30, "section_benefit.png", colw)
    yy = text_block(x3, yy - 6, "Key findings",
        f"Central belt best served ({best}); {sb.df.iloc[-1]['section']} lags. Access is strongly "
        f"clustered (Moran's I = {ext.moran[0]:.2f}) and moderately unequal (Gini = "
        f"{ext.gini_combined:.2f}). Road-network distance roughly doubles the underserved share. "
        "Water and metro are the widest gaps; dense old Dhaka (Motijheel) is the top investment "
        "target for new hospitals and fire stations.", colw)
    text_block(x3, yy - 18, "Reproducible",
        "python voronoi_dhaka.py  ·  github.com/abedinm/voronoi-dhaka  ·  29 tests, interactive "
        "Google maps + full report.", colw)

    c.showPage()
    c.save()
    return str(out)


# --------------------------------------------------------------------------- #
# In-text citation numbering  ([n] matching the sorted reference list)
# --------------------------------------------------------------------------- #
CITE_KEYS = [
    ("Ahmed", "2019"), ("Alam", "2025"), ("Bentley", "1975"), ("Bhuiya", "2023"),
    ("Boeing", "2017"), ("Church", "1974"), ("Cui", "2021"), ("Deliry", "2023"),
    ("El-Geneidy", "2014"), ("Goodchild", "2007"), ("Klinkhardt", "2023"),
    ("Lloyd", "2017"), ("Luo", "2009"), ("Luo", "2003"), ("NFPA", "2020"),
    ("Okabe", "2000"), ("Rahman", "2022"), ("Tatem", "2017"),
]


def cite_number(surname: str, year: str) -> int:
    """1-based index of a reference in the sorted REFERENCES list."""
    return CITE_KEYS.index((surname, year)) + 1


def add_citation_numbers(text: str) -> str:
    """Append the bracketed reference number after each in-text citation.

    Handles both narrative ("Luo and Wang (2003)") and parenthetical
    ("(Church and ReVelle, 1974)") forms, and skips text already numbered."""
    import re as _re

    for idx, (surname, year) in enumerate(CITE_KEYS, 1):
        tag = " [%d]" % idx
        esc = _re.escape(surname)
        # parenthetical: (Surname ..., YEAR)
        text = _re.sub(r"(\(" + esc + r"[^()]{0,60}?" + year + r"\))(?!\s*\[)",
                       r"\1" + tag, text)
        # narrative: Surname ... (YEAR)
        text = _re.sub(r"(" + esc + r"[^()]{0,60}?\(" + year + r"\))(?!\s*\[)",
                       r"\1" + tag, text)
    return text


# --------------------------------------------------------------------------- #
# AIUB footer + page numbering (matches the official template exactly)
# --------------------------------------------------------------------------- #
COURSE_CODE = "CSC 4298 Thesis/Project"
DEPARTMENT = "Department of Computer Science"


def _w(tag: str) -> str:
    return "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}" + tag


def _page_field(paragraph):
    """Insert a live PAGE field so numbers update when the document reflows."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), kind)
            run._r.append(fld)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = " PAGE "
            run._r.append(instr)
    return run


def build_aiub_footer(section, show_number: bool = True):
    """Two-line AIUB footer: page number, then course code + department."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH as AL
    from docx.shared import Pt, RGBColor

    footer = section.footer
    footer.is_linked_to_previous = False
    for p in list(footer.paragraphs):
        p._element.getparent().remove(p._element)

    p1 = footer.add_paragraph()
    p1.alignment = AL.LEFT
    if show_number:
        r = _page_field(p1)
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0, 0, 0)

    p2 = footer.add_paragraph()
    p2.alignment = AL.LEFT
    tabs = p2.paragraph_format.tab_stops
    from docx.enum.text import WD_TAB_ALIGNMENT
    from docx.shared import Inches
    tabs.add_tab_stop(Inches(6.3), WD_TAB_ALIGNMENT.RIGHT)
    r1 = p2.add_run(COURSE_CODE + "\t" + DEPARTMENT)
    r1.font.size = Pt(11)
    r1.font.color.rgb = RGBColor(0, 0, 0)
    return footer


def set_page_numbering(section, fmt: str, start: int | None = None):
    """Set a section's page-number format ('lowerRoman' or 'decimal')."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    sectPr = section._sectPr
    for old in sectPr.findall(qn("w:pgNumType")):
        sectPr.remove(old)
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:fmt"), fmt)
    if start is not None:
        pg.set(qn("w:start"), str(start))
    sectPr.append(pg)


def _render_aiub(table, sb, ext, recs, flagship_key, voronois, FIGURE_INDEX, TABLE_INDEX,
                 collect: bool = False) -> str:
    """Render the AIUB-format thesis. With ``collect=True`` it only harvests the
    figure/table captions (skipping images) so the front-matter lists can be built."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH as AL
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5      # standard thesis spacing
    normal.paragraph_format.space_after = Pt(6)
    for hs in ("Heading 1", "Heading 2", "Heading 3", "Title"):
        try:
            doc.styles[hs].font.name = "Times New Roman"
        except KeyError:
            pass
    for s in doc.sections:
        s.page_width, s.page_height = Inches(8.27), Inches(11.69)
        s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Inches(1.0)

    def para(t, justify=True, italic=False, bold=False):
        p = doc.add_paragraph()
        r = p.add_run(add_citation_numbers(t))
        r.italic, r.bold = italic, bold
        r.font.color.rgb = RGBColor(0, 0, 0)
        if justify:
            p.alignment = AL.JUSTIFY
        return p

    def _black_heading(t, level):
        h = doc.add_heading(t, level=level)
        for r in h.runs:
            r.font.color.rgb = RGBColor(0, 0, 0)
            r.font.name = "Times New Roman"
        return h

    def h1(t):
        _black_heading(t, 1)

    def h2(t):
        _black_heading(t, 2)

    def figure(name, caption, width=5.6):
        if collect:
            FIGURE_INDEX.append(caption)
            return
        p = FIGURES_DIR / name
        if p.exists():
            doc.add_picture(str(p), width=Inches(width))
            doc.paragraphs[-1].alignment = AL.CENTER
            _caption(caption)                    # figure caption BELOW the figure

    def roman_list(items):
        """Numbered list in lowercase Roman numerals, restarting each time."""
        romans = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]
        for n, item in enumerate(items):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.5)
            p.paragraph_format.first_line_indent = Inches(-0.3)
            r = p.add_run(f"{romans[n]}.  ")
            r.font.color.rgb = RGBColor(0, 0, 0)
            r2 = p.add_run(add_citation_numbers(item))
            r2.font.color.rgb = RGBColor(0, 0, 0)
            p.alignment = AL.JUSTIFY

    def _caption(text, above=False):
        c = doc.add_paragraph()
        run = c.add_run(text)
        run.italic = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0, 0, 0)
        c.alignment = AL.CENTER
        return c

    def table_from(header, rows, caption=None):
        if collect:
            if caption:
                TABLE_INDEX.append(caption)
            return
        if caption:                       # table caption goes ABOVE the table
            _caption(caption)
        t = doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"            # plain black grid, no colour
        for j, hh in enumerate(header):
            cell = t.rows[0].cells[j]
            cell.text = str(hh)
            for r in cell.paragraphs[0].runs:
                r.bold = True
                r.font.color.rgb = RGBColor(0, 0, 0)
        for row in rows:
            cells = t.add_row().cells
            for j, v in enumerate(row):
                cells[j].text = str(v)
                for p_ in cells[j].paragraphs:
                    for r in p_.runs:
                        r.font.color.rgb = RGBColor(0, 0, 0)
        doc.add_paragraph()
        return
        if caption:
            c = doc.add_paragraph()
            run = c.add_run(caption)
            run.italic = True
            run.font.size = Pt(10)
            c.alignment = AL.CENTER

    def eq(t):
        p = doc.add_paragraph()
        r = p.add_run(t)
        r.italic = True
        p.alignment = AL.CENTER

    def code(lines):
        p = doc.add_paragraph()
        r = p.add_run("\n".join(lines))
        r.font.name = "Courier New"
        r.font.size = Pt(10)

    tf = table.set_index("service")
    ref_sections = zone_reference()
    def upct(s):
        return tf.loc[s, "pct_grid_underserved"]
    total_pop_m = (sb.df["pop_est"].sum() / 1e6) if sb.pop_weighted else 10.7
    best = ", ".join(f"{r['section']} ({r['benefit_score']:.0f})" for _, r in sb.df.head(3).iterrows())
    worst = sb.df.iloc[-1]

    # ------------------------------------------------------------------ title page
    def centred(txt, size, bold=False, space_after=0):
        p = doc.add_paragraph()
        p.alignment = AL.CENTER
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(space_after)
        r = p.add_run(txt)
        r.font.size = Pt(size)
        r.bold = bold
        return p

    if AIUB_LOGO.exists():
        doc.add_picture(str(AIUB_LOGO), width=Inches(1.35))
        _lp = doc.paragraphs[-1]
        _lp.alignment = AL.CENTER
        _lp.paragraph_format.space_after = Pt(10)
    centred("American International University-Bangladesh (AIUB)", 14)
    centred("Faculty of Science and Technology", 14, space_after=22)
    centred(THESIS_TITLE, 22, bold=True, space_after=30)
    for nm, sid in AUTHORS:
        centred(f"{nm} ({sid})", 17)
    doc.add_paragraph()
    for line in DEGREE_LINES:
        centred(line, 14)
    doc.add_paragraph()
    centred(SEMESTER, 14)
    centred("Submission Date: " + SUBMISSION_DATE, 14)

    # --- section 1 ends: title page carries the footer text but no page number ---
    if not collect:
        from docx.enum.section import WD_SECTION
        build_aiub_footer(doc.sections[0], show_number=False)
        set_page_numbering(doc.sections[0], "lowerRoman", start=1)
        _front = doc.add_section(WD_SECTION.NEW_PAGE)
        build_aiub_footer(_front, show_number=True)
        set_page_numbering(_front, "lowerRoman", start=1)
    else:
        doc.add_page_break()

    # ------------------------------------------------------------------ front matter
    h1("Declaration")
    para("(All candidates to reproduce this section in their thesis verbatim)", italic=True)
    for t in DECLARATION_TEXT:
        para(t)
    doc.add_paragraph()
    sig = doc.add_table(rows=len(AUTHORS), cols=2)
    sig.style = "Table Grid"
    for i, (nm, sid) in enumerate(AUTHORS):
        sig.rows[i].cells[0].text = f"{nm}\n{sid}"
        sig.rows[i].cells[1].text = "\n______________________\nSignature"
    doc.add_page_break()

    h1("Approval")
    para("The thesis titled “" + THESIS_TITLE + "” has been submitted to the following "
         "respected members of the board of examiners of the department of computer science in "
         "partial fulfilment of the requirements for the degree of Bachelor of Science in "
         "Computer Science on " + DEFENSE_DATE + " and has been accepted as satisfactory.")
    doc.add_paragraph()
    ex = doc.add_table(rows=len(EXAMINERS), cols=2)
    ex.style = "Table Grid"
    for i, (nm, rank) in enumerate(EXAMINERS):
        c0 = ex.rows[i].cells[0]
        c0.text = nm
        for r in c0.paragraphs[0].runs:
            r.bold = True
        c0.add_paragraph(rank)
        ex.rows[i].cells[1].text = "\n______________________\nSignature"
    doc.add_page_break()

    h1("Acknowledgement")
    para("All praise is due to Almighty Allah for granting us the strength, patience and "
         "opportunity to complete this thesis successfully.")
    para("We express our sincere gratitude to our supervisor, " + SUPERVISOR + ", "
         + SUPERVISOR_RANK + ", Department of Computer Science, American International "
         "University-Bangladesh, for "
         "continuous guidance, constructive criticism and encouragement throughout this research. "
         "The scope and rigour of this work owe much to that supervision.")
    para("We are grateful to the Faculty of Science and Technology and the Department of Computer "
         "Science, AIUB, for providing the academic environment, laboratory access and resources "
         "that made this study possible, and to the members of the board of examiners for their "
         "time and valuable feedback.")
    para("We also acknowledge the open-data communities whose freely available datasets underpin "
         "this research: the OpenStreetMap contributors, whose volunteered geographic information "
         "provided every facility location used here; the WorldPop programme at the University of "
         "Southampton for open gridded population estimates; and the maintainers of the "
         "open-source scientific Python ecosystem — NumPy, SciPy, Shapely, GeoPandas, OSMnx, "
         "Matplotlib and others — on which the entire analysis is built.")
    para("Finally, we thank our families and friends for their patience and support during the "
         "course of this work.")
    doc.add_page_break()

    h1("Abstract")
    para(
        "Dhaka is among the most densely populated cities in the world and has expanded far "
        "faster than its public utility networks, producing pronounced spatial inequalities in "
        "access to essential services. This thesis analyses the provision of six utility services "
        "across Dhaka — metro stations, hospitals, water sources, fuel stations, bus stops and "
        "fire stations — using Voronoi diagrams, and recommends where new facilities should be "
        f"placed. Facility locations for {int(table['n_facilities'].sum())} facilities were "
        "collected from OpenStreetMap and the resident population from the WorldPop 1 km gridded "
        f"estimates (approximately {total_pop_m:.1f} million residents within the study area). "
        "For every service an exact Voronoi partition was constructed from perpendicular "
        "bisectors and clipped to the city boundary; nearest-facility distance was measured on a "
        f"{GRID_SPACING_M:.0f} m demand grid using a k-d tree; the city was divided into eight "
        "named sections and scored with a population- and emergency-weighted benefit index; and "
        "new facility sites were selected with a greedy maximal-covering heuristic that targets "
        "the most-populated underserved locations.")
    para(
        f"The results show that combined utility access is moderately unequal (Gini = "
        f"{ext.gini_combined:.3f}) and strongly spatially clustered (Moran's I = "
        f"{ext.moran[0]:.2f}, pseudo p = {ext.moran[1]:.3f}). The central belt is best served "
        f"({best}), while {worst['section']} ({worst['benefit_score']:.0f}) and Uttara lag "
        f"behind. Water sources ({upct('water_pump'):.0f}% of the area beyond threshold) and "
        f"metro stations ({upct('metro_station'):.0f}%) exhibit the widest coverage gaps, whereas "
        f"hospitals show the narrowest ({upct('hospital'):.0f}%). Because Motijheel is the most "
        "populous section yet only moderately served, it emerges as the highest-impact target for "
        "investment: three new fire stations there and in adjacent sections reduce the "
        f"underserved population from {recs['fire_station'].before.underserved_people/1000:.0f} "
        f"thousand to {recs['fire_station'].after.underserved_people/1000:.0f} thousand.")
    para(
        "The approach was validated in three ways: its section rankings agree with the "
        "established two-step floating catchment area (2SFCA) method for scarce, "
        "distance-dominated services; the greedy recommender recovers essentially all of the "
        "coverage achieved by an exact maximal-covering optimum; and repeating the analysis with "
        "road-network shortest-path distance shows that straight-line distance understates the "
        "true access gap, roughly doubling the underserved share. The work is significant because "
        "it provides the first integrated, multi-utility, population-weighted and fully "
        "reproducible accessibility assessment of Dhaka, giving planners an auditable evidence "
        "base for siting decisions; the complete pipeline, figures, interactive maps and this "
        "report regenerate from a single command.")
    h1("Keywords")
    para("Voronoi diagram; spatial accessibility; utility services; facility location; maximal "
         "covering location problem; geographic information system; OpenStreetMap; WorldPop; "
         "urban service equity; Dhaka.", justify=False)
    doc.add_page_break()

    h1("Table of Content")
    para("Insert an automatic table of contents here in Microsoft Word "
         "(References → Table of Contents → Automatic Table), then right-click and choose "
         "“Update Field” after the document is finalised. All chapter and section headings in "
         "this document use the built-in Heading 1/2/3 styles, so they will be captured "
         "automatically.", italic=True)
    doc.add_page_break()

    h1("List of Figures")
    _fig_rows = [[cap, ""] for cap in FIGURE_INDEX]
    table_from(["Figure", "Page"], _fig_rows)
    para("Page numbers are populated automatically when the list is inserted as a Table of "
         "Figures in Word (References → Insert Table of Figures).", italic=True)
    doc.add_page_break()

    h1("List of Tables")
    _tab_rows = [[cap, ""] for cap in TABLE_INDEX]
    table_from(["Table", "Page"], _tab_rows)
    doc.add_page_break()

    h1("List of Abbreviations")
    table_from(["Abbreviation", "Elaboration"], [[a, b] for a, b in ABBREVIATIONS])

    # ------------------------------------------------------------------ Chapter 1
    if not collect:                      # body section: Arabic numbering from 1
        from docx.enum.section import WD_SECTION
        _body = doc.add_section(WD_SECTION.NEW_PAGE)
        build_aiub_footer(_body, show_number=True)
        set_page_numbering(_body, "decimal", start=1)
    h1("Chapter 1 — Introduction")
    h2("1.1 Introduction")
    para("Dhaka is, by most measures, among the most densely populated cities in the world, and it "
         "reached that state faster than almost any comparable city in South Asia. This rapid, "
         "largely unplanned growth has left the spatial distribution of essential utility services "
         "uneven: some neighbourhoods enjoy abundant access while others are poorly served. This "
         "thesis analyses that distribution for six utility services using Voronoi diagrams and "
         "open data, and identifies where new facilities would most improve access.")
    h2("1.2 Problem Statement")
    para("Existing accessibility studies of Dhaka each consider a single service and typically rely "
         "on the two-step floating catchment area method or simple buffers. There is no integrated, "
         "multi-utility, population-weighted assessment of Dhaka's service coverage that also "
         "recommends where to invest, and few such studies are released as reproducible software. "
         "As a result, planners lack a city-wide, evidence-based picture of which neighbourhoods "
         "are underserved across the utilities that matter most to daily life and safety.")
    h2("1.3 Problem Background")
    para("Dhaka's population has grown several-fold within a generation, while its utility "
         "networks — transport, healthcare, water, fuel and emergency services — have expanded "
         "piecemeal. Official, up-to-date registries of facility locations are fragmented or "
         "unavailable, which is precisely why open, volunteered geographic data such as "
         "OpenStreetMap has become the practical basis for spatial analysis in the city. Voronoi "
         "diagrams assign every location to its nearest facility, making them a natural, "
         "interpretable tool for the ‘nearest-service’ question; combined with gridded population "
         "(WorldPop), they enable a city-wide, multi-service accessibility assessment at "
         "negligible cost.")
    h2("1.4 Research Objectives")
    roman_list([
        "Partition Dhaka into Voronoi service areas for six utility services from open data.",
        "Quantify coverage and identify underserved areas, weighted by population.",
        "Rank the city's areas by how well their residents are served.",
        "Recommend new facility locations that most improve access.",
        "Validate the approach against established accessibility methods and release a fully "
        "reproducible pipeline."])
    h2("1.5 Research Questions")
    roman_list([
        "How well do the six utility services cover Dhaka, and which areas are underserved?",
        "Which parts of the city benefit most once population is taken into account?",
        "Where should new facilities be added to help the most people?",
        "Do the Voronoi-based results agree with established accessibility methods, and how "
        "much does road-network distance change the picture?"])
    h2("1.6 Motivations")
    para("The motivation for this research is practical: every year Dhaka invests in new "
         "facilities, yet siting decisions are rarely backed by open, quantitative evidence of "
         "where residents are actually underserved. The authors' own experience of unequal "
         "access across the city — long journeys to hospitals or fuel from some neighbourhoods, "
         "abundance in others — motivated a method that measures the gap for people rather than "
         "land, is transparent enough for a planner to audit, and is cheap enough to repeat as "
         "the city grows.")
    h2("1.7 Flow of Research")
    para("The research proceeded in sequence: literature review and gap identification; "
         "acquisition and cleaning of facility, boundary and population data; exact Voronoi "
         "construction and its verification on textbook cases; grid-based coverage measurement; "
         "population-weighted section scoring; greedy facility recommendation; validation against "
         "2SFCA, the exact covering optimum and road-network distance; and finally packaging of "
         "the pipeline, figures, interactive maps and this report.")
    h2("1.8 Scope of the Study")
    para(f"The study covers the Dhaka metropolitan bounding box {DHAKA_BBOX} and six OpenStreetMap "
         "service categories. Distances are computed in a metric projection; the core analysis uses "
         "straight-line distance, with an optional road-network extension. Facility capacity is not "
         "modelled, and the eight sections are analytical zones rather than official administrative "
         "units.")
    h2("1.9 Significance of the Research")
    para("By turning opaque service-coverage patterns into clear maps, quantitative scores and "
         "concrete recommendations, this study gives planners and citizens an evidence base for "
         "prioritising investment. Its open, reproducible design means the analysis can be updated "
         "as data improves, extended with more services, or transferred to other cities at "
         "negligible cost.")
    h2("1.10 Research Contribution")
    para("The thesis contributes: (i) the first integrated, multi-utility Voronoi accessibility "
         "assessment of Dhaka built entirely from open data; (ii) a population- and emergency-"
         "weighted section benefit index; (iii) population-targeted, near-optimal facility "
         "recommendations with quantified before/after impact; (iv) cross-validation against the "
         "2SFCA method, the exact covering optimum and road-network distance; and (v) a fully "
         "reproducible open pipeline with interactive maps and a dashboard.")
    h2("1.11 Thesis Organization")
    para("Chapter 2 reviews related work and states the research gap. Chapter 3 describes the "
         "proposed model and methodology. Chapter 4 covers implementation, testing and results. "
         "Chapter 5 discusses standards, constraints and milestones. Chapter 6 concludes with "
         "contributions, limitations and future work.")
    h2("1.12 Summary")
    para("This chapter introduced the problem of uneven utility access in Dhaka, stated the "
         "research problem and its background, and set out the objectives, questions, motivations, "
         "flow, scope, significance and contributions of the study. The next chapter reviews the "
         "literature on which the proposed model builds.")
    doc.add_page_break()

    # ------------------------------------------------------------------ Chapter 2
    h1("Chapter 2 — Literature Review")
    _ch2_names = {"Research gap": "Problem Analysis (Research Gap)"}
    for _i, (head, txt) in enumerate(LIT_REVIEW, start=1):
        h2(f"2.{_i} {_ch2_names.get(head, head)}")
        para(txt)
        if head.startswith("Comparative"):
            table_from(COMPARISON_TABLE["header"], COMPARISON_TABLE["rows"],
                       "Table 2.1. Comparison of related accessibility studies (this study, last row).")
    h2(f"2.{len(LIT_REVIEW) + 1} Detailed Review of Key Studies")
    para("Okabe, Boots, Sugihara and Chiu (2000) provide the definitive treatment of Voronoi "
         "tessellations and their spatial applications; their formalisation of ordinary, weighted "
         "and network Voronoi diagrams underpins the geometric method used in this thesis. Church "
         "and ReVelle (1974) introduced the maximal covering location problem, which frames "
         "facility siting as choosing a fixed number of locations to cover the most demand within a "
         "distance threshold — the exact objective our greedy recommender approximates.")
    para("Luo and Wang (2003) introduced the two-step floating catchment area (2SFCA) method, and "
         "Luo and Qi (2009) enhanced it with distance-decay weights (E2SFCA); together these remain "
         "the dominant accessibility framework and provide the supply–demand perspective against "
         "which the present Voronoi results are validated. Cui, Wu, Hu and Lu (2021) extend the "
         "diagram itself, using a dynamic Voronoi construction to balance facility service capacity "
         "— motivating capacity-weighting as a future extension of this work.")
    para("Within Dhaka, Ahmed, Adams, Islam, Hasan and Panciera (2019) apply 2SFCA to emergency "
         "healthcare and demonstrate that ignoring traffic congestion overstates coverage roughly "
         "threefold, identifying peripheral and older-core settlements as underserved. Rahman, Ashik "
         "and Mouli (2022) examine accessibility around transit-oriented developments, and Bhuiya, "
         "Shao and Jones (2023) use participatory GIS for evacuation accessibility. Alam, Nur and "
         "Mitra (2025) construct an accessibility index for public open space and report that "
         "central and south-western Dhaka enjoy the best access — a finding this thesis independently "
         "reproduces for utilities, lending external validity to the section-level results.")
    para("Beyond Dhaka, Deliry and Uyguçgil (2023) combine GIS network analysis with location-"
         "allocation to site new fire, emergency and park facilities in Eskişehir, the closest "
         "methodological analogue to the recommendation component here, though it is single-city and "
         "does not weight by population. On the data side, Klinkhardt et al. (2023) quantify the "
         "completeness of OpenStreetMap points of interest against ground truth, and Tatem (2017) "
         "and Lloyd, Sorichetta and Tatem (2017) document the WorldPop modelling that produces the "
         "gridded population used for weighting.")
    h2(f"2.{len(LIT_REVIEW) + 2} Summary")
    para("The reviewed literature establishes the Voronoi partition and the maximal-covering "
         "problem as sound foundations, the 2SFCA family as the benchmark accessibility method, "
         "OpenStreetMap and WorldPop as accepted open data sources, and a consistent centre-versus-"
         "periphery inequality in Dhaka. The gap this thesis fills is the absence of an integrated, "
         "multi-utility, population-weighted, reproducible accessibility study of Dhaka that also "
         "recommends where to invest.")
    doc.add_page_break()

    # ------------------------------------------------------------------ Chapter 3
    h1("Chapter 3 — Proposed Model")
    h2("3.1 Introduction")
    para("The proposed model is a five-stage pipeline: (1) collect and clean facility and "
         "population data; (2) build an exact Voronoi partition per service; (3) measure coverage "
         "on a fine grid; (4) score eight sections by a population-weighted benefit index; and "
         "(5) recommend new facilities. Extended analyses validate the results. This chapter "
         "presents the feasibility and requirements of that system, the research methodology, the "
         "design of each stage with its governing equations, and the tools used.")
    h2("3.2 Feasibility Analysis")
    para("The study is technically feasible because every input is openly available "
         "(OpenStreetMap facilities, the OSM administrative boundary, the WorldPop population "
         "grid) and every algorithm — Voronoi tessellation, k-d tree search, greedy covering — "
         "runs in seconds to minutes on a commodity laptop. It is economically feasible because "
         "no paid data, software or infrastructure is required, and operationally feasible "
         "because the entire pipeline regenerates from a single command, so it can be re-run by "
         "planners or future students without specialised setup.")
    h2("3.3 Requirement Analysis (Functional and Non-Functional)")
    para("Functional requirements: the system shall (i) fetch and clean facility locations for "
         "six services; (ii) construct an exact Voronoi partition per service clipped to the city "
         "boundary; (iii) compute nearest-facility distance on a fine grid and flag underserved "
         "locations; (iv) score eight sections by a population-weighted benefit index; "
         "(v) recommend k new facility sites per service; and (vi) produce figures, tables, "
         "interactive maps and this report.")
    para("Non-functional requirements: correctness (geometry verified by automated tests), "
         "reproducibility (identical outputs from cached data), performance (full run in minutes "
         "on a laptop), transparency (open source, open data, documented parameters), and "
         "portability (pure-Python stack, no proprietary dependencies).")
    h2("3.4 Research Methodology")
    para("The methodology is quantitative and geospatial: facilities are modelled as Voronoi "
         "seeds, demand as a population-weighted grid, access as nearest-facility distance against "
         "per-service thresholds, and investment as a maximal-covering optimisation. Each design "
         "decision below is justified against the literature reviewed in Chapter 2.")
    para("Facility locations for the six services come from OpenStreetMap via the osmnx library, "
         "giving " + ", ".join(f"{int(tf.loc[k,'n_facilities'])} {SERVICE_TYPES[k].label.lower()}s"
                                for k in SERVICE_TYPES) +
         f" after cleaning. Population is the WorldPop 1 km grid (2020), about {total_pop_m:.1f} "
         "million residents in the study area. The city boundary is the OSM administrative polygon.")
    para("Input and output use WGS84 (EPSG:4326); every distance and area is computed in UTM zone "
         f"46N (EPSG:32646), in metres. Points are reprojected, de-duplicated within "
         f"{MIN_SEED_DISTANCE:.0f} m, and clipped to the boundary.")
    h2("3.5 System Design and Architecture")
    para("Each facility is a Voronoi seed. For two seeds p and q, the set of points at least as "
         "close to p as to q is a half-plane whose boundary is the perpendicular bisector of the "
         "segment pq:")
    eq("H(p, q) = { x : |x − p| ≤ |x − q| }")
    para("The Voronoi cell of facility p is the intersection of these half-planes over all of p's "
         "Delaunay neighbours N(p), clipped to the study boundary B:")
    eq("V(p) = B ∩ ⋂_{q ∈ N(p)} H(p, q)")
    para("Because each cell is an intersection of half-planes, every interior edge is a true "
         "perpendicular bisector, exactly three cells meet at each vertex in general position, and "
         "the cells tile the region without gaps or overlaps. This exact construction is what makes "
         "the diagram a faithful, testable model of the service areas rather than an approximation.")
    h2("3.6 Implementation and Simulation")
    para("The design is realised in three computational stages — coverage measurement, section "
         "scoring, and facility recommendation — described in turn below.")
    _black_heading("Coverage and underserved detection", 3)
    para(f"For a fine grid of demand points laid over the city at {GRID_SPACING_M:.0f} m spacing, "
         "the nearest-facility distance is computed with a k-d tree:")
    eq("d(x) = min_{p} |x − p|;    x is underserved for a service if d(x) > τ_service")
    para("Each service has its own threshold τ (e.g. 800 m for bus stops, 2 km for hospitals, 3 km "
         "for fire stations), reflecting how far a resident can reasonably travel for that service. "
         "The cell area of each Voronoi region (km²) is also recorded: a large cell means one "
         "facility must serve a wide area.")
    _black_heading("Population-weighted section benefit", 3)
    para("Eight named sections are defined as a nearest-centre (coarse Voronoi) partition of "
         "well-known area centres. Each section s is scored by a benefit index — the share of its "
         "residents within reach of each service, averaged over services with weights that "
         "emphasise emergencies and water:")
    eq("B_s = 100 · ( Σ_j w_j · f_{s,j} ) / ( Σ_j w_j )")
    para("where f_{s,j} is the population-weighted fraction of section s within threshold τ_j of "
         "service j, and w_j is the service weight (hospital and fire = 2, water = 1.5, others = 1). "
         "Population weights come from the WorldPop grid, so the index measures how well the "
         "section's people — not its land — are served.")
    _black_heading("Facility recommendation", 3)
    para("New facilities are placed with a greedy maximal-covering heuristic (Church & ReVelle, "
         "1974). At each step the algorithm adds a facility at the most-populated location that is "
         "still underserved, then recomputes distances, so the recommendations target people rather "
         "than empty land:")
    code(["Input: existing facilities F, demand grid X with population pop(x), threshold τ, count k",
          "for i in 1 .. k:",
          "    x* = argmax_{x in X}  pop(x) · [ d_F(x) > τ ]   # most-populated underserved cell",
          "    F = F ∪ { x* }                                 # add a facility there",
          "return the k new sites x*"])
    para("This greedy strategy is simple yet, for the sub-modular maximal-covering objective, "
         "provably within a (1 − 1/e) factor of the optimum; Section 4.4 shows it in fact recovers "
         "essentially all of the exact optimum on the study data.")
    h2("3.7 Tools and Technologies Used")
    para("The pipeline is implemented in Python 3.12 as a single reproducible script. NumPy and "
         "SciPy provide the numerics and spatial structures (Voronoi, k-d tree, Dijkstra via "
         "NetworkX); Shapely and GeoPandas the computational geometry and CRS handling; osmnx the "
         "OpenStreetMap acquisition; rasterio the WorldPop raster sampling; Matplotlib and "
         "contextily the static cartography; folium the interactive Google-basemap maps; "
         "Streamlit the dashboard; reportlab and python-docx the report generation; and pytest "
         "the automated test suite (29 tests). Git provides version control with continuous "
         "integration on GitHub Actions.")
    h2("3.8 Validation and Extended Analyses")
    para("The model is cross-checked against the two-step floating catchment area (2SFCA) method. "
         "The 2SFCA accessibility of a location i is the sum of the supply-to-demand ratios R_j of "
         "the facilities within its catchment:")
    eq("A_i = Σ_{j ∈ cat(i)} R_j,   with   R_j = S_j / Σ_{k ∈ cat(j)} P_k")
    para("Access equity is summarised by the Gini coefficient of the combined access index (with a "
         "Lorenz curve), and spatial structure by Moran's I of spatial autocorrelation:")
    eq("Gini = 1 − 2 ∫₀¹ L(p) dp;    I = (n / Σ w) · ( Σ_i Σ_j w_ij z_i z_j ) / Σ_i z_i²")
    para("Robustness is checked with a sensitivity analysis (varying thresholds and weights), the "
         "greedy recommender is benchmarked against the exact optimum, and an optional extension "
         "recomputes coverage with road-network shortest-path distance instead of straight-line "
         "distance.")
    h2("3.9 Summary")
    para("This chapter established that the proposed system is feasible with open data and "
         "commodity computation, stated its functional and non-functional requirements, and "
         "presented the design: an exact Voronoi partition per service, grid-based coverage "
         "against per-service thresholds, a population-weighted section benefit index, and a "
         "greedy maximal-covering recommender — together with the validation strategy. The next "
         "chapter reports its implementation and results.")
    doc.add_page_break()

    # ------------------------------------------------------------------ Chapter 4
    h1("Chapter 4 — Implementation and Testing")
    h2("4.1 Introduction")
    para("This chapter presents the practical implementation of the model described in Chapter 3, "
         "the testing performed, and the results obtained.")
    h2("4.2 System Setup and Environment")
    para("The system is implemented in Python as a single reproducible script using NumPy, SciPy, "
         "Shapely, GeoPandas, osmnx, rasterio, contextily, folium, Matplotlib and pytest. All "
         "outputs — figures, report, interactive maps and a dashboard — regenerate with a "
         "single command.")
    h2("4.3 Data Collection and Preparation")
    para("All facility data used in this study is authentic, openly licensed data rather than "
         "simulated coordinates. Each of the six services was queried from the live OpenStreetMap "
         "database through the OSMnx library using the tag filters listed in Table 4.1, restricted "
         f"to the Dhaka bounding box {DHAKA_BBOX}. Because OpenStreetMap represents many "
         "facilities as building polygons rather than points, every returned geometry was reduced "
         "to a single interior representative point computed in the metric projection. The raw "
         "responses were then de-duplicated within "
         f"{MIN_SEED_DISTANCE:.0f} m — necessary because large hospitals and filling stations are "
         "frequently mapped several times as separate nodes, ways and relations — and clipped to "
         "the administrative boundary of the city.")
    _osm_rows = []
    for k in SERVICE_TYPES:
        svc = SERVICE_TYPES[k]
        tags = "; ".join(f"{t}={'|'.join(v) if isinstance(v, list) else v}"
                         for t, v in svc.osm_tags.items())
        raw_p = RAW_DIR / f"{k}.csv"
        n_raw = max(sum(1 for _ in open(raw_p, encoding="utf-8")) - 1, 0) if raw_p.exists() else 0
        _osm_rows.append([svc.label, tags, n_raw, int(tf.loc[k, "n_facilities"]),
                          f"{svc.underserved_m/1000:.1f}"])
    table_from(["Service", "OpenStreetMap tag filter", "Raw", "Cleaned", "Threshold (km)"],
               _osm_rows,
               "Table 4.1. Authentic OpenStreetMap queries, facility counts before and after "
               "cleaning, and the distance threshold applied to each service.")
    para(f"The retained dataset comprises {int(table['n_facilities'].sum())} facilities. The "
         "reduction from raw to cleaned counts is substantial for the densely mapped categories "
         "(water sources and hospitals in particular), which reflects duplicate mapping and "
         "features lying just outside the administrative boundary rather than data loss. Table 4.2 "
         "lists representative records drawn directly from the processed files to demonstrate the "
         "authenticity and heterogeneity of the source data: names appear in both Bangla and "
         "English exactly as contributed by OpenStreetMap volunteers.")
    _sample_rows = []
    for k in SERVICE_TYPES:
        _pp = PROCESSED_DIR / f"{k}.csv"
        if not _pp.exists():
            continue
        _df = pd.read_csv(_pp)
        _named = [n for n in _df["name"].tolist()
                  if isinstance(n, str) and not n.startswith(k + " #") and n.lower() != "unknown"]
        for _nm in _named[:2]:
            _row = _df[_df["name"] == _nm].iloc[0]
            _sample_rows.append([SERVICE_TYPES[k].label, _nm[:44],
                                 f"{_row['lat']:.4f}", f"{_row['lon']:.4f}", _row["source"]])
    table_from(["Service", "Facility name (as mapped)", "Latitude", "Longitude", "Source"],
               _sample_rows,
               "Table 4.2. Representative authentic records from the processed datasets, showing "
               "original OpenStreetMap names and coordinates.")
    para("Resident population was taken from the WorldPop Bangladesh 1 km UN-adjusted 2020 raster "
         "and sampled at every demand-grid point, scaled from persons per raster pixel to persons "
         f"per grid cell. Summed over the study area this yields approximately {total_pop_m:.1f} "
         "million residents, which is consistent with published estimates for the Dhaka city "
         "area and provides an independent check that the raster was sampled and scaled correctly. "
         "Table 4.3 records the fixed analysis parameters so that the experiment can be repeated "
         "exactly.")
    table_from(["Parameter", "Value"],
               [["Study-area bounding box (lon/lat)", str(DHAKA_BBOX)],
                ["Geographic CRS (input/output)", CRS_GEO + " (WGS 84)"],
                ["Metric CRS (all distance and area)", CRS_METRIC + " (UTM zone 46N)"],
                ["Boundary", "OpenStreetMap administrative polygon ∩ bounding box"],
                ["Demand-grid spacing", f"{GRID_SPACING_M:.0f} m"],
                ["De-duplication distance", f"{MIN_SEED_DISTANCE:.0f} m"],
                ["Population raster", "WorldPop BGD 1 km UN-adjusted, 2020"],
                ["Facilities proposed per service (k)", str(RECOMMEND_K)],
                ["Figure resolution", f"{FIGURE_DPI} DPI"]],
               "Table 4.3. Fixed analysis parameters.")
    para("Finally, Table 4.4 reports how the authentic facilities distribute across the eight "
         "sections. The concentration in the central sections, and the sparse coverage of "
         "Bashundhara and the outer fringe, is visible in the raw counts before any accessibility "
         "modelling is applied — an early indication of the inequality the later analysis "
         "quantifies.")
    _sec_names, _sec_counts = list(ref_sections.names), {}
    for k, sv in voronois.items():
        _idx = KDTree(ref_sections.centers_m).query(sv.seeds)[1]
        _sec_counts[k] = [int((_idx == i).sum()) for i in range(len(_sec_names))]
    _rows = []
    for i, _s in enumerate(_sec_names):
        _rows.append([_s] + [_sec_counts[k][i] for k in SERVICE_TYPES]
                     + [sum(_sec_counts[k][i] for k in SERVICE_TYPES)])
    table_from(["Section"] + [SERVICE_TYPES[k].label.split()[0] for k in SERVICE_TYPES] + ["Total"],
               _rows,
               "Table 4.4. Authentic facility counts by section and service.")

    h2("4.4 Implementation of the System")
    para("Before analysing Dhaka, the Voronoi construction was verified on three textbook seed "
         "sets: every diagram has straight perpendicular-bisector edges, degree-three vertices, and "
         "tiles its bounding box exactly (Figure 4.1).")
    figure("textbook_all.png", "Figure 4.1. Textbook Voronoi correctness verification.", 5.8)
    para("With the geometry verified, the pipeline builds a Voronoi partition, coverage grid and "
         "section scores for each of the six services in turn; the resulting maps are presented "
         "service by service in Section 4.5.1.")
    h2("4.5 Evaluation and Testing")
    para("As a spatial-analysis system, testing centred on correctness rather than predictive "
         "accuracy. A suite of 29 automated tests verifies the geometry (exact tiling, degree-three "
         "vertices, bisector midpoints), the coverage metrics, and the recommender. The Voronoi "
         "rankings were cross-validated against 2SFCA, and the greedy recommender against the exact "
         "maximal-covering optimum.")
    table_from(["Service", "2SFCA vs Voronoi (ρ)"],
               [[r["service"], r["spearman_vs_voronoi"]] for _, r in ext.tsfca_agreement.iterrows()],
               "Table 4.5. Agreement between Voronoi and 2SFCA rankings.")
    table_from(["Service", "Greedy (k, thousands)", "Optimal (k, thousands)", "Greedy % of optimal"],
               [[r["service"], f"{r['greedy_covered_k']:.0f}", f"{r['optimal_covered_k']:.0f}",
                 f"{r['greedy_pct_of_optimal']}%"] for _, r in ext.mclp.iterrows()],
               "Table 4.6. Greedy vs exact maximal-covering placement.")
    h2("4.6 Results and Discussion")
    para("Coverage varies sharply by service. Water pumps and metro have the widest gaps "
         f"({upct('water_pump'):.0f}% and {upct('metro_station'):.0f}% of the area beyond threshold), "
         f"while hospitals cover the most ({upct('hospital'):.0f}% underserved). Table 4.7 "
         "summarises the per-service coverage.")
    table_from(["Service", "Facilities", "Mean cell (km²)", "Max cell (km²)", "Area underserved (%)"],
               [[SERVICE_TYPES[k].label, int(tf.loc[k, "n_facilities"]),
                 f"{tf.loc[k, 'mean_cell_km2']:.2f}", f"{tf.loc[k, 'max_cell_km2']:.1f}",
                 f"{tf.loc[k, 'pct_grid_underserved']:.0f}"] for k in SERVICE_TYPES],
               "Table 4.7. Per-service coverage summary.")

    h2("4.6.1 Coverage of each service")
    para("Each service is examined individually below. Its Voronoi partition is drawn over the "
         "Dhaka basemap with cells coloured by the section they belong to, the facilities marked "
         "in the service's own colour, and underserved (oversized) cells outlined in red.")
    _svc_notes = {
        "metro_station": "Coverage follows only the single MRT-6 corridor from Uttara to Motijheel, "
                         "leaving the east and much of the south well beyond reach — the sparsest network.",
        "hospital": "Hospitals are the most numerous service and are spread across the built-up "
                    "core, giving the best area coverage, though the eastern and southern fringes lag.",
        "water_pump": "Mapped water sources are uneven and thin toward the fringes, producing the "
                      "widest population gap of any service.",
        "fuel": "Fuel stations cluster along arterial roads, with gaps in the residential interiors "
                "and the periphery.",
        "bus_stop": "Bus stops are dense in the central wards but thin on the outskirts, so cell "
                    "sizes grow sharply toward the edges.",
        "fire_station": "Fire stations are few and widely spaced; their Voronoi cells are the "
                        "largest, and emergency reach is a concern on the fringe.",
    }
    for _svc_i, k in enumerate(SERVICE_TYPES):
        svc = SERVICE_TYPES[k]
        figure(f"voronoi_{k}.png",
               f"Figure 4.{_svc_i + 2}. {svc.label} — Voronoi coverage over Dhaka, cells "
               "coloured by section.", 4.4)
        para(f"{svc.label}. {int(tf.loc[k,'n_facilities'])} facilities; mean cell "
             f"{tf.loc[k,'mean_cell_km2']:.2f} km² (largest {tf.loc[k,'max_cell_km2']:.1f} km²); "
             f"{tf.loc[k,'pct_grid_underserved']:.0f}% of the area beyond the "
             f"{svc.underserved_m/1000:.1f} km threshold. {_svc_notes[k]}")

    h2("4.6.2 Which areas benefit most")
    para(f"Weighting by population and emergency importance, the central belt is best served "
         f"({best}); {worst['section']} scores lowest ({worst['benefit_score']:.0f}). The most "
         "populous section, Motijheel (old Dhaka), is only moderately served and is therefore the "
         "highest-impact target for investment (Figures 4.8–4.9, Table 4.8).")
    figure("zones_dhaka_flagship.png", "Figure 4.8. Voronoi coloured by the eight sections.", 5.0)
    figure("section_benefit.png", "Figure 4.9. Population-weighted benefit score by section.", 5.0)
    table_from(["Section", "Population", "Benefit score", "Weakest service"],
               [[r["section"], f"{r['pop_est']/1e6:.2f} M" if sb.pop_weighted else "-",
                 f"{r['benefit_score']:.0f}", r["weakest_service"]] for _, r in sb.df.iterrows()],
               "Table 4.8. Section benefit ranking (population-weighted).")

    h2("4.6.3 Recommendations")
    para("Population-targeted greedy placement concentrates new facilities in dense, underserved "
         "areas rather than the empty fringe. Table 4.9 reports the drop in underserved population "
         "from adding three facilities per service, and Figures 4.10–4.12 show three examples.")
    table_from(["Service", "Underserved before → after (thousands)", "New sites (sections)"],
               [[SERVICE_TYPES[k].label,
                 f"{recs[k].before.underserved_people/1000:.0f} → {recs[k].after.underserved_people/1000:.0f}",
                 ", ".join(recs[k].new_zones)] for k in SERVICE_TYPES],
               "Table 4.9. Coverage improvement from the proposed facilities.")
    figure("recommendations_fire_station.png", "Figure 4.10. Existing vs proposed fire stations.", 4.8)
    figure("recommendations_hospital.png", "Figure 4.11. Existing vs proposed hospitals.", 4.8)
    figure("recommendations_water_pump.png", "Figure 4.12. Existing vs proposed water sources.", 4.8)

    h2("4.6.4 Equity, clustering and combined access")
    para(f"Combining all services into one access index, access is moderately unequal (Gini = "
         f"{ext.gini_combined:.3f}) and strongly clustered (Moran's I = {ext.moran[0]:.3f}, "
         f"pseudo p = {ext.moran[1]:.3f}) — well- and poorly-served areas form contiguous "
         "regions. Per-section values of the combined index mirror the benefit ranking of "
         "Table 4.8. The Lorenz curve (Figure 4.13) summarises the equity of access.")
    figure("lorenz_access.png", "Figure 4.13. Lorenz curve of combined utility access.", 4.2)
    para("A sensitivity check (Table 4.10) shows the section ranking is robust: under ±25% "
         "thresholds and equal service weights the ranking barely changes (Spearman ρ ≈ 0.98).")
    table_from(["Scenario", "Rank corr. (ρ)", "Best", "Worst"],
               [[r["scenario"], r["rank_corr_vs_baseline"], r["best"], r["worst"]]
                for _, r in ext.sensitivity.iterrows()],
               "Table 4.10. Sensitivity of the section ranking.")

    h2("4.6.5 Road-network distance")
    para("Repeating the analysis with shortest-path distance on the Dhaka road network (rather than "
         "straight-line distance) confirms that Euclidean distance understates real travel: the "
         "median detour is about 1.5×, and the underserved share roughly doubles for several "
         "services (Figure 4.14). This is a key finding — the true access gap is larger than a "
         "straight-line analysis suggests.")
    figure("network_vs_euclid.png", "Figure 4.14. Underserved share: straight-line vs road network.", 5.6)

    h2("4.6.6 Validation against the 2SFCA method")
    para("As a further check, the two-step floating catchment area (2SFCA) accessibility was "
         "computed per service and its section ranking correlated with the Voronoi nearest-distance "
         "ranking (Table 4.5). Agreement is strong for scarce, distance-dominated services (metro, "
         "water, hospital) and weaker for dense or demand-sensitive ones, where 2SFCA additionally "
         "penalises the crowding of facilities. The two methods are complementary: the Voronoi "
         "partition captures proximity cleanly and reproducibly, while 2SFCA adds supply–demand "
         "balance.")
    para("Facility density (Table 4.11) contextualises the counts against area and population; "
         "because OpenStreetMap completeness varies, these figures should be read as a lower bound.")
    table_from(["Service", "Facilities", "per 100k people", "km² / facility"],
               [[r["service"], int(r["facilities"]), r["per_100k_people"], r["km2_per_facility"]]
                for _, r in ext.density.iterrows()],
               "Table 4.11. Facility density and completeness context.")

    h2("4.7 Summary")
    para("This chapter described the implementation environment, the pipeline stages, the testing "
         "performed, and the results — identifying the central belt as best served, Motijheel "
         "as the top investment target, and water and metro as the weakest services.")
    doc.add_page_break()

    # ------------------------------------------------------------------ Chapter 5
    h1("Chapter 5 — Standards, Constraints and Milestones")
    h2("5.1 Standards and Compliance")
    para("The research follows established geospatial and software-engineering practices: standard "
         "coordinate reference systems (EPSG:4326 and EPSG:32646), open geospatial data formats "
         "(GeoJSON, GeoTIFF, GraphML), the ODbL licence for OpenStreetMap and CC-BY for WorldPop, "
         "and reproducible software practice (version control, automated testing, a single "
         "regenerating pipeline).")
    h2("5.2 Sustainability Considerations")
    para("The computational approach is deliberately lightweight: all processing runs on a "
         "commodity laptop from open datasets, with no specialised hardware or paid services, "
         "keeping the environmental and financial footprint minimal.")
    h2("5.3 Societal Impact")
    para("By turning otherwise opaque service-coverage patterns into clear maps and recommendations, "
         "the study can help planners and citizens identify underserved neighbourhoods and target "
         "investment where it benefits the most people.")
    h2("5.4 Ethical Considerations")
    para("The main ethical consideration concerns data completeness and representativeness: "
         "OpenStreetMap coverage is uneven, so results are presented as a lower bound and the "
         "limitations are stated explicitly. No personal data is used.")
    h2("5.5 Security and Privacy Considerations")
    para("The study does not collect, store or process any personal or sensitive data; all inputs "
         "are aggregate, publicly available geospatial datasets, so privacy risk is negligible.")
    h2("5.6 Design Constraints and Component Constraints")
    para("The design relies entirely on open data and open-source tools. The core analysis uses "
         "straight-line distance for tractability and reproducibility; road-network distance is "
         "provided as an optional extension.")
    h2("5.7 Data Constraints and Computational Constraints")
    para("The primary data constraint is the completeness of OpenStreetMap, which varies by "
         "category, so facility counts are a lower bound. Population is modelled at 1 km resolution. "
         "Computation is modest and completes on a laptop in minutes.")
    h2("5.8 Budget Constraints")
    para("The research was conducted with effectively no direct financial cost: all data, software "
         "and basemaps are free and open.")
    h2("5.9 Task Breakdown and Project Timeline")
    para("The project followed an iterative, phase-wise structure: topic definition and literature "
         "review; data acquisition and cleaning; Voronoi construction and coverage metrics; "
         "population-weighted benefit analysis; recommendations and validation; extended analyses; "
         "interactive maps and dashboard; and thesis documentation.")
    h2("5.10 Milestones and Deliverables")
    para("Key milestones: (1) verified exact Voronoi construction; (2) real multi-service data "
         "pipeline; (3) population-weighted benefit ranking; (4) facility recommendations; "
         "(5) method validation (2SFCA, exact optimum, network distance); and (6) the complete "
         "reproducible software, report, interactive maps and dashboard.")
    h2("5.11 Gantt Chart")
    figure("gantt.png", "Figure 5.1. Project timeline (Gantt chart).", 6.2)
    h2("5.12 Summary")
    para("This chapter outlined the standards, constraints and project milestones relevant to the "
         "study.")
    doc.add_page_break()

    # ------------------------------------------------------------------ Chapter 6
    h1("Chapter 6 — Conclusion")
    h2("6.1 Summary of the Study")
    para("This thesis built a reproducible Voronoi-based framework to analyse the provision of six "
         "utility services in Dhaka, measure coverage and equity, and recommend new facility "
         "locations. It identified the central belt as best served, dense old Dhaka as the "
         "highest-impact investment target, and water and metro as the weakest services.")
    h2("6.2 Key Contributions")
    for c in ["A multi-utility, Voronoi-based accessibility assessment of Dhaka from open data.",
              "A population- and emergency-weighted section benefit index.",
              "Population-targeted, near-optimal facility recommendations.",
              "Cross-validation against 2SFCA, the exact optimum and road-network distance.",
              "A fully reproducible open pipeline, interactive maps and a dashboard."]:
        doc.add_paragraph(c, style="List Bullet")
    h2("6.3 Limitations of the Study")
    para("Several limitations qualify the findings of this study and should be considered when "
         "interpreting the results.")
    para("First, the core analysis measures straight-line (Euclidean) distance in a metric "
         "projection rather than the distance a resident actually travels. Section 4.6.5 quantifies "
         "the consequence — a median detour factor of roughly 1.5 and an underserved share that "
         "roughly doubles — so the headline coverage figures should be read as an optimistic bound. "
         "Travel time, traffic congestion, road quality and the reality that Dhaka's traffic makes "
         "distance a poor proxy for time are not modelled at all; Ahmed et al. (2019) show that "
         "ignoring congestion can overstate emergency coverage roughly threefold.")
    para("Second, all facility locations come from OpenStreetMap, a volunteered source whose "
         "completeness varies by category and by neighbourhood. Comparing the raw and cleaned counts "
         "in Table 4.1 shows how much duplicate and boundary-adjacent mapping the data contains, and "
         "Klinkhardt et al. (2023) document uneven completeness in exactly this kind of dataset. "
         "Facility counts are therefore a lower bound: unmapped clinics, private water points and "
         "informal transport stops are invisible to the analysis, which likely understates coverage "
         "in poorly mapped peripheral areas.")
    para("Third, the model treats every facility as identical. A twelve-bed clinic and a thousand-bed "
         "tertiary hospital seed the same Voronoi cell, because OpenStreetMap carries no reliable "
         "capacity attribute. Real accessibility depends on capacity, opening hours, cost and "
         "service quality, none of which are represented here.")
    para("Fourth, the eight sections are analytical zones defined by nearest-centre partitioning of "
         "well-known area centres, not official ward or thana boundaries. They were chosen because "
         "the administrative polygons available through OpenStreetMap for Dhaka are inconsistent, "
         "but it means section-level figures depend on where those centres were placed.")
    para("Fifth, population comes from a modelled 1 km raster rather than a census enumeration. "
         "WorldPop disaggregates census totals using satellite covariates, so fine-grained "
         "population distribution within each kilometre is estimated rather than observed, and the "
         "estimates date from 2020.")
    para("Finally, the distance thresholds and service weights are planning conventions drawn from "
         "the literature rather than universal constants. The sensitivity analysis in Section 4.6.4 "
         "shows the section ranking is robust to reasonable variation in both, but the absolute "
         "percentages would shift under a different threshold regime.")
    h2("6.4 Future Work Scopes")
    para("The limitations above map directly onto opportunities for further research, and the "
         "reproducible pipeline released with this thesis is intended to make each of them "
         "straightforward to pursue.")
    para("The most valuable extension is to replace straight-line distance with travel time on the "
         "road network under realistic traffic conditions. The road-network machinery already exists "
         "in the pipeline; adding time-of-day speed profiles would turn the coverage maps into "
         "genuine accessibility-by-travel-time surfaces, which is what planners actually need for "
         "emergency response.")
    para("A second direction is capacity-weighted Voronoi diagrams, in which each facility's cell "
         "grows or shrinks according to its service capacity, following the dynamic formulation of "
         "Cui et al. (2021). This would require capacity data from official registries — hospital "
         "bed counts from the Directorate General of Health Services, pumping capacity from Dhaka "
         "WASA — which would simultaneously address the completeness limitation by validating and "
         "supplementing the OpenStreetMap layer.")
    para("Third, the spatial resolution can be improved: WorldPop publishes a 100 m population "
         "raster, and official thana or ward boundaries would replace the analytical sections with "
         "units that match how the city is actually administered and budgeted.")
    para("Fourth, the accessibility measure can be broadened beyond physical proximity to include "
         "socio-economic dimensions — income, vehicle ownership and informal-settlement status — so "
         "that the benefit index reflects who can realistically reach a facility rather than who "
         "lives near one.")
    para("Fifth, a machine-learning component could be introduced to predict underservice from "
         "urban form indicators such as population density, road density and land use, allowing the "
         "framework to anticipate where gaps will emerge as the city grows rather than only "
         "describing the present.")
    para("Finally, the framework is city-agnostic. Applying it to Chattogram, Khulna or Sylhet "
         "would test its transferability and produce comparable national evidence, and extending it "
         "to additional services — schools, markets, waste collection — would broaden the picture of "
         "urban service equity in Bangladesh.")
    doc.add_page_break()

    # ------------------------------------------------------------------ References
    h1("References")
    for i, r in enumerate(REFERENCES, 1):
        p = doc.add_paragraph(f"[{i}]  " + r.replace("&amp;", "&"))
        p.paragraph_format.left_indent = Pt(24)
        p.paragraph_format.first_line_indent = Pt(-24)

    # ------------------------------------------------------------------ Appendix
    doc.add_page_break()
    h1("Appendix")
    h2("Appendix A: Reproducibility")
    para("The complete pipeline, data-fetch scripts, tests and this document's generator are "
         "available in the project repository (github.com/abedinm/voronoi-dhaka). To reproduce "
         "every figure, table and analysis:")
    code(["python -m venv .venv && source .venv/bin/activate",
          "pip install -r requirements.txt",
          "python voronoi_dhaka.py            # full pipeline + report",
          "python voronoi_dhaka.py --network  # add road-network analysis",
          "pytest                             # 29 correctness tests",
          "streamlit run dashboard.py         # interactive dashboard"])
    h2("Appendix B: Data Provenance")
    para("Facility data: © OpenStreetMap contributors (ODbL), fetched via osmnx and cached under "
         "data/raw/. Population: WorldPop Bangladesh 1 km UN-adjusted 2020 (CC-BY). Boundary: OSM "
         "administrative polygon intersected with the study window. Every processed point carries "
         "a source column, and data/SOURCE.md documents each dataset. Basemaps: © CARTO (static "
         "figures) and © Google (interactive maps).")
    h2("Appendix C: Per-Service Thresholds and Weights")
    table_from(["Service", "Threshold (km)", "Benefit weight"],
               [[SERVICE_TYPES[k].label, f"{SERVICE_TYPES[k].underserved_m/1000:.1f}",
                 f"{SERVICE_WEIGHT[k]:.1f}"] for k in SERVICE_TYPES],
               "Table A.1. Distance thresholds and service weights used throughout.")

    out = OUTPUTS_DIR / "Dhaka_Voronoi_AIUB_Thesis.docx"
    if collect:
        return ""
    doc.save(str(out))
    return str(out)


def build_aiub_thesis_docx(table, sb, ext, recs, flagship_key, voronois) -> str:
    """Two-pass build: harvest figure/table captions, then render with real lists."""
    figs: list[str] = []
    tabs: list[str] = []
    _render_aiub(table, sb, ext, recs, flagship_key, voronois, figs, tabs, collect=True)
    return _render_aiub(table, sb, ext, recs, flagship_key, voronois, figs, tabs, collect=False)


def build_thesis_docx(table, sb, ext, recs, flagship_key) -> str:
    """Full editable thesis draft (Abstract + Ch.1, 3, 4, 5) with real numbers.

    Chapter 2 (Literature Review) is provided by build_literature_docx()."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    doc = Document()

    def para(t, justify=True):
        p = doc.add_paragraph(t)
        if justify:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        return p

    def figure(name, caption, width=5.6):
        path = FIGURES_DIR / name
        if path.exists():
            doc.add_picture(str(path), width=Inches(width))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            c = doc.add_paragraph(caption)
            c.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if c.runs:
                c.runs[0].italic = True
                c.runs[0].font.size = Pt(9)

    tf = table.set_index("service")
    def pct(s):
        return tf.loc[s, "pct_grid_underserved"]
    total_pop_m = (sb.df["pop_est"].sum() / 1e6) if sb.pop_weighted else None
    best = sb.df.iloc[0]
    worst = sb.df.iloc[-1]
    top3 = ", ".join(f"{r['section']} ({r['benefit_score']:.0f})" for _, r in sb.df.head(3).iterrows())

    # ---- title ----
    doc.add_heading(THESIS_TITLE, level=0)
    sub = doc.add_paragraph(f"{AUTHOR}   ·   Undergraduate Thesis, Department of Computer "
                            "Science & Engineering")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("").alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ---- Abstract ----
    doc.add_heading("Abstract", level=1)
    para(
        "Dhaka, one of the world's densest megacities, has expanded far faster than its "
        "public utilities, producing sharp spatial inequalities in access. This thesis "
        "presents a reproducible framework that uses Voronoi diagrams to analyse the "
        "provision of six utility services — metro stations, hospitals, water sources, "
        "fuel stations, bus stops and fire stations — across Dhaka. Facility locations are "
        "drawn from OpenStreetMap and residents from the WorldPop 1 km population grid. "
        "For each service an exact Voronoi partition is built (straight perpendicular-"
        "bisector edges), nearest-facility coverage is measured on a fine grid, and the "
        "city is scored by a population- and emergency-weighted benefit index over eight "
        "named sections. New facility locations are recommended with a greedy maximal-"
        "covering heuristic that targets the most-populated underserved areas. Results show "
        f"access is strongly clustered (Moran's I = {ext.moran[0]:.2f}) and moderately "
        f"unequal (Gini = {ext.gini_combined:.2f}); the central belt ({top3}) is best "
        f"served while {worst['section']} ({worst['benefit_score']:.0f}) lags. Water pumps "
        f"({pct('water_pump'):.0f}% of area underserved) and metro ({pct('metro_station'):.0f}%) "
        "are the widest gaps, and dense old Dhaka (Motijheel) is the highest-impact site "
        "for new facilities. The Voronoi results agree with the established 2SFCA method for "
        "scarce services, and the greedy recommendations recover essentially all of the "
        "exact optimum. The complete pipeline is released as a single reproducible program.")
    para("Keywords: Voronoi diagram; spatial accessibility; utility services; facility "
         "location; GIS; OpenStreetMap; WorldPop; Dhaka.", justify=False)

    # ---- Chapter 1 ----
    doc.add_heading("Chapter 1 — Introduction", level=1)
    doc.add_heading("1.1 Background", level=2)
    para(
        "Dhaka is among the fastest-growing megacities in the world, with rapid, largely "
        "unplanned expansion on its fringe. Utility provision — transport, health, water, "
        "fuel and emergency services — has not kept pace, leaving pronounced differences in "
        "access between the dense core and the periphery. Understanding where services fall "
        "short, and where new ones would help the most people, is therefore a pressing "
        "planning problem. Voronoi diagrams, which assign every location to its nearest "
        "facility, provide a natural and interpretable tool for this 'nearest-service' "
        "question.")
    doc.add_heading("1.2 Problem statement", level=2)
    para(
        "Existing accessibility studies of Dhaka each consider a single service (healthcare, "
        "transit, open space or evacuation) and typically rely on the two-step floating "
        "catchment area method or simple buffers. There is no integrated, multi-utility, "
        "population-weighted assessment of Dhaka's service coverage that also recommends "
        "where to invest, and few such studies are released as reproducible software.")
    doc.add_heading("1.3 Objectives", level=2)
    for o in ["Partition Dhaka into Voronoi service areas for six utility services from open data.",
              "Quantify coverage and identify underserved areas, weighted by population.",
              "Rank the city's areas by how well their residents are served.",
              "Recommend new facility locations that most improve access.",
              "Validate the approach against established accessibility methods and release "
              "a fully reproducible pipeline."]:
        doc.add_paragraph(o, style="List Bullet")
    doc.add_heading("1.4 Scope and limitations", level=2)
    para(
        "The study covers the Dhaka metropolitan bounding box and six OpenStreetMap service "
        "categories. Distances are straight-line (Euclidean) in a metric projection; road-"
        "network travel distance and real-time traffic are out of scope. Facility capacity "
        "is not modelled, and the eight sections are analytical zones rather than official "
        "administrative units.")
    doc.add_heading("1.5 Thesis organisation", level=2)
    para(
        "Chapter 2 reviews related work and states the research gap. Chapter 3 describes the "
        "data and methodology. Chapter 4 presents and discusses the results. Chapter 5 "
        "concludes with contributions, limitations and future work.")

    # ---- Chapter 3 ----
    doc.add_heading("Chapter 3 — Methodology", level=1)
    doc.add_heading("3.1 Study area and data", level=2)
    para(
        f"The study area is the Dhaka bounding box {DHAKA_BBOX} intersected with the OSM "
        "administrative boundary. Facility locations for the six services were collected "
        "from OpenStreetMap via the osmnx library, de-duplicated within "
        f"{MIN_SEED_DISTANCE:.0f} m and clipped to the boundary, giving "
        + ", ".join(f"{int(tf.loc[k,'n_facilities'])} {SERVICE_TYPES[k].label.lower()}s"
                    for k in SERVICE_TYPES) +
        f". Population came from the WorldPop 1 km grid (2020), totalling about "
        f"{total_pop_m:.1f} million residents in the study area.")
    doc.add_heading("3.2 Coordinate systems and preprocessing", level=2)
    para(
        "All input/output uses WGS84 (EPSG:4326); every distance and area is computed in "
        "UTM zone 46N (EPSG:32646), in metres. Points are reprojected, de-duplicated and "
        "boundary-clipped before analysis.")
    doc.add_heading("3.3 Voronoi construction", level=2)
    para(
        "Each facility of a service is a Voronoi seed. Cells are computed exactly as the "
        "intersection of the half-planes bounded by the perpendicular bisectors to each "
        "seed's Delaunay neighbours, then clipped to the study boundary. This guarantees "
        "straight bisector edges, degree-three vertices in general position, and an exact "
        "tiling — verified by an automated test suite.")
    doc.add_heading("3.4 Coverage metrics", level=2)
    para(
        "For each service the cell area (km²) and the nearest-facility distance on a "
        f"{GRID_SPACING_M:.0f} m grid (via a KD-tree) are computed. A location is "
        "'underserved' if its nearest facility exceeds a per-service distance threshold "
        "(e.g. 800 m for bus stops, 2 km for hospitals, 3 km for fire stations).")
    doc.add_heading("3.5 Population-weighted section benefit", level=2)
    para(
        "The city is divided into eight named sections (nearest-centre Voronoi of well-known "
        "area centres). Each section is scored by the share of its residents within reach of "
        "each service, averaged across services with emergency services (hospital, fire) and "
        "water weighted higher, and weighted by WorldPop population.")
    doc.add_heading("3.6 Facility recommendations", level=2)
    para(
        "New facilities are placed with a greedy maximal-covering heuristic (Church & "
        "ReVelle, 1974): each new site is the most-populated still-underserved location, "
        "chosen iteratively. The result targets people rather than empty land.")
    doc.add_heading("3.7 Validation and extended analyses", level=2)
    para(
        "The approach is cross-checked with the two-step floating catchment area (2SFCA) "
        "method; access equity is measured with the Gini coefficient and a Lorenz curve; "
        "spatial clustering with Moran's I; robustness with a threshold/weight sensitivity "
        "analysis; and the greedy recommender against the exact maximal-covering optimum.")
    doc.add_heading("3.8 Tools", level=2)
    para(
        "The pipeline is implemented in Python using NumPy, SciPy, Shapely, GeoPandas, "
        "contextily, osmnx, rasterio, folium, Matplotlib and pytest, released as a single "
        "reproducible script.")

    # ---- Chapter 4 ----
    doc.add_heading("Chapter 4 — Results and Discussion", level=1)
    doc.add_heading("4.1 Coverage by service", level=2)
    para(
        "Coverage varies sharply by service. Water pumps and the metro have the widest gaps "
        f"({pct('water_pump'):.0f}% and {pct('metro_station'):.0f}% of the area beyond "
        f"threshold), while hospitals cover the most area ({pct('hospital'):.0f}% "
        "underserved). The metro's gap reflects its single MRT-6 corridor.")
    figure("voronoi_hospital.png", "Figure 4.1. Hospital Voronoi coverage over Dhaka.", 5.4)
    doc.add_heading("4.2 Which areas benefit most", level=2)
    para(
        f"Weighting by population and emergency importance, the central belt is best served "
        f"({top3}), while {worst['section']} scores lowest ({worst['benefit_score']:.0f}). "
        "The most populous section, Motijheel (old Dhaka), is only moderately served and is "
        "therefore the highest-impact target for investment.")
    figure("section_benefit.png", "Figure 4.2. Population-weighted benefit score by section.", 5.2)
    doc.add_heading("4.3 Recommendations", level=2)
    para(
        "Population-weighted greedy placement concentrates new facilities in dense, "
        "underserved areas. For example, three new fire stations cut the underserved "
        f"population from {recs['fire_station'].before.underserved_people/1000:.0f}k to "
        f"{recs['fire_station'].after.underserved_people/1000:.0f}k, and three hospitals "
        f"from {recs['hospital'].before.underserved_people/1000:.0f}k to "
        f"{recs['hospital'].after.underserved_people/1000:.0f}k.")
    figure(f"recommendations_{flagship_key}.png",
           "Figure 4.3. Existing (blue) vs proposed (red) sites.", 5.0)
    doc.add_heading("4.4 Equity and spatial clustering", level=2)
    para(
        f"The combined access index has a Gini coefficient of {ext.gini_combined:.3f} "
        "(0 = perfectly equal), indicating moderate inequality, and a Moran's I of "
        f"{ext.moran[0]:.3f} (pseudo p = {ext.moran[1]:.3f}), indicating strong spatial "
        "clustering: well- and poorly-served areas form contiguous regions.")
    figure("lorenz_access.png", "Figure 4.4. Lorenz curve of combined utility access.", 4.4)
    doc.add_heading("4.5 Method validation", level=2)
    para(
        "The Voronoi rankings agree strongly with 2SFCA for scarce services (metro, water, "
        "hospital) and less so for dense or demand-sensitive ones, where 2SFCA additionally "
        "penalises crowding — the methods are complementary. The greedy recommender recovers "
        "essentially all of the exact maximal-covering optimum, confirming its adequacy.")
    doc.add_heading("4.6 Sensitivity", level=2)
    para(
        "Re-running the section ranking under ±25% thresholds and equal service weights "
        "leaves it almost unchanged (Spearman ρ ≈ 0.98), so the conclusions do not hinge on "
        "the exact parameter choices.")
    doc.add_heading("4.7 Discussion", level=2)
    para(
        "The centre-versus-periphery pattern found here is consistent with prior Dhaka "
        "studies: Ahmed et al. (2019) report peripheral and older-core settlements as "
        "underserved for emergency care, and Alam et al. (2025) find central and "
        "south-western areas most accessible for open space. This study extends that picture "
        "to six utilities simultaneously and adds explicit, population-aware recommendations.")

    # ---- Chapter 5 ----
    doc.add_heading("Chapter 5 — Conclusion", level=1)
    doc.add_heading("5.1 Summary", level=2)
    para(
        "This thesis built a reproducible Voronoi-based framework to analyse the provision of "
        "six utility services in Dhaka, measure coverage and equity, and recommend new "
        "facility locations. It identified the central belt as best served, dense old Dhaka "
        "as the highest-impact investment target, and water and metro as the weakest "
        "services.")
    doc.add_heading("5.2 Contributions", level=2)
    for c in ["A multi-utility, Voronoi-based accessibility assessment of Dhaka from open data.",
              "A population- and emergency-weighted section benefit index.",
              "Population-targeted, near-optimal facility recommendations.",
              "Cross-validation against 2SFCA and the exact maximal-covering optimum.",
              "A fully reproducible open pipeline and an interactive map set."]:
        doc.add_paragraph(c, style="List Bullet")
    doc.add_heading("5.3 Limitations", level=2)
    para(
        "Distances are straight-line rather than road-network or traffic-aware; OpenStreetMap "
        "completeness varies, so counts are a lower bound; facility capacity is not modelled; "
        "and the sections are analytical rather than official administrative units.")
    doc.add_heading("5.4 Future work", level=2)
    para(
        "Natural extensions include road-network and traffic-aware travel distance, capacity-"
        "weighted Voronoi diagrams, finer (100 m) population and official administrative "
        "boundaries, an interactive web dashboard, and validation against official facility "
        "registries.")

    # ---- References ----
    doc.add_heading("References", level=1)
    for r in REFERENCES:
        p = doc.add_paragraph(r.replace("&amp;", "&"))
        p.paragraph_format.left_indent = Pt(18)
        p.paragraph_format.first_line_indent = Pt(-18)

    out = OUTPUTS_DIR / "Dhaka_Voronoi_Thesis_Draft.docx"
    doc.save(str(out))
    return str(out)


# =========================================================================== #
# PDF REPORT
# =========================================================================== #
def build_pdf_report(voronois, coverages, table, recs, flagship_key, sb, ext, light=False) -> str:
    import os
    import tempfile

    from PIL import Image as PILImage
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak,
                                     Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

    out = OUTPUTS_DIR / ("Dhaka_Voronoi_Report_light.pdf" if light else "Dhaka_Voronoi_Report.pdf")
    _tmp = tempfile.mkdtemp(prefix="litefig_") if light else None
    margin = 1.8 * cm
    content_w = A4[0] - 2 * margin
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin,
                            title="Voronoi Analysis of Dhaka Utility Services",
                            author="Minhazul Abedin")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceBefore=14, spaceAfter=6,
                        textColor=colors.HexColor("#1a1a1a"))
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4,
                        textColor=colors.HexColor("#333333"))
    body = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=9.5, leading=13, spaceAfter=6)
    cap = ParagraphStyle("Cap", parent=body, fontSize=8, textColor=colors.HexColor("#666666"),
                         alignment=TA_CENTER, spaceBefore=2, spaceAfter=10)
    title_style = ParagraphStyle("Title", parent=ss["Title"], fontSize=19, leading=24)
    sub_style = ParagraphStyle("Sub", parent=ss["Title"], fontSize=12, leading=16,
                               textColor=colors.HexColor("#555555"))

    def fig(path, max_w=content_w, max_h=20 * cm, caption=None):
        src = path
        if light:                                    # downscale to a compact JPEG
            im = PILImage.open(path).convert("RGB")
            if im.width > 1200:
                im = im.resize((1200, round(im.height * 1200 / im.width)))
            src = os.path.join(_tmp, os.path.basename(str(path)).rsplit(".", 1)[0] + ".jpg")
            im.save(src, "JPEG", quality=80)
        iw, ih = PILImage.open(src).size
        w = max_w
        h = w * ih / iw
        if h > max_h:
            h, w = max_h, max_h * iw / ih
        elems = [RLImage(src, width=w, height=h)]
        if caption:
            elems.append(Paragraph(caption, cap))
        return KeepTogether(elems)

    story: list = []

    # --- title page ---
    story += [Spacer(1, 2.4 * cm),
              Paragraph(THESIS_TITLE, title_style),
              Spacer(1, 0.6 * cm),
              Paragraph("Accessibility of six utility services, measured with Voronoi "
                        "partitions, and data-driven recommendations for new facilities.", sub_style),
              Spacer(1, 1.2 * cm),
              fig(str(FIGURES_DIR / "zones_dhaka_flagship.png"), max_h=13 * cm),
              Spacer(1, 0.8 * cm),
              Paragraph(f"Minhazul Abedin &nbsp;·&nbsp; {datetime.date.today().isoformat()}",
                        ParagraphStyle("by", parent=body, alignment=TA_CENTER, fontSize=10)),
              PageBreak()]

    # --- 1. objective ---
    story += [Paragraph("1. Objective", h1),
              Paragraph(
        "This study evaluates how accessible Dhaka's utility services are — metro "
        "stations, hospitals, water sources, fuel stations, bus stops and fire "
        "stations. Each facility of a given type is used as a Voronoi seed, "
        "partitioning the city so that every location is assigned to its nearest "
        "facility. Large cells and long nearest-facility distances reveal coverage "
        "gaps; a greedy algorithm then proposes where new facilities would most "
        "improve access.", body)]

    # --- 2. data & method ---
    story += [Paragraph("2. Data &amp; Method", h1),
              Paragraph(
        "<b>Data.</b> Facility locations come from OpenStreetMap (via <i>osmnx</i>) "
        f"inside the Dhaka bounding box {DHAKA_BBOX}. Sparse categories can fall "
        "back to clearly-labelled synthetic landmark points; in this build all six "
        "services resolved to real OSM data.", body),
              Paragraph(
        "<b>Coordinate systems.</b> Input and output use WGS84 (EPSG:4326); every "
        "distance and area is computed in UTM zone 46N (EPSG:32646), in metres.", body),
              Paragraph(
        "<b>Cleaning.</b> Points are reprojected, de-duplicated within "
        f"{MIN_SEED_DISTANCE:.0f} m, and clipped to the OSM administrative boundary "
        "of Dhaka.", body),
              Paragraph(
        "<b>Voronoi construction.</b> Each cell is the intersection of the "
        "half-planes bounded by the perpendicular bisectors to its Delaunay "
        "neighbours, clipped to the study window and then to the city boundary. "
        "This guarantees every interior edge is a true perpendicular bisector and "
        "that the cells tile the region exactly.", body),
              Paragraph(
        "<b>Metrics.</b> Cell area (km²); nearest-facility distance on a "
        f"{GRID_SPACING_M:.0f} m grid (via a KD-tree). A location is "
        "<i>underserved</i> if its nearest facility exceeds a per-service distance "
        "threshold; a cell is <i>underserved</i> if its area exceeds mean + 1σ. "
        "Access is area-weighted (no population raster is used).", body)]

    # --- 3. textbook ---
    story += [PageBreak(), Paragraph("3. Textbook Voronoi (correctness proof)", h1),
              Paragraph(
        "Before analysing Dhaka, three hand-sketches (P.B, M.R, Phiruz) are redrawn "
        "as mathematically correct Voronoi diagrams: seeds in general position, "
        "straight perpendicular-bisector edges, and exactly three cells meeting at "
        "every vertex (red circles). The blue overlay proves one edge is the "
        "perpendicular bisector of its two seeds via a right-angle mark.", body),
              fig(str(FIGURES_DIR / "textbook_all.png"),
                  caption="Figure 1. The three sketches redrawn as correct Voronoi diagrams.")]

    # --- 4. coverage table ---
    story += [PageBreak(), Paragraph("4. Coverage results", h1),
              Paragraph("Per-service summary (distances converted to km):", body)]
    header = ["Service", "Facilities", "Mean cell\n(km²)", "Max cell\n(km²)",
              "Underserved\ncells", "Threshold\n(km)", "Max dist\n(km)", "Area under-\nserved (%)"]
    tdata = [header]
    for _, r in table.iterrows():
        tdata.append([r["label"], int(r["n_facilities"]), f"{r['mean_cell_km2']:.2f}",
                      f"{r['max_cell_km2']:.1f}", int(r["n_underserved_cells"]),
                      f"{r['threshold_m']/1000:.1f}", f"{r['max_nn_m']/1000:.1f}",
                      f"{r['pct_grid_underserved']:.0f}"])
    tbl = Table(tdata, colWidths=[3.1 * cm] + [1.75 * cm] * 7, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [tbl, Spacer(1, 0.3 * cm),
              Paragraph("<i>Table 1. Coverage metrics per service.</i>", cap)]

    # per-service figures
    for key in SERVICE_TYPES:
        label = SERVICE_TYPES[key].label
        cov = coverages[key]
        story += [PageBreak(), Paragraph(f"4.{list(SERVICE_TYPES).index(key)+1} {label}", h2),
                  Paragraph(
            f"{voronois[key].n} facilities. Mean cell {cov.mean_area_km2:.2f} km²; "
            f"{100*cov.frac_grid_underserved:.0f}% of the city lies beyond the "
            f"{cov.threshold_m/1000:.1f} km threshold, with the worst-served point "
            f"{cov.max_nn_m/1000:.1f} km from any facility.", body),
                  fig(str(FIGURES_DIR / f"voronoi_{key}.png"), max_h=17 * cm,
                      caption=f"{label} Voronoi over the Dhaka street map, "
                              "cells coloured by area (red outline = underserved).")]

    # --- 5. underserved summary ---
    worst = table.sort_values("pct_grid_underserved", ascending=False)
    story += [PageBreak(), Paragraph("5. Underserved-area summary", h1)]
    for _, r in worst.iterrows():
        story.append(Paragraph(
            f"<b>{r['label']}</b>: {r['pct_grid_underserved']:.0f}% of the city is beyond "
            f"the {r['threshold_m']/1000:.1f} km threshold; worst-served point is "
            f"{r['max_nn_m']/1000:.1f} km from any facility "
            f"({int(r['n_underserved_cells'])} oversized cells).", body))

    # --- 6. recommendations ---
    story += [PageBreak(), Paragraph("6. Recommendations", h1),
              Paragraph(
        f"For each service a greedy algorithm places K = {RECOMMEND_K} new facilities "
        "at the most-populated still-underserved locations, so new sites target where "
        "people actually lack access (not the empty fringe). The table shows the drop "
        "in underserved population and worst-case distance.", body)]
    rhead = ["Service", "Underserved people", "Worst access (km)", "New sites (area)"]
    rdata = [rhead]
    for key, rec in recs.items():
        zones_str = ", ".join(rec.new_zones)
        rdata.append([SERVICE_TYPES[key].label,
                      f"{rec.before.underserved_people/1000:.0f}k → "
                      f"{rec.after.underserved_people/1000:.0f}k",
                      f"{rec.before.max_nn_m/1000:.1f} → {rec.after.max_nn_m/1000:.1f}",
                      zones_str])
    rtbl = Table(rdata, colWidths=[3.2 * cm, 3.9 * cm, 3.5 * cm, 3.8 * cm], repeatRows=1)
    rtbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [rtbl, Spacer(1, 0.3 * cm),
              Paragraph("<i>Table 2. Coverage improvement from the proposed facilities.</i>", cap),
              fig(str(FIGURES_DIR / f"recommendations_{flagship_key}.png"), max_h=12 * cm,
                  caption=f"Existing (blue) vs proposed (red stars) "
                          f"{SERVICE_TYPES[flagship_key].label.lower()} sites.")]
    story.append(Paragraph("Exact proposed coordinates:", h2))
    for key, rec in recs.items():
        pts = "; ".join(f"{z} (lat {lat:.4f}, lon {lon:.4f})"
                        for (lon, lat), z in zip(rec.new_points_lonlat, rec.new_zones))
        story.append(Paragraph(f"<b>{SERVICE_TYPES[key].label}:</b> {pts}", body))

    # --- 7. which areas benefit / where to add ---
    story += [PageBreak(), Paragraph("7. Which areas benefit most — and where to add", h1),
              Paragraph(
        ("Each section is scored by the share of its <b>people</b> within reach of "
         "each utility, averaging the six services with emergencies (hospital, fire) "
         "and water weighted higher. Population is from WorldPop (1&nbsp;km, 2020)."
         if sb.pop_weighted else
         "Each section is scored by the share of its <b>area</b> within reach of each "
         "utility (no population raster was available), with hospital, fire and water "
         "weighted higher."), body),
              fig(str(FIGURES_DIR / "section_benefit.png"), max_h=15 * cm,
                  caption="Sections coloured green (well served) to red (underserved).")]
    bhead = (["Section", "Population", "Benefit", "Weakest service"] if sb.pop_weighted
             else ["Section", "Benefit", "Weakest service"])
    bdata = [bhead]
    for _, r in sb.df.iterrows():
        if sb.pop_weighted:
            bdata.append([r["section"], f"{r['pop_est']/1e6:.2f} M",
                          f"{r['benefit_score']:.0f}", r["weakest_service"]])
        else:
            bdata.append([r["section"], f"{r['benefit_score']:.0f}", r["weakest_service"]])
    bcw = [3.4 * cm, 3.0 * cm, 2.6 * cm, 4.3 * cm] if sb.pop_weighted else [4.5 * cm, 3 * cm, 5 * cm]
    btbl = Table(bdata, colWidths=bcw, repeatRows=1)
    btbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    best, worst = sb.df.iloc[0], sb.df.iloc[-1]
    story += [btbl, Spacer(1, 0.3 * cm),
              Paragraph("<i>Table 3. Section benefit ranking (higher = better served).</i>", cap),
              Paragraph(
        f"<b>Most benefited:</b> {best['section']} (score {best['benefit_score']:.0f}). "
        f"<b>Least benefited:</b> {worst['section']} (score {worst['benefit_score']:.0f}).", body),
              Paragraph("Where new facilities would help the most people:", h2)]
    for key in SERVICE_TYPES:
        up = sb.underserved_people[key]
        order = list(np.argsort(up)[::-1][:2])
        if sb.pop_weighted:
            parts = ", ".join(f"{sb.names[i]} (~{up[i]/1000:.0f}k underserved)" for i in order)
        else:
            parts = ", ".join(f"{sb.names[i]}" for i in order)
        story.append(Paragraph(f"<b>{SERVICE_TYPES[key].label}:</b> {parts}", body))

    # --- 8. extended analyses ---
    def _simple_table(header, rows, widths):
        d = [header] + rows
        tb = Table(d, colWidths=widths, repeatRows=1)
        tb.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f6")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return tb

    gini_line = ", ".join(f"{SERVICE_TYPES[k].label} {v:.2f}" for k, v in ext.gini_by_service.items())
    story += [PageBreak(), Paragraph("8. Extended analyses", h1),
              Paragraph(
        "Three analyses summarise the results beyond per-service coverage: a combined "
        "access index across all six utilities, the equity of that access, and a "
        "sensitivity check of the thresholds and weights.", body),
              Paragraph("8.1 Combined access and equity", h2),
              fig(str(FIGURES_DIR / "combined_access.png"), max_h=11 * cm,
                  caption="Combined access index (population-weighted mean over all utilities)."),
              Paragraph(
        f"Access is uneven across the population: the combined-access Gini coefficient "
        f"is <b>{ext.gini_combined:.3f}</b> (0 = perfectly equal, 1 = maximally unequal). "
        f"Per-service Gini of access: {gini_line}. The Lorenz curve below shows how far "
        "the access distribution departs from equality.", body),
              fig(str(FIGURES_DIR / "lorenz_access.png"), max_h=9 * cm,
                  caption="Lorenz curve of combined utility access."),
              Paragraph(
        f"Access is also strongly <b>spatially clustered</b>: Moran's I of the combined "
        f"access index is <b>{ext.moran[0]:.3f}</b> (pseudo p = {ext.moran[1]:.3f}, "
        "permutation test), so well- and poorly-served locations form contiguous regions "
        "rather than being randomly scattered — which supports treating the city as a "
        "small number of coherent sections.", body),
              Paragraph("8.2 Facility density (data completeness)", h2),
              Paragraph(
        "OpenStreetMap coverage is a lower bound; the densities below contextualise the "
        "counts against area and population.", body),
              _simple_table(["Service", "Facilities", "per 100k people", "km² / facility"],
                            [[r["service"], str(int(r["facilities"])), f"{r['per_100k_people']}",
                              f"{r['km2_per_facility']}"] for _, r in ext.density.iterrows()],
                            [4.2 * cm, 2.6 * cm, 3.4 * cm, 3.4 * cm]),
              Spacer(1, 0.2 * cm),
              Paragraph("8.3 Sensitivity of the section ranking", h2),
              Paragraph(
        "Re-running the section benefit score under altered thresholds and weights and "
        "correlating the section ranking against the baseline (Spearman ρ) tests how much "
        "the conclusions depend on those choices:", body),
              _simple_table(["Scenario", "Rank corr. (ρ)", "Best", "Worst"],
                            [[r["scenario"], f"{r['rank_corr_vs_baseline']}", r["best"], r["worst"]]
                             for _, r in ext.sensitivity.iterrows()],
                            [4.6 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm]),
              Spacer(1, 0.2 * cm),
              Paragraph(
        "High correlations indicate the best- and worst-served sections are robust to the "
        "exact thresholds and weights chosen.", cap)]

    story += [Paragraph("8.4 Validation against the 2SFCA method", h2),
              Paragraph(
        "The two-step floating catchment area (2SFCA) method (Luo &amp; Wang, 2003) is the "
        "standard supply–demand accessibility measure. Computing it per service and "
        "correlating its section ranking with the Voronoi nearest-distance ranking "
        "(Spearman ρ) tests whether the simpler Voronoi partition reproduces the same "
        "accessibility pattern:", body),
              fig(str(FIGURES_DIR / "tsfca_hospital.png"), max_h=10.5 * cm,
                  caption="2SFCA accessibility to hospitals, by section."),
              _simple_table(["Service", "2SFCA vs Voronoi ranking (ρ)"],
                            [[r["service"], f"{r['spearman_vs_voronoi']}"]
                             for _, r in ext.tsfca_agreement.iterrows()],
                            [6.0 * cm, 6.0 * cm]),
              Spacer(1, 0.2 * cm),
              Paragraph(
        "Agreement is strong for scarce, distance-dominated services (metro, water, "
        "hospital: ρ ≥ 0.7) and weaker for dense or demand-sensitive ones (bus, fuel, "
        "fire), where 2SFCA additionally penalises the crowding of facilities that a pure "
        "distance partition ignores. The two methods are therefore complementary: the "
        "Voronoi partition captures proximity cleanly and reproducibly, while 2SFCA adds "
        "supply–demand balance.", cap)]

    story += [Paragraph("8.5 Greedy vs optimal facility placement", h2),
              Paragraph(
        "The greedy recommender (§6) is compared against the exact solution of the Maximal "
        "Covering Location Problem (Church &amp; ReVelle, 1974) — an exhaustive search over "
        f"the same candidate sites for the {RECOMMEND_K} placements that cover the most "
        "underserved population. Coverage is shown in thousands of people:", body),
              _simple_table(["Service", "Greedy (k people)", "Optimal (k people)", "Greedy % of optimal"],
                            [[r["service"], f"{r['greedy_covered_k']:.0f}k",
                              f"{r['optimal_covered_k']:.0f}k", f"{r['greedy_pct_of_optimal']}%"]
                             for _, r in ext.mclp.iterrows()],
                            [3.8 * cm, 3.2 * cm, 3.2 * cm, 3.4 * cm]),
              Spacer(1, 0.2 * cm),
              Paragraph(
        "The greedy heuristic recovers most of the optimal coverage at a fraction of the "
        "cost, justifying its use for the recommendations.", cap)]

    _net_csv = PROCESSED_DIR / "network_comparison.csv"
    if _net_csv.exists() and (FIGURES_DIR / "network_vs_euclid.png").exists():
        ndf = pd.read_csv(_net_csv)
        story += [Paragraph("8.6 Road-network vs straight-line distance", h2),
                  Paragraph(
            "Repeating the coverage analysis with shortest-path distance on the Dhaka road "
            "network (43k nodes, 108k edges) instead of straight-line distance confirms that "
            "Euclidean distance understates real travel. The median detour factor and the "
            "resulting increase in underserved population are:", body),
                  fig(str(FIGURES_DIR / "network_vs_euclid.png"), max_h=9 * cm,
                      caption="Underserved population: straight-line vs road-network distance."),
                  _simple_table(["Service", "Median detour", "Underserved (line)", "Underserved (road)"],
                                [[r["service"], f"×{r['median_detour']}", f"{r['pct_under_euclid']}%",
                                  f"{r['pct_under_network']}%"] for _, r in ndf.iterrows()],
                                [3.6 * cm, 2.9 * cm, 3.1 * cm, 3.1 * cm])]

    # --- 9. flagship ---
    story += [PageBreak(), Paragraph("9. Zone-coloured flagship map", h1),
              Paragraph(
        "The real service Voronoi with every cell coloured by the named Dhaka zone "
        "its seed falls in (nearest zone centre). Dashed lines are the coarse "
        "eight-zone Voronoi boundaries — a single map that is both a correct "
        "Voronoi diagram and a recognisable partition of the city.", body),
              fig(str(FIGURES_DIR / "zones_dhaka_flagship.png"), max_h=18 * cm,
                  caption="Figure. Dhaka Voronoi coloured by named zone (densest service).")]

    # --- 10. limitations & repro ---
    story += [PageBreak(), Paragraph("10. Limitations", h1),
              Paragraph(
        "• OpenStreetMap completeness varies by category, so facility counts are a "
        "lower bound.<br/>"
        "• The coverage metrics (§4) and the greedy recommendations (§6) are "
        "area-based, so they lean toward the low-density eastern fringe. The section "
        "benefit analysis (§7) corrects for this — it is population-weighted "
        "(WorldPop 1&nbsp;km, 2020) with emergency services weighted higher, and is "
        "the people-first view of where to invest.<br/>"
        "• The study window is the Dhaka bbox intersected with the OSM admin "
        "polygon; peripheral cells extend to that boundary.<br/>"
        "• Any synthetic fallback points would be flagged in <i>data/SOURCE.md</i> "
        "and the <i>source</i> column (none were needed here).", body),
              Paragraph("11. Reproducibility", h1),
              Paragraph(
        "The entire analysis and this report are produced by a single script:", body),
              Paragraph(
        '<font face="Courier">pip install -r requirements.txt<br/>'
        'python voronoi_dhaka.py</font>', body),
              Paragraph(
        "Data source: © OpenStreetMap contributors. Basemap: © CartoDB. "
        "Geometry with SciPy / Shapely; maps with GeoPandas / contextily / folium.", cap)]

    story += _literature_flowables(h1, h2, body, cap, "12. Literature review", "13. References")

    doc.build(story)
    return str(out)


def export_office_pdfs() -> list[str]:
    """Convert the Word/PowerPoint deliverables to PDF via LibreOffice, if available.

    Returns the paths written. Skips silently (with a note) when LibreOffice is not
    installed, since the .docx/.pptx files remain the primary artefacts."""
    import shutil
    import subprocess

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
        soffice = str(mac) if mac.exists() else None
    if soffice is None:
        print("    [pdf] LibreOffice not found; skipping .docx/.pptx -> PDF export")
        return []

    targets = ["Dhaka_Voronoi_AIUB_Thesis.docx", "Dhaka_Voronoi_Poster_AIUB.pptx",
               "Dhaka_Voronoi_Slides.pptx"]
    written = []
    for name in targets:
        src_file = OUTPUTS_DIR / name
        if not src_file.exists():
            continue
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                            "--outdir", str(OUTPUTS_DIR), str(src_file)],
                           check=True, capture_output=True, timeout=300)
        except Exception as exc:
            print(f"    [pdf] {name}: conversion failed ({type(exc).__name__})")
            continue
        out = src_file.with_suffix(".pdf")
        if out.exists():
            written.append(str(out))
    return written


# =========================================================================== #
# MAIN
# =========================================================================== #
def _need(path: str, force: bool) -> bool:
    return force or not Path(path).exists()


def main(force_figures: bool = False, k: int = RECOMMEND_K, network: bool = False) -> None:
    print("=" * 60)
    print("Voronoi analysis of Dhaka utility services")
    print("=" * 60)

    print("\n[1/7] textbook Voronoi")
    if force_figures or not (FIGURES_DIR / "textbook_all.png").exists():
        render_textbook()

    print("[2/7] data (OSM, cached)")
    boundary = boundary_metric()
    for key in SERVICE_TYPES:
        load_points(key)

    print("[3/7] Voronoi + coverage")
    ref = zone_reference()
    voronois, coverages, rows = {}, {}, []
    for key in SERVICE_TYPES:
        sv = build_service_voronoi(key, boundary)
        cov = compute_coverage(sv)
        voronois[key], coverages[key] = sv, cov
        rows.append(metrics_row(sv, cov))
        print(f"      {key:14s} n={sv.n:4d}  mean_cell={cov.mean_area_km2:5.2f}km²  "
              f"underserved={100*cov.frac_grid_underserved:4.1f}%")
    table = pd.DataFrame(rows)
    table.to_csv(REPORT_DIR / "coverage_metrics.csv", index=False)
    flagship_key = max(voronois, key=lambda k: voronois[k].n)

    print("[4/7] recommendations (population-targeted)")
    grid_pop = sample_population(make_grid(boundary))
    recs = {key: greedy_new_facilities(sv, coverages[key], ref, k=k, pop=grid_pop)
            for key, sv in voronois.items()}

    print("[5/7] section benefit + extended analyses (equity, combined access, sensitivity)")
    sb = section_benefit(voronois, ref, pop=grid_pop)
    plot_section_benefit(voronois, ref, sb)
    for _, r in sb.df.iterrows():
        pop = f"{r['pop_est']/1e6:.2f}M" if sb.pop_weighted else "n/a"
        print(f"      {r['section']:12s} benefit={r['benefit_score']:5.1f}  pop={pop:>7s}  "
              f"weakest={r['weakest_service']}")
    ext = extended_analysis(voronois, ref, grid_pop)
    plot_combined_access(voronois, ref, ext)
    plot_lorenz(ext)
    plot_2sfca(voronois, ref, ext, "hospital")
    print(f"      combined-access Gini = {ext.gini_combined:.3f}  "
          f"(rank stability vs baseline: "
          f"{', '.join(f'{r.scenario}={r.rank_corr_vs_baseline}' for r in ext.sensitivity.itertuples() if r.scenario!='baseline')})")
    if network:
        network_analysis(voronois, grid_pop)

    print("[6/7] figures")
    for key, sv in voronois.items():
        cov = coverages[key]
        for path, fn in [
            (FIGURES_DIR / f"voronoi_{key}.png", lambda: plot_service_voronoi(sv, cov)),
            (FIGURES_DIR / f"recommendations_{key}.png", lambda: plot_recommendations(sv, recs[key])),
            (FIGURES_DIR / f"zones_{key}.png", lambda: plot_zone_colored_voronoi(sv, ref)),
        ]:
            if _need(str(path), force_figures):
                fn()
        folium_service_map(sv, cov, recs[key])
    if _need(str(FIGURES_DIR / "zones_dhaka_flagship.png"), force_figures):
        plot_zone_colored_voronoi(voronois[flagship_key], ref, flagship=True)
    headline_html = folium_sections_map(voronois, ref)

    print("[7/7] PDF report + literature review")
    pdf = build_pdf_report(voronois, coverages, table, recs, flagship_key, sb, ext)
    pdf_light = build_pdf_report(voronois, coverages, table, recs, flagship_key, sb, ext, light=True)
    litpdf = build_literature_pdf()
    litdocx = build_literature_docx()
    thesisdocx = build_thesis_docx(table, sb, ext, recs, flagship_key)
    poster = build_poster(table, sb, ext, recs, flagship_key)
    plot_gantt()
    aiub = build_aiub_thesis_docx(table, sb, ext, recs, flagship_key, voronois)
    print("\nDONE")
    print("  PDF (static, full)                             ->", pdf)
    print("  PDF (static, lightweight)                      ->", pdf_light)
    print("  Literature review (PDF)                        ->", litpdf)
    print("  Literature review (Word, editable)             ->", litdocx)
    print("  Thesis draft (Word: Abstract, Ch.1,3,4,5)      ->", thesisdocx)
    print("  AIUB-formatted thesis (Word, full)             ->", aiub)
    print("  Defense poster (A1)                            ->", poster)
    for _p in export_office_pdfs():
        print("  PDF export                                     ->", _p)
    print("  Benefit map                                    -> outputs/figures/section_benefit.png")
    print("  Interactive — Dhaka sections + all utilities   ->", headline_html)
    print("  Interactive — per-utility Voronoi coverage     -> outputs/report/interactive_<service>.html")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Voronoi utility-services analysis for Dhaka City.")
    p.add_argument("--force", action="store_true", help="regenerate every figure from scratch")
    p.add_argument("--k", type=int, default=RECOMMEND_K,
                   help="number of new facilities proposed per service (default 3)")
    p.add_argument("--network", action="store_true",
                   help="also run road-network distance analysis (downloads the Dhaka graph)")
    args = p.parse_args()
    main(force_figures=args.force, k=args.k, network=args.network)
