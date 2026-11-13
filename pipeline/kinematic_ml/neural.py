"""Small feedforward neural network and NumPy forward pass for AC75 kinematic speed (T11).

Contract (G3.1, G2.6):
- Mandatory 2-hidden-layer architecture with 32 SiLU units per layer.
- Strictly adheres to MOTION_PREDICTOR_ALLOWLIST: inputs are causal, SI units.
- Gaussian log-speed likelihood with left-censored handling for slow speeds (sog <= 2.0 m/s).
- Numerical equivalence: Pure NumPy forward pass matches PyTorch forward within 1e-5.
- Exports .pt, safe .npz, and .json inference representations with SHA-256 hashes.
- Seed reproducibility (seeds: 2027, 2028, 2029).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import warnings
from pathlib import Path
from typing import Any, Mapping, Sequence

# Prevent Windows MKL / OpenMP runtime collision when running alongside Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

try:
    torch.set_num_threads(4)
except RuntimeError as err:
    warnings.warn(f"torch.set_num_threads(4) skipped: {err}", RuntimeWarning, stacklevel=1)


CANONICAL_TEAMS = [
    "ac37:ETNZ",
    "ac37:INEOS",
    "ac37:LUNA_ROSSA",
    "ac37:AMERICAN_MAGIC",
    "ac37:ALINGHI",
    "ac37:ORIENT_EXPRESS",
]

FEATURE_COLS = [
    "tws_mps",
    "twa_sin",
    "twa_cos",
    "tack_side",
    "leg_type",
    "heading_cog_offset_deg",
    "course_wind_angle_deg",
    "practice_domain",
]

INPUT_DIM = len(FEATURE_COLS) + len(CANONICAL_TEAMS)  # 8 + 6 = 14


def encode_features(
    rows: Sequence[Mapping[str, Any]],
    scaler_mean: np.ndarray | None = None,
    scaler_scale: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Encodes input feature rows into float32 array adhering strictly to MOTION_PREDICTOR_ALLOWLIST.

    Returns (X, scaler_mean, scaler_scale).
    """
    n = len(rows)
    X = np.zeros((n, INPUT_DIM), dtype=np.float32)

    for i, r in enumerate(rows):
        X[i, 0] = float(r.get("tws_mps", 0.0))
        X[i, 1] = float(r.get("twa_sin", 0.0))
        X[i, 2] = float(r.get("twa_cos", 0.0))
        X[i, 3] = float(r.get("tack_side", 1.0))
        X[i, 4] = float(r.get("leg_type", 1.0))
        X[i, 5] = float(r.get("heading_cog_offset_deg", 0.0))
        X[i, 6] = float(r.get("course_wind_angle_deg", 0.0))
        X[i, 7] = float(r.get("practice_domain", 0.0))

        tid = r.get("team_id", "")
        for t_idx, team in enumerate(CANONICAL_TEAMS):
            if tid == team:
                X[i, 8 + t_idx] = 1.0
                break

    if scaler_mean is None or scaler_scale is None:
        if n > 0:
            scaler_mean = np.mean(X[:, :8], axis=0)
            scaler_scale = np.std(X[:, :8], axis=0)
            scaler_scale[scaler_scale < 1e-4] = 1.0
        else:
            scaler_mean = np.zeros(8, dtype=np.float32)
            scaler_scale = np.ones(8, dtype=np.float32)

    X[:, :8] = (X[:, :8] - scaler_mean) / scaler_scale
    return X, scaler_mean, scaler_scale


class AC75SpeedNN(nn.Module):
    """2x32 SiLU neural network predicting mean log-sog and log-scale."""

    def __init__(self, in_dim: int = INPUT_DIM, hidden_dim: int = 32) -> None:
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden_dim)
        self.act1 = nn.SiLU()
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.act2 = nn.SiLU()
        self.fc_out = nn.Linear(hidden_dim, 2)  # [mean_log_sog, log_scale]
        with torch.no_grad():
            self.fc_out.bias[0] = 2.5
            self.fc_out.bias[1] = -1.5

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h1 = self.act1(self.fc1(x))
        h2 = self.act2(self.fc2(h1))
        out = self.fc_out(h2)
        mu = torch.clamp(out[:, 0], min=-1.0, max=3.8)
        log_scale = torch.clamp(out[:, 1], min=-3.0, max=1.0)
        return mu, log_scale


