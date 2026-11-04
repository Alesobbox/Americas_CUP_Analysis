"""Unit tests for telemetry streaming ingestion, resampling, and synchronization."""

import json
import math
import os
import tempfile
import unittest

from pipeline.config import (
    MPS_TO_KNOTS,
    COURSE_AXIS_DEG,
    SAMPLE_INTERVAL_MS,
    COMPETITORS,
    MARKS,
    MARK_RM8_UUID,
    MARK_RM6_UUID,
    OFFICIAL_WIND_ASSET_ID,
)
from pipeline.ingest import (
    interpolate_linear,
    interpolate_circular_deg,
    compute_twa,
    compute_vmg,
    clean_and_sort_series,
    resample_scalar_series,
    resample_circular_series,
    IngestionPipeline,
)


class TestIngest(unittest.TestCase):
    """Test suite for telemetry ingestion, interpolation, and unit conversions."""

    def test_mps_to_knots_conversion(self):
        """Conversion factor must strictly adhere to 1 m/s = 1.94384449 kt."""
        self.assertAlmostEqual(0.0 * MPS_TO_KNOTS, 0.0, places=6)
        self.assertAlmostEqual(1.0 * MPS_TO_KNOTS, 1.94384449, places=8)
        self.assertAlmostEqual(10.0 * MPS_TO_KNOTS, 19.4384449, places=6)
        # Typical AC40 foiling speed: 15 m/s (~29.16 kt)
        self.assertAlmostEqual(15.0 * MPS_TO_KNOTS, 29.15766735, places=6)
        # AC40 top speed: 22 m/s (~42.76 kt)
        self.assertAlmostEqual(22.0 * MPS_TO_KNOTS, 42.76457878, places=6)

    def test_linear_interpolation(self):
        """Linear interpolation must produce exact intermediate points and handle endpoints."""
        # Midpoint
        self.assertAlmostEqual(interpolate_linear(150, 100, 200, 10.0, 20.0), 15.0, places=6)
        # Quarter point
        self.assertAlmostEqual(interpolate_linear(125, 100, 200, 10.0, 20.0), 12.5, places=6)
        # Same timestamp
        self.assertAlmostEqual(interpolate_linear(100, 100, 100, 10.0, 20.0), 10.0, places=6)

    def test_circular_shortest_arc_interpolation(self):
        """Circular interpolation must follow the shortest arc and wrap correctly across 0/360."""
        # Crossing 0 deg North: 350 deg to 10 deg -> midpoint must be 0.0 deg
        mid1 = interpolate_circular_deg(150, 100, 200, 350.0, 10.0)
        self.assertAlmostEqual(mid1, 0.0, places=6)

        # Crossing 0 deg North in reverse: 10 deg to 350 deg -> midpoint must be 0.0 deg
        mid2 = interpolate_circular_deg(150, 100, 200, 10.0, 350.0)
        self.assertAlmostEqual(mid2, 0.0, places=6)

        # 359 deg to 1 deg at 50% -> 0.0 deg
        mid3 = interpolate_circular_deg(150, 100, 200, 359.0, 1.0)
        self.assertAlmostEqual(mid3, 0.0, places=6)

        # Standard non-wrapping arc: 40 deg to 60 deg -> midpoint 50 deg
        mid4 = interpolate_circular_deg(150, 100, 200, 40.0, 60.0)
        self.assertAlmostEqual(mid4, 50.0, places=6)

        # Wrapping across 180 deg: 170 deg to 190 deg -> midpoint 180 deg
        mid5 = interpolate_circular_deg(150, 100, 200, 170.0, 190.0)
        self.assertAlmostEqual(mid5, 180.0, places=6)

    def test_compute_twa(self):
        """TWA must correctly compute wind angle relative to boat heading in [-180, +180]."""
        # Wind from 68 deg, boat heading 115 deg -> TWA = -47 deg (Port Tack)
        twa_port = compute_twa(68.0, 115.0)
        self.assertAlmostEqual(twa_port, -47.0, places=6)

        # Wind from 68 deg, boat heading 21 deg -> TWA = +47 deg (Starboard Tack)
        twa_stbd = compute_twa(68.0, 21.0)
        self.assertAlmostEqual(twa_stbd, +47.0, places=6)

        # Head to wind: heading == twd -> TWA = 0.0
        self.assertAlmostEqual(compute_twa(50.0, 50.0), 0.0, places=6)

        # Dead run: heading == twd + 180 -> TWA = 180.0 or -180.0
        dead_run = compute_twa(40.0, 220.0)
        self.assertAlmostEqual(abs(dead_run), 180.0, places=6)

    def test_compute_vmg(self):
        """VMG along target axis must project SOG using cosine of angle difference."""
        target_axis = 40.0
        sog = 30.0

        # COG aligned with axis -> full VMG
        self.assertAlmostEqual(compute_vmg(sog, 40.0, target_axis), 30.0, places=6)

        # COG perpendicular to axis -> zero VMG
        self.assertAlmostEqual(compute_vmg(sog, 130.0, target_axis), 0.0, places=6)

        # COG directly opposite to axis -> negative full VMG
        self.assertAlmostEqual(compute_vmg(sog, 220.0, target_axis), -30.0, places=6)

        # COG at 45 deg to axis -> SOG * cos(45 deg)
        self.assertAlmostEqual(compute_vmg(sog, 85.0, target_axis), 30.0 * math.sqrt(2) / 2.0, places=5)

    def test_clean_and_sort_series(self):
        """Time series cleaner must sort out-of-order packets and overwrite duplicates."""
        raw = [
            (200, 20.0),
            (100, 10.0),
            (300, 30.0),
            (200, 25.0),  # duplicate timestamp, should update to 25.0
        ]
        times, values = clean_and_sort_series(raw)
        self.assertEqual(times, [100, 200, 300])
        self.assertEqual(values, [10.0, 25.0, 30.0])

    def test_resample_scalar_series(self):
        """Scalar series resampler must linearly interpolate across a regular grid."""
        times = [1000, 2000, 3000]
        values = [10.0, 20.0, 30.0]
        grid = [500, 1000, 1500, 2000, 2500, 3000, 3500]

        res = resample_scalar_series(times, values, grid)
        self.assertEqual(len(res), len(grid))
        # Before first sample clamps
        self.assertAlmostEqual(res[0], 10.0)
        self.assertAlmostEqual(res[1], 10.0)
        # Midpoint
        self.assertAlmostEqual(res[2], 15.0)
        self.assertAlmostEqual(res[3], 20.0)
        self.assertAlmostEqual(res[4], 25.0)
        self.assertAlmostEqual(res[5], 30.0)
        # After last sample clamps
        self.assertAlmostEqual(res[6], 30.0)

    def test_resample_circular_series(self):
        """Circular series resampler must wrap across 0 deg North boundary smoothly."""
        times = [1000, 2000]
        values = [350.0, 10.0]  # wraps across 0 deg
        grid = [1000, 1250, 1500, 1750, 2000]

        res = resample_circular_series(times, values, grid)
        self.assertEqual(len(res), 5)
        self.assertAlmostEqual(res[0], 350.0, places=5)
        self.assertAlmostEqual(res[1], 355.0, places=5)
        self.assertAlmostEqual(res[2], 0.0, places=5)
        self.assertAlmostEqual(res[3], 5.0, places=5)
        self.assertAlmostEqual(res[4], 10.0, places=5)

    def test_streaming_ingestion_on_synthetic_dataset(self):
        """Full pipeline must stream and regularize multi-rate JSONL data correctly."""
        fra_uuid = "42e39310-fef5-4c5d-b099-a599aad5ddbb"

        synthetic_records = [
            # 1. Session record
            {
                "session": {
                    "id": "test-session-123",
                    "name": "Test Regatta",
                    "race_state": "RACE_STATE_RACING",
                    "race_type": "RACE_TYPE_FLEET",
                    "race_start": "1000",
                    "window_start": "1000",
                    "window_end": "1500",
                    "official_wind_asset_id": OFFICIAL_WIND_ASSET_ID,
                    "rules": {"mark_zone_size": 60},
                    "race_course": {
                        "course_axis": COURSE_AXIS_DEG,
                        "course_length": 2259.0,
                        "sequences": [],
                    },
                    "race_boundary": {
                        "polygon": {
                            "coordinates": [
                                {"x": 14.23, "y": 40.80},
                                {"x": 14.24, "y": 40.81},
                            ]
                        }
                    },
                    "safety_boundary": {
                        "polygon": {
                            "coordinates": [
                                {"x": 14.22, "y": 40.79},
                                {"x": 14.25, "y": 40.82},
                            ]
                        }
                    },
                    "asset_targets": [],
                }
            },
            # 2. Competitor record
            {
                "competitor": {
                    "asset_id": fra_uuid,
                    "classification": "COMPETITOR_CLASSIFICATION_UNSPECIFIED",
                    "course_position": {"leg_number": 1},
                    "start_state": {"started": True},
                    "leg_timings": [{"leg_number": 0, "gate_time": "1000"}],
                    "penalties": [],
                }
            },
            # 3. Telemetry records for FRA
            # 20Hz GNSS
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1000", "gnss_position": {"latitude": 40.80948, "longitude": 14.23727}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1200", "gnss_position": {"latitude": 40.81000, "longitude": 14.23800}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1500", "gnss_position": {"latitude": 40.81100, "longitude": 14.23900}}},
            # 20Hz Heading
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1000", "heading": {"value": 40.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1500", "heading": {"value": 44.0}}},
            # 4.4Hz SOG (in SI m/s: 10 m/s -> ~19.44 kt)
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1000", "speed_over_ground": {"value": 10.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1500", "speed_over_ground": {"value": 12.0}}},
            # 4.4Hz COG
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1000", "course_over_ground": {"value": 40.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1500", "course_over_ground": {"value": 42.0}}},
            # 4.4Hz Wind
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1000", "true_wind_speed": {"value": 7.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1500", "true_wind_speed": {"value": 8.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1000", "true_wind_direction": {"value": 68.0}}},
            {"telemetry": {"asset_id": fra_uuid, "timestamp": "1500", "true_wind_direction": {"value": 70.0}}},
            # 4. Telemetry for RM8
            {"telemetry": {"asset_id": MARK_RM8_UUID, "timestamp": "1000", "gnss_position": {"latitude": 40.80293, "longitude": 14.22662}}},
            {"telemetry": {"asset_id": MARK_RM8_UUID, "timestamp": "1500", "gnss_position": {"latitude": 40.80293, "longitude": 14.22662}}},
            # 5. Telemetry for Official Wind
            {"telemetry": {"asset_id": OFFICIAL_WIND_ASSET_ID, "timestamp": "1000", "true_wind_speed": {"value": 7.5}}},
            {"telemetry": {"asset_id": OFFICIAL_WIND_ASSET_ID, "timestamp": "1000", "true_wind_direction": {"value": 65.0}}},
        ]

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as tf:
            for rec in synthetic_records:
                tf.write(json.dumps(rec) + "\n")
            temp_path = tf.name

        try:
            pipeline = IngestionPipeline(file_path=temp_path, sample_interval_ms=100)
            result = pipeline.process()

            # Verify grid: [1000, 1100, 1200, 1300, 1400, 1500] = 6 frames
            self.assertEqual(result.grid_timestamps_ms, [1000, 1100, 1200, 1300, 1400, 1500])

            # Verify FRA boat
            self.assertIn("FRA", result.boats)
            fra = result.boats["FRA"]
            self.assertEqual(len(fra.x), 6)
            self.assertEqual(len(fra.sog_kt), 6)

            # First SOG frame: 10.0 m/s * MPS_TO_KNOTS ~= 19.438 kt
            self.assertAlmostEqual(fra.sog_kt[0], 10.0 * MPS_TO_KNOTS, places=4)
            # Last SOG frame: 12.0 m/s * MPS_TO_KNOTS ~= 23.326 kt
            self.assertAlmostEqual(fra.sog_kt[-1], 12.0 * MPS_TO_KNOTS, places=4)

            # Heading interpolation: starts at 40.0, ends at 44.0
            self.assertAlmostEqual(fra.heading[0], 40.0, places=4)
            self.assertAlmostEqual(fra.heading[-1], 44.0, places=4)

            # TWA is calculated
            self.assertEqual(len(fra.twa_deg), 6)
            self.assertAlmostEqual(fra.twa_deg[0], compute_twa(68.0, 40.0), places=4)

            # VMG is calculated
            self.assertEqual(len(fra.vmg_kt), 6)

            # RM8 mark is present
            self.assertIn("RM8", result.marks)
            self.assertEqual(len(result.marks["RM8"].x), 6)

            # Official wind is present
            self.assertEqual(len(result.official_wind.speed_kt), 6)
            self.assertAlmostEqual(result.official_wind.speed_kt[0], 7.5 * MPS_TO_KNOTS, places=4)

            # Serialization to dict works
            serialized = result.to_dict()
            self.assertIn("session", serialized)
            self.assertIn("boats", serialized)
            self.assertIn("marks", serialized)
            self.assertIn("official_wind", serialized)
            self.assertIn("safety_borders", serialized)
            self.assertEqual(serialized["boat_class"], "AC40")
            self.assertEqual(serialized["event_edition"], "37th America's Cup Preliminary Regatta Naples 2026")
            self.assertIn("platform_border", serialized["safety_borders"])
            self.assertIn("keep_clear_border", serialized["safety_borders"])
            self.assertEqual(serialized["chronology"]["total_frames"], 6)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
