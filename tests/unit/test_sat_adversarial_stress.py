"""Adversarial stress testing suite for SAT collision detection and contact coalescing.

Empirical Challenger M1.1 stress tests:
1. Rapid rotation sweeps (0° to 359° at 1° increments)
2. High-velocity crossings (closing speed 40 knots = 20.6 m/s across 100ms frames)
3. Glancing touches with sub-centimeter clearances (foil tips, bowsprits)
4. Numerical stability (no NaN, infinity, negative area, or false positives)
5. Physical validation of all 6 detected incidents in naples_pr1.json
"""

import json
import math
import os
import unittest

from pipeline.contact_coalescer import (
    DEFAULT_KEEP_CLEAR_BORDER,
    coalesce_from_replay_dict,
    coalesce_virtual_contacts,
    compute_polygon_area,
    compute_polygon_intersection_area,
    test_sat_overlap,
    transform_local_to_world,
)


class TestSATAdversarialStress(unittest.TestCase):
    """Adversarial challenge test harness for 2D SAT collision detection."""

    def test_rapid_rotation_sweep_360_degrees(self):
        """Sweeps heading from 0° to 359° at 1° increments and validates rotational invariance."""
        # Fixed relative geometry: Boat B is offset laterally by 10.0m in Boat A's frame (overlapping by 4.83m)
        base_dist = 10.0
        ref_depth = None
        ref_area = None

        for deg in range(360):
            rad = math.radians(deg)
            # In navigation frame (0=North, 90=East):
            # Starboard vector (+u) is (cos(deg), -sin(deg))
            boat_a_pos = (100.0, 200.0)
            boat_b_pos = (
                boat_a_pos[0] + base_dist * math.cos(rad),
                boat_a_pos[1] - base_dist * math.sin(rad),
            )

            poly_a = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, boat_a_pos[0], boat_a_pos[1], deg)
            poly_b = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, boat_b_pos[0], boat_b_pos[1], deg)

            has_contact, depth = test_sat_overlap(poly_a, poly_b)
            area = compute_polygon_intersection_area(poly_a, poly_b)

            # Numerical stability: must never be NaN or infinite
            self.assertFalse(math.isnan(depth), f"NaN depth at {deg}°")
            self.assertFalse(math.isinf(depth), f"Inf depth at {deg}°")
            self.assertFalse(math.isnan(area), f"NaN area at {deg}°")
            self.assertFalse(math.isinf(area), f"Inf area at {deg}°")

            self.assertTrue(has_contact, f"Expected contact at {deg}°")
            self.assertGreater(depth, 0.0)
            self.assertGreater(area, 0.0)

            if ref_depth is None:
                ref_depth = depth
                ref_area = area
            else:
                self.assertAlmostEqual(depth, ref_depth, delta=0.05, msg=f"Depth variance at {deg}°")
                self.assertAlmostEqual(area, ref_area, delta=0.5, msg=f"Area variance at {deg}°")

    def test_rapid_rotation_sweep_separated_vessels_no_false_positives(self):
        """Sweeps heading 0° to 359° at 1° increments for clearly separated vessels (20m separation)."""
        sep_dist = 20.0  # Clearance 20m - 14.83m = 5.17m
        for deg in range(360):
            rad = math.radians(deg)
            boat_a_pos = (0.0, 0.0)
            boat_b_pos = (
                sep_dist * math.cos(rad),
                -sep_dist * math.sin(rad),
            )

            poly_a = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, boat_a_pos[0], boat_a_pos[1], deg)
            poly_b = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, boat_b_pos[0], boat_b_pos[1], deg)

            has_contact, depth = test_sat_overlap(poly_a, poly_b)
            area = compute_polygon_intersection_area(poly_a, poly_b)

            self.assertFalse(has_contact, f"False positive collision at {deg}°")
            self.assertEqual(depth, 0.0)
            self.assertEqual(area, 0.0)

    def test_glancing_touches_sub_centimeter_foil_clearances(self):
        """Tests glancing lateral touches at foil tips with sub-centimeter clearances."""
        # Keep clear border span is 14.830m (+/- 7.415m)
        exact_threshold = 14.830

        # Case 1: 1 cm clearance (separated)
        sep_1cm = exact_threshold + 0.010
        poly_a = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 0.0, 0.0, 0.0)
        poly_b_clear = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, sep_1cm, 0.0, 0.0)
        has_c, d = test_sat_overlap(poly_a, poly_b_clear)
        self.assertFalse(has_c)
        self.assertEqual(d, 0.0)
        self.assertEqual(compute_polygon_intersection_area(poly_a, poly_b_clear), 0.0)

        # Case 2: 1 mm clearance (separated)
        sep_1mm = exact_threshold + 0.001
        poly_b_1mm = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, sep_1mm, 0.0, 0.0)
        has_c, d = test_sat_overlap(poly_a, poly_b_1mm)
        self.assertFalse(has_c)
        self.assertEqual(d, 0.0)

        # Case 3: 1 mm penetration (contact)
        sep_overlap_1mm = exact_threshold - 0.001
        poly_b_touch = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, sep_overlap_1mm, 0.0, 0.0)
        has_c, d = test_sat_overlap(poly_a, poly_b_touch)
        self.assertTrue(has_c)
        self.assertGreater(d, 0.0)
        self.assertLessEqual(d, 0.01)

        # Case 4: 1 cm penetration (contact)
        sep_overlap_1cm = exact_threshold - 0.010
        poly_b_1cm = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, sep_overlap_1cm, 0.0, 0.0)
        has_c, d = test_sat_overlap(poly_a, poly_b_1cm)
        self.assertTrue(has_c)
        self.assertAlmostEqual(d, 0.010, places=3)
        self.assertGreater(compute_polygon_intersection_area(poly_a, poly_b_1cm), 0.0)

    def test_glancing_touches_sub_centimeter_bowsprit_clearances(self):
        """Tests glancing longitudinal head-on touches at bowsprit tips."""
        # Bowsprit reaches y = +12.963m. Two opposing boats (headings 0° and 180°):
        # Bow tips meet when longitudinal separation is 2 * 12.963 = 25.926m
        exact_threshold = 25.926

        # 5 mm separation
        sep_clear = exact_threshold + 0.005
        poly_a = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 0.0, 0.0, 0.0)
        poly_b_clear = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 0.0, sep_clear, 180.0)
        has_c, d = test_sat_overlap(poly_a, poly_b_clear)
        self.assertFalse(has_c)
        self.assertEqual(d, 0.0)

        # 5 mm overlap
        sep_touch = exact_threshold - 0.005
        poly_b_touch = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 0.0, sep_touch, 180.0)
        has_c, d = test_sat_overlap(poly_a, poly_b_touch)
        self.assertTrue(has_c)
        self.assertGreater(d, 0.0)
        self.assertAlmostEqual(d, 0.005, places=3)
        self.assertGreater(compute_polygon_intersection_area(poly_a, poly_b_touch), 0.0)

    def test_high_velocity_40_knot_crossings(self):
        """Tests high-velocity crossings at 40 knots (20.58 m/s = 2.058 m/frame at 100ms).

        Verifies that rapid crossings are captured across multiple consecutive frames without tunneling.
        """
        speed_kts = 40.0
        speed_mps = speed_kts * 0.514444444  # 20.578 m/s
        dt_s = 0.1  # 100ms
        dist_per_frame = speed_mps * dt_s  # 2.058 m per frame

        # Scenario 1: Perpendicular T-bone crossing at 40 knots
        # Boat A is stationary at (0, 0) heading 0° (North)
        # Boat B crosses from West (-50m) to East (+50m) along y = 6.5m (through foil wing area) heading 90° (East)
        # Total distance = 100m, frames = 50 frames (5.0s)
        n_frames = 51
        t_start = 1000
        timestamps = [t_start + i * 100 for i in range(n_frames)]

        x_b_traj = [-50.0 + i * dist_per_frame for i in range(n_frames)]
        boats = {
            "A": {
                "id": "boat-a",
                "code": "BOAT_A",
                "x": [0.0] * n_frames,
                "y": [0.0] * n_frames,
                "heading": [0.0] * n_frames,
            },
            "B": {
                "id": "boat-b",
                "code": "BOAT_B",
                "x": x_b_traj,
                "y": [6.5] * n_frames,
                "heading": [90.0] * n_frames,
            },
        }

        incidents = coalesce_virtual_contacts(timestamps, boats)
        # There must be exactly 1 coalesced incident (no tunneling, no fragmentation)
        self.assertEqual(len(incidents), 1, "High velocity crossing must produce exactly 1 incident")
        inc = incidents[0]
        self.assertEqual(inc["boat_a"], "BOAT_A")
        self.assertEqual(inc["boat_b"], "BOAT_B")
        # Boat B Keep Clear Border is ~13.2m long and Boat A is ~14.8m wide
        # Total contact length is approximately 14.8 + 13.2 = 28m
        # At 2.058 m/frame, contact should span ~10-14 frames (~1000-1400 ms)
        self.assertGreaterEqual(inc["duration_ms"], 900, "Incident duration must be at least 900ms")
        self.assertLessEqual(inc["duration_ms"], 1800, "Incident duration must be at most 1800ms")
        self.assertGreater(inc["peak_overlap_m"], 5.0)
        self.assertGreater(inc["peak_overlap_m2"], 20.0)

    def test_head_on_40_knot_closing_velocity(self):
        """Two boats closing head-on at 40 knots relative speed (each at 20 knots)."""
        speed_rel_mps = 40.0 * 0.514444444  # 20.578 m/s
        dt_s = 0.1
        step_m = speed_rel_mps * dt_s  # 2.058 m per frame

        # Boat A heading 0° at origin, Boat B heading 180° moving South towards origin
        n_frames = 41
        timestamps = [10000 + i * 100 for i in range(n_frames)]
        y_b_traj = [40.0 - i * step_m for i in range(n_frames)]

        boats = {
            "FRA": {
                "id": "fra",
                "code": "FRA",
                "x": [0.0] * n_frames,
                "y": [0.0] * n_frames,
                "heading": [0.0] * n_frames,
            },
            "NZL": {
                "id": "nzl",
                "code": "NZL",
                "x": [0.0] * n_frames,
                "y": y_b_traj,
                "heading": [180.0] * n_frames,
            },
        }

        incidents = coalesce_virtual_contacts(timestamps, boats)
        self.assertEqual(len(incidents), 1)
        inc = incidents[0]
        # Combined longitudinal length = 13.178 + 13.178 = 26.356m
        # Number of frames = 26.356 / 2.058 ~= 12 frames
        self.assertGreaterEqual(inc["duration_ms"], 1000)
        self.assertLessEqual(inc["duration_ms"], 1500)
        self.assertGreater(inc["peak_overlap_m"], 10.0)

    def test_numerical_stability_edge_cases(self):
        """Verifies no NaN, infinity, or crash across degenerate cases."""
        # 1. Identical coincident polygons (exact same position and heading)
        poly_same_1 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 50.0, -100.0, 37.5)
        poly_same_2 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 50.0, -100.0, 37.5)

        has_c, d = test_sat_overlap(poly_same_1, poly_same_2)
        self.assertTrue(has_c)
        self.assertFalse(math.isnan(d))
        self.assertFalse(math.isinf(d))
        self.assertGreater(d, 0.0)

        area = compute_polygon_intersection_area(poly_same_1, poly_same_2)
        full_area = compute_polygon_area(poly_same_1)
        self.assertFalse(math.isnan(area))
        self.assertFalse(math.isinf(area))
        self.assertAlmostEqual(area, full_area, delta=0.1)

        # 2. Large coordinate values (10^5 metres)
        poly_large_1 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 500000.0, 500000.0, 120.0)
        poly_large_2 = transform_local_to_world(DEFAULT_KEEP_CLEAR_BORDER, 500010.0, 500000.0, 120.0)
        has_c, d = test_sat_overlap(poly_large_1, poly_large_2)
        self.assertTrue(has_c)
        self.assertFalse(math.isnan(d))

        # 3. Degenerate empty or single-point polygons
        self.assertFalse(test_sat_overlap([], [])[0])
        self.assertFalse(test_sat_overlap([(0.0, 0.0)], [(1.0, 1.0)])[0])
        self.assertEqual(compute_polygon_intersection_area([], []), 0.0)
        self.assertEqual(compute_polygon_area([(0.0, 0.0), (1.0, 1.0)]), 0.0)

    def test_naples_pr1_incident_ground_truth_validation(self):
        """Validates that all 6 detected incidents in naples_pr1.json are physically genuine."""
        replay_path = "public/data/replays/naples_pr1.json"
        if not os.path.exists(replay_path):
            self.skipTest("public/data/replays/naples_pr1.json is excluded from git; skipping Naples PR1 ground-truth check")

        with open(replay_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        incidents = data.get("virtual_contact_incidents", [])
        self.assertEqual(len(incidents), 6, f"Expected exactly 6 incidents in naples_pr1.json, found {len(incidents)}")

        timestamps = data["telemetry"]["timestamps"]
        boats = data["telemetry"]["boats"]

        kc_border = data.get("safety_borders", {}).get("keep_clear_border") or DEFAULT_KEEP_CLEAR_BORDER
        kc_coords = [(pt["x"], pt["y"]) if isinstance(pt, dict) else (pt[0], pt[1]) for pt in kc_border]

        # Verify each of the 6 incidents in detail
        expected_incidents = [
            ("ITA B", "GBR G", 1790078886600),
            ("GBR G", "SUI", 1790079006600),
            ("GBR G", "GBR B", 1790079088400),
            ("NZL B", "GBR B", 1790079089300),
            ("NZL B", "SUI", 1790079571100),
            ("USA", "ITA G", 1790080168100),
        ]

        found_pairs = []
        for inc in incidents:
            pair = tuple(sorted((inc["boat_a"], inc["boat_b"])))
            found_pairs.append((*pair, inc["start_ms"]))

            # Verify boat IDs and telemetry presence
            aid_a = inc.get("boat_a_id")
            aid_b = inc.get("boat_b_id")
            self.assertIn(aid_a, boats, f"Missing boat {aid_a} in telemetry")
            self.assertIn(aid_b, boats, f"Missing boat {aid_b} in telemetry")

            # Verify that peak frame exhibits valid SAT contact and matching metrics
            start_f = inc["start_frame_idx"]
            end_f = inc["end_frame_idx"]
            self.assertGreaterEqual(end_f, start_f)

            # Check every frame of the incident
            for f_idx in range(start_f, end_f + 1):
                t_frame = timestamps[f_idx]
                xa = boats[aid_a]["x"][f_idx]
                ya = boats[aid_a]["y"][f_idx]
                hdg_a = boats[aid_a]["heading"][f_idx]

                xb = boats[aid_b]["x"][f_idx]
                yb = boats[aid_b]["y"][f_idx]
                hdg_b = boats[aid_b]["heading"][f_idx]

                poly_a = transform_local_to_world(kc_coords, xa, ya, hdg_a)
                poly_b = transform_local_to_world(kc_coords, xb, yb, hdg_b)

                has_c, depth = test_sat_overlap(poly_a, poly_b)
                self.assertTrue(
                    has_c,
                    f"Frame {f_idx} (t={t_frame}) of incident {inc['id']} must exhibit physical SAT contact",
                )
                self.assertGreater(depth, 0.0)

            # Check boundary frames (start - 1 and end + 1)
            if start_f > 0:
                prev_f = start_f - 1
                poly_a_prev = transform_local_to_world(
                    kc_coords,
                    boats[aid_a]["x"][prev_f],
                    boats[aid_a]["y"][prev_f],
                    boats[aid_a]["heading"][prev_f],
                )
                poly_b_prev = transform_local_to_world(
                    kc_coords,
                    boats[aid_b]["x"][prev_f],
                    boats[aid_b]["y"][prev_f],
                    boats[aid_b]["heading"][prev_f],
                )
                has_c_prev, _ = test_sat_overlap(poly_a_prev, poly_b_prev)
                self.assertFalse(
                    has_c_prev,
                    f"Frame before start ({prev_f}) for incident {inc['id']} must NOT have contact",
                )

            if end_f + 1 < len(timestamps):
                next_f = end_f + 1
                poly_a_next = transform_local_to_world(
                    kc_coords,
                    boats[aid_a]["x"][next_f],
                    boats[aid_a]["y"][next_f],
                    boats[aid_a]["heading"][next_f],
                )
                poly_b_next = transform_local_to_world(
                    kc_coords,
                    boats[aid_b]["x"][next_f],
                    boats[aid_b]["y"][next_f],
                    boats[aid_b]["heading"][next_f],
                )
                has_c_next, _ = test_sat_overlap(poly_a_next, poly_b_next)
                self.assertFalse(
                    has_c_next,
                    f"Frame after end ({next_f}) for incident {inc['id']} must NOT have contact",
                )

        canonical_expected = [(*tuple(sorted((a, b))), ts) for a, b, ts in expected_incidents]
        self.assertEqual(sorted(found_pairs), sorted(canonical_expected))

    def test_recomputation_from_scratch_matches_replay_exactly(self):
        """Re-runs coalesce_from_replay_dict directly on naples_pr1.json and verifies 100% equivalence."""
        replay_path = "public/data/replays/naples_pr1.json"
        if not os.path.exists(replay_path):
            replay_path = "tests/fixtures/synthetic_replay.json"
        if not os.path.exists(replay_path):
            self.skipTest(f"Replay not found at {replay_path}")

        with open(replay_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        existing_incidents = data.get("virtual_contact_incidents", [])
        recomputed = coalesce_from_replay_dict(data)

        self.assertEqual(len(recomputed), len(existing_incidents))
        for exp, actual in zip(existing_incidents, recomputed):
            self.assertEqual(exp["id"], actual["id"])
            self.assertEqual(exp["boat_a"], actual["boat_a"])
            self.assertEqual(exp["boat_b"], actual["boat_b"])
            self.assertEqual(exp["start_ms"], actual["start_ms"])
            self.assertEqual(exp["end_ms"], actual["end_ms"])
            self.assertEqual(exp["duration_ms"], actual["duration_ms"])
            self.assertEqual(exp["peak_ms"], actual["peak_ms"])
            self.assertAlmostEqual(exp["min_center_distance_m"], actual["min_center_distance_m"], places=2)
            self.assertAlmostEqual(exp["peak_overlap_m"], actual["peak_overlap_m"], places=2)
            self.assertAlmostEqual(exp["peak_overlap_m2"], actual["peak_overlap_m2"], places=2)

    def test_run_all_stress_harness_metrics(self):
        """Executes full benchmark suite from adversarial_sat_stress_harness and prints summary metrics."""
        from tests.adversarial_sat_stress_harness import (
            run_rotation_sweep_metrics,
            run_glancing_touch_sweep,
            run_velocity_sweep,
            run_naples_incident_validation,
        )
        run_rotation_sweep_metrics()
        run_glancing_touch_sweep()
        run_velocity_sweep()
        if os.path.exists("public/data/replays/naples_pr1.json"):
            run_naples_incident_validation()


if __name__ == "__main__":
    unittest.main()
