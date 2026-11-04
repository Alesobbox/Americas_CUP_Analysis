"""Frozen-date, race-level scoring and available-forecast contracts."""
from datetime import datetime, timezone
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from pipeline.prediction.evaluation import (AUDIT_DAYS, DEVELOPMENT_DAYS,
                                                GUARD_BUDGETS, aggregate,
                                                guardrails, promotion, scores)
    from pipeline.prediction.labels import before_day
    from pipeline.prediction.weather import ForecastWind, available_run, condition_support


@unittest.skipIf(np is None, "Install the locked forecast-core extra")
class PredictionEvaluationTests(unittest.TestCase):
    def test_actual_day_and_result_availability_both_precede_frozen_cutoff(self):
        cutoff = int(datetime(2026, 9, 26, tzinfo=timezone.utc).timestamp()*1000)
        rows = [
            {"id": "earlier-known", "date": "2026-09-25", "available_at_ms": cutoff-1},
            {"id": "published-at-cutoff", "date": "2026-09-25", "available_at_ms": cutoff},
            {"id": "earlier-but-late", "date": "2026-05-22", "result_available_at_ms": cutoff+1000},
            {"id": "same-day", "date": "2026-09-26", "available_at_ms": cutoff-1},
            {"id": "26_09_25_nap_ipr_race_3", "date": "2026-09-26", "available_at_ms": cutoff+1000},
        ]
        self.assertEqual([r["id"] for r in before_day(rows, "2026-09-26")], ["earlier-known"])
        self.assertEqual(DEVELOPMENT_DAYS, ("2026-05-23", "2026-05-24", "2026-09-25"))
        self.assertEqual(AUDIT_DAYS, ("2026-09-26", "2026-09-27"))

    def test_checkpoints_are_averaged_within_race_before_race_and_day(self):
        rows = [
            {"date": "A", "race_id": "one", "checkpoint": k, "log_loss": loss}
            for k, loss in enumerate([1., 3., 2.])
        ] + [{"date": "A", "race_id": "two", "log_loss": 6.},
             {"date": "B", "race_id": "three", "log_loss": 10.}]
        result = aggregate(rows)
        self.assertEqual(result["race_count"], 3)
        self.assertEqual(result["independent_days"], 2)
        self.assertAlmostEqual(result["race_equal"]["log_loss"], 6.)
        self.assertAlmostEqual(result["day_equal"]["log_loss"], 7.)
        self.assertEqual(result["leave_one_day"]["A"]["log_loss"], 10.)
        self.assertEqual(result["leave_one_day"]["B"]["log_loss"], 4.)
        duplicate_checkpoints = aggregate(rows[:3]*100 + rows[3:])
        self.assertEqual(result["race_equal"], duplicate_checkpoints["race_equal"])
        self.assertEqual(result["day_equal"], duplicate_checkpoints["day_equal"])

    def test_sum_brier_rank_rps_and_normalized_position_mse(self):
        result = scores([.5, .5, 0.], 0, [1.5, 2., 2.5], [1, 2, 3],
                        rank_cdf=[[.6, .9], [.2, .8], [.1, .3]])
        self.assertAlmostEqual(result["log_loss"], -math.log(.5))
        self.assertAlmostEqual(result["brier"], .5)
        self.assertAlmostEqual(result["normalized_rps"], .35/6)
        self.assertAlmostEqual(result["normalized_mse"], 1/24)

    def test_tied_N_nonfinishers_do_not_require_rank_sum_conservation(self):
        positions = [1, 2, 5, 5, 5]
        cdf = (np.asarray(positions)[:, None] <= np.arange(1, 5)).astype(float)
        result = scores([1., 0., 0., 0., 0., 0.], 0, positions, positions, cdf)
        self.assertEqual(result["normalized_rps"], 0.)
        self.assertEqual(result["normalized_mse"], 0.)
        self.assertEqual(sum(positions), 18)

    def test_single_entry_rank_targets_are_deterministic(self):
        result = scores([1.], 0, [1.], [1.], np.empty((1, 0)))
        self.assertEqual(result["normalized_rps"], 0.)
        self.assertEqual(result["normalized_mse"], 0.)

    def test_scoring_rejects_incoherent_or_unknown_inputs(self):
        for probabilities in [[.4, .4], [-.1, 1.1], [float("nan"), 0.]]:
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                scores(probabilities, 0)
        with self.assertRaises(ValueError):
            scores([.5, .5], -1)
        with self.assertRaises(ValueError):
            scores([.5, .5], 2)
        for expected, observed, cdf in [
            ([1., float("nan")], [1, 2], [[.5], [.5]]),
            ([1., 2.], [0, 2], [[.5], [.5]]),
            ([1., 2.], [1, 2], [[1.1], [.5]]),
            ([1., 2., 3.], [1, 2, 3], [[.9, .1], [.4, .5], [.1, .2]]),
        ]:
            with self.subTest(expected=expected, observed=observed, cdf=cdf), self.assertRaises(ValueError):
                scores([.5, .5], 0, expected, observed, cdf)

    def _aggregate(self, *, log_loss=1., brier=.4, rps=.2, mse=.2, race="same"):
        return aggregate([{"date": day, "race_id": f"{race}-{day}", "log_loss": log_loss,
                           "brier": brier, "normalized_rps": rps, "normalized_mse": mse}
                          for day in DEVELOPMENT_DAYS])

    def test_practical_budgets_allow_small_loss_increases_but_require_primary_gain(self):
        reference = self._aggregate()
        candidate = self._aggregate(log_loss=.9, brier=.409, rps=.219, mse=.219)
        self.assertTrue(promotion(candidate, reference)["promoted"])
        self.assertFalse(promotion(self._aggregate(log_loss=1.), reference)["promoted"])
        self.assertFalse(promotion(self._aggregate(log_loss=.9, brier=.411), reference)["promoted"])
        self.assertFalse(promotion(self._aggregate(log_loss=.9, rps=.221), reference)["promoted"])
        self.assertEqual(GUARD_BUDGETS, {"brier": .01, "normalized_rps": .02, "normalized_mse": .02})

    def test_live_only_extension_does_not_require_unrelated_prerace_improvement(self):
        reference = self._aggregate()
        candidate = self._aggregate(log_loss=.9, brier=.409, rps=.5, mse=.5)
        self.assertTrue(promotion(candidate, reference, applicable=("brier",))["promoted"])

    def test_missing_applicable_metric_or_unpaired_race_prevents_promotion(self):
        reference = self._aggregate()
        candidate = self._aggregate(log_loss=.9)
        for averaging in ["race_equal", "day_equal"]:
            del candidate[averaging]["normalized_rps"]
        self.assertFalse(promotion(candidate, reference)["promoted"])
        self.assertFalse(promotion(self._aggregate(log_loss=.9, race="different"), reference)["promoted"])

    def test_primary_improvement_must_hold_under_both_race_and_day_weighting(self):
        reference_rows = [{"date": "A", "race_id": f"A-{k}", "log_loss": 1., "brier": .4}
                          for k in range(3)] + [{"date": "B", "race_id": "B", "log_loss": 1., "brier": .4}]
        candidate_rows = [dict(row, log_loss=.8 if row["date"] == "A" else 1.5) for row in reference_rows]
        reference, candidate = aggregate(reference_rows), aggregate(candidate_rows)
        self.assertLess(candidate["race_equal"]["log_loss"], reference["race_equal"]["log_loss"])
        self.assertGreater(candidate["day_equal"]["log_loss"], reference["day_equal"]["log_loss"])
        self.assertFalse(promotion(candidate, reference, applicable=("brier",))["promoted"])

    def test_prerace_guardrails_do_not_invent_an_extra_primary_gain_requirement(self):
        result = guardrails(self._aggregate(log_loss=4., rps=.219, mse=.219), self._aggregate(),
                            applicable=("normalized_rps", "normalized_mse"))
        self.assertTrue(result["passed"])

    def test_same_race_different_checkpoint_coverage_is_not_paired(self):
        reference = aggregate([{"date": "A", "race_id": "one", "checkpoint": 10,
                                "log_loss": 1., "brier": .4}])
        candidate = aggregate([{"date": "A", "race_id": "one", "checkpoint": 20,
                                "log_loss": .5, "brier": .3}])
        self.assertFalse(promotion(candidate, reference, applicable=("brier",))["promoted"])

    def test_partial_metric_coverage_cannot_hide_a_difficult_race(self):
        rows = [{"date": day, "race_id": day, "log_loss": 1., "brier": .4,
                 "normalized_rps": .2} for day in DEVELOPMENT_DAYS]
        candidate = [dict(row, log_loss=.5) for row in rows]
        candidate[-1].pop("normalized_rps")
        self.assertFalse(promotion(aggregate(candidate), aggregate(rows),
                                   applicable=("brier", "normalized_rps"))["promoted"])


