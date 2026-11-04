"""Unit tests for pipeline.contact_coalescer."""

import math
import unittest

from pipeline.contact_coalescer import (
    DEFAULT_KEEP_CLEAR_BORDER,
    DEFAULT_PLATFORM_BORDER,
    transform_local_to_world,
    test_sat_overlap,
    compute_polygon_area,
    compute_polygon_intersection_area,
    coalesce_virtual_contacts,
)


class TestContactCoalescer(unittest.TestCase):
    """Test suite for SAT collision detection and incident coalescing."""

    def test_sat_rotation_invariance(self):
        """Rotating two colliding boats and their offset vector preserves collision and overlap."""
        base_dist = 10.0  # 10m < 14.83m span
        test_angles = [0.0, 45.0, 90.0, 180.0, 270.0]
        results = []

        for angle in test_angles:
            rad = math.radians(angle)
            boat_a_pos = (0.0, 0.0)
            # Offset perpendicular to heading (starboard)
            boat_b_pos = (base_dist * math.cos(rad), -base_dist * math.sin(rad))

            poly_a = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, boat_a_pos[0], boat_a_pos[1], angle)
            poly_b = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, boat_b_pos[0], boat_b_pos[1], angle)

            has_contact, depth = test_sat_overlap(poly_a, poly_b)
            area = compute_polygon_intersection_area(poly_a, poly_b)
            results.append((has_contact, depth, area))

        ref_contact, ref_depth, ref_area = results[0]
        self.assertTrue(ref_contact)
        self.assertGreater(ref_depth, 0.0)
        self.assertGreater(ref_area, 0.0)

        for has_c, d, a in results[1:]:
            self.assertTrue(has_c)
            self.assertAlmostEqual(d, ref_depth, places=2)
            self.assertAlmostEqual(a, ref_area, places=1)

    def test_lateral_separation_thresholds(self):
        """15.0m lateral separation has no contact, 12.0m lateral separation has contact."""
        # 15.0m: Keep Clear Border span is 14.83m -> clearance of 0.17m
        poly_a_15 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 0.0, 0.0, 0.0)
        poly_b_15 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 15.0, 0.0, 0.0)
        has_contact_15, depth_15 = test_sat_overlap(poly_a_15, poly_b_15)
        self.assertFalse(has_contact_15)
        self.assertEqual(depth_15, 0.0)

        # 12.0m: Keep Clear Border intersects
        poly_b_12 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 12.0, 0.0, 0.0)
        has_contact_12, depth_12 = test_sat_overlap(poly_a_15, poly_b_12)
        self.assertTrue(has_contact_12)
        self.assertAlmostEqual(depth_12, 2.73, places=1)

    def test_coalesce_discrete_incidents(self):
        """Consecutive colliding frames are coalesced into a single incident with peak metrics."""
        timestamps = [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700]
        # Frame 0: 20m (no contact)
        # Frame 1: 13m (contact, depth ~1.83m)
        # Frame 2: 10m (contact, peak depth ~4.83m)
        # Frame 3: 12m (contact, depth ~2.83m)
        # Frame 4: 14m (contact, depth ~0.83m)
        # Frame 5: 25m (no contact)
        # Frame 6: 25m (no contact)
        # Frame 7: 25m (no contact)
        separations = [20.0, 13.0, 10.0, 12.0, 14.0, 25.0, 25.0, 25.0]

        boats = {
            "FRA": {
                "id": "uuid-fra",
                "code": "FRA",
                "x": [0.0] * 8,
                "y": [0.0] * 8,
                "heading": [0.0] * 8,
            },
            "NZL_G": {
                "id": "uuid-nzl",
                "code": "NZL G",
                "x": separations,
                "y": [0.0] * 8,
                "heading": [0.0] * 8,
            },
        }

        incidents = coalesce_virtual_contacts(timestamps, boats)
        self.assertEqual(len(incidents), 1)

        inc = incidents[0]
        self.assertEqual(inc["boat_a"], "FRA")
        self.assertEqual(inc["boat_b"], "NZL G")
        self.assertEqual(inc["start_ms"], 1100)
        self.assertEqual(inc["end_ms"], 1400)
        self.assertEqual(inc["duration_ms"], 300)
        self.assertEqual(inc["peak_ms"], 1200)
        self.assertAlmostEqual(inc["min_center_distance_m"], 10.0, places=1)
        self.assertGreater(inc["peak_overlap_m"], 4.0)
        self.assertGreater(inc["peak_overlap_m2"], 0.0)


if __name__ == "__main__":
    unittest.main()
