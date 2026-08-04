#!/usr/bin/env python3
"""Plain-language copies of the figures, for the talk and the poster only.

The thesis keeps the technical captions — a thesis that talks like a poster
reads as thin. The defense deck and the poster point at outputs/figures/plain/
instead, which holds a retitled copy of every figure they use.

Only wording changes. Every plot draws the same data from the same functions.

Run:  python build_plain_figures.py
"""

import shutil
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import voronoi_dhaka as V

warnings.simplefilter("ignore")
PLAIN = V.FIGURES_DIR / "plain"
PLAIN.mkdir(exist_ok=True)
WEB = V.WEB


def _save(fig, name):
    out = PLAIN / name
    fig.savefig(out, dpi=V.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}")
    return out


# ───────────────────────────────────────────────── 1. the six Voronoi diagrams
def voronoi_all_services(voronois):
    fig, axes = plt.subplots(2, 3, figsize=(16.5, 13))
    order = [k for k in V.SERVICE_TYPES if k in voronois]
    for ax, key in zip(axes.ravel(), order):
        sv, svc = voronois[key], V.SERVICE_TYPES[key]
        cw = V._cells_web(sv)
        cw.plot(ax=ax, color=svc.color, alpha=0.18, edgecolor="none")
        cw.boundary.plot(ax=ax, color=svc.color, linewidth=0.6, alpha=0.95)
        V._boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.1)
        V._draw_generators(ax, sv, svc, size=26, zorder=5)
        V._add_basemap(ax)
        ax.set_title(f"{svc.label} — {sv.n} locations",     # was "generator points"
                     fontsize=12.5, fontweight="bold", color=svc.color)
        ax.set_axis_off()
    for ax in axes.ravel()[len(order):]:
        ax.set_axis_off()
    # was "one colour and marker per utility, generator points shown"
    fig.suptitle("Which part of Dhaka is nearest to each kind of facility",
                 fontsize=16, fontweight="bold", y=0.975)
    fig.legend(handles=[Line2D([], [], marker=V.SERVICE_MARKER.get(k, "o"), color="none",
                               markerfacecolor=V.SERVICE_TYPES[k].color,
                               markeredgecolor="white", markersize=11,
                               label=V.SERVICE_TYPES[k].label) for k in order],
               loc="lower center", ncol=len(order), fontsize=11, frameon=False,
               bbox_to_anchor=(0.5, 0.005))
    fig.tight_layout(rect=(0, 0.035, 1, 0.955))
    return _save(fig, "voronoi_all_services.png")


# ───────────────────────────────────────────── 2. facility vs centre of its area
def cell_centroids(voronois):
    fig, axes = plt.subplots(2, 3, figsize=(16.5, 13))
    order = [k for k in V.SERVICE_TYPES if k in voronois]
    for ax, key in zip(axes.ravel(), order):
        sv, svc = voronois[key], V.SERVICE_TYPES[key]
        df = V.cell_centroid_offsets(sv)
        cw = V._cells_web(sv)
        cw.plot(ax=ax, color=svc.color, alpha=0.12, edgecolor="none")
        cw.boundary.plot(ax=ax, color=svc.color, linewidth=0.5, alpha=0.9)
        gen = gpd.GeoSeries(gpd.points_from_xy(df["gx"], df["gy"]),
                            crs=V.CRS_METRIC).to_crs(WEB)
        cen = gpd.GeoSeries(gpd.points_from_xy(df["cx"], df["cy"]),
                            crs=V.CRS_METRIC).to_crs(WEB)
        for a, b in zip(gen, cen):
            ax.plot([a.x, b.x], [a.y, b.y], color="#333333", linewidth=0.7,
                    alpha=0.8, zorder=4)
        gen.plot(ax=ax, color=svc.color, markersize=24, marker="o",
                 edgecolor="white", linewidth=0.5, zorder=6)
        cen.plot(ax=ax, color="none", markersize=26, marker="o",
                 edgecolor="#111111", linewidth=1.0, zorder=5)
        V._boundary_web(sv).boundary.plot(ax=ax, color="black", linewidth=1.0)
        V._add_basemap(ax)
        ax.set_title(f"{svc.label} — typically "        # was "median offset"
                     f"{df['offset_m'].median()/1000:.2f} km off-centre",
                     fontsize=12.5, fontweight="bold", color=svc.color)
        ax.set_axis_off()
    for ax in axes.ravel()[len(order):]:
        ax.set_axis_off()
    fig.suptitle("Is each facility in the middle of the area it covers?",
                 fontsize=16, fontweight="bold", y=0.975)
    fig.legend(handles=[
        Line2D([], [], marker="o", color="none", markerfacecolor="#555555",
               markeredgecolor="white", markersize=9, label="where the facility is"),
        Line2D([], [], marker="o", color="none", markerfacecolor="none",
               markeredgecolor="#111111", markersize=9,
               label="middle of the area it covers"),
        Line2D([], [], color="#333333", linewidth=1.2,
               label="how far off-centre it sits")],
        loc="lower center", ncol=3, fontsize=12, frameon=False,
        bbox_to_anchor=(0.5, 0.005))
    fig.tight_layout(rect=(0, 0.035, 1, 0.955))
    return _save(fig, "cell_centroids.png")


