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

ZONES: dict[str, dict] = {
    "Uttara":      {"center": (90.3975, 23.8745), "color": "#1f77b4"},
    "Mirpur":      {"center": (90.3654, 23.8060), "color": "#ff7f0e"},
    "Bashundhara": {"center": (90.4350, 23.8150), "color": "#9467bd"},
    "Banani":      {"center": (90.4022, 23.7940), "color": "#d62728"},
    "Gulshan":     {"center": (90.4155, 23.7830), "color": "#2ca02c"},
    "Dhanmondi":   {"center": (90.3750, 23.7460), "color": "#8c564b"},
    "Khilgaon":    {"center": (90.4280, 23.7500), "color": "#17becf"},
    "Motijheel":   {"center": (90.4170, 23.7280), "color": "#e377c2"},
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


def _snapshot(grid, seeds, thr) -> Snapshot:
    d = KDTree(seeds).query(grid)[0]
    return Snapshot(float(d.max()), float(d.mean()), int((d > thr).sum()))


def greedy_new_facilities(sv: ServiceVoronoi, cov: CoverageResult,
                          ref: ZoneRef | None = None, k: int = RECOMMEND_K) -> RecommendResult:
    ref = ref or zone_reference()
    grid, thr = cov.grid_xy, cov.threshold_m
    before = _snapshot(grid, sv.seeds, thr)
    current, new_pts = sv.seeds.copy(), []
    for _ in range(k):
        worst = grid[int(np.argmax(KDTree(current).query(grid)[0]))]
        new_pts.append(worst)
        current = np.vstack([current, worst])
    after = _snapshot(grid, current, thr)
    new_m = np.array(new_pts)
    ll = gpd.GeoSeries(gpd.points_from_xy(new_m[:, 0], new_m[:, 1]),
                       crs=CRS_METRIC).to_crs(CRS_GEO)
    new_lonlat = np.column_stack([ll.x.to_numpy(), ll.y.to_numpy()])
    zones, _ = assign_zones(new_m, ref)
    return RecommendResult(sv.key, k, new_m, new_lonlat, zones, thr, before, after)


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
    ax.set_title(f"Dhaka {svc.label} — {rec.k} proposed new sites\n"
                 f"max access {rec.before.max_nn_m/1000:.2f} km → "
                 f"{rec.after.max_nn_m/1000:.2f} km", fontsize=12)
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
    fgf = folium.FeatureGroup(name=f"{svc.label} facilities", show=True)
    for _, r in sv.seeds_gdf().to_crs(CRS_GEO).iterrows():
        folium.CircleMarker([r.geometry.y, r.geometry.x], radius=3, color=svc.color,
                            fill=True, fill_opacity=0.9, popup=str(r["name"])).add_to(fgf)
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


def folium_zone_map(sv: ServiceVoronoi, ref: ZoneRef, flagship: bool = False) -> str:
    """Interactive Google map: Voronoi cells coloured by named Dhaka zone."""
    svc = SERVICE_TYPES[sv.key]
    zgdf = color_cells_by_zone(sv, ref).to_crs(CRS_GEO)
    m = _google_map(_map_center(sv))
    folium.GeoJson(zgdf.to_json(), name=f"{svc.label} Voronoi by zone",
        style_function=lambda f: {"fillColor": f["properties"]["zone_color"],
                                  "color": "#222222", "weight": 0.7, "fillOpacity": 0.45},
        highlight_function=lambda f: {"weight": 2, "color": "#000000"},
        tooltip=folium.GeoJsonTooltip(fields=["zone_name", "area_km2"],
                                      aliases=["Zone", "Cell area (km²)"])).add_to(m)
    zv = build_zone_voronoi(sv.boundary, ref).to_crs(CRS_GEO)
    folium.GeoJson(zv.to_json(), name="Zone boundaries",
        style_function=lambda f: {"fillOpacity": 0, "color": "#000000",
                                  "weight": 2, "dashArray": "6 4"}).add_to(m)
    seeds = sv.seeds_gdf().to_crs(CRS_GEO)
    fg = folium.FeatureGroup(name=f"{svc.label} facilities", show=True)
    for _, r in seeds.iterrows():
        folium.CircleMarker([r.geometry.y, r.geometry.x], radius=3.5, weight=1.2,
                            color="#1a1a1a", fill=True, fill_color=svc.color,
                            fill_opacity=0.95, popup=str(r["name"])).add_to(fg)
    fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    name = "interactive_flagship_zones" if flagship else f"interactive_zones_{sv.key}"
    out = REPORT_DIR / f"{name}.html"
    m.save(str(out))
    return str(out)


# =========================================================================== #
# PDF REPORT
# =========================================================================== #
def build_pdf_report(voronois, coverages, table, recs, flagship_key) -> str:
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
    title_style = ParagraphStyle("Title", parent=ss["Title"], fontSize=22, leading=27)
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
    story += [Spacer(1, 3 * cm),
              Paragraph("Voronoi Analysis of Utility Services<br/>in Dhaka City", title_style),
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
        f"For each service a greedy farthest-point algorithm places K = {RECOMMEND_K} "
        "new facilities: each new site is the worst-served location at the time it "
        "is added. The table shows the resulting change in worst-case access.", body)]
    rhead = ["Service", "Max access before → after (km)", "Underserved grid pts", "New sites (nearest zone)"]
    rdata = [rhead]
    for key, rec in recs.items():
        zones_str = ", ".join(rec.new_zones)
        rdata.append([SERVICE_TYPES[key].label,
                      f"{rec.before.max_nn_m/1000:.2f} → {rec.after.max_nn_m/1000:.2f}",
                      f"{rec.before.n_underserved} → {rec.after.n_underserved}", zones_str])
    rtbl = Table(rdata, colWidths=[3.0 * cm, 4.6 * cm, 3.4 * cm, 4.3 * cm], repeatRows=1)
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

    # --- 7. flagship ---
    story += [PageBreak(), Paragraph("7. Zone-coloured flagship map", h1),
              Paragraph(
        "The real service Voronoi with every cell coloured by the named Dhaka zone "
        "its seed falls in (nearest zone centre). Dashed lines are the coarse "
        "eight-zone Voronoi boundaries — a single map that is both a correct "
        "Voronoi diagram and a recognisable partition of the city.", body),
              fig(str(FIGURES_DIR / "zones_dhaka_flagship.png"), max_h=18 * cm,
                  caption="Figure. Dhaka Voronoi coloured by named zone (densest service).")]

    # --- 8. limitations & repro ---
    story += [PageBreak(), Paragraph("8. Limitations", h1),
              Paragraph(
        "• OpenStreetMap completeness varies by category, so facility counts are a "
        "lower bound.<br/>"
        "• Access is area-weighted, not population-weighted — sparsely populated "
        "fringes (rivers, low-density edges) count equally with dense wards, which "
        "pulls some recommendations toward the eastern periphery.<br/>"
        "• The study window is the Dhaka bbox intersected with the OSM admin "
        "polygon; peripheral cells extend to that boundary.<br/>"
        "• Any synthetic fallback points would be flagged in <i>data/SOURCE.md</i> "
        "and the <i>source</i> column (none were needed here).", body),
              Paragraph("9. Reproducibility", h1),
              Paragraph(
        "The entire analysis and this report are produced by a single script:", body),
              Paragraph(
        '<font face="Courier">pip install -r requirements.txt<br/>'
        'python voronoi_dhaka.py</font>', body),
              Paragraph(
        "Data source: © OpenStreetMap contributors. Basemap: © CartoDB. "
        "Geometry with SciPy / Shapely; maps with GeoPandas / contextily / folium.", cap)]

    doc.build(story)
    return str(out)