def censored_gaussian_nll(
    y_sog: torch.Tensor,
    mu: torch.Tensor,
    log_scale: torch.Tensor,
    censor_threshold_mps: float = 2.0,
    sample_weights: torch.Tensor | None = None,
) -> torch.Tensor:
    """Computes negative log-likelihood with left-censoring for slow speeds (<= 2 m/s)."""
    scale = torch.exp(log_scale)
    censor_log_val = math.log(censor_threshold_mps)

    is_censored = y_sog <= censor_threshold_mps
    nll = torch.zeros_like(y_sog)

    if (~is_censored).any():
        uncensored_y = torch.log(torch.clamp(y_sog[~is_censored], min=1e-3))
        diff = uncensored_y - mu[~is_censored]
        z = diff / scale[~is_censored]
        nll[~is_censored] = (
            log_scale[~is_censored] + 0.5 * (z * z) + 0.5 * math.log(2.0 * math.pi)
        )

    if is_censored.any():
        z_c = (censor_log_val - mu[is_censored]) / scale[is_censored]
        phi = 0.5 * (1.0 + torch.erf(z_c / math.sqrt(2.0)))
        phi = torch.clamp(phi, min=1e-7, max=1.0 - 1e-7)
        nll[is_censored] = -torch.log(phi)

    if sample_weights is not None:
        w_sum = torch.clamp(torch.sum(sample_weights), min=1e-8)
        return torch.sum(nll * sample_weights) / w_sum
    return torch.mean(nll)


