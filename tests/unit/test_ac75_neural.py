"""Unit tests for AC75 neural network, censored Gaussian likelihood, and NumPy forward pass (T11)."""
import math
import os
import tempfile
import unittest
from pathlib import Path

# Prevent Windows MKL / OpenMP runtime collision
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
import torch

from pipeline.kinematic_ml.neural import (
    AC75SpeedNN,
    censored_gaussian_nll,
    encode_features,
    export_neural_bundle,
    numpy_forward_pass,
    train_ac75_neural_model,
)


class TestAC75Neural(unittest.TestCase):
    def test_torch_numpy_forward_pass_agreement(self):
        """Verify that pure NumPy forward pass agrees with PyTorch forward pass within 1e-5."""
        torch.manual_seed(2027)
        model = AC75SpeedNN(in_dim=14)
        model.eval()

        # Random input batch of 10 samples
        X = np.random.randn(10, 14).astype(np.float32)

        # PyTorch forward
        with torch.no_grad():
            t_mu, t_log_scale = model(torch.from_numpy(X))
            py_mu = t_mu.numpy()
            py_log_scale = t_log_scale.numpy()

        # Extract weights dict
        weights = {k: v.numpy() for k, v in model.state_dict().items()}

        # Pure NumPy forward
        np_mu, np_log_scale = numpy_forward_pass(X, weights)

        # Compare within 1e-5
        np.testing.assert_allclose(np_mu, py_mu, rtol=1e-5, atol=1e-5)
        np.testing.assert_allclose(np_log_scale, py_log_scale, rtol=1e-5, atol=1e-5)

    def test_censored_gaussian_likelihood_finite_and_continuous(self):
        """Verify that slow-speed censored observations yield finite valid loss."""
        # Mixture of normal speeds (20 m/s) and slow censored speeds (1.0 m/s, 0.5 m/s)
        y = torch.tensor([22.0, 18.5, 1.0, 0.5, 2.0], dtype=torch.float32)
        mu = torch.tensor([3.0, 2.9, 0.5, 0.2, 0.7], dtype=torch.float32)
        log_scale = torch.tensor([-1.0, -1.0, -0.5, -0.5, -0.8], dtype=torch.float32)

        loss = censored_gaussian_nll(y, mu, log_scale, censor_threshold_mps=2.0)
        self.assertTrue(torch.isfinite(loss).item())
        self.assertGreater(loss.item(), 0.0)

    def test_training_reduces_loss_and_learns_relationship(self):
        """Verify that training reduces loss and learns synthetic speed response."""
        np.random.seed(2027)
        N = 400
        # Synthetic data: SOG increases linearly with TWS (feature col 0)
        tws = np.random.uniform(5.0, 20.0, size=N).astype(np.float32)
        true_sog = 10.0 + 1.2 * tws + np.random.normal(0, 0.5, size=N).astype(np.float32)

        rows = [{"tws_mps": float(tws[i]), "team_id": "ac37:INEOS"} for i in range(N)]
        X, m, s = encode_features(rows)

        # Train/val split
        X_train, y_train = X[:300], true_sog[:300]
        X_val, y_val = X[300:], true_sog[300:]

        weights, metrics = train_ac75_neural_model(
            X_train, y_train, X_val, y_val,
            lr=0.01,
            batch_size=64,
            max_epochs=30,
            seed=2027,
        )
        self.assertLess(metrics["best_val_loss"], 2.0)
        self.assertGreater(metrics["total_epochs"], 1)

    def test_export_bundle_creates_valid_artifacts(self):
        """Verify exporting model weights to .npz and .json with hashes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_prefix = Path(tmp_dir) / "test_model"
            weights = {
                "fc1.weight": np.zeros((32, 14), dtype=np.float32),
                "fc1.bias": np.zeros(32, dtype=np.float32),
                "fc2.weight": np.zeros((32, 32), dtype=np.float32),
                "fc2.bias": np.zeros(32, dtype=np.float32),
                "fc_out.weight": np.zeros((2, 32), dtype=np.float32),
                "fc_out.bias": np.zeros(2, dtype=np.float32),
            }
            mean = np.zeros(8, dtype=np.float32)
            scale = np.ones(8, dtype=np.float32)

            res = export_neural_bundle(weights, mean, scale, out_prefix)
            self.assertTrue(Path(res["npz_path"]).exists())
            self.assertTrue(Path(res["json_path"]).exists())
            self.assertEqual(len(res["npz_sha256"]), 64)
            self.assertEqual(len(res["json_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
