"""Adversarial stress-testing suite for geodetic projection and numerical robustness.

Targets: pipeline/projection.py and pipeline/config.py
Adversarial tests include:
1. 10,000 geodetic point forward/inverse invertibility roundtrip across course envelope (|lat - lat'| < 1e-9, |lon - lon'| < 1e-9).
2. Pairwise distance distortion: Cartesian Euclidean distance vs Haversine geodesic distance across gate marks (<0.1%)
   and directional anisotropy analysis demonstrating the spherical Earth limit (~0.193%).
3. Geodesic distance distortion against WGS84 Ellipsoidal ground truth (Vincenty formula): strictly < 0.1% everywhere (achieves < 0.032%).
4. Boundary and corner stress tests (extremal coordinates, active race boundary polygon edges, course diagonal).
5. Floating point stability, sub-millimetre limits, identical points, and Cartesian-to-WGS84 roundtrip invertibility.
6. NaN, Infinity, malformed types, and degenerate input handling.
"""

from __future__ import annotations

import math
import random
import unittest

from pipeline.config import (
    LAT0,
    LON0,
    K_LAT,
    EARTH_RADIUS_LOCAL_M,
    MARKS,
)
from pipeline.projection import (
    wgs84_to_metric,
    metric_to_wgs84,
    haversine_distance,
    euclidean_distance,
    project_polygon_coords,
)


COURSE_LAT_MIN = 40.7900
COURSE_LAT_MAX = 40.8300
COURSE_LON_MIN = 14.2100
COURSE_LON_MAX = 14.2600

ACTIVE_RACE_BOUNDARY_WGS84 = [
    (40.823133, 14.240044),
    (40.803647, 14.218905),
    (40.794665, 14.233246),
    (40.794099, 14.234149),
    (40.794261, 14.236356),
    (40.800332, 14.242942),
    (40.803261, 14.242571),
    (40.814149, 14.254387),
]


def vincenty_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes exact geodesic distance on the WGS84 ellipsoid using Vincenty's inverse formula."""
    a = 6378137.0
    f = 1 / 298.257223563
    b = 6356752.314245
    phi1, lambda1 = math.radians(lat1), math.radians(lon1)
    phi2, lambda2 = math.radians(lat2), math.radians(lon2)
    L = lambda2 - lambda1
    U1 = math.atan((1 - f) * math.tan(phi1))
    U2 = math.atan((1 - f) * math.tan(phi2))
    sinU1, cosU1 = math.sin(U1), math.cos(U1)
    sinU2, cosU2 = math.sin(U2), math.cos(U2)
    lam = L
    for _ in range(100):
        sinLambda = math.sin(lam)
        cosLambda = math.cos(lam)
        sinSigma = math.sqrt(
            (cosU2 * sinLambda) ** 2 + (cosU1 * sinU2 - sinU1 * cosU2 * cosLambda) ** 2
        )
        if sinSigma == 0:
            return 0.0
        cosSigma = sinU1 * sinU2 + cosU1 * cosU2 * cosLambda
        sigma = math.atan2(sinSigma, cosSigma)
        sinAlpha = (cosU1 * cosU2 * sinLambda) / sinSigma
        cos2Alpha = 1 - sinAlpha**2
        cos2SigmaM = cosSigma - (2 * sinU1 * sinU2) / cos2Alpha if cos2Alpha != 0 else 0
        C = f / 16 * cos2Alpha * (4 + f * (4 - 3 * cos2Alpha))
        lamPrev = lam
        lam = L + (1 - C) * f * sinAlpha * (
            sigma + C * sinSigma * (cos2SigmaM + C * cosSigma * (-1 + 2 * cos2SigmaM**2))
        )
        if abs(lam - lamPrev) < 1e-12:
            break
    u2 = cos2Alpha * (a**2 - b**2) / b**2
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    deltaSigma = (
        B
        * sinSigma
        * (
            cos2SigmaM
            + B
            / 4
            * (
                cosSigma * (-1 + 2 * cos2SigmaM**2)
                - B
                / 6
                * cos2SigmaM
                * (-3 + 4 * sinSigma**2)
                * (-3 + 4 * cos2SigmaM**2)
            )
        )
    )
    return b * A * (sigma - deltaSigma)


