

def create_marker(feature):
    geometry = feature["geometry"]
    if geometry["type"] != "Point":
        return
    lon, lat = geometry["coordinates"]
