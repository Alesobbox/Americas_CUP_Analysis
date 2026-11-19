"""Domain models, specifications, ground truth oracles, and mathematical formulas
for E2E opaque-box testing of the AC40 America's Cup 2D Regatta Replay.
"""

from __future__ import annotations
import math
from typing import Tuple, Dict

# ==============================================================================
# AUTHORITATIVE GROUND TRUTH CONSTANTS (From ORIGINAL_REQUEST & PROJECT.md)
# ==============================================================================

# WGS84 Geodetic Reference Ellipsoid
WGS84_A = 6378137.0                # Semi-major axis (metres)
WGS84_F = 1.0 / 298.257223563      # Flattening
WGS84_E2 = 2 * WGS84_F - WGS84_F**2  # First eccentricity squared (~0.00669438)

# Local Metric Projection Parameters (Naples Course Center Midpoint)
COURSE_ORIGIN_LAT = 40.80948067    # phi_0 (degrees North)
COURSE_ORIGIN_LON = 14.23726898    # lambda_0 (degrees East)
K_LAT = 111047.746                 # Meridian curvature scaling (metres / degree lat)
K_LON = 84374.839                  # Parallel curvature scaling (metres / degree lon)

# Speed Conversion (Exact Nautical Mile Definition)
# 1 NM = 1852 m, 1 hr = 3600 s => 1 m/s = 3600 / 1852 knots
KNOT_PER_MPS = 3600.0 / 1852.0     # 1.943844492440605

# AC40 Geometry
AC40_BOW_OFFSET_M = 12.963          # Foremost bowsprit tip forward of GNSS receiver at (0, 0)
AC40_LENGTH_OVERALL_M = 11.8        # Hull LOA
AC40_BEAM_M = 4.5                   # Hull Beam

# Regatta Chronology
GUN_TIME_MS = 1790079000000        # T = 0 Gun time epoch ms (2026-09-22 10:50:00.000 UTC)
WINDOW_START_MS = 1790078820000    # T = -180.0 s (-03:00 Pre-start warning)
WINDOW_END_MS = 1790078820000 + 1948700  # 1790080768700 (~29m 28.7s)

# Nominal Course Parameters
COURSE_AXIS_NOMINAL_DEG = 39.99999999878744  # Session definition (~40.0 deg)
COURSE_AXIS_SETTLED_DEG = 44.39              # Settled mark bearing (upwind direction)
COURSE_LENGTH_NOMINAL_M = 2259.44            # Session definition

# Gate Marks Catalog
MARKS_GROUND_TRUTH = {
    "RM8": {
        "uuid": "026f70b1-9ecb-479d-b03c-085e40fd166d",
        "role": "Bottom Port / Start & Finish",
        "color": "#eeff00",
        "target_lat": 40.80297685,
        "target_lon": 14.22666341,
        "initial_lat": 40.80293791,
        "initial_lon": 14.22662080,
    },
    "RM6": {
        "uuid": "c35b7718-40e5-4a9d-a4e6-934d18ecfa2a",
        "role": "Bottom Starboard / Start & Finish",
        "color": "#ff282e",
        "target_lat": 40.80032415,
        "target_lon": 14.23089874,
        "initial_lat": 40.80029953,
        "initial_lon": 14.23084192,
    },
    "RM4": {
        "uuid": "a392c0a6-582e-41a6-905e-0e490f3a27b1",
        "role": "Top Port (Windward)",
        "color": "#ff0f15",
        "target_lat": 40.81801854,
        "target_lon": 14.24476155,
        "initial_lat": 40.81800615,
        "initial_lon": 14.24476797,
    },
    "RM2": {
        "uuid": "e018121d-b03e-4be7-9998-2a000135a599",
        "role": "Top Starboard (Windward)",
        "color": "#ff0d13",
        "target_lat": 40.81669188,
        "target_lon": 14.24687938,
        "initial_lat": 40.81667910,
        "initial_lon": 14.24684522,
    },
}

OFFICIAL_WIND_ASSET_ID = "0a18270a-3758-46e8-9a5e-3b441051674f"

