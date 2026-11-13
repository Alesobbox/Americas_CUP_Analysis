"""Unit tests for chronological inner splits and predictor-specific calibration artifacts (T15/P3)."""
from __future__ import annotations

import math
import unittest

import numpy as np

from pipeline.kinematic_ml.calibration import (
    ChronologicalInnerSplit,
    PredictorCalibrationArtifacts,
    build_predictor_calibration,
    calibrate_margin_interval_scale,
    calibrate_motion_residual_scale,
)


class TestAC75Calibration(unittest.TestCase):
    def test_chronological_inner_split_five_dates(self):
        """Verify strict chronological assignment across fit, tune, refit, calibrate, and outer-test."""
        train_dates = ["2024-08-22", "2024-08-23", "2024-08-24", "2024-08-25", "2024-08-28"]
        test_dates = ["2024-08-29"]

        split = ChronologicalInnerSplit.from_outer_dates(train_dates, test_dates)
        split.validate_isolation()

        # 1. Fit on earlier dates (first 3)
        self.assertEqual(split.fit_dates, ("2024-08-22", "2024-08-23", "2024-08-24"))
        # 2. Tune on penultimate available date
        self.assertEqual(split.tune_dates, ("2024-08-25",))
        # 3. Refit on fit + tune (first 4)
        self.assertEqual(split.refit_dates, ("2024-08-22", "2024-08-23", "2024-08-24", "2024-08-25"))
        # 4. Calibrate on last training date
        self.assertEqual(split.calibrate_dates, ("2024-08-28",))
        # 5. Subsequent outer-test date is strictly isolated
        self.assertEqual(split.outer_test_dates, ("2024-08-29",))
        self.assertNotIn("2024-08-29", split.outer_train_dates)

    def test_chronological_inner_split_three_dates(self):
        """Verify 3-date split: 1 fit, 1 tune, 1 calibrate."""
        train_dates = ["2024-08-22", "2024-08-23", "2024-08-24"]
        test_dates = ["2024-08-25"]

        split = ChronologicalInnerSplit.from_outer_dates(train_dates, test_dates)
        split.validate_isolation()

        self.assertEqual(split.fit_dates, ("2024-08-22",))
        self.assertEqual(split.tune_dates, ("2024-08-23",))
        self.assertEqual(split.refit_dates, ("2024-08-22", "2024-08-23"))
        self.assertEqual(split.calibrate_dates, ("2024-08-24",))

    def test_chronological_inner_split_two_dates(self):
        """Verify 2-date split: fit on first, calibrate on second."""
        train_dates = ["2024-08-22", "2024-08-23"]
        split = ChronologicalInnerSplit.from_outer_dates(train_dates)
        self.assertEqual(split.fit_dates, ("2024-08-22",))
        self.assertEqual(split.calibrate_dates, ("2024-08-23",))

    def test_test_date_leakage_raises_error(self):
        """Verify that any test date appearing in training dates raises ValueError."""
        train_dates = ["2024-08-22", "2024-08-23", "2024-08-24"]
        test_dates = ["2024-08-23"]  # Leaked into train!
        split = ChronologicalInnerSplit.from_outer_dates(train_dates, test_dates)
        with self.assertRaises(ValueError):
            split.validate_isolation()

    def test_calibrate_motion_residual_scale(self):
        """Verify empirical motion residual scaling computation."""
        # Predictions under-predict the true residual standard deviation
        y_sog = np.array([12.0, 28.0, 15.0, 26.0, 10.0, 30.0])
        mu_log = np.array([np.log(20.0)] * len(y_sog))
        sigma_log = np.array([0.05] * len(y_sog))  # very narrow std

        scale = calibrate_motion_residual_scale(y_sog, mu_log, sigma_log)
        self.assertGreater(scale, 1.0)
        self.assertLessEqual(scale, 2.0)

    def test_calibrate_margin_interval_scale(self):
        """Verify margin interval scaling tunes gamma to match target coverage on calibration set."""
        # 4 calibration races with observed margins
        obs_margins = np.array([10.0, -15.0, 25.0, -5.0])
        rng = np.random.default_rng(42)

        # Trials with true std = 20, but central interval might be slightly miscalibrated
        trial_lists = [
            rng.normal(loc=m, scale=5.0, size=500)
            for m in obs_margins
        ]

        gamma = calibrate_margin_interval_scale(
            trial_lists,
            obs_margins,
            target_nominal_coverage=0.80,
        )
        self.assertGreaterEqual(gamma, 0.5)
        self.assertLessEqual(gamma, 2.5)

    def test_build_predictor_calibration_pipeline(self):
        """Verify end-to-end predictor calibration artifact construction on calibration date."""
        train_dates = ["2024-08-22", "2024-08-23", "2024-08-24", "2024-08-25", "2024-08-28"]
        test_dates = ["2024-08-29"]
        inner_split = ChronologicalInnerSplit.from_outer_dates(train_dates, test_dates)

        calib_windows = [
            {"date_str": "2024-08-28", "sog_mps": 22.5, "tws_mps": 11.0},
            {"date_str": "2024-08-28", "sog_mps": 24.0, "tws_mps": 12.0},
            {"date_str": "2024-08-28", "sog_mps": 20.0, "tws_mps": 10.0},
            {"date_str": "2024-08-28", "sog_mps": 21.5, "tws_mps": 10.5},
            {"date_str": "2024-08-28", "sog_mps": 23.0, "tws_mps": 11.5},
            {"date_str": "2024-08-28", "sog_mps": 25.0, "tws_mps": 12.5},
        ]

        def dummy_predict_dist(row):
            tws = float(row.get("tws_mps", 10.0))
            return math.log(2.0 * tws), math.log(0.1)

        artifacts = build_predictor_calibration(
            predictor_family="spline",
            model_id="regularized_spline_polar",
            inner_split=inner_split,
            calibration_telemetry_windows=calib_windows,
            predict_dist_fn=dummy_predict_dist,
        )

        self.assertEqual(artifacts.predictor_family, "spline")
        self.assertEqual(artifacts.calibration_date, "2024-08-28")
        self.assertTrue(artifacts.verified_no_test_leakage)
        self.assertGreater(artifacts.calibration_sample_count, 0)
        self.assertGreater(artifacts.motion_residual_scale, 0.0)


if __name__ == "__main__":
    unittest.main()
