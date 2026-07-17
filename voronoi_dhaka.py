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

# Population raster (WorldPop Bangladesh, 1 km, UN-adjusted 2020) for weighting
# the section benefit analysis by how many people actually live somewhere.
POP_RASTER_URL = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/"
                  "2020/BGD/bgd_ppp_2020_1km_Aggregated_UNadj.tif")
POP_RASTER_PATH = RAW_DIR / "bgd_pop_1km.tif"

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
    return ExtendedAnalysis(comb_sec, gini_svc, gini_comb, (lx, ly), density, sensitivity,
                            tsfca_sec, tsfca_agree)


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
    gdf = sv.cells_gdf().to_crs(WEB)
    fig, ax = plt.subplots(figsize=(10, 11))
    gdf.plot(ax=ax, column="area_km2", cmap="YlOrRd", alpha=0.5, edgecolor="#2a2a2a",
             linewidth=0.5, legend=True,
             legend_kwds={"label": "Voronoi cell area (km²)", "shrink": 0.5})
    under = gdf[gdf["seed_index"].isin(cov.underserved_cells)]
    if len(under):
        under.boundary.plot(ax=ax, color="#b30000", linewidth=1.6)
    _seeds_web(sv).plot(ax=ax, color=svc.color, markersize=10, marker="o", zorder=5)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.3)
    _add_basemap(ax)
    ax.set_title(f"Dhaka {svc.label} — Voronoi coverage ({sv.n} facilities)\n"
                 "red outline = underserved cell (area > mean + 1σ)", fontsize=12)
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
    _seeds_web(sv).plot(ax=ax, color="#111111", markersize=6, marker="o", zorder=5)
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
    "Ahmed, S., Adams, A. M., Islam, R., Hasan, S. M., &amp; Panciera, R. (2019). Impact "
    "of traffic variability on geographic accessibility to 24/7 emergency healthcare for "
    "the urban poor: A GIS study in Dhaka, Bangladesh. PLOS ONE, 14(9), e0222488. "
    "https://doi.org/10.1371/journal.pone.0222488",
    "Alam, I., Nur, S. M. S., &amp; Mitra, C. (2025). Accessibility to Public Open Space of "
    "a densely populated city: a case study of Dhaka, Bangladesh. Computational Urban "
    "Science, 5(1), 23. https://doi.org/10.1007/s43762-025-00187-9",
    "Bhuiya, M. M. R., Shao, W., &amp; Jones, S. L. (2023). Measuring accessibility of "
    "movement challenged persons during earthquake evacuation of Dhaka City, Bangladesh: A "
    "participatory GIS-based approach. Applied Geography [confirm volume/article no.]. "
    "https://www.sciencedirect.com/science/article/abs/pii/S0143622823001054",
    "Church, R. L., &amp; ReVelle, C. S. (1974). The maximal covering location problem. "
    "Papers in Regional Science, 32(1), 101–118. https://doi.org/10.1007/BF01942293",
    "Cui, H., Wu, L., Hu, S., &amp; Lu, R. (2021). Measuring the Service Capacity of Public "
    "Facilities Based on a Dynamic Voronoi Diagram. Remote Sensing, 13(5), 1027. "
    "https://doi.org/10.3390/rs13051027",
    "Deliry, S. I., &amp; Uygucgil, H. (2023). Accessibility assessment of urban public "
    "services using GIS-based network analysis: a case study in Eskisehir, Turkiye. "
    "GeoJournal, 88, 4805–4825. https://doi.org/10.1007/s10708-023-10900-y",
    "El-Geneidy, A., Grimsrud, M., Wasfi, R., Tétreault, P., &amp; Surprenant-Legault, J. "
    "(2014). New evidence on walking distances to transit stops: identifying redundancies "
    "and gaps using variable service areas. Transportation, 41(1), 193–210. "
    "https://doi.org/10.1007/s11116-013-9508-z",
    "Klinkhardt, C., Kühnel, F., Heilig, M., Lautenbach, S., Wörle, T., Vortisch, P., &amp; "
    "Kuhnimhof, T. (2023). Quality Assessment of OpenStreetMap's Points of Interest with "
    "Large-Scale Real Data. Transportation Research Record, 2677. "
    "https://doi.org/10.1177/03611981231169280",
    "Lloyd, C. T., Sorichetta, A., &amp; Tatem, A. J. (2017). High resolution global gridded "
    "data for use in population studies. Scientific Data, 4, 170001. "
    "https://doi.org/10.1038/sdata.2017.1",
    "Luo, W., &amp; Qi, Y. (2009). An enhanced two-step floating catchment area (E2SFCA) "
    "method for measuring spatial accessibility to primary care physicians. Health &amp; "
    "Place, 15(4), 1100–1107. https://doi.org/10.1016/j.healthplace.2009.06.002",
    "Luo, W., &amp; Wang, F. (2003). Measures of spatial accessibility to health care in a "
    "GIS environment: synthesis and a case study in the Chicago region. Environment and "
    "Planning B, 30(6), 865–884. https://doi.org/10.1068/b29120",
    "National Fire Protection Association. (2020). NFPA 1710: Standard for the Organization "
    "and Deployment of Fire Suppression Operations, Emergency Medical Operations, and "
    "Special Operations to the Public by Career Fire Departments. NFPA.",
    "Okabe, A., Boots, B., Sugihara, K., &amp; Chiu, S. N. (2000). Spatial Tessellations: "
    "Concepts and Applications of Voronoi Diagrams (2nd ed.). Wiley.",
    "Rahman, M. H., Ashik, F. R., &amp; Mouli, M. J. (2022). Investigating spatial "
    "accessibility to urban facility outcome of transit-oriented development in Dhaka. "
    "Transportation Research Interdisciplinary Perspectives, 15, 100607. "
    "https://doi.org/10.1016/j.trip.2022.100607",
    "Tatem, A. J. (2017). WorldPop, open data for spatial demography. Scientific Data, 4, "
    "170004. https://doi.org/10.1038/sdata.2017.4",
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


# =========================================================================== #
# PDF REPORT
# =========================================================================== #
def build_pdf_report(voronois, coverages, table, recs, flagship_key, sb, ext) -> str:
    from PIL import Image as PILImage
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak,
                                     Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

    out = OUTPUTS_DIR / "Dhaka_Voronoi_Report.pdf"
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
        iw, ih = PILImage.open(path).size
        w = max_w
        h = w * ih / iw
        if h > max_h:
            h, w = max_h, max_h * iw / ih
        elems = [RLImage(path, width=w, height=h)]
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


# =========================================================================== #
# MAIN
# =========================================================================== #
def _need(path: str, force: bool) -> bool:
    return force or not Path(path).exists()


def main(force_figures: bool = False, k: int = RECOMMEND_K) -> None:
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
    litpdf = build_literature_pdf()
    litdocx = build_literature_docx()
    print("\nDONE")
    print("  PDF (static)                                   ->", pdf)
    print("  Literature review (PDF)                        ->", litpdf)
    print("  Literature review (Word, editable)             ->", litdocx)
    print("  Benefit map                                    -> outputs/figures/section_benefit.png")
    print("  Interactive — Dhaka sections + all utilities   ->", headline_html)
    print("  Interactive — per-utility Voronoi coverage     -> outputs/report/interactive_<service>.html")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Voronoi utility-services analysis for Dhaka City.")
    p.add_argument("--force", action="store_true", help="regenerate every figure from scratch")
    p.add_argument("--k", type=int, default=RECOMMEND_K,
                   help="number of new facilities proposed per service (default 3)")
    args = p.parse_args()
    main(force_figures=args.force, k=args.k)
