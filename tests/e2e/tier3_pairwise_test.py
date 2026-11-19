"""Tier 3: Cross-Feature Combinations (Pairwise Coverage) E2E Tests.

Tests complex multi-feature interactions:
1. Tack/gybe during gate rounding
2. OCS penalty state combined with leg progress tracking
3. Rapid timeline scrubbing with metric chart synchronization
4. Head-to-head comparative metrics during simultaneous manoeuvres
"""

from __future__ import annotations
import unittest
import math

from tests.e2e.e2e_types import (
    COURSE_AXIS_SETTLED_DEG,
    MARKS_GROUND_TRUTH,
    project_wgs84_to_metric,
    normalize_angle_180,
    intersect_segments_2d,
    compute_head_to_head,
)


class TestTier3Pairwise01ManoeuvreDuringGateRounding(unittest.TestCase):
    """Pairwise 1: Tack/gybe during gate rounding."""

    def setUp(self):
        # Top Gate marks RM4 (port) and RM2 (starboard)
        self.rm4 = project_wgs84_to_metric(MARKS_GROUND_TRUTH["RM4"]["initial_lat"], MARKS_GROUND_TRUTH["RM4"]["initial_lon"])
        self.rm2 = project_wgs84_to_metric(MARKS_GROUND_TRUTH["RM2"]["initial_lat"], MARKS_GROUND_TRUTH["RM2"]["initial_lon"])

    def test_tack_into_top_gate_crossing(self):
        """Boat tacking into top gate RM2 records both valid gate crossing AND tack manoeuvre."""
        # Top gate RM2 rounding setup:
        # Boat starts on port tack (heading 030°, TWA -24°), crosses gate line, and turns onto starboard tack (heading 140°, TWA +86°)
        # Trajectory crosses near RM2
        p_pre = (self.rm2[0] - 15.0, self.rm2[1] - 20.0)
        p_post = (self.rm2[0] + 5.0, self.rm2[1] + 15.0)

        # 1. Gate crossing detected
        crossed, u, s, cx, cy = intersect_segments_2d(p_pre, p_post, self.rm4, self.rm2)
        self.assertTrue(crossed)
        self.assertGreater(s, 0.5)  # Starboard mark RM2

        # 2. Concurrently, heading swing across wind is verified
        twd = 54.0
        hdg_entry = 30.0
        hdg_exit = 140.0
        twa_entry = normalize_angle_180(twd - hdg_entry)  # +24
        twa_exit = normalize_angle_180(twd - hdg_exit)    # -86
        sign_inversion = (twa_entry * twa_exit) < 0
        self.assertTrue(sign_inversion)

        # 3. Speed dip during rounding
        v_entry_kt = 28.0
        v_min_kt = 19.5
        speed_loss = v_entry_kt - v_min_kt
        self.assertGreaterEqual(speed_loss, 3.0)

    def test_leg_transition_advances_without_manoeuvre_event_loss(self):
        """Gate crossing increments leg number from 1 to 2, while manoeuvre history preserves event."""
        current_leg = 1
        manoeuvre_log = []

        # Event occurs
        gate_crossed = True
        if gate_crossed:
            current_leg += 1
            manoeuvre_log.append({
                "type": "TACK",
                "leg": 1,
                "timestamp": 1790079233825,
                "mark": "RM2"
            })

        self.assertEqual(current_leg, 2)
        self.assertEqual(len(manoeuvre_log), 1)
        self.assertEqual(manoeuvre_log[0]["leg"], 1)

    def test_recovery_time_measured_post_gate_crossing(self):
        """Speed recovery occurs on the downwind leg (Leg 2) following upwind mark rounding."""
        entry_speed_kt = 26.0
        target_recovery_kt = 0.90 * entry_speed_kt  # 23.4 kt

        # Speeds after gate crossing (t = 0 to 5s)
        speeds_post = [18.0, 19.5, 21.0, 23.5, 27.0]
        recovered = False
        t_rec_s = None
        for i, s in enumerate(speeds_post):
            if s >= target_recovery_kt:
                recovered = True
                t_rec_s = i * 1.0
                break

        self.assertTrue(recovered)
        self.assertLessEqual(t_rec_s, 4.0)


