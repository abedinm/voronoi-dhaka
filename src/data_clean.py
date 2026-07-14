"""Track B, phase 4.2 — clean raw POIs into tidy processed tables.

Steps per service:
  1. reproject lon/lat (EPSG:4326) into the metric CRS (UTM 46N);
  2. drop near-duplicate points closer than ``MIN_SEED_DISTANCE``;
  3. clip to the real Dhaka admin boundary (fetched from OSM, else the bbox);
  4. write ``data/processed/<service>.csv`` with
     ``name, lon, lat, x_m, y_m, source``.
"""

from __future__ import annotations

import warnings

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import box

from . import config, data_fetch

PROCESSED_COLUMNS = ["name", "lon", "lat", "x_m", "y_m", "source"]
_BOUNDARY_PATH = config.RAW_DIR / "dhaka_boundary.geojson"


# --------------------------------------------------------------------------- #
# Dhaka boundary
# --------------------------------------------------------------------------- #
def get_dhaka_boundary() -> gpd.GeoDataFrame:
    """Return the Dhaka boundary polygon (geographic CRS), cached to disk.

    Uses the OSM administrative polygon intersected with ``DHAKA_BBOX`` so the
    study area never exceeds the analysis window. Falls back to the plain bbox
    rectangle if the geocode lookup is unavailable.
    """
    if _BOUNDARY_PATH.exists():
        return gpd.read_file(_BOUNDARY_PATH)

    bbox_poly = box(*config.DHAKA_BBOX)
    geom = bbox_poly
    source = "bbox"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            admin = ox.geocode_to_gdf(config.DHAKA_ADMIN_QUERY)
        admin = admin.to_crs(config.CRS_GEO)
        clipped = admin.geometry.iloc[0].intersection(bbox_poly)
        if not clipped.is_empty and clipped.area > 0.5 * bbox_poly.area:
            geom, source = clipped, "OSM admin ∩ bbox"
        else:
            # admin polygon much smaller than bbox -> keep bbox for coverage
            geom, source = bbox_poly, "bbox (OSM admin too small)"
    except Exception as exc:
        print(f"    [boundary] OSM geocode failed ({type(exc).__name__}); using bbox")

    gdf = gpd.GeoDataFrame(
        {"name": ["Dhaka study area"], "source": [source]},
        geometry=[geom],
        crs=config.CRS_GEO,
    )
    gdf.to_file(_BOUNDARY_PATH, driver="GeoJSON")
    return gdf


def boundary_metric():
    """Dhaka boundary polygon reprojected to the metric CRS."""
    return get_dhaka_boundary().to_crs(config.CRS_METRIC).geometry.iloc[0]


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def _to_metric(df: pd.DataFrame) -> pd.DataFrame:
    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs=config.CRS_GEO,
    ).to_crs(config.CRS_METRIC)
    df = df.copy()
    df["x_m"] = gdf.geometry.x.to_numpy()
    df["y_m"] = gdf.geometry.y.to_numpy()
    return df


def _drop_near_duplicates(df: pd.DataFrame, min_dist: float) -> pd.DataFrame:
    """Greedy dedup: keep a point only if it is >= ``min_dist`` from all kept."""
    coords = df[["x_m", "y_m"]].to_numpy()
    kept: list[int] = []
    for i in range(len(coords)):
        if all(np.hypot(*(coords[i] - coords[j])) >= min_dist for j in kept):
            kept.append(i)
    return df.iloc[kept].reset_index(drop=True)


def clean_service(service_key: str, raw: pd.DataFrame | None = None) -> pd.DataFrame:
    if raw is None:
        raw = data_fetch.fetch_service(service_key)
    df = _to_metric(raw)
    df = _drop_near_duplicates(df, config.MIN_SEED_DISTANCE)

    # clip to the real boundary (metric)
    poly = boundary_metric()
    inside = gpd.GeoSeries(
        gpd.points_from_xy(df["x_m"], df["y_m"]), crs=config.CRS_METRIC
    ).within(poly.buffer(1.0))
    df = df[inside.to_numpy()].reset_index(drop=True)

    df = df[PROCESSED_COLUMNS]
    out = config.PROCESSED_DIR / f"{service_key}.csv"
    df.to_csv(out, index=False)
    print(f"    {service_key:14s} clean={len(df):4d}  -> {out.name}")
    return df


def clean_all(raw: dict[str, pd.DataFrame] | None = None) -> dict[str, pd.DataFrame]:
    print("[phase 4.2] cleaning (reproject, dedup, boundary clip)")
    get_dhaka_boundary()  # ensure boundary is cached before the loop
    out: dict[str, pd.DataFrame] = {}
    for key in config.SERVICE_TYPES:
        raw_df = raw.get(key) if raw else None
        out[key] = clean_service(key, raw_df)
    return out


if __name__ == "__main__":
    clean_all()
