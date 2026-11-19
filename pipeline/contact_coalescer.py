"""Continuous pairwise Separating Axis Theorem (SAT) collision detector and contact coalescer.

Evaluates 2D Keep Clear Border polygon overlaps across 100ms frames and coalesces
consecutive colliding frames into discrete VirtualContactIncident events.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple, Any, Optional

# AC40 Keep Clear Border local coordinates (metres)
# Longitudinal: -0.215m to 12.963m
# Lateral: +/-7.415m at foil wings, +/-3.5075m at transom
DEFAULT_KEEP_CLEAR_BORDER: List[Tuple[float, float]] = [
    (0.0, -0.215),
    (3.5075, 0.0),
    (7.415, 6.278),
    (7.415, 6.89),
    (2.0, 12.963),
    (-2.0, 12.963),
    (-7.415, 6.89),
    (-7.415, 6.278),
    (-3.5075, 0.0),
]

DEFAULT_PLATFORM_BORDER: List[Tuple[float, float]] = [
    (0.0, -0.215),
    (1.5075, 0.0),
    (5.415, 6.278),
    (5.415, 6.89),
    (0.0, 12.963),
    (-5.415, 6.89),
    (-5.415, 6.278),
    (-1.5075, 0.0),
]


def transform_local_to_world(
    local_coords: List[Any],
    boat_x: float,
    boat_y: float,
    heading_deg: float,
) -> List[Tuple[float, float]]:
    """Transforms local (u starboard, v forward) coordinates to world (x East, y North)."""
    rad = math.radians(heading_deg)
    cos_h = math.cos(rad)
    sin_h = math.sin(rad)

    world: List[Tuple[float, float]] = []
    for pt in local_coords:
        if isinstance(pt, dict):
            u = float(pt["x"])
            v = float(pt["y"])
        elif isinstance(pt, (list, tuple)):
            u = float(pt[0])
            v = float(pt[1])
        else:
            continue
        x = boat_x + u * cos_h + v * sin_h
        y = boat_y - u * sin_h + v * cos_h
        world.append((x, y))
    return world


def _strip_closing_vertex(poly: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(poly) > 1:
        if math.isclose(poly[0][0], poly[-1][0], abs_tol=1e-6) and math.isclose(poly[0][1], poly[-1][1], abs_tol=1e-6):
            return poly[:-1]
    return poly


def test_sat_overlap(
    poly_a: List[Tuple[float, float]],
    poly_b: List[Tuple[float, float]],
) -> Tuple[bool, float]:
    """Tests 2D collision between two strictly convex polygons using SAT.

    Returns (has_overlap, penetration_depth_m).
    """
    verts_a = _strip_closing_vertex(poly_a)
    verts_b = _strip_closing_vertex(poly_b)

    if len(verts_a) < 3 or len(verts_b) < 3:
        return False, 0.0

    min_overlap = float("inf")
    polygons = [verts_a, verts_b]

    for p in range(2):
        poly = polygons[p]
        count = len(poly)
        for i in range(count):
            p1 = poly[i]
            p2 = poly[(i + 1) % count]

            ex = p2[0] - p1[0]
            ey = p2[1] - p1[1]
            edge_len = math.hypot(ex, ey)
            if edge_len < 1e-9:
                continue

            nx = -ey / edge_len
            ny = ex / edge_len

            # Project poly_a
            min_a = float("inf")
            max_a = float("-inf")
            for pt in verts_a:
                dot = pt[0] * nx + pt[1] * ny
                if dot < min_a:
                    min_a = dot
                if dot > max_a:
                    max_a = dot

            # Project poly_b
            min_b = float("inf")
            max_b = float("-inf")
            for pt in verts_b:
                dot = pt[0] * nx + pt[1] * ny
                if dot < min_b:
                    min_b = dot
                if dot > max_b:
                    max_b = dot

            overlap = min(max_a, max_b) - max(min_a, min_b)
            if overlap <= 0.0:
                return False, 0.0

            if overlap < min_overlap:
                min_overlap = overlap

    return True, min_overlap if min_overlap != float("inf") else 0.0


test_sat_overlap.__test__ = False


def compute_polygon_area(poly: List[Tuple[float, float]]) -> float:
    """Computes area of a 2D polygon using the Shoelace formula."""
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1]
    return abs(area) * 0.5


def _clip_polygon_by_line(
    subject: List[Tuple[float, float]],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
) -> List[Tuple[float, float]]:
    result: List[Tuple[float, float]] = []
    if not subject:
        return result

    def is_inside(pt: Tuple[float, float]) -> bool:
        return (p2[0] - p1[0]) * (pt[1] - p1[1]) - (p2[1] - p1[1]) * (pt[0] - p1[0]) >= -1e-9

    def intersection(s: Tuple[float, float], e: Tuple[float, float]) -> Tuple[float, float]:
        a1 = e[1] - s[1]
        b1 = s[0] - e[0]
        c1 = a1 * s[0] + b1 * s[1]

        a2 = p2[1] - p1[1]
        b2 = p1[0] - p2[0]
        c2 = a2 * p1[0] + b2 * p1[1]

        det = a1 * b2 - a2 * b1
        if abs(det) < 1e-11:
            return s
        return ((b2 * c1 - b1 * c2) / det, (a1 * c2 - a2 * c1) / det)

    s = subject[-1]
    for e in subject:
        if is_inside(e):
            if not is_inside(s):
                result.append(intersection(s, e))
            result.append(e)
        elif is_inside(s):
            result.append(intersection(s, e))
        s = e
    return result


def compute_polygon_intersection_area(
    poly_a: List[Tuple[float, float]],
    poly_b: List[Tuple[float, float]],
) -> float:
    """Computes exact 2D intersection area (m^2) between two convex polygons."""
    subject = list(_strip_closing_vertex(poly_a))
    clipper = list(_strip_closing_vertex(poly_b))

    if len(subject) < 3 or len(clipper) < 3:
        return 0.0

    # Ensure clipper is counter-clockwise
    area_sum = 0.0
    for i in range(len(clipper)):
        j = (i + 1) % len(clipper)
        area_sum += clipper[i][0] * clipper[j][1] - clipper[j][0] * clipper[i][1]
    if area_sum < 0:
        clipper.reverse()

    for i in range(len(clipper)):
        p1 = clipper[i]
        p2 = clipper[(i + 1) % len(clipper)]
        subject = _clip_polygon_by_line(subject, p1, p2)
        if len(subject) < 3:
            return 0.0

    return compute_polygon_area(subject)


def coalesce_virtual_contacts(
    grid_timestamps_ms: List[int],
    boats: Dict[str, Any],
    keep_clear_border_coords: Optional[List[Any]] = None,
    bounding_radius_m: float = 15.0,
    active_masks: Optional[Dict[str, List[bool]]] = None,
) -> List[Dict[str, Any]]:
    """Evaluates pairwise Keep Clear Border overlaps across 100ms frames and coalesces incidents.

    boats can be:
    - Dict mapping code/id -> SynchronizedBoatData (with .x, .y, .heading, .code, .asset_id)
    - Dict mapping id -> {"x": [...], "y": [...], "heading": [...], "code": "..."}
    """
    if keep_clear_border_coords is None:
        keep_clear_border_coords = DEFAULT_KEEP_CLEAR_BORDER

    n_frames = len(grid_timestamps_ms)
    boat_keys = list(boats.keys())

    # Extract arrays and metadata for each boat
    boat_metadata: Dict[str, Dict[str, Any]] = {}
    for key in boat_keys:
        b = boats[key]
        if hasattr(b, "x"):
            # Dataclass SynchronizedBoatData
            boat_metadata[key] = {
                "id": getattr(b, "asset_id", key),
                "code": getattr(b, "code", key),
                "x": b.x,
                "y": b.y,
                "heading": b.heading,
            }
        elif isinstance(b, dict):
            # Dict structure
            tel = b.get("telemetry", b)
            boat_metadata[key] = {
                "id": b.get("id", key),
                "code": b.get("code", b.get("team_code", key)),
                "x": tel.get("x", []),
                "y": tel.get("y", []),
                "heading": tel.get("heading", []),
            }

    active_incidents: Dict[Tuple[str, str], Dict[str, Any]] = {}
    closed_incidents: List[Dict[str, Any]] = []

    # Broadphase radius threshold: 2 * 15m = 30m -> 30^2 = 900
    bounding_threshold_sq = (2 * bounding_radius_m) ** 2

    for f_idx in range(n_frames):
        t_ms = grid_timestamps_ms[f_idx]
        current_frame_contacts = set()

        for i in range(len(boat_keys)):
            k_a = boat_keys[i]
            if active_masks is not None and k_a in active_masks:
                mask_a = active_masks[k_a]
                if f_idx >= len(mask_a) or not mask_a[f_idx]:
                    continue
            b_a = boat_metadata[k_a]
            if f_idx >= len(b_a["x"]) or f_idx >= len(b_a["y"]) or f_idx >= len(b_a["heading"]):
                continue
            xa = b_a["x"][f_idx]
            ya = b_a["y"][f_idx]
            hdg_a = b_a["heading"][f_idx]
            if not (math.isfinite(xa) and math.isfinite(ya) and math.isfinite(hdg_a)):
                continue

            for j in range(i + 1, len(boat_keys)):
                k_b = boat_keys[j]
                if active_masks is not None and k_b in active_masks:
                    mask_b = active_masks[k_b]
                    if f_idx >= len(mask_b) or not mask_b[f_idx]:
                        continue
                b_b = boat_metadata[k_b]
                if f_idx >= len(b_b["x"]) or f_idx >= len(b_b["y"]) or f_idx >= len(b_b["heading"]):
                    continue
                xb = b_b["x"][f_idx]
                yb = b_b["y"][f_idx]
                hdg_b = b_b["heading"][f_idx]
                if not (math.isfinite(xb) and math.isfinite(yb) and math.isfinite(hdg_b)):
                    continue

                # 1. Broadphase bounding filter
                dx = xb - xa
                dy = yb - ya
                dist_sq = dx * dx + dy * dy
                if dist_sq > bounding_threshold_sq:
                    continue

                center_dist = math.sqrt(dist_sq)

                # 2. Narrowphase SAT
                poly_a = transform_local_to_world(keep_clear_border_coords, xa, ya, hdg_a)
                poly_b = transform_local_to_world(keep_clear_border_coords, xb, yb, hdg_b)
                has_contact, depth = test_sat_overlap(poly_a, poly_b)

                pair_key = (k_a, k_b)
                if has_contact:
                    current_frame_contacts.add(pair_key)
                    overlap_area = compute_polygon_intersection_area(poly_a, poly_b)

                    if pair_key not in active_incidents:
                        active_incidents[pair_key] = {
                            "id": f"vci-{b_a['code']}-{b_b['code']}-{t_ms}",
                            "boat_a": b_a["code"],
                            "boat_b": b_b["code"],
                            "boat_a_id": b_a["id"],
                            "boat_b_id": b_b["id"],
                            "boat_a_code": b_a["code"],
                            "boat_b_code": b_b["code"],
                            "start_ms": t_ms,
                            "end_ms": t_ms,
                            "duration_ms": 0,
                            "peak_ms": t_ms,
                            "min_center_distance_m": round(center_dist, 2),
                            "peak_overlap_m": round(depth, 3),
                            "peak_overlap_m2": round(overlap_area, 3),
                            "start_frame_idx": f_idx,
                            "end_frame_idx": f_idx,
                            "type": "KEEP_CLEAR_BORDER_CROSSING",
                        }
                    else:
                        inc = active_incidents[pair_key]
                        inc["end_ms"] = t_ms
                        inc["end_frame_idx"] = f_idx
                        inc["duration_ms"] = inc["end_ms"] - inc["start_ms"]

                        if center_dist < inc["min_center_distance_m"]:
                            inc["min_center_distance_m"] = round(center_dist, 2)

                        if depth > inc["peak_overlap_m"]:
                            inc["peak_overlap_m"] = round(depth, 3)
                            inc["peak_ms"] = t_ms

                        if overlap_area > inc["peak_overlap_m2"]:
                            inc["peak_overlap_m2"] = round(overlap_area, 3)

        # Close incidents that ended on this frame
        ended_pairs = [pair for pair in active_incidents if pair not in current_frame_contacts]
        for pair in ended_pairs:
            inc = active_incidents.pop(pair)
            inc["duration_ms"] = inc["end_ms"] - inc["start_ms"]
            closed_incidents.append(inc)

    # Close any remaining active incidents at dataset conclusion
    for inc in active_incidents.values():
        inc["duration_ms"] = inc["end_ms"] - inc["start_ms"]
        closed_incidents.append(inc)

    closed_incidents.sort(key=lambda x: x["start_ms"])
    return closed_incidents


def coalesce_from_replay_dict(replay_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts telemetry streams from a serialized replay dictionary and computes virtual contact incidents."""
    tel = replay_dict.get("telemetry", {})
    timestamps = tel.get("timestamps", [])
    boats_tel = tel.get("boats", {})

    # Map asset_id to team_code if competitors catalog is present
    id_to_code: Dict[str, str] = {}
    for comp in replay_dict.get("competitors", []):
        aid = comp.get("id")
        code = comp.get("team_code")
        if aid and code:
            id_to_code[aid] = code

    # Extract keep clear border from course or root safety_borders
    safety_borders = replay_dict.get("safety_borders") or replay_dict.get("course", {}).get("safety_borders")
    keep_clear = DEFAULT_KEEP_CLEAR_BORDER
    if safety_borders and "keep_clear_border" in safety_borders:
        kc = safety_borders["keep_clear_border"]
        if kc:
            keep_clear = [(float(pt["x"]), float(pt["y"])) if isinstance(pt, dict) else (float(pt[0]), float(pt[1])) for pt in kc]

    # Reshape boats into dictionary expected by coalesce_virtual_contacts
    boat_dict: Dict[str, Any] = {}
    stream_cov = (replay_dict.get("provenance") or {}).get("stream_coverage") or {}
    active_masks: Optional[Dict[str, List[bool]]] = None
    if isinstance(stream_cov, dict) and stream_cov:
        active_masks = {}

    for aid, b_data in boats_tel.items():
        code = id_to_code.get(aid, aid)
        boat_dict[aid] = {
            "id": aid,
            "code": code,
            "x": b_data.get("x", []),
            "y": b_data.get("y", []),
            "heading": b_data.get("heading", []),
        }
        if active_masks is not None:
            cov = stream_cov.get(code) or stream_cov.get(aid)
            if isinstance(cov, dict) and cov.get("first_ms") is not None and cov.get("last_ms") is not None:
                f_ms = int(cov["first_ms"])
                l_ms = int(cov["last_ms"])
                gaps = [(int(g[0]), int(g[1])) for g in cov.get("gaps", []) if isinstance(g, (list, tuple)) and len(g) >= 2]
                g_idx = 0
                n_gaps = len(gaps)
                mask: List[bool] = []
                for t in timestamps:
                    if t < f_ms or t > l_ms:
                        mask.append(False)
                        continue
                    while g_idx < n_gaps and t >= gaps[g_idx][1]:
                        g_idx += 1
                    in_gap = g_idx < n_gaps and gaps[g_idx][0] < t < gaps[g_idx][1]
                    mask.append(not in_gap)
                active_masks[aid] = mask

    return coalesce_virtual_contacts(
        grid_timestamps_ms=timestamps,
        boats=boat_dict,
        keep_clear_border_coords=keep_clear,
        active_masks=active_masks,
    )
