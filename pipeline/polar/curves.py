"""Descriptive full-data curves; never labelled as held-out forecasts."""

from typing import Any
from collections import defaultdict
import numpy as np
from .dataset import PolarDataset
from .fitting import _estimate_tack_fixed_effect
from .constants import (
    KERNEL_BW_TWS_KT,
    KERNEL_BW_TWA_DEG,
    MIN_CURVE_SUPPORT_S,
    MIN_CURVE_CLUSTERS,
    STEADY_MIN_TWS_KT,
    STEADY_MAX_TWS_KT,
    ARCHIVE_TWS_BRACKETS,
)


def _eval_curve_points(
    ds: PolarDataset,
    mask: np.ndarray,
    mode_val: int,
    tws_lo: float,
    tws_hi: float,
    twa_grid: list[float],
) -> list[dict[str, Any]]:
    """Compute observed conditional polar curve (mean, p50, p90) vs |TWA| for a TWS band."""
    sel = mask & (ds.mode == mode_val) & (ds.tws >= tws_lo) & (ds.tws <= tws_hi)
    if not np.any(sel):
        return []
    tack_eff = _estimate_tack_fixed_effect(ds, mask)
    beta_sog = tack_eff[mode_val][0]
    beta_vmg = tack_eff[mode_val][1]

    sog_adj = ds.sog[sel] - beta_sog * ds.tack[sel]
    vmg_adj = ds.vmg[sel] - beta_vmg * ds.tack[sel]
    tws_sel = ds.tws[sel]
    twa_sel = ds.twa[sel]
    w_sel = ds.weights[sel]
    cids = ds.cluster_id[sel]
    tws_ref = float(np.average(tws_sel, weights=w_sel))

    points: list[dict[str, Any]] = []
    for target_twa in twa_grid:
        k = (
            np.exp(
                -0.5
                * (
                    ((tws_ref - tws_sel) / KERNEL_BW_TWS_KT) ** 2
                    + ((target_twa - twa_sel) / KERNEL_BW_TWA_DEG) ** 2
                )
            )
            * w_sel
        )
        eff_s = float(k.sum())
        support_clusters = int(len(set(int(c) for c in cids[k >= 0.25 * w_sel])))
        if eff_s < MIN_CURVE_SUPPORT_S or support_clusters < MIN_CURVE_CLUSTERS:
            continue
        mean_sog = float(np.sum(k * sog_adj) / eff_s)
        mean_vmg = float(np.sum(k * vmg_adj) / eff_s)
        order = np.argsort(sog_adj)
        cdf = np.cumsum(k[order]) / eff_s
        p50_sog = float(sog_adj[order][int(np.argmax(cdf >= 0.50))])
        p90_sog = float(sog_adj[order][int(np.argmax(cdf >= 0.90))])

        order_v = np.argsort(vmg_adj)
        cdf_v = np.cumsum(k[order_v]) / eff_s
        p50_vmg = float(vmg_adj[order_v][int(np.argmax(cdf_v >= 0.50))])
        p90_vmg = float(vmg_adj[order_v][int(np.argmax(cdf_v >= 0.90))])
        points.append(
            {
                "twa_deg": float(target_twa),
                "mean_sog_kt": round(mean_sog, 2),
                "p50_sog_kt": round(p50_sog, 2),
                "p90_sog_kt": round(max(p50_sog, p90_sog), 2),
                "mean_wind_vmg_kt": round(mean_vmg, 2),
                "p50_wind_vmg_kt": round(p50_vmg, 2),
                "p90_wind_vmg_kt": round(max(p50_vmg, p90_vmg), 2),
                "effective_coverage_s": round(eff_s, 1),
                "support_clusters": support_clusters,
            }
        )
    return points


def _build_race_brackets(
    ds: PolarDataset, race_mask: np.ndarray, full_mask: np.ndarray
) -> dict[str, list[dict[str, Any]]]:
    twa_grids = {
        "upwind": [30.0 + 2.5 * i for i in range(18)],  # 30..72.5
        "downwind": [110.0 + 2.5 * i for i in range(25)],  # 110..170
    }
    out: dict[str, list[dict[str, Any]]] = {"upwind": [], "downwind": []}
    for mode_name, mode_val in (("upwind", 1), ("downwind", 0)):
        sel = race_mask & (ds.mode == mode_val)
        if not np.any(sel):
            continue
        r_tws = ds.tws[sel]
        r_w = ds.weights[sel]
        tws_min = float(r_tws.min())
        tws_max = float(r_tws.max())
        tws_ref = float(np.average(r_tws, weights=r_w))
        pts = _eval_curve_points(
            ds,
            full_mask,
            mode_val,
            max(STEADY_MIN_TWS_KT, tws_min - 1.0),
            min(STEADY_MAX_TWS_KT, tws_max + 1.0),
            twa_grids[mode_name],
        )
        out[mode_name].append(
            {
                "id": "race_window",
                "label": f"Race wind ({tws_min:.1f}–{tws_max:.1f} kt)",
                "tws_min_kt": round(tws_min, 1),
                "tws_max_kt": round(tws_max, 1),
                "tws_ref_kt": round(tws_ref, 1),
                "points": pts,
            }
        )
        for bid, blabel, b_lo, b_hi, _ in ARCHIVE_TWS_BRACKETS:
            if np.any(sel & (ds.tws >= b_lo) & (ds.tws <= b_hi)):
                bpts = _eval_curve_points(ds, full_mask, mode_val, b_lo, b_hi, twa_grids[mode_name])
                if bpts:
                    out[mode_name].append(
                        {
                            "id": bid,
                            "label": blabel,
                            "tws_min_kt": b_lo,
                            "tws_max_kt": b_hi,
                            "tws_ref_kt": 0.5 * (b_lo + b_hi),
                            "points": bpts,
                        }
                    )
    return out


def _build_observed_bins(
    ds: PolarDataset, boat_mask: np.ndarray, pred_sog: np.ndarray
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"upwind": [], "downwind": []}
    for mode_name, mode_val in (("upwind", 1), ("downwind", 0)):
        sel = boat_mask & (ds.mode == mode_val)
        if not np.any(sel):
            continue
        grouped: dict[tuple[str, float, float], list[int]] = defaultdict(list)
        indices = np.flatnonzero(sel)
        for i in indices:
            tack_lbl = "STARBOARD" if ds.tack[i] > 0 else "PORT"
            grouped[(tack_lbl, float(ds.tws_bin[i]), float(ds.twa_bin[i]))].append(int(i))
        rows = []
        for (tack_lbl, tws_b, twa_b), idxs in sorted(
            grouped.items(), key=lambda x: (x[0][2], x[0][1], x[0][0])
        ):
            w = ds.weights[idxs]
            w_sum = float(w.sum())
            rows.append(
                {
                    "tack": tack_lbl,
                    "tws_bin_kt": tws_b,
                    "twa_bin_deg": twa_b,
                    "sog_mean_kt": round(float(np.average(ds.sog[idxs], weights=w)), 2),
                    "sog_p90_kt": round(float(np.quantile(ds.sog[idxs], 0.9)), 2),
                    "wind_vmg_mean_kt": round(float(np.average(ds.vmg[idxs], weights=w)), 2),
                    "predicted_sog_kt": (
                        round(float(np.mean(pred_sog[idxs][np.isfinite(pred_sog[idxs])])), 2)
                        if np.any(np.isfinite(pred_sog[idxs]))
                        else None
                    ),
                    "predicted_sample_count": int(np.isfinite(pred_sog[idxs]).sum()),
                    "sample_count": int(round(w_sum)),
                }
            )
        out[mode_name] = rows
    return out