class TestProjectionInvertibilityAdversarial(unittest.TestCase):
    """Stress tests forward/inverse invertibility: (lat, lon) -> (x, y) -> (lat', lon')."""

    def test_ten_thousand_random_points_invertibility(self):
        """Generates 10,000 random geodetic points across the course box and asserts |lat - lat'| < 1e-9 and |lon - lon'| < 1e-9."""
        rng = random.Random(42)
        num_points = 10_000

        max_lat_err = 0.0
        max_lon_err = 0.0

        for _ in range(num_points):
            lat = rng.uniform(COURSE_LAT_MIN, COURSE_LAT_MAX)
            lon = rng.uniform(COURSE_LON_MIN, COURSE_LON_MAX)

            x, y = wgs84_to_metric(lat, lon)
            lat_rec, lon_rec = metric_to_wgs84(x, y)

            lat_err = abs(lat - lat_rec)
            lon_err = abs(lon - lon_rec)

            if lat_err > max_lat_err:
                max_lat_err = lat_err
            if lon_err > max_lon_err:
                max_lon_err = lon_err

            self.assertLess(
                lat_err,
                1e-9,
                f"Latitude invertibility failed at ({lat}, {lon}): error {lat_err:.2e} >= 1e-9",
            )
            self.assertLess(
                lon_err,
                1e-9,
                f"Longitude invertibility failed at ({lat}, {lon}): error {lon_err:.2e} >= 1e-9",
            )

        # Invertibility achieves sub-picometre machine precision
        self.assertLess(max_lat_err, 1e-12)
        self.assertLess(max_lon_err, 1e-12)

    def test_cartesian_to_wgs84_roundtrip_invertibility(self):
        """Generates 10,000 Cartesian points (x, y) across [-5000m, +5000m] and asserts roundtrip |x - x'| < 1e-9 and |y - y'| < 1e-9."""
        rng = random.Random(1337)
        num_points = 10_000

        max_x_err = 0.0
        max_y_err = 0.0

        for _ in range(num_points):
            x = rng.uniform(-5000.0, 5000.0)
            y = rng.uniform(-5000.0, 5000.0)

            lat, lon = metric_to_wgs84(x, y)
            x_rec, y_rec = wgs84_to_metric(lat, lon)

            x_err = abs(x - x_rec)
            y_err = abs(y - y_rec)

            if x_err > max_x_err:
                max_x_err = x_err
            if y_err > max_y_err:
                max_y_err = y_err

            self.assertLess(
                x_err,
                1e-9,
                f"Cartesian X invertibility failed at ({x}, {y}): error {x_err:.2e} >= 1e-9",
            )
            self.assertLess(
                y_err,
                1e-9,
                f"Cartesian Y invertibility failed at ({x}, {y}): error {y_err:.2e} >= 1e-9",
            )

        self.assertLess(max_x_err, 1e-10)
        self.assertLess(max_y_err, 1e-9)


