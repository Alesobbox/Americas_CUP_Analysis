"""Adversarial Stress Test and Ingestion Benchmark for Milestone 1.

Targets:
1. pipeline/ingest.py - Circular shortest-arc interpolation with adversarial angle pairs
2. pipeline/ingest.py - Series cleaning, deduplication, sorting, and resampling with synthetic stress streams
3. Real telemetry dataset ingestion benchmark on Data/26 09 22 NAP IPR PR1.jsonl (<60s requirement)
"""

import math
import os
import sys
import time
import json
import tempfile
import unittest
from typing import List, Tuple

# Add workspace root to sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from pipeline.ingest import (
    interpolate_linear,
    interpolate_circular_deg,
    compute_twa,
    compute_vmg,
    clean_and_sort_series,
    clean_and_sort_xy_series,
    resample_scalar_series,
    resample_circular_series,
    resample_xy_series,
    IngestionPipeline,
    ingest_telemetry_file,
)
from pipeline.config import (
    COURSE_AXIS_DEG,
    SAMPLE_INTERVAL_MS,
    COMPETITORS,
    MARKS,
    OFFICIAL_WIND_ASSET_ID,
)


class TestAdversarialCircularInterpolation(unittest.TestCase):
    """Stress tests circular shortest-arc interpolation with adversarial angle pairs."""

    def test_pair_359_to_1(self):
        """Angle pair (359°, 1°): Shortest arc is 2° clockwise across 0° North, midpoint must be 0.0°."""
        # Check midpoint
        mid = interpolate_circular_deg(150, 100, 200, 359.0, 1.0)
        self.assertAlmostEqual(mid, 0.0, places=6)

        # Check fine trajectory samples: u in [0, 1]
        for step in range(11):
            u = step / 10.0
            t = 100 + u * 100
            val = interpolate_circular_deg(t, 100, 200, 359.0, 1.0)
            # Delta is +2°. Angle should be (359 + u * 2) % 360
            expected = (359.0 + u * 2.0) % 360.0
            self.assertAlmostEqual(val, expected, places=5)
            # Ensure it never goes through the long arc (e.g., ~180°)
            self.assertTrue(val >= 359.0 or val <= 1.0)

    def test_pair_1_to_359(self):
        """Angle pair (1°, 359°): Shortest arc is 2° counter-clockwise across 0°, midpoint must be 0.0°."""
        mid = interpolate_circular_deg(150, 100, 200, 1.0, 359.0)
        self.assertAlmostEqual(mid, 0.0, places=6)

        for step in range(11):
            u = step / 10.0
            t = 100 + u * 100
            val = interpolate_circular_deg(t, 100, 200, 1.0, 359.0)
            # Delta is -2°. Angle should be (1.0 - u * 2) % 360
            expected = (1.0 - u * 2.0) % 360.0
            self.assertAlmostEqual(val, expected, places=5)
            self.assertTrue(val >= 359.0 or val <= 1.0)

    def test_pair_179_to_neg179(self):
        """Angle pair (179°, -179°): -179° = 181°, shortest arc is 2° across 180°, midpoint must be 180.0°."""
        mid = interpolate_circular_deg(150, 100, 200, 179.0, -179.0)
        self.assertAlmostEqual(mid, 180.0, places=6)

        # Reverse direction: (-179°, 179°)
        mid_rev = interpolate_circular_deg(150, 100, 200, -179.0, 179.0)
        self.assertAlmostEqual(mid_rev, 180.0, places=6)

        # Check progression: should remain in [179.0, 181.0]
        for step in range(11):
            u = step / 10.0
            t = 100 + u * 100
            val = interpolate_circular_deg(t, 100, 200, 179.0, -179.0)
            self.assertTrue(179.0 <= val <= 181.0)

    def test_pair_0_to_360(self):
        """Angle pair (0°, 360°): Equivalent angles, shortest arc is 0°, interpolation must stay 0.0°."""
        for step in range(11):
            u = step / 10.0
            t = 100 + u * 100
            val = interpolate_circular_deg(t, 100, 200, 0.0, 360.0)
            self.assertAlmostEqual(val, 0.0, places=6)

    def test_pair_720_to_neg360(self):
        """Angle pair (720°, -360°): Both are multiples of 360°, shortest arc is 0°, output must be 0.0°."""
        for step in range(11):
            u = step / 10.0
            t = 100 + u * 100
            val = interpolate_circular_deg(t, 100, 200, 720.0, -360.0)
            self.assertAlmostEqual(val, 0.0, places=6)

    def test_exact_half_circle_antipodal_pairs(self):
        """Antipodal angle pairs (diff = 180°) must not produce NaN, inf, or values outside [0, 360)."""
        antipodal_pairs = [
            (0.0, 180.0),
            (180.0, 0.0),
            (90.0, 270.0),
            (270.0, 90.0),
            (45.0, 225.0),
            (315.0, 135.0),
        ]
        for a0, a1 in antipodal_pairs:
            for step in range(11):
                t = 100 + (step / 10.0) * 100
                val = interpolate_circular_deg(t, 100, 200, a0, a1)
                self.assertFalse(math.isnan(val))
                self.assertFalse(math.isinf(val))
                self.assertGreaterEqual(val, 0.0)
                self.assertLess(val, 360.0)

    def test_extreme_rotations_and_multi_turns(self):
        """Angles with large multiples of 360° must normalize and interpolate along shortest arc."""
        # 3600.5° (equivalent to 0.5°) and 3599.5° (equivalent to 359.5°)
        # Shortest arc is 1° across 0°
        mid = interpolate_circular_deg(150, 100, 200, 3600.5, 3599.5)
        self.assertAlmostEqual(mid, 0.0, places=5)

    def test_instantaneous_same_timestamp(self):
        """t0 == t1 must return deg0 % 360.0 without division by zero."""
        val1 = interpolate_circular_deg(100, 100, 100, 359.0, 1.0)
        self.assertAlmostEqual(val1, 359.0, places=6)
        val2 = interpolate_circular_deg(100, 100, 100, 720.0, 180.0)
        self.assertAlmostEqual(val2, 0.0, places=6)


