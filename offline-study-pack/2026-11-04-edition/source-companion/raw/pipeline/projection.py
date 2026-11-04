"""WGS84 geodetic to local metric Cartesian projection and geodesic distance calculation.

Implements WGS84 Ellipsoidal Equirectangular projection parameterized
with local curvature coefficients at the Gulf of Naples racecourse center.
"""

import math
from typing import Tuple, List, Dict, Any, Union

from pipeline.config import (
    LAT0,
    LON0,
    K_LAT,
    K_LON,
    EARTH_RADIUS_LOCAL_M,
    MARKS,
)


def wgs84_to_metric(
    lat: float,
    lon: float,
    lat0: float = LAT0,
    lon0: float = LON0,
    k_lat: float = K_LAT,
    k_lon: float = K_LON,
) -> Tuple[float, float]:
    """Projects WGS84 coordinates (lat, lon) in degrees to local metric (x, y) in metres.

    Convention:
      x: Easting in metres relative to (lat0, lon0)
      y: Northing in metres relative to (lat0, lon0)
    """
    x = (lon - lon0) * k_lon
    y = (lat - lat0) * k_lat
    return (x, y)


def metric_to_wgs84(
    x: float,
    y: float,
    lat0: float = LAT0,
    lon0: float = LON0,
    k_lat: float = K_LAT,
    k_lon: float = K_LON,
) -> Tuple[float, float]:
    """Inverts local metric coordinates (x, y) in metres to WGS84 (lat, lon) in degrees."""
    lon = lon0 + (x / k_lon)
    lat = lat0 + (y / k_lat)
    return (lat, lon)


def project_polygon_coords(
    points: List[Union[Dict[str, float], Tuple[float, float]]]
) -> List[Tuple[float, float]]:
    """Projects a list of boundary coordinate points to local metric (x, y).

    Accepts points as:
      - dict with 'x' (lon) and 'y' (lat) [America's Cup session polygon convention]
      - dict with 'latitude' and 'longitude'
      - tuple of (lat, lon)
    """
    projected: List[Tuple[float, float]] = []
    for pt in points:
        if isinstance(pt, dict):
            if "latitude" in pt and "longitude" in pt:
                lat = float(pt["latitude"])
                lon = float(pt["longitude"])
            elif "x" in pt and "y" in pt:
                # In session polygons, x = longitude, y = latitude
                lon = float(pt["x"])
                lat = float(pt["y"])
            else:
                raise ValueError(f"Unrecognized coordinate dict keys: {pt.keys()}")
        elif isinstance(pt, (tuple, list)):
            lat = float(pt[0])
            lon = float(pt[1])
        else:
            raise TypeError(f"Unsupported point type: {type(pt)}")
        projected.append(wgs84_to_metric(lat, lon))
    return projected


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    radius: float = EARTH_RADIUS_LOCAL_M,
) -> float:
    """Computes great-circle distance between two points on a spherical Earth in metres."""
    if any(math.isnan(value) for value in (lat1, lon1, lat2, lon2, radius)):
        return math.nan
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    sin_half_dphi = math.sin(dphi / 2.0)
    sin_half_dlam = math.sin(dlam / 2.0)

    a = (sin_half_dphi * sin_half_dphi) + (
        math.cos(phi1) * math.cos(phi2) * sin_half_dlam * sin_half_dlam
    )
    # Clamp 'a' to [0.0, 1.0] to prevent floating point domain errors
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius * c


def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Computes 2D Euclidean distance in metric Cartesian space."""
    return math.hypot(x2 - x1, y2 - y1)


def verify_gate_marks_projection_accuracy(
    tolerance_pct: float = 0.1,
    radius: float = EARTH_RADIUS_LOCAL_M,
) -> Dict[str, Any]:
    """Verifies that Euclidean metric distances between gate marks match Haversine distances.

    Checks:
      1. Bottom gate: RM8 to RM6
      2. Top gate: RM4 to RM2

    Returns detailed error breakdown and boolean pass/fail status.
    """
    rm8 = MARKS["RM8"]
    rm6 = MARKS["RM6"]
    rm4 = MARKS["RM4"]
    rm2 = MARKS["RM2"]

    # 1. Bottom Gate (RM8 -> RM6)
    x8, y8 = wgs84_to_metric(rm8.target_lat, rm8.target_lon)
    x6, y6 = wgs84_to_metric(rm6.target_lat, rm6.target_lon)
    d_cart_bottom = euclidean_distance(x8, y8, x6, y6)
    d_hav_bottom = haversine_distance(
        rm8.target_lat, rm8.target_lon, rm6.target_lat, rm6.target_lon, radius=radius
    )
    err_bottom_pct = abs(d_cart_bottom - d_hav_bottom) / d_hav_bottom * 100.0

    # 2. Top Gate (RM4 -> RM2)
    x4, y4 = wgs84_to_metric(rm4.target_lat, rm4.target_lon)
    x2, y2 = wgs84_to_metric(rm2.target_lat, rm2.target_lon)
    d_cart_top = euclidean_distance(x4, y4, x2, y2)
    d_hav_top = haversine_distance(
        rm4.target_lat, rm4.target_lon, rm2.target_lat, rm2.target_lon, radius=radius
    )
    err_top_pct = abs(d_cart_top - d_hav_top) / d_hav_top * 100.0

    passed_bottom = err_bottom_pct <= tolerance_pct
    passed_top = err_top_pct <= tolerance_pct

    return {
        "all_passed": passed_bottom and passed_top,
        "tolerance_pct": tolerance_pct,
        "bottom_gate": {
            "from_mark": "RM8",
            "to_mark": "RM6",
            "cartesian_distance_m": d_cart_bottom,
            "haversine_distance_m": d_hav_bottom,
            "abs_error_m": abs(d_cart_bottom - d_hav_bottom),
            "error_pct": err_bottom_pct,
            "passed": passed_bottom,
        },
        "top_gate": {
            "from_mark": "RM4",
            "to_mark": "RM2",
            "cartesian_distance_m": d_cart_top,
            "haversine_distance_m": d_hav_top,
            "abs_error_m": abs(d_cart_top - d_hav_top),
            "error_pct": err_top_pct,
            "passed": passed_top,
        },
    }
