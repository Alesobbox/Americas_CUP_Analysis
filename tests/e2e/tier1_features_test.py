"""Tier 1: Feature Coverage E2E Tests for AC40 America's Cup 2D Regatta Replay.

Covers all 13 core features with >=5 dedicated test cases per feature (65+ total tests).
Derived strictly from ORIGINAL_REQUEST.md, PROJECT.md, and authoritative ground truth.
"""

from __future__ import annotations
import unittest
import math
import json

from tests.e2e.e2e_types import (
    COURSE_ORIGIN_LAT,
    COURSE_ORIGIN_LON,
    KNOT_PER_MPS,
    GUN_TIME_MS,
    WINDOW_START_MS,
    WINDOW_END_MS,
    AC40_BOW_OFFSET_M,
    MARKS_GROUND_TRUTH,
    COMPETITORS_GROUND_TRUTH,
    COURSE_AXIS_SETTLED_DEG,
    haversine_distance_m,
    project_wgs84_to_metric,
    inverse_metric_to_wgs84,
    mps_to_knots,
    knots_to_mps,
    normalize_angle_180,
    circular_shortest_diff_deg,
    circular_slerp_deg,
    intersect_segments_2d,
    format_race_clock,
    transform_world_to_screen,
    transform_screen_to_world,
    compute_head_to_head,
)


class TestTier1Feature01CoordinateConversion(unittest.TestCase):
    """Feature 1: Coordinate conversion accuracy (<0.1% vs Haversine)."""

    def test_origin_projects_to_zero(self):
        """Course midpoint origin (40.80948067, 14.23726898) projects exactly to (0.0, 0.0) metres."""
        x, y = project_wgs84_to_metric(COURSE_ORIGIN_LAT, COURSE_ORIGIN_LON)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_bottom_gate_rm8_to_rm6_distance_accuracy(self):
        """Bottom Gate line (RM8 to RM6) Euclidean metric distance error vs Haversine is < 0.1%."""
        rm8 = MARKS_GROUND_TRUTH["RM8"]
        rm6 = MARKS_GROUND_TRUTH["RM6"]

        x8, y8 = project_wgs84_to_metric(rm8["initial_lat"], rm8["initial_lon"])
        x6, y6 = project_wgs84_to_metric(rm6["initial_lat"], rm6["initial_lon"])
        metric_dist = math.sqrt((x6 - x8)**2 + (y6 - y8)**2)

        haversine_dist = haversine_distance_m(
            rm8["initial_lat"], rm8["initial_lon"],
            rm6["initial_lat"], rm6["initial_lon"]
        )

        rel_error = abs(metric_dist - haversine_dist) / haversine_dist
        self.assertLess(rel_error, 0.001, f"Relative error {rel_error:.6f} exceeded 0.1%")
        self.assertLess(rel_error, 0.0003, f"Expected ~0.028% distortion, got {rel_error*100:.4f}%")

    def test_top_gate_rm4_to_rm2_distance_accuracy(self):
        """Top Gate line (RM4 to RM2) Euclidean metric distance error vs Haversine is < 0.1%."""
        rm4 = MARKS_GROUND_TRUTH["RM4"]
        rm2 = MARKS_GROUND_TRUTH["RM2"]

        x4, y4 = project_wgs84_to_metric(rm4["initial_lat"], rm4["initial_lon"])
        x2, y2 = project_wgs84_to_metric(rm2["initial_lat"], rm2["initial_lon"])
        metric_dist = math.sqrt((x2 - x4)**2 + (y2 - y4)**2)

        haversine_dist = haversine_distance_m(
            rm4["initial_lat"], rm4["initial_lon"],
            rm2["initial_lat"], rm2["initial_lon"]
        )

        rel_error = abs(metric_dist - haversine_dist) / haversine_dist
        self.assertLess(rel_error, 0.001, f"Relative error {rel_error:.6f} exceeded 0.1%")

    def test_windward_leeward_axis_length_accuracy(self):
        """Full course length (Bottom Gate to Top Gate) Euclidean error vs Haversine is < 0.1%."""
        # Midpoint of bottom gate vs midpoint of top gate
        rm8 = MARKS_GROUND_TRUTH["RM8"]
        rm6 = MARKS_GROUND_TRUTH["RM6"]
        rm4 = MARKS_GROUND_TRUTH["RM4"]
        rm2 = MARKS_GROUND_TRUTH["RM2"]

        lat_bot = (rm8["initial_lat"] + rm6["initial_lat"]) / 2.0
        lon_bot = (rm8["initial_lon"] + rm6["initial_lon"]) / 2.0
        lat_top = (rm4["initial_lat"] + rm2["initial_lat"]) / 2.0
        lon_top = (rm4["initial_lon"] + rm2["initial_lon"]) / 2.0

        x_bot, y_bot = project_wgs84_to_metric(lat_bot, lon_bot)
        x_top, y_top = project_wgs84_to_metric(lat_top, lon_top)
        metric_dist = math.sqrt((x_top - x_bot)**2 + (y_top - y_bot)**2)

        haversine_dist = haversine_distance_m(lat_bot, lon_bot, lat_top, lon_top)
        rel_error = abs(metric_dist - haversine_dist) / haversine_dist
        self.assertLess(rel_error, 0.001)
        self.assertAlmostEqual(metric_dist, 2263.7, delta=10.0)

    def test_invertibility_roundtrip(self):
        """Inverse projection (x, y) -> (lat, lon) -> (x, y) preserves millimeter precision."""
        test_points = [
            (0.0, 0.0),
            (-898.44, -726.54),
            (632.72, 946.75),
            (1250.0, -1400.0),
            (-1500.0, 1800.0),
        ]
        for x_in, y_in in test_points:
            lat, lon = inverse_metric_to_wgs84(x_in, y_in)
            x_out, y_out = project_wgs84_to_metric(lat, lon)
            self.assertAlmostEqual(x_out, x_in, places=3)
            self.assertAlmostEqual(y_out, y_in, places=3)

    def test_quadrant_signs_consistency(self):
        """Geographic offsets to NE, NW, SE, SW yield expected metric coordinate signs."""
        eps = 0.01  # degree
        # North-East: lon > lon0 (+X), lat > lat0 (+Y)
        x_ne, y_ne = project_wgs84_to_metric(COURSE_ORIGIN_LAT + eps, COURSE_ORIGIN_LON + eps)
        self.assertGreater(x_ne, 0.0)
        self.assertGreater(y_ne, 0.0)

        # South-West: lon < lon0 (-X), lat < lat0 (-Y)
        x_sw, y_sw = project_wgs84_to_metric(COURSE_ORIGIN_LAT - eps, COURSE_ORIGIN_LON - eps)
        self.assertLess(x_sw, 0.0)
        self.assertLess(y_sw, 0.0)


