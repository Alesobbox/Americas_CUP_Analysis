"""Sample-level kernel conditional distributions and quadratic tack adjustment."""

from typing import Any
import math
import numpy as np
from .dataset import PolarDataset
from .bootstrap import design
from .constants import HIST_MIN_KT, HIST_STEP_KT, HIST_N_BINS


def _estimate_tack_fixed_effect(
    ds: PolarDataset, mask: np.ndarray, weights: np.ndarray | None = None
) -> dict[int, tuple[float, float]]:
    """Estimate fixed tack effect (STARBOARD - PORT) for SOG & wind-VMG per mode."""
    weights = ds.weights if weights is None else weights
    out: dict[int, tuple[float, float]] = {}
    for m in (1, 0):
        idx = mask & (ds.mode == m)
        if not np.any(idx):
            out[m] = (0.0, 0.0)
            continue
        tacks = ds.tack[idx]
        if np.all(tacks == tacks[0]):
            out[m] = (0.0, 0.0)
            continue
        X = design(ds, idx)
        gram = X.T @ (weights[idx, None] * X)
        beta_sog = np.linalg.lstsq(gram, X.T @ (weights[idx] * ds.sog[idx]), rcond=None)[0]
        beta_vmg = np.linalg.lstsq(gram, X.T @ (weights[idx] * ds.vmg[idx]), rcond=None)[0]
        out[m] = (float(beta_sog[-1]), float(beta_vmg[-1]))
    return out


def _weighted_quantile_from_hist(hist: np.ndarray, q: float) -> np.ndarray:
    """Linearly interpolated quantile across fixed 0.25 kt bins [4.0, 50.0)."""
    totals = hist.sum(axis=1, keepdims=True)
    safe_totals = np.where(totals > 1e-12, totals, 1.0)
    cdf = np.cumsum(hist, axis=1) / safe_totals
    pos = np.argmax(cdf >= q, axis=1)
    rows = np.arange(hist.shape[0])
    c_hi = cdf[rows, pos]
    c_lo = np.where(pos > 0, cdf[rows, np.maximum(0, pos - 1)], 0.0)
    frac = np.where((c_hi - c_lo) > 1e-12, (q - c_lo) / np.maximum(1e-12, c_hi - c_lo), 0.5)
    vals = HIST_MIN_KT + (pos + frac) * HIST_STEP_KT
    return np.where(totals[:, 0] > 1e-12, vals, np.nan)


def _fit_and_predict_subset(
    ds: PolarDataset,
    train_mask: np.ndarray,
    eval_mask: np.ndarray | None = None,
    sample_weights: np.ndarray | None = None,
) -> dict[str, Any]:
    """Fit kernel mean + fixed-effect tack + nonparametric conditional quantiles."""
    G = len(ds.grid_keys)
    weights = ds.weights if sample_weights is None else sample_weights
    tack_eff = _estimate_tack_fixed_effect(ds, train_mask, weights)
    beta_sog_cell = np.array([tack_eff[int(m)][0] for m in ds.mode], dtype=float)
    beta_vmg_cell = np.array([tack_eff[int(m)][1] for m in ds.mode], dtype=float)

    sog_adj = ds.sog - beta_sog_cell * ds.tack
    vmg_adj = ds.vmg - beta_vmg_cell * ds.tack

    # Mode fallback means if a boundary cell has near-zero kernel support
    mode_mean_sog: dict[int, float] = {}
    mode_mean_vmg: dict[int, float] = {}
    for m in (1, 0):
        tr_m = train_mask & (ds.mode == m)
        if np.any(tr_m):
            mode_mean_sog[m] = float(np.average(sog_adj[tr_m], weights=weights[tr_m]))
            mode_mean_vmg[m] = float(np.average(vmg_adj[tr_m], weights=weights[tr_m]))
        else:
            mode_mean_sog[m] = float(np.average(sog_adj[train_mask], weights=weights[train_mask]))
            mode_mean_vmg[m] = float(np.average(vmg_adj[train_mask], weights=weights[train_mask]))

    g_tr_idx = ds.cell_to_grid[train_mask]
    w_tr = weights[train_mask]
    w_grid = np.bincount(g_tr_idx, weights=w_tr, minlength=G)
    wsog_grid = np.bincount(g_tr_idx, weights=w_tr * sog_adj[train_mask], minlength=G)
    wvmg_grid = np.bincount(g_tr_idx, weights=w_tr * vmg_adj[train_mask], minlength=G)

    denom = ds.K_grid @ w_grid
    valid_g = denom > 1e-6
    safe_d = np.where(valid_g, denom, 1.0)
    fallback_sog_g = np.array([mode_mean_sog[int(m)] for m in ds.grid_keys[:, 0]], dtype=float)
    fallback_vmg_g = np.array([mode_mean_vmg[int(m)] for m in ds.grid_keys[:, 0]], dtype=float)

    grid_mean_sog = np.where(valid_g, (ds.K_grid @ wsog_grid) / safe_d, fallback_sog_g)
    grid_mean_vmg = np.where(valid_g, (ds.K_grid @ wvmg_grid) / safe_d, fallback_vmg_g)

    # Conditional quantile histograms at each grid point in adjusted SOG & VMG space
    y_bin_sog = np.clip(
        np.floor((sog_adj[train_mask] - HIST_MIN_KT) / HIST_STEP_KT).astype(int),
        0,
        HIST_N_BINS - 1,
    )
    h_sog = np.zeros((G, HIST_N_BINS), dtype=float)
    np.add.at(h_sog, (g_tr_idx, y_bin_sog), w_tr)
    smoothed_h = ds.K_grid @ h_sog
    grid_p50_sog = _weighted_quantile_from_hist(smoothed_h, 0.50)
    grid_p90_sog = _weighted_quantile_from_hist(smoothed_h, 0.90)
    grid_p50_sog = np.where(np.isfinite(grid_p50_sog), grid_p50_sog, grid_mean_sog)
    grid_p90_sog = np.where(np.isfinite(grid_p90_sog), grid_p90_sog, grid_mean_sog)

    result: dict[str, Any] = {
        "tack_effect": tack_eff,
        "grid_support": denom,
        "grid_mean_sog": grid_mean_sog,
        "grid_mean_vmg": grid_mean_vmg,
        "grid_p50_sog": grid_p50_sog,
        "grid_p90_sog": grid_p90_sog,
    }
    occupancy = np.zeros((G, len(ds.cluster_key)), dtype=np.int32)
    occupancy[ds.cell_to_grid[train_mask], ds.cluster_id[train_mask]] = 1
    cluster_support = ((ds.K_grid >= 0.25).astype(np.int32) @ occupancy > 0).sum(axis=1)
    result["grid_clusters"] = cluster_support
    if eval_mask is not None:
        ev_g = ds.cell_to_grid[eval_mask]
        tack_offset_sog = beta_sog_cell[eval_mask] * ds.tack[eval_mask]
        tack_offset_vmg = beta_vmg_cell[eval_mask] * ds.tack[eval_mask]
        result["eval_sog"] = grid_mean_sog[ev_g] + tack_offset_sog
        result["eval_vmg"] = grid_mean_vmg[ev_g] + tack_offset_vmg
        result["eval_p50"] = grid_p50_sog[ev_g] + tack_offset_sog
        result["eval_p90"] = grid_p90_sog[ev_g] + tack_offset_sog
        supported = (denom[ev_g] >= 12) & (cluster_support[ev_g] >= 2)
        result["eval_supported"] = supported
        for key in ("eval_sog", "eval_vmg", "eval_p50", "eval_p90"):
            result[key] = np.where(supported, result[key], np.nan)
    return result


