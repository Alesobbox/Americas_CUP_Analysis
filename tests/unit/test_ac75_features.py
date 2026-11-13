"""Acceptance tests for AC75 causal alignment, steady windows, and feature extraction (T06)."""
import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.kinematic_ml.contracts import (
    MOTION_PREDICTOR_ALLOWLIST,
    SteadyWindowRecord,
    leg_course_vmg_mps,
    validate_feature_separation,
    wind_relative_vmg_mps,
)
from pipeline.kinematic_ml.maneuvers import circular_diff_deg
from pipeline.kinematic_ml.features import (
    compute_circular_duration_weighted_mean,
    compute_duration_weighted_mean,
    extract_partition_artifacts,
    select_wind_at_time,
    validate_stream_support,
)


class TestAC75Features(unittest.TestCase):
    def test_post_issue_immutability(self):
        """Verify that SteadyWindowRecord is immutable and post-issue mutation raises FrozenInstanceError."""
        rec = SteadyWindowRecord(
            attempt_id="test_attempt",
            team_id="ac37:LUNA_ROSSA",
            t_start_ms=1000,
            t_end_ms=6000,
            duration_s=5.0,
            sog_mps=20.0,
            tws_mps=8.0,
            twa_sin=0.7071,
            twa_cos=0.7071,
            tack_side=1,
            leg_type=1,
        )
        with self.assertRaises((AttributeError, TypeError)):
            rec.sog_mps = 25.0  # type: ignore

    def test_heading_cog_leeway_and_vmg(self):
        """Verify that heading differs from COG under leeway and ground-relative VMG uses COG."""
        # Vessel heading 040 deg, with 5 deg leeway to starboard -> COG = 045 deg
        heading_deg = 40.0
        cog_deg = 45.0
        leeway_deg = circular_diff_deg(cog_deg, heading_deg)
        self.assertEqual(leeway_deg, 5.0)

        sog_mps = 20.0
        course_axis_deg = 0.0  # Upwind leg bearing 000
        # Leg 1 (upwind): bearing is 000 deg.
        # VMG along course axis should be sog * cos(cog - bearing) = 20 * cos(45 deg) = 20 * sqrt(2)/2 ~= 14.142 m/s
        vmg_course = leg_course_vmg_mps(sog_mps, cog_deg, course_axis_deg, leg=1)
        expected_vmg = sog_mps * math.cos(math.radians(45.0))
        self.assertAlmostEqual(vmg_course, expected_vmg, places=3)

        # Wind-relative VMG with TWD = 000:
        # upwind VMG = sog * cos(cog - twd)
        vmg_wind = wind_relative_vmg_mps(sog_mps, cog_deg, twd_deg=0.0, upwind=True)
        self.assertAlmostEqual(vmg_wind, expected_vmg, places=3)

    def test_wind_isolation_no_anonymous_pooling(self):
        """Verify that one boat's wind sensor cannot be pooled to another boat."""
        boat_a_id = "boat_a"
        boat_b_id = "boat_b"

        # Boat A has fresh wind at t=5000: tws=10.0, twd=180.0
        boat_a_wind = [(5000, 10.0, 180.0)]
        # Boat B has no local wind
        boat_b_wind = []
        # Course official wind at t=4000: tws=8.0, twd=190.0
        course_wind = [(4000, 8.0, 190.0)]

        # Query for Boat A at t=5500: should get boat A local wind
        tws_a, twd_a, src_a = select_wind_at_time(boat_a_id, 5500, boat_a_wind, course_wind)
        self.assertEqual(src_a, "boat_local")
        self.assertEqual(tws_a, 10.0)

        # Query for Boat B at t=5500: must NOT receive Boat A's wind; falls back to course wind
        tws_b, twd_b, src_b = select_wind_at_time(boat_b_id, 5500, boat_b_wind, course_wind)
        self.assertEqual(src_b, "course_official")
        self.assertEqual(tws_b, 8.0)

    def test_stale_and_gapped_wind_fails_support(self):
        """Verify that 1-Hz wind passes when fresh, but stale or gapped wind fails."""
        # 1-Hz wind frames over 5-second window [10000, 15000]
        # Frame every 1000ms: 10000, 11000, 12000, 13000, 14000, 15000
        ts_1hz = [10000, 11000, 12000, 13000, 14000, 15000]
        supp_valid = validate_stream_support(ts_1hz, 10000, 15000, max_gap_ms=2500)
        self.assertTrue(supp_valid["valid"])
        self.assertFalse(supp_valid["dropout_exceeded"])
        self.assertGreaterEqual(supp_valid["supported_fraction"], 0.95)

        # Wind with 3500ms gap (> max_gap_ms 2500)
        ts_gapped = [10000, 11000, 14500, 15000]
        supp_invalid = validate_stream_support(ts_gapped, 10000, 15000, max_gap_ms=2500)
        self.assertFalse(supp_invalid["valid"])
        self.assertTrue(supp_invalid["dropout_exceeded"])

        # Stale wind selection (> 2500ms old)
        course_wind = [(1000, 8.0, 180.0)]
        tws, twd, src = select_wind_at_time("boat_a", 5000, [], course_wind, max_stale_ms=2500)
        self.assertIsNone(tws)
        self.assertEqual(src, "stale_or_missing")

    def test_duration_weighting_cadence_invariance(self):
        """Verify that uneven sampling cadence does not bias duration-weighted mean."""
        # Over interval [0, 10_000] ms:
        # State 1: 10 m/s for first 2 seconds [0, 2000] (20% of time)
        # State 2: 20 m/s for next 8 seconds [2000, 10000] (80% of time)
        # Analytical true duration-weighted mean = 0.20 * 10 + 0.80 * 20 = 18.0 m/s

        # Case A: High-rate sampling during State 1 (100 samples) and low-rate during State 2 (4 samples)
        # Unweighted average would be heavily biased towards 10 m/s (~10.4 m/s)
        times_ms = [i * 20 for i in range(100)] + [2000, 4000, 6000, 8000]
        values = [10.0] * 100 + [20.0] * 4

        dw_mean = compute_duration_weighted_mean(times_ms, values, 0, 10_000)
        self.assertIsNotNone(dw_mean)
        self.assertAlmostEqual(dw_mean, 18.0, places=1)

    def test_feature_allowlist_enforcement(self):
        """Verify that motion predictor feature dictionary strictly obeys MOTION_PREDICTOR_ALLOWLIST."""
        valid_features = {
            "team_id": "ac37:INEOS",
            "tws_mps": 7.5,
            "twa_sin": 0.6,
            "twa_cos": 0.8,
            "tack_side": 1,
            "leg_type": 1,
            "heading_cog_offset_deg": 3.0,
            "course_wind_angle_deg": 40.0,
            "practice_domain": 0,
        }
        # Should not raise
        validate_feature_separation(valid_features, task_type="motion")

        # Injected leaky future predictor must raise ValueError
        invalid_features = dict(valid_features)
        invalid_features["future_speed_mps"] = 24.5
        with self.assertRaises(ValueError):
            validate_feature_separation(invalid_features, task_type="motion")

    def test_extract_partition_causal_prestart_and_hindsight_isolation(self):
        """Verify prestart context enforces causal gun-minus-latency cutoff with zero invented defaults."""
        race_start_ms = 1_725_000_100_000
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            meta_path = tmp / "att_meta.json"
            meta_path.write_text(
                json.dumps({
                    "session_id": "att_causal",
                    "session_name": "20240901_test",
                    "race_start_ms": race_start_ms,
                    "causal_latency_ms": 6000,
                    "competitor_map": {"boat_a": "ac37:ETNZ", "boat_b": "ac37:INEOS"},
                    "course_wind_asset": "course_wind",
                }),
                encoding="utf-8",
            )

            def _write_part(pq_path: Path, wind_rows: list[tuple[int, float, float]]) -> None:
                recs = []
                for ts_ms, tws_v, twd_v in wind_rows:
                    recs.append((ts_ms, "true_wind_speed", "course_wind", None, None, None, None, tws_v))
                    recs.append((ts_ms, "true_wind_direction", "course_wind", None, None, None, twd_v, None))
                # Minimal steady race windows after race_start_ms at distinct weather (tws=12.4, twd=225)
                for sec in range(2, 16):
                    ts = race_start_ms + sec * 1000
                    for aid in ("boat_a", "boat_b"):
                        recs.append((ts, "heading", aid, 20.0, None, None, None, None))
                        recs.append((ts, "speed_over_ground", aid, None, 21.0, None, None, None))
                        recs.append((ts, "course_over_ground", aid, None, None, 22.0, None, None))
                        recs.append((ts, "true_wind_speed", aid, None, None, None, None, 12.4))
                        recs.append((ts, "true_wind_direction", aid, None, None, None, 225.0, None))
                table = pa.table({
                    "timestamp_ms": pa.array([r[0] for r in recs], type=pa.int64()),
                    "channel": pa.array([r[1] for r in recs], type=pa.string()),
                    "asset_id": pa.array([r[2] for r in recs], type=pa.string()),
                    "heading_deg": pa.array([r[3] for r in recs], type=pa.float64()),
                    "sog_mps": pa.array([r[4] for r in recs], type=pa.float64()),
                    "cog_deg": pa.array([r[5] for r in recs], type=pa.float64()),
                    "twd_deg": pa.array([r[6] for r in recs], type=pa.float64()),
                    "tws_mps": pa.array([r[7] for r in recs], type=pa.float64()),
                })
                pq.write_table(table, pq_path)

            # 1. Only post-cutoff course wind (within 6s latency window): must mark prestart unavailable
            pq_post = tmp / "part_post.parquet"
            _write_part(pq_post, [(race_start_ms - 3000, 15.0, 210.0), (race_start_ms + 5000, 15.5, 212.0)])
            out_post = extract_partition_artifacts(pq_post, meta_path)
            rc_post = out_post["race_course_summary"]
            self.assertEqual(rc_post["prestart_context_status"], "unavailable")
            self.assertIsNone(rc_post["prestart_tws_mps"])
            self.assertIsNone(rc_post["prestart_twd_deg"])
            self.assertFalse(rc_post["prestart_is_whole_race_average"])
            self.assertFalse(rc_post["prestart_is_invented_default"])
            self.assertTrue(rc_post["hindsight_whole_race_weather"]["is_whole_race_average"])

            # 2. Causal pre-gun course wind (<= race_start_ms - 6000) differs cleanly from hindsight race mean
            pq_pre = tmp / "part_pre.parquet"
            _write_part(pq_pre, [(race_start_ms - 10_000, 7.2, 145.0), (race_start_ms - 2000, 15.0, 210.0)])
            out_pre = extract_partition_artifacts(pq_pre, meta_path)
            rc_pre = out_pre["race_course_summary"]
            self.assertEqual(rc_pre["prestart_context_status"], "available")
            self.assertAlmostEqual(rc_pre["prestart_tws_mps"], 7.2, places=2)
            self.assertAlmostEqual(rc_pre["prestart_twd_deg"], 145.0, places=1)
            self.assertLessEqual(rc_pre["prestart_available_at_ms"], race_start_ms)
            self.assertFalse(rc_pre["prestart_is_whole_race_average"])
            self.assertAlmostEqual(rc_pre["hindsight_whole_race_weather"]["mean_tws_mps"], 12.4, places=2)


if __name__ == "__main__":
    unittest.main()
