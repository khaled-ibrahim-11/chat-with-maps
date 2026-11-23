import argparse
from math import isfinite
from pathlib import Path
from typing import Optional

import geopandas as gpd
from pyproj import Geod

from .config import DATA_PATH

WGS84 = Geod(ellps="WGS84")


def load_places(data_path: Path = DATA_PATH) -> gpd.GeoDataFrame:
    """Load the fields used by the map and GIS queries."""
    places = gpd.read_file(data_path)
    return places[["POI_Name_English", "Category", "Locality", "geometry"]].copy()


def filter_places(
    places: gpd.GeoDataFrame, category: Optional[str] = None, locality: Optional[str] = None
) -> gpd.GeoDataFrame:
    """Apply whichever filters are supplied, or return all places."""
    matches = places
    if category is not None:
        matches = matches.loc[matches["Category"] == category]
    if locality is not None:
        matches = matches.loc[matches["Locality"] == locality]
    return matches.copy()


def find_landmark(places: gpd.GeoDataFrame, landmark_name: str):
    """Find a uniquely named point and return it in longitude and latitude."""
    landmarks = places.loc[places["POI_Name_English"] == landmark_name, "geometry"]
    if len(landmarks) != 1:
        raise ValueError(f"Expected one place named {landmark_name!r}, found {len(landmarks)}.")
    return landmarks.to_crs(epsg=4326).iloc[0]


def find_places_nearby(
    places: gpd.GeoDataFrame, category: str, landmark_name: str, radius_m: float
) -> gpd.GeoDataFrame:
    """Return places in a category within radius_m of a named point."""
    if not isfinite(radius_m) or radius_m <= 0:
        raise ValueError("The radius must be a positive, finite distance in meters.")

    landmark = find_landmark(places, landmark_name)
    candidates = places.loc[places["Category"] == category].copy()
    candidate_points = candidates.geometry.to_crs(epsg=4326)
    candidates["distance_m"] = [
        WGS84.inv(landmark.x, landmark.y, point.x, point.y)[2]
        for point in candidate_points
    ]
    return candidates.loc[candidates["distance_m"] <= radius_m].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Dubai restaurant demos.")
    parser.parse_args()

    places = load_places()
    restaurants = filter_places(places, category="Restaurant", locality="Al Satwa")
    landmark_name = "Financial Center Metro Bus Stop Seaside"
    nearby_restaurants = find_places_nearby(
        places, category="Restaurant", landmark_name=landmark_name, radius_m=500
    )

    print(f"Loaded {len(places):,} places in {places.crs}.")
    print(f"Found {len(restaurants):,} restaurants in Al Satwa.")
    print(f"Found {len(nearby_restaurants):,} restaurants within 500 m of {landmark_name}.")


if __name__ == "__main__":
    main()