def _validation_metrics(
    ds: PolarDataset,
    predictions: dict[str, np.ndarray],
    label: str,
    folds: int,
) -> dict[str, Any]:
    pred_sog, pred_vmg = predictions["sog"], predictions["vmg"]
    pred_p50, pred_p90 = predictions["p50"], predictions["p90"]
    valid = np.isfinite(pred_sog) & np.isfinite(pred_vmg) & np.isfinite(pred_p90)
    if not np.any(valid):
        return {
            "label": label,
            "folds": folds,
            "status": "unavailable",
            "evaluated_sample_count": 0,
            "excluded_sample_count": len(ds.sog),
        }
    w = ds.weights[valid]
    sog, vmg = ds.sog[valid], ds.vmg[valid]
    pred_p50, pred_p90 = pred_p50[valid], pred_p90[valid]
    err_sog = sog - pred_sog[valid]
    err_vmg = vmg - pred_vmg[valid]
    ybar_sog = float(np.average(sog, weights=w))
    ybar_vmg = float(np.average(vmg, weights=w))
    mse_sog = float(np.average(err_sog * err_sog, weights=w))
    mse_vmg = float(np.average(err_vmg * err_vmg, weights=w))
    var_sog = max(1e-9, float(np.average((sog - ybar_sog) ** 2, weights=w)))
    var_vmg = max(1e-9, float(np.average((vmg - ybar_vmg) ** 2, weights=w)))

    def pinball(y_true: np.ndarray, q_hat: np.ndarray, q: float) -> float:
        diff = y_true - q_hat
        loss = np.where(diff >= 0.0, q * diff, (q - 1.0) * diff)
        return float(np.average(loss, weights=w))

    return {
        "label": label,
        "target": "individual accepted 1 Hz speed observations",
        "evaluated_sample_count": int(valid.sum()),
        "excluded_sample_count": int((~valid).sum()),
        "folds": int(folds),
        "sog_rmse_kt": round(math.sqrt(mse_sog), 3),
        "sog_mae_kt": round(float(np.average(np.abs(err_sog), weights=w)), 3),
        "sog_r2": round(1.0 - mse_sog / var_sog, 4),
        "vmg_rmse_kt": round(math.sqrt(mse_vmg), 3),
        "vmg_mae_kt": round(float(np.average(np.abs(err_vmg), weights=w)), 3),
        "vmg_r2": round(1.0 - mse_vmg / var_vmg, 4),
        "p50_pinball_loss_kt": round(pinball(sog, pred_p50, 0.50), 3),
        "p90_pinball_loss_kt": round(pinball(sog, pred_p90, 0.90), 3),
        "p50_empirical_coverage": round(
            float(np.average((sog <= pred_p50).astype(float), weights=w)), 4
        ),
        "p90_empirical_coverage": round(
            float(np.average((sog <= pred_p90).astype(float), weights=w)), 4
        ),
    }
