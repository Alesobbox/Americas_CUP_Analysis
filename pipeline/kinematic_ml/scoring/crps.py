"""Continuous Ranked Probability Score (CRPS) and probabilistic scoring metrics (T15/P3).

Implements:
1. Vectorized unrounded empirical CRPS without Gaussian approximation:
   CRPS(X, y) = E|X - y| - 0.5 * E|X - X'|
   computed in O(M log M) for M simulation trials.
2. Direct O(M^2) pairwise calculation as an exact mathematical assertion reference.
3. Analytical Gaussian CRPS (normal_crps) for benchmark comparisons.
4. Binary probability metrics: Brier score and LogLoss.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def empirical_crps(trials: Sequence[float] | np.ndarray, y: float) -> float:
    """Compute exact empirical CRPS from unrounded simulation trials.
    
    CRPS(F_M, y) = 1/M * sum(|x_i - y|) - 1/(2 * M^2) * sum_i sum_j (|x_i - x_j|)
                 = 1/M * sum(|x_i - y|) - 1/M^2 * sum_{i=0}^{M-1} (2i + 1 - M) * x_{(i)}
    where x_{(0)} <= x_{(1)} <= ... <= x_{(M-1)} are the sorted trial values.
    
    This avoids Gaussian approximation and scores arbitrary non-Gaussian
    (bimodal, skewed, Student-t, discrete) distributions correctly.
    """
    arr = np.asarray(trials, dtype=np.float64)
    m = len(arr)
    if m == 0:
        raise ValueError("Cannot compute empirical CRPS on empty trials")
    if not math.isfinite(y):
        raise ValueError(f"Target y must be finite, got {y}")

    # First term: E|X - y|
    mean_abs_error = float(np.mean(np.abs(arr - y)))

    # Second term: 0.5 * E|X - X'| using sorted values in O(M log M)
    sorted_arr = np.sort(arr)
    # Weights for i in 0..M-1: 2*i + 1 - M
    # e.g., for M=2: i=0 -> -1, i=1 -> +1
    i_indices = np.arange(m, dtype=np.float64)
    weights = 2.0 * i_indices + 1.0 - float(m)
    pairwise_half_diff = float(np.sum(weights * sorted_arr) / (m * m))

    score = mean_abs_error - pairwise_half_diff
    return float(max(0.0, score))


def pairwise_empirical_crps(trials: Sequence[float] | np.ndarray, y: float) -> float:
    """Compute empirical CRPS via direct O(M^2) all-pairs calculation.
    
    Used as an exact mathematical ground-truth reference for verification.
    """
    arr = np.asarray(trials, dtype=np.float64)
    m = len(arr)
    if m == 0:
        raise ValueError("Cannot compute empirical CRPS on empty trials")
    if not math.isfinite(y):
        raise ValueError(f"Target y must be finite, got {y}")

    # E|X - y|
    mean_abs_error = float(np.mean(np.abs(arr - y)))

    # 0.5 * 1/M^2 * sum_i sum_j |x_i - x_j|
    diff_matrix = np.abs(arr[:, None] - arr[None, :])
    pairwise_term = float(np.sum(diff_matrix) / (2.0 * m * m))

    score = mean_abs_error - pairwise_term
    return float(max(0.0, score))


def normal_crps(y: float, mu: float, sigma: float) -> float:
    """Compute exact analytical CRPS for a univariate Gaussian prediction.
    
    CRPS(N(mu, sigma^2), y) = sigma * (z * (2*Phi(z) - 1) + 2*phi(z) - 1/sqrt(pi))
    where z = (y - mu) / sigma.
    """
    if not math.isfinite(y) or not math.isfinite(mu):
        raise ValueError(f"y and mu must be finite, got y={y}, mu={mu}")
    if sigma <= 1e-6:
        return float(abs(y - mu))

    z = (y - mu) / sigma
    phi = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    Phi = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    crps_val = sigma * (z * (2.0 * Phi - 1.0) + 2.0 * phi - (1.0 / math.sqrt(math.pi)))
    return float(max(0.0, crps_val))


def brier_score(y_true: int, p_pred: float) -> float:
    """Brier score for a binary outcome: (p - y)^2."""
    if y_true not in (0, 1):
        raise ValueError(f"y_true must be 0 or 1, got {y_true}")
    p_clipped = float(np.clip(p_pred, 0.0, 1.0))
    return float((p_clipped - y_true) ** 2)


def log_loss(y_true: int, p_pred: float, eps: float = 1e-6) -> float:
    """Log loss (cross-entropy) for a binary outcome with epsilon boundary protection."""
    if y_true not in (0, 1):
        raise ValueError(f"y_true must be 0 or 1, got {y_true}")
    p_clipped = float(np.clip(p_pred, eps, 1.0 - eps))
    if y_true == 1:
        return -float(math.log(p_clipped))
    return -float(math.log(1.0 - p_clipped))