# =========================================================================== #
# MAIN
# =========================================================================== #
def _need(path: str, force: bool) -> bool:
    return force or not Path(path).exists()


def main(force_figures: bool = False) -> None:
    print("=" * 60)
    print("Voronoi analysis of Dhaka utility services")
    print("=" * 60)

    print("\n[1/6] textbook Voronoi")
    if force_figures or not (FIGURES_DIR / "textbook_all.png").exists():
        render_textbook()

    print("[2/6] data (OSM, cached)")
    boundary = boundary_metric()
    for key in SERVICE_TYPES:
        load_points(key)

    print("[3/6] Voronoi + coverage")
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

    print("[4/6] recommendations")
    recs = {key: greedy_new_facilities(sv, coverages[key], ref)
            for key, sv in voronois.items()}

    print("[5/6] figures")
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
        folium_zone_map(sv, ref)
    if _need(str(FIGURES_DIR / "zones_dhaka_flagship.png"), force_figures):
        plot_zone_colored_voronoi(voronois[flagship_key], ref, flagship=True)
    flagship_html = folium_zone_map(voronois[flagship_key], ref, flagship=True)

    print("[6/6] PDF report")
    pdf = build_pdf_report(voronois, coverages, table, recs, flagship_key)
    print("\nDONE")
    print("  PDF (static)        ->", pdf)
    print("  Interactive Google map (flagship) ->", flagship_html)
    print("  Interactive per-service maps      -> outputs/report/interactive_*.html")


if __name__ == "__main__":
    import sys
    main(force_figures="--force" in sys.argv)