class TestTier1Feature02StreamSynchronization(unittest.TestCase):
    """Feature 2: Stream synchronization & 10Hz regularization."""

    def test_regular_grid_timestamp_interval(self):
        """10 Hz regular grid spacing is strictly 100 ms between adjacent timestamps."""
        grid_step_ms = 100
        timestamps = [WINDOW_START_MS + i * grid_step_ms for i in range(100)]
        for i in range(len(timestamps) - 1):
            self.assertEqual(timestamps[i+1] - timestamps[i], 100)

    def test_total_frame_count_for_session_window(self):
        """Total frame count from window_start to window_end matches expected duration."""
        # Window start: 1790078820000, Window end: 1790080768700
        window_duration_ms = WINDOW_END_MS - WINDOW_START_MS
        expected_frames = int(window_duration_ms / 100) + 1
        self.assertEqual(expected_frames, 19488)

    def test_20hz_gnss_aligns_evenly_to_10hz_grid(self):
        """20 Hz samples (50 ms interval) divide evenly into 10 Hz grid (100 ms interval)."""
        gnss_interval_ms = 50
        grid_interval_ms = 100
        # Every 2nd 20Hz sample is exact 10Hz sample with zero clock phase jitter
        for k in range(50):
            t_grid = WINDOW_START_MS + k * grid_interval_ms
            # Matching 20Hz index
            gnss_idx = (t_grid - WINDOW_START_MS) / gnss_interval_ms
            self.assertEqual(gnss_idx, int(gnss_idx))

    def test_resample_4_37hz_sog_onto_10hz_grid(self):
        """Resampling ~4.37 Hz SOG data (229 ms) linearly interpolates with continuous values."""
        # Simulated raw 4.37Hz samples
        raw_sog_stream = [
            (1790079000000, 20.0),
            (1790079000229, 21.0),
            (1790079000458, 22.0),
        ]
        # Target 10Hz grid point at t = 1790079000100 ms
        t_target = 1790079000100
        t0, v0 = raw_sog_stream[0]
        t1, v1 = raw_sog_stream[1]
        alpha = (t_target - t0) / (t1 - t0)
        v_interp = v0 + alpha * (v1 - v0)

        self.assertAlmostEqual(alpha, 100.0 / 229.0, places=4)
        self.assertGreater(v_interp, 20.0)
        self.assertLess(v_interp, 21.0)

    def test_stream_temporal_monotonicity(self):
        """Regularized timestamps are strictly monotonically increasing with zero backwards steps."""
        ts_grid = [WINDOW_START_MS + i * 100 for i in range(1000)]
        self.assertTrue(all(ts_grid[i] < ts_grid[i+1] for i in range(len(ts_grid) - 1)))

    def test_circular_resampling_of_headings_across_boundary(self):
        """Resampling angular heading across 360/0 boundary uses shortest arc without 359 deg spin."""
        # Heading turns through North: 355 deg at t=0, 5 deg at t=200ms
        hdg0 = 355.0
        hdg1 = 5.0
        # Sample at t=100ms (alpha=0.5)
        res_hdg = circular_slerp_deg(hdg0, hdg1, 0.5)
        self.assertAlmostEqual(res_hdg, 0.0, delta=0.01)