# Competitors Ground Truth Catalog (9 AC40 Boats)
COMPETITORS_GROUND_TRUTH = {
    "FRA": {
        "uuid": "42e39310-fef5-4c5d-b099-a599aad5ddbb",
        "team_name": "Orient Express / La Roche-Posay",
        "color": "#ff80c0",
        "official_rank": 1,
        "finish_time_ms": 1790080059555,
        "elapsed_s": 1059.555,
        "delta_to_winner_s": 0.0,
        "status": "FINISHED",
        "start_crossing_ms": 1790079000436,
        "start_delta_s": 0.436,
        "ocs": False,
    },
    "NZL G": {
        "uuid": "80d4cda4-17f5-4bcf-b7fd-5fc0f39f3d60",
        "team_name": "Emirates Team NZ Women & Youth",
        "color": "#ff0000",
        "official_rank": 2,
        "finish_time_ms": 1790080074857,
        "elapsed_s": 1074.857,
        "delta_to_winner_s": 15.302,
        "status": "FINISHED",
        "start_crossing_ms": 1790079004289,
        "start_delta_s": 4.289,
        "ocs": False,
    },
    "ITA B": {
        "uuid": "4f5369cd-0fa3-4241-afd2-00f356898e22",
        "team_name": "Luna Rossa Prada Pirelli",
        "color": "#26e8fd",
        "official_rank": 3,
        "finish_time_ms": 1790080077932,
        "elapsed_s": 1077.932,
        "delta_to_winner_s": 18.377,
        "status": "FINISHED",
        "start_crossing_ms": 1790079000858,
        "start_delta_s": 0.858,
        "ocs": False,
    },
    "USA": {
        "uuid": "126368d2-98e9-4c3e-97ce-fb047d40ab0e",
        "team_name": "American Magic",
        "color": "#36d8e4",
        "official_rank": 4,
        "finish_time_ms": 1790080113160,
        "elapsed_s": 1113.160,
        "delta_to_winner_s": 53.605,
        "status": "FINISHED",
        "start_crossing_ms": 1790079000348,  # Reconstructed
        "start_delta_s": 0.348,
        "ocs": False,
    },
    "ITA G": {
        "uuid": "130ac4af-df5a-4568-af62-9d9395df9e9e",
        "team_name": "Luna Rossa Women and Youth",
        "color": "#ff8000",
        "official_rank": 5,
        "finish_time_ms": 1790080147935,
        "elapsed_s": 1147.935,
        "delta_to_winner_s": 88.380,
        "status": "FINISHED",
        "start_crossing_ms": 1790079003071,
        "start_delta_s": 3.071,
        "ocs": False,
    },
    "GBR G": {
        "uuid": "0890cbf9-fc5e-4187-8eee-0bf59e9f05e4",
        "team_name": "INEOS Britannia Women & Youth",
        "color": "#ffd700",
        "official_rank": 6,
        "finish_time_ms": 1790080166602,
        "elapsed_s": 1166.602,
        "delta_to_winner_s": 107.047,
        "status": "FINISHED",
        "start_crossing_ms": 1790079001148,
        "start_delta_s": 1.148,
        "ocs": False,
    },
    "NZL B": {
        "uuid": "f7a7d97a-040e-4ad5-af0f-ae6ff7b51cea",
        "team_name": "Emirates Team New Zealand",
        "color": "#00b700",
        "official_rank": 7,
        "finish_time_ms": None,
        "status": "DNF",
        "start_crossing_ms": 1790079008406,
        "start_delta_s": 8.406,
        "ocs": False,
    },
    "SUI": {
        "uuid": "ed5d37be-52fa-4902-b190-757027017085",
        "team_name": "Alinghi Red Bull Racing",
        "color": "#ffff00",
        "official_rank": 8,
        "finish_time_ms": None,
        "status": "DNF",
        "start_crossing_ms": 1790079001079,
        "start_delta_s": 1.079,
        "ocs": False,
    },
    "GBR B": {
        "uuid": "f535f0dc-a45b-4668-ae07-bd52e0cdd947",
        "team_name": "INEOS Britannia",
        "color": "#8e8eff",
        "official_rank": 9,
        "finish_time_ms": None,
        "status": "RET",
        "start_crossing_ms": None,
        "start_delta_s": None,
        "ocs": True,
        "ocs_distance_m": 610.5,
        "ocs_awarded_ms": 1790079000333,
    },
}

