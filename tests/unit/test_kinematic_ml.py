"""Unit tests for kinematic ML features, turn detection, and match race simulator."""
import unittest
from pathlib import Path

import numpy as np

from pipeline.kinematic_ml.features import validate_window_support, detect_kinematic_turns_no_speed_gate
from pipeline.kinematic_ml.models import PhaseDurationModel, NonFinishModel
from pipeline.kinematic_ml.simulator import simulate_kinematic_race
from pipeline.kinematic_ml.course_lvc import COURSE_PRESETS, BARCELONA_2024_LVC


class KinematicMLTests(unittest.TestCase):
    def test_window_support_validation(self):
        # 1. Valid window with 10Hz frames
        start_ms = 10_000
        end_ms = 70_000
        # Frames every 100ms from 9000 to 71000
        ts = list(range(9000, 71500, 100))
        res = validate_window_support(ts, start_ms, end_ms)
        self.assertTrue(res["valid"])
        self.assertFalse(res["dropout_exceeded"])
        self.assertLessEqual(res["max_gap_ms"], 100)
        self.assertGreaterEqual(res["pre_count"], 3)
        self.assertGreaterEqual(res["post_count"], 3)

        # 2. Window with dropout > 1200ms
        ts_dropout = [t for t in ts if not (20_000 < t < 22_000)]  # 2000ms gap
        res_drop = validate_window_support(ts_dropout, start_ms, end_ms)
        self.assertFalse(res_drop["valid"])
        self.assertTrue(res_drop["dropout_exceeded"])
        self.assertGreaterEqual(res_drop["max_gap_ms"], 1900)

    def test_speed_loss_independent_turn_detector(self):
        # Synthetic heading sequence: steady 045, then tack to 315 through 000 (TWD=000)
        # Rotation = -90 deg in 8 seconds
        heading_recs = []
        t = 10_000
        # 5 seconds steady on starboard tack (45 deg)
        for _ in range(50):
            heading_recs.append((t, 45.0))
            t += 100
        # 8 seconds rotating 45 -> 0 -> 315 (-90 deg)
        for step in range(80):
            h = (45.0 - (90.0 * (step / 79.0))) % 360.0
            heading_recs.append((t, h))
            t += 100
        # 5 seconds steady on port tack (315 deg)
        for _ in range(50):
            heading_recs.append((t, 315.0))
            t += 100

        twd_recs = [(10_000, 0.0), (30_000, 0.0)]
        turns = detect_kinematic_turns_no_speed_gate(heading_recs, twd_recs)
        self.assertGreaterEqual(len(turns), 1)
        self.assertEqual(turns[0]["turn_type"], "tack")
        self.assertGreaterEqual(abs(turns[0]["rotation_deg"]), 65.0)
        self.assertEqual(turns[0]["detection_contract"], "angular_rotation_only_no_speed_gate")

    def test_kinematic_race_simulation(self):
        sim = simulate_kinematic_race("ETNZ", "GB1", tws_kt=12.0, n_sims=500, seed=42)
        self.assertEqual(sim["schema_version"], "kinematic-race-sim-1")
        self.assertIn("win_probability_a", sim)
        self.assertIn("win_probability_b", sim)
        self.assertAlmostEqual(sim["win_probability_a"] + sim["win_probability_b"], 1.0, places=2)

        # Joint finisher conditioning
        jf = sim["joint_finisher_conditioning"]
        self.assertGreater(jf["both_finished_count"], 400)
        self.assertIsNotNone(jf["mean_delta_t_s"])
        self.assertIsNotNone(jf["p10_delta_t_s"])
        self.assertIsNotNone(jf["p90_delta_t_s"])

        # 7-component attribution
        attr = sim["attribution_7_component"]
        self.assertIn("pre_start_positioning_s", attr)
        self.assertIn("upwind_vmg_s", attr)
        self.assertIn("downwind_vmg_s", attr)
        self.assertIn("tack_execution_s", attr)
        self.assertIn("gybe_execution_s", attr)
        self.assertIn("boundary_avoidance_s", attr)
        self.assertIn("technical_reliability_advantage", attr)

        # Status breakdown
        self.assertIn("ETNZ", sim["status_breakdown"])
        self.assertIn("GB1", sim["status_breakdown"])
        for team in ("ETNZ", "GB1"):
            sb = sim["status_breakdown"][team]
            tot = sb["finished_rate"] + sb["dns_rate"] + sb["dnf_exogenous_rate"] + sb["ocs_dsq_rate"]
            self.assertAlmostEqual(tot, 1.0, places=3)

    def test_course_presets(self):
        self.assertIn("barcelona_2024_lvc", COURSE_PRESETS)
        self.assertIn("naples_2026_prelim", COURSE_PRESETS)
        self.assertEqual(BARCELONA_2024_LVC.venue, "Barcelona")


if __name__ == "__main__":
    unittest.main()
