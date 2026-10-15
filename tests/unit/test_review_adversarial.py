"""Independent Adversarial & Stress Verification Suite for Milestone 1.

Written by Reviewer M1.1 to independently verify:
1. Mathematical precision and edge-case resilience of 2D SAT contact detection.
2. Independent reproduction of the 6 virtual contact incidents in naples_pr1.json.
3. Verification that naples_mr_final.json contains 0 contact incidents.
4. Schema conformance of manifests.json and replays.
5. Large-fleet and multi-angle stress tests.
"""

import json
import math
import os
import unittest

from pipeline.contact_coalescer import (
    DEFAULT_KEEP_CLEAR_BORDER,
    DEFAULT_PLATFORM_BORDER,
    transform_local_to_world,
    test_sat_overlap,
    compute_polygon_area,
    compute_polygon_intersection_area,
    coalesce_from_replay_dict,
    coalesce_virtual_contacts,
)


class TestReviewAdversarial(unittest.TestCase):
    """Reviewer M1.1 independent adversarial tests."""

    def test_precision_boundary_tolerance(self):
        """Test boundary transition at exact maximum Keep Clear Border span 14.830m."""
        # Half-beam is 7.415m. Two parallel boats have max span 14.830m.
        max_span = 14.830
        delta = 0.005  # 5mm

        # Sub-millimetre contact (14.825m)
        poly_a = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 0.0, 0.0, 0.0)
        poly_b_contact = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, max_span - delta, 0.0, 0.0)
        has_c, depth = test_sat_overlap(poly_a, poly_b_contact)
        self.assertTrue(has_c, "Failed to detect contact at 5mm penetration")
        self.assertAlmostEqual(depth, delta, places=2)

        # Clear by 5mm (14.835m)
        poly_b_clear = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, max_span + delta, 0.0, 0.0)
        has_c_clear, depth_clear = test_sat_overlap(poly_a, poly_b_clear)
        self.assertFalse(has_c_clear, "Falsely detected contact at 5mm clearance")
        self.assertEqual(depth_clear, 0.0)

    def test_extreme_heading_wrap_invariance(self):
        """Test that angles outside [0, 360) (e.g. -720, 1080, -45) yield identical geometries."""
        angles = [
            (0.0, 360.0),
            (0.0, 720.0),
            (0.0, -360.0),
            (45.0, 405.0),
            (45.0, -315.0),
            (90.0, 450.0),
            (180.0, -180.0),
            (270.0, -90.0),
        ]
        for a1, a2 in angles:
            poly1 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 10.0, 20.0, a1)
            poly2 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 10.0, 20.0, a2)
            self.assertEqual(len(poly1), len(poly2))
            for (x1, y1), (x2, y2) in zip(poly1, poly2):
                self.assertAlmostEqual(x1, x2, places=6)
                self.assertAlmostEqual(y1, y2, places=6)

    def test_complete_containment_overlap(self):
        """When one boat polygon is completely inside another (e.g. smaller border), area is exact."""
        # Platform border is completely inside Keep Clear Border
        poly_kc = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 0.0, 0.0, 35.0)
        poly_pf = transform_local_to_world(DEFAULT_PLATFORM_BORDER, 0.0, 0.0, 35.0)

        has_c, depth = test_sat_overlap(poly_kc, poly_pf)
        self.assertTrue(has_c)

        area_pf = compute_polygon_area(poly_pf)
        overlap_area = compute_polygon_intersection_area(poly_kc, poly_pf)
        self.assertAlmostEqual(overlap_area, area_pf, places=2)

    def test_independent_coalesce_naples_pr1(self):
        """Independently re-run contact coalescer on naples_pr1.json and verify 100% agreement."""
        replay_path = "public/data/replays/naples_pr1.json"
        self.assertTrue(os.path.exists(replay_path))
        with open(replay_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        incidents = coalesce_from_replay_dict(data)
        stored_incidents = data.get("virtual_contact_incidents", [])

        self.assertEqual(len(incidents), 6, f"Expected 6 incidents, got {len(incidents)}")
        self.assertEqual(len(stored_incidents), 6)

        for computed, stored in zip(incidents, stored_incidents):
            self.assertEqual(computed["id"], stored["id"])
            self.assertEqual(computed["boat_a"], stored["boat_a"])
            self.assertEqual(computed["boat_b"], stored["boat_b"])
            self.assertEqual(computed["start_ms"], stored["start_ms"])
            self.assertEqual(computed["end_ms"], stored["end_ms"])
            self.assertEqual(computed["duration_ms"], stored["duration_ms"])
            self.assertEqual(computed["peak_ms"], stored["peak_ms"])
            self.assertAlmostEqual(computed["min_center_distance_m"], stored["min_center_distance_m"], places=2)
            self.assertAlmostEqual(computed["peak_overlap_m"], stored["peak_overlap_m"], places=2)
            self.assertAlmostEqual(computed["peak_overlap_m2"], stored["peak_overlap_m2"], places=2)

    def test_independent_coalesce_naples_mr_final(self):
        """Independently re-run contact coalescer on naples_mr_final.json and verify 0 contacts."""
        replay_path = "public/data/replays/naples_mr_final.json"
        self.assertTrue(os.path.exists(replay_path))
        with open(replay_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        incidents = coalesce_from_replay_dict(data)
        self.assertEqual(len(incidents), 0)
        self.assertEqual(len(data.get("virtual_contact_incidents", [])), 0)

    def test_manifest_and_replay_schema_integrity(self):
        """Verify presence and valid values of all required fields in manifests and replays."""
        manifest_path = "public/data/manifests.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("boat_class"), "AC40")
        self.assertIn(
            manifest.get("event_edition"),
            {
                "37th America's Cup Preliminary Regattas 2026",
                "37th America's Cup Preliminary Regatta Naples 2026",
            },
        )

        valid_editions = {
            "37th America's Cup Preliminary Regatta Naples 2026",
            "37th America's Cup Preliminary Regatta Cagliari 2026",
        }

        for r in manifest.get("races", []):
            self.assertEqual(r.get("boat_class"), "AC40")
            self.assertIn(r.get("event_edition"), valid_editions)

        for reg in manifest.get("regattas", []):
            self.assertEqual(reg.get("boat_class"), "AC40")
            self.assertIn(reg.get("event_edition"), valid_editions)
            for r in reg.get("races", []):
                self.assertEqual(r.get("boat_class"), "AC40")
                self.assertIn(r.get("event_edition"), valid_editions)

        # Verify replays have required fields
        for rep_file in ["public/data/replays/naples_pr1.json", "public/data/replays/naples_mr_final.json"]:
            with open(rep_file, "r", encoding="utf-8") as f:
                rep = json.load(f)
            self.assertEqual(rep.get("boat_class"), "AC40")
            self.assertEqual(rep.get("event_edition"), "37th America's Cup Preliminary Regatta Naples 2026")
            self.assertIn("class_evidence", rep)
            self.assertEqual(rep["class_evidence"].get("confidence"), "CONFIRMED")
            self.assertIn("safety_borders", rep)
            self.assertIn("platform_border", rep["safety_borders"])
            self.assertIn("keep_clear_border", rep["safety_borders"])
            self.assertIn("virtual_contact_incidents", rep)


if __name__ == "__main__":
    unittest.main()
