"""Synthetic end-to-end evidence, chronology and publication regression tests.

The fixture is invented, tiny and explicitly audited for testing. It is never
merged into the archive and establishes no real sailing forecast accuracy.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

try:
    import numpy as np
    import pyarrow  # noqa: F401
    import scipy  # noqa: F401
except ImportError:
    np = None

if np is not None:
    from pipeline.prediction.backtest import run_backtest
    from pipeline.prediction.build import export_archive, prepare
    from pipeline.prediction.contracts import validate_race, verify_public
    from pipeline.prediction.labels import before_day, load_reviews
    from pipeline.prediction.source import load_dataset, read_source, seal_existing_dataset, source_dataset
    from pipeline.prediction.state import CausalRace


def tiny_source(day, *, session_end=True):
    gun = int(datetime.fromisoformat(day + "T12:00:00").replace(tzinfo=timezone.utc).timestamp() * 1000)
    gate0 = {"port_asset_id": "START_P", "starboard_asset_id": "START_S"}
    gate1 = {"port_asset_id": "TOP_P", "starboard_asset_id": "TOP_S"}
    marks = {"START_P": (-25, 0), "START_S": (25, 0), "TOP_P": (-25, 500), "TOP_S": (25, 500)}
    assets = [{"id": "BOAT_A", "abbreviation": "TEST_A", "official_name": "Synthetic A", "type": "ASSET_TYPE_YACHT"},
              {"id": "BOAT_B", "abbreviation": "TEST_B", "official_name": "Synthetic B", "type": "ASSET_TYPE_YACHT"}]
    assets += [{"id": name, "type": "ASSET_TYPE_RACE_MARK"} for name in marks]
    session = {"timestamp": gun - 1000, "race_start": gun, "window_start": gun - 1000,
               "window_end": gun + 50000, "assets": assets,
               "competitors": [{"asset_id": "BOAT_A"}, {"asset_id": "BOAT_B"}],
               "official_wind_asset_id": "WIND", "race_course": {"course_length": 500,
               "sequences": [{"gate": gate0}, {"gate": gate1}, {"gate": gate0}]}}
    records = [{"session": session}]

    def position(asset, second, x, y):
        return {"telemetry": {"asset_id": asset, "timestamp": gun + second * 1000,
                "gnss_position": {"latitude": 50 + y / 111320, "longitude": 1 + x / (111320 * np.cos(np.deg2rad(50)))}}}

    for second in range(51):
        for name, (x, y) in marks.items():
            records.append(position(name, second, x, y))
        records.append({"telemetry": {"asset_id": "WIND", "timestamp": gun + second * 1000,
                                      "true_wind_speed": {"value": 12 / 1.943844}}})
        for index, boat in enumerate(("BOAT_A", "BOAT_B")):
            turn, finish = 20 + index * 2, 40 + index * 4
            y = 500 * second / turn if second <= turn else max(0, 500 * (finish - second) / (finish - turn))
            records.append(position(boat, second, index * 4, y))
            for name, value in (("speed_over_ground", 25), ("course_over_ground", 0 if second < turn else 180)):
                records.append({"telemetry": {"asset_id": boat, "timestamp": gun + second * 1000,
                                              name: {"value": value}}})
            if second in (0, turn, finish):
                gates = [{"leg_number": 0, "gate_time": gun}]
                if second >= turn:
                    gates.append({"leg_number": 1, "gate_time": gun + turn * 1000})
                if second >= finish:
                    gates.append({"leg_number": 2, "gate_time": gun + finish * 1000})
                records.append({"competitor": {"asset_id": boat, "timestamp": gun + second * 1000,
                    "classification": "FINISHED" if second == finish else "RACING",
                    "start_state": {"started": True}, "leg_timings": gates}})
    if session_end:
        records.append({"session": dict(session, timestamp=gun + 50000)})
    return gun, records


def fixture_archive(root):
    (root / "Data").mkdir()
    for day in ("2026-05-22", "2026-05-23", "2026-05-24"):
        _, records = tiny_source(day)
        name = day[2:].replace("-", " ") + " CAG IPR Race 1.jsonl"
        (root / "Data" / name).write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    dataset = source_dataset(root)
    metadata, _, _, _ = prepare(root)
    (root / "docs").mkdir()
    reviews = {"schema_version": "completion-review-1", "races": [
        {"race_id": meta["race_id"], "evidence_ref": "synthetic-test-fixture://" + meta["race_id"],
         "available_at_ms": meta["gun_ms"] + 56000,
         "entries": [{"asset_id": boat, "started": True, "completed": True} for boat in meta["boat_ids"]]}
        for meta in metadata]}
    (root / "docs" / "forecast_completion_review.json").write_text(json.dumps(reviews), encoding="utf-8")
    return dataset


@unittest.skipIf(np is None, "Install the locked forecast-core extra for end-to-end forecasting tests")
class PredictionPipelineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        fixture_archive(cls.root)
        cls.report = export_archive(cls.root, pre_n=1200, live_n=600)
        cls.directory = cls.root / "public" / "data" / "predictions"
        cls.index = json.loads((cls.directory / "index.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def artifact(self, index=1):
        return json.loads((self.directory / self.index["races"][index]["path"]).read_text())

    def test_raw_to_parquet_to_chronological_models_to_public_artifacts(self):
        metadata, labels, transitions, reviews = prepare(self.root)
        self.assertEqual(len(metadata), 3)
        self.assertEqual(len(reviews), 6)
        self.assertEqual(len(transitions), 12)
        self.assertEqual([label["order"] for label in labels], [["TEST_A", "TEST_B"]] * 3)
        self.assertTrue(all(label["official_order_verified"] is False for label in labels))
        self.assertEqual(self.report["races"], 3)
        self.assertTrue(self.report["hard_3_MiB_passed"])
        first, next_day = self.artifact(0), self.artifact(1)
        self.assertEqual(first["pre_race"]["status"], "unavailable")
        self.assertTrue(all(p is None for p in first["pre_race"]["expected_position_by_boat"].values()))
        self.assertEqual(next_day["pre_race"]["status"], "estimated")
        self.assertTrue(all(1 <= p <= 2 for p in next_day["pre_race"]["expected_position_by_boat"].values()))
        for earlier_races, entry in enumerate(self.index["races"]):
            card = json.loads((self.directory / "models" / (entry["model_ref"] + ".json")).read_text())
            artifact = json.loads((self.directory / entry["path"]).read_text())
            self.assertEqual(card["strength"]["n_races"], earlier_races)
            self.assertEqual(card["completion"]["scheduled_audited"], earlier_races * 2)
            self.assertLess(artifact["header"]["train_cutoff_ms"], artifact["live"]["state_timestamps_ms"][0])
            validate_race(artifact)
        self.assertTrue(list((self.root / ".forecast" / "dataset").glob("*.parquet")))

    def test_results_and_reviews_are_not_available_before_their_recorded_cutoffs(self):
        _, labels, _, reviews = prepare(self.root)
        self.assertEqual(len(before_day(labels, "2026-05-23")), 1)
        self.assertEqual(len(before_day(reviews, "2026-05-23")), 2)
        delayed = dict(labels[0], result_available_at_ms=int(datetime(2026, 5, 24, tzinfo=timezone.utc).timestamp() * 1000))
        self.assertEqual(before_day([delayed], "2026-05-23"), [])

    def test_true_terminal_winner_waits_for_global_order_and_modeled_publication(self):
        artifact = self.artifact(1)
        live = artifact["live"]
        self.assertTrue(all(p - t == 6000 for p, t in zip(live["published_at_ms"], live["state_timestamps_ms"])))
        last = len(live["state_timestamps_ms"]) - 1
        self.assertEqual(live["win_prob_by_boat"]["BOAT_A"][last], 1)
        self.assertEqual(live["win_prob_by_boat"]["BOAT_B"][last], 0)
        self.assertEqual(live["no_finisher_prob"][last], 0)
        self.assertEqual(artifact["pre_race"]["nonfinish_score"], "N")

    def test_backtest_runs_with_full_scheduled_field_and_reports_day_counts(self):
        report = run_backtest(self.root, n=600)
        self.assertEqual(report["development"]["reference"]["race_count"], 2)
        self.assertEqual(report["development"]["reference"]["independent_days"], 2)
        self.assertEqual(report["selected"], "joint_pl_reference")
        self.assertEqual(report["calibration"], "identity; empirical calibration not established")

    def test_reviewed_completed_entry_missing_from_source_order_cannot_supply_a_winner_label(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_archive(root)
            source = next((root / "Data").glob("26 05 23*.jsonl"))
            records = [json.loads(line) for line in source.read_text().splitlines()]
            # Deliberately stale source flag contradicts the independent fixture
            # review. A source-valid subset cannot become a full-field target.
            for record in records:
                event = record.get("competitor", {})
                if event.get("asset_id") == "BOAT_B":
                    event["start_state"]["started"] = False
            source.write_text("".join(json.dumps(record) + "\n" for record in records))
            source_dataset(root, force=True)
            report = run_backtest(root, n=80)
            self.assertEqual(report["coverage_reasons"]["reviewed_finishers_disagree_with_source_order"], 1)
            self.assertEqual(report["pre_race_development"]["reference"]["race_count"], 1)

    def test_audited_no_finisher_scores_the_joint_extra_outcome_and_rank_N(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_archive(root)
            source = next((root / "Data").glob("26 05 23*.jsonl"))
            records = [json.loads(line) for line in source.read_text().splitlines()]
            for record in records:
                event = record.get("competitor")
                if event:
                    event["leg_timings"] = [gate for gate in event["leg_timings"] if gate["leg_number"] < 2]
                    if event["classification"] == "FINISHED":
                        event["classification"] = "RETIRED"
            source.write_text("".join(json.dumps(record) + "\n" for record in records))
            source_dataset(root, force=True)
            review_path = root / "docs" / "forecast_completion_review.json"
            review = json.loads(review_path.read_text())
            metadata, _, _, _ = prepare(root)
            race_id = next(meta["race_id"] for meta in metadata if meta["date"] == "2026-05-23")
            for race in review["races"]:
                if race["race_id"] == race_id:
                    for entry in race["entries"]:
                        entry.update(completed=False, failure_type="exogenous")
            review_path.write_text(json.dumps(review))
            from pipeline.prediction.evaluation import scores as actual_scores
            scored_no_finisher = []

            def record_target(probabilities, winner_index, expected_positions=None, positions=None, rank_cdf=None):
                if len(probabilities) == 3 and winner_index == 2 and positions is not None:
                    scored_no_finisher.append(list(positions))
                return actual_scores(probabilities, winner_index, expected_positions, positions, rank_cdf)

            with patch("pipeline.prediction.backtest.scores", side_effect=record_target):
                report = run_backtest(root, n=80)
            self.assertEqual(report["pre_race_development"]["reference"]["race_count"], 2)
            self.assertTrue(scored_no_finisher)
            self.assertTrue(all(positions == [2, 2] for positions in scored_no_finisher))

    def test_partial_review_denominators_fail_closed(self):
        metadata, _, _, _ = prepare(self.root)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.json"
            path.write_text(json.dumps({"schema_version": "completion-review-1", "races": [{
                "race_id": metadata[0]["race_id"], "evidence_ref": "synthetic://partial", "available_at_ms": 1,
                "entries": [{"asset_id": "BOAT_A", "started": True, "completed": True}]}]}))
            with self.assertRaisesRegex(ValueError, "denominator"):
                load_reviews(self.root, metadata, path)

    def test_replay_subset_cannot_remove_a_scheduled_forecast_competitor(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = fixture_archive(root)
            race_id = dataset["races"][1]["race_id"]
            replay_directory = root / "public" / "data" / "replays"
            replay_directory.mkdir(parents=True)
            (replay_directory / (race_id + ".json")).write_text(json.dumps({
                "competitors": [{"id": "BOAT_A"}]}))

            export_archive(root, pre_n=120, live_n=80)
            directory = root / "public" / "data" / "predictions"
            index = json.loads((directory / "index.json").read_text())
            entry = next(item for item in index["races"] if item["race_id"] == race_id)
            artifact = json.loads((directory / entry["path"]).read_text())
            header = artifact["header"]
            self.assertEqual(header["boat_ids"], ["BOAT_A", "BOAT_B"])
            self.assertEqual(header["replay_boat_ids"], ["BOAT_A"])
            self.assertEqual(header["scheduled_entries"], [
                {"id": "BOAT_A", "team_code": "TEST_A", "team_name": "Synthetic A"},
                {"id": "BOAT_B", "team_code": "TEST_B", "team_name": "Synthetic B"}])
            self.assertEqual(entry["boat_ids"], header["boat_ids"])
            self.assertEqual(entry["replay_boat_ids"], header["replay_boat_ids"])
            self.assertEqual(set(artifact["pre_race"]["expected_position_by_boat"]), {"BOAT_A", "BOAT_B"})
            self.assertEqual(set(artifact["live"]["win_prob_by_boat"]), {"BOAT_A", "BOAT_B"})
            self.assertEqual(artifact["pre_race"]["status"], "estimated")
            self.assertIsNotNone(artifact["pre_race"]["expected_position_by_boat"]["BOAT_B"])
            verify_public(root)

            for key, incorrect in (("boat_ids", ["BOAT_A"]),
                                   ("replay_boat_ids", ["BOAT_A", "BOAT_B"])):
                with self.subTest(key=key):
                    mismatched = deepcopy(index)
                    target = next(item for item in mismatched["races"] if item["race_id"] == race_id)
                    target[key] = incorrect
                    with self.assertRaisesRegex(ValueError, "Index/scheduled roster mismatch"):
                        verify_public(root, index=mismatched)

    def test_modified_valid_parquet_cannot_be_reused_as_identical_source_data(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = fixture_archive(root)
            race_id = dataset["races"][0]["race_id"]
            parquet = root / ".forecast" / "dataset" / (race_id + ".parquet")
            table = pq.read_table(parquet).to_pylist()
            index = next(i for i, row in enumerate(table) if row["field"] == "gnss_position")
            original_latitude = table[index]["latitude"]
            table[index]["latitude"] = original_latitude + 0.01
            pq.write_table(pa.Table.from_pylist(table), parquet)
            # Rejecting an invalid derived cache or rebuilding it from the
            # unchanged raw bytes are both safe outcomes. Silent reuse is not.
            try:
                source_dataset(root)
                _, restored = load_dataset(root, race_id)
            except ValueError:
                return
            self.assertEqual(restored[index]["latitude"], original_latitude)

    def test_unsealed_load_requires_explicit_migration_and_metadata_tampering_is_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = fixture_archive(root)
            race_id = dataset["races"][0]["race_id"]
            metadata_path = root / ".forecast" / "dataset" / (race_id + ".json")
            metadata = json.loads(metadata_path.read_text())
            metadata.pop("metadata_sha256")
            metadata.pop("derived_table_sha256")
            metadata_path.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "Unsealed"):
                load_dataset(root, race_id)
            result = seal_existing_dataset(root)
            self.assertEqual(result["races"], 3)
            loaded, _ = load_dataset(root, race_id)
            self.assertEqual(loaded["cache_seal_method"], "explicit_fresh_conversion_migration_raw_hash_verified")
            loaded["gun_ms"] += 1
            metadata_path.write_text(json.dumps(loaded))
            with self.assertRaisesRegex(ValueError, "metadata content hash"):
                load_dataset(root, race_id)

    def test_manifest_model_and_cup_tampering_are_detected_from_actual_content(self):
        # Another test intentionally republishes after a failed build. Check
        # the currently active publication rather than an obsolete index copy.
        index = json.loads((self.directory / "index.json").read_text())
        paths = [self.directory / index["source_manifest_path"],
                 self.directory / "models" / (index["races"][1]["model_ref"] + ".json"),
                 self.directory / index["cup_path"]]
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                value = json.loads(original)
                value["tampered_fixture"] = True
                if path == self.directory / index["cup_path"]:
                    value["header"]["boat_class"] = "AC40"
                try:
                    path.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        verify_public(self.root)
                finally:
                    path.write_bytes(original)

    def test_invalid_status_indices_and_future_result_cutoffs_fail_closed(self):
        artifact = self.artifact(0)
        bad_status = deepcopy(artifact)
        bad_status["live"]["status_code"][0] = -1
        with self.assertRaises(ValueError):
            validate_race(bad_status)
        future = deepcopy(artifact)
        future["header"]["result_cutoff_ms"] = future["live"]["state_timestamps_ms"][0] + 1
        with self.assertRaises(ValueError):
            validate_race(future)

    def test_failed_rebuild_preserves_the_previous_complete_publication(self):
        # A source-code/lock change changes the source manifest. A later failed
        # race must leave the previously published index and its artifacts valid.
        index_bytes = (self.directory / "index.json").read_bytes()
        from pipeline.prediction import build
        real_build = build.build_race
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("synthetic second-race build failure")
            return real_build(*args, **kwargs)

        source_path = self.root / "pyproject.toml"
        source_path.write_text("# synthetic changed build input\n")
        try:
            with patch("pipeline.prediction.build.build_race", side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, "second-race"):
                    export_archive(self.root, pre_n=30, live_n=20)
            self.assertEqual((self.directory / "index.json").read_bytes(), index_bytes)
            verify_public(self.root)
        finally:
            source_path.unlink()
            # Restore the original complete fixture for later tests.
            export_archive(self.root, pre_n=1200, live_n=600)

    def test_open_subsecond_buckets_cannot_be_consumed_by_prefix_or_full_source(self):
        gun, records = tiny_source("2026-05-22", session_end=False)
        session = records[0]
        early = {"telemetry": {"asset_id": "BOAT_A", "timestamp": gun + 100,
                               "gnss_position": {"latitude": 50, "longitude": 1}}}
        later = {"telemetry": {"asset_id": "BOAT_A", "timestamp": gun + 900,
                               "gnss_position": {"latitude": 51, "longitude": 1}}}
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "26 05 22 CAG IPR Race 1.jsonl"
            source.write_text("\n".join(json.dumps(record) for record in (session, early)))
            prefix_meta, prefix_rows = read_source(source)
            source.write_text("\n".join(json.dumps(record) for record in (session, early, later)))
            full_meta, full_rows = read_source(source)
            prefix = CausalRace(prefix_meta, prefix_rows).position("BOAT_A", gun + 500)
            full = CausalRace(full_meta, full_rows).position("BOAT_A", gun + 500)
            # The parser's one-second reduction is publishable only after that
            # second has closed. Neither the prefix nor the full source can
            # expose an open bucket at this subsecond state cutoff.
            self.assertIsNone(prefix)
            self.assertIsNone(full)


if __name__ == "__main__":
    unittest.main()
