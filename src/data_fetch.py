"""Track B, phase 4.1 — collect utility POIs for Dhaka.

Primary source is OpenStreetMap via ``osmnx``. Fetches are cached under
``data/raw/osm_cache`` so re-runs are deterministic and offline-friendly.
When OSM returns fewer than a service's ``min_count`` (a sparse category, or
no network), we supplement with clearly-labelled ``SYNTHETIC`` points drawn
from known Dhaka landmark lists (e.g. the MRT Line-6 corridor, major
hospitals) or a reproducible zone-clustered scatter.
"""

from __future__ import annotations

import warnings

import numpy as np
import osmnx as ox
import pandas as pd

from . import config

ox.settings.use_cache = True
ox.settings.cache_folder = str(config.RAW_DIR / "osm_cache")
ox.settings.requests_timeout = 90
ox.settings.log_console = False

RAW_COLUMNS = ["name", "lon", "lat", "source"]


# --------------------------------------------------------------------------- #
# Synthetic landmark lists (real, well-known locations; approximate coords)
# --------------------------------------------------------------------------- #
# MRT Line-6 corridor, north (Uttara) to south (Motijheel) — 16 stations.
_MRT6 = [
    ("Uttara North", 90.4030, 23.8710),
    ("Uttara Center", 90.4000, 23.8620),
    ("Uttara South", 90.3970, 23.8540),
    ("Pallabi", 90.3660, 23.8280),
    ("Mirpur 11", 90.3665, 23.8210),
    ("Mirpur 10", 90.3685, 23.8070),
    ("Kazipara", 90.3720, 23.7980),
    ("Shewrapara", 90.3760, 23.7900),
    ("Agargaon", 90.3800, 23.7780),
    ("Bijoy Sarani", 90.3840, 23.7690),
    ("Farmgate", 90.3900, 23.7580),
    ("Kawran Bazar", 90.3930, 23.7510),
    ("Shahbagh", 90.3960, 23.7390),
    ("Dhaka University", 90.3970, 23.7330),
    ("Bangladesh Secretariat", 90.4090, 23.7300),
    ("Motijheel", 90.4180, 23.7280),
]

# Major Dhaka hospitals (24).
_HOSPITALS = [
    ("Dhaka Medical College Hospital", 90.3990, 23.7260),
    ("Square Hospital", 90.3770, 23.7540),
    ("United Hospital", 90.4180, 23.8030),
    ("Evercare (Apollo) Hospital", 90.4250, 23.8130),
    ("BSMMU", 90.3960, 23.7390),
    ("BIRDEM General Hospital", 90.3970, 23.7380),
    ("Holy Family Red Crescent", 90.4080, 23.7430),
    ("Ibn Sina Dhanmondi", 90.3730, 23.7480),
    ("Popular Diagnostic Dhanmondi", 90.3760, 23.7500),
    ("Labaid Hospital Dhanmondi", 90.3790, 23.7460),
    ("Central Hospital", 90.3810, 23.7530),
    ("National Heart Foundation", 90.3690, 23.8000),
    ("Kurmitola General Hospital", 90.3970, 23.8400),
    ("Sher-e-Bangla Nagar Hospital", 90.3680, 23.7770),
    ("Shaheed Suhrawardy Hospital", 90.3690, 23.7760),
    ("Mugda Medical College", 90.4310, 23.7360),
    ("Sir Salimullah Mitford", 90.4020, 23.7100),
    ("Bangladesh Medical College", 90.3760, 23.7530),
    ("Delta Health Care Mirpur", 90.3640, 23.7960),
    ("Green Life Hospital", 90.3830, 23.7490),
    ("Anwer Khan Modern Hospital", 90.3820, 23.7520),
    ("City Hospital Mirpur", 90.3660, 23.7980),
    ("Uttara Adhunik Medical", 90.3990, 23.8660),
    ("Shaheed Monsur Ali Uttara", 90.3960, 23.8620),
]

# Dhaka Fire Service & Civil Defence stations (12).
_FIRE = [
    ("Kakrail Fire Station (HQ)", 90.4030, 23.7390),
    ("Sadarghat Fire Station", 90.4090, 23.7060),
    ("Mirpur Fire Station", 90.3660, 23.8060),
    ("Mohammadpur Fire Station", 90.3590, 23.7590),
    ("Tejgaon Fire Station", 90.3930, 23.7620),
    ("Postagola Fire Station", 90.4340, 23.6960),
    ("Lalbagh Fire Station", 90.3880, 23.7180),
    ("Kurmitola Fire Station", 90.3980, 23.8380),
    ("Baridhara Fire Station", 90.4180, 23.7960),
    ("Uttara Fire Station", 90.3990, 23.8690),
    ("Khilgaon Fire Station", 90.4260, 23.7500),
    ("Demra Fire Station", 90.4560, 23.7110),
]