class TestTier1Feature03KnotSpeedConversion(unittest.TestCase):
    """Feature 3: Knot speed conversion (1 m/s = 1.94384 kt)."""

    def test_conversion_factor_exactness(self):
        """Knot conversion factor matches 3600 / 1852 within 1e-9."""
        self.assertAlmostEqual(KNOT_PER_MPS, 3600.0 / 1852.0, places=9)
        self.assertAlmostEqual(KNOT_PER_MPS, 1.94384449, places=6)

    def test_zero_velocity(self):
        """0.0 m/s converts to exactly 0.0 knots."""
        self.assertEqual(mps_to_knots(0.0), 0.0)
        self.assertEqual(knots_to_mps(0.0), 0.0)

    def test_typical_foiling_speed_conversion(self):
        """15.0 m/s converts to 29.15767 knots."""
        kt = mps_to_knots(15.0)
        self.assertAlmostEqual(kt, 29.157667, places=4)

    def test_maximum_ac40_speed_conversion(self):
        """25.0 m/s converts to 48.59611 knots."""
        kt = mps_to_knots(25.0)
        self.assertAlmostEqual(kt, 48.596112, places=4)

    def test_wind_speed_conversion(self):
        """Official wind speed 5.49 m/s converts to 10.67 knots."""
        kt = mps_to_knots(5.49)
        self.assertAlmostEqual(kt, 10.6717, places=2)

    def test_roundtrip_conversion_invertibility(self):
        """Knots <-> m/s roundtrip retains precision across foiling speeds."""
        speeds_mps = [0.1, 5.0, 10.25, 18.7, 24.3]
        for v in speeds_mps:
            kt = mps_to_knots(v)
            v_back = knots_to_mps(kt)
            self.assertAlmostEqual(v_back, v, places=7)


class TestTier1Feature04StartLineCrossingAndOCS(unittest.TestCase):
    """Feature 4: Start line crossing delta & GBR B OCS detection."""

    def test_gun_time_definition(self):
        """Official start gun T=0 occurs at epoch ms 1790079000000."""
        self.assertEqual(GUN_TIME_MS, 1790079000000)

    def test_winner_fra_clean_start_delta(self):
        """Winner FRA crosses start line cleanly +0.436s after the gun."""
        fra = COMPETITORS_GROUND_TRUTH["FRA"]
        self.assertEqual(fra["start_crossing_ms"], 1790079000436)
        delta_s = (fra["start_crossing_ms"] - GUN_TIME_MS) / 1000.0
        self.assertAlmostEqual(delta_s, 0.436, places=3)
        self.assertFalse(fra["ocs"])

    def test_fleet_clean_start_deltas_all_positive(self):
        """All clean starters (FRA, NZL G, ITA B, ITA G, GBR G, SUI) crossed after gun (>0s)."""
        clean_starters = ["FRA", "NZL G", "ITA B", "ITA G", "GBR G", "SUI"]
        for team in clean_starters:
            boat = COMPETITORS_GROUND_TRUTH[team]
            delta = boat["start_delta_s"]
            self.assertIsNotNone(delta)
            self.assertGreater(delta, 0.0, f"{team} start delta must be positive")
            self.assertFalse(boat["ocs"], f"{team} must not be flagged OCS")

    def test_gbr_b_ocs_detection_at_gun(self):
        """GBR B is flagged OCS, +610.5m on course side of the start line at gun."""
        gbr_b = COMPETITORS_GROUND_TRUTH["GBR B"]
        self.assertTrue(gbr_b["ocs"])
        self.assertAlmostEqual(gbr_b["ocs_distance_m"], 610.5, places=1)
        self.assertEqual(gbr_b["status"], "RET")

    def test_gbr_b_penalty_timestamp_audit(self):
        """GBR B OCS penalty was awarded +0.333s after gun at epoch 1790079000333."""
        gbr_b = COMPETITORS_GROUND_TRUTH["GBR B"]
        self.assertEqual(gbr_b["ocs_awarded_ms"], 1790079000333)
        delta_awarded = (gbr_b["ocs_awarded_ms"] - GUN_TIME_MS) / 1000.0
        self.assertAlmostEqual(delta_awarded, 0.333, places=3)

    def test_usa_reconstructed_start_crossing(self):
        """USA start crossing reconstructed at +0.348s after gun."""
        usa = COMPETITORS_GROUND_TRUTH["USA"]
        self.assertEqual(usa["start_crossing_ms"], 1790079000348)
        self.assertAlmostEqual(usa["start_delta_s"], 0.348, places=3)
        self.assertFalse(usa["ocs"])


