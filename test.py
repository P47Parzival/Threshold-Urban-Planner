import gzip
import shutil
import geopandas as gpd
from shapely.geometry import box
from pyproj import Transformer
import os

# Step 1. Decompress the .gpkg.gz (only once)
gz_file = "kontur_population_20231101.gpkg.gz"
gpkg_file = "kontur_population_20231101.gpkg"

if not os.path.exists(gpkg_file):
    print("Decompressing .gpkg.gz ...")
    with gzip.open(gz_file, "rb") as f_in:
        with open(gpkg_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

# Step 2. Define your bounding box in lon/lat (India)
# Bounding box covering all of India
minx, miny, maxx, maxy = (72.168284875, 23.032082167797736, 73.047191125, 23.40502149464026)  # lon/lat - Custom area

# Step 3. Reproject bbox to EPSG:3857
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
minx_m, miny_m = transformer.transform(minx, miny)
maxx_m, maxy_m = transformer.transform(maxx, maxy)
bbox = box(minx_m, miny_m, maxx_m, maxy_m)

# Step 4. Read features within India's bounding box
print("Loading data for custom area...")
gdf = gpd.read_file(gpkg_file, bbox=bbox)
print(f"Extracted {len(gdf)} features")

# Step 5. Save to GeoJSON (will be in lon/lat again)
output_geojson = "population_custom.geojson"
gdf = gdf.to_crs(epsg=4326)  # reproject back for frontend
gdf.to_file(output_geojson, driver="GeoJSON")

print(f"Saved {output_geojson}")