# ─────────────────────────────────────────────────────── 3. groups of facilities
def cluster_centres(voronois, ref):
    boundary = next(iter(voronois.values())).boundary
    fig, ax = plt.subplots(figsize=(11, 12))
    zv = V.build_zone_voronoi(boundary, ref).to_crs(WEB)
    zv.plot(ax=ax, color=zv["zone_color"].tolist(), alpha=0.16,
            edgecolor="#333333", linewidth=1.3)
    import pandas as pd
    frames = []
    for key in V.SERVICE_TYPES:
        if key not in voronois:
            continue
        svc = V.SERVICE_TYPES[key]
        cc = V.cluster_centres(voronois[key], ref)
        frames.append(cc)
        g = gpd.GeoSeries(gpd.points_from_xy(cc["x"], cc["y"]),
                          crs=V.CRS_METRIC).to_crs(WEB)
        g.plot(ax=ax, color=svc.color, markersize=28 + 9 * cc["n"].to_numpy(),
               marker=V.SERVICE_MARKER.get(key, "o"), edgecolor="white",
               linewidth=1.0, alpha=0.92, zorder=5)
    gpd.GeoSeries([boundary], crs=V.CRS_METRIC).to_crs(WEB).boundary.plot(
        ax=ax, color="black", linewidth=1.4)
    centers = gpd.GeoSeries(
        gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
        crs=V.CRS_METRIC).to_crs(WEB)
    for name, pt in zip(ref.names, centers):
        ax.annotate(name, (pt.x, pt.y), ha="center", va="center", fontsize=10,
                    fontweight="bold", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#333",
                              alpha=0.85))
    allc = pd.concat(frames, ignore_index=True)
    ax.legend(handles=[Line2D([], [], marker=V.SERVICE_MARKER.get(k, "o"),
                              color="none", markerfacecolor=V.SERVICE_TYPES[k].color,
                              markeredgecolor="white", markersize=9,
                              label=f"{V.SERVICE_TYPES[k].label} "
                                    f"({int((allc['service'] == k).sum())} groups)")
                       for k in V.SERVICE_TYPES if k in voronois],
              loc="upper right", fontsize=9, framealpha=0.93,
              title="Groups of facilities", title_fontsize=10)
    V._add_basemap(ax)
    # was "Centre point of every facility cluster, by section ... marker size grows
    #      with cluster size"
    ax.set_title(f"Where each service is concentrated, area by area\n"
                 f"facilities close together are counted as one group "
                 f"({len(allc)} groups from "
                 f"{sum(v.n for v in voronois.values())} facilities); "
                 "bigger marker = more facilities", fontsize=12.5)
    ax.set_axis_off()
    return _save(fig, "cluster_centres.png")