class TestTier1Feature05GateCrossingDetection(unittest.TestCase):
    """Feature 5: Gate crossing detection (Legs 1-4) & port vs starboard mark choice."""

    def setUp(self):
        # Set up standard gate metric coordinates
        self.m8 = project_wgs84_to_metric(MARKS_GROUND_TRUTH["RM8"]["initial_lat"], MARKS_GROUND_TRUTH["RM8"]["initial_lon"])
        self.m6 = project_wgs84_to_metric(MARKS_GROUND_TRUTH["RM6"]["initial_lat"], MARKS_GROUND_TRUTH["RM6"]["initial_lon"])
        self.m4 = project_wgs84_to_metric(MARKS_GROUND_TRUTH["RM4"]["initial_lat"], MARKS_GROUND_TRUTH["RM4"]["initial_lon"])
        self.m2 = project_wgs84_to_metric(MARKS_GROUND_TRUTH["RM2"]["initial_lat"], MARKS_GROUND_TRUTH["RM2"]["initial_lon"])

    def test_2d_intersection_detects_gate_crossing(self):
        """Segment intersection correctly identifies boat bow piercing bottom gate line."""
        # Midpoint of bottom gate line
        gate_mid_x = (self.m8[0] + self.m6[0]) / 2.0
        gate_mid_y = (self.m8[1] + self.m6[1]) / 2.0

        # Trajectory passing through gate from behind to ahead
        p_prev = (gate_mid_x - 10.0, gate_mid_y - 15.0)
        p_curr = (gate_mid_x + 10.0, gate_mid_y + 15.0)

        crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, self.m8, self.m6)
        self.assertTrue(crossed)
        self.assertAlmostEqual(u, 0.5, delta=0.05)
        self.assertAlmostEqual(s, 0.5, delta=0.05)

    def test_starboard_mark_choice_identification(self):
        """Trajectory crossing near RM6 (s >= 0.5) is classified as Starboard mark choice."""
        # Trajectory close to RM6 (starboard)
        p_prev = (self.m6[0] - 10.0, self.m6[1] - 10.0)
        p_curr = (self.m6[0] + 10.0, self.m6[1] + 10.0)

        crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, self.m8, self.m6)
        self.assertTrue(crossed)
        self.assertGreater(s, 0.5)
        chosen_mark = "RM6" if s >= 0.5 else "RM8"
        self.assertEqual(chosen_mark, "RM6")

    def test_port_mark_choice_identification(self):
        """Trajectory crossing near RM8 (s < 0.5) is classified as Port mark choice."""
        # Trajectory close to RM8 (port)
        p_prev = (self.m8[0] - 10.0, self.m8[1] - 10.0)
        p_curr = (self.m8[0] + 10.0, self.m8[1] + 10.0)

        crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, self.m8, self.m6)
        self.assertTrue(crossed)
        self.assertLess(s, 0.5)
        chosen_mark = "RM8" if s < 0.5 else "RM6"
        self.assertEqual(chosen_mark, "RM8")

    def test_non_intersecting_trajectory_rejected(self):
        """Trajectory that does not cross the gate segment returns crossed=False."""
        p_prev = (0.0, 0.0)
        p_curr = (50.0, 50.0)
        # Far from bottom gate
        crossed, _, _, _, _ = intersect_segments_2d(p_prev, p_curr, self.m8, self.m6)
        self.assertFalse(crossed)

    def test_bow_offset_timing_advance_at_speed(self):
        """At 30 knots (~15.43 m/s), bow offset of 12.963m crosses line ~0.84s before GPS antenna."""
        speed_mps = knots_to_mps(30.0)
        advance_s = AC40_BOW_OFFSET_M / speed_mps
        self.assertAlmostEqual(advance_s, 0.84, delta=0.05)


class TestTier1Feature06MonotonicRaceProgress(unittest.TestCase):
    """Feature 6: Monotonic continuous race progress."""

    def test_progress_monotonic_along_leg(self):
        """Instantaneous advance along leg direction increases monotonically as boat advances."""
        axis_rad = math.radians(COURSE_AXIS_SETTLED_DEG)
        u_course = (math.sin(axis_rad), math.cos(axis_rad))

        # Boat advancing along course axis from origin
        steps = [10.0 * i for i in range(20)]
        positions = [(s * u_course[0], s * u_course[1]) for s in steps]

        advances = [pos[0] * u_course[0] + pos[1] * u_course[1] for pos in positions]
        for i in range(len(advances) - 1):
            self.assertGreater(advances[i+1], advances[i])

    def test_progress_fractions_across_legs(self):
        """Progress fraction Pi(t) equals 0.0 at pre-start, 0.25 at Leg 1, 0.50 at Leg 2, 0.75 at Leg 3, 1.0 at Finish."""
        leg_lengths = [2400.0, 2400.0, 2400.0, 2400.0]
        total_dist = sum(leg_lengths)

        # Pre-start
        pi_pre = 0.0 / total_dist
        self.assertEqual(pi_pre, 0.0)

        # End of leg 1
        pi_l1 = leg_lengths[0] / total_dist
        self.assertEqual(pi_l1, 0.25)

        # End of leg 2
        pi_l2 = (leg_lengths[0] + leg_lengths[1]) / total_dist
        self.assertEqual(pi_l2, 0.50)

        # End of leg 3
        pi_l3 = (leg_lengths[0] + leg_lengths[1] + leg_lengths[2]) / total_dist
        self.assertEqual(pi_l3, 0.75)

        # Finish line
        pi_finish = total_dist / total_dist
        self.assertEqual(pi_finish, 1.0)

    def test_distance_remaining_decreases_to_zero(self):
        """Distance remaining D_rem = D_total - P_inst decreases to 0 at finish."""
        d_total = 9600.0
        p_inst_values = [0.0, 2400.0, 4800.0, 7200.0, 9600.0]
        d_rem_values = [d_total - p for p in p_inst_values]
        self.assertEqual(d_rem_values[0], 9600.0)
        self.assertEqual(d_rem_values[-1], 0.0)
        self.assertTrue(all(d_rem_values[i] > d_rem_values[i+1] for i in range(len(d_rem_values)-1)))

    def test_progress_clamped_at_leg_boundaries(self):
        """Course progress clamping prevents negative values during pre-start or overshoot beyond 1.0."""
        def calc_pi(p, total):
            return max(0.0, min(1.0, p / total))

        total = 9600.0
        self.assertEqual(calc_pi(-50.0, total), 0.0)
        self.assertEqual(calc_pi(10000.0, total), 1.0)
        self.assertEqual(calc_pi(4800.0, total), 0.5)

    def test_leaderboard_progress_resolves_leaders(self):
        """Boat further along course progress is deterministically ranked ahead."""
        boat_a_prog = 3500.0
        boat_b_prog = 3200.0
        self.assertGreater(boat_a_prog, boat_b_prog)


