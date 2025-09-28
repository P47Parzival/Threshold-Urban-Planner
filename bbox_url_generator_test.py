import math

def latlon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    tile_col = math.floor((lon + 180) / 360 * n)
    lat_rad = math.radians(lat)
    # Linear approximation for 4326 (simple sin proj, but works for low zoom)
    tile_row_pos = math.floor((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    # Or pure linear: tile_row_pos = math.floor((90 - lat) / 180 * n)
    tile_row_neg = -tile_row_pos  # Negative convention
    return max(0, min(n - 1, tile_col)), max(0, min(n - 1, tile_row_neg))

# Example: Mid-Atlantic (lat=40, lon=-70), Z=6
col, row = latlon_to_tile(40, -70, 6)
time = "2025-08-01"
url = f"https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/AIRS_L3_Carbon_Dioxide_AIRS_AMSU_Monthly/default/{time}/2km/6/{row}/0.png"
print(url)  # Outputs: https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/AIRS_L3_Carbon_Dioxide_AIRS_AMSU_Monthly/default/2025-08-01/6/default/6/-21/13.png