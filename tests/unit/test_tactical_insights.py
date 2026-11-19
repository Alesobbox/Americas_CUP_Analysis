"""Hand-checkable causal wind windows, projection suppression and raw parsing."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.tactical_insights import TACTICAL_DEFINITIONS, attach_tactical_insights, source_wind_observations

GUN = 1_000_000


def samples(start=-130, end=40, direction=lambda second: (359 + second * .02) % 360,
            speed=lambda second: 10 + second * .005):
    return source_wind_observations(
        [(GUN + second * 1000, direction(second)) for second in range(start, end + 1)],
        [(GUN + second * 1000, speed(second)) for second in range(start, end + 1)])


def detail():
    return {"race": {"id": "test", "gun_time_ms": GUN}}


def analyze(observations, end=GUN + 40_000):
    return attach_tactical_insights(detail(), observations, window_end_ms=end)["tactical_insights"]


class TestTacticalInsights(unittest.TestCase):
    def test_each_exported_diagnostic_has_a_complete_metric_definition(self):
        result = analyze(samples())
        self.assertEqual(result["definitions"], TACTICAL_DEFINITIONS)
        self.assertEqual(set(result["definitions"]), {"direction_change_deg", "direction_rate_deg_per_min",
                                                   "speed_change_kt", "projection_change_deg"})
        for definition in result["definitions"].values():
            self.assertEqual(set(definition), {"label", "unit", "formula", "window", "denominator", "source"})
            self.assertTrue(all(isinstance(value, str) and value for value in definition.values()))
        self.assertIn("unvalidated", result["definitions"]["projection_change_deg"]["denominator"])

    def test_wrap_and_linear_trend_have_hand_checkable_values(self):
        snapshot = analyze(samples())["snapshots"][0]
        self.assertEqual(snapshot["quality"], "derived")
        self.assertEqual(snapshot["coverage_s"], 120)
        self.assertEqual(snapshot["sample_count"], 121)
        self.assertAlmostEqual(snapshot["direction_change_deg"], 2.4)
        self.assertAlmostEqual(snapshot["direction_rate_deg_per_min"], 1.2)
        self.assertAlmostEqual(snapshot["projection_change_deg"], 6)
        self.assertAlmostEqual(snapshot["speed_change_kt"], .6)
        self.assertIn("unvalidated", snapshot["projection_reason"])
        self.assertIn("Conditional", snapshot["projection_reason"])

    def test_each_snapshot_is_invariant_to_future_observations(self):
        observations = samples(end=300)
        prefix = [s for s in observations if s["timestamp_ms"] <= GUN + 40_000]
        full = analyze(observations)
        prior = analyze(prefix)
        self.assertEqual(full["snapshots"], prior["snapshots"])
        changed = copy.deepcopy(observations)
        for sample in changed:
            if sample["timestamp_ms"] > GUN + 40_000:
                sample.update(twd_deg=170, tws_kt=99)
        self.assertEqual(full["snapshots"], analyze(changed)["snapshots"])

    def test_future_direction_cannot_fill_missing_past_direction(self):
        observations = [{"timestamp_ms": GUN + 1000, "twd_deg": 5}]
        observations += [{"timestamp_ms": GUN + i * 1000, "tws_kt": 12} for i in range(-130, 1)]
        snapshot = analyze(observations, GUN)["snapshots"][0]
        self.assertEqual(snapshot["quality"], "unavailable")
        self.assertIsNone(snapshot["direction_change_deg"])
        self.assertEqual(snapshot["sample_count"], 0)
        self.assertIsNone(snapshot["projection_change_deg"])
        self.assertEqual(snapshot["speed_quality"], "derived")
        self.assertEqual(snapshot["speed_coverage_s"], 120)
        self.assertEqual(snapshot["speed_sample_count"], 121)
        self.assertIsNone(snapshot["speed_reason"])
        self.assertEqual(snapshot["speed_change_kt"], 0)

    def test_missing_speed_has_its_own_unavailable_evidence(self):
        observations = [sample for sample in samples() if "twd_deg" in sample]
        snapshot = analyze(observations, GUN)["snapshots"][0]
        self.assertEqual(snapshot["quality"], "derived")
        self.assertEqual(snapshot["speed_quality"], "unavailable")
        self.assertEqual(snapshot["speed_coverage_s"], 0)
        self.assertEqual(snapshot["speed_sample_count"], 0)
        self.assertIsNone(snapshot["speed_change_kt"])
        self.assertTrue(snapshot["speed_reason"])

    def test_session_ending_before_gun_has_no_manufactured_gun_snapshot(self):
        result = analyze(samples(), GUN - 1)
        self.assertEqual(result["snapshots"], [])
        self.assertIn("before the source gun", result["reason"])

    def test_irregular_gap_reduces_coverage_even_when_grid_endpoints_are_fresh(self):
        observations = [sample for sample in samples() if sample["timestamp_ms"] not in (GUN - 60_000, GUN - 59_000)]
        observations += [{"timestamp_ms": GUN - 60_900, "twd_deg": 10},
                         {"timestamp_ms": GUN - 58_800, "twd_deg": 10}]
        snapshot = analyze(observations, GUN)["snapshots"][0]
        self.assertEqual(snapshot["quality"], "unavailable")
        self.assertLess(snapshot["coverage_s"], 120)
        self.assertIsNone(snapshot["direction_change_deg"])
        self.assertEqual(snapshot["speed_quality"], "unavailable")

    def test_missing_field_does_not_become_zero_direction(self):
        snapshot = analyze(source_wind_observations([], [(GUN, 10)]), GUN)["snapshots"][0]
        self.assertIsNone(snapshot["direction_change_deg"])
        self.assertEqual(snapshot["coverage_s"], 0)

    def test_sparse_internal_gap_and_stale_endpoint_are_unavailable(self):
        complete = samples()
        cases = ([s for s in complete if not GUN - 50_000 <= s["timestamp_ms"] <= GUN - 45_000],
                 [s for s in complete if s["timestamp_ms"] <= GUN - 3000],
                 samples(start=-30))
        for observations in cases:
            with self.subTest(size=len(observations)):
                snapshot = analyze(observations, GUN)["snapshots"][0]
                self.assertEqual(snapshot["quality"], "unavailable")
                self.assertIsNone(snapshot["projection_change_deg"])

    def test_erratic_flat_and_unbounded_trends_have_no_projection(self):
        for direction in (lambda i: 35, lambda i: (35 + i * .2) % 360,
                          lambda i: (35 + abs(i + 60) * .1) % 360,
                          lambda i: (35 + i * .02 + (5 if i % 2 else -5)) % 360):
            snapshot = analyze(samples(direction=direction), GUN)["snapshots"][0]
            self.assertEqual(snapshot["quality"], "derived")
            self.assertIsNone(snapshot["projection_change_deg"])

    def test_out_of_order_and_duplicate_samples_are_deterministic(self):
        observations = samples()
        self.assertEqual(analyze(observations)["snapshots"], analyze(list(reversed(observations)))["snapshots"])
        self.assertEqual(analyze(observations)["snapshots"], analyze(observations + observations)["snapshots"])

    def test_invalid_values_are_not_emitted(self):
        observations = source_wind_observations([(GUN, float("nan")), (GUN, 360)],
                                               [(GUN, float("inf")), (GUN, -1)])
        result = analyze(observations, GUN)
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["snapshots"][0]["quality"], "unavailable")
        self.assertEqual(result["source_provenance"]["direction_sample_count"], 0)

    def test_source_provenance_and_availability_policy_are_explicit(self):
        result = attach_tactical_insights(detail(), samples(), window_end_ms=GUN,
            source_provenance={"source_file": "Data/test.jsonl", "source_sha256": "a" * 64})["tactical_insights"]
        self.assertEqual(result["source_provenance"]["source_sha256"], "a" * 64)
        self.assertIn("not arrival-time causal", result["availability_basis"])
        self.assertIn("Late records", result["availability_basis"])


class TestRawWindRefresh(unittest.TestCase):
    def test_ingestion_and_refresh_share_exact_raw_policy_and_hash(self):
        from pipeline.config import OFFICIAL_WIND_ASSET_ID
        from pipeline.ingest import IngestionPipeline
        from scripts.refresh_team_analytics import read_source_wind
        session = {"session": {"race_start": GUN, "window_start": GUN - 130_000,
                   "window_end": GUN + 40_000, "race_course": {"course_axis": 0, "course_length": 1000}}}
        raw_records = [session]
        for sample in samples():
            field = "true_wind_direction" if "twd_deg" in sample else "true_wind_speed"
            value = sample.get("twd_deg", sample.get("tws_kt"))
            if field == "true_wind_speed":
                from pipeline.config import MPS_TO_KNOTS
                value /= MPS_TO_KNOTS
            raw_records.append({"telemetry": {"asset_id": OFFICIAL_WIND_ASSET_ID,
                "timestamp": sample["timestamp_ms"], field: {"value": value}}})
        raw = ("\r\n".join(json.dumps(record) for record in raw_records) + "\r\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "test.jsonl"
            source.write_bytes(raw)
            ingestion = IngestionPipeline(str(source)).process()
            observations, end, provenance = read_source_wind(source, Path(directory))
        self.assertEqual(ingestion.official_wind.source_provenance["source_sha256"], provenance["source_sha256"])
        self.assertEqual(ingestion.official_wind.source_provenance["source_size_bytes"], len(raw))
        self.assertEqual(analyze(ingestion.official_wind.causal_samples)["snapshots"], analyze(observations)["snapshots"])
        self.assertEqual(end, GUN + 40_000)

    def test_stream_parser_preserves_independent_times_and_exact_hash(self):
        from pipeline.config import MPS_TO_KNOTS, OFFICIAL_WIND_ASSET_ID
        from scripts.refresh_team_analytics import read_source_wind
        records = [{"session": {"window_end": GUN + 10_000}},
            {"telemetry": {"asset_id": OFFICIAL_WIND_ASSET_ID, "timestamp": GUN + 400,
                           "true_wind_direction": {"value": 359}}},
            {"telemetry": {"asset_id": "another-boat", "timestamp": GUN,
                           "true_wind_direction": {"value": 90}}},
            {"telemetry": {"asset_id": OFFICIAL_WIND_ASSET_ID, "timestamp": GUN,
                           "true_wind_speed": {"value": 5}}}]
        raw = "\r\n".join(json.dumps(record) for record in records).encode("utf-8") + b"\r\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Data").mkdir()
            source = root / "Data" / "test.jsonl"
            source.write_bytes(raw)
            observations, end, provenance = read_source_wind(source, root)
        self.assertEqual(end, GUN + 10_000)
        self.assertEqual(observations, [{"timestamp_ms": GUN + 400, "twd_deg": 359},
                                      {"timestamp_ms": GUN, "tws_kt": 5 * MPS_TO_KNOTS}])
        self.assertEqual(provenance["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(provenance["source_size_bytes"], len(raw))
        self.assertEqual(provenance["source_file"], "Data/test.jsonl")


if __name__ == "__main__":
    unittest.main()
