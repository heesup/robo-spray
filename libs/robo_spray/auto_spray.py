import json
from scipy.spatial import KDTree
from shapely.geometry import Point
from geopy.distance import geodesic

def load_geojson(geojson_file):
    with open('src/assets/spray_position_all.json') as file:
        data = json.load(file)
    return data

def build_kd_tree(geojson_data):
    points = [feature['geometry']['coordinates'] for feature in geojson_data['features']]
    kdtree = KDTree(points)
    return kdtree

def match_gps_position(gps_position, kdtree, geojson_data):
    _, index = kdtree.query(gps_position, k=1)
    matched_feature = geojson_data['features'][index]
    return matched_feature

def calculate_utm_distance(lat1, lon1, lat2, lon2):
    distance = geodesic((lat1, lon1), (lat2, lon2)).meters
    return distance

if __name__ == "__main__":
    # Example usage
    geojson_file = 'src/assets/spray_position_all.json'
    gps_position = (-121.7520339, 38.5322914)  # Current GPS position

    # Load GeoJSON data
    geojson_data = load_geojson(geojson_file)

    # Build KD-Tree
    kdtree = build_kd_tree(geojson_data)

    # Match GPS position to GeoJSON feature
    matched_feature = match_gps_position(gps_position, kdtree, geojson_data)

    # Access matched feature properties
    name = matched_feature['properties']['name']
    # You can access other properties based on your GeoJSON structure

    print(f'Matched feature name: {name}')


    # Example usage
    lat1 = 37.7750  # Latitude of location 1
    lon1 = -122.4194  # Longitude of location 1
    lat2 = 37.7749  # Latitude of location 2
    lon2 = -122.4194  # Longitude of location 2

    distance = calculate_utm_distance(lat1, lon1, lat2, lon2)
    print("UTM Distance:", distance, "meters")