# ─────────────────────────────────────────────────────────── 4. the eight areas
def sections_only(boundary, ref):
    zv = V.build_zone_voronoi(boundary, ref).to_crs(WEB)
    fig, ax = plt.subplots(figsize=(11, 12))
    zv.plot(ax=ax, color=zv["zone_color"].tolist(), alpha=0.50,
            edgecolor="#222222", linewidth=1.6)
    gpd.GeoSeries([boundary], crs=V.CRS_METRIC).to_crs(WEB).boundary.plot(
        ax=ax, color="black", linewidth=1.6)
    centers = gpd.GeoSeries(
        gpd.points_from_xy(ref.centers_m[:, 0], ref.centers_m[:, 1]),
        crs=V.CRS_METRIC).to_crs(WEB)
    centers.plot(ax=ax, color="#111111", markersize=42, marker="o",
                 edgecolor="white", linewidth=1.4, zorder=6)
    for name, pt in zip(ref.names, centers):
        ax.annotate(name, (pt.x, pt.y), xytext=(0, 13), textcoords="offset points",
                    ha="center", va="bottom", fontsize=12, fontweight="bold",
                    zorder=7, bbox=dict(boxstyle="round,pad=0.25", fc="white",
                                        ec="#333", alpha=0.85))
    V._add_basemap(ax)
    ax.legend(handles=[Line2D([], [], marker="o", color="none",
                              markerfacecolor="#111111", markeredgecolor="white",
                              markersize=9, label="centre of the area")],
              loc="upper right", fontsize=9, framealpha=0.92)
    # was "a coarse Voronoi of eight well-known area centres, independent of any utility"
    ax.set_title("The eight areas of Dhaka we studied\n"
                 "each area is everywhere closest to one well-known centre",
                 fontsize=13)
    ax.set_axis_off()
    return _save(fig, "sections_only.png")


# ────────────────────────────────────────────────── 5. the worked-by-hand check
def textbook_all():
    fig, axes = plt.subplots(2, 2, figsize=(13, 12))
    for ax, key in zip(axes.flat, ["PB", "MR", "PHIRUZ"]):
        sk = V.SKETCHES[key]
        V.draw_textbook(ax, sk)
        # was "<name> — corrected Voronoi (n seeds, all vertices degree 3)"
        ax.set_title(f"{sk.name} — worked by hand, {len(sk.seeds)} facilities",
                     fontsize=11)
    ax = axes.flat[3]
    ax.axis("off")
    ax.text(0.02, 0.98, "What we checked", fontsize=14, fontweight="bold", va="top")
    ax.text(0.02, 0.86,
            "In every diagram:\n\n"
            "  •  each border sits exactly halfway\n     between two facilities\n\n"
            "  •  each border meets the line joining\n     them at a right angle\n\n"
            "  •  exactly three areas meet at\n     each corner (marked in red)\n\n"
            "  •  the areas fill the space with\n     no gaps and no overlaps\n\n"
            "The blue mark shows the halfway point and\n"
            "the right angle for one pair of facilities.",
            fontsize=11, va="top")
    fig.tight_layout()
    return _save(fig, "textbook_all.png")


# ─────────────────────────────────────────────────────────────────────── driver
# figures whose wording is already plain — copied across unchanged
COPY_AS_IS = ["all_facilities.png", "section_benefit.png",
              "recommendations_all_services.png", "network_vs_euclid.png",
              "gantt.png"]

if __name__ == "__main__":
    ref = V.zone_reference()
    b = V.boundary_metric()
    vs = {k: V.build_service_voronoi(k, b) for k in V.SERVICE_TYPES}
    print("plain figures ->", PLAIN)
    voronoi_all_services(vs)
    cell_centroids(vs)
    cluster_centres(vs, ref)
    sections_only(b, ref)
    textbook_all()
    for n in COPY_AS_IS:
        src = V.FIGURES_DIR / n
        if src.exists():
            shutil.copy2(src, PLAIN / n)
            print(f"  {n}  (copied unchanged)")
    print("done")
