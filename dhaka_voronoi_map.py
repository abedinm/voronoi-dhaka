import folium
import numpy as np
import geopandas as gpd
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box, MultiPoint, Point
from shapely.ops import voronoi_diagram

dhaka_center = [23.8103, 90.4125]
min_lat, max_lat = 23.68, 23.90
min_lon, max_lon = 90.32, 90.50

dhaka_bbox = box(min_lon, min_lat, max_lon, max_lat)

np.random.seed(42)
police_lats = np.random.uniform(min_lat, max_lat, 20)
police_lons = np.random.uniform(min_lon, max_lon, 20)

points_list = [Point(lon, lat) for lon, lat in zip(police_lons, police_lats)]
multi_point = MultiPoint(points_list)

voronoi_geoms = voronoi_diagram(multi_point, envelope=dhaka_bbox)

m = folium.Map(location=dhaka_center, zoom_start=12, tiles='OpenStreetMap')

for poly in voronoi_geoms.geoms:
    clipped_poly = poly.intersection(dhaka_bbox)

    if not clipped_poly.is_empty:
        coords = [[pt[1], pt[0]] for pt in clipped_poly.exterior.coords]

        folium.Polygon(
            locations=coords,
            color='#1f77b4',
            weight=2,
            fill=True,
            fill_color='#aec7e8',
            fill_opacity=0.35,
            tooltip="Voronoi Coverage Zone"
        ).add_to(m)

for lat, lon in zip(police_lats, police_lons):
    folium.Marker(
        location=[lat, lon],
        popup="Police Station Location",
        icon=folium.Icon(color="red", icon="shield", prefix="fa")
    ).add_to(m)

m.save("dhaka_voronoi_map.html")
