"""Project configuration: CRS, Dhaka bounding box, service definitions, paths.

All distance and area computations happen in the metric CRS (``CRS_METRIC``).
Geographic coordinates (lon/lat) only ever appear at the I/O boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORT_DIR = OUTPUTS_DIR / "report"

for _d in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Coordinate reference systems
# --------------------------------------------------------------------------- #
# Geographic (WGS84) for I/O; UTM zone 46N (metres) for all geometry/maths.
CRS_GEO = "EPSG:4326"
CRS_METRIC = "EPSG:32646"  # WGS84 / UTM zone 46N — correct zone for Dhaka

# --------------------------------------------------------------------------- #
# Study area
# --------------------------------------------------------------------------- #
# Dhaka metropolitan area (Dhaka North + South City Corporations and fringe).
# (min_lon, min_lat, max_lon, max_lat)
DHAKA_BBOX = (90.33, 23.66, 90.50, 23.90)

# OSM administrative relation used to fetch the real city boundary polygon.
# Falls back to the rectangle above if the lookup fails (see data_clean.py).
DHAKA_ADMIN_QUERY = "Dhaka, Bangladesh"

# Figures are always saved at this resolution.
FIGURE_DPI = 300

# General-position / dedup distance in metres. Seeds closer than this are
# treated as duplicates; also used to jitter cocircular textbook seeds.
MIN_SEED_DISTANCE = 150.0

# Fine grid spacing (metres) for nearest-facility distance rasters.
GRID_SPACING_M = 250.0

# Random seed for any synthetic-data generation (reproducibility).
RANDOM_SEED = 42


# --------------------------------------------------------------------------- #
# Service catalogue
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ServiceType:
    """One utility-service category.

    Attributes
    ----------
    key:            machine name / filename stem.
    label:         human-readable label for legends and reports.
    osm_tags:      tag filter handed to ``osmnx.features_from_bbox``.
    color:         matplotlib/folium colour for markers and cells.
    min_count:     validation minimum (gate 4) — fewer points => fail.
    underserved_m: nearest-facility distance (m) above which a location is
                   considered underserved for this service.
    """

    key: str
    label: str
    osm_tags: dict[str, list[str] | str] = field(default_factory=dict)
    color: str = "#333333"
    min_count: int = 5
    underserved_m: float = 2000.0


SERVICE_TYPES: dict[str, ServiceType] = {
    "metro_station": ServiceType(
        key="metro_station",
        label="Metro station",
        osm_tags={"railway": ["station", "halt"], "station": ["subway"]},
        color="#d62728",
        min_count=15,
        underserved_m=2000.0,
    ),
    "hospital": ServiceType(
        key="hospital",
        label="Hospital",
        osm_tags={"amenity": ["hospital"]},
        color="#2ca02c",
        min_count=20,
        underserved_m=2000.0,
    ),
    "water_pump": ServiceType(
        key="water_pump",
        label="Water pump / source",
        osm_tags={
            "man_made": ["water_well", "pumping_station", "water_works"],
            "amenity": ["drinking_water"],
        },
        color="#1f77b4",
        min_count=10,
        underserved_m=1000.0,
    ),
    "fuel": ServiceType(
        key="fuel",
        label="Fuel station",
        osm_tags={"amenity": ["fuel"]},
        color="#ff7f0e",
        min_count=20,
        underserved_m=1500.0,
    ),
    "bus_stop": ServiceType(
        key="bus_stop",
        label="Bus stop",
        osm_tags={"highway": ["bus_stop"], "public_transport": ["platform"]},
        color="#9467bd",
        min_count=30,
        underserved_m=800.0,
    ),
    "fire_station": ServiceType(
        key="fire_station",
        label="Fire station",
        osm_tags={"amenity": ["fire_station"]},
        color="#8c564b",
        min_count=8,
        underserved_m=3000.0,
    ),
}

# Number of new facilities the recommender proposes per service.
RECOMMEND_K = 3


# --------------------------------------------------------------------------- #
# Named Dhaka zones (Track C — zone-colored Voronoi)
# --------------------------------------------------------------------------- #
# Eight recognizable areas with good spatial spread. Each centre is an anchor:
# every fine service cell inherits the colour of the nearest zone centre
# (a coarse Voronoi-of-zones membership test, done in the metric CRS).
# Colours are the qualitative matplotlib ``tab10`` palette.
ZONES: dict[str, dict] = {
    "Uttara":      {"center": (90.3975, 23.8745), "color": "#1f77b4"},  # north
    "Mirpur":      {"center": (90.3654, 23.8060), "color": "#ff7f0e"},  # northwest
    "Bashundhara": {"center": (90.4350, 23.8150), "color": "#9467bd"},  # northeast
    "Banani":      {"center": (90.4022, 23.7940), "color": "#d62728"},  # north-central
    "Gulshan":     {"center": (90.4155, 23.7830), "color": "#2ca02c"},  # central-east
    "Dhanmondi":   {"center": (90.3750, 23.7460), "color": "#8c564b"},  # central-west
    "Khilgaon":    {"center": (90.4280, 23.7500), "color": "#17becf"},  # southeast
    "Motijheel":   {"center": (90.4170, 23.7280), "color": "#e377c2"},  # central-south / old Dhaka
}

