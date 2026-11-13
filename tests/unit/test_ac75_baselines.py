"""Unit tests for AC75 empirical and regularized polar baselines (T10)."""
import math
import unittest
import numpy as np

from pipeline.kinematic_ml.baselines import (
    BinnedPolarBaseline,
    RegularizedSplinePolarBaseline,
)


class TestAC75Baselines(unittest.TestCase):
    def test_binned_polar_interpolation(self):
        """Verify binned polar table interpolates smoothly between grid nodes."""
        model = BinnedPolarBaseline(tws_bins=[6.0, 12.0], twa_bins=[45.0, 135.0])
        # Synthetic data:
        # At (6m/s, 45 deg) -> 16 m/s
        # At (12m/s, 45 deg) -> 24 m/s
        rows = [
            {"tws_mps": 6.0, "twa_sin": math.sin(math.radians(45.0)), "twa_cos": math.cos(math.radians(45.0)), "sog_mps": 16.0},
            {"tws_mps": 12.0, "twa_sin": math.sin(math.radians(45.0)), "twa_cos": math.cos(math.radians(45.0)), "sog_mps": 24.0},
        ]
        model.fit(rows)

        # Midpoint at 9 m/s should interpolate to ~20 m/s
        pred_mid = model.predict(tws_mps=9.0, twa_deg=45.0)
        self.assertAlmostEqual(pred_mid, 20.0, delta=1.5)

    def test_regularized_spline_shrinkage(self):
        """Verify regularized spline baseline shrinks sparse team effects towards zero."""
        model = RegularizedSplinePolarBaseline(alpha=10.0)

        # 50 rows for INEOS, 2 rows for ALINGHI with artificially high speed
        rows = []
        for _ in range(50):
            rows.append({"tws_mps": 10.0, "twa_cos": 0.7, "twa_sin": 0.7, "sog_mps": 20.0, "team_id": "ac37:INEOS"})
        for _ in range(2):
            rows.append({"tws_mps": 10.0, "twa_cos": 0.7, "twa_sin": 0.7, "sog_mps": 30.0, "team_id": "ac37:ALINGHI"})

        model.fit(rows)
        pred_ineos, _ = model.predict({"tws_mps": 10.0, "twa_cos": 0.7, "twa_sin": 0.7, "team_id": "ac37:INEOS"})
        pred_alinghi, _ = model.predict({"tws_mps": 10.0, "twa_cos": 0.7, "twa_sin": 0.7, "team_id": "ac37:ALINGHI"})

        # Sparse team with 2 rows should be heavily regularized towards baseline (~20), not jumping to 30
        self.assertLess(pred_alinghi, 23.0)
        self.assertAlmostEqual(pred_ineos, 20.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