@unittest.skipIf(np is None, "Install the locked forecast-core extra")
class ForecastWeatherContractTests(unittest.TestCase):
    def test_latest_run_is_selected_only_after_publication_availability(self):
        records = [
            ForecastWind(100, 130, 1000, 12, 20, "older-run"),
            ForecastWind(200, 280, 1000, 14, 30, "newer-run"),
            ForecastWind(200, 280, 1200, 15, 40, "newer-run"),
        ]
        self.assertEqual(available_run(records, 120), [])
        self.assertEqual([r.source for r in available_run(records, 250)], ["older-run"])
        selected = available_run(records, 280)
        self.assertEqual([r.valid_at_ms for r in selected], [1000, 1200])
        self.assertTrue(all(r.issued_at_ms == 200 for r in selected))

    def test_reanalysis_and_inverted_time_units_are_rejected(self):
        for kwargs in [dict(product="reanalysis"), dict(available_at_ms=50),
                       dict(valid_at_ms=50), dict(tws_kt=float("nan")), dict(twd_deg=360)]:
            values = dict(issued_at_ms=100, available_at_ms=150, valid_at_ms=1000,
                          tws_kt=12., twd_deg=270., source="IFS-run")
            values.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ForecastWind(**values)

    def test_condition_support_needs_earlier_competitive_dates_and_valid_records(self):
        rows = [{"date": "2026-05-22", "race_id": "one", "wind_knots": 12},
                {"date": "2026-05-23", "race_id": "two", "wind_knots": 13},
                {"date": "2026-05-23", "race_id": "three", "wind_knots": 11}]
        self.assertEqual(condition_support(rows, tws_kt=12, direction_offset_deg=0), (True, None))
        self.assertFalse(condition_support(rows, tws_kt=12, direction_offset_deg=15)[0])
        self.assertFalse(condition_support(rows, tws_kt=20, direction_offset_deg=0)[0])
        for flag in ["practice", "competitive", "valid"]:
            invalid = [dict(r, **{flag: False if flag != "practice" else True}) for r in rows]
            with self.subTest(flag=flag):
                self.assertFalse(condition_support(invalid, tws_kt=12, direction_offset_deg=0)[0])
        self.assertFalse(condition_support(before_day(rows, "2026-05-23"),
                                           tws_kt=12, direction_offset_deg=0)[0])
