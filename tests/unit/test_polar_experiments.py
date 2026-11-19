"""Research contracts for sample targets, train clocks and environmental joins."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from pipeline.research.environment_ablation import KNOT_MPS, current_vectors, join_environment
from pipeline.research.feature_evaluation import compare_features
from pipeline.research.polar_evaluation import evaluate_surfaces, score_predictions
from pipeline.research.polar_experiments import run_polar_experiments
from pipeline.research.polar_surface import ridge_features
from pipeline.research.polar_table import ResearchTable, circular_difference
from pipeline.research.wind_agreement import _adjusted_features, _offset_intervals, peer_wind


def research_table(days: int = 5, per_day: int = 80) -> ResearchTable:
    size = days * per_day
    index = np.arange(size)
    within = index % per_day
    wind = 12 + (within % 4) * 0.5
    angle = 45 + (within % 5)
    return ResearchTable(
        race=np.array([f"r{value // per_day}" for value in index]),
        day=np.array([f"2026-05-{22 + value // per_day:02}" for value in index]),
        boat=np.full(size, "a"),
        team=np.full(size, "A"),
        timestamp=1000.0 * index,
        leg=np.ones(size),
        mode=np.ones(size),
        tack=np.where(within % 2, 1.0, -1.0),
        tws=wind,
        twa=angle,
        sog=10 + wind + 0.1 * angle + np.sin(index),
        heading=np.zeros(size),
        cog=np.full(size, 90.0),
        twd=angle,
        x=index.astype(float) * 100,
        y=np.zeros(size),
    )


class PolarExperimentTests(unittest.TestCase):
    def test_score_preserves_sample_variance(self):
        metrics = score_predictions(np.array([10.0] * 5 + [30.0] * 5), np.full(10, 20.0))
        self.assertEqual(metrics["rmse_kt"], 10.0)
        self.assertEqual(metrics["sample_count"], 10)

    def test_nested_chronological_fits_do_not_consume_future_targets(self):
        table = research_table()
        original = evaluate_surfaces(table, True)
        altered_sog = table.sog.copy()
        altered_sog[table.day == max(table.day)] += 100
        altered = ResearchTable(**{**vars(table), "sog": altered_sog})
        changed = evaluate_surfaces(altered, True)
        self.assertEqual(original["folds"][0], changed["folds"][0])
        for fold in original["folds"]:
            self.assertTrue(all(day < fold["day"] for day in fold["training_dates"]))
            self.assertNotIn(fold["day"], fold["training_dates"])
        self.assertGreater(original["sample_weighted"]["kernel"]["sample_count"], 0)

    def test_peer_consensus_excludes_target_and_handles_north_wrap(self):
        table = research_table(1, 3)
        table = ResearchTable(
            **{
                **vars(table),
                "boat": np.array(["a", "b", "c"]),
                "timestamp": np.zeros(3),
                "tws": np.array([20.0, 10.0, 12.0]),
                "twd": np.array([100.0, 359.0, 1.0]),
            }
        )
        speed, direction, count = peer_wind(table)
        self.assertEqual(speed[0], 11.0)
        self.assertEqual(count[0], 2)
        self.assertAlmostEqual(float(circular_difference(direction[:1], np.array([0.0]))[0]), 0.0)
        self.assertEqual(speed[1], 16.0)

    def test_wind_agreement_offsets_use_training_pairs_only(self):
        table = research_table(2, 80)
        train = table.day == min(table.day)
        reference = (table.tws - 0.5, table.twd - 2)
        expected = _adjusted_features(table, reference, train)
        speed = reference[0].copy()
        direction = reference[1].copy()
        speed[~train] += 200
        direction[~train] += 90
        self.assertTrue(
            np.array_equal(expected, _adjusted_features(table, (speed, direction), train))
        )

    def test_direction_uncertainty_respects_circular_wrap(self):
        summary = _offset_intervals(
            np.array(["d1", "d2", "d3"]),
            np.array([0.5, 0.5, 0.5]),
            np.array([179.0, -179.0, 180.0]),
        )
        self.assertAlmostEqual(abs(summary["circular_mean_daily_direction_difference_deg"]), 180.0)
        self.assertLess(
            summary["direction_interval_95_deg"][1] - summary["direction_interval_95_deg"][0], 5
        )

    def test_current_adjustment_subtracts_both_vector_components(self):
        table = research_table(1, 1)
        table = ResearchTable(**{**vars(table), "sog": np.array([10.0])})
        values = current_vectors(
            table, {"current_u_mps": np.array([0.0]), "current_v_mps": np.array([KNOT_MPS])}
        )
        self.assertAlmostEqual(values["model_adjusted_stw_kt"][0], np.sqrt(101.0))
        self.assertAlmostEqual(values["along_kt"][0], 0.0)
        self.assertAlmostEqual(values["cross_kt"][0], -1.0)

    def test_environment_join_keeps_null_and_rejects_stale_samples(self):
        table = research_table(1, 3)
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            folder = data_dir / "environment" / "boats"
            folder.mkdir(parents=True)
            payload = {
                "boats": {"a": {"time_ms": [0], "current_u_mps": [None], "current_v_mps": [0.2]}}
            }
            (folder / "r0.json").write_text(json.dumps(payload), encoding="utf-8")
            joined = join_environment(table, data_dir)
        self.assertTrue(np.isnan(joined["current_u_mps"]).all())
        self.assertEqual(joined["current_v_mps"][0], 0.2)
        self.assertTrue(np.isnan(joined["current_v_mps"][1:]).all())

    def test_feature_ablation_uses_same_complete_cohort(self):
        table = research_table()
        baseline = ridge_features(table)
        environmental = np.ones(table.size)
        environmental[::2] = np.nan
        report = compare_features(
            table,
            {
                "baseline": baseline,
                "extended": np.column_stack([baseline, environmental]),
            },
        )
        self.assertEqual(report["cohort"]["sample_count"], table.size // 2)
        for fold in report["folds"]:
            self.assertEqual(
                fold["models"]["baseline"]["sample_count"],
                fold["models"]["extended"]["sample_count"],
            )

    def test_missing_sample_table_is_explicitly_unavailable(self):
        report = run_polar_experiments({}, Path("public/data"))
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["cohort"]["sample_count"], 0)


if __name__ == "__main__":
    unittest.main()