class TestPairwiseDistanceDistortionAdversarial(unittest.TestCase):
    """Stress tests distance distortion: Cartesian Euclidean vs Haversine Geodesic and Vincenty Ellipsoidal."""

    def test_pairwise_distance_distortion_vs_vincenty_geodesic(self):
        """Tests pairwise distance distortion across arbitrary vectors (50m to 3000m) against WGS84 Vincenty geodesic.

        Asserts distortion percentage |d_cart - d_vinc| / d_vinc * 100 < 0.1% strictly everywhere.
        Nominal empirical performance achieves < 0.032% (3x better than threshold).
        """
        rng = random.Random(999)
        tested_pairs = 0
        target_pairs = 3_000

        max_distortion_pct = 0.0

        while tested_pairs < target_pairs:
            lat1 = rng.uniform(COURSE_LAT_MIN, COURSE_LAT_MAX)
            lon1 = rng.uniform(COURSE_LON_MIN, COURSE_LON_MAX)
            lat2 = rng.uniform(COURSE_LAT_MIN, COURSE_LAT_MAX)
            lon2 = rng.uniform(COURSE_LON_MIN, COURSE_LON_MAX)

            d_vinc = vincenty_distance(lat1, lon1, lat2, lon2)
            if not (50.0 <= d_vinc <= 3000.0):
                continue

            x1, y1 = wgs84_to_metric(lat1, lon1)
            x2, y2 = wgs84_to_metric(lat2, lon2)
            d_cart = euclidean_distance(x1, y1, x2, y2)

            err_pct = abs(d_cart - d_vinc) / d_vinc * 100.0

            self.assertLess(
                err_pct,
                0.1,
                f"Cartesian distortion vs Vincenty {err_pct:.4f}% exceeded 0.1% for vector len {d_vinc:.1f}m",
            )

            tested_pairs += 1
            if err_pct > max_distortion_pct:
                max_distortion_pct = err_pct

        self.assertEqual(tested_pairs, target_pairs)
        # Verify that max distortion vs true WGS84 geodesic is strictly under 0.035%
        self.assertLess(max_distortion_pct, 0.035)

    def test_gate_marks_and_course_axis_haversine_accuracy(self):
        """Verifies that along course gate lines and course axis, Cartesian distance matches Haversine distance with < 0.1% error."""
        # Bottom gate
        rm8 = MARKS["RM8"]
        rm6 = MARKS["RM6"]
        x8, y8 = wgs84_to_metric(rm8.target_lat, rm8.target_lon)
        x6, y6 = wgs84_to_metric(rm6.target_lat, rm6.target_lon)
        d_cart_b = euclidean_distance(x8, y8, x6, y6)
        d_hav_b = haversine_distance(rm8.target_lat, rm8.target_lon, rm6.target_lat, rm6.target_lon)
        err_b_pct = abs(d_cart_b - d_hav_b) / d_hav_b * 100.0
        self.assertLess(err_b_pct, 0.1)
        self.assertAlmostEqual(err_b_pct, 0.028, delta=0.01)

        # Top gate
        rm4 = MARKS["RM4"]
        rm2 = MARKS["RM2"]
        x4, y4 = wgs84_to_metric(rm4.target_lat, rm4.target_lon)
        x2, y2 = wgs84_to_metric(rm2.target_lat, rm2.target_lon)
        d_cart_t = euclidean_distance(x4, y4, x2, y2)
        d_hav_t = haversine_distance(rm4.target_lat, rm4.target_lon, rm2.target_lat, rm2.target_lon)
        err_t_pct = abs(d_cart_t - d_hav_t) / d_hav_t * 100.0
        self.assertLess(err_t_pct, 0.1)
        self.assertAlmostEqual(err_t_pct, 0.042, delta=0.01)

        # Course axis (40 deg)
        d_course = 2259.44
        bearing_rad = math.radians(40.0)
        dx = d_course * math.sin(bearing_rad)
        dy = d_course * math.cos(bearing_rad)
        p_top_lat, p_top_lon = metric_to_wgs84(dx, dy)
        d_hav_axis = haversine_distance(LAT0, LON0, p_top_lat, p_top_lon)
        err_axis_pct = abs(d_course - d_hav_axis) / d_hav_axis * 100.0
        self.assertLess(err_axis_pct, 0.1)
        self.assertLess(err_axis_pct, 0.04)

    def test_haversine_spherical_anisotropy_characterization(self):
        """Characterizes and verifies the intrinsic spherical Earth distortion limit of Haversine.

        Due to Earth's oblateness (M != N), spherical Haversine with scalar radius R = sqrt(MN)
        inherently deviates by ~0.193% in cardinal directions:
        - Meridian (North-South, 0 deg): +0.194%
        - Parallel (East-West, 90 deg): -0.191%
        This test documents this physical boundary condition and verifies that error is bounded by 0.25%.
        """
        for length in [100.0, 500.0, 1000.0, 2000.0]:
            # North-South vector
            p_ns_lat, p_ns_lon = metric_to_wgs84(0.0, length)
            d_hav_ns = haversine_distance(LAT0, LON0, p_ns_lat, p_ns_lon)
            err_ns_pct = abs(length - d_hav_ns) / d_hav_ns * 100.0
            self.assertAlmostEqual(err_ns_pct, 0.194, delta=0.01)
            self.assertLess(err_ns_pct, 0.25)

            # East-West vector
            p_ew_lat, p_ew_lon = metric_to_wgs84(length, 0.0)
            d_hav_ew = haversine_distance(LAT0, LON0, p_ew_lat, p_ew_lon)
            err_ew_pct = abs(length - d_hav_ew) / d_hav_ew * 100.0
            self.assertAlmostEqual(err_ew_pct, 0.191, delta=0.01)
            self.assertLess(err_ew_pct, 0.25)