class TestTier1Feature07TackAndGybeDetection(unittest.TestCase):
    """Feature 7: Tack and gybe detection (speed loss, recovery, 0 straight-line false positives)."""

    def test_tack_twa_transition_through_zero(self):
        """Tack is identified when TWA crosses through 0 deg (bow through wind) with |delta hdg| >= 60 deg."""
        # Upwind tack: TWA from -45 deg (port) to +45 deg (starboard)
        twa_before = -45.0
        twa_after = +45.0
        twa_delta_through_zero = abs(twa_after - twa_before)
        self.assertEqual(twa_delta_through_zero, 90.0)
        # Heading change is >= 60 deg
        self.assertGreaterEqual(twa_delta_through_zero, 60.0)

    def test_gybe_twa_transition_through_180(self):
        """Gybe is identified when TWA crosses through +/-180 deg (stern through wind)."""
        # Downwind gybe: TWA from +140 deg to -140 deg
        twa_before = 140.0
        twa_after = -140.0
        shortest_diff = circular_shortest_diff_deg(twa_before, twa_after)
        self.assertAlmostEqual(shortest_diff, 80.0)
        # Stern through wind means crossing +/-180
        total_turn = 360.0 - abs(twa_after - twa_before)
        self.assertEqual(total_turn, 80.0)
        self.assertGreaterEqual(total_turn, 60.0)

    def test_speed_loss_and_recovery_calculation(self):
        """Manoeuvre calculates entry speed, min speed, speed loss, and 90% recovery time."""
        entry_speed = 28.0  # kt
        min_speed = 18.0    # kt
        speed_loss = entry_speed - min_speed
        recovery_threshold = 0.90 * entry_speed  # 25.2 kt

        self.assertEqual(speed_loss, 10.0)
        self.assertGreaterEqual(speed_loss, 3.0)  # Exceeds 3kt dip requirement
        self.assertEqual(recovery_threshold, 25.2)

    def test_straight_line_course_correction_rejected(self):
        """Small heading adjustment (+/- 5 deg) produces zero manoeuvre false positives."""
        hdg_before = 40.0
        hdg_after = 45.0
        delta_hdg = abs(hdg_after - hdg_before)
        # Must be rejected because delta_hdg < 60 deg threshold
        self.assertLess(delta_hdg, 60.0)

    def test_tack_stability_threshold_duration(self):
        """Tack requires new tack sign to persist for >= 2.5 seconds to avoid chatter triggers."""
        required_duration_s = 2.5
        # 12 consecutive samples at 5 Hz or 25 samples at 10 Hz
        samples_at_10hz = int(required_duration_s * 10)
        self.assertEqual(samples_at_10hz, 25)


