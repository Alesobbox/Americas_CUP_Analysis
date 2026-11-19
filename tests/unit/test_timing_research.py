"""Exact accounting, geometric event selection and censored reference deficits."""

from __future__ import annotations

import copy
import unittest

from pipeline.research.timing_research import build_timing_research
from pipeline.research.maneuver_review import evaluate_reviewed_windows
from pipeline.research.timing_track import SOURCE_FIELDS


def _fixture() -> tuple[dict, dict]:
    timestamps = [i * 1000 for i in range(161)]
    boats, telemetry = [], {}
    for index, identifier in enumerate(("a", "b")):
        start = 1000 + 2000 * index
        end_leg_one, finish = 81000 + 2000 * index, 151000 + 2000 * index
        boat = {
            "id": identifier,
            "team_code": identifier.upper(),
            "classification": f"RANK_{index + 1}",
            "official_elapsed_s": finish / 1000,
            "source_conflicts": [],
            "source_coverage": {
                field: {"first_ms": 0, "last_ms": timestamps[-1], "gaps": []}
                for field in SOURCE_FIELDS
            },
            "start": {"crossing_time_ms": start, "ocs": False},
            "gates": [{"crossing_time_ms": end_leg_one}, {"crossing_time_ms": finish}],
            "legs": [
                {"leg": 1, "start_ms": start, "end_ms": end_leg_one, "complete": True},
                {"leg": 2, "start_ms": end_leg_one, "end_ms": finish, "complete": True},
            ],
        }
        headings = []
        for second in range(161):
            heading = -45 if second < 40 else 45 if second > 50 else -45 + 9 * (second - 40)
            headings.append(heading % 360)
        telemetry[identifier] = {
            "heading": headings,
            "cog": headings,
            "sog": [30.0] * len(timestamps),
            "twd": [0.0] * len(timestamps),
            "tws": [12.0] * len(timestamps),
            "x": [index * 200.0] * len(timestamps),
            "y": [float(i) * 10 for i in range(len(timestamps))],
        }
        boats.append(boat)
    detail = {"race": {"id": "test", "date": "2026-09-22", "gun_time_ms": 0}, "boats": boats}
    replay = {
        "course": {"axis_deg": 0},
        "telemetry": {"timestamps": timestamps, "boats": telemetry},
    }
    return detail, replay