_LANDMARKS: dict[str, list[tuple[str, float, float]]] = {
    "metro_station": _MRT6,
    "hospital": _HOSPITALS,
    "fire_station": _FIRE,
}

# Distributed services with no compact landmark list: scatter reproducibly
# around the populated zone centres.
_DISTRIBUTED_COUNT = {
    "water_pump": 28,
    "fuel": 40,
    "bus_stop": 72,
}


# --------------------------------------------------------------------------- #
# Synthetic generation
# --------------------------------------------------------------------------- #
def _synthetic_distributed(service_key: str, n: int) -> pd.DataFrame:
    """Reproducible zone-clustered scatter inside the Dhaka bbox."""
    rng = np.random.default_rng(config.RANDOM_SEED + hash(service_key) % 10_000)
    centres = np.array([z["center"] for z in config.ZONES.values()])
    minlon, minlat, maxlon, maxlat = config.DHAKA_BBOX
    rows = []
    i = 0
    while len(rows) < n:
        c = centres[rng.integers(len(centres))]
        lon = c[0] + rng.normal(0, 0.018)
        lat = c[1] + rng.normal(0, 0.014)
        if minlon <= lon <= maxlon and minlat <= lat <= maxlat:
            rows.append((f"{service_key} #{i + 1}", lon, lat, "SYNTHETIC"))
            i += 1
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def _synthetic_landmarks(service_key: str) -> pd.DataFrame:
    lm = _LANDMARKS.get(service_key)
    if lm is None:
        return _synthetic_distributed(service_key, _DISTRIBUTED_COUNT.get(service_key, 20))
    return pd.DataFrame(
        [(name, lon, lat, "SYNTHETIC") for name, lon, lat in lm], columns=RAW_COLUMNS
    )


# --------------------------------------------------------------------------- #
# OSM fetch
# --------------------------------------------------------------------------- #
def _osm_points(service_key: str) -> pd.DataFrame | None:
    """Fetch a service from OSM and reduce every feature to a point.

    Returns a DataFrame ``[name, lon, lat, source]`` or ``None`` on failure.
    """
    service = config.SERVICE_TYPES[service_key]
    bbox = config.DHAKA_BBOX  # (left, bottom, right, top) == (W, S, E, N)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gdf = ox.features_from_bbox(bbox, tags=service.osm_tags)
    except Exception as exc:  # network down, no results, rate limit, ...
        print(f"    [OSM] {service_key}: fetch failed ({type(exc).__name__}) -> synthetic")
        return None
    if gdf is None or len(gdf) == 0:
        return None

    # represent every geometry by an interior point (metric CRS for accuracy)
    pts = gdf.to_crs(config.CRS_METRIC).representative_point().to_crs(config.CRS_GEO)
    names = gdf["name"] if "name" in gdf.columns else pd.Series([None] * len(gdf))
    rows = []
    for k, (name, geom) in enumerate(zip(names.tolist(), pts.tolist())):
        label = name if isinstance(name, str) and name.strip() else f"{service_key} #{k + 1}"
        rows.append((label, float(geom.x), float(geom.y), "OSM"))
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def fetch_service(service_key: str, prefer_osm: bool = True, use_cache: bool = True) -> pd.DataFrame:
    """Collect one service, supplement if sparse, cache the raw result."""
    raw_path = config.RAW_DIR / f"{service_key}.csv"
    if use_cache and raw_path.exists():
        return pd.read_csv(raw_path)

    service = config.SERVICE_TYPES[service_key]
    frames: list[pd.DataFrame] = []

    osm = _osm_points(service_key) if prefer_osm else None
    if osm is not None:
        frames.append(osm)

    have = sum(len(f) for f in frames)
    if have < service.min_count:
        # supplement (or fully populate) with clearly-labelled synthetic points
        syn = _synthetic_landmarks(service_key)
        frames.append(syn)

    df = pd.concat(frames, ignore_index=True) if frames else _synthetic_landmarks(service_key)
    df = df[RAW_COLUMNS]
    df.to_csv(raw_path, index=False)
    n_osm = int((df["source"] == "OSM").sum())
    n_syn = int((df["source"] == "SYNTHETIC").sum())
    print(f"    {service_key:14s} raw={len(df):4d}  (OSM {n_osm}, SYNTHETIC {n_syn})")
    return df


def fetch_all(prefer_osm: bool = True, use_cache: bool = True) -> dict[str, pd.DataFrame]:
    print("[phase 4.1] fetching POIs (OSM primary, synthetic fallback)")
    return {
        key: fetch_service(key, prefer_osm=prefer_osm, use_cache=use_cache)
        for key in config.SERVICE_TYPES
    }


if __name__ == "__main__":
    for key, df in fetch_all().items():
        print(key, len(df))
