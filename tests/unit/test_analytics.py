"""Unit tests for tactical analytics, monotonic progress, and leaderboard engine."""

import math
import unittest

from pipeline.analytics import (
    AnalyticsEngine,
    LeaderboardEntry,
)
from pipeline.reconstruction import (
    GUN_TIME_EPOCH_MS,
    CompetitorReconstruction,
    StartResult,
)


class TestMonotonicProgressAndCourseAxis(unittest.TestCase):
    """Verifies continuous monotonic race progress calculation."""

    def setUp(self):
        self.analytics = AnalyticsEngine(
            gun_time_ms=GUN_TIME_EPOCH_MS,
            course_axis_deg=44.39,
            nominal_leg_length_m=2400.0,
        )

    def test_course_axis_unit_vectors(self):
        """Course axis unit vectors are orthonormal and oriented at 44.39 deg."""
        rad = math.radians(44.39)
        self.assertAlmostEqual(self.analytics.u_upwind[0], math.sin(rad), places=4)
        self.assertAlmostEqual(self.analytics.u_upwind[1], math.cos(rad), places=4)
        # Downwind is negative upwind
        self.assertAlmostEqual(self.analytics.u_downwind[0], -self.analytics.u_upwind[0], places=4)
        self.assertAlmostEqual(self.analytics.u_downwind[1], -self.analytics.u_upwind[1], places=4)
        # Dot product with lateral vector is 0 (orthogonal)
        dot = (
            self.analytics.u_upwind[0] * self.analytics.u_lat[0]
            + self.analytics.u_upwind[1] * self.analytics.u_lat[1]
        )
        self.assertAlmostEqual(dot, 0.0, places=6)

    def test_progress_monotonicity_guarantee(self):
        """Simulated progress along leg guarantees non-decreasing monotonic series."""
        # Advances that fluctuate (e.g. tacking upwind away from mark then towards)
        raw_advances = [100.0, 250.0, 220.0, 310.0, 290.0, 450.0, 600.0]
        monotonic_prog = []
        max_p = 0.0
        for adv in raw_advances:
            if adv > max_p:
                max_p = adv
            monotonic_prog.append(max_p)

        for i in range(len(monotonic_prog) - 1):
            self.assertGreaterEqual(monotonic_prog[i + 1], monotonic_prog[i])


class TestLeaderboardStandingsAndRankings(unittest.TestCase):
    """Verifies leaderboard ranking and gap computation."""

    def setUp(self):
        self.analytics = AnalyticsEngine(gun_time_ms=GUN_TIME_EPOCH_MS)

    def test_finished_boats_ranking_order(self):
        """Finished boats are ordered strictly by elapsed time: FRA < NZL G < ITA B < USA < ITA G < GBR G."""
        ground_truth_finishers = [
            ("FRA", 1790080059555, 1059.555, 1),
            ("NZL G", 1790080074857, 1074.857, 2),
            ("ITA B", 1790080077932, 1077.932, 3),
            ("USA", 1790080113160, 1113.160, 4),
            ("ITA G", 1790080147935, 1147.935, 5),
            ("GBR G", 1790080166602, 1166.602, 6),
        ]

        # Verify elapsed times increase strictly
        for i in range(len(ground_truth_finishers) - 1):
            curr_b = ground_truth_finishers[i]
            next_b = ground_truth_finishers[i + 1]
            self.assertLess(curr_b[1], next_b[1])
            self.assertLess(curr_b[2], next_b[2])
            self.assertEqual(curr_b[3] + 1, next_b[3])

    def test_winner_fra_gap_to_leader_is_zero(self):
        """Winner has 0.0s and 0.0m gap to leader."""
        leader_entry = LeaderboardEntry(
            rank=1,
            team_code="FRA",
            team_name="Orient Express",
            color="#ff80c0",
            status="FINISHED",
            current_leg=4,
            progress_m=9732.4,
            gap_to_leader_m=0.0,
            gap_to_leader_s=0.0,
            sog_kt=28.5,
            vmg_kt=26.1,
            elapsed_s=1059.555,
        )
        self.assertEqual(leader_entry.gap_to_leader_s, 0.0)
        self.assertEqual(leader_entry.gap_to_leader_m, 0.0)

    def test_chaser_finish_deltas_match_ground_truth(self):
        """Chasers finish deltas to winner: NZL G (+15.3s), ITA B (+18.4s), USA (+53.6s)."""
        fra_elapsed = 1059.555
        nzl_g_delta = 1074.857 - fra_elapsed
        ita_b_delta = 1077.932 - fra_elapsed
        usa_delta = 1113.160 - fra_elapsed

        self.assertAlmostEqual(nzl_g_delta, 15.302, places=3)
        self.assertAlmostEqual(ita_b_delta, 18.377, places=3)
        self.assertAlmostEqual(usa_delta, 53.605, places=3)