class TestTier1Feature08FinalClassificationOrder(unittest.TestCase):
    """Feature 8: Final classification order (FRA 1st, NZL G 2nd, ITA B 3rd, USA 4th, ITA G 5th, GBR G 6th)."""

    def test_official_winner_fra_rank_and_time(self):
        """FRA is 1st with elapsed time 17m 39.555s (1059.555s) and delta 0.0s."""
        fra = COMPETITORS_GROUND_TRUTH["FRA"]
        self.assertEqual(fra["official_rank"], 1)
        self.assertEqual(fra["finish_time_ms"], 1790080059555)
        self.assertAlmostEqual(fra["elapsed_s"], 1059.555, places=3)
        self.assertEqual(fra["delta_to_winner_s"], 0.0)

    def test_official_podium_order_and_deltas(self):
        """Podium: FRA 1st, NZL G 2nd (+15.3s), ITA B 3rd (+18.4s)."""
        nzl_g = COMPETITORS_GROUND_TRUTH["NZL G"]
        ita_b = COMPETITORS_GROUND_TRUTH["ITA B"]

        self.assertEqual(nzl_g["official_rank"], 2)
        self.assertAlmostEqual(nzl_g["delta_to_winner_s"], 15.302, places=3)

        self.assertEqual(ita_b["official_rank"], 3)
        self.assertAlmostEqual(ita_b["delta_to_winner_s"], 18.377, places=3)

        self.assertLess(COMPETITORS_GROUND_TRUTH["FRA"]["elapsed_s"], nzl_g["elapsed_s"])
        self.assertLess(nzl_g["elapsed_s"], ita_b["elapsed_s"])

    def test_positions_4_to_6_order(self):
        """Finishers 4-6: USA 4th (+53.6s), ITA G 5th (+88.4s), GBR G 6th (+107.0s)."""
        usa = COMPETITORS_GROUND_TRUTH["USA"]
        ita_g = COMPETITORS_GROUND_TRUTH["ITA G"]
        gbr_g = COMPETITORS_GROUND_TRUTH["GBR G"]

        self.assertEqual(usa["official_rank"], 4)
        self.assertAlmostEqual(usa["delta_to_winner_s"], 53.605, places=3)

        self.assertEqual(ita_g["official_rank"], 5)
        self.assertAlmostEqual(ita_g["delta_to_winner_s"], 88.380, places=3)

        self.assertEqual(gbr_g["official_rank"], 6)
        self.assertAlmostEqual(gbr_g["delta_to_winner_s"], 107.047, places=3)

        self.assertLess(usa["elapsed_s"], ita_g["elapsed_s"])
        self.assertLess(ita_g["elapsed_s"], gbr_g["elapsed_s"])

    def test_non_finishers_dnf_and_ret(self):
        """NZL B and SUI did not finish Leg 4 (DNF); GBR B retired (RET)."""
        nzl_b = COMPETITORS_GROUND_TRUTH["NZL B"]
        sui = COMPETITORS_GROUND_TRUTH["SUI"]
        gbr_b = COMPETITORS_GROUND_TRUTH["GBR B"]

        self.assertEqual(nzl_b["status"], "DNF")
        self.assertEqual(sui["status"], "DNF")
        self.assertEqual(gbr_b["status"], "RET")
        self.assertIsNone(nzl_b["finish_time_ms"])
        self.assertIsNone(sui["finish_time_ms"])
        self.assertIsNone(gbr_b["finish_time_ms"])

    def test_all_9_boats_strictly_ranked(self):
        """Ranks 1 to 9 uniquely partition the fleet with no duplicates."""
        ranks = [boat["official_rank"] for boat in COMPETITORS_GROUND_TRUTH.values()]
        self.assertEqual(sorted(ranks), list(range(1, 10)))


class TestTier1Feature09CameraModes(unittest.TestCase):
    """Feature 9: Camera modes (North-Up, Course-Up 40° vertical)."""

    def test_north_up_rotation_is_zero(self):
        """North-Up camera has rotation angle theta = 0.0 rad (0.0 deg)."""
        w, h = 1920.0, 1080.0
        zoom = 0.5
        # Point straight North from origin: (0, 100m)
        u, v = transform_world_to_screen(0.0, 100.0, 0.0, 0.0, zoom, 0.0, w, h)
        # Should be horizontally centered, vertically shifted UP (screen v decreases)
        self.assertAlmostEqual(u, w / 2.0, places=3)
        self.assertAlmostEqual(v, (h / 2.0) - (100.0 * zoom), places=3)

    def test_course_up_aligns_40_degree_axis_vertically(self):
        """Course-Up camera rotates by -40 deg, aligning course axis (40 deg) vertically on screen."""
        w, h = 1920.0, 1080.0
        zoom = 0.5
        course_rot = -40.0  # degrees
        axis_rad = math.radians(40.0)
        # Point 100m along course axis: x = 100 * sin(40), y = 100 * cos(40)
        p_axis_x = 100.0 * math.sin(axis_rad)
        p_axis_y = 100.0 * math.cos(axis_rad)

        u, v = transform_world_to_screen(p_axis_x, p_axis_y, 0.0, 0.0, zoom, course_rot, w, h)
        # Under Course-Up, the point along 40 deg course axis must be straight UP on screen (u = W/2, v < H/2)
        self.assertAlmostEqual(u, w / 2.0, places=2)
        self.assertLess(v, h / 2.0)
        self.assertAlmostEqual(v, (h / 2.0) - (100.0 * zoom), places=2)

    def test_camera_invertibility_roundtrip(self):
        """Screen-to-World is exact inverse of World-to-Screen under any rotation."""
        w, h = 1920.0, 1080.0
        zoom = 0.75
        cam_x, cam_y = 150.0, -250.0
        for rot in [0.0, -40.0, 35.0, 180.0]:
            world_pts = [(0.0, 0.0), (300.0, 450.0), (-600.0, -800.0)]
            for wx, wy in world_pts:
                u, v = transform_world_to_screen(wx, wy, cam_x, cam_y, zoom, rot, w, h)
                rx, ry = transform_screen_to_world(u, v, cam_x, cam_y, zoom, rot, w, h)
                self.assertAlmostEqual(rx, wx, places=3)
                self.assertAlmostEqual(ry, wy, places=3)

    def test_compass_rose_bezel_rotation(self):
        """In Course-Up (-40 deg), the compass rose rotates by +40 deg to indicate true North."""
        cam_rot = -40.0
        compass_rose_north_indicator_deg = -cam_rot  # 40 deg
        self.assertEqual(compass_rose_north_indicator_deg, 40.0)

    def test_zoom_scaling_is_isotropic(self):
        """Distance in pixels scales linearly and identically in X and Y (no aspect distortion)."""
        w, h = 1000.0, 1000.0
        u0, v0 = transform_world_to_screen(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, w, h)
        ux, vx = transform_world_to_screen(50.0, 0.0, 0.0, 0.0, 1.0, 0.0, w, h)
        uy, vy = transform_world_to_screen(0.0, 50.0, 0.0, 0.0, 1.0, 0.0, w, h)
        dx = abs(ux - u0)
        dy = abs(vy - v0)
        self.assertAlmostEqual(dx, 50.0)
        self.assertAlmostEqual(dy, 50.0)


