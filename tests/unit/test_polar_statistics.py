"""Independent checks of sample targets, block refits and evaluation clocks."""

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np

from pipeline.polar.bootstrap import refit, refitted_intervals, summarize
from pipeline.polar.dataset import assemble_dataset
from pipeline.polar.extraction import _cells, extract_race_polar_cells
from pipeline.polar.fitting import _estimate_tack_fixed_effect, _fit_and_predict_subset
from pipeline.polar.inputs import _coverage_valid
from pipeline.polar.residuals import peer_contrasts
from pipeline.polar.validation import grouped_predictions, metrics


def accepted_samples(speeds, *, leg=1, tack="PORT", start=0):
    return [
        {
            "timestamp_ms": start + index * 1000,
            "leg": leg,
            "mode": "upwind",
            "tack": tack,
            "tws_kt": 12.0,
            "abs_twa_deg": 45.0,
            "sog_kt": float(speed),
            "wind_vmg_kt": float(speed) / np.sqrt(2),
        }
        for index, speed in enumerate(speeds)
    ]


def dataset_from_races(specifications):
    details = {}
    for race, day, boats in specifications:
        details[race] = {
            "race": {"id": race, "date": day},
            "boats": [
                {
                    "id": team,
                    "team_code": team,
                    "classification": "RANK_1",
                    "start": {"crossing_time_ms": 0},
                    "polar_samples": samples,
                }
                for team, samples in boats.items()
            ],
        }
    return assemble_dataset(details)


def three_days():
    races = []
    for index, offset in enumerate((0.0, 2.0, 4.0)):
        boats = {}
        for team in ("A", "B"):
            samples = accepted_samples([18 + offset] * 20)
            samples += accepted_samples([19 + offset] * 20, tack="STARBOARD", start=20_000)
            boats[team] = samples
        races.append((f"race{index}", f"2026-09-{22 + index}", boats))
    return dataset_from_races(races)


class IdentityBlockDraws:
    def integers(self, lower, upper, size):
        return np.arange(upper)