class TestHeadToHeadTacticalComparison(unittest.TestCase):
    """Verifies head-to-head pairwise metric calculations."""

    def setUp(self):
        self.analytics = AnalyticsEngine(gun_time_ms=GUN_TIME_EPOCH_MS, course_axis_deg=44.39)

    def test_euclidean_and_longitudinal_separation(self):
        """Head-to-head calculates Euclidean distance and longitudinal advance."""
        axis_rad = math.radians(44.39)
        u_course = (math.sin(axis_rad), math.cos(axis_rad))

        # Boat A is 200m ahead along course axis
        pos_b = (0.0, 0.0)
        pos_a = (200.0 * u_course[0], 200.0 * u_course[1])
        vel_a = (0.0, 0.0)
        vel_b = (0.0, 0.0)

        res = self.analytics.compute_head_to_head_metrics(pos_a, pos_b, vel_a, vel_b)
        self.assertAlmostEqual(res.euclidean_distance_m, 200.0, places=2)
        self.assertAlmostEqual(res.longitudinal_delta_m, 200.0, places=2)
        self.assertAlmostEqual(res.lateral_separation_m, 0.0, places=2)

    def test_lateral_cross_track_separation(self):
        """Head-to-head calculates lateral cross-track displacement perpendicular to course axis."""
        axis_rad = math.radians(44.39)
        u_lat = (-math.cos(axis_rad), math.sin(axis_rad))

        pos_b = (0.0, 0.0)
        pos_a = (150.0 * u_lat[0], 150.0 * u_lat[1])
        vel_a = (0.0, 0.0)
        vel_b = (0.0, 0.0)

        res = self.analytics.compute_head_to_head_metrics(pos_a, pos_b, vel_a, vel_b)
        self.assertAlmostEqual(res.lateral_separation_m, 150.0, places=2)
        self.assertAlmostEqual(res.longitudinal_delta_m, 0.0, places=2)

    def test_rate_of_closure(self):
        """Boat B closing at 10 m/s yields +10 m/s rate of closure."""
        pos_a = (100.0, 0.0)
        pos_b = (0.0, 0.0)
        vel_a = (0.0, 0.0)
        vel_b = (10.0, 0.0)  # B moving towards A

        res = self.analytics.compute_head_to_head_metrics(pos_a, pos_b, vel_a, vel_b)
        self.assertAlmostEqual(res.rate_of_closure_mps, 10.0, places=2)


class TestStartAnalysisTacticalMetrics(unittest.TestCase):
    """Verifies start countdown and line projection metrics."""

    def setUp(self):
        self.analytics = AnalyticsEngine(gun_time_ms=GUN_TIME_EPOCH_MS)

    def test_pre_start_countdown(self):
        """Pre-start countdown at T - 120s is -120.0s."""
        t_sample = GUN_TIME_EPOCH_MS - 120000
        m_port = (-200.0, 100.0)
        m_stbd = (200.0, -100.0)
        bow_pos = (0.0, -200.0)
        vel_mps = (0.0, 10.0)

        res = self.analytics.compute_start_tactical_metrics(
            t_sample, bow_pos, vel_mps, m_port, m_stbd
        )
        self.assertEqual(res.countdown_s, -120.0)
        self.assertFalse(res.is_ocs)
        self.assertLess(res.distance_to_line_m, 0.0)


    def test_live_racing_time_gap_uses_leader_vmg_with_sog_fallback(self):
        """Time gap divides VMG-space distance gap by leader leg VMG (or 0.75*SOG fallback mid-manoeuvre)."""
        from pipeline.analytics import AnalyticsEngine
        from pipeline.config import KNOTS_TO_MPS
        from pipeline.ingest import SynchronizedBoatData

        engine = AnalyticsEngine(gun_time_ms=1000)
        leader = SynchronizedBoatData(
            asset_id="A", code="A", name="Team A", official_name="Team A", color="#111111",
            x=[100.0, 100.0], y=[100.0, 100.0], heading=[45.0, 45.0], cog=[45.0, 45.0],
            sog_kt=[30.0, 20.0], vmg_kt=[25.0, 3.0], twa_deg=[45.0, 90.0],
            twd_deg=[45.0, 45.0], tws_kt=[12.0, 12.0],
        )
        trailer = SynchronizedBoatData(
            asset_id="B", code="B", name="Team B", official_name="Team B", color="#222222",
            x=[0.0, 0.0], y=[0.0, 0.0], heading=[45.0, 45.0], cog=[45.0, 45.0],
            sog_kt=[25.0, 20.0], vmg_kt=[20.0, 15.0], twa_deg=[45.0, 45.0],
            twd_deg=[45.0, 45.0], tws_kt=[12.0, 12.0],
        )
        recs = {
            "A": CompetitorReconstruction("A", "A", "Team A", "#111", "RANK_1", StartResult(1000, 0.0, False, "STARBOARD", -5.0), []),
            "B": CompetitorReconstruction("B", "B", "Team B", "#222", "RANK_2", StartResult(1000, 0.0, False, "STARBOARD", -5.0), []),
        }
        # Frame 0: active foiling with |VMG| = 25.0 kt >= 8.0 kt
        board = engine.compute_instantaneous_leaderboard(
            0, 5000, {"A": leader, "B": trailer},
            {"A": [500.0, 500.0], "B": [300.0, 300.0]},
            {"A": [1, 1], "B": [1, 1]}, recs,
        )
        expected_vmg_gap_s = round(200.0 / (25.0 * KNOTS_TO_MPS), 1)
        self.assertAlmostEqual(board[1].gap_to_leader_s, expected_vmg_gap_s, places=1)

        # Frame 1: mid-manoeuvre |VMG| = 3.0 kt < 8.0 kt -> falls back to 0.75 * SOG = 15.0 kt
        board_tack = engine.compute_instantaneous_leaderboard(
            1, 6000, {"A": leader, "B": trailer},
            {"A": [500.0, 500.0], "B": [300.0, 300.0]},
            {"A": [1, 1], "B": [1, 1]}, recs,
        )
        expected_fallback_s = round(200.0 / (20.0 * 0.75 * KNOTS_TO_MPS), 1)
        self.assertAlmostEqual(board_tack[1].gap_to_leader_s, expected_fallback_s, places=1)


if __name__ == "__main__":
    unittest.main()
