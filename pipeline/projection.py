"""WGS84 geodetic to local metric Cartesian projection and geodesic distance calculation.

Implements WGS84 Ellipsoidal Equirectangular projection parameterized
with dynamic or venue-origin local curvature coefficients.
"""

import math
from typing import Tuple, List, Dict, Any, Union, Optional

from pipeline.config import (
    LAT0,
    LON0,
    K_LAT,
    K_LON,
    EARTH_RADIUS_LOCAL_M,
    MARKS,
)

WGS84_A_M = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


def wgs84_curvature_coefficients(lat0_deg: float) -> Tuple[float, float]:
    """Compute local WGS84 curvature coefficients (k_lat, k_lon) in m/deg at lat0_deg."""
    phi = math.radians(lat0_deg)
    sin_phi = math.sin(phi)
    denom = 1.0 - WGS84_E2 * sin_phi * sin_phi
    m_radius = WGS84_A_M * (1.0 - WGS84_E2) / (denom * math.sqrt(denom))
    n_radius = WGS84_A_M / math.sqrt(denom)
    k_lat = math.radians(1.0) * m_radius
    k_lon = math.radians(1.0) * n_radius * math.cos(phi)
    return k_lat, k_lon


def _resolve_curvature(
    lat0: float,
    k_lat: Optional[float],
    k_lon: Optional[float],
) -> Tuple[float, float]:
    if k_lat is not None and k_lon is not None:
        return k_lat, k_lon
    if abs(lat0 - LAT0) < 1e-9:
        return (K_LAT if k_lat is None else k_lat), (K_LON if k_lon is None else k_lon)
    dyn_lat, dyn_lon = wgs84_curvature_coefficients(lat0)
    return (dyn_lat if k_lat is None else k_lat), (dyn_lon if k_lon is None else k_lon)


def wgs84_to_metric(
    lat: float,
    lon: float,
    lat0: float = LAT0,
    lon0: float = LON0,
    k_lat: Optional[float] = None,
    k_lon: Optional[float] = None,
) -> Tuple[float, float]:
    """Projects WGS84 coordinates (lat, lon) in degrees to local metric (x, y) in metres.

    Convention:
      x: Easting in metres relative to (lat0, lon0)
      y: Northing in metres relative to (lat0, lon0)
    """
    eff_k_lat, eff_k_lon = _resolve_curvature(lat0, k_lat, k_lon)
    x = (lon - lon0) * eff_k_lon
    y = (lat - lat0) * eff_k_lat
    return (x, y)


def metric_to_wgs84(
    x: float,
    y: float,
    lat0: float = LAT0,
    lon0: float = LON0,
    k_lat: Optional[float] = None,
    k_lon: Optional[float] = None,
) -> Tuple[float, float]:
    """Inverts local metric coordinates (x, y) in metres to WGS84 (lat, lon) in degrees."""
    eff_k_lat, eff_k_lon = _resolve_curvature(lat0, k_lat, k_lon)
    lon = lon0 + (x / eff_k_lon)
    lat = lat0 + (y / eff_k_lat)
    return (lat, lon)


def project_polygon_coords(
    points: List[Union[Dict[str, float], Tuple[float, float]]],
    lat0: float = LAT0,
    lon0: float = LON0,
    k_lat: Optional[float] = None,
    k_lon: Optional[float] = None,
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
        projected.append(wgs84_to_metric(lat, lon, lat0=lat0, lon0=lon0, k_lat=k_lat, k_lon=k_lon))
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
    lat0: float = LAT0,
    lon0: float = LON0,
    k_lat: Optional[float] = None,
    k_lon: Optional[float] = None,
) -> Dict[str, Any]:
    """Verifies that Euclidean metric distances between gate marks match Haversine distances.

    Offsets the baseline RM8/RM6 (bottom) and RM4/RM2 (top) gate geometries around
    the target venue origin ``(lat0, lon0)`` and curvature coefficients ``(k_lat, k_lon)``.
    """
    rm8 = MARKS["RM8"]
    rm6 = MARKS["RM6"]
    rm4 = MARKS["RM4"]
    rm2 = MARKS["RM2"]

    def _offset_mark(mark: Any) -> Tuple[float, float]:
        return (
            lat0 + (mark.target_lat - LAT0),
            lon0 + (mark.target_lon - LON0),
        )

    b1_lat, b1_lon = _offset_mark(rm8)
    b2_lat, b2_lon = _offset_mark(rm6)
    t1_lat, t1_lon = _offset_mark(rm4)
    t2_lat, t2_lon = _offset_mark(rm2)

    # 1. Bottom Gate (RM8 -> RM6)
    x8, y8 = wgs84_to_metric(b1_lat, b1_lon, lat0=lat0, lon0=lon0, k_lat=k_lat, k_lon=k_lon)
    x6, y6 = wgs84_to_metric(b2_lat, b2_lon, lat0=lat0, lon0=lon0, k_lat=k_lat, k_lon=k_lon)
    d_cart_bottom = euclidean_distance(x8, y8, x6, y6)
    d_hav_bottom = haversine_distance(b1_lat, b1_lon, b2_lat, b2_lon, radius=radius)
    err_bottom_pct = abs(d_cart_bottom - d_hav_bottom) / d_hav_bottom * 100.0

    # 2. Top Gate (RM4 -> RM2)
    x4, y4 = wgs84_to_metric(t1_lat, t1_lon, lat0=lat0, lon0=lon0, k_lat=k_lat, k_lon=k_lon)
    x2, y2 = wgs84_to_metric(t2_lat, t2_lon, lat0=lat0, lon0=lon0, k_lat=k_lat, k_lon=k_lon)
    d_cart_top = euclidean_distance(x4, y4, x2, y2)
    d_hav_top = haversine_distance(t1_lat, t1_lon, t2_lat, t2_lon, radius=radius)
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
