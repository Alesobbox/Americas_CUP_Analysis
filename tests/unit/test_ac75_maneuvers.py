"""Focused unit tests for AC75 maneuver detection, classification, and recovery (T07)."""
import unittest

from pipeline.kinematic_ml.maneuvers import (
    build_maneuver_review_sample,
    circular_diff_deg,
    classify_turn_type,
    compute_turn_dynamics,
    detect_angular_turns,
    filter_overlapping_maneuvers,
)


class TestAC75Maneuvers(unittest.TestCase):
    def test_constant_speed_tack_detected_without_speed_loss(self):
        """Verify that a turn is detected purely on angular rotation even at constant speed."""
        # Tacking through wind (TWD = 180): heading goes from 140 to 220 at constant 20 m/s
        heading_recs = []
        # Include pre-turn SOG history in [t_start - 7000, t_start - 2000]
        sog_recs = [(-6000, 20.0), (-4000, 20.0), (-1500, 20.0), (0, 20.0)]
        for i in range(25):
            t_ms = 1000 + i * 500  # 12.5 seconds total
            hdg = 140.0 + (i / 24.0) * 80.0  # 80 deg rotation across 180
            heading_recs.append((t_ms, hdg))
            sog_recs.append((t_ms, 20.0))  # strictly constant speed

        twd_recs = [(500, 180.0), (10000, 180.0)]
        turns = detect_angular_turns(heading_recs, twd_recs)

        self.assertEqual(len(turns), 1)
        turn = turns[0]
        self.assertGreaterEqual(turn["rotation_deg"], 65.0)
        self.assertEqual(turn["turn_type"], "tack")

        # Compute dynamics: exit speed is 20, min speed is 20, recovery_s is 0
        dyn = compute_turn_dynamics(turn, sog_recs)
        self.assertEqual(dyn["entry_speed_mps"], 20.0)
        self.assertEqual(dyn["exit_speed_mps"], 20.0)
        self.assertEqual(dyn["min_speed_mps"], 20.0)
        self.assertFalse(dyn["censoring"])

    def test_isolated_speed_loss_without_rotation_not_detected(self):
        """Verify that deceleration in a straight line produces zero detected maneuvers."""
        heading_recs = []
        sog_recs = []
        for i in range(30):
            t_ms = 1000 + i * 500
            heading_recs.append((t_ms, 45.0))  # steady heading
            # Huge speed drop from 25 m/s to 5 m/s
            speed = 25.0 - (i / 29.0) * 20.0
            sog_recs.append((t_ms, speed))

        turns = detect_angular_turns(heading_recs)
        self.assertEqual(len(turns), 0, "Straight deceleration must not trigger turn detector")

    def test_causal_wind_lookup_never_sees_future_twd(self):
        """Verify that turn classifier uses wind strictly as-of turn onset, not future shifts."""
        heading_recs = [(1000 + i * 500, 40.0 + i * 4.0) for i in range(25)]
        # Wind was 0 deg at onset (1000ms), but shifts to 90 deg at 5000ms
        twd_recs = [(500, 0.0), (5000, 90.0)]
        turns = detect_angular_turns(heading_recs, twd_recs)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["as_of_twd_deg"], 0.0)

        # If wind only exists AFTER turn onset, as_of_twd_deg must be None (no future leak)
        future_only_twd = [(5000, 90.0)]
        turns_no_past_wind = detect_angular_turns(heading_recs, future_only_twd)
        self.assertEqual(len(turns_no_past_wind), 1)
        self.assertIsNone(turns_no_past_wind[0]["as_of_twd_deg"])
        self.assertEqual(turns_no_past_wind[0]["turn_type"], "unsupported_missing_wind")

    def test_missing_pre_turn_speed_never_reads_in_turn_future_speed(self):
        """Verify that missing pre-turn reference speed returns None instead of reading in-turn/future speed."""
        turn = {
            "start_ms": 10000,
            "end_ms": 15000,
            "duration_s": 5.0,
            "rotation_deg": 75.0,
            "turn_type": "tack",
        }
        # Only samples during and after the turn (no samples in [3000, 8000])
        sog_recs = [(10000, 19.0), (12000, 14.0), (16000, 20.0)]
        dyn = compute_turn_dynamics(turn, sog_recs)
        self.assertIsNone(dyn["entry_speed_mps"])
        self.assertIsNone(dyn["recovery_s"])
        self.assertTrue(dyn["censoring"])
        self.assertEqual(dyn["censoring_reason"], "unavailable_entry_reference")

    def test_censored_recovery_records_explicit_censoring(self):
        """Verify that a boat that never recovers speed gets flagged with censoring=True."""
        turn = {
            "start_ms": 10000,
            "end_ms": 15000,
            "duration_s": 5.0,
            "rotation_deg": 75.0,
            "turn_type": "gybe",
        }
        # Boat entered at 22 m/s in [3000, 8000], exited at 8 m/s, and stayed at 8 m/s
        sog_recs = [
            (4000, 22.0), (6000, 22.0), (7500, 22.0),
            (11000, 12.0), (13000, 8.0),
            (15500, 8.0), (20000, 8.0), (30000, 8.0), (46000, 8.0)
        ]
        dyn = compute_turn_dynamics(turn, sog_recs, max_recovery_ms=30000)
        self.assertTrue(dyn["censoring"])
        self.assertEqual(dyn["recovery_s"], 30.0)

    def test_circular_diff_deg_wraparound(self):
        """Test heading angle difference across 0/360 boundary."""
        self.assertEqual(circular_diff_deg(10.0, 350.0), 20.0)
        self.assertEqual(circular_diff_deg(350.0, 10.0), -20.0)
        self.assertEqual(circular_diff_deg(180.0, 180.0), 0.0)

    def test_overlapping_intervals_not_double_counted(self):
        """Verify that overlapping turns are filtered and not double counted."""
        t1 = {"start_ms": 1000, "end_ms": 6000, "rotation_deg": 70.0}
        t2 = {"start_ms": 4000, "end_ms": 9000, "rotation_deg": 85.0}  # Overlaps t1, larger rotation
        t3 = {"start_ms": 12000, "end_ms": 17000, "rotation_deg": 75.0}

        filtered = filter_overlapping_maneuvers([t1, t2, t3])
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["rotation_deg"], 85.0)
        self.assertEqual(filtered[1]["start_ms"], 12000)

    def test_maneuver_review_sample_provisional_status(self):
        """Verify review sample creation and explicit provisional status."""
        clips = [{"turn_id": f"t_{i}", "team_id": "ac37:INEOS"} for i in range(150)]
        windows = [{"win_id": f"w_{i}", "duration_s": 60.0} for i in range(80)]
        sample = build_maneuver_review_sample(clips, windows, max_candidate_clips=120, max_continuous_windows=60)
        self.assertEqual(sample["review_status"], "provisional")
        self.assertEqual(sample["sample_counts"]["candidate_clips"], 120)
        self.assertEqual(sample["sample_counts"]["continuous_windows"], 60)


if __name__ == "__main__":
    unittest.main()
