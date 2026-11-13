"""Candidate motion model adapters and interfaces (T15/P3).

Standardizes fit, predict_distribution, and complexity ordering for:
- Empirical Polar Baseline (complexity order 1)
- Regularized Spline Polar Baseline (complexity order 2)
- Small Neural Network 2x32 SiLU (complexity order 3)
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from pipeline.kinematic_ml.baselines import (
    BinnedPolarBaseline,
    RegularizedSplinePolarBaseline,
    _compute_race_weights,
)
from pipeline.kinematic_ml.neural import (
    encode_features,
    numpy_forward_pass,
    train_ac75_neural_model,
)


class BaseCandidateModel:
    """Base interface for AC75 kinematic motion candidates."""
    family_name: str = "base"
    complexity_order: int = 99

    def fit(self, train_rows: Sequence[Mapping[str, Any]]) -> None:
        raise NotImplementedError

    def fit_with_validation(
        self,
        train_rows: Sequence[Mapping[str, Any]],
        val_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        self.fit(train_rows)

    def predict_distribution(self, features: Mapping[str, Any]) -> tuple[float, float]:
        """Returns (mu_log_sog, log_sigma_log_sog)."""
        raise NotImplementedError


class EmpiricalPolarCandidate(BaseCandidateModel):
    """Empirical binned polar baseline (complexity order 1)."""
    family_name: str = "empirical"
    complexity_order: int = 1

    def __init__(self) -> None:
        self.model = BinnedPolarBaseline()

    def fit(self, train_rows: Sequence[Mapping[str, Any]]) -> None:
        self.model.fit(train_rows)

    def predict_distribution(self, features: Mapping[str, Any]) -> tuple[float, float]:
        return self.model.predict_distribution(features)


class SplinePolarCandidate(BaseCandidateModel):
    """Regularized tensor-spline polar baseline (complexity order 2)."""
    family_name: str = "spline"
    complexity_order: int = 2

    def __init__(self, alpha: float = 1.0) -> None:
        self.model = RegularizedSplinePolarBaseline(alpha=alpha)

    def fit(self, train_rows: Sequence[Mapping[str, Any]]) -> None:
        self.model.fit(train_rows)

    def fit_with_validation(
        self,
        train_rows: Sequence[Mapping[str, Any]],
        val_rows: Sequence[Mapping[str, Any]],
    ) -> None:
        self.model.fit_with_validation(train_rows, val_rows)

    def predict_distribution(self, features: Mapping[str, Any]) -> tuple[float, float]:
        return self.model.predict_distribution(features)


class NeuralPolarCandidate(BaseCandidateModel):
    """Small neural network 2x32 SiLU baseline (complexity order 3)."""
    family_name: str = "neural"
    complexity_order: int = 3

    def __init__(self, seed: int = 2027) -> None:
        self.seed = seed
        self.weights: dict[str, np.ndarray] = {}
        self.scaler_mean: np.ndarray | None = None
        self.scaler_scale: np.ndarray | None = None

    def fit_with_validation(
        self,
        train_rows: Sequence[Mapping[str, Any]],
        val_rows: Sequence[Mapping[str, Any]],
        *,
        lr: float = 0.001,
        batch_size: int = 512,
        max_epochs: int = 60,
        patience: int = 10,
    ) -> None:
        X_tr, mean_tr, scale_tr = encode_features(train_rows)
        y_tr = np.array([float(r.get("sog_mps", 0.0)) for r in train_rows], dtype=np.float32)
        w_tr = _compute_race_weights(train_rows).astype(np.float32)

        self.scaler_mean = mean_tr
        self.scaler_scale = scale_tr

        X_v, _, _ = encode_features(val_rows, scaler_mean=mean_tr, scaler_scale=scale_tr)
        y_v = np.array([float(r.get("sog_mps", 0.0)) for r in val_rows], dtype=np.float32)

        weights, _hist = train_ac75_neural_model(
            X_tr,
            y_tr,
            X_v,
            y_v,
            sample_weights=w_tr,
            lr=lr,
            batch_size=batch_size,
            max_epochs=max_epochs,
            patience=patience,
            seed=self.seed,
        )
        self.weights = weights

    def fit(self, train_rows: Sequence[Mapping[str, Any]]) -> None:
        n_tr = max(1, int(len(train_rows) * 0.8))
        tr = train_rows[:n_tr]
        val = train_rows[n_tr:] if n_tr < len(train_rows) else train_rows
        self.fit_with_validation(tr, val)

    def predict_distribution(self, features: Mapping[str, Any]) -> tuple[float, float]:
        if not self.weights or self.scaler_mean is None or self.scaler_scale is None:
            raise RuntimeError("Neural model is not fitted")
        X, _, _ = encode_features([features], scaler_mean=self.scaler_mean, scaler_scale=self.scaler_scale)
        mu, log_scale = numpy_forward_pass(X, self.weights)
        return float(mu[0]), float(log_scale[0])
