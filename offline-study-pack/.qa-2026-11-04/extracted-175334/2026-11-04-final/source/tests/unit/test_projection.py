"""Unit tests for WGS84 to local metric Cartesian projection."""

import math
import unittest

from pipeline.config import (
    LAT0,
    LON0,
    K_LAT,
    K_LON,
    EARTH_RADIUS_LOCAL_M,
    MARKS,
)
from pipeline.projection import (
    wgs84_to_metric,
    metric_to_wgs84,
    haversine_distance,
    euclidean_distance,
    project_polygon_coords,
    verify_gate_marks_projection_accuracy,
)


class TestProjection(unittest.TestCase):
    """Test suite for coordinate projections and geodetic calculations."""

    def test_origin_projection(self):
        """Course origin (lat0, lon0) must project exactly to (0.0, 0.0) metres."""
        x, y = wgs84_to_metric(LAT0, LON0)
        self.assertAlmostEqual(x, 0.0, places=9)
        self.assertAlmostEqual(y, 0.0, places=9)

    def test_origin_inverse_projection(self):
        """Cartesian (0.0, 0.0) must invert exactly to (lat0, lon0)."""
        lat, lon = metric_to_wgs84(0.0, 0.0)
        self.assertAlmostEqual(lat, LAT0, places=9)
        self.assertAlmostEqual(lon, LON0, places=9)

    def test_invertibility_roundtrip(self):
        """Arbitrary points within the regatta arena must invert back with sub-nanometre error."""
        test_points = [
            (40.80948, 14.23727),
            (40.80294, 14.22662),  # RM8
            (40.80030, 14.23084),  # RM6
            (40.81801, 14.24477),  # RM4
            (40.81668, 14.24685),  # RM2
            (40.79000, 14.21000),  # SW boundary
            (40.83000, 14.26000),  # NE boundary
        ]
        for orig_lat, orig_lon in test_points:
            x, y = wgs84_to_metric(orig_lat, orig_lon)
            rec_lat, rec_lon = metric_to_wgs84(x, y)
            self.assertAlmostEqual(
                rec_lat,
                orig_lat,
                places=11,
                msg=f"Latitude invertibility failed for ({orig_lat}, {orig_lon})",
            )
            self.assertAlmostEqual(
                rec_lon,
                orig_lon,
                places=11,
                msg=f"Longitude invertibility failed for ({orig_lat}, {orig_lon})",
            )

    def test_linear_symmetry_and_scaling(self):
        """Displacements from origin must scale linearly with curvature coefficients."""
        delta_deg = 0.01  # ~1.1 km
        # Northing
        _, y_pos = wgs84_to_metric(LAT0 + delta_deg, LON0)
        _, y_neg = wgs84_to_metric(LAT0 - delta_deg, LON0)
        self.assertAlmostEqual(y_pos, delta_deg * K_LAT, places=6)
        self.assertAlmostEqual(y_neg, -delta_deg * K_LAT, places=6)
        self.assertAlmostEqual(y_pos, -y_neg, places=9)

        # Easting
        x_pos, _ = wgs84_to_metric(LAT0, LON0 + delta_deg)
        x_neg, _ = wgs84_to_metric(LAT0, LON0 - delta_deg)
        self.assertAlmostEqual(x_pos, delta_deg * K_LON, places=6)
        self.assertAlmostEqual(x_neg, -delta_deg * K_LON, places=6)
        self.assertAlmostEqual(x_pos, -x_neg, places=9)

    def test_haversine_properties(self):
        """Haversine distance must satisfy identity, symmetry, and triangle inequality."""
        p1 = (40.80293791, 14.22662080)
        p2 = (40.80029953, 14.23084192)
        p3 = (40.81800615, 14.24476797)

        # Identity
        self.assertAlmostEqual(haversine_distance(p1[0], p1[1], p1[0], p1[1]), 0.0, places=9)

        # Symmetry
        d12 = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        d21 = haversine_distance(p2[0], p2[1], p1[0], p1[1])
        self.assertAlmostEqual(d12, d21, places=9)

        # Triangle inequality: d(1, 3) <= d(1, 2) + d(2, 3)
        d23 = haversine_distance(p2[0], p2[1], p3[0], p3[1])
        d13 = haversine_distance(p1[0], p1[1], p3[0], p3[1])
        self.assertLessEqual(d13, d12 + d23 + 1e-6)

    def test_bottom_gate_projection_accuracy(self):
        """Metric distance between RM8 and RM6 must match Haversine distance with <0.1% error."""
        rm8 = MARKS["RM8"]
        rm6 = MARKS["RM6"]

        x8, y8 = wgs84_to_metric(rm8.target_lat, rm8.target_lon)
        x6, y6 = wgs84_to_metric(rm6.target_lat, rm6.target_lon)
        d_cart = euclidean_distance(x8, y8, x6, y6)
        d_hav = haversine_distance(rm8.target_lat, rm8.target_lon, rm6.target_lat, rm6.target_lon)

        error_pct = abs(d_cart - d_hav) / d_hav * 100.0

        # Must be strictly under 0.1% (nominal ~0.028%)
        self.assertLess(
            error_pct,
            0.1,
            f"Bottom gate error {error_pct:.4f}% exceeds 0.1% limit",
        )
        self.assertAlmostEqual(error_pct, 0.028, delta=0.01)

    def test_top_gate_projection_accuracy(self):
        """Metric distance between RM4 and RM2 must match Haversine distance with <0.1% error."""
        rm4 = MARKS["RM4"]
        rm2 = MARKS["RM2"]

        x4, y4 = wgs84_to_metric(rm4.target_lat, rm4.target_lon)
        x2, y2 = wgs84_to_metric(rm2.target_lat, rm2.target_lon)
        d_cart = euclidean_distance(x4, y4, x2, y2)
        d_hav = haversine_distance(rm4.target_lat, rm4.target_lon, rm2.target_lat, rm2.target_lon)

        error_pct = abs(d_cart - d_hav) / d_hav * 100.0

        # Must be strictly under 0.1% (nominal ~0.042%)
        self.assertLess(
            error_pct,
            0.1,
            f"Top gate error {error_pct:.4f}% exceeds 0.1% limit",
        )
        self.assertAlmostEqual(error_pct, 0.042, delta=0.01)

    def test_verify_gate_marks_helper(self):
        """Verification helper must report all_passed=True for 0.1% tolerance."""
        res = verify_gate_marks_projection_accuracy(tolerance_pct=0.1)
        self.assertTrue(res["all_passed"])
        self.assertTrue(res["bottom_gate"]["passed"])
        self.assertTrue(res["top_gate"]["passed"])

    def test_polygon_coords_projection(self):
        """Polygon coords conversion must support AC session x/y and standard lat/lon dicts."""
        # AC session convention: x = lon, y = lat
        session_pts = [
            {"x": 14.23726898, "y": 40.80948067},  # origin
            {"x": 14.24000000, "y": 40.82000000},
        ]
        projected = project_polygon_coords(session_pts)
        self.assertEqual(len(projected), 2)
        self.assertAlmostEqual(projected[0][0], 0.0, places=6)
        self.assertAlmostEqual(projected[0][1], 0.0, places=6)

        # Standard lat/lon dict
        std_pts = [{"latitude": 40.80948067, "longitude": 14.23726898}]
        projected_std = project_polygon_coords(std_pts)
        self.assertAlmostEqual(projected_std[0][0], 0.0, places=6)
        self.assertAlmostEqual(projected_std[0][1], 0.0, places=6)

        # Tuples (lat, lon)
        tuple_pts = [(40.80948067, 14.23726898)]
        projected_tuple = project_polygon_coords(tuple_pts)
        self.assertAlmostEqual(projected_tuple[0][0], 0.0, places=6)
        self.assertAlmostEqual(projected_tuple[0][1], 0.0, places=6)

        # Invalid keys should raise ValueError
        with self.assertRaises(ValueError):
            project_polygon_coords([{"foo": 1, "bar": 2}])


if __name__ == "__main__":
    unittest.main()