class TestBoundaryPointsAndRaceGeometry(unittest.TestCase):
    """Stress tests boundary points, active race boundary, and official course marks."""

    def test_course_marks_pairwise_distortion(self):
        """All mark pairs (RM8, RM6, RM4, RM2) have distortion strictly < 0.1% vs Haversine."""
        mark_keys = ["RM8", "RM6", "RM4", "RM2"]
        for i in range(len(mark_keys)):
            for j in range(i + 1, len(mark_keys)):
                m1 = MARKS[mark_keys[i]]
                m2 = MARKS[mark_keys[j]]

                x1, y1 = wgs84_to_metric(m1.target_lat, m1.target_lon)
                x2, y2 = wgs84_to_metric(m2.target_lat, m2.target_lon)
                d_cart = euclidean_distance(x1, y1, x2, y2)
                d_hav = haversine_distance(m1.target_lat, m1.target_lon, m2.target_lat, m2.target_lon)

                err_pct = abs(d_cart - d_hav) / d_hav * 100.0
                self.assertLess(
                    err_pct,
                    0.1,
                    f"Mark pair {m1.code}-{m2.code} distortion {err_pct:.4f}% exceeded 0.1%",
                )

    def test_active_race_boundary_polygon_edges_vs_vincenty(self):
        """All 8 segments of the active race boundary polygon have distortion < 0.1% vs Vincenty geodesic."""
        poly = ACTIVE_RACE_BOUNDARY_WGS84
        n = len(poly)
        for i in range(n):
            lat1, lon1 = poly[i]
            lat2, lon2 = poly[(i + 1) % n]

            x1, y1 = wgs84_to_metric(lat1, lon1)
            x2, y2 = wgs84_to_metric(lat2, lon2)
            d_cart = euclidean_distance(x1, y1, x2, y2)
            d_vinc = vincenty_distance(lat1, lon1, lat2, lon2)

            err_pct = abs(d_cart - d_vinc) / d_vinc * 100.0
            self.assertLess(
                err_pct,
                0.1,
                f"Boundary segment {i}->{(i+1)%n} distortion {err_pct:.4f}% exceeded 0.1%",
            )
            # In fact, error is under 0.03%
            self.assertLess(err_pct, 0.03)

    def test_project_polygon_coords_edge_cases(self):
        """Tests project_polygon_coords with various structures and edge cases."""
        # Empty polygon
        self.assertEqual(project_polygon_coords([]), [])

        # Heterogeneous formats
        mixed_input = [
            {"latitude": LAT0, "longitude": LON0},
            {"x": LON0, "y": LAT0},
            (LAT0, LON0),
            [LAT0, LON0],
        ]
        res = project_polygon_coords(mixed_input)
        self.assertEqual(len(res), 4)
        for pt in res:
            self.assertAlmostEqual(pt[0], 0.0, places=3)
            self.assertAlmostEqual(pt[1], 0.0, places=3)

        # Invalid structure raises ValueError or TypeError
        with self.assertRaises(ValueError):
            project_polygon_coords([{"unknown_field": 12.3}])

        with self.assertRaises(TypeError):
            project_polygon_coords([12345])  # type: ignore


class TestFloatingPointStabilityAndEdgeCases(unittest.TestCase):
    """Stress tests floating point stability, sub-millimetre distances, and NaN/Inf handling."""

    def test_zero_distance_and_identity(self):
        """Haversine and Euclidean distance between identical points is strictly 0.0."""
        points = [
            (LAT0, LON0),
            (0.0, 0.0),
            (89.999999, 179.999999),
            (-89.999999, -179.999999),
        ]
        for lat, lon in points:
            d_hav = haversine_distance(lat, lon, lat, lon)
            self.assertEqual(d_hav, 0.0)

            x, y = wgs84_to_metric(lat, lon)
            d_cart = euclidean_distance(x, y, x, y)
            self.assertEqual(d_cart, 0.0)

    def test_sub_millimetre_separations(self):
        """Micro-step displacements (sub-millimetre to micron) maintain numerical stability."""
        displacements_deg = [1e-5, 1e-6, 1e-7, 1e-8, 1e-9]
        for delta in displacements_deg:
            d_hav = haversine_distance(LAT0, LON0, LAT0 + delta, LON0)
            self.assertFalse(math.isnan(d_hav))
            self.assertFalse(math.isinf(d_hav))
            self.assertGreater(d_hav, 0.0)

            expected_m = delta * K_LAT
            self.assertAlmostEqual(d_hav, expected_m, delta=expected_m * 0.01)

    def test_antipodal_points_haversine(self):
        """Haversine distance between antipodal points does not produce NaN from acos/asin domain error."""
        d_antipodal = haversine_distance(0.0, 0.0, 0.0, 180.0)
        self.assertFalse(math.isnan(d_antipodal))
        expected = math.pi * EARTH_RADIUS_LOCAL_M
        self.assertAlmostEqual(d_antipodal, expected, delta=1.0)

        # North Pole to South Pole
        d_poles = haversine_distance(90.0, 0.0, -90.0, 0.0)
        self.assertFalse(math.isnan(d_poles))
        self.assertAlmostEqual(d_poles, expected, delta=1.0)

    def test_nan_and_inf_propagation(self):
        """NaN and Inf inputs propagate cleanly according to IEEE 754 without unhandled exceptions."""
        x_nan, y_nan = wgs84_to_metric(float("nan"), LON0)
        self.assertTrue(math.isnan(y_nan))
        self.assertFalse(math.isnan(x_nan))

        x_inf, y_inf = wgs84_to_metric(float("inf"), LON0)
        self.assertTrue(math.isinf(y_inf))

        d_nan = haversine_distance(float("nan"), LON0, LAT0, LON0)
        self.assertTrue(math.isnan(d_nan))

        d_euc_nan = euclidean_distance(float("nan"), 0.0, 0.0, 0.0)
        self.assertTrue(math.isnan(d_euc_nan))


if __name__ == "__main__":
    unittest.main()
