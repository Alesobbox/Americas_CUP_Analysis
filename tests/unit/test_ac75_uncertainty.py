"""Unit tests for AC75 predictive uncertainty, residuals, and completion scope (T13)."""
import unittest
import numpy as np

from pipeline.kinematic_ml.uncertainty import (
    CompletionModel,
    PairedResidualSampler,
    VarianceLedger,
)


class TestAC75Uncertainty(unittest.TestCase):
    def test_variance_ledger_completeness(self):
        """Verify variance ledger explicitly attributes all variance sources."""
        ledger = VarianceLedger()
        self.assertIn("30-second", ledger.serial_execution_variation)
        self.assertIn("paired-boat", ledger.shared_conditions_variation)
        self.assertIn("SE = s / sqrt(N)", ledger.monte_carlo_numerical_error)

    def test_paired_residual_sampling_correlation(self):
        """Verify that paired residual sampler generates correlated series without double-added noise."""
        sampler = PairedResidualSampler(block_duration_s=30.0)
        rng = np.random.default_rng(2027)

        res_a, res_b = sampler.sample_residuals(duration_s=60.0, step_s=5.0, rng=rng, cross_boat_correlation=0.7)
        self.assertEqual(len(res_a), 12)
        self.assertEqual(len(res_b), 12)

        # Draw longer series to check correlation
        long_a, long_b = sampler.sample_residuals(duration_s=5000.0, step_s=5.0, rng=rng, cross_boat_correlation=0.7)
        corr = float(np.corrcoef(long_a, long_b)[0, 1])
        self.assertGreater(corr, 0.4)
        self.assertLess(corr, 0.9)

    def test_completion_scope_unconditional_null(self):
        """Verify completion-assumed scope leaves unconditional probabilities as None, not zero."""
        model = CompletionModel(probability_scope="completion_assumed_on_water")
        detail = model.get_completion_detail()
        self.assertEqual(detail["probability_scope"], "completion_assumed_on_water")
        self.assertIsNone(detail["unconditional_win_a"])
        self.assertIsNone(detail["unconditional_win_b"])
        self.assertIsNone(detail["unconditional_no_winner"])


if __name__ == "__main__":
    unittest.main()
