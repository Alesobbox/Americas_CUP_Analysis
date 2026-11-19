"""Forecast causality, circular targets, source gaps and grouped evaluation."""

import copy
import math
import unittest

from pipeline.research.wind_forecast import _reliability, run_wind_forecast
from pipeline.research.wind_forecast_data import build_contexts, previous_grid, prior_training_rows
from pipeline.research.wind_forecast_models import (
    circular_pair_mean,
    distribution_prediction,
    fit_models,
    score_prediction,
)


def wind_record(day, index, seconds=700):
    start = 1_790_000_000_000 + index * 86_400_000
    return {
        "id": f"r{index}",
        "date": day,
        "gun_time_ms": start + 120_000,
        "window_end_ms": start + seconds * 1000,
        "samples": [
            {
                "timestamp_ms": start + second * 1000,
                "twd_deg": (358 + 7 * math.sin(second / 95 + index) + 0.01 * second) % 360,
            }
            for second in range(seconds + 1)
        ],
    }


class WindForecastTests(unittest.TestCase):
    def test_exact_circular_distribution_matches_pairwise_definition(self):
        import numpy as np

        from pipeline.research.wind_forecast_data import wrapped

        values = np.array([-179.0, -150.0, -2.0, 0.0, 5.0, 40.0, 178.0])
        expected = float(np.abs(wrapped(values[:, None] - values[None, :])).mean())
        self.assertAlmostEqual(circular_pair_mean(values), expected, places=10)

    def test_endpoint_wrap_and_future_do_not_enter_features(self):
        record = wind_record("2026-09-22", 0)
        rows, _ = build_contexts(record)
        changed = copy.deepcopy(record)
        issue = rows[0]["issue_ms"]
        for sample in changed["samples"]:
            if sample["timestamp_ms"] > issue:
                sample["twd_deg"] = (sample["twd_deg"] + 40) % 360
        revised, _ = build_contexts(changed)
        self.assertEqual(rows[0]["features"], revised[0]["features"])
        self.assertNotEqual(rows[0]["target_delta_deg"], revised[0]["target_delta_deg"])
        self.assertGreater(rows[0]["target_delta_deg"], -180)
        self.assertLessEqual(rows[0]["target_delta_deg"], 180)

    def test_source_gap_and_end_of_record_are_not_zero_targets(self):
        self.assertIsNone(previous_grid(([0, 1000, 3500], [359.0, 1.0, 3.0]), 0, 4000))
        record = wind_record("2026-09-22", 0, seconds=400)
        rows, counts = build_contexts(record)
        self.assertGreater(counts["censored_target"], 0)
        self.assertIsNone(rows[-1]["target_delta_deg"])

    def test_training_purges_horizons_not_available_at_issue(self):
        rows = [
            {"date": "2026-09-21", "label_end_ms": end, "target_delta_deg": 4.0}
            for end in (999, 1000, 1001)
        ]
        selected = prior_training_rows(rows, "2026-09-22", 1000)
        self.assertEqual([row["label_end_ms"] for row in selected], [999])

    def test_chronological_forecasts_ignore_changed_same_day_future(self):
        records = [wind_record(f"2026-09-{22 + index}", index) for index in range(4)]
        result = run_wind_forecast(records)
        revised = copy.deepcopy(records)
        first = result["per_race"]["r3"]["predictions"][0]
        for sample in revised[-1]["samples"]:
            if sample["timestamp_ms"] > first["timestamp_ms"]:
                sample["twd_deg"] = (sample["twd_deg"] + 30) % 360
        changed = run_wind_forecast(revised)
        self.assertEqual(first["methods"], changed["per_race"]["r3"]["predictions"][0]["methods"])
        self.assertEqual(result["by_day"]["2026-09-22"]["status"], "unavailable")
        self.assertEqual(result["validation"]["local_angle_ar"]["scored_days"], 3)
        for race in result["per_race"].values():
            for prediction in race["predictions"]:
                self.assertLess(race["training_last_label_ms"], prediction["timestamp_ms"])

    def test_circular_distribution_scores_and_reliability_are_finite(self):
        records = [wind_record(f"2026-09-{22 + index}", index) for index in range(2)]
        rows = [
            row
            for record in records
            for row in build_contexts(record)[0]
            if row["target_delta_deg"] is not None
        ]
        model = fit_models(rows)
        prediction = distribution_prediction(model, "probabilistic_persistence", rows[0])
        scores = score_prediction(prediction, rows[0]["target_delta_deg"])
        self.assertTrue(all(math.isfinite(value) for value in scores.values()))
        self.assertGreaterEqual(scores["circular_crps_deg"], 0)
        self.assertGreater(prediction["probability"], 0)
        self.assertLess(prediction["probability"], 1)
        bins = _reliability(
            [{"probability": value, "event": 0} for value in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        )
        self.assertEqual(sum(item["count"] for item in bins), 6)


if __name__ == "__main__":
    unittest.main()