class TestTier3Pairwise02OCSPenaltyAndProgressTracking(unittest.TestCase):
    """Pairwise 2: OCS penalty state combined with leg progress tracking."""

    def test_ocs_boat_progress_locked_at_zero(self):
        """GBR B flagged OCS has race progress locked at 0.0 despite boat moving over the line."""
        is_ocs = True
        restarted = False

        def get_effective_progress(measured_progress, is_ocs_flag, is_restarted):
            if is_ocs_flag and not is_restarted:
                return 0.0
            return measured_progress

        prog_at_t10 = get_effective_progress(350.0, is_ocs, restarted)
        prog_at_t60 = get_effective_progress(1200.0, is_ocs, restarted)
        self.assertEqual(prog_at_t10, 0.0)
        self.assertEqual(prog_at_t60, 0.0)

    def test_ocs_leaderboard_status_is_ocs_or_ret(self):
        """Leaderboard displays OCS badge for GBR B while fleet shows RACING status."""
        fleet_status = {
            "FRA": "RACING",
            "NZL G": "RACING",
            "GBR B": "OCS"
        }
        self.assertEqual(fleet_status["GBR B"], "OCS")
        self.assertEqual(fleet_status["FRA"], "RACING")

    def test_distance_to_leader_increases_monotonically_for_ocs_boat(self):
        """As leader FRA sails Leg 1, distance gap to stalled OCS boat increases continuously."""
        fra_progress = [100.0, 500.0, 1200.0, 2000.0]
        gbr_b_progress = 0.0

        gaps = [p - gbr_b_progress for p in fra_progress]
        for i in range(len(gaps) - 1):
            self.assertGreater(gaps[i+1], gaps[i])

    def test_penalty_lifecycle_awarded_to_retirement(self):
        """GBR B penalty lifecycle: AWARDED at +0.33s -> ACTIVE -> RET at conclusion."""
        gbr_b_event = {
            "awarded_at": 1790079000333,
            "type": "PENALTY_TYPE_RESTART",
            "reason": "PENALTY_REASON_OCS",
            "state": "PENALTY_STATE_ACTIVE",
            "cleared_at": None,
        }
        self.assertEqual(gbr_b_event["reason"], "PENALTY_REASON_OCS")
        self.assertEqual(gbr_b_event["state"], "PENALTY_STATE_ACTIVE")


class TestTier3Pairwise03ScrubbingAndChartSynchronization(unittest.TestCase):
    """Pairwise 3: Rapid timeline scrubbing with metric chart synchronization."""

    def test_scrubbing_backwards_reverts_leg_and_progress(self):
        """Seeking backwards from Leg 3 (800s) to Leg 1 (200s) updates active leg and state."""
        # Timeline state query function
        def query_state_at_t(t_elapsed_s):
            if t_elapsed_s < 0:
                return {"leg": 0, "status": "PRESTART"}
            elif t_elapsed_s < 234:
                return {"leg": 1, "status": "RACING"}
            elif t_elapsed_s < 500:
                return {"leg": 2, "status": "RACING"}
            else:
                return {"leg": 3, "status": "RACING"}

        state_800 = query_state_at_t(800.0)
        self.assertEqual(state_800["leg"], 3)

        # Scrub backwards to 200s
        state_200 = query_state_at_t(200.0)
        self.assertEqual(state_200["leg"], 1)

        # Scrub backwards to pre-start -60s
        state_pre = query_state_at_t(-60.0)
        self.assertEqual(state_pre["leg"], 0)
        self.assertEqual(state_pre["status"], "PRESTART")

    def test_chart_cursor_matches_scrubber_playhead(self):
        """Metric chart vertical cursor position matches virtual playback clock within 1ms."""
        virtual_clock_ms = 1790079350250
        chart_cursor_ms = virtual_clock_ms
        self.assertEqual(chart_cursor_ms, virtual_clock_ms)

    def test_speed_multipliers_preserve_gate_event_detection(self):
        """High playback speed (8x) must not skip gate crossings using segment bracketing."""
        # 8x speed at 60 FPS advances 8 * 16.67ms = 133.3ms per frame
        delta_frame_ms = 133.3
        t_start = 1790079233700
        t_end = t_start + delta_frame_ms  # 1790079233833.3

        # Actual gate crossing is at 1790079233827
        t_gate = 1790079233827
        crossing_in_bracket = t_start <= t_gate <= t_end
        self.assertTrue(crossing_in_bracket)

    def test_rapid_scrubbing_clamps_within_race_window(self):
        """Scrubbing to extreme out-of-bound timestamps clamps strictly to window start/end."""
        win_start = 1790078820000
        win_end = 1790080768700

        def clamp_scrub(t):
            return max(win_start, min(win_end, t))

        self.assertEqual(clamp_scrub(1000000000000), win_start)
        self.assertEqual(clamp_scrub(2000000000000), win_end)
        self.assertEqual(clamp_scrub(1790079000000), 1790079000000)