class TimingResearchTests(unittest.TestCase):
    def test_checkpoint_and_peer_components_reconcile_exactly(self):
        detail, replay = _fixture()
        result = build_timing_research(detail, replay)
        first = result["boats"][0]["ledger"]
        self.assertTrue(first["complete_finish"])
        self.assertEqual(first["accounted_elapsed_s"], 151)
        self.assertEqual(first["reconciliation_error_s"], 0)
        self.assertEqual(first["reported_elapsed_difference_s"], 0)
        peers = first["peer_comparison"]
        self.assertEqual(peers["total_difference_s"], -2)
        self.assertEqual(sum(c["difference_s"] for c in peers["components"]), -2)
        self.assertEqual(peers["reconciliation_error_s"], 0)

    def test_phases_are_disjoint_with_gaps_and_overlapping_turn_gate_windows(self):
        detail, replay = _fixture()
        detail["boats"][0]["gates"].append({"crossing_time_ms": 45000})
        detail["boats"][0]["source_coverage"]["sog"]["gaps"] = [[44500, 45500]]
        result = build_timing_research(detail, replay)
        phases = result["boats"][0]["phases"]
        self.assertEqual(phases["reconciliation_error_s"], 0)
        self.assertAlmostEqual(sum(phases["seconds"].values()), 150)
        self.assertAlmostEqual(phases["seconds"]["unavailable"], 1)
        self.assertGreater(phases["seconds"]["gate_approach"], 16)

    def test_clean_constant_speed_tack_is_included_without_speed_loss_filter(self):
        detail, replay = _fixture()
        turns = build_timing_research(detail, replay)["boats"][0]["turns"]
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["type"], "TACK")
        self.assertEqual(turns[0]["recovery"]["speed_loss_kt"], 0)
        self.assertEqual(turns[0]["recovery"]["physical_event_label"], None)
        self.assertEqual([h["horizon_s"] for h in turns[0]["horizons"]], [10, 20, 30])

    def test_gap_censors_cost_and_recovery(self):
        detail, replay = _fixture()
        detail["boats"][0]["source_coverage"]["sog"]["gaps"] = [[52000, 62000]]
        for second in range(40, 70):
            replay["telemetry"]["boats"]["a"]["sog"][second] = 10
        event = build_timing_research(detail, replay)["boats"][0]["turns"][0]
        horizon = event["horizons"][-1]
        self.assertTrue(horizon["right_censored"])
        self.assertEqual(horizon["censor_reason"], "source_gap")
        self.assertIsNone(horizon["progress_deficit_m"])
        self.assertTrue(event["recovery"]["right_censored"])
        self.assertIsNone(event["recovery"]["recovery_s"])

    def test_gate_and_next_turn_limit_horizons(self):
        detail, replay = _fixture()
        detail["boats"][0]["legs"][0]["end_ms"] = 60000
        detail["boats"][0]["legs"][1]["start_ms"] = 60000
        event = build_timing_research(detail, replay)["boats"][0]["turns"][0]
        self.assertFalse(event["horizons"][0]["right_censored"])
        self.assertTrue(event["horizons"][-1]["right_censored"])
        self.assertEqual(event["horizons"][-1]["censor_reason"], "gate_approach")

    def test_polar_reference_queries_only_supported_pre_turn_conditions(self):
        detail, replay = _fixture()
        queries = []

        def predictor(features):
            queries.append(features)
            return {"sog_kt": 31, "evaluation_scope": "leave_one_day_out", "support": 40}

        event = build_timing_research(detail, replay, predictor)["boats"][0]["turns"][0]
        self.assertTrue(queries)
        self.assertLess(queries[0]["timestamp_ms"], event["start_ms"])
        self.assertGreaterEqual(queries[0]["abs_twa_deg"], 28)
        self.assertIsNotNone(event["horizons"][0]["polar_reference_deficit_m"])

        def wrong_scope(_):
            return {"sog_kt": 31, "evaluation_scope": "full_data"}

        refused = build_timing_research(detail, replay, wrong_scope)["boats"][0]["turns"][0]
        self.assertEqual(refused["reference"]["polar"]["quality"], "unavailable")

    def test_incomplete_or_conflicted_finish_remains_partial(self):
        detail, replay = _fixture()
        detail["boats"][0]["classification"] = "DNF"
        detail["boats"][0]["legs"][-1]["complete"] = False
        detail["boats"][1]["source_conflicts"] = ["contradictory source start state"]
        result = build_timing_research(detail, replay)
        for row in result["boats"]:
            self.assertFalse(row["ledger"]["complete_finish"])
            self.assertIsNone(row["ledger"]["peer_comparison"])

    def test_missing_coverage_is_unavailable_and_input_is_not_mutated(self):
        detail, replay = _fixture()
        detail["boats"][0]["source_coverage"] = {}
        snapshot = copy.deepcopy(detail)
        result = build_timing_research(detail, replay)
        self.assertEqual(result["boats"][0]["phases"]["seconds"]["unavailable"], 150)
        self.assertEqual(result["boats"][0]["turns"], [])
        self.assertEqual(detail, snapshot)

    def test_unreviewed_windows_do_not_become_detector_labels(self):
        detail, replay = _fixture()
        row = build_timing_research(detail, replay)["boats"][0]
        self.assertEqual(row["detector_evaluation"]["status"], "insufficient_reviewed_labels")
        self.assertIsNone(row["detector_evaluation"]["precision"])
        self.assertTrue(any(window["stratum"] == "background" for window in row["review_queue"]))
        ordered = sorted(row["review_queue"], key=lambda window: window["start_ms"])
        self.assertTrue(all(a["end_ms"] < b["start_ms"] for a, b in zip(ordered, ordered[1:])))

    def test_review_matching_is_one_to_one_and_rejects_overlapping_windows(self):
        predictions = [
            {"type": "TACK", "timestamp_ms": 10000},
            {"type": "TACK", "timestamp_ms": 11000},
        ]
        window = {
            "start_ms": 0,
            "end_ms": 20000,
            "review_status": "reviewed",
            "reviewed_events": [{"type": "TACK", "timestamp_ms": 10500}],
        }
        result = evaluate_reviewed_windows(predictions, [window])
        self.assertEqual(result["true_positive"], 1)
        self.assertEqual(result["false_positive"], 1)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 1)
        with self.assertRaises(ValueError):
            evaluate_reviewed_windows(predictions, [window, window])


if __name__ == "__main__":
    unittest.main()