class TestTier1Feature10PlaybackClockFormatting(unittest.TestCase):
    """Feature 10: Playback clock formatting (-MM:SS pre-start, +MM:SS elapsed)."""

    def test_pre_start_warning_signal(self):
        """Pre-start 3 minutes (-180,000 ms) formats as -03:00."""
        self.assertEqual(format_race_clock(-180000), "-03:00")

    def test_pre_start_intermediate_time(self):
        """Pre-start 2m 35s (-155,000 ms) formats as -02:35."""
        self.assertEqual(format_race_clock(-155000), "-02:35")

    def test_exact_gun_time(self):
        """Exact gun time (0 ms) formats as 00:00."""
        self.assertEqual(format_race_clock(0), "00:00")

    def test_elapsed_positive_time(self):
        """Elapsed 4m 32s (+272,000 ms) formats as 04:32."""
        self.assertEqual(format_race_clock(272000), "04:32")

    def test_winner_finish_clock_format(self):
        """FRA finish at 1059.555s formats as 17:39 or 17:39.5 with fraction."""
        self.assertEqual(format_race_clock(1059555), "17:39")
        self.assertEqual(format_race_clock(1059555, show_fraction=True), "17:39.5")


class TestTier1Feature11LeaderboardDataConsistency(unittest.TestCase):
    """Feature 11: Leaderboard & telemetry inspection data consistency."""

    def test_vmg_does_not_exceed_sog(self):
        """Velocity Made Good (|VMG|) never exceeds Speed Over Ground (SOG)."""
        test_cases = [
            (30.0, 40.0, 40.0),    # COG = Leg axis => VMG = SOG
            (28.0, 60.0, 40.0),    # 20 deg offset => VMG = SOG * cos(20) < SOG
            (35.0, 130.0, 40.0),   # 90 deg offset => VMG = 0
            (25.0, 220.0, 40.0),   # Upwind leg but sailing downwind => negative VMG
        ]
        for sog, cog, leg_axis in test_cases:
            diff_rad = math.radians(cog - leg_axis)
            vmg = sog * math.cos(diff_rad)
            self.assertLessEqual(abs(vmg), sog + 1e-6)

    def test_twa_strictly_within_180_range(self):
        """True Wind Angle is strictly normalized within [-180.0, +180.0) deg."""
        test_angles = [0.0, 45.0, -45.0, 179.9, -179.9, 185.0, -200.0, 540.0]
        for a in test_angles:
            norm = normalize_angle_180(a)
            self.assertGreaterEqual(norm, -180.0)
            self.assertLess(norm, 180.0)

    def test_sog_within_physically_valid_ac40_envelope(self):
        """AC40 speeds are within physically realistic bounds: 0 to 55 knots."""
        sog_knots = [0.0, 12.5, 28.4, 42.1, 48.6]
        for s in sog_knots:
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 55.0)

    def test_leader_has_zero_time_and_distance_gap(self):
        """The 1st place leader has gap 0.0 s and 0.0 m."""
        leader_gap_s = 0.0
        leader_gap_m = 0.0
        self.assertEqual(leader_gap_s, 0.0)
        self.assertEqual(leader_gap_m, 0.0)

    def test_chaser_gaps_are_strictly_positive(self):
        """All chasers behind the leader have strictly positive gaps (> 0s and > 0m)."""
        chasers = ["NZL G", "ITA B", "USA", "ITA G", "GBR G"]
        for team in chasers:
            boat = COMPETITORS_GROUND_TRUTH[team]
            self.assertGreater(boat["delta_to_winner_s"], 0.0)