def numpy_forward_pass(
    X: np.ndarray,
    weights: Mapping[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Pure NumPy forward pass matching AC75SpeedNN with zero PyTorch dependency."""
    W1 = weights["fc1.weight"]
    b1 = weights["fc1.bias"]
    W2 = weights["fc2.weight"]
    b2 = weights["fc2.bias"]
    W3 = weights["fc_out.weight"]
    b3 = weights["fc_out.bias"]

    z1 = X @ W1.T + b1
    h1 = z1 / (1.0 + np.exp(-np.clip(z1, -30.0, 30.0)))

    z2 = h1 @ W2.T + b2
    h2 = z2 / (1.0 + np.exp(-np.clip(z2, -30.0, 30.0)))

    out = h2 @ W3.T + b3
    mu = np.clip(out[:, 0], -1.0, 3.8)
    log_scale = np.clip(out[:, 1], -3.0, 1.0)
    return mu, log_scale


def train_ac75_neural_model(
    X_train: np.ndarray,
    y_sog_train: np.ndarray,
    X_val: np.ndarray,
    y_sog_val: np.ndarray,
    *,
    sample_weights: np.ndarray | None = None,
    lr: float = 0.001,
    weight_decay: float = 0.0001,
    batch_size: int = 512,
    max_epochs: int = 150,
    patience: int = 15,
    seed: int = 2027,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Trains AC75SpeedNN on CPU with early stopping on validation loss."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    model = AC75SpeedNN(in_dim=X_train.shape[1])
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    t_X_train = torch.from_numpy(X_train).float()
    t_y_train = torch.from_numpy(y_sog_train).float()
    t_w_train = (
        torch.from_numpy(sample_weights).float()
        if sample_weights is not None
        else None
    )
    t_X_val = torch.from_numpy(X_val).float()
    t_y_val = torch.from_numpy(y_sog_val).float()

    best_val_loss = float("inf")
    best_weights = {
        k: v.cpu().detach().numpy().copy() for k, v in model.state_dict().items()
    }
    epochs_no_improve = 0
    history = []

    n_samples = len(X_train)
    indices = np.arange(n_samples)

    for epoch in range(max_epochs):
        model.train()
        np.random.shuffle(indices)
        epoch_losses = []

        for start_idx in range(0, n_samples, batch_size):
            end_idx = min(start_idx + batch_size, n_samples)
            batch_idx = indices[start_idx:end_idx]

            bx = t_X_train[batch_idx]
            by = t_y_train[batch_idx]
            bw = t_w_train[batch_idx] if t_w_train is not None else None

            optimizer.zero_grad()
            mu, log_scale = model(bx)
            loss = censored_gaussian_nll(by, mu, log_scale, sample_weights=bw)
            loss.backward()
            optimizer.step()
            epoch_losses.append(loss.item())

        train_loss = float(np.mean(epoch_losses)) if epoch_losses else 0.0

        model.eval()
        with torch.no_grad():
            if len(X_val) > 0:
                val_mu, val_log_scale = model(t_X_val)
                val_loss = float(
                    censored_gaussian_nll(t_y_val, val_mu, val_log_scale).item()
                )
            else:
                val_loss = train_loss

        history.append(
            {"epoch": epoch + 1, "train_loss": train_loss, "val_loss": val_loss}
        )

        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            epochs_no_improve = 0
            best_weights = {
                k: v.cpu().detach().numpy().copy()
                for k, v in model.state_dict().items()
            }
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                break

    metrics = {
        "best_epoch": max(1, len(history) - epochs_no_improve),
        "total_epochs": len(history),
        "best_val_loss": round(best_val_loss, 4),
        "final_train_loss": round(train_loss, 4),
        "seed": seed,
    }
    return best_weights, metrics


def train_ac75_neural_multiseed(
    X_train: np.ndarray,
    y_sog_train: np.ndarray,
    X_val: np.ndarray,
    y_sog_val: np.ndarray,
    *,
    sample_weights: np.ndarray | None = None,
    seeds: Sequence[int] = (2027, 2028, 2029),
    lr: float = 0.001,
    weight_decay: float = 0.0001,
    batch_size: int = 512,
    max_epochs: int = 120,
    patience: int = 15,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Trains AC75SpeedNN across frozen seeds (2027, 2028, 2029) and selects the best validation seed."""
    best_weights: dict[str, np.ndarray] = {}
    best_metrics: dict[str, Any] = {}
    best_val = float("inf")
    seed_results = []

    for s in seeds:
        w, m = train_ac75_neural_model(
            X_train,
            y_sog_train,
            X_val,
            y_sog_val,
            sample_weights=sample_weights,
            lr=lr,
            weight_decay=weight_decay,
            batch_size=batch_size,
            max_epochs=max_epochs,
            patience=patience,
            seed=int(s),
        )
        seed_results.append(m)
        if m["best_val_loss"] < best_val:
            best_val = m["best_val_loss"]
            best_weights = w
            best_metrics = dict(m)

    val_losses = [r["best_val_loss"] for r in seed_results]
    best_metrics["seed_runs"] = seed_results
    best_metrics["between_seed_val_loss_std"] = round(float(np.std(val_losses)), 5)
    return best_weights, best_metrics


def export_neural_bundle(
    weights: Mapping[str, np.ndarray],
    scaler_mean: np.ndarray,
    scaler_scale: np.ndarray,
    output_prefix: Path,
) -> dict[str, str]:
    """Exports .pt, .npz, and .json representations with stable SHA-256 hashes."""
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    # 1. Export PyTorch state_dict (.pt)
    pt_path = output_prefix.with_suffix(".pt")
    torch_state = {k: torch.from_numpy(np.asarray(v)) for k, v in weights.items()}
    torch.save(
        {
            "state_dict": torch_state,
            "scaler_mean": np.asarray(scaler_mean),
            "scaler_scale": np.asarray(scaler_scale),
        },
        pt_path,
    )
    pt_hash = hashlib.sha256(pt_path.read_bytes()).hexdigest()

    # 2. Export NPZ
    npz_path = output_prefix.with_suffix(".npz")
    export_dict = dict(weights)
    export_dict["scaler_mean"] = scaler_mean
    export_dict["scaler_scale"] = scaler_scale
    np.savez_compressed(npz_path, **export_dict)
    npz_hash = hashlib.sha256(npz_path.read_bytes()).hexdigest()

    # 3. Export JSON representation
    json_path = output_prefix.with_suffix(".json")
    json_export = {
        "schema_version": "ac75-model-1",
        "model_architecture": "2x32_silu_gaussian",
        "input_dim": int(INPUT_DIM),
        "canonical_teams": CANONICAL_TEAMS,
        "feature_cols": FEATURE_COLS,
        "scaler_mean": [round(float(v), 6) for v in scaler_mean],
        "scaler_scale": [round(float(v), 6) for v in scaler_scale],
        "weights": {k: v.tolist() for k, v in weights.items()},
        "pt_sha256": pt_hash,
        "npz_sha256": npz_hash,
    }
    json_path.write_text(json.dumps(json_export, indent=2), encoding="utf-8")
    json_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()

    return {
        "pt_path": str(pt_path),
        "npz_path": str(npz_path),
        "json_path": str(json_path),
        "pt_sha256": pt_hash,
        "npz_sha256": npz_hash,
        "json_sha256": json_hash,
    }
