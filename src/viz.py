"""Phase 7 (+5B) — all plotting: static maps, heatmaps, zone flagship, folium.

Static maps place every Dhaka Voronoi over a contextily basemap so the cells
read as a real map. Basemap tiles are fetched from the web; if that fails the
figure still renders on a plain background. Everything is projected to Web
Mercator (EPSG:3857) for tile alignment.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import branca.colormap as bcm
import contextily as cx
import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from folium.plugins import HeatMap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from . import config
from .coverage import CoverageResult
from .recommend import RecommendResult
from .voronoi_dhaka import ServiceVoronoi
from .zones import ZoneRef, build_zone_voronoi, color_cells_by_zone, zone_reference

WEB = "EPSG:3857"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _add_basemap(ax, source=cx.providers.CartoDB.Positron) -> None:
    try:
        cx.add_basemap(ax, crs=WEB, source=source, attribution_size=5)
    except Exception as exc:  # offline / tile server hiccup
        print(f"    [basemap] skipped ({type(exc).__name__})")


def _boundary_web(sv: ServiceVoronoi) -> gpd.GeoSeries:
    return gpd.GeoSeries([sv.boundary], crs=config.CRS_METRIC).to_crs(WEB)


def _seeds_web(sv: ServiceVoronoi) -> gpd.GeoDataFrame:
    return sv.seeds_gdf().to_crs(WEB)


# --------------------------------------------------------------------------- #
# static: service Voronoi coloured by cell area
# --------------------------------------------------------------------------- #
def plot_service_voronoi(sv: ServiceVoronoi, cov: CoverageResult) -> str:
    svc = config.SERVICE_TYPES[sv.key]
    gdf = sv.cells_gdf().to_crs(WEB)

    fig, ax = plt.subplots(figsize=(10, 11))
    gdf.plot(
        ax=ax,
        column="area_km2",
        cmap="YlOrRd",
        alpha=0.6,
        edgecolor="#3a3a3a",
        linewidth=0.4,
        legend=True,
        legend_kwds={"label": "Voronoi cell area (km²)", "shrink": 0.5},
    )
    under = gdf[gdf["seed_index"].isin(cov.underserved_cells)]
    if len(under):
        under.boundary.plot(ax=ax, color="#b30000", linewidth=1.6)
    _seeds_web(sv).plot(ax=ax, color=svc.color, markersize=10, marker="o", zorder=5)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.3)
    _add_basemap(ax)

    ax.set_title(
        f"Dhaka {svc.label} — Voronoi coverage ({sv.n} facilities)\n"
        f"red outline = underserved cell (area > mean + 1σ)",
        fontsize=12,
    )
    ax.set_axis_off()
    out = config.FIGURES_DIR / f"voronoi_{sv.key}.png"
    fig.savefig(out, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


# --------------------------------------------------------------------------- #
# static: nearest-facility distance heatmap
# --------------------------------------------------------------------------- #
def plot_nn_heatmap(sv: ServiceVoronoi, cov: CoverageResult) -> str:
    svc = config.SERVICE_TYPES[sv.key]
    grid = gpd.GeoSeries(
        gpd.points_from_xy(cov.grid_xy[:, 0], cov.grid_xy[:, 1]), crs=config.CRS_METRIC
    ).to_crs(WEB)
    gx, gy = grid.x.to_numpy(), grid.y.to_numpy()

    fig, ax = plt.subplots(figsize=(10, 11))
    tcf = ax.tricontourf(gx, gy, cov.grid_nn_m / 1000.0, levels=14, cmap="inferno", alpha=0.72)
    cbar = fig.colorbar(tcf, ax=ax, shrink=0.5)
    cbar.set_label("distance to nearest facility (km)")

    _seeds_web(sv).plot(ax=ax, color="white", markersize=8, marker="o", edgecolor="black", linewidth=0.4, zorder=5)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.3)
    _add_basemap(ax)

    ax.set_title(
        f"Dhaka {svc.label} — nearest-facility distance heatmap\n"
        f"threshold {cov.threshold_m/1000:.1f} km · "
        f"{100*cov.frac_grid_underserved:.0f}% of area underserved",
        fontsize=12,
    )
    ax.set_axis_off()
    out = config.FIGURES_DIR / f"heatmap_{sv.key}.png"
    fig.savefig(out, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


# --------------------------------------------------------------------------- #
# static: recommendations (existing vs proposed)
# --------------------------------------------------------------------------- #
def plot_recommendations(sv: ServiceVoronoi, rec: RecommendResult) -> str:
    from .voronoi_dhaka import build_service_voronoi

    svc = config.SERVICE_TYPES[sv.key]

    # rebuild the improved Voronoi with the proposed points added
    import numpy as _np

    seeds_after = _np.vstack([sv.seeds, rec.new_points_m])
    from .voronoi_core import clip_voronoi_to_box, compute_voronoi

    vor = compute_voronoi(seeds_after)
    rect = clip_voronoi_to_box(vor, sv.bbox)
    polys = []
    for idx, poly in rect.items():
        c = poly.intersection(sv.boundary)
        if not c.is_empty and c.area > 0:
            polys.append(c)
    improved = gpd.GeoSeries(polys, crs=config.CRS_METRIC).to_crs(WEB)

    fig, ax = plt.subplots(figsize=(10, 11))
    improved.boundary.plot(ax=ax, color="#666666", linewidth=0.5)
    _seeds_web(sv).plot(ax=ax, color="#1f77b4", markersize=12, marker="o", label="existing", zorder=5)
    new_web = gpd.GeoSeries(
        gpd.points_from_xy(rec.new_points_m[:, 0], rec.new_points_m[:, 1]),
        crs=config.CRS_METRIC,
    ).to_crs(WEB)
    new_web.plot(ax=ax, color="#d62728", markersize=170, marker="*", edgecolor="black", linewidth=0.6, label="proposed", zorder=6)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.3)
    _add_basemap(ax)

    ax.legend(loc="upper right", fontsize=9)
    ax.set_title(
        f"Dhaka {svc.label} — {rec.k} proposed new sites\n"
        f"max access {rec.before.max_nn_m/1000:.2f} km → {rec.after.max_nn_m/1000:.2f} km",
        fontsize=12,
    )
    ax.set_axis_off()
    out = config.FIGURES_DIR / f"recommendations_{sv.key}.png"
    fig.savefig(out, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


# --------------------------------------------------------------------------- #
# Track C: zone-coloured Voronoi
# --------------------------------------------------------------------------- #
def _zone_legend_handles(ref: ZoneRef) -> list[Patch]:
    return [Patch(facecolor=c, edgecolor="#333", label=n, alpha=0.7)
            for n, c in zip(ref.names, ref.colors)]


def plot_zone_colored_voronoi(
    sv: ServiceVoronoi, ref: ZoneRef | None = None, flagship: bool = False
) -> str:
    ref = ref or zone_reference()
    svc = config.SERVICE_TYPES[sv.key]
    zgdf = color_cells_by_zone(sv, ref).to_crs(WEB)

    fig, ax = plt.subplots(figsize=(11, 12))
    zgdf.plot(ax=ax, color=zgdf["zone_color"].tolist(), alpha=0.55,
              edgecolor="#333333", linewidth=0.4)

    # coarse 8-zone Voronoi boundaries (dashed) so the grouping is obvious
    zv = build_zone_voronoi(sv.boundary, ref).to_crs(WEB)
    zv.boundary.plot(ax=ax, color="#111111", linewidth=1.4, linestyle=(0, (5, 3)))

    _seeds_web(sv).plot(ax=ax, color="#111111", markersize=6, marker="o", zorder=5)
    _boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.4)

    # zone name labels at centres
    centers = gpd.GeoSeries(
        gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
        crs=config.CRS_METRIC,
    ).to_crs(WEB)
    for name, pt in zip(ref.names, centers):
        ax.annotate(
            name, (pt.x, pt.y), ha="center", va="center", fontsize=11,
            fontweight="bold", color="#111111",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#333", alpha=0.75),
            zorder=7,
        )
    _add_basemap(ax)

    ax.legend(handles=_zone_legend_handles(ref), title="Dhaka zones",
              loc="upper right", fontsize=8, title_fontsize=9, framealpha=0.9)
    title = "Dhaka Voronoi coloured by named zone"
    ax.set_title(f"{title} — {svc.label} ({sv.n} cells)", fontsize=13)
    ax.set_axis_off()

    name = "zones_dhaka_flagship" if flagship else f"zones_{sv.key}"
    out = config.FIGURES_DIR / f"{name}.png"
    fig.savefig(out, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    return str(out)


# --------------------------------------------------------------------------- #
# interactive: folium per service
# --------------------------------------------------------------------------- #
def _map_center(sv: ServiceVoronoi) -> list[float]:
    c = gpd.GeoSeries([sv.boundary], crs=config.CRS_METRIC).to_crs(config.CRS_GEO).iloc[0].centroid
    return [c.y, c.x]


def folium_service_map(
    sv: ServiceVoronoi, cov: CoverageResult, rec: RecommendResult | None = None
) -> str:
    svc = config.SERVICE_TYPES[sv.key]
    m = folium.Map(location=_map_center(sv), zoom_start=12, tiles="CartoDB positron")

    cells = sv.cells_gdf().to_crs(config.CRS_GEO)
    areas = cells["area_km2"]
    cmap = bcm.linear.YlOrRd_09.scale(float(areas.min()), float(areas.max()))
    cmap.caption = "Voronoi cell area (km²)"

    fg_cells = folium.FeatureGroup(name="Voronoi cells (by area)", show=True)
    folium.GeoJson(
        cells.to_json(),
        style_function=lambda f: {
            "fillColor": cmap(f["properties"]["area_km2"]),
            "color": "#444444",
            "weight": 0.5,
            "fillOpacity": 0.55,
        },
        tooltip=folium.GeoJsonTooltip(fields=["name", "area_km2"],
                                      aliases=["facility", "cell km²"]),
    ).add_to(fg_cells)
    fg_cells.add_to(m)

    fg_fac = folium.FeatureGroup(name=f"{svc.label} facilities", show=True)
    seeds_geo = sv.seeds_gdf().to_crs(config.CRS_GEO)
    for _, row in seeds_geo.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3, color=svc.color, fill=True, fill_opacity=0.9,
            popup=str(row["name"]),
        ).add_to(fg_fac)
    fg_fac.add_to(m)

    # underserved heat (grid points beyond threshold)
    under_mask = cov.grid_nn_m > cov.threshold_m
    if under_mask.any():
        gpts = gpd.GeoSeries(
            gpd.points_from_xy(cov.grid_xy[under_mask, 0], cov.grid_xy[under_mask, 1]),
            crs=config.CRS_METRIC,
        ).to_crs(config.CRS_GEO)
        heat = [[p.y, p.x, float(w)] for p, w in zip(gpts, cov.grid_nn_m[under_mask])]
        fg_heat = folium.FeatureGroup(name="Underserved heat", show=False)
        HeatMap(heat, radius=14, blur=18).add_to(fg_heat)
        fg_heat.add_to(m)

    if rec is not None:
        fg_new = folium.FeatureGroup(name="Proposed new sites", show=True)
        for i, (lon, lat) in enumerate(rec.new_points_lonlat):
            folium.Marker(
                [lat, lon],
                icon=folium.Icon(color="red", icon="plus"),
                popup=f"Proposed {svc.label} #{i+1} ({rec.new_zones[i]})",
            ).add_to(fg_new)
        fg_new.add_to(m)

    cmap.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    out = config.REPORT_DIR / f"interactive_{sv.key}.html"
    m.save(str(out))
    return str(out)


def folium_zone_map(sv: ServiceVoronoi, ref: ZoneRef | None = None) -> str:
    ref = ref or zone_reference()
    zgdf = color_cells_by_zone(sv, ref).to_crs(config.CRS_GEO)
    m = folium.Map(location=_map_center(sv), zoom_start=12, tiles="CartoDB positron")
    folium.GeoJson(
        zgdf.to_json(),
        style_function=lambda f: {
            "fillColor": f["properties"]["zone_color"],
            "color": "#333333",
            "weight": 0.5,
            "fillOpacity": 0.6,
        },
        tooltip=folium.GeoJsonTooltip(fields=["zone_name", "area_km2"],
                                      aliases=["zone", "cell km²"]),
    ).add_to(m)
    out = config.REPORT_DIR / f"zones_{sv.key}.html"
    m.save(str(out))
    return str(out)