class TestAdversarialResamplingStreams(unittest.TestCase):
    """Stress tests resampling routines with pathological and irregular streams."""

    def test_zero_length_inputs(self):
        """Zero-length inputs must return empty or zero-filled output without throwing exceptions."""
        grid = [100, 200, 300, 400]

        # clean_and_sort_series
        t_clean, v_clean = clean_and_sort_series([])
        self.assertEqual(t_clean, [])
        self.assertEqual(v_clean, [])

        # clean_and_sort_xy_series
        t_xy, x_xy, y_xy = clean_and_sort_xy_series([])
        self.assertEqual(t_xy, [])
        self.assertEqual(x_xy, [])
        self.assertEqual(y_xy, [])

        # resample_scalar_series
        res_scalar = resample_scalar_series([], [], grid)
        self.assertEqual(res_scalar, [0.0, 0.0, 0.0, 0.0])

        # resample_circular_series
        res_circ = resample_circular_series([], [], grid)
        self.assertEqual(res_circ, [0.0, 0.0, 0.0, 0.0])

        # resample_xy_series
        res_x, res_y = resample_xy_series([], [], [], grid)
        self.assertEqual(res_x, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(res_y, [0.0, 0.0, 0.0, 0.0])

        # Empty grid
        self.assertEqual(resample_scalar_series([100], [5.0], []), [])
        self.assertEqual(resample_circular_series([100], [5.0], []), [])

    def test_single_element_inputs(self):
        """Single-element streams must broadcast their value across all grid points."""
        grid = [50, 100, 150, 200]

        res_scalar = resample_scalar_series([100], [42.5], grid)
        self.assertEqual(res_scalar, [42.5, 42.5, 42.5, 42.5])

        # Single circular angle (e.g., 725° -> 5°)
        res_circ = resample_circular_series([100], [725.0], grid)
        self.assertEqual(res_circ, [5.0, 5.0, 5.0, 5.0])

    def test_duplicate_timestamps_handling(self):
        """Duplicate adjacent and non-adjacent timestamps must overwrite with latest value and deduplicate."""
        raw_stream = [
            (100, 10.0),
            (100, 12.0),
            (100, 15.0),  # final for 100 is 15.0
            (200, 20.0),
            (200, 25.0),  # final for 200 is 25.0
            (300, 30.0),
        ]
        times, values = clean_and_sort_series(raw_stream)
        self.assertEqual(times, [100, 200, 300])
        self.assertEqual(values, [15.0, 25.0, 30.0])

        # 2D coordinate series deduplication
        raw_xy = [
            (100, 1.0, 2.0),
            (100, 3.0, 4.0),
            (200, 5.0, 6.0),
        ]
        t_xy, xs, ys = clean_and_sort_xy_series(raw_xy)
        self.assertEqual(t_xy, [100, 200])
        self.assertEqual(xs, [3.0, 5.0])
        self.assertEqual(ys, [4.0, 6.0])

    def test_inverted_out_of_order_timestamps(self):
        """Streams received in reverse or scrambled order must be strictly sorted."""
        scrambled = [
            (500, 50.0),
            (100, 10.0),
            (400, 40.0),
            (200, 20.0),
            (300, 30.0),
            (200, 25.0),  # duplicate of out-of-order 200
        ]
        times, values = clean_and_sort_series(scrambled)
        self.assertEqual(times, [100, 200, 300, 400, 500])
        self.assertEqual(values, [10.0, 25.0, 30.0, 40.0, 50.0])

    def test_irregular_large_gaps_resampling(self):
        """Resampling across massive temporal gaps (e.g. 60 seconds) must interpolate linearly without drift."""
        # Gap from t=1000 to t=61000 (60s)
        times = [1000, 61000]
        values = [10.0, 70.0]  # rate: 1.0 per 1000 ms
        grid = [1000, 16000, 31000, 46000, 61000]

        res = resample_scalar_series(times, values, grid)
        self.assertEqual(len(res), 5)
        self.assertAlmostEqual(res[0], 10.0)
        self.assertAlmostEqual(res[1], 25.0)
        self.assertAlmostEqual(res[2], 40.0)
        self.assertAlmostEqual(res[3], 55.0)
        self.assertAlmostEqual(res[4], 70.0)

    def test_dense_samples_and_sub_millisecond_jitter(self):
        """Resampling with hundreds of samples between grid points must bracket and interpolate correctly."""
        # Grid at 100, 200, 300
        # 1000 raw samples between 100 and 300
        raw_times = list(range(100, 301))
        raw_values = [float(t) for t in raw_times]

        grid = [50, 100, 150, 200, 250, 300, 350]
        res = resample_scalar_series(raw_times, raw_values, grid)

        self.assertAlmostEqual(res[0], 100.0)  # clamped
        self.assertAlmostEqual(res[1], 100.0)  # exact start
        self.assertAlmostEqual(res[2], 150.0)  # exact match
        self.assertAlmostEqual(res[3], 200.0)
        self.assertAlmostEqual(res[4], 250.0)
        self.assertAlmostEqual(res[5], 300.0)
        self.assertAlmostEqual(res[6], 300.0)  # clamped


class TestAdversarialSyntheticDatasetPipeline(unittest.TestCase):
    """Stress tests the IngestionPipeline with corrupted/adversarial synthetic JSONL inputs."""

    def test_synthetic_jsonl_with_malformed_and_edge_records(self):
        """Pipeline must ignore irrelevant lines, handle empty boat telemetry, and complete gracefully."""
        fra_uuid = "42e39310-fef5-4c5d-b099-a599aad5ddbb"
        unknown_uuid = "00000000-0000-0000-0000-000000000000"

        records = [
            # 1. Random comment or noise line
            {"noise": "ignore this"},
            # 2. Session definition
            {
                "session": {
                    "id": "stress-test-session",
                    "name": "Stress Regatta",
                    "race_state": "RACE_STATE_RACING",
                    "race_type": "RACE_TYPE_FLEET",
                    "race_start": "10000",
                    "window_start": "10000",
                    "window_end": "10500",
                    "official_wind_asset_id": OFFICIAL_WIND_ASSET_ID,
                    "race_course": {"course_axis": COURSE_AXIS_DEG, "course_length": 2259.0},
                    "race_boundary": {"polygon": {"coordinates": [{"x": 14.2, "y": 40.8}]}},
                    "safety_boundary": {"polygon": {"coordinates": [{"x": 14.2, "y": 40.8}]}},
                }
            },
            # 3. Telemetry for untracked asset (must be skipped cleanly)
            {"telemetry": {"asset_id": unknown_uuid, "timestamp": "10100", "heading": {"value": 180.0}}},
            # 4. Inverted/scrambled telemetry for FRA
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "10500", "heading": {"value": 1.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "10000", "heading": {"value": 359.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "10250", "heading": {"value": 0.0}}},
            # SOG packets with duplicates
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "10000", "speed_over_ground": {"value": 10.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "10000", "speed_over_ground": {"value": 15.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "10500", "speed_over_ground": {"value": 20.0}}},
        ]

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as tf:
            for r in records:
                tf.write(json.dumps(r) + "\n")
            temp_path = tf.name

        try:
            pipeline = IngestionPipeline(file_path=temp_path, sample_interval_ms=100)
            res = pipeline.process()

            # Grid timestamps: 10000, 10100, 10200, 10300, 10400, 10500 -> 6 frames
            self.assertEqual(len(res.grid_timestamps_ms), 6)

            # Check FRA boat
            fra = res.boats["FRA"]
            self.assertEqual(len(fra.heading), 6)
            # Heading should interpolate shortest arc across 0°
            self.assertAlmostEqual(fra.heading[0], 359.0, places=4)
            self.assertAlmostEqual(fra.heading[-1], 1.0, places=4)

            # Check boats with 0 records: should have zero arrays without crashing
            nzl_g = res.boats["NZL G"]
            self.assertEqual(len(nzl_g.heading), 6)
            self.assertEqual(nzl_g.heading, [0.0] * 6)

            # Check marks with 0 records: should use static target without crashing
            rm8 = res.marks["RM8"]
            self.assertEqual(len(rm8.x), 6)
            self.assertEqual(rm8.x, [rm8.target_x] * 6)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


def run_real_dataset_benchmark() -> dict:
    """Runs ingestion benchmark on Data/26 09 22 NAP IPR PR1.jsonl."""
    dataset_rel_path = os.path.join("Data", "26 09 22 NAP IPR PR1.jsonl")
    dataset_abs_path = os.path.join(WORKSPACE_ROOT, dataset_rel_path)

    print(f"\n=======================================================")
    print(f" REAL DATASET INGESTION BENCHMARK")
    print(f" Target File: {dataset_abs_path}")
    print(f"=======================================================")

    if not os.path.exists(dataset_abs_path):
        raise FileNotFoundError(f"Benchmark dataset not found: {dataset_abs_path}")

    file_size_bytes = os.path.getsize(dataset_abs_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB ({file_size_bytes:,} bytes)")

    # Timing harness
    t_start_wall = time.perf_counter()
    t_start_cpu = time.process_time()

    pipeline = IngestionPipeline(file_path=dataset_abs_path, sample_interval_ms=100)
    result = pipeline.process()

    t_end_wall = time.perf_counter()
    t_end_cpu = time.process_time()

    wall_duration_s = t_end_wall - t_start_wall
    cpu_duration_s = t_end_cpu - t_start_cpu

    print(f"\nBenchmark Results:")
    print(f"  Wall-clock time: {wall_duration_s:.3f} s")
    print(f"  CPU time:        {cpu_duration_s:.3f} s")
    print(f"  Throughput:      {file_size_mb / wall_duration_s:.2f} MB/s")
    print(f"  Lines parsed:    {result.stats['total_lines']:,} lines")
    print(f"  Lines/sec:       {result.stats['total_lines'] / wall_duration_s:,.0f} lines/s")
    print(f"  Frames created:  {result.stats['resampled_grid_frames']:,} frames (10 Hz)")
    print(f"  Boats parsed:    {len(result.boats)} competitors")
    print(f"  Marks parsed:    {len(result.marks)} gate marks")

    # Audit sanity of extracted data
    assert wall_duration_s < 60.0, f"FAILED: Wall-clock time {wall_duration_s:.2f}s exceeded 60s limit!"
    assert result.stats["total_lines"] >= 1400000, f"Expected >1.4M lines, got {result.stats['total_lines']}"
    assert len(result.boats) == 9, f"Expected 9 boats, got {len(result.boats)}"
    assert len(result.marks) == 4, f"Expected 4 marks, got {len(result.marks)}"
    assert result.stats["resampled_grid_frames"] > 10000, f"Expected >10000 frames"

    # Check FRA telemetry sanity
    fra = result.boats["FRA"]
    max_sog = max(fra.sog_kt)
    avg_sog = sum(fra.sog_kt) / len(fra.sog_kt)
    print(f"  FRA SOG:         Avg {avg_sog:.2f} kt, Max {max_sog:.2f} kt")
    assert 0.0 <= max_sog <= 60.0, f"Unrealistic FRA max SOG: {max_sog}"

    print(f"\nRequirement check: Wall-clock time ({wall_duration_s:.3f}s) < 60.0s => PASS!")
    print(f"=======================================================\n")

    return {
        "wall_duration_s": round(wall_duration_s, 3),
        "cpu_duration_s": round(cpu_duration_s, 3),
        "file_size_mb": round(file_size_mb, 2),
        "total_lines": result.stats["total_lines"],
        "resampled_grid_frames": result.stats["resampled_grid_frames"],
        "throughput_mb_s": round(file_size_mb / wall_duration_s, 2),
        "lines_per_sec": int(result.stats["total_lines"] / wall_duration_s),
        "pass_60s_limit": wall_duration_s < 60.0,
    }


if __name__ == "__main__":
    # If run with --benchmark flag, run benchmark
    if "--benchmark" in sys.argv:
        sys.argv.remove("--benchmark")
        benchmark_results = run_real_dataset_benchmark()

    # Run unittest suite
    unittest.main()
