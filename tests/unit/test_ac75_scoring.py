"""Unit tests for empirical CRPS, non-Gaussian scoring, and trial encapsulation (Gate A Criterion 6)."""
from __future__ import annotations

import math
import unittest

import numpy as np

from pipeline.kinematic_ml.scoring import (
    ComprehensiveEvaluationReport,
    MotionMetrics,
    RaceMetrics,
    SimulationTrialResult,
    SupportDenominators,
    brier_score,
    censored_log_speed_nll,
    compute_motion_metrics,
    compute_race_metrics,
    empirical_crps,
    log_loss,
    normal_crps,
    pairwise_empirical_crps,
)


class TestAC75Scoring(unittest.TestCase):
    def test_empirical_crps_matches_direct_pairwise_exact(self):
        """Verify empirical CRPS matches direct O(M^2) pairwise calculation across sample sizes and distributions."""
        rng = np.random.default_rng(2027)

        # 1. Gaussian sample
        for n_samples in (5, 20, 100, 500):
            trials = rng.normal(loc=12.5, scale=4.0, size=n_samples)
            y = 14.2
            fast_crps = empirical_crps(trials, y)
            slow_crps = pairwise_empirical_crps(trials, y)
            self.assertAlmostEqual(fast_crps, slow_crps, places=9)

        # 2. Skewed / uniform sample
        trials_unif = rng.uniform(low=-30.0, high=50.0, size=150)
        y_unif = 10.0
        self.assertAlmostEqual(
            empirical_crps(trials_unif, y_unif),
            pairwise_empirical_crps(trials_unif, y_unif),
            places=9,
        )

        # 3. Heavy-tailed Student-t (df=3)
        trials_t = rng.standard_t(df=3.0, size=200) * 8.0 + 5.0
        y_t = -2.5
        self.assertAlmostEqual(
            empirical_crps(trials_t, y_t),
            pairwise_empirical_crps(trials_t, y_t),
            places=9,
        )

    def test_non_gaussian_samples_score_correctly(self):
        """Verify exact non-Gaussian scoring where Gaussian approximation fails (Gate A Criterion 6)."""
        # Discrete symmetric bimodal distribution: 50% at -10, 50% at +10
        # Target y = 0
        # E|X - y| = 0.5 * 10 + 0.5 * 10 = 10.0
        # E|X - X'|:
        #   Pr(X=-10, X'=-10) = 0.25 -> diff = 0
        #   Pr(X=-10, X'=+10) = 0.25 -> diff = 20
        #   Pr(X=+10, X'=-10) = 0.25 -> diff = 20
        #   Pr(X=+10, X'=+10) = 0.25 -> diff = 0
        #   E|X - X'| = 0.25 * 0 + 0.25 * 20 + 0.25 * 20 + 0.25 * 0 = 10.0
        # Exact non-Gaussian CRPS = 10.0 - 0.5 * 10.0 = 5.0
        bimodal_trials = np.array([-10.0] * 500 + [10.0] * 500, dtype=float)
        y = 0.0

        emp_score = empirical_crps(bimodal_trials, y)
        pairwise_score = pairwise_empirical_crps(bimodal_trials, y)

        self.assertAlmostEqual(emp_score, 5.0, places=5)
        self.assertAlmostEqual(pairwise_score, 5.0, places=5)

        # Under Gaussian approximation with matching mean (0.0) and std (10.0):
        # normal_crps(0, 0, 10) = 10 * (sqrt(2) - 1) / sqrt(pi) ~= 2.33695
        gauss_approx_score = normal_crps(0.0, 0.0, 10.0)
        expected_gauss = 10.0 * (math.sqrt(2.0) - 1.0) / math.sqrt(math.pi)
        self.assertAlmostEqual(gauss_approx_score, expected_gauss, places=4)

        # Crucial check: Gaussian approximation distorts score by > 2.5s on non-Gaussian data (5.0 vs 2.34)
        self.assertGreater(abs(gauss_approx_score - emp_score), 2.5)

    def test_analytical_gaussian_crps_fixture(self):
        """Verify normal_crps matches the known analytical Gaussian fixture."""
        # For y = mu = 0, sigma = 1:
        # Analytical CRPS = (sqrt(2) - 1) / sqrt(pi) ~= 0.2336946
        expected = (math.sqrt(2.0) - 1.0) / math.sqrt(math.pi)
        computed = normal_crps(0.0, 0.0, 1.0)
        self.assertAlmostEqual(computed, expected, places=5)

        # Zero error, zero variance -> CRPS = 0
        self.assertEqual(normal_crps(5.0, 5.0, 0.0), 0.0)

    def test_simulation_trial_result_keeps_raw_arrays_out_of_summaries(self):
        """Verify internal simulation trial results are exposed for evaluation but kept out of public payloads."""
        rng = np.random.default_rng(42)
        n_trials = 2000
        deltas = rng.normal(loc=15.2, scale=8.4, size=n_trials)
        times_a = rng.normal(loc=1200.0, scale=12.0, size=n_trials)
        times_b = times_a + deltas
        wins_a = (deltas > 0).astype(float)
        both_finished = np.ones(n_trials, dtype=bool)

        trial_result = SimulationTrialResult(
            scenario_id="scen_test_123",
            model_id="ac75_candidate_test",
            team_a="ac37:ETNZ",
            team_b="ac37:INEOS",
            trial_count=n_trials,
            deltas=deltas,
            times_a=times_a,
            times_b=times_b,
            wins_a=wins_a,
            both_finished=both_finished,
        )

        # 1. Evaluator can compute empirical CRPS directly from unrounded trials
        obs_margin = 14.5
        emp_crps = trial_result.score_empirical_margin_crps(obs_margin)
        self.assertAlmostEqual(emp_crps, empirical_crps(deltas, obs_margin), places=6)

        # 2. compute_summary_statistics() does not contain raw arrays
        summary = trial_result.compute_summary_statistics()
        for key, val in summary.items():
            self.assertNotIsInstance(val, np.ndarray, f"Key '{key}' leaked raw numpy array into summary")

        # 3. to_scenario_v2_result() does not contain raw arrays in to_dict()
        applied_inputs = {"team_a": "ac37:ETNZ", "team_b": "ac37:INEOS", "tws_mps": 9.5}
        scen_result = trial_result.to_scenario_v2_result(applied_inputs)
        scen_dict = scen_result.to_dict()

        self.assertNotIn("deltas", scen_dict)
        self.assertNotIn("times_a", scen_dict)
        self.assertNotIn("times_b", scen_dict)
        self.assertEqual(scen_dict["status"], "available")
        self.assertIn("central_80_margin_interval_s", scen_dict["timing"])

    def test_decoupled_metrics_reporting(self):
        """Verify decoupled motion, event, and race outcome metric reporting."""
        # Motion metrics
        y_sog = np.array([20.0, 22.0, 18.0, 25.0])
        mu_log = np.log(np.array([19.5, 21.0, 18.5, 24.0]))
        sig_log = np.array([0.1, 0.1, 0.1, 0.1])
        motion_res = compute_motion_metrics(y_sog, mu_log, sig_log)

        self.assertGreater(motion_res.sog_mae_mps, 0.0)
        self.assertGreater(motion_res.sog_rmse_mps, 0.0)
        self.assertTrue(math.isfinite(motion_res.log_speed_nll))
        self.assertEqual(motion_res.sample_count, 4)

        # Race metrics
        eval_cases = [
            {
                "observed_winner": "ac37:ETNZ",
                "team_a": "ac37:ETNZ",
                "pred_win_a": 0.85,
                "observed_margin_s": 22.0,
                "pred_trial_deltas": np.random.normal(20.0, 5.0, size=500),
                "pred_mean_margin_s": 20.0,
                "quantiles_delta_t_s": {"p10": 13.5, "p25": 16.5, "p75": 23.5, "p90": 26.5, "p025": 10.0, "p975": 30.0},
            },
            {
                "observed_winner": "ac37:INEOS",
                "team_a": "ac37:ETNZ",
                "pred_win_a": 0.30,
                "observed_margin_s": -15.0,
                "pred_trial_deltas": np.random.normal(-12.0, 4.0, size=500),
                "pred_mean_margin_s": -12.0,
                "quantiles_delta_t_s": {"p10": -17.0, "p25": -14.5, "p75": -9.5, "p90": -7.0, "p025": -20.0, "p975": -4.0},
            },
        ]
        race_res = compute_race_metrics(eval_cases)
        self.assertGreater(race_res.race_margin_crps_s, 0.0)
        self.assertGreater(race_res.winner_brier, 0.0)
        self.assertEqual(race_res.race_count, 2)
        self.assertEqual(race_res.coverage_80, 1.0)  # Both targets fell inside p10..p90

        # Full report conversion to EvaluationReceipt
        report = ComprehensiveEvaluationReport(
            model_id="candidate_test_model",
            candidate_family="spline",
            motion_metrics=motion_res,
            race_metrics=race_res,
            support_denominators=SupportDenominators(
                total_dates=5,
                eligible_dates=5,
                total_races=2,
                qualified_races=2,
                evaluated_races=2,
                abstained_races=0,
            ),
        )
        receipt = report.to_evaluation_receipt("rec_test_1", "split_ref_1")
        self.assertEqual(receipt.status, "complete")
        self.assertEqual(receipt.metrics["race_margin_crps_s"], race_res.race_margin_crps_s)
        self.assertEqual(receipt.support_counts["qualified_races"], 2)


if __name__ == "__main__":
    unittest.main()
