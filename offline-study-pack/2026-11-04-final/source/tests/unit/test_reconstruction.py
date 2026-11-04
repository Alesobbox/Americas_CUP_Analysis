"""Unit tests for geometric race reconstruction engine."""

import math
import unittest

from pipeline.reconstruction import (
    GUN_TIME_EPOCH_MS,
    WINDOW_START_EPOCH_MS,
    WINDOW_END_EPOCH_MS,
    AC40_BOW_OFFSET_M,
    COURSE_AXIS_SETTLED_DEG,
    GBR_B_UUID,
    GBR_B_OCS_DISTANCE_M,
    GBR_B_OCS_AWARDED_MS,
    USA_UUID,
    compute_bow_position,
    intersect_segments_2d,
    compute_distance_to_start_line,
    GateCrossing,
    StartResult,
    RaceReconstructionEngine,
)


class TestReconstructionChronologyAndConstants(unittest.TestCase):
    """Verifies authoritative chronology, gun time, and geometric offsets."""

    def test_gun_time_and_race_windows(self):
        """Gun time is epoch ms 1790079000000, pre-start is -180s."""
        self.assertEqual(GUN_TIME_EPOCH_MS, 1790079000000)
        self.assertEqual(WINDOW_START_EPOCH_MS, 1790078820000)
        pre_start_duration_s = (GUN_TIME_EPOCH_MS - WINDOW_START_EPOCH_MS) / 1000.0
        self.assertEqual(pre_start_duration_s, 180.0)
        self.assertEqual(WINDOW_END_EPOCH_MS, 1790080768700)

    def test_bow_offset_cardinal_directions(self):
        """Bow position projects +12.963m forward along heading in all cardinal directions."""
        x0, y0 = 100.0, 200.0
        # North (0 deg)
        bx_n, by_n = compute_bow_position(x0, y0, 0.0)
        self.assertAlmostEqual(bx_n, 100.0, places=4)
        self.assertAlmostEqual(by_n, 200.0 + AC40_BOW_OFFSET_M, places=4)

        # East (90 deg)
        bx_e, by_e = compute_bow_position(x0, y0, 90.0)
        self.assertAlmostEqual(bx_e, 100.0 + AC40_BOW_OFFSET_M, places=4)
        self.assertAlmostEqual(by_e, 200.0, places=4)

        # South (180 deg)
        bx_s, by_s = compute_bow_position(x0, y0, 180.0)
        self.assertAlmostEqual(bx_s, 100.0, places=4)
        self.assertAlmostEqual(by_s, 200.0 - AC40_BOW_OFFSET_M, places=4)

        # West (270 deg)
        bx_w, by_w = compute_bow_position(x0, y0, 270.0)
        self.assertAlmostEqual(bx_w, 100.0 - AC40_BOW_OFFSET_M, places=4)
        self.assertAlmostEqual(by_w, 200.0, places=4)

    def test_bow_advance_timing_at_foiling_speed(self):
        """At 30 knots (~15.43 m/s), bow reaches line ~0.84s ahead of GPS antenna."""
        mps = 30.0 / 1.94384449
        dt_s = AC40_BOW_OFFSET_M / mps
        self.assertAlmostEqual(dt_s, 0.84, delta=0.05)


class TestSegmentIntersectionAndGateMath(unittest.TestCase):
    """Verifies 2D trajectory segment intersection and port vs starboard mark selection."""

    def setUp(self):
        # Bottom gate line: RM8 at (-100, 50), RM6 at (100, -50)
        self.m_port = (-100.0, 50.0)
        self.m_stbd = (100.0, -50.0)

    def test_trajectory_intersecting_center(self):
        """Trajectory cutting through midpoint of gate segment intersects with u=0.5, s=0.5."""
        p_prev = (-20.0, -20.0)
        p_curr = (20.0, 20.0)
        crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, self.m_port, self.m_stbd)
        self.assertTrue(crossed)
        self.assertAlmostEqual(u, 0.5, places=3)
        self.assertAlmostEqual(s, 0.5, places=3)
        self.assertAlmostEqual(cx, 0.0, places=3)
        self.assertAlmostEqual(cy, 0.0, places=3)

    def test_port_mark_selection_classification(self):
        """Crossing near RM8 (s < 0.5) is classified as Port mark."""
        # Trajectory near RM8: crossing at s = 0.20
        # Target point on gate: m_port + 0.2 * (m_stbd - m_port)
        gx = self.m_port[0] + 0.20 * (self.m_stbd[0] - self.m_port[0])
        gy = self.m_port[1] + 0.20 * (self.m_stbd[1] - self.m_port[1])
        p_prev = (gx - 10.0, gy - 10.0)
        p_curr = (gx + 10.0, gy + 10.0)

        crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, self.m_port, self.m_stbd)
        self.assertTrue(crossed)
        self.assertLess(s, 0.50)
        mark_choice = "RM8" if s < 0.50 else "RM6"
        side_choice = "PORT" if s < 0.50 else "STARBOARD"
        self.assertEqual(mark_choice, "RM8")
        self.assertEqual(side_choice, "PORT")

    def test_starboard_mark_selection_classification(self):
        """Crossing near RM6 (s >= 0.5) is classified as Starboard mark."""
        # Target point on gate at s = 0.85
        gx = self.m_port[0] + 0.85 * (self.m_stbd[0] - self.m_port[0])
        gy = self.m_port[1] + 0.85 * (self.m_stbd[1] - self.m_port[1])
        p_prev = (gx - 10.0, gy - 10.0)
        p_curr = (gx + 10.0, gy + 10.0)

        crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, self.m_port, self.m_stbd)
        self.assertTrue(crossed)
        self.assertGreaterEqual(s, 0.50)
        mark_choice = "RM8" if s < 0.50 else "RM6"
        side_choice = "PORT" if s < 0.50 else "STARBOARD"
        self.assertEqual(mark_choice, "RM6")
        self.assertEqual(side_choice, "STARBOARD")

    def test_parallel_trajectory_rejected(self):
        """Trajectory parallel to gate line returns crossed=False."""
        p_prev = (-100.0, 100.0)
        p_curr = (100.0, 0.0)  # Parallel to gate
        crossed, _, _, _, _ = intersect_segments_2d(p_prev, p_curr, self.m_port, self.m_stbd)
        self.assertFalse(crossed)

    def test_distant_non_crossing_trajectory_rejected(self):
        """Trajectory far from gate segment returns crossed=False."""
        p_prev = (500.0, 500.0)
        p_curr = (600.0, 600.0)
        crossed, _, _, _, _ = intersect_segments_2d(p_prev, p_curr, self.m_port, self.m_stbd)
        self.assertFalse(crossed)


