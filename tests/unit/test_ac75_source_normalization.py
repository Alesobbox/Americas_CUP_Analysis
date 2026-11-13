"""Focused unit tests for streaming JSONL normalization and native Parquet partitioning (T03)."""
import json
from pathlib import Path
import tempfile
import unittest

import pyarrow.parquet as pq

from pipeline.kinematic_ml.source import (
    iter_source_packets,
    extract_session_header,
    normalize_telemetry_packet,
    NormalizationErrorReport,
    RawPacket,
)
from pipeline.kinematic_ml.dataset import normalize_and_write_partition, NATIVE_ARROW_SCHEMA

ROOT = Path(__file__).resolve().parents[2]


class TestAC75SourceNormalization(unittest.TestCase):
    def test_multi_field_packet_preservation_no_elif_chain(self):
        """Verify that multiple channels in a single telemetry packet survive (no elif skipping)."""
        session_meta = {"competitor_map": {"boat-1": "ac37:ETNZ"}}
        packet_data = {
            "asset_id": "boat-1",
            "timestamp": "1724328500000",
            "gnss_position": {"latitude": 41.38, "longitude": 2.19, "altitude": 0.0},
            "heading": {"value": 45.0},
            "speed_over_ground": {"value": 18.5},
            "course_over_ground": {"value": 48.0},
            "true_wind_speed": {"value": 7.2},
            "true_wind_direction": {"value": 105.0},
        }
        raw = RawPacket(
            line_ordinal=10,
            offset=500,
            correlation_id="cid-1",
            sequence_id=1,
            packet_type="telemetry",
            data=packet_data,
        )
        norm_rows = list(normalize_telemetry_packet(raw, session_meta))
        channels = [r["channel"] for r in norm_rows]
        self.assertEqual(len(norm_rows), 6)
        self.assertIn("gnss_position", channels)
        self.assertIn("heading", channels)
        self.assertIn("speed_over_ground", channels)
        self.assertIn("course_over_ground", channels)
        self.assertIn("true_wind_speed", channels)
        self.assertIn("true_wind_direction", channels)

    def test_malformed_lines_and_error_reporting(self):
        """Verify malformed JSON/UTF-8 records are explicitly tracked with offsets and bounded examples."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as fp:
            tmp_path = Path(fp.name)
            fp.write('{"telemetry": {"asset_id": "b1", "timestamp": "1000", "heading": {"value": 10.0}}}\n')
            fp.write('MALFORMED_JSON_LINE_1\n')
            fp.write('{"telemetry": {"asset_id": "b1", "timestamp": "2000", "heading": {"value": 20.0}}}\n')
            fp.write('{BROKEN JSON LINE 2\n')
            fp.write('NOT VALID JSON 3\n')
            fp.write('EXTRA CORRUPT 4\n')

        try:
            report = NormalizationErrorReport()
            packets = list(iter_source_packets(tmp_path, error_report=report))
            self.assertEqual(len(packets), 2)
            self.assertEqual(report.malformed_lines, 4)
            # Maximum 3 bounded examples
            self.assertEqual(len(report.bounded_examples), 3)
            self.assertEqual(report.bounded_examples[0]["line"], 1)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_out_of_order_packets_and_deterministic_parquet_sorting(self):
        """Verify stream with out-of-order timestamps is deterministically sorted in Parquet."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_jsonl = Path(tmp_dir) / "test_stream.jsonl"
            out_parquet = Path(tmp_dir) / "test_stream.parquet"

            with open(tmp_jsonl, "w", encoding="utf-8") as fp:
                # Session packet first
                fp.write(json.dumps({"session": {"id": "sess-1", "name": "Test", "competitors": {"b1": "ETNZ"}}}) + "\n")
                # Telemetry out of order: 3000ms, then 1000ms, then 2000ms
                fp.write(json.dumps({"telemetry": {"asset_id": "b1", "timestamp": "3000", "heading": {"value": 30.0}}}) + "\n")
                fp.write(json.dumps({"telemetry": {"asset_id": "b1", "timestamp": "1000", "heading": {"value": 10.0}}}) + "\n")
                fp.write(json.dumps({"telemetry": {"asset_id": "b1", "timestamp": "2000", "heading": {"value": 20.0}}}) + "\n")

            res = normalize_and_write_partition(tmp_jsonl, out_parquet, batch_size=10)
            self.assertEqual(res["total_rows"], 3)

            table = pq.read_table(out_parquet)
            ts_list = table["timestamp_ms"].to_pylist()
            self.assertEqual(ts_list, [1000, 2000, 3000])

    def test_cross_batch_global_sorting_multi_chunk_merge(self):
        """Verify probe records [3000, 4000, 1000, 2000] with batch_size=2 are globally sorted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_jsonl = Path(tmp_dir) / "test_cross_batch.jsonl"
            out_parquet = Path(tmp_dir) / "test_cross_batch.parquet"

            with open(tmp_jsonl, "w", encoding="utf-8") as fp:
                fp.write(json.dumps({"session": {"id": "sess-probe", "competitors": {"b1": "ETNZ"}}}) + "\n")
                # 4 records in order 3000, 4000, 1000, 2000
                fp.write(json.dumps({"telemetry": {"asset_id": "b1", "timestamp": "3000", "heading": {"value": 30.0}}}) + "\n")
                fp.write(json.dumps({"telemetry": {"asset_id": "b1", "timestamp": "4000", "heading": {"value": 40.0}}}) + "\n")
                fp.write(json.dumps({"telemetry": {"asset_id": "b1", "timestamp": "1000", "heading": {"value": 10.0}}}) + "\n")
                fp.write(json.dumps({"telemetry": {"asset_id": "b1", "timestamp": "2000", "heading": {"value": 20.0}}}) + "\n")

            # batch_size=2 forces 2 separate chunks: [3000, 4000] and [1000, 2000]
            res = normalize_and_write_partition(tmp_jsonl, out_parquet, batch_size=2)
            self.assertEqual(res["total_rows"], 4)

            table = pq.read_table(out_parquet)
            ts_list = table["timestamp_ms"].to_pylist()
            self.assertEqual(ts_list, [1000, 2000, 3000, 4000])

    def test_bounded_memory_beyond_old_line_cap(self):
        """Verify normalization runs seamlessly beyond 100,001 lines with bounded batching."""
        # Create a synthetic stream of 105,000 lines
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_jsonl = Path(tmp_dir) / "long_stream.jsonl"
            out_parquet = Path(tmp_dir) / "long_stream.parquet"

            with open(tmp_jsonl, "w", encoding="utf-8") as fp:
                fp.write(json.dumps({"session": {"id": "s1", "competitors": {"b1": "ETNZ"}}}) + "\n")
                for i in range(100005):
                    fp.write(json.dumps({
                        "telemetry": {
                            "asset_id": "b1",
                            "timestamp": str(1724000000000 + i * 100),
                            "heading": {"value": float(i % 360)},
                        }
                    }) + "\n")

            # Process with 20,000 batch size
            res = normalize_and_write_partition(tmp_jsonl, out_parquet, batch_size=20000)
            self.assertEqual(res["total_rows"], 100005)

            # Check that line 100,004 was captured
            table = pq.read_table(out_parquet)
            self.assertEqual(len(table), 100005)
            self.assertEqual(table["line_ordinal"][-1].as_py(), 100005)


if __name__ == "__main__":
    unittest.main()