# ==============================================================================
# MATHEMATICAL ORACLE FUNCTIONS
# ==============================================================================

def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes exact geodesic great-circle distance between two coordinates in metres."""
    r = 6374912.4  # Ellipsoidal mean curvature radius in Gulf of Naples
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def project_wgs84_to_metric(
    lat: float, lon: float,
    lat0: float = COURSE_ORIGIN_LAT,
    lon0: float = COURSE_ORIGIN_LON,
    k_lat: float = K_LAT,
    k_lon: float = K_LON
) -> Tuple[float, float]:
    """Projects geographic coordinates (lat, lon) to local Cartesian metric (x, y) in metres."""
    x = (lon - lon0) * k_lon
    y = (lat - lat0) * k_lat
    return x, y


def inverse_metric_to_wgs84(
    x: float, y: float,
    lat0: float = COURSE_ORIGIN_LAT,
    lon0: float = COURSE_ORIGIN_LON,
    k_lat: float = K_LAT,
    k_lon: float = K_LON
) -> Tuple[float, float]:
    """Inverse projection from metric (x, y) back to geographic (lat, lon)."""
    lon = lon0 + (x / k_lon)
    lat = lat0 + (y / k_lat)
    return lat, lon


def mps_to_knots(v_mps: float) -> float:
    """Converts velocity from SI m/s to international knots."""
    return v_mps * KNOT_PER_MPS


def knots_to_mps(v_kt: float) -> float:
    """Converts velocity from international knots to SI m/s."""
    return v_kt / KNOT_PER_MPS


def normalize_angle_360(deg: float) -> float:
    """Normalizes an angle in degrees into [0.0, 360.0)."""
    res = deg % 360.0
    return res if res >= 0.0 else res + 360.0


def normalize_angle_180(deg: float) -> float:
    """Normalizes an angle in degrees into [-180.0, +180.0)."""
    return ((deg + 180.0) % 360.0) - 180.0


def circular_shortest_diff_deg(from_deg: float, to_deg: float) -> float:
    """Computes shortest signed angular difference from from_deg to to_deg in [-180, 180)."""
    diff = (to_deg - from_deg + 180.0) % 360.0 - 180.0
    return diff


def circular_slerp_deg(angle0: float, angle1: float, alpha: float) -> float:
    """Performs shortest-arc circular spherical interpolation between two angles in degrees."""
    delta = ((angle1 - angle0 + 540.0) % 360.0) - 180.0
    return (angle0 + alpha * delta + 360.0) % 360.0


def compute_bow_position(
    x_gps: float, y_gps: float, heading_deg: float, bow_offset_m: float = AC40_BOW_OFFSET_M
) -> Tuple[float, float]:
    """Computes foremost bow position given GPS antenna coordinates and compass heading."""
    hdg_rad = math.radians(heading_deg)
    # 0 deg = North (+Y), 90 deg = East (+X)
    x_bow = x_gps + bow_offset_m * math.sin(hdg_rad)
    y_bow = y_gps + bow_offset_m * math.cos(hdg_rad)
    return x_bow, y_bow


def intersect_segments_2d(
    p_prev: Tuple[float, float],
    p_curr: Tuple[float, float],
    m_port: Tuple[float, float],
    m_starboard: Tuple[float, float],
    margin_epsilon: float = 0.20
) -> Tuple[bool, float, float, float, float]:
    """Calculates 2D trajectory segment intersection against a gate line segment.

    Trajectory: B(u) = p_prev + u * (p_curr - p_prev), u in [0, 1]
    Gate:       G(s) = m_port + s * (m_starboard - m_port), s in [-margin, 1 + margin]

    Returns: (is_intersecting, u, s, x_cross, y_cross)
    """
    dx_p = p_curr[0] - p_prev[0]
    dy_p = p_curr[1] - p_prev[1]
    dx_m = m_starboard[0] - m_port[0]
    dy_m = m_starboard[1] - m_port[1]

    denom = dx_p * dy_m - dy_p * dx_m
    if abs(denom) < 1e-9:
        return False, 0.0, 0.0, 0.0, 0.0

    orig_dx = m_port[0] - p_prev[0]
    orig_dy = m_port[1] - p_prev[1]

    u = (orig_dx * dy_m - orig_dy * dx_m) / denom
    s = (orig_dx * dy_p - orig_dy * dx_p) / denom

    is_intersecting = (0.0 <= u <= 1.0) and (-margin_epsilon <= s <= 1.0 + margin_epsilon)
    x_cross = p_prev[0] + u * dx_p
    y_cross = p_prev[1] + u * dy_p

    return is_intersecting, u, s, x_cross, y_cross


def format_race_clock(elapsed_ms: int, show_fraction: bool = False) -> str:
    """Formats race-relative epoch ms offset into broadcast clock string.
    
    Negative (pre-start): -MM:SS
    Positive (elapsed):    MM:SS (or +MM:SS)
    """
    total_seconds = elapsed_ms / 1000.0
    sign = "-" if total_seconds < 0 else ""
    abs_sec = abs(total_seconds)
    minutes = int(abs_sec // 60)
    seconds = int(abs_sec % 60)

    if show_fraction:
        fraction = int((abs_sec - int(abs_sec)) * 10)
        return f"{sign}{minutes:02d}:{seconds:02d}.{fraction:01d}"
    return f"{sign}{minutes:02d}:{seconds:02d}"


def transform_world_to_screen(
    x: float, y: float,
    cam_x: float, cam_y: float,
    zoom: float,
    rotation_deg: float,
    viewport_width: float,
    viewport_height: float
) -> Tuple[float, float]:
    """Applies camera affine transformation from world metric metres to screen pixels.

    Screen +V increases downwards; geographic +Y increases upwards.
    """
    rot_rad = math.radians(rotation_deg)
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)

    # Relative to camera center
    dx = x - cam_x
    dy = y - cam_y

    # Scale with inverted Y for canvas screen space
    sx = dx * zoom
    sy = -dy * zoom

    # Rotate
    u = cos_r * sx - sin_r * sy + (viewport_width / 2.0)
    v = sin_r * sx + cos_r * sy + (viewport_height / 2.0)
    return u, v


def transform_screen_to_world(
    u: float, v: float,
    cam_x: float, cam_y: float,
    zoom: float,
    rotation_deg: float,
    viewport_width: float,
    viewport_height: float
) -> Tuple[float, float]:
    """Inverse transformation from screen pixels to world metric metres."""
    rot_rad = math.radians(rotation_deg)
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)

    du = u - (viewport_width / 2.0)
    dv = v - (viewport_height / 2.0)

    # Inverse rotate
    rx = cos_r * du + sin_r * dv
    ry = -sin_r * du + cos_r * dv

    # Inverse scale & uninvert Y
    dx = rx / zoom
    dy = -ry / zoom

    x = dx + cam_x
    y = dy + cam_y
    return x, y


def compute_head_to_head(
    pos_a: Tuple[float, float],
    pos_b: Tuple[float, float],
    vel_a: Tuple[float, float],
    vel_b: Tuple[float, float],
    course_axis_deg: float = COURSE_AXIS_SETTLED_DEG
) -> Dict[str, float]:
    """Computes pairwise comparative tactical metrics between Boat A and Boat B."""
    axis_rad = math.radians(course_axis_deg)
    u_long = (math.sin(axis_rad), math.cos(axis_rad))  # Along-course unit vector
    u_lat = (-math.cos(axis_rad), math.sin(axis_rad))  # Lateral unit vector

    sep_x = pos_a[0] - pos_b[0]
    sep_y = pos_a[1] - pos_b[1]
    euclidean_sep = math.sqrt(sep_x**2 + sep_y**2)

    delta_long = sep_x * u_long[0] + sep_y * u_long[1]
    delta_lat = abs(sep_x * u_lat[0] + sep_y * u_lat[1])

    # Rate of closure: -d(distance)/dt = (v_b - v_a) . (pos_a - pos_b) / distance
    rel_vx = vel_b[0] - vel_a[0]
    rel_vy = vel_b[1] - vel_a[1]
    if euclidean_sep > 1e-6:
        rate_of_closure = (rel_vx * sep_x + rel_vy * sep_y) / euclidean_sep
    else:
        rate_of_closure = 0.0

    return {
        "euclidean_distance_m": euclidean_sep,
        "longitudinal_delta_m": delta_long,
        "lateral_separation_m": delta_lat,
        "rate_of_closure_mps": rate_of_closure,
    }