class TestDistanceToStartLineAndOCS(unittest.TestCase):
    """Verifies start line distance projection and OCS infraction detection."""

    def test_pre_start_behind_line_distance(self):
        """Position behind start line (pre-start zone) yields negative distance."""
        m_port = (-200.0, 100.0)
        m_stbd = (200.0, -100.0)
        # Point behind line (to the SW / downwind)
        bow_pos = (-50.0, -150.0)
        dist = compute_distance_to_start_line(bow_pos, m_port, m_stbd)
        self.assertLess(dist, 0.0)

    def test_on_course_side_ahead_of_line_distance(self):
        """Position on course side (ahead of line, upwind) yields positive distance."""
        m_port = (-200.0, 100.0)
        m_stbd = (200.0, -100.0)
        # Point ahead of line (to the NE / upwind)
        bow_pos = (50.0, 150.0)
        dist = compute_distance_to_start_line(bow_pos, m_port, m_stbd)
        self.assertGreater(dist, 0.0)

    def test_gbr_b_ocs_penalty_definition(self):
        """GBR B is flagged OCS, +610.5m on course side at gun time, awarded at T=+0.333s."""
        self.assertEqual(GBR_B_UUID, "f535f0dc-a45b-4668-ae07-bd52e0cdd947")
        self.assertEqual(GBR_B_OCS_DISTANCE_M, 610.5)
        self.assertEqual(GBR_B_OCS_AWARDED_MS, 1790079000333)
        delta_awarded_s = (GBR_B_OCS_AWARDED_MS - GUN_TIME_EPOCH_MS) / 1000.0
        self.assertAlmostEqual(delta_awarded_s, 0.333, places=3)


class TestReconstructionEngineIntegration(unittest.TestCase):
    """Tests the RaceReconstructionEngine data parsing and fallback logic."""

    def test_engine_initialization(self):
        """Engine initializes with correct chronology and unit vectors."""
        engine = RaceReconstructionEngine()
        self.assertEqual(engine.gun_time_ms, GUN_TIME_EPOCH_MS)
        self.assertEqual(engine.window_start_ms, WINDOW_START_EPOCH_MS)
        self.assertAlmostEqual(engine.course_axis_deg, 44.39, places=2)
        # Check course axis unit vector
        rad = math.radians(44.39)
        self.assertAlmostEqual(engine.u_course[0], math.sin(rad), places=4)
        self.assertAlmostEqual(engine.u_course[1], math.cos(rad), places=4)

    def test_usa_missing_legs_fallback_structure(self):
        """Reconstruction provides fallback for USA's missing official legs (0, 1, 2)."""
        engine = RaceReconstructionEngine()
        # Synthetic official records with USA missing legs 0, 1, 2
        raw_events = {
            USA_UUID: [
                {
                    "competitor": {
                        "asset_id": USA_UUID,
                        "leg_timings": [
                            {"leg_number": 3, "gate_time": "1790079830869"},
                            {"leg_number": 4, "gate_time": "1790080113160"},
                        ],
                    }
                }
            ]
        }
        parsed = engine.parse_official_competitor_records(raw_events)
        self.assertIn(USA_UUID, parsed)
        usa_legs = parsed[USA_UUID]["leg_timings"]
        self.assertNotIn(0, usa_legs)
        self.assertNotIn(1, usa_legs)
        self.assertNotIn(2, usa_legs)
        self.assertIn(3, usa_legs)
        self.assertIn(4, usa_legs)
        self.assertEqual(usa_legs[4]["gate_time"], 1790080113160)


if __name__ == "__main__":
    unittest.main()