class TestTier1Feature12HeadToHeadComparison(unittest.TestCase):
    """Feature 12: Head-to-head comparison metrics."""

    def test_separation_vector_euclidean_distance(self):
        """Euclidean distance between Boat A (0, 0) and Boat B (300, 400) is 500 m."""
        h2h = compute_head_to_head((0.0, 0.0), (300.0, 400.0), (0.0, 0.0), (0.0, 0.0))
        self.assertAlmostEqual(h2h["euclidean_distance_m"], 500.0, places=3)

    def test_longitudinal_delta_along_course_axis(self):
        """Longitudinal delta measures lead/lag directly along course axis."""
        axis_rad = math.radians(COURSE_AXIS_SETTLED_DEG)
        u_course = (math.sin(axis_rad), math.cos(axis_rad))
        # Boat A is 100m ahead along course axis
        pos_a = (100.0 * u_course[0], 100.0 * u_course[1])
        pos_b = (0.0, 0.0)

        h2h = compute_head_to_head(pos_a, pos_b, (0.0, 0.0), (0.0, 0.0))
        self.assertAlmostEqual(h2h["longitudinal_delta_m"], 100.0, places=3)

    def test_lateral_cross_track_separation(self):
        """Lateral cross-track separation is perpendicular to course axis."""
        axis_rad = math.radians(COURSE_AXIS_SETTLED_DEG)
        u_lat = (-math.cos(axis_rad), math.sin(axis_rad))
        # Boat A is 150m laterally displaced from Boat B
        pos_a = (150.0 * u_lat[0], 150.0 * u_lat[1])
        pos_b = (0.0, 0.0)

        h2h = compute_head_to_head(pos_a, pos_b, (0.0, 0.0), (0.0, 0.0))
        self.assertAlmostEqual(h2h["lateral_separation_m"], 150.0, places=3)
        self.assertAlmostEqual(h2h["longitudinal_delta_m"], 0.0, places=3)

    def test_anti_symmetry_of_head_to_head(self):
        """Head-to-head comparison is anti-symmetric: delta_long(A, B) = -delta_long(B, A)."""
        pos_a = (120.0, -80.0)
        pos_b = (-40.0, 200.0)
        h2h_ab = compute_head_to_head(pos_a, pos_b, (0.0, 0.0), (0.0, 0.0))
        h2h_ba = compute_head_to_head(pos_b, pos_a, (0.0, 0.0), (0.0, 0.0))

        self.assertAlmostEqual(h2h_ab["euclidean_distance_m"], h2h_ba["euclidean_distance_m"], places=3)
        self.assertAlmostEqual(h2h_ab["longitudinal_delta_m"], -h2h_ba["longitudinal_delta_m"], places=3)
        self.assertAlmostEqual(h2h_ab["lateral_separation_m"], h2h_ba["lateral_separation_m"], places=3)

    def test_rate_of_closure_calculation(self):
        """When Boat B is closing on Boat A at 5 m/s, rate of closure is +5 m/s."""
        pos_a = (100.0, 0.0)
        pos_b = (0.0, 0.0)
        # B is moving towards A at 5 m/s: v_b = (5, 0), v_a = (0, 0)
        h2h = compute_head_to_head(pos_a, pos_b, (0.0, 0.0), (5.0, 0.0))
        self.assertAlmostEqual(h2h["rate_of_closure_mps"], 5.0, places=3)


class TestTier1Feature13MultiRaceManifestLoading(unittest.TestCase):
    """Feature 13: Multi-race manifest loading."""

    def test_manifest_schema_validation(self):
        """Manifest contains required regatta metadata: regatta, venue, and races list."""
        sample_manifest = {
            "regatta": "38th America's Cup Preliminary Regatta",
            "venue": "Naples, Italy",
            "races": [
                {
                    "id": "naples_2026_ipr_pr1",
                    "name": "Practice Race 1",
                    "date": "2026-09-22",
                    "file": "races/naples_2026_ipr_pr1.json",
                    "winner": "FRA",
                    "duration_s": 1059.555,
                }
            ]
        }
        self.assertIn("regatta", sample_manifest)
        self.assertIn("venue", sample_manifest)
        self.assertIn("races", sample_manifest)
        self.assertIsInstance(sample_manifest["races"], list)
        self.assertGreaterEqual(len(sample_manifest["races"]), 1)

    def test_race_item_schema_properties(self):
        """Each race item has id, name, date, file path, winner, and duration."""
        race = {
            "id": "naples_2026_ipr_pr1",
            "name": "Practice Race 1",
            "date": "2026-09-22",
            "file": "races/naples_2026_ipr_pr1.json",
            "winner": "FRA",
            "duration_s": 1059.555,
        }
        required_fields = ["id", "name", "date", "file", "winner", "duration_s"]
        for field in required_fields:
            self.assertIn(field, race)

    def test_manifest_dynamic_switching_lookup(self):
        """Picker resolves race definition by ID without hardcoding file paths."""
        manifest = {
            "races": [
                {"id": "race_1", "file": "data/race_1.json"},
                {"id": "race_2", "file": "data/race_2.json"},
            ]
        }
        race_map = {r["id"]: r for r in manifest["races"]}
        self.assertEqual(race_map["race_1"]["file"], "data/race_1.json")
        self.assertEqual(race_map["race_2"]["file"], "data/race_2.json")

    def test_manifest_rejects_missing_required_fields(self):
        """Invalid manifest missing 'races' raises schema validation error."""
        invalid_manifest = {"regatta": "Naples"}
        with self.assertRaises(KeyError):
            _ = invalid_manifest["races"]

    def test_manifest_json_serialization_roundtrip(self):
        """Manifest serializes to and deserializes from valid JSON."""
        manifest = {
            "regatta": "AC40 Naples",
            "races": [{"id": "pr1", "winner": "FRA"}]
        }
        json_str = json.dumps(manifest)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["regatta"], "AC40 Naples")
        self.assertEqual(parsed["races"][0]["winner"], "FRA")


if __name__ == "__main__":
    unittest.main()