class PolarStatisticsTests(unittest.TestCase):
    def test_raw_distribution_and_sse_survive_cell_aggregation(self):
        samples = accepted_samples([10.0, 30.0] * 20)
        ds = dataset_from_races([("race", "2026-09-22", {"A": samples, "B": samples})])
        mask = np.ones(len(ds.sog), dtype=bool)
        fitted = _fit_and_predict_subset(ds, mask, mask)
        self.assertEqual(len(ds.sog), 80)
        self.assertTrue(np.allclose(fitted["eval_sog"], 20.0))
        self.assertTrue(np.all((fitted["eval_p90"] >= 30) & (fitted["eval_p90"] <= 30.25)))
        predictions = {name: fitted["eval_" + name] for name in ("sog", "vmg", "p50", "p90")}
        result = metrics(ds, predictions, "controlled", 1)
        self.assertAlmostEqual(result["sog_rmse_kt"], 10.0)
        self.assertAlmostEqual(result["p90_empirical_coverage"], 1.0)
        cell = _cells(samples)[0]
        self.assertAlmostEqual(cell["sog_sum_squares_kt2"], 20 * (100 + 900))

    def test_bootstrap_refit_matches_reported_tack_when_one_side_is_absent(self):
        samples = accepted_samples([20.0] * 30)
        ds = dataset_from_races([("race", "2026-09-22", {"A": samples, "B": samples})])
        mask = np.ones(len(ds.sog), dtype=bool)
        summary = summarize(ds, ds.date)
        means, effects = refit(ds, summary, np.ones(len(summary.names)))
        expected = _fit_and_predict_subset(ds, mask, mask)
        self.assertEqual(_estimate_tack_fixed_effect(ds, mask)[1][0], 0.0)
        self.assertAlmostEqual(effects[1], 0.0)
        np.testing.assert_allclose(means, expected["grid_mean_sog"])

    def test_bootstrap_support_matches_main_fitter_for_single_training_leg(self):
        ds = dataset_from_races([("race", "2026-09-22", {"A": accepted_samples([20.0] * 30)})])
        mask = np.ones(len(ds.sog), dtype=bool)
        fitted = _fit_and_predict_subset(ds, mask, mask)
        self.assertFalse(np.any(fitted["eval_supported"]))
        summary = summarize(ds, ds.date)
        means, _ = refit(ds, summary, np.ones(len(summary.names)))
        self.assertTrue(np.all(np.isnan(means)))

    def test_identity_block_refits_reproduce_point_estimator(self):
        ds = three_days()
        predictions = grouped_predictions(ds, ds.date)["sog"]
        with patch(
            "pipeline.polar.bootstrap.np.random.default_rng", return_value=IdentityBlockDraws()
        ):
            intervals, _ = refitted_intervals(ds, predictions, ds.date, draws=3)
        for team, result in intervals.items():
            expected = float((ds.sog - predictions)[ds.team_code == team].mean())
            self.assertAlmostEqual(result["value"], round(expected, 3))
            self.assertAlmostEqual(result["ci_low_kt"], result["value"])
            self.assertAlmostEqual(result["ci_high_kt"], result["value"])

    def test_summary_preserves_every_leg_and_boat_in_day_blocks(self):
        ds = three_days()
        summary = summarize(ds, ds.date)
        self.assertEqual(len(summary.names), 3)
        for index, day in enumerate(summary.names):
            self.assertEqual(summary.mass[index].sum(), (ds.date == day).sum())
        self.assertAlmostEqual(summary.sums.sum(), ds.sog.sum())

    def test_peer_contrasts_use_equal_peers_and_ignore_unpaired_legs(self):
        boats = {
            "A": accepted_samples([20.0]),
            "B": accepted_samples([12.0] * 100),
            "C": accepted_samples([14.0] * 2),
        }
        boats["A"] += accepted_samples([50.0] * 30, leg=3)
        ds = dataset_from_races([("race", "2026-09-22", boats)])
        predictions = np.full(len(ds.sog), 10.0)
        result = peer_contrasts(ds, predictions)
        for team, expected in (("A", 7.0), ("B", -5.0), ("C", -2.0)):
            self.assertEqual(len(result[team]), 1)
            self.assertAlmostEqual(result[team][0][1], expected)
        predictions[ds.team_code == "C"] = np.nan
        revised = peer_contrasts(ds, predictions)
        self.assertAlmostEqual(revised["A"][0][1], 8.0)
        self.assertNotIn("C", revised)

    def test_earlier_day_predictions_do_not_use_current_or_future_targets(self):
        ds = three_days()
        original = grouped_predictions(ds, ds.date, chronological=True)["sog"]
        final_day = ds.date == "2026-09-24"
        changed = replace(ds, sog=np.where(final_day, ds.sog + 15, ds.sog))
        updated = grouped_predictions(changed, changed.date, chronological=True)["sog"]
        self.assertTrue(np.all(np.isnan(original[~final_day])))
        self.assertTrue(np.all(np.isfinite(original[final_day])))
        np.testing.assert_allclose(original[final_day], updated[final_day])

    def test_missing_source_field_and_internal_gaps_are_rejected(self):
        coverage = {
            field: {"first_ms": 0, "last_ms": 100_000, "gaps": []}
            for field in ("gnss", "heading", "sog", "cog", "twd", "tws")
        }
        self.assertTrue(_coverage_valid(coverage, 50_000))
        missing = deepcopy(coverage)
        del missing["tws"]
        self.assertFalse(_coverage_valid(missing, 50_000))
        coverage["sog"]["gaps"] = [(49_000, 51_000)]
        self.assertFalse(_coverage_valid(coverage, 50_000))
        self.assertFalse(_coverage_valid({}, 50_000))

    def test_extraction_does_not_synthesize_uncovered_samples(self):
        times = list(range(0, 120_000, 1000))
        detail = {
            "race": {"id": "race"},
            "boats": [
                {
                    "id": "A",
                    "team_code": "A",
                    "classification": "RANK_1",
                    "start": {"crossing_time_ms": 0},
                    "legs": [{"leg": 1, "complete": True, "start_ms": 0, "end_ms": 119_000}],
                }
            ],
        }
        telemetry = {
            "timestamps": times,
            "boats": {
                "A": {
                    key: [value] * len(times)
                    for key, value in {
                        "x": 0.0,
                        "y": 0.0,
                        "heading": 315.0,
                        "cog": 315.0,
                        "twd": 0.0,
                        "tws": 12.0,
                        "sog": 20.0,
                    }.items()
                }
            },
        }
        extract_race_polar_cells(detail, replay_doc={"telemetry": telemetry})
        self.assertEqual(detail["boats"][0]["polar_samples"], [])


if __name__ == "__main__":
    unittest.main()
