"""Hand-checkable same-leg comparisons and source-window safety cases."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline.historical_analysis import attach_performance_analysis


def metric(value, coverage=100, quality="derived"):
    return {"value": value, "coverage_s": coverage, "quality": quality, "unit": "kt"}


def boat(code, speed, retention=.8):
    legs, events = [], []
    for number in range(1, 5):
        start = 1_000_000 + (number - 1) * 100_000
        legs.append({"leg": number, "complete": True, "start_ms": start, "end_ms": start + 100_000,
                     "metrics": {"sog_mean_kt": metric(speed), "course_vmg_kt": metric(speed / 2),
                                 "elapsed_s": metric(100, quality="reconstructed")}})
        events.append({"type": "TACK" if number % 2 else "GYBE", "leg": number,
                       "timestamp": start + 50_000, "quality": "reconstructed",
                       "entry_speed_kt": 20, "min_speed_kt": 20 * retention,
                       "speed_loss_kt": 20 * (1 - retention)})
    return {"id": code, "classification": "RANK_1", "source_conflicts": [],
            "start": {"crossing_time_ms": 1_000_000, "ocs": False}, "legs": legs, "manoeuvres": events,
            "source_coverage": {field: {"first_ms": 900_000, "last_ms": 1_500_000, "gaps": []}
                                for field in ("sog", "heading", "twd")}}


def dimension(boat, key):
    return next(d for d in boat["performance"]["dimensions"] if d["id"] == key)


class PerformanceAnalysisTests(unittest.TestCase):
    def test_other_boats_mean_excludes_self_and_every_boat_has_one_vote(self):
        a, b, c = boat("A", 20), boat("B", 10), boat("C", 30)
        detail = {"boats": [a, b, c]}
        self.assertIs(attach_performance_analysis(detail), detail)
        upwind = dimension(a, "upwind_speed")
        self.assertEqual(upwind["index"], 100)
        self.assertEqual(upwind["peer_mean"], 20)
        self.assertEqual(upwind["peer_count"], 2)
        self.assertEqual(upwind["matched_legs"], [1, 3])
        self.assertEqual(upwind["coverage_s"], 200)
        self.assertEqual(dimension(b, "upwind_speed")["index"], 40)
        self.assertEqual(dimension(c, "upwind_speed")["index"], 200)
        self.assertEqual(a["performance"]["overall_index"], 100)
        json.dumps(detail, allow_nan=False)

    def test_indexes_average_leg_ratios_not_raw_aggregates(self):
        a, b = boat("A", 20), boat("B", 10)
        a["legs"][2]["metrics"]["sog_mean_kt"] = metric(30)
        b["legs"][2]["metrics"]["sog_mean_kt"] = metric(30)
        attach_performance_analysis({"boats": [a, b]})
        value = dimension(a, "upwind_speed")
        self.assertEqual(value["index"], 150)
        self.assertEqual(value["value"], 25)
        self.assertEqual(value["peer_mean"], 20)
        self.assertNotEqual(value["index"], 100 * value["value"] / value["peer_mean"])

    def test_partial_missing_or_mismatched_legs_do_not_enter_comparison(self):
        a, b = boat("A", 20), boat("B", 10)
        b["legs"][0]["metrics"]["sog_mean_kt"] = metric(10, coverage=94.99)
        b["legs"][2]["complete"] = False
        attach_performance_analysis({"boats": [a, b]})
        value = dimension(a, "upwind_speed")
        self.assertIsNone(value["index"])
        self.assertEqual(value["quality"], "unavailable")
        self.assertEqual(value["peer_count"], 0)
        self.assertIsNone(a["performance"]["overall_index"])
        self.assertIn("all six", a["performance"]["reason"])
        b["legs"][0]["metrics"]["sog_mean_kt"] = metric(10, coverage=95)
        attach_performance_analysis({"boats": [a, b]})
        self.assertEqual(dimension(a, "upwind_speed")["matched_legs"], [1])
        self.assertEqual(dimension(a, "upwind_speed")["index"], 200)

    def test_debrief_excludes_incomplete_and_partial_leg_comparisons(self):
        a, b = boat("A", 20), boat("B", 20)
        for leg in b["legs"]:
            leg["metrics"]["elapsed_s"]["value"] = 90
            leg["metrics"]["sog_mean_kt"]["quality"] = "partial"
        attach_performance_analysis({"boats": [a, b]})
        self.assertFalse(any(item["kind"] == "leg_deficit" for item in a["debrief"]["items"]))
        for leg in b["legs"]:
            leg["metrics"]["sog_mean_kt"]["quality"] = "derived"
            leg["complete"] = False
        attach_performance_analysis({"boats": [a, b]})
        self.assertFalse(any(item["kind"] == "leg_deficit" for item in a["debrief"]["items"]))

    def test_conflicts_and_non_starters_retirements_are_excluded_as_peers(self):
        for state in ("RET", "RETIRED", "DNS", "DID_NOT_START", "OCS", "conflict"):
            with self.subTest(state=state):
                a, b = boat("A", 20), boat("B", 10)
                if state == "conflict":
                    b["source_conflicts"] = ["start state disagrees"]
                else:
                    b["classification"] = state
                attach_performance_analysis({"boats": [a, b]})
                self.assertTrue(all(d["index"] is None for d in a["performance"]["dimensions"]))
                self.assertEqual(b["debrief"]["items"], [])

    def test_zero_negative_and_non_finite_peer_values_remain_unavailable(self):
        for value in (0, -10, float("nan"), float("inf")):
            a, b = boat("A", 20), boat("B", value)
            attach_performance_analysis({"boats": [a, b]})
            self.assertIsNone(dimension(a, "upwind_speed")["index"])

    def test_single_boat_and_ineligible_window_do_not_impute_a_score(self):
        a = boat("A", 20)
        attach_performance_analysis({"boats": [a]})
        self.assertTrue(all(d["index"] is None for d in a["performance"]["dimensions"]))
        a, b = boat("A", 20), boat("B", 10)
        a["start"]["crossing_time_ms"] = None
        attach_performance_analysis({"boats": [a, b]})
        self.assertTrue(all(d["index"] is None for d in a["performance"]["dimensions"]))

    def test_retention_uses_same_leg_and_equal_weight_peer_boats(self):
        a, b, c = boat("A", 20, .8), boat("B", 20, .5), boat("C", 20, .85)
        b["manoeuvres"].extend(copy.deepcopy(b["manoeuvres"]))
        attach_performance_analysis({"boats": [a, b, c]})
        value = dimension(a, "tack_retention")
        self.assertAlmostEqual(value["value"], 80)
        self.assertAlmostEqual(value["peer_mean"], 67.5)
        self.assertAlmostEqual(value["index"], 100 * 80 / 67.5)
        self.assertEqual(value["sample_count"], 2)
        self.assertEqual(value["coverage_s"], 25)
        self.assertEqual(value["quality"], "reconstructed")

    def test_retention_excludes_rounding_missing_sources_and_full_window_gaps(self):
        a, b = boat("A", 20), boat("B", 20)
        b["manoeuvres"][0]["quality"] = "ambiguous_rounding"
        # Event timestamp itself is covered; a gap before onset still rejects it.
        timestamp = b["manoeuvres"][2]["timestamp"]
        b["source_coverage"]["sog"]["gaps"] = [[timestamp - 6000, timestamp - 3000]]
        attach_performance_analysis({"boats": [a, b]})
        self.assertIsNone(dimension(a, "tack_retention")["index"])
        self.assertEqual(dimension(a, "gybe_retention")["index"], 100)
        b["source_coverage"] = None
        attach_performance_analysis({"boats": [a, b]})
        self.assertIsNone(dimension(a, "gybe_retention")["index"])

    def test_retention_requires_search_window_inside_completed_leg(self):
        a, b = boat("A", 20), boat("B", 20)
        for event in b["manoeuvres"]:
            event["timestamp"] -= 45_000
        attach_performance_analysis({"boats": [a, b]})
        self.assertIsNone(dimension(a, "tack_retention")["index"])

    def test_200ms_cadence_covers_the_full_detector_search_window(self):
        a, b = boat("A", 20), boat("B", 20)
        attach_performance_analysis({"race": {"sample_interval_ms": 200}, "boats": [a, b]})
        value = dimension(a, "tack_retention")
        self.assertEqual(value["index"], 100)
        self.assertEqual(value["coverage_s"], 50)
        self.assertTrue(all(evidence["coverage_s"] == 25 for evidence in value["leg_evidence"]))
        self.assertIn("[-13,+12] s", value["source"])
        self.assertIn("validated 25 s", a["performance"]["notes"][3])

    def test_200ms_cadence_rejects_gap_outside_the_default_window(self):
        a, b = boat("A", 20), boat("B", 20)
        b["source_coverage"]["sog"]["gaps"] = [
            [event["timestamp"] - 12_000, event["timestamp"] - 10_000]
            for event in b["manoeuvres"] if event["type"] == "TACK"]
        attach_performance_analysis({"boats": [a, b]})
        self.assertEqual(dimension(a, "tack_retention")["index"], 100)
        attach_performance_analysis({"race": {"sample_interval_ms": 200}, "boats": [a, b]})
        self.assertIsNone(dimension(a, "tack_retention")["index"])
        self.assertFalse(any(item["kind"] == "manoeuvre_loss" and item["title"].startswith("Tack")
                             for item in b["debrief"]["items"]))

    def test_200ms_cadence_excludes_detector_support_crossing_leg_start(self):
        a, b = boat("A", 20), boat("B", 20)
        for event in b["manoeuvres"]:
            event["timestamp"] -= 40_000
        attach_performance_analysis({"boats": [a, b]})
        self.assertEqual(dimension(a, "tack_retention")["index"], 100)
        attach_performance_analysis({"race": {"sample_interval_ms": 200}, "boats": [a, b]})
        self.assertIsNone(dimension(a, "tack_retention")["index"])

    def test_default_cadence_and_explicit_100ms_outputs_match(self):
        boats = [boat("A", 20), boat("B", 10)]
        implicit = attach_performance_analysis({"boats": copy.deepcopy(boats)})
        explicit = attach_performance_analysis({"race": {"sample_interval_ms": 100}, "boats": boats})
        self.assertEqual(implicit["boats"], explicit["boats"])
        self.assertIn("[-6.5,+6] s", dimension(boats[0], "tack_retention")["source"])
        self.assertIn("validated 12.5 s", boats[0]["performance"]["notes"][3])

    def test_nondefault_regular_grid_cadence_is_exported(self):
        from tests.unit.test_historical_analysis import analyze_synthetic
        # This hand-checkable fixture uses a one-second regular grid.
        self.assertEqual(analyze_synthetic()["race"]["sample_interval_ms"], 1000)

    def test_nonuniform_grid_and_invalid_cadence_are_rejected(self):
        from pipeline.historical_analysis import build_race_analysis
        from tests.unit.test_historical_analysis import synthetic_race
        ingestion, reconstruction, manoeuvres, legs = synthetic_race()
        ingestion.grid_timestamps_ms[-1] += 1
        with self.assertRaisesRegex(ValueError, "regular, increasing"):
            build_race_analysis(ingestion, reconstruction, manoeuvres, legs,
                                "test", "Test", "2026-11-01", "Test")
        for cadence in (0, -100, False, float("nan"), float("inf"), "100"):
            with self.subTest(cadence=cadence), self.assertRaisesRegex(ValueError, "positive and finite"):
                attach_performance_analysis({"race": {"sample_interval_ms": cadence}, "boats": []})

    def test_overlapping_event_support_counts_unique_seconds(self):
        a, b = boat("A", 20), boat("B", 20)
        duplicate = copy.deepcopy(a["manoeuvres"][0])
        duplicate["timestamp"] += 1000
        a["manoeuvres"].append(duplicate)
        attach_performance_analysis({"boats": [a, b]})
        value = dimension(a, "tack_retention")
        self.assertEqual(value["sample_count"], 3)
        self.assertEqual(value["coverage_s"], 26)

    def test_completed_legs_of_non_finisher_remain_useful(self):
        a, b = boat("A", 20), boat("B", 10)
        b["classification"] = "DNF"
        attach_performance_analysis({"boats": [a, b]})
        self.assertEqual(dimension(a, "upwind_speed")["index"], 200)

    def test_debrief_ranks_observed_peer_deficits_and_limits_review_items(self):
        a, b = boat("A", 20), boat("B", 20, .6)
        for number, leg in enumerate(a["legs"]):
            leg["metrics"]["elapsed_s"]["value"] = 110 + number
        attach_performance_analysis({"boats": [a, b]})
        items = a["debrief"]["items"]
        deficits = [i for i in items if i["kind"] == "leg_deficit"]
        manoeuvres = [i for i in items if i["kind"] == "manoeuvre_loss"]
        self.assertEqual([i["leg"] for i in deficits], [4, 3, 2])
        self.assertEqual([i["value"] for i in deficits], [13, 12, 11])
        self.assertEqual(len(manoeuvres), 2)
        self.assertTrue(all(i["timestamp_ms"] and i["source"] for i in items))
        self.assertIn("does not identify a cause", deficits[0]["detail"])
        self.assertIn("not an estimate of time", manoeuvres[0]["detail"])

    def test_repeat_attachment_is_identical(self):
        detail = {"boats": [boat("A", 20), boat("B", 10)]}
        attach_performance_analysis(detail)
        first = json.dumps(detail, sort_keys=True, allow_nan=False)
        attach_performance_analysis(detail)
        self.assertEqual(first, json.dumps(detail, sort_keys=True, allow_nan=False))

    def test_evidence_names_values_windows_and_exclusions_are_traceable(self):
        a, b, c = boat("A", 20), boat("B", 10), boat("C", 30)
        c["source_conflicts"] = ["source start mismatch"]
        attach_performance_analysis({"boats": [a, b, c]})
        axis = dimension(a, "upwind_vmg")
        evidence = axis["leg_evidence"][0]
        self.assertEqual(evidence["peers"][0]["id"], "B")
        self.assertEqual(evidence["peers"][0]["value"], 5)
        self.assertEqual(evidence["peers"][0]["coverage_s"], 100)
        self.assertEqual((evidence["start_ms"], evidence["end_ms"]), (1_000_000, 1_100_000))
        self.assertEqual(evidence["excluded_peers"][0]["id"], "C")
        self.assertIn("conflicts", evidence["excluded_peers"][0]["reason"])
        self.assertEqual(a["performance"]["scope"], {"expected_legs": [1, 2, 3, 4], "matched_legs": [1, 2, 3, 4],
                         "expected_leg_count": 4, "matched_leg_count": 4, "min_peer_count": 1,
                         "covered_s": 400, "excluded_legs": []})
        event = dimension(a, "tack_retention")["leg_evidence"][0]["events"][0]
        self.assertEqual(event["retention_pct"], 80)
        self.assertEqual(event["window_end_ms"] - event["window_start_ms"], 12500)

    def test_missing_match_final_crossing_is_explicitly_four_of_six(self):
        path = Path(__file__).resolve().parents[2] / "public/data/analysis/naples_mr_final.json"
        detail = attach_performance_analysis(json.loads(path.read_text(encoding="utf-8")))
        selected = next(b for b in detail["boats"] if b["team_code"] == "ITA B")
        self.assertEqual(selected["performance"]["scope"]["matched_legs"], [1, 2, 3, 4])
        self.assertEqual(selected["performance"]["scope"]["expected_leg_count"], 6)
        self.assertEqual([entry["leg"] for entry in selected["performance"]["scope"]["excluded_legs"]], [5, 6])
        self.assertFalse(selected["legs"][4]["complete"])
        self.assertFalse(selected["legs"][5]["complete"])
        self.assertIsNotNone(selected["performance"]["overall_index"])

    def test_nonchronological_source_gate_explains_exclusion_without_repair(self):
        folder = Path(__file__).resolve().parents[2] / "public/data/analysis"
        detail = attach_performance_analysis(json.loads((folder / "26_09_22_nap_ipr_pr2.json").read_text(encoding="utf-8")))
        selected = next(b for b in detail["boats"] if b["team_code"] == "USA")
        entry = next(e for e in selected["performance"]["scope"]["excluded_legs"] if e["leg"] == 3)
        self.assertIn("non-increasing", entry["reason"])
        self.assertGreater(selected["legs"][2]["start_ms"], selected["legs"][2]["end_ms"])

    def test_metadata_refresh_preserves_all_published_numeric_performance_values(self):
        folder = Path(__file__).resolve().parents[2] / "public/data/analysis"
        keys = ("index", "value", "peer_mean", "peer_count", "coverage_s", "sample_count", "matched_legs", "quality")
        paths = [path for path in folder.glob("*.json") if path.name != "index.json"]
        self.assertEqual(len(paths), 28)
        for path in paths:
            detail = json.loads(path.read_text(encoding="utf-8"))
            before = [(b["performance"]["overall_index"], [{key: d[key] for key in keys} for d in b["performance"]["dimensions"]]) for b in detail["boats"]]
            attach_performance_analysis(detail)
            after = [(b["performance"]["overall_index"], [{key: d[key] for key in keys} for d in b["performance"]["dimensions"]]) for b in detail["boats"]]
            self.assertEqual(before, after, path.name)
        detail = json.loads((folder / "naples_pr1.json").read_text(encoding="utf-8"))
        axis = dimension(next(b for b in detail["boats"] if b["team_code"] == "ITA G"), "downwind_vmg")
        self.assertAlmostEqual(axis["index"], 109.9671, places=4)
        self.assertAlmostEqual(axis["leg_evidence"][0]["index"], 127.0241, places=4)
        self.assertAlmostEqual(axis["leg_evidence"][1]["index"], 92.9101, places=4)
        self.assertAlmostEqual(100 * axis["value"] / axis["peer_mean"], 108.0853, places=4)

    def test_fast_performance_refresh_preserves_tactical_data_and_never_reads_raw(self):
        from scripts.refresh_team_analytics import refresh
        detail = {"schema_version": "2.0", "method_version": "historical-2", "race": {"id": "test"},
                  "boats": [boat("A", 20), boat("B", 10)], "tactical_insights": {"snapshots": [], "marker": "preserved"}}
        for entry in detail["boats"]:
            entry["team_code"] = entry["id"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analysis = root / "public/data/analysis"
            analysis.mkdir(parents=True)
            (root / "public/data/manifests.json").write_text(json.dumps({"races": [{"id": "test"}]}), encoding="utf-8")
            (analysis / "test.json").write_text(json.dumps(detail), encoding="utf-8")
            with patch("scripts.refresh_team_analytics.read_source_wind", side_effect=AssertionError("raw scan forbidden")), \
                 patch("scripts.refresh_team_analytics.build_historical_index", return_value={"schema_version": "2.0"}), \
                 patch("scripts.refresh_team_analytics.build_inventory") as inventory:
                result = refresh(root, performance_only=True)
            refreshed = json.loads((analysis / "test.json").read_text(encoding="utf-8"))
            self.assertEqual(refreshed["tactical_insights"], detail["tactical_insights"])
            self.assertIn("scope", refreshed["boats"][0]["performance"])
            self.assertEqual(result["boat_race_count"], 2)
            inventory.assert_called_once_with(root)
            self.assertTrue((analysis / "test_performance.csv").is_file())


if __name__ == "__main__":
    unittest.main()
