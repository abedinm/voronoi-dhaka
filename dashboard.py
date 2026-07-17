"""Interactive web dashboard for the Dhaka Voronoi analysis.

Run after generating the outputs (``python voronoi_dhaka.py``):

    streamlit run dashboard.py

It reads the already-generated figures, interactive maps and metrics table, so
it is fast and needs no recomputation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "outputs" / "figures"
REP = ROOT / "outputs" / "report"

SERVICES = {
    "metro_station": "🚇 Metro station",
    "hospital": "🏥 Hospital",
    "water_pump": "🚰 Water pump",
    "fuel": "⛽ Fuel station",
    "bus_stop": "🚌 Bus stop",
    "fire_station": "🚒 Fire station",
}

st.set_page_config(page_title="Dhaka Voronoi Utilities", layout="wide", page_icon="🗺️")
st.title("Providing Utility Services using Voronoi Diagrams")
st.caption("Some analyses, recommendations, and a case study for Dhaka City — Minhazul Abedin")


def show_image(path: Path, **kw):
    if path.exists():
        st.image(str(path), use_container_width=True, **kw)
    else:
        st.info(f"Run `python voronoi_dhaka.py` first — missing {path.name}")


overview, per_service, interactive = st.tabs(["Overview", "Per service", "Interactive map"])

with overview:
    metrics = REP / "coverage_metrics.csv"
    if metrics.exists():
        df = pd.read_csv(metrics)
        c = st.columns(4)
        c[0].metric("Services", len(df))
        c[1].metric("Facilities", int(df["n_facilities"].sum()))
        c[2].metric("Most underserved",
                    df.loc[df["pct_grid_underserved"].idxmax(), "label"])
        c[3].metric("Study area (km²)", int(df["total_area_km2"].iloc[0]))
        st.dataframe(df, use_container_width=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Eight coloured sections")
        show_image(FIG / "zones_dhaka_flagship.png")
    with right:
        st.subheader("Benefit by section (population-weighted)")
        show_image(FIG / "section_benefit.png")

with per_service:
    key = st.selectbox("Choose a utility", list(SERVICES), format_func=SERVICES.get)
    a, b = st.columns(2)
    with a:
        st.subheader("Voronoi coverage")
        show_image(FIG / f"voronoi_{key}.png")
    with b:
        st.subheader("Proposed new sites")
        show_image(FIG / f"recommendations_{key}.png")

with interactive:
    opts = {"dhaka_map": "🗺️ All utilities + sections", **SERVICES}
    key = st.selectbox("Choose a map", list(opts), format_func=opts.get)
    html_path = REP / f"interactive_{key}.html"
    if html_path.exists():
        components.html(html_path.read_text(encoding="utf-8"), height=720, scrolling=True)
    else:
        st.info(f"Run `python voronoi_dhaka.py` first — missing {html_path.name}")
