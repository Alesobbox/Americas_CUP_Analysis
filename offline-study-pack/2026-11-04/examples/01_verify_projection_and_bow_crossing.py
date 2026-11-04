#!/usr/bin/env python3
"""
Executable Example 01 — WGS84 Curvature Projection, Circular Interpolation & Bow Crossing
=========================================================================================
Data Provenance:
  - PART A uses ACTUAL REPOSITORY EVIDENCE from `evidence/naples_pr1_replay_bounded_excerpt.json`
    (Naples course origin, WGS84 scale factors `k_lat` and `k_lon`, and FRA start crossing).
  - PART B uses SYNTHETIC DATA to demonstrate shortest-arc circular interpolation across 0/360 deg
    and exact sub-frame bow-tip (+12.963 m) segment intersection math.

Requires: Python 3.10+ standard library only (no third-party packages).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "evidence"

# WGS84 constants matching pipeline/projection.py:L14-L16
WGS84_A = 6_378_137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = 2.0 * WGS84_F - WGS84_F * WGS84_F
BOW_OFFSET_M = 12.963  # AC40 transom-to-bowsprit tip (pipeline/reconstruction.py:L25)


def wgs84_scale_factors(lat0_deg: float) -> tuple[float, float]:
    """Return (k_lon, k_lat) in metres per degree at reference latitude lat0_deg."""
    phi = math.radians(lat0_deg)
    sin_phi = math.sin(phi)
    denom = 1.0 - WGS84_E2 * sin_phi * sin_phi
    m_radius = WGS84_A * (1.0 - WGS84_E2) / (denom ** 1.5)
    n_radius = WGS84_A / math.sqrt(denom)
    k_lon = math.radians(1.0) * n_radius * math.cos(phi)
    k_lat = math.radians(1.0) * m_radius
    return k_lon, k_lat


def interpolate_angle_deg(a0: float, a1: float, alpha: float) -> float:
    """Shortest-arc circular interpolation in [0, 360) (pipeline/synchronize.py:L29-L48)."""
    delta = ((a1 - a0 + 540.0) % 360.0) - 180.0
    return (a0 + alpha * delta) % 360.0


def bow_point(x: float, y: float, heading_deg: float, offset_m: float = BOW_OFFSET_M) -> tuple[float, float]:
    """Project transom GNSS (x, y) forward along true heading to bowsprit tip."""
    rad = math.radians(heading_deg)
    return (x + offset_m * math.sin(rad), y + offset_m * math.cos(rad))


def segment_intersection_fraction(
    p0: tuple[float, float],
    p1: tuple[float, float],
    q0: tuple[float, float],
    q1: tuple[float, float],
) -> tuple[float, float] | None:
    """
    Exact 2D segment intersection matching pipeline/reconstruction.py:L39-L73.
    Returns (u, v) in [0, 1]^2 where u is fraction along motion p0->p1
    and v is fraction along gate segment q0->q1, or None if non-intersecting.
    """
    rx, ry = p1[0] - p0[0], p1[1] - p0[1]
    sx, sy = q1[0] - q0[0], q1[1] - q0[1]
    rxs = rx * sy - ry * sx
    if abs(rxs) < 1e-12:
        return None
    qpx, qpy = q0[0] - p0[0], q0[1] - p0[1]
    u = (qpx * sy - qpy * sx) / rxs
    v = (qpx * ry - qpy * rx) / rxs
    if -1e-9 <= u <= 1.0 + 1e-9 and -1e-9 <= v <= 1.0 + 1e-9:
        return max(0.0, min(1.0, u)), max(0.0, min(1.0, v))
    return None


def main() -> None:
    print("=" * 78)
    print("EXECUTABLE EXAMPLE 01: PROJECTION, CIRCULAR INTERPOLATION & BOW CROSSING")
    print("=" * 78)

    # PART A: Actual Repository Evidence (naples_pr1)
    excerpt_path = EVIDENCE_DIR / "naples_pr1_replay_bounded_excerpt.json"
    excerpt = json.loads(excerpt_path.read_text(encoding="utf-8"))
    origin = excerpt["course"]["origin"]
    proj = excerpt["course"]["projection"]
    k_lon, k_lat = wgs84_scale_factors(origin["lat"])

    print("\n[PART A — ACTUAL REPOSITORY EVIDENCE: naples_pr1]")
    print(f"  Session Course Origin    : ({origin['lat']:.8f} N, {origin['lon']:.8f} E)")
    print(f"  WGS84 Analytical Curv.   : k_lon = {k_lon:.3f} m/deg, k_lat = {k_lat:.3f} m/deg")
    print(f"  Exported course.projection: k_lon = {proj['k_lon']:.3f} m/deg, k_lat = {proj['k_lat']:.3f} m/deg")
    assert abs(k_lon - proj["k_lon"]) < 5.0
    assert abs(k_lat - proj["k_lat"]) < 5.0

    cag_lon, cag_lat = wgs84_scale_factors(39.1900)
    print(f"  CAGLIARI_REFERENCE(39.19N): k_lon = {cag_lon:.3f} m/deg, k_lat = {cag_lat:.3f} m/deg")

    gun_ms = excerpt["chronology"]["gun_time"]
    fra = next(c for c in excerpt["competitors"] if c["team_code"] == "FRA")
    fra_cross_ms = fra["start"]["crossing_time"]
    print(f"  naples_pr1 Gun Time      : {gun_ms} ms")
    print(f"  FRA Start Crossing Time  : {fra_cross_ms} ms ( Gun + {(fra_cross_ms - gun_ms)/1000:.3f} s )")
    assert fra_cross_ms - gun_ms == 436

    # PART B: Synthetic Hand-Checkable Examples
    print("\n[PART B — SYNTHETIC HAND-CHECKABLE EXAMPLES]")
    # 1. Shortest-arc circular interpolation across 0 deg North
    h0, h1, alpha = 355.0, 5.0, 0.30
    naive_linear = h0 + alpha * (h1 - h0)
    circular = interpolate_angle_deg(h0, h1, alpha)
    print(f"  1. Heading wrap 355 deg -> 5 deg at alpha=0.30:")
    print(f"     Naive linear lerp (WRONG) : {naive_linear:6.2f} deg (points South!)")
    print(f"     Shortest-arc angleLerp    : {circular:6.2f} deg (correct: 358.00 deg)")
    assert abs(circular - 358.0) < 1e-9

    # 2. Sub-frame bow crossing vs transom GNSS crossing
    q0, q1 = (-50.0, 100.0), (50.0, 100.0)
    t0, t1 = 1000, 1100
    transom0, transom1 = (0.0, 86.5), (0.0, 87.5)
    bow0 = bow_point(*transom0, heading_deg=0.0)
    bow1 = bow_point(*transom1, heading_deg=0.0)
    transom_hit = segment_intersection_fraction(transom0, transom1, q0, q1)
    bow_hit = segment_intersection_fraction(bow0, bow1, q0, q1)
    assert transom_hit is None and bow_hit is not None
    u, v = bow_hit
    t_cross = round(t0 + u * (t1 - t0))
    print(f"  2. Sub-frame bow crossing across gate y=100 m between t0=1000 ms and t1=1100 ms:")
    print(f"     Transom y0 -> y1          : {transom0[1]:.3f} m -> {transom1[1]:.3f} m (hit={transom_hit})")
    print(f"     Bowsprit y0 -> y1 (+12.963): {bow0[1]:.3f} m -> {bow1[1]:.3f} m")
    print(f"     Intersection fractions    : u = {u:.4f}, v = {v:.4f} -> t_cross = {t_cross} ms")
    assert t_cross == 1054
    print("\nAll assertions passed successfully.")


if __name__ == "__main__":
    main()