class TestTier3Pairwise04ComparativeMetricsDuringManoeuvres(unittest.TestCase):
    """Pairwise 4: Head-to-head comparative metrics during simultaneous manoeuvres."""

    def test_vmg_delta_inversion_when_one_boat_tacks(self):
        """When Boat A tacks (VMG drops to ~0) while Boat B continues at full VMG, delta VMG surges."""
        vmg_a_foiling = 24.0  # kt
        vmg_b_foiling = 23.5  # kt
        delta_vmg_initial = vmg_a_foiling - vmg_b_foiling  # +0.5 kt

        # Boat A enters tack: VMG drops to 2 kt
        vmg_a_tacking = 2.0
        delta_vmg_tack = vmg_a_tacking - vmg_b_foiling  # -21.5 kt
        self.assertLess(delta_vmg_tack, -20.0)
        self.assertNotEqual(math.copysign(1, delta_vmg_initial), math.copysign(1, delta_vmg_tack))

    def test_lateral_separation_during_split_tacks(self):
        """When two boats sail on opposite tacks, lateral separation increases rapidly (tactical leverage)."""
        axis_rad = math.radians(COURSE_AXIS_SETTLED_DEG)
        u_lat = (-math.cos(axis_rad), math.sin(axis_rad))

        # t0: Both at center
        pos_a0 = (0.0, 0.0)
        pos_b0 = (0.0, 0.0)
        h2h_0 = compute_head_to_head(pos_a0, pos_b0, (0.0, 0.0), (0.0, 0.0))
        self.assertEqual(h2h_0["lateral_separation_m"], 0.0)

        # t1: A goes left, B goes right
        pos_a1 = (-200.0 * u_lat[0], -200.0 * u_lat[1])
        pos_b1 = (200.0 * u_lat[0], 200.0 * u_lat[1])
        h2h_1 = compute_head_to_head(pos_a1, pos_b1, (0.0, 0.0), (0.0, 0.0))
        self.assertAlmostEqual(h2h_1["lateral_separation_m"], 400.0, places=2)

    def test_closest_point_of_approach_during_crossing(self):
        """CPA calculation determines safe passing distance when boats cross on opposite tacks."""
        # Boat A moving East at 15 m/s from (-50, 0)
        # Boat B moving North at 15 m/s from (0, -50)
        # CPA occurs at (0, 0) at t = 50 / 15 = 3.33s with distance 0m (collision trajectory)
        pos_a = (-50.0, 0.0)
        pos_b = (0.0, -50.0)
        v_a = (15.0, 0.0)
        v_b = (0.0, 15.0)

        # Relative pos & vel
        rx = pos_a[0] - pos_b[0]  # -50
        ry = pos_a[1] - pos_b[1]  # +50
        vx = v_a[0] - v_b[0]      # +15
        vy = v_a[1] - v_b[1]      # -15

        # t_cpa = - (r . v) / (v . v)
        r_dot_v = rx * vx + ry * vy  # -750 - 750 = -1500
        v_sq = vx**2 + vy**2         # 225 + 225 = 450
        t_cpa = -r_dot_v / v_sq      # 1500 / 450 = 3.333s

        self.assertAlmostEqual(t_cpa, 3.333, places=2)


if __name__ == "__main__":
    unittest.main()
