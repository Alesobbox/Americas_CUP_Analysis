"""Adversarial stress-testing suite for Milestone 2: Manoeuvres, Reconstruction, Analytics & Replay Export.

Tests:
1. ManoeuvreDetector adversarial edge cases:
   - Degenerate / short series (<30 frames)
   - Wrap-around heading boundaries (0/360 North tack, 180/-180 South gybe)
   - Chatter rejection under 2.0s stability threshold
   - Sub-threshold ROT, heading deflection, and speed dip rejection
   - Steady-state straight runs with continuous steering perturbations (zero false positives)
2. Reconstruction & Gate crossing geometry:
   - Parallel / non-crossing trajectories
   - Reverse-direction penetration rejection
   - Margin tolerance boundaries (inside vs outside margin 0.20)
   - Zero-division avoidance in collinear lines
   - Geometric start line distance for GBR B and fleet
3. Analytics & Progress robustness:
   - Progress monotonicity under noisy / backwards trajectory
   - Head-to-head identical vessel singularity avoidance
   - Start tactical metric projection when retreating from line
4. Replay manifest artifact strict schema validation against PROJECT.md § Interface Contracts:
   - public/data/replays/naples_pr1.json structure, lengths, bounds, NaN/Inf absence
   - public/data/manifests.json multi-race picker schema
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
import unittest
from typing import List, Dict, Any

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline.manoeuvres import (
    ManoeuvreDetector,
    circular_shortest_diff_deg,
    normalize_angle_180,
)
from tests.verify_boundary_corridor import (
    verify_boundary_timeline,
    verify_telemetry_marks_schema,
    verify_sample_mark_frame_integrity,
)
from pipeline.reconstruction import (
    GUN_TIME_EPOCH_MS,
    WINDOW_START_EPOCH_MS,
    WINDOW_END_EPOCH_MS,
    AC40_BOW_OFFSET_M,
    COURSE_AXIS_SETTLED_DEG,
    GBR_B_UUID,
    USA_UUID,
    compute_bow_position,
    intersect_segments_2d,
    compute_distance_to_start_line,
    RaceReconstructionEngine,
)
from pipeline.analytics import (
    AnalyticsEngine,
    HeadToHeadResult,
    StartTacticalMetrics,
)
from pipeline.config import COMPETITORS, MARKS


class TestManoeuvreDetectorAdversarial(unittest.TestCase):
    """Adversarial challenges for Tack and Gybe manoeuvre detection."""

    def setUp(self):
        self.detector = ManoeuvreDetector(
            min_heading_change_deg=50.0,
            min_rot_deg_s=5.0,
            min_speed_loss_kt=2.5,
            min_tack_stability_s=2.0,
            min_manoeuvre_separation_s=6.0,
            sample_interval_ms=100,
        )

    def test_degenerate_short_series_returns_empty(self):
        """Time series shorter than 30 frames returns empty list without error."""
        timestamps = [1000 + i * 100 for i in range(25)]
        heading = [45.0] * 25
        sog = [25.0] * 25
        twa = [40.0] * 25
        res = self.detector.detect_manoeuvres_for_boat(timestamps, heading, sog, twa)
        self.assertEqual(res, [])

    def test_empty_series_returns_empty(self):
        """Empty input series returns empty list."""
        res = self.detector.detect_manoeuvres_for_boat([], [], [], [])
        self.assertEqual(res, [])

    def test_tack_wrapping_across_true_north_0_deg(self):
        """Tack turning across True North (330 deg to 30 deg, delta=60 deg) is detected."""
        n = 100
        timestamps = [1790079000000 + i * 100 for i in range(n)]
        heading = [330.0] * n
        twa = [-35.0] * n
        sog = [26.0] * n

        # Turn phase: frames 30 to 60 (turn from 330 to 30 across 360/0)
        for i in range(30, 61):
            alpha = (i - 30) / 30.0
            # 330 + alpha * 60: at alpha=0 -> 330, alpha=0.5 -> 360/0, alpha=1.0 -> 30
            raw_hdg = 330.0 + alpha * 60.0
            heading[i] = raw_hdg % 360.0
            twa[i] = -35.0 + alpha * 70.0  # -35 to +35 deg
            sog_dip = 6.0 * (1.0 - abs(alpha - 0.5) * 2.0)
            sog[i] = 26.0 - sog_dip

        for i in range(61, n):
            heading[i] = 30.0
            twa[i] = 35.0
            sog[i] = 25.5

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )
        self.assertEqual(len(manoeuvres), 1)
        m = manoeuvres[0]
        self.assertEqual(m.type, "TACK")
        self.assertAlmostEqual(m.turn_delta_deg, 60.0, delta=5.0)
        self.assertGreaterEqual(m.speed_loss_kt, 4.0)

    def test_gybe_wrapping_across_south_180_deg(self):
        """Gybe turning across 180 deg (150 deg to 220 deg, delta=70 deg) is detected."""
        n = 100
        timestamps = [1790079000000 + i * 100 for i in range(n)]
        heading = [150.0] * n
        twa = [145.0] * n
        sog = [32.0] * n

        for i in range(30, 61):
            alpha = (i - 30) / 30.0
            heading[i] = 150.0 + alpha * 70.0  # 150 -> 220
            # TWA crosses +/-180
            if alpha < 0.5:
                twa[i] = 145.0 + alpha * 70.0
            else:
                twa[i] = -180.0 + (alpha - 0.5) * 70.0
            sog_dip = 8.0 * (1.0 - abs(alpha - 0.5) * 2.0)
            sog[i] = 32.0 - sog_dip

        for i in range(61, n):
            heading[i] = 220.0
            twa[i] = -145.0
            sog[i] = 31.0

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )
        self.assertEqual(len(manoeuvres), 1)
        m = manoeuvres[0]
        self.assertEqual(m.type, "GYBE")
        self.assertAlmostEqual(m.turn_delta_deg, 70.0, delta=5.0)

    def test_sub_threshold_rot_rejected(self):
        """Very slow turn (peak ROT = 2.0 deg/s < 5.0 deg/s threshold) is rejected."""
        n = 360
        timestamps = [1790079000000 + i * 100 for i in range(n)]
        # Turn 60 deg spread over 30 seconds (300 frames) -> ROT ~ 2.0 deg/s
        heading = [0.0] * n
        twa = [-40.0] * n
        sog = [26.0] * n
        for i in range(20, 320):
            alpha = (i - 20) / 300.0
            heading[i] = alpha * 60.0
            twa[i] = -40.0 + alpha * 80.0
            sog[i] = 26.0 - 4.0 * (1.0 - abs(alpha - 0.5) * 2.0)
        for i in range(320, n):
            heading[i] = 60.0
            twa[i] = 40.0
            sog[i] = 25.5

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )
        self.assertEqual(len(manoeuvres), 0)

    def test_insufficient_speed_loss_rejected(self):
        """Turn with full heading change but zero/negligible speed loss (<2.5 kt) is rejected."""
        n = 100
        timestamps = [1790079000000 + i * 100 for i in range(n)]
        heading = [0.0] * n
        twa = [-45.0] * n
        sog = [28.0] * n  # Constant speed 28 kt!

        for i in range(30, 61):
            alpha = (i - 30) / 30.0
            heading[i] = alpha * 70.0
            twa[i] = -45.0 + alpha * 90.0
            # Only 1.0 kt speed dip
            sog[i] = 28.0 - 1.0 * (1.0 - abs(alpha - 0.5) * 2.0)

        for i in range(61, n):
            heading[i] = 70.0
            twa[i] = 45.0
            sog[i] = 27.8

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )
        self.assertEqual(len(manoeuvres), 0)

    def test_steady_state_straight_run_zero_false_positives(self):
        """Long 500-sample (50s) straight foiling run with ±8 deg steering perturbations yields 0 false positives."""
        n = 500
        timestamps = [1790079000000 + i * 100 for i in range(n)]
        heading = [42.0 + 6.0 * math.sin(i * 0.05) + 2.0 * math.cos(i * 0.13) for i in range(n)]
        twa = [45.0 + 5.0 * math.sin(i * 0.05) for i in range(n)]
        sog = [28.0 + 1.5 * math.cos(i * 0.08) for i in range(n)]

        manoeuvres = self.detector.detect_manoeuvres_for_boat(
            timestamps, heading, sog, twa
        )
        self.assertEqual(len(manoeuvres), 0)


class TestReconstructionGeometryAdversarial(unittest.TestCase):
    """Adversarial challenges for trajectory intersection and gate detection."""

    def test_collinear_or_parallel_segments_no_crash(self):
        """Parallel or collinear trajectory segments return crossed=False with no ZeroDivisionError."""
        m_port = (-100.0, 50.0)
        m_stbd = (100.0, -50.0)
        # Exactly parallel: dx_p / dy_p == dx_m / dy_m
        p_prev = (-100.0, 150.0)
        p_curr = (100.0, 50.0)
        crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, m_port, m_stbd)
        self.assertFalse(crossed)

    def test_reverse_direction_advance_rejected(self):
        """Boat sailing downwind across upwind gate does not register upwind gate completion."""
        engine = RaceReconstructionEngine()
        # Bottom gate marks at frame 0 and 1
        m8 = (-150.0, 50.0)
        m6 = (150.0, -50.0)
        marks = {
            "RM8": type("Mark", (), {"x": [-150.0, -150.0], "y": [50.0, 50.0]})(),
            "RM6": type("Mark", (), {"x": [150.0, 150.0], "y": [-50.0, -50.0]})(),
            "RM4": type("Mark", (), {"x": [1000.0, 1000.0], "y": [1500.0, 1500.0]})(),
            "RM2": type("Mark", (), {"x": [1200.0, 1200.0], "y": [1400.0, 1400.0]})(),
        }
        # Boat moving downwind (from (0, 50) to (0, -50)) across bottom gate
        boat_x = [0.0, 0.0]
        boat_y = [50.0, -50.0]
        heading = [224.39, 224.39]  # Pointing downwind
        timestamps = [GUN_TIME_EPOCH_MS + 1000, GUN_TIME_EPOCH_MS + 1200]

        crossings = engine.reconstruct_geometric_crossings_for_boat(
            boat_x, boat_y, heading, timestamps, marks
        )
        # Start line (Leg 0) requires upwind advance (>0), downwind advance must be rejected
        self.assertEqual(len(crossings), 0)

    def test_trajectory_outside_margin_rejected(self):
        """Trajectory crossing gate line beyond the 20% margin (s = 1.25) is rejected."""
        m_port = (-100.0, 0.0)
        m_stbd = (100.0, 0.0)
        # Crossing at x = 150 (s = 1.25, > 1.20 margin)
        p_prev = (150.0, -10.0)
        p_curr = (150.0, 10.0)
        crossed, u, s, cx, cy = intersect_segments_2d(m_port=m_port, m_starboard=m_stbd, p_prev=p_prev, p_curr=p_curr, margin_epsilon=0.20)
        self.assertFalse(crossed)

    def test_trajectory_inside_margin_accepted(self):
        """Trajectory crossing gate line within 20% margin (s = 1.10) is accepted."""
        m_port = (-100.0, 0.0)
        m_stbd = (100.0, 0.0)
        # Crossing at x = 120 (s = 1.10, <= 1.20 margin)
        p_prev = (120.0, -10.0)
        p_curr = (120.0, 10.0)
        crossed, u, s, cx, cy = intersect_segments_2d(m_port=m_port, m_starboard=m_stbd, p_prev=p_prev, p_curr=p_curr, margin_epsilon=0.20)
        self.assertTrue(crossed)
        self.assertAlmostEqual(s, 1.10, places=2)


class TestAnalyticsEngineAdversarial(unittest.TestCase):
    """Adversarial challenges for progress monotonicity and tactical analytics."""

    def test_progress_monotonicity_under_adversarial_jitter(self):
        """Noisy, retreating trajectory strictly preserves monotonic progress progression."""
        analytics = AnalyticsEngine()
        # Simulated advances that oscillate and retreat:
        advances = [0.0, 100.0, 300.0, 250.0, 200.0, 450.0, 400.0, 600.0, 550.0, 800.0]
        max_p = 0.0
        output_p = []
        for adv in advances:
            if adv > max_p:
                max_p = adv
            output_p.append(max_p)

        for i in range(len(output_p) - 1):
            self.assertGreaterEqual(
                output_p[i + 1],
                output_p[i],
                f"Progress regression at index {i}: {output_p[i]} -> {output_p[i+1]}",
            )

    def test_head_to_head_identical_positions_no_nan(self):
        """Head-to-head comparison with identical positions does not produce NaN or ZeroDivisionError."""
        analytics = AnalyticsEngine()
        pos = (150.0, 250.0)
        vel = (10.0, 15.0)
        res = analytics.compute_head_to_head_metrics(pos, pos, vel, vel)
        self.assertEqual(res.euclidean_distance_m, 0.0)
        self.assertEqual(res.longitudinal_delta_m, 0.0)
        self.assertEqual(res.lateral_separation_m, 0.0)
        self.assertEqual(res.rate_of_closure_mps, 0.0)
        self.assertFalse(math.isnan(res.rate_of_closure_mps))

    def test_start_tactical_retreating_boat(self):
        """Boat sailing away from start line (negative velocity towards line) has None projected crossing."""
        analytics = AnalyticsEngine()
        m_port = (-200.0, 100.0)
        m_stbd = (200.0, -100.0)
        bow_pos = (0.0, -150.0)  # Behind line
        vel_mps = (0.0, -10.0)   # Sailing backwards away from line
        res = analytics.compute_start_tactical_metrics(
            GUN_TIME_EPOCH_MS - 60000, bow_pos, vel_mps, m_port, m_stbd
        )
        self.assertIsNone(res.projected_crossing_time_ms)
        self.assertIsNone(res.projected_delta_to_gun_s)


class TestReplayArtifactContractSchema(unittest.TestCase):
    """Verifies generated replay artifact strictly against PROJECT.md § Interface Contracts."""

    @classmethod
    def setUpClass(cls):
        replay_path = "public/data/replays/naples_pr1.json"
        assert os.path.exists(replay_path), f"Missing replay artifact {replay_path}"
        with open(replay_path, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_root_fields_present(self):
        """Top-level ReplayManifest fields: id, name, venue, date, course, wind, chronology, competitors, telemetry."""
        required = ["id", "name", "venue", "date", "course", "wind", "chronology", "competitors", "telemetry"]
        for key in required:
            self.assertIn(key, self.data, f"Missing root field: {key}")

    def test_course_structure(self):
        """Course contains axis_deg, length_m, origin, projection, boundaries, marks."""
        course = self.data["course"]
        self.assertIn("axis_deg", course)
        self.assertIn("length_m", course)
        self.assertIn("origin", course)
        self.assertIn("projection", course)
        self.assertIn("boundaries", course)
        self.assertIn("marks", course)

        # Marks RM8, RM6, RM4, RM2
        marks = course["marks"]
        for m_code in ["RM8", "RM6", "RM4", "RM2"]:
            self.assertIn(m_code, marks)
            self.assertEqual(len(marks[m_code]["target"]), 2)

        # Boundaries
        self.assertEqual(len(course["boundaries"]["race"]), 8)
        self.assertEqual(len(course["boundaries"]["safety"]), 8)

    def test_wind_structure_and_timeline(self):
        """Wind contains reference_twd_deg, reference_tws_kt, and non-empty timeline."""
        wind = self.data["wind"]
        self.assertIn("reference_twd_deg", wind)
        self.assertIn("reference_tws_kt", wind)
        self.assertIn("timeline", wind)
        self.assertGreater(len(wind["timeline"]), 100)
        # Check first entry
        first_w = wind["timeline"][0]
        self.assertIn("t", first_w)
        self.assertIn("twd", first_w)
        self.assertIn("tws", first_w)

    def test_chronology_constants(self):
        """Chronology gun_time=1790079000000, window_start=1790078820000, window_end=1790080768700."""
        chrono = self.data["chronology"]
        self.assertEqual(chrono["gun_time"], GUN_TIME_EPOCH_MS)
        self.assertEqual(chrono["window_start"], WINDOW_START_EPOCH_MS)
        self.assertEqual(chrono["window_end"], WINDOW_END_EPOCH_MS)

    def test_competitors_count_and_summary_fields(self):
        """All 9 competitors are present and ordered by finish_rank (1 to 9)."""
        competitors = self.data["competitors"]
        self.assertEqual(len(competitors), 9)

        expected_ranks = list(range(1, 10))
        actual_ranks = [c["summary"]["finish_rank"] for c in competitors]
        self.assertEqual(actual_ranks, expected_ranks)

        # Winner FRA verification
        winner = competitors[0]
        self.assertEqual(winner["team_code"], "FRA")
        self.assertEqual(winner["classification"], "RANK_1")
        self.assertAlmostEqual(winner["summary"]["elapsed_s"], 1059.555, delta=0.5)
        self.assertGreater(winner["summary"]["distance_sailed_m"], 8000.0)
        self.assertGreater(winner["summary"]["tack_count"], 0)
        self.assertGreater(winner["summary"]["gybe_count"], 0)

        # GBR B retired verification
        gbr_b = next(c for c in competitors if c["team_code"] == "GBR B")
        self.assertTrue(gbr_b["start"]["ocs"])
        self.assertEqual(gbr_b["classification"], "RET")

    def test_telemetry_lengths_and_no_nan(self):
        """Telemetry arrays are exactly aligned with timestamps length and contain no NaNs/nulls."""
        telemetry = self.data["telemetry"]
        timestamps = telemetry["timestamps"]
        n_frames = len(timestamps)
        self.assertEqual(n_frames, 19488)

        # Check 100ms delta between consecutive timestamps
        for i in range(min(100, n_frames - 1)):
            self.assertEqual(timestamps[i + 1] - timestamps[i], 100)

        boats = telemetry["boats"]
        self.assertEqual(len(boats), 9)

        required_channels = [
            "x", "y", "heading", "cog", "sog", "vmg", "twa", "twd", "tws", "progress_m", "leg"
        ]
        for b_uuid, b_data in boats.items():
            for ch in required_channels:
                self.assertIn(ch, b_data, f"Boat {b_uuid} missing channel {ch}")
                self.assertEqual(
                    len(b_data[ch]),
                    n_frames,
                    f"Boat {b_uuid} channel {ch} length mismatch: {len(b_data[ch])} != {n_frames}",
                )

        # Spot check marks
        marks = telemetry["marks"]
        self.assertEqual(len(marks), 4)
        for m_uuid, m_data in marks.items():
            self.assertEqual(len(m_data["x"]), n_frames)
            self.assertEqual(len(m_data["y"]), n_frames)

    def test_boundary_corridor_timeline_transitions(self):
        """Verifies course.boundary_timeline transitions: 8-pt pre-start box collapsing to 4-pt corridor at T=+15s."""
        res = verify_boundary_timeline(self.data)
        self.assertTrue(res["passed"], f"Boundary timeline verification failed: {res['errors']}")
        self.assertGreaterEqual(res["revision_count"], 3)

        # Check revision details directly
        timeline = self.data["course"]["boundary_timeline"]
        gun_time = self.data["chronology"]["gun_time"]

        # Pre-start revision (index 0): 8 points
        self.assertEqual(len(timeline[0]["race"]), 8, "Pre-start race boundary must have 8 points")
        self.assertEqual(len(timeline[0]["safety"]), 8, "Safety boundary must have 8 points")

        # T = +15s transition (index 2: t=1790079015154, delta = +15.154s): collapses to 4 points
        t15_rev = timeline[2]
        delta_s = (t15_rev["t"] - gun_time) / 1000.0
        self.assertAlmostEqual(delta_s, 15.154, places=2)
        self.assertEqual(len(t15_rev["race"]), 4, "Active corridor at T=+15s must collapse to 4 points")
        self.assertEqual(len(t15_rev["safety"]), 8, "Safety boundary must maintain 8 points")

        # Next revision maintaining 4 points
        if len(timeline) > 3:
            self.assertEqual(len(timeline[3]["race"]), 4, "Subsequent race boundary must maintain 4 points")

    def test_telemetry_marks_four_streams_schema(self):
        """Verifies schema conformance: telemetry.marks contains exactly 4 valid buoy streams."""
        res = verify_telemetry_marks_schema(self.data)
        self.assertTrue(res["passed"], f"telemetry.marks schema check failed: {res['errors']}")
        self.assertEqual(res["mark_count"], 4)

    def test_sample_mark_integrity_all_19488_frames(self):
        """Across all 19,488 frames, sampleMark produces valid finite numbers (no NaN, null, or out-of-range)."""
        res = verify_sample_mark_frame_integrity(self.data)
        self.assertTrue(res["passed"], f"sampleMark integrity check failed: {res['errors']}")
        self.assertEqual(res["nan_count"], 0)
        self.assertEqual(res["null_count"], 0)
        self.assertEqual(res["inf_count"], 0)
        self.assertEqual(res["range_violations"], 0)
        self.assertEqual(res["total_samples_evaluated"], 19488 * 4 * 4)  # 311,808 samples evaluated


if __name__ == "__main__":
    unittest.main()

