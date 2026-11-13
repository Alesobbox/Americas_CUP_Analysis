"""Unit tests for model selection, candidate-specific SEs, and explicit fallbacks (Gate A Criteria 7-8)."""
from __future__ import annotations

import unittest

from pipeline.kinematic_ml.selection import (
    select_default_model_from_date_crps,
    select_default_model_from_races,
)


class TestAC75ModelSelection(unittest.TestCase):
    def test_candidate_specific_se_produces_registered_result(self):
        """Verify candidate-specific paired SE selects simplest candidate within its own 1-SE limit (Gate A Criterion 8)."""
        # 6 common eligible dates (>= 5)
        dates = [f"2024-08-{d:02d}" for d in (22, 23, 24, 25, 28, 29)]

        # Neural has the lowest mean CRPS across all 6 dates
        neural_crps = {d: 1.10 for d in dates}  # mean = 1.10

        # Case A: Spline has mean 1.14 (paired difference = +0.04)
        # with variable differences across dates such that paired SE = 0.055
        # Diffs: [0.00, 0.08, 0.01, 0.07, 0.02, 0.06] -> mean = 0.04
        # std(ddof=1) ~= 0.0346 -> SE = 0.0346 / sqrt(6) ~= 0.0141? Wait, let's craft exact diffs:
        # If diffs have std = 0.13, SE = 0.13 / sqrt(6) ~= 0.053 > 0.04
        diffs_high_var = [-0.08, 0.16, -0.05, 0.15, -0.02, 0.08]  # mean = 0.04
        spline_crps_high_var = {d: 1.10 + diff for d, diff in zip(dates, diffs_high_var)}

        decision_a = select_default_model_from_date_crps({
            "neural_network_silu": neural_crps,
            "regularized_spline_polar": spline_crps_high_var,
            "empirical_binned_polar": {d: 2.50 for d in dates},
        })

        self.assertFalse(decision_a.is_fallback)
        self.assertEqual(decision_a.eligible_dates_count, 6)
        # In Case A: Spline mean difference (+0.04) <= Spline paired SE (>0.04),
        # Spline is simpler than Neural (spline < neural in hierarchy), so Spline is selected!
        self.assertEqual(decision_a.selected_model_family, "spline")
        self.assertIn("regularized_spline_polar", decision_a.selected_model_id)

        # Case B: Spline has the same mean 1.14 (mean difference = +0.04),
        # but with very low variance so its paired SE is ~0.008 < 0.04
        diffs_low_var = [0.035, 0.045, 0.038, 0.042, 0.039, 0.041]  # mean = 0.040
        spline_crps_low_var = {d: 1.10 + diff for d, diff in zip(dates, diffs_low_var)}

        decision_b = select_default_model_from_date_crps({
            "neural_network_silu": neural_crps,
            "regularized_spline_polar": spline_crps_low_var,
            "empirical_binned_polar": {d: 2.50 for d in dates},
        })

        self.assertFalse(decision_b.is_fallback)
        # In Case B: Spline mean difference (+0.04) > Spline paired SE (~0.008),
        # so Spline is NOT within its own 1-SE limit of Neural. Neural is selected!
        self.assertEqual(decision_b.selected_model_family, "neural")
        self.assertIn("neural_network_silu", decision_b.selected_model_id)

    def test_explicit_fallback_fewer_than_five_dates(self):
        """Verify fewer than 5 eligible dates follows explicit fallback to empirical (Gate A Criterion 8)."""
        # Exactly 4 eligible dates
        dates = [f"2024-08-{d:02d}" for d in (22, 23, 24, 25)]

        decision = select_default_model_from_date_crps({
            "neural_network_silu": {d: 0.50 for d in dates},
            "regularized_spline_polar": {d: 0.60 for d in dates},
            "empirical_binned_polar": {d: 1.50 for d in dates},
        })

        self.assertTrue(decision.is_fallback)
        self.assertEqual(decision.fallback_reason, "insufficient_eligible_dates")
        self.assertEqual(decision.selected_model_family, "empirical")
        self.assertEqual(decision.eligible_dates_count, 4)

    def test_explicit_fallback_zero_qualified_race_targets(self):
        """Verify zero qualified targets follows explicit fallback to empirical (Gate A Criterion 8)."""
        dates = [f"2024-08-{d:02d}" for d in (22, 23, 24, 25, 28, 29)]

        decision = select_default_model_from_date_crps(
            {
                "neural_network_silu": {d: 0.50 for d in dates},
                "regularized_spline_polar": {d: 0.60 for d in dates},
                "empirical_binned_polar": {d: 1.50 for d in dates},
            },
            qualified_targets_count=0,
        )

        self.assertTrue(decision.is_fallback)
        self.assertEqual(decision.fallback_reason, "insufficient_qualified_race_targets")
        self.assertEqual(decision.selected_model_family, "empirical")
        self.assertEqual(decision.qualified_targets_count, 0)

    def test_speed_and_race_margin_rankings_disagree_without_corrupting_selection(self):
        """Verify that speed error rankings and race-margin rankings can disagree without corrupting selection (Gate A Criterion 7)."""
        dates = [f"2024-08-{d:02d}" for d in (22, 23, 24, 25, 28, 29)]

        # Speed ranking: Neural is best, Spline is second, Empirical is worst
        # (e.g. SOG RMSE: Neural 0.40 m/s < Spline 0.90 m/s < Empirical 1.50 m/s)
        speed_scores = {
            "neural_network_silu": {"sog_rmse_mps": 0.40, "sog_mae_mps": 0.30},
            "regularized_spline_polar": {"sog_rmse_mps": 0.90, "sog_mae_mps": 0.70},
            "empirical_binned_polar": {"sog_rmse_mps": 1.50, "sog_mae_mps": 1.20},
        }

        # Race-margin ranking: Spline is decisively best on race margin CRPS!
        # Neural performs worse end-to-end on race margins (e.g. 3.20s vs 2.10s for Spline)
        candidate_race_crps = {
            "regularized_spline_polar": {d: 2.10 for d in dates},
            "neural_network_silu": {d: 3.20 for d in dates},
            "empirical_binned_polar": {d: 4.50 for d in dates},
        }

        decision = select_default_model_from_date_crps(
            candidate_race_crps,
            model_ids={
                "empirical": "empirical_binned_polar",
                "spline": "regularized_spline_polar",
                "neural": "neural_network_silu",
            },
        )

        # Selection MUST be driven by race-margin CRPS, not speed RMSE
        self.assertFalse(decision.is_fallback)
        self.assertEqual(decision.selected_model_family, "spline")
        self.assertEqual(decision.selected_model_id, "regularized_spline_polar")
        # Confirm Neural was NOT selected despite its superior speed RMSE
        self.assertNotEqual(decision.selected_model_family, "neural")

    def test_race_level_aggregation_to_common_qualified_dates(self):
        """Verify that race-level scores aggregate across common qualified race IDs to dates."""
        race_dates = {
            "race_1": "2024-08-22",
            "race_2": "2024-08-22",
            "race_3": "2024-08-23",
            "race_4": "2024-08-24",
            "race_5": "2024-08-25",
            "race_6": "2024-08-28",
            "race_unqualified": "2024-08-29",
        }
        qualified_races = {"race_1", "race_2", "race_3", "race_4", "race_5", "race_6"}

        candidate_races = {
            "regularized_spline_polar": {
                "race_1": 2.0, "race_2": 3.0, "race_3": 2.5, "race_4": 2.2, "race_5": 2.1, "race_6": 2.4,
                "race_unqualified": 99.0,
            },
            "neural_network_silu": {
                "race_1": 2.2, "race_2": 2.8, "race_3": 2.4, "race_4": 2.3, "race_5": 2.2, "race_6": 2.5,
                "race_unqualified": 99.0,
            },
            "empirical_binned_polar": {
                "race_1": 4.0, "race_2": 4.0, "race_3": 4.0, "race_4": 4.0, "race_5": 4.0, "race_6": 4.0,
                "race_unqualified": 99.0,
            },
        }

        decision = select_default_model_from_races(
            candidate_races,
            race_dates,
            qualified_race_ids=qualified_races,
        )

        self.assertFalse(decision.is_fallback)
        self.assertEqual(decision.qualified_targets_count, 6)
        self.assertEqual(decision.eligible_dates_count, 5)
        # On 2024-08-22, spline mean CRPS = (2.0 + 3.0)/2 = 2.5
        self.assertAlmostEqual(decision.candidate_crps_by_date["regularized_spline_polar"]["2024-08-22"], 2.5, places=4)


if __name__ == "__main__":
    unittest.main()
