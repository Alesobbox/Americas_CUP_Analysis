"""Chronological cross-validation and candidate model selection for AC75 (T15).

Contract (G3.6):
- Evaluates empirical, spline, and mandatory small neural network on expanding chronological folds.
- Uses ChronologicalSplitManager train_families and val_families without leakage.
- Component metrics: log-speed censored NLL, SOG RMSE/MAE, lognormal speed CRPS, censored event NLL.
- End-to-end race metrics: race-margin CRPS (s), margin MAE (s), winner Brier, winner LogLoss,
  and 50% / 80% / 95% empirical interval coverage on verified completed races.
- Paired candidate-minus-best differences per date on common supported races.
- Candidate selection: simplest candidate within 1 standard error of best CRPS,
  ordering: empirical < spline < neural.
- Strictly respects final evaluation holdout isolation.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

# Cap CPU threads at 4 and prevent Windows MKL collisions
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.special import log_ndtr

from pipeline.kinematic_ml.baselines import (
    BinnedPolarBaseline,
    RegularizedSplinePolarBaseline,
    _compute_race_weights,
)
from pipeline.kinematic_ml.calibration import (
    ChronologicalInnerSplit,
    PredictorCalibrationArtifacts,
    build_predictor_calibration,
)
from pipeline.kinematic_ml.events import (
    ManeuverDurationModel,
    StartBehaviorModel,
)
from pipeline.kinematic_ml.evidence.basis import EvidenceBasis
from pipeline.kinematic_ml.evidence.policy import EvidencePolicy
from pipeline.kinematic_ml.evidence.qualifier import qualify_evaluation_targets
from pipeline.kinematic_ml.inference import (
    InstalledModelBundle,
    predict_scenario,
)
from pipeline.kinematic_ml.neural import (
    encode_features,
    numpy_forward_pass,
    train_ac75_neural_model,
    train_ac75_neural_multiseed,
)
from pipeline.kinematic_ml.routes import (
    LegRouteTemplate,
    RouteTemplateLibrary,
)
from pipeline.kinematic_ml.selection import select_default_model_from_races
from pipeline.kinematic_ml.splits import ChronologicalSplitManager
from pipeline.kinematic_ml.training_view import (
    filter_maneuvers,
    filter_route_templates,
    filter_start_intervals,
    filter_steady_windows,
    load_authenticated_training_view,
)
from pipeline.kinematic_ml.uncertainty import (
    PairedResidualSampler,
    VarianceLedger,
)

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
SEALED_DIR = FORECAST_DIR / "sealed"
EVAL_DIR = FORECAST_DIR / "evaluation"

CANDIDATE_NAMES = (
    "empirical_binned_polar",
    "regularized_spline_polar",
    "neural_network_silu",
)


def normal_crps(y: float, mu: float, sigma: float) -> float:
    """Computes exact analytical CRPS for a univariate Gaussian prediction."""
    if sigma <= 1e-6:
        return abs(y - mu)

    z = (y - mu) / sigma
    phi = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    Phi = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    crps = sigma * (z * (2.0 * Phi - 1.0) + 2.0 * phi - (1.0 / math.sqrt(math.pi)))
    return float(max(0.0, crps))


def brier_score(y_true: int, p_pred: float) -> float:
    """Brier score for binary outcome."""
    p_clipped = float(np.clip(p_pred, 0.0, 1.0))
    return float((p_clipped - y_true) ** 2)


def log_loss(y_true: int, p_pred: float, eps: float = 1e-6) -> float:
    """Log loss (cross-entropy) for binary outcome."""
    p_clipped = float(np.clip(p_pred, eps, 1.0 - eps))
    if y_true == 1:
        return -math.log(p_clipped)
    return -math.log(1.0 - p_clipped)


def _censored_log_speed_nll(y_sog: float, mu_log: float, sigma_log: float, censor_mps: float = 2.0) -> float:
    sig = max(0.05, float(sigma_log))
    if y_sog <= censor_mps:
        z_c = (math.log(censor_mps) - mu_log) / sig
        return float(-log_ndtr(z_c))
    z = (math.log(y_sog) - mu_log) / sig
    return float(math.log(sig) + 0.5 * (z * z) + 0.5 * math.log(2.0 * math.pi))


def _score_motion_predictions(
    y_sog_arr: np.ndarray,
    mu_log_arr: np.ndarray,
    sigma_log_arr: np.ndarray,
) -> dict[str, float]:
    """Computes SOG MAE/RMSE, log-speed censored NLL, log-speed CRPS, and linear SOG CRPS."""
    sig = np.clip(sigma_log_arr, 0.05, 1.5)
    pred_sog = np.exp(mu_log_arr + 0.5 * (sig ** 2))
    pred_sog_std = pred_sog * np.sqrt(np.maximum(1e-6, np.exp(sig ** 2) - 1.0))

    mae = float(np.mean(np.abs(y_sog_arr - pred_sog)))
    rmse = float(math.sqrt(np.mean((y_sog_arr - pred_sog) ** 2)))

    nlls = [
        _censored_log_speed_nll(float(y), float(m), float(s))
        for y, m, s in zip(y_sog_arr, mu_log_arr, sig)
    ]
    log_crps = [
        normal_crps(math.log(max(float(y), 2.0)), float(m), float(s))
        for y, m, s in zip(y_sog_arr, mu_log_arr, sig)
    ]
    sog_crps = [
        normal_crps(float(y), float(ps), float(std_s))
        for y, ps, std_s in zip(y_sog_arr, pred_sog, pred_sog_std)
    ]

    return {
        "sog_mae_mps": round(mae, 3),
        "sog_rmse_mps": round(rmse, 3),
        "log_speed_nll": round(float(np.mean(nlls)), 4),
        "log_speed_crps": round(float(np.mean(log_crps)), 4),
        "sog_crps_mps": round(float(np.mean(sog_crps)), 3),
        "crps": round(float(np.mean(sog_crps)), 3),
    }


def evaluate_candidates_on_data(
    train_rows: Sequence[Mapping[str, Any]],
    test_rows: Sequence[Mapping[str, Any]],
    *,
    val_rows: Sequence[Mapping[str, Any]] | None = None,
    seed: int = 2027,
) -> dict[str, dict[str, float]]:
    """Trains and evaluates empirical, spline, and neural candidates on a train/val/test fold."""
    if not train_rows or not test_rows:
        return {}

    if val_rows is None or len(val_rows) == 0:
        n_tr = max(1, int(len(train_rows) * 0.8))
        inner_train = list(train_rows[:n_tr])
        inner_val = list(train_rows[n_tr:]) if n_tr < len(train_rows) else list(train_rows)
    else:
        inner_train = list(train_rows)
        inner_val = list(val_rows)

    y_test_sog = np.array([float(r.get("sog_mps", 0.0)) for r in test_rows], dtype=float)

    # 1. Empirical Polar Baseline
    binned_model = BinnedPolarBaseline()
    binned_model.fit(inner_train)
    binned_mu = np.zeros(len(test_rows), dtype=float)
    binned_sig = np.zeros(len(test_rows), dtype=float)
    for idx, r in enumerate(test_rows):
        mu_l, log_s = binned_model.predict_distribution(r)
        binned_mu[idx] = mu_l
        binned_sig[idx] = math.exp(log_s)
    binned_metrics = _score_motion_predictions(y_test_sog, binned_mu, binned_sig)
    binned_metrics["complexity_order"] = 1

    # 2. Regularized Spline Baseline (tuned on inner_val)
    spline_model = RegularizedSplinePolarBaseline(alpha=1.0)
    spline_model.fit_with_validation(inner_train, inner_val)
    spline_mu = np.zeros(len(test_rows), dtype=float)
    spline_sig = np.zeros(len(test_rows), dtype=float)
    for idx, r in enumerate(test_rows):
        mu_l, log_s = spline_model.predict_distribution(r)
        spline_mu[idx] = mu_l
        spline_sig[idx] = math.exp(log_s)
    spline_metrics = _score_motion_predictions(y_test_sog, spline_mu, spline_sig)
    spline_metrics["complexity_order"] = 2

    # 3. Small Neural Network (2x32 SiLU) — scaler fit strictly on inner_train
    X_train, mean_tr, scale_tr = encode_features(inner_train)
    y_train = np.array([float(r.get("sog_mps", 0.0)) for r in inner_train], dtype=np.float32)
    w_train = _compute_race_weights(inner_train).astype(np.float32)

    X_val, _, _ = encode_features(inner_val, scaler_mean=mean_tr, scaler_scale=scale_tr)
    y_val = np.array([float(r.get("sog_mps", 0.0)) for r in inner_val], dtype=np.float32)

    X_test, _, _ = encode_features(test_rows, scaler_mean=mean_tr, scaler_scale=scale_tr)

    nn_weights, _ = train_ac75_neural_model(
        X_train,
        y_train,
        X_val,
        y_val,
        sample_weights=w_train,
        lr=0.001,
        batch_size=512,
        max_epochs=60,
        patience=10,
        seed=seed,
    )
    nn_mu, nn_log_scale = numpy_forward_pass(X_test, nn_weights)
    nn_metrics = _score_motion_predictions(y_test_sog, nn_mu, np.exp(nn_log_scale))
    nn_metrics["complexity_order"] = 3

    return {
        "empirical_binned_polar": binned_metrics,
        "regularized_spline_polar": spline_metrics,
        "neural_network_silu": nn_metrics,
    }


def select_best_candidate(
    candidate_scores: Mapping[str, dict[str, float]],
    per_date_crps_diffs: Mapping[str, Sequence[float]] | None = None,
) -> tuple[str, str]:
    """Selects the default experimental candidate under G3.6.

    Rule: Simplest candidate within 1 standard error of the minimum CRPS.
    Order of simplicity: empirical (1) < spline (2) < neural (3).
    """
    sorted_by_crps = sorted(candidate_scores.items(), key=lambda x: x[1]["crps"])
    best_candidate, best_metrics = sorted_by_crps[0]
    best_crps = best_metrics["crps"]

    se = 0.05
    if per_date_crps_diffs:
        # Compute largest standard error of paired candidate-minus-best differences across dates
        ses = []
        for cand_name, diffs in per_date_crps_diffs.items():
            if cand_name != best_candidate and len(diffs) >= 5:
                ses.append(float(np.std(diffs, ddof=1) / math.sqrt(len(diffs))))
        if ses:
            se = float(max(ses))

    eligible = [
        (name, m)
        for name, m in candidate_scores.items()
        if m["crps"] <= best_crps + se
    ]
    eligible.sort(key=lambda x: x[1].get("complexity_order", 99))
    selected_name = eligible[0][0]
    rationale = (
        f"Selected '{selected_name}' (complexity {eligible[0][1]['complexity_order']}) "
        f"within 1 SE ({se:.3f}) of best CRPS ({best_crps:.3f})"
    )
    return selected_name, rationale


def _predict_maneuver_entry_speeds(
    turns: Sequence[Mapping[str, Any]],
    predict_dist_fn: Any,
) -> list[dict[str, Any]]:
    """Populates entry_speed_predicted_mps on turns using the candidate motion model."""
    enriched: list[dict[str, Any]] = []
    for t in turns:
        row = dict(t)
        tws_raw = t.get("as_of_tws_mps")
        if tws_raw is None:
            tws_raw = t.get("tws_mps")
        if tws_raw is None or not math.isfinite(float(tws_raw)):
            row["entry_speed_predicted_mps"] = None
            enriched.append(row)
            continue
        tws = float(tws_raw)
        leg_type = int(t.get("leg_type", 1 if str(t.get("turn_type", "tack")) == "tack" else 0))
        twa_deg = 45.0 if leg_type == 1 else 140.0
        feat = {
            "team_id": str(t.get("team_id", "")),
            "tws_mps": tws,
            "twa_sin": math.sin(math.radians(twa_deg)),
            "twa_cos": math.cos(math.radians(twa_deg)),
            "tack_side": 1,
            "leg_type": leg_type,
            "heading_cog_offset_deg": 2.5,
            "course_wind_angle_deg": twa_deg,
            "practice_domain": int(t.get("practice_domain", 0)),
        }
        mu_l, log_s = predict_dist_fn(feat)
        sig = max(0.05, math.exp(log_s))
        pred_sog = math.exp(mu_l + 0.5 * (sig ** 2))
        row["entry_speed_predicted_mps"] = round(float(pred_sog), 3)
        row["tws_mps"] = tws
        enriched.append(row)
    return enriched


def make_neural_predict_fn(
    weights: Mapping[str, np.ndarray],
    scaler_mean: np.ndarray,
    scaler_scale: np.ndarray,
) -> Any:
    """Builds a single-row (mu_log_sog, log_scale) predictor closure for a fitted neural model."""
    def _predict_dist(feature_row: Mapping[str, Any]) -> tuple[float, float]:
        X_one, _, _ = encode_features([feature_row], scaler_mean=scaler_mean, scaler_scale=scaler_scale)
        mu, log_s = numpy_forward_pass(X_one, weights)
        return float(mu[0]), float(log_s[0])

    return _predict_dist


def _filter_rows_by_dates(
    rows: Sequence[Mapping[str, Any]],
    allowed_dates: set[str],
) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in rows
        if str(r.get("date_str") or r.get("date") or "") in allowed_dates
        or str(r.get("family_id") or r.get("attempt_id") or "") in allowed_dates
    ]


def _extract_ledger_field(raw_val: Any) -> tuple[Any, bool | None, str | None, str]:
    if isinstance(raw_val, Mapping):
        val = raw_val.get("value")
        ver = raw_val.get("verified")
        ver_bool = bool(ver) if ver is not None else None
        prov = str(raw_val.get("provenance") or "")
        basis = raw_val.get("evidence_basis")
        if basis is None and prov.startswith("candidate"):
            basis = EvidenceBasis.CANDIDATE_UNVERIFIED.value
        src = str(raw_val.get("source_ref") or raw_val.get("source_url") or "")
        return val, ver_bool, (str(basis) if basis is not None else None), src
    return raw_val, None, None, ""


def _build_race_target_record(
    fid: str,
    d_str: str,
    out_row: Mapping[str, Any] | None,
    rc_info: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], float | None]:
    """Converts outcome ledger entry into EvidencePolicy target schema and simulation sign delta_t_s."""
    if not out_row:
        return (
            {
                "race_id": fid,
                "family_id": fid,
                "date": d_str,
                "attempt_id": str((rc_info or {}).get("attempt_id") or fid),
                "evidence_basis": EvidenceBasis.UNAVAILABLE.value,
                "verified": False,
                "status": "unavailable",
            },
            None,
        )

    team_a = str(out_row.get("team_a") or "")
    team_b = str(out_row.get("team_b") or "")
    if not team_a or not team_b:
        comps = out_row.get("competitors", [])
        if isinstance(comps, list) and len(comps) == 2:
            team_a, team_b = str(comps[0]), str(comps[1])

    fs_val, fs_ver, fs_basis, fs_src = _extract_ledger_field(out_row.get("finish_status"))
    win_val, win_ver, win_basis, win_src = _extract_ledger_field(out_row.get("winner"))
    delta_raw_val, d_ver, d_basis, d_src = _extract_ledger_field(out_row.get("delta_s"))
    margin_raw_val, m_ver, m_basis, m_src = _extract_ledger_field(out_row.get("race_margin_s"))
    fa_val, fa_ver, fa_basis, fa_src = _extract_ledger_field(out_row.get("finish_time_a_s"))
    fb_val, fb_ver, fb_basis, fb_src = _extract_ledger_field(out_row.get("finish_time_b_s"))

    winner = str(win_val) if win_val is not None else None
    row_ver = bool(out_row.get("verified", False))
    row_basis = out_row.get("evidence_basis")
    if row_basis is None:
        nested_bases = [b for b in (fs_basis, win_basis, d_basis, m_basis, fa_basis, fb_basis) if b]
        if any(b == EvidenceBasis.CANDIDATE_UNVERIFIED.value for b in nested_bases):
            row_basis = EvidenceBasis.CANDIDATE_UNVERIFIED.value
        elif row_ver:
            row_basis = EvidenceBasis.SOURCE_CONFIRMED_ON_WATER.value
        else:
            row_basis = EvidenceBasis.CANDIDATE_UNVERIFIED.value

    nested_vers = [v for v in (fs_ver, win_ver, d_ver, m_ver, fa_ver, fb_ver) if v is not None]
    is_verified = (bool(out_row.get("verified", True)) and all(nested_vers)) if nested_vers else row_ver

    # Determine signed margin under BOTH EvidencePolicy (finish_a - finish_b) and simulator (times_b - times_a)
    policy_margin_s: float | None = None
    sim_delta_t_s: float | None = None
    if margin_raw_val is not None:
        policy_margin_s = float(margin_raw_val)
        sim_delta_t_s = -policy_margin_s
    elif delta_raw_val is not None and winner in (team_a, team_b):
        abs_d = float(delta_raw_val)
        sim_delta_t_s = abs_d if winner == team_a else -abs_d
        policy_margin_s = -abs_d if winner == team_a else abs_d

    attempts = out_row.get("attempts")
    attempt_id = str(
        out_row.get("attempt_id")
        or (rc_info or {}).get("attempt_id")
        or (attempts[0] if isinstance(attempts, list) and attempts else fid)
    )
    field_evidence: dict[str, Any] = {}
    for fname, val, ver, basis in (
        ("finish_status", fs_val, fs_ver if fs_ver is not None else is_verified, fs_basis or row_basis),
        ("winner", winner, win_ver if win_ver is not None else is_verified, win_basis or row_basis),
        ("race_margin_s", policy_margin_s, (d_ver if d_ver is not None else (m_ver if m_ver is not None else is_verified)), d_basis or m_basis or row_basis),
    ):
        if val is not None:
            field_evidence[fname] = {
                "value": val,
                "verified": bool(ver),
                "evidence_basis": str(basis),
            }

    target = {
        "race_id": str(out_row.get("race_id") or fid),
        "family_id": fid,
        "date": d_str,
        "date_str": d_str,
        "attempt_id": attempt_id,
        "team_a": team_a,
        "team_b": team_b,
        "winner": winner,
        "finish_time_a_s": float(fa_val) if fa_val is not None else None,
        "finish_time_b_s": float(fb_val) if fb_val is not None else None,
        "race_margin_s": policy_margin_s,
        "observed_delta_t_s": sim_delta_t_s,
        "finish_status": str(fs_val) if fs_val is not None else "unverified_or_retired",
        "evidence_basis": str(row_basis),
        "verified": bool(is_verified),
        "source_ref": str(out_row.get("source_ref") or win_src or d_src or fs_src),
        "source_hash": str(out_row.get("source_hash") or ""),
        "status": str(out_row.get("status") or ("valid" if str(fs_val) in ("both_finished", "Completed") else "unverified_or_retired")),
        "field_evidence": field_evidence,
    }
    return target, sim_delta_t_s


def _validate_race_pre_context(
    rc_info: Mapping[str, Any] | None,
    policy: EvidencePolicy,
) -> tuple[bool, str, dict[str, Any]]:
    """Validates strictly causal pre-gun weather and course geometry with zero invented defaults."""
    if not isinstance(rc_info, Mapping) or not rc_info:
        return False, "missing_race_course_context", {}

    if rc_info.get("course_context_status") not in (None, "available"):
        return False, str(rc_info.get("course_unavailable_reason") or "course_context_unavailable"), {}
    if rc_info.get("prestart_context_status") not in (None, "available"):
        return False, str(rc_info.get("prestart_unavailable_reason") or "prestart_context_unavailable"), {}

    weather_record = {
        "tws_mps": rc_info.get("prestart_tws_mps"),
        "available_at_ms": rc_info.get("prestart_available_at_ms"),
        "race_gun_ms": rc_info.get("race_gun_ms"),
        "is_whole_race_average": bool(rc_info.get("prestart_is_whole_race_average", False)),
        "is_invented_default": bool(rc_info.get("prestart_is_invented_default", False)),
    }
    ok_weather, weather_reason = policy.validate_pre_race_inputs(weather_record)
    if not ok_weather:
        return False, weather_reason, {}

    twd_raw = rc_info.get("prestart_twd_deg")
    axis_raw = rc_info.get("course_axis_deg")
    leg_len_raw = rc_info.get("leg_length_m")
    leg_cnt_raw = rc_info.get("leg_count")
    if any(v is None for v in (twd_raw, axis_raw, leg_len_raw, leg_cnt_raw)):
        return False, "missing_required_course_or_wind_direction", {}

    try:
        tws_race = float(rc_info["prestart_tws_mps"])
        twd_race = float(twd_raw) % 360.0
        axis_deg = float(axis_raw) % 360.0
        leg_len = float(leg_len_raw)
        leg_cnt = int(leg_cnt_raw)
    except (TypeError, ValueError):
        return False, "invalid_course_or_wind_value", {}

    if (
        not math.isfinite(tws_race)
        or not math.isfinite(twd_race)
        or not math.isfinite(axis_deg)
        or not math.isfinite(leg_len)
        or leg_len <= 0.0
        or leg_cnt < 2
    ):
        return False, "non_finite_or_out_of_range_course_context", {}

    return (
        True,
        "valid",
        {
            "tws_mps": tws_race,
            "twd_deg": twd_race,
            "course_id": f"custom_{leg_cnt}leg_{int(round(leg_len))}m_{int(round(axis_deg))}deg",
        },
    )


def fit_and_calibrate_predictor_suite(
    outer_rows: Sequence[Mapping[str, Any]],
    inner_split: ChronologicalInnerSplit,
    *,
    maneuvers: Sequence[Mapping[str, Any]] = (),
    start_intervals: Sequence[Mapping[str, Any]] = (),
    route_templates: Sequence[LegRouteTemplate] = (),
    qualified_cal_races: Sequence[Mapping[str, Any]] = (),
    seed: int = 2027,
    neural_max_epochs: int = 60,
    neural_patience: int = 10,
    multiseed: bool = False,
    oof_residual_max_dates: int = 1,
    model_prefix: str = "eval",
) -> dict[str, Any]:
    """Chronological fit -> tune -> refit -> held-out calibrate per predictor.

    Never inspects outer-test data and never mixes residuals across predictors.
    """
    inner_split.validate_isolation()

    fit_set = set(inner_split.fit_dates)
    tune_set = set(inner_split.tune_dates)
    refit_set = set(inner_split.refit_dates)
    cal_set = set(inner_split.calibrate_dates)
    outer_set = set(inner_split.outer_train_dates)

    fit_rows = _filter_rows_by_dates(outer_rows, fit_set)
    tune_rows = _filter_rows_by_dates(outer_rows, tune_set)
    refit_rows = _filter_rows_by_dates(outer_rows, refit_set)
    cal_rows = _filter_rows_by_dates(outer_rows, cal_set)

    if not fit_rows or not tune_rows or not refit_rows or not cal_rows:
        raise ValueError("Inner chronological partitions must all be non-empty")

    refit_mans = _filter_rows_by_dates(maneuvers, refit_set)
    outer_mans = _filter_rows_by_dates(maneuvers, outer_set)
    refit_starts = _filter_rows_by_dates(start_intervals, refit_set)
    outer_starts = _filter_rows_by_dates(start_intervals, outer_set)
    refit_tpls = [
        t for t in route_templates
        if t.date_str in refit_set or t.attempt_id in refit_set
    ]
    outer_tpls = [
        t for t in route_templates
        if t.date_str in outer_set or t.attempt_id in outer_set
    ]

    # 1. Empirical polar predictor
    emp_refit = BinnedPolarBaseline()
    emp_refit.fit(refit_rows)
    emp_final = BinnedPolarBaseline()
    emp_final.fit(outer_rows)

    # 2. Regularized spline polar predictor: tune alpha on fit -> tune, refit on refit_rows, final on outer_rows
    spl_tune = RegularizedSplinePolarBaseline(alpha=1.0)
    best_alpha = float(spl_tune.fit_with_validation(fit_rows, tune_rows))
    spl_refit = RegularizedSplinePolarBaseline(alpha=best_alpha)
    spl_refit.fit(refit_rows)
    spl_final = RegularizedSplinePolarBaseline(alpha=best_alpha)
    spl_final.fit(outer_rows)

    # 3. Neural network predictor: tune on fit -> tune, refit on refit_rows, final on outer_rows
    X_fit, mean_fit, scale_fit = encode_features(fit_rows)
    y_fit = np.array([float(r.get("sog_mps", 0.0)) for r in fit_rows], dtype=np.float32)
    w_fit = _compute_race_weights(fit_rows).astype(np.float32)
    X_tune, _, _ = encode_features(tune_rows, scaler_mean=mean_fit, scaler_scale=scale_fit)
    y_tune = np.array([float(r.get("sog_mps", 0.0)) for r in tune_rows], dtype=np.float32)

    if multiseed:
        _, tune_metrics = train_ac75_neural_multiseed(
            X_fit,
            y_fit,
            X_tune,
            y_tune,
            sample_weights=w_fit,
            seeds=(2027, 2028, 2029),
            lr=0.001,
            batch_size=512,
            max_epochs=neural_max_epochs,
            patience=neural_patience,
        )
        tuned_seed = int(tune_metrics["seed"])
    else:
        _, tune_metrics = train_ac75_neural_model(
            X_fit,
            y_fit,
            X_tune,
            y_tune,
            sample_weights=w_fit,
            lr=0.001,
            batch_size=512,
            max_epochs=neural_max_epochs,
            patience=neural_patience,
            seed=seed,
        )
        tuned_seed = int(seed)
    tuned_epochs = max(1, int(tune_metrics.get("best_epoch", neural_max_epochs)))

    X_refit, mean_refit, scale_refit = encode_features(refit_rows)
    y_refit = np.array([float(r.get("sog_mps", 0.0)) for r in refit_rows], dtype=np.float32)
    w_refit = _compute_race_weights(refit_rows).astype(np.float32)
    empty_x = np.zeros((0, X_refit.shape[1]), dtype=np.float32)
    empty_y = np.zeros(0, dtype=np.float32)
    nn_refit_weights, _ = train_ac75_neural_model(
        X_refit,
        y_refit,
        empty_x,
        empty_y,
        sample_weights=w_refit,
        lr=0.001,
        batch_size=512,
        max_epochs=tuned_epochs,
        patience=tuned_epochs + 5,
        seed=tuned_seed,
    )
    nn_refit_pred_fn = make_neural_predict_fn(nn_refit_weights, mean_refit, scale_refit)

    X_full, mean_full, scale_full = encode_features(outer_rows)
    y_full = np.array([float(r.get("sog_mps", 0.0)) for r in outer_rows], dtype=np.float32)
    w_full = _compute_race_weights(outer_rows).astype(np.float32)
    nn_full_weights, full_fit_metrics = train_ac75_neural_model(
        X_full,
        y_full,
        empty_x,
        empty_y,
        sample_weights=w_full,
        lr=0.001,
        batch_size=512,
        max_epochs=tuned_epochs,
        patience=tuned_epochs + 5,
        seed=tuned_seed,
    )
    full_fit_metrics = {
        **full_fit_metrics,
        "tuned_seed": tuned_seed,
        "tuned_epochs": tuned_epochs,
        "tune_best_val_loss": tune_metrics.get("best_val_loss"),
        "training_steady_windows": len(fit_rows),
        "validation_steady_windows": len(tune_rows),
        "refit_steady_windows": len(refit_rows),
        "calibration_steady_windows": len(cal_rows),
        "total_development_windows": len(outer_rows),
    }
    nn_final_pred_fn = make_neural_predict_fn(nn_full_weights, mean_full, scale_full)

    # Fit shared non-motion context models for refit and final stages
    start_refit = StartBehaviorModel()
    if refit_starts:
        start_refit.fit(refit_starts)
    start_final = StartBehaviorModel()
    if outer_starts:
        start_final.fit(outer_starts)
    tpl_refit_lib = RouteTemplateLibrary(refit_tpls)
    tpl_final_lib = RouteTemplateLibrary(outer_tpls)

    # Out-of-sample residual samplers (chronological expanding OOF + cal_rows) and
    # held-out predictor-specific calibrations strictly on cal_rows.
    extra_oof_preds: dict[str, list[tuple[list[dict[str, Any]], Any]]] = {
        "empirical_binned_polar": [],
        "regularized_spline_polar": [],
        "neural_network_silu": [],
    }
    outer_dates = list(inner_split.outer_train_dates)
    if oof_residual_max_dates > 1 and len(outer_dates) >= 4:
        start_idx = max(2, len(outer_dates) - int(oof_residual_max_dates))
        for idx in range(start_idx, len(outer_dates)):
            d_target = outer_dates[idx]
            if d_target in cal_set:
                continue
            hist_rows = _filter_rows_by_dates(outer_rows, set(outer_dates[:idx]))
            tgt_rows = _filter_rows_by_dates(outer_rows, {d_target})
            if not hist_rows or not tgt_rows:
                continue
            emp_h = BinnedPolarBaseline()
            emp_h.fit(hist_rows)
            spl_h = RegularizedSplinePolarBaseline(alpha=best_alpha)
            spl_h.fit(hist_rows)
            X_h, mean_h, scale_h = encode_features(hist_rows)
            y_h = np.array([float(r.get("sog_mps", 0.0)) for r in hist_rows], dtype=np.float32)
            w_h = _compute_race_weights(hist_rows).astype(np.float32)
            nn_h_w, _ = train_ac75_neural_model(
                X_h,
                y_h,
                empty_x,
                empty_y,
                sample_weights=w_h,
                lr=0.001,
                batch_size=512,
                max_epochs=tuned_epochs,
                patience=tuned_epochs + 5,
                seed=tuned_seed,
            )
            nn_h_fn = make_neural_predict_fn(nn_h_w, mean_h, scale_h)
            extra_oof_preds["empirical_binned_polar"].append((tgt_rows, emp_h.predict_distribution))
            extra_oof_preds["regularized_spline_polar"].append((tgt_rows, spl_h.predict_distribution))
            extra_oof_preds["neural_network_silu"].append((tgt_rows, nn_h_fn))

    cal_races_on_date = [
        r for r in qualified_cal_races
        if str(r.get("date_str") or r.get("date") or "") in cal_set
    ]

    predictor_specs = (
        ("empirical_binned_polar", "empirical", emp_refit.predict_distribution, emp_final.predict_distribution),
        ("regularized_spline_polar", "spline", spl_refit.predict_distribution, spl_final.predict_distribution),
        ("neural_network_silu", "neural", nn_refit_pred_fn, nn_final_pred_fn),
    )

    predictors_out: dict[str, dict[str, Any]] = {}
    for c_name, mode_key, ref_pred_fn, final_pred_fn in predictor_specs:
        cal_res = PairedResidualSampler(block_duration_s=30.0)
        for tgt_rows, oof_pred_fn in extra_oof_preds[c_name]:
            cal_res.extract_from_steady_windows(tgt_rows, oof_pred_fn)
        cal_res.extract_from_steady_windows(cal_rows, ref_pred_fn)
        if cal_res.blocks:
            all_za = np.concatenate([b[0] for b in cal_res.blocks])
            all_zb = np.concatenate([b[1] for b in cal_res.blocks])
            if len(all_za) >= 10 and np.std(all_za) > 1e-4 and np.std(all_zb) > 1e-4:
                corr = float(np.corrcoef(all_za, all_zb)[0, 1])
                if np.isfinite(corr):
                    cal_res.empirical_correlation = float(np.clip(corr, -0.5, 0.9))
        cal_blocks = len(cal_res.blocks)

        man_refit = ManeuverDurationModel()
        if refit_mans:
            man_refit.fit(_predict_maneuver_entry_speeds(refit_mans, ref_pred_fn))

        man_final = ManeuverDurationModel()
        if outer_mans:
            man_final.fit(_predict_maneuver_entry_speeds(outer_mans, final_pred_fn))

        cal_model_id = f"{model_prefix}_{mode_key}"
        cal_stage1 = build_predictor_calibration(
            predictor_family=mode_key,
            model_id=cal_model_id,
            inner_split=inner_split,
            calibration_telemetry_windows=cal_rows,
            predict_dist_fn=ref_pred_fn,
            calibration_races=None,
            predict_race_fn=None,
        )

        if cal_races_on_date and len(cal_races_on_date) >= 3 and tpl_refit_lib.total_templates > 0:
            refit_bundle = InstalledModelBundle(
                model_id=cal_model_id,
                motion_weights=nn_refit_weights,
                scaler_mean=mean_refit,
                scaler_scale=scale_refit,
                template_library=tpl_refit_lib,
                maneuver_model=man_refit,
                start_model=start_refit,
                residual_sampler=cal_res,
                variance_ledger=VarianceLedger(
                    empirical_paired_block_count=cal_blocks,
                    empirical_cross_boat_correlation=round(cal_res.empirical_correlation, 4),
                ),
                selected_motion_model=mode_key,
                empirical_model=emp_refit,
                spline_model=spl_refit,
                motion_residual_scale=cal_stage1.motion_residual_scale,
                margin_interval_scale=1.0,
            )

            def _predict_cal_race(race_row: Mapping[str, Any], b: InstalledModelBundle = refit_bundle) -> np.ndarray | None:
                req = race_row.get("scenario_request")
                if not isinstance(req, Mapping):
                    return None
                req_copy = dict(req)
                req_copy["model_id"] = b.model_id
                s_res, t_res = predict_scenario(b, req_copy, return_trials=True)
                if s_res.status != "available":
                    return None
                return t_res.deltas

            cal_art = build_predictor_calibration(
                predictor_family=mode_key,
                model_id=cal_model_id,
                inner_split=inner_split,
                calibration_telemetry_windows=cal_rows,
                predict_dist_fn=ref_pred_fn,
                calibration_races=cal_races_on_date,
                predict_race_fn=_predict_cal_race,
            )
        else:
            cal_art = cal_stage1

        predictors_out[c_name] = {
            "mode_key": mode_key,
            "calibration": cal_art,
            "residual_sampler": cal_res,
            "paired_block_count": cal_blocks,
            "maneuver_model": man_final,
            "final_pred_fn": final_pred_fn,
        }

    return {
        "inner_split": inner_split,
        "empirical_model": emp_final,
        "spline_model": spl_final,
        "best_spline_alpha": best_alpha,
        "nn_weights": nn_full_weights,
        "scaler_mean": mean_full,
        "scaler_scale": scale_full,
        "neural_fit_metrics": full_fit_metrics,
        "start_model": start_final,
        "template_library": tpl_final_lib,
        "predictors": predictors_out,
        "split_counts": {
            "fit_windows": len(fit_rows),
            "tune_windows": len(tune_rows),
            "refit_windows": len(refit_rows),
            "cal_windows": len(cal_rows),
            "outer_windows": len(outer_rows),
        },
    }


def run_ac75_full_evaluation(
    steady_windows: Sequence[Mapping[str, Any]] | None = None,
    family_dates: Mapping[str, str] | None = None,
    split_manager: ChronologicalSplitManager | None = None,
    *,
    maneuvers: Sequence[Mapping[str, Any]] | None = None,
    route_templates: Sequence[LegRouteTemplate] | None = None,
    start_intervals: Sequence[Mapping[str, Any]] | None = None,
    race_courses_by_family: Mapping[str, Mapping[str, Any]] | None = None,
    outcomes_by_family: Mapping[str, Mapping[str, Any]] | None = None,
    out_dir: Path = EVAL_DIR,
    seed: int = 2027,
) -> dict[str, Any]:
    """Executes full chronological expanding evaluation across development dates."""
    out_dir.mkdir(parents=True, exist_ok=True)

    sw_path = SEALED_DIR / "steady_windows.parquet"
    if steady_windows is None:
        steady_windows = pq.read_table(sw_path).to_pylist() if sw_path.exists() else []
    if maneuvers is None:
        m_path = SEALED_DIR / "maneuvers.parquet"
        maneuvers = pq.read_table(m_path).to_pylist() if m_path.exists() else []
    if route_templates is None:
        rt_path = SEALED_DIR / "route_templates.json"
        if rt_path.exists():
            rt_lib = RouteTemplateLibrary.from_dict(json.loads(rt_path.read_text(encoding="utf-8")))
            route_templates = rt_lib._templates
        else:
            route_templates = []
    if start_intervals is None:
        si_path = SEALED_DIR / "start_intervals.json"
        if si_path.exists():
            si_raw = json.loads(si_path.read_text(encoding="utf-8"))
            start_intervals = si_raw.get("intervals", []) if isinstance(si_raw, dict) else si_raw
        else:
            start_intervals = []

    # Centralized family-based isolation (P1): strictly exclude reserved families
    tv = load_authenticated_training_view(dataset_path=sw_path if sw_path.exists() else None)
    steady_windows = filter_steady_windows(tv, steady_windows)
    maneuvers = filter_maneuvers(tv, maneuvers)
    start_intervals = filter_start_intervals(tv, start_intervals)
    route_templates = filter_route_templates(tv, route_templates)

    if race_courses_by_family is None:
        rc_path = SEALED_DIR / "race_courses_by_family.json"
        race_courses_by_family = json.loads(rc_path.read_text(encoding="utf-8")) if rc_path.exists() else {}
    if outcomes_by_family is None:
        ol_path = FORECAST_DIR / "outcome_evidence_ledger.json"
        outcomes_by_family = {}
        if ol_path.exists():
            ol_doc = json.loads(ol_path.read_text(encoding="utf-8"))
            for row in ol_doc.get("outcomes", []):
                fid = str(row.get("family_id", ""))
                if fid:
                    outcomes_by_family[fid] = row

    if family_dates is None:
        f_dates: dict[str, str] = {}
        for r in steady_windows:
            fid = str(r.get("family_id") or r.get("attempt_id") or "")
            d_str = str(r.get("date_str") or "")
            if fid and d_str:
                f_dates[fid] = d_str
        family_dates = f_dates

    if split_manager is None:
        split_manager = ChronologicalSplitManager()

    folds = split_manager.build_expanding_folds(family_dates)
    policy = EvidencePolicy()

    fold_results = []
    skipped_folds: list[dict[str, Any]] = []
    oof_speed_records: list[dict[str, Any]] = []
    oof_race_records: list[dict[str, Any]] = []
    exploratory_race_records: list[dict[str, Any]] = []
    all_primary_target_records: list[dict[str, Any]] = []
    pre_context_rejections: dict[str, int] = defaultdict(int)
    per_date_race_crps: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    per_date_speed_crps: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    candidate_race_crps: dict[str, dict[str, float]] = {c: {} for c in CANDIDATE_NAMES}
    race_dates: dict[str, str] = {}

    for fold in folds:
        outer_train_fids = set(fold.train_families) | set(fold.val_families)
        test_fids = set(fold.test_families)
        outer_train_dates = sorted(set(fold.train_dates) | set(fold.val_dates))

        outer_train_rows = [
            r for r in steady_windows
            if (r.get("family_id") or r.get("attempt_id")) in outer_train_fids
        ]
        te_rows = [
            r for r in steady_windows
            if (r.get("family_id") or r.get("attempt_id")) in test_fids
        ]

        if not outer_train_rows or not te_rows:
            skipped_folds.append({"fold_id": fold.fold_id, "reason": "empty_outer_train_or_test"})
            continue
        if len(outer_train_dates) < 3:
            skipped_folds.append({"fold_id": fold.fold_id, "reason": "insufficient_inner_chronological_dates"})
            continue

        inner_split = ChronologicalInnerSplit.from_outer_dates(outer_train_dates, fold.test_dates)
        outer_mans = [
            m for m in (maneuvers or [])
            if (m.get("family_id") or m.get("attempt_id")) in outer_train_fids
        ]
        te_mans = [
            m for m in (maneuvers or [])
            if (m.get("family_id") or m.get("attempt_id")) in test_fids
        ]
        outer_starts = [
            s for s in (start_intervals or [])
            if (s.get("family_id") or s.get("attempt_id")) in outer_train_fids
        ]
        outer_tpls = [
            t for t in (route_templates or [])
            if t.date_str in set(outer_train_dates) or t.attempt_id in outer_train_fids
        ]

        # Only pre-qualified calibration-date races (never unverified candidates) may inform margin_interval_scale
        cal_date_set = set(inner_split.calibrate_dates)
        qualified_cal_races: list[dict[str, Any]] = []
        for fid_c in sorted(outer_train_fids):
            d_c = str(family_dates.get(fid_c, ""))
            if d_c not in cal_date_set:
                continue
            out_c = (outcomes_by_family or {}).get(fid_c)
            rc_c = (race_courses_by_family or {}).get(fid_c, {})
            t_rec_c, sim_d_c = _build_race_target_record(fid_c, d_c, out_c, rc_c)
            ok_q_c, _r_q_c, _fe_c = policy.qualify_race_target(t_rec_c)
            ok_ctx_c, _r_ctx_c, parsed_ctx_c = _validate_race_pre_context(rc_c, policy)
            if ok_q_c and ok_ctx_c and sim_d_c is not None and t_rec_c["team_a"] and t_rec_c["team_b"]:
                t_rec_c["scenario_request"] = {
                    "schema_version": "kinematic-race-sim-2",
                    "model_id": f"cal_{fold.fold_id}",
                    "team_a": t_rec_c["team_a"],
                    "team_b": t_rec_c["team_b"],
                    "course_id": parsed_ctx_c["course_id"],
                    "environment": {
                        "tws_mps": parsed_ctx_c["tws_mps"],
                        "twd_deg": parsed_ctx_c["twd_deg"],
                    },
                    "purpose": "preview",
                    "scenario_policy_id": "training_observed_routes_v1",
                    "seed": seed,
                    "trial_count": 500,
                }
                qualified_cal_races.append(t_rec_c)

        try:
            suite = fit_and_calibrate_predictor_suite(
                outer_train_rows,
                inner_split,
                maneuvers=outer_mans,
                start_intervals=outer_starts,
                route_templates=outer_tpls,
                qualified_cal_races=qualified_cal_races,
                seed=seed,
                neural_max_epochs=60,
                neural_patience=10,
                multiseed=False,
                oof_residual_max_dates=4,
                model_prefix=f"eval_{fold.fold_id}",
            )
        except ValueError as err:
            skipped_folds.append({"fold_id": fold.fold_id, "reason": str(err)})
            continue

        binned_model = suite["empirical_model"]
        spline_model = suite["spline_model"]
        nn_weights = suite["nn_weights"]
        mean_tr = suite["scaler_mean"]
        scale_tr = suite["scaler_scale"]
        start_model = suite["start_model"]
        fold_tpl_lib = suite["template_library"]
        predictors = suite["predictors"]

        # Evaluate calibrated motion predictions on te_rows
        y_te = np.array([float(r.get("sog_mps", 0.0)) for r in te_rows], dtype=float)
        X_te, _, _ = encode_features(te_rows, scaler_mean=mean_tr, scaler_scale=scale_tr)

        b_scale = float(predictors["empirical_binned_polar"]["calibration"].motion_residual_scale)
        s_scale = float(predictors["regularized_spline_polar"]["calibration"].motion_residual_scale)
        n_scale = float(predictors["neural_network_silu"]["calibration"].motion_residual_scale)

        b_mu = np.zeros(len(te_rows), dtype=float)
        b_sig = np.zeros(len(te_rows), dtype=float)
        s_mu = np.zeros(len(te_rows), dtype=float)
        s_sig = np.zeros(len(te_rows), dtype=float)
        for idx, r in enumerate(te_rows):
            ml_b, ls_b = binned_model.predict_distribution(r)
            b_mu[idx], b_sig[idx] = ml_b, max(0.05, math.exp(ls_b) * b_scale)
            ml_s, ls_s = spline_model.predict_distribution(r)
            s_mu[idx], s_sig[idx] = ml_s, max(0.05, math.exp(ls_s) * s_scale)

        n_mu, n_ls = numpy_forward_pass(X_te, nn_weights)
        n_sig = np.maximum(0.05, np.exp(n_ls) * n_scale)

        scores = {
            "empirical_binned_polar": _score_motion_predictions(y_te, b_mu, b_sig),
            "regularized_spline_polar": _score_motion_predictions(y_te, s_mu, s_sig),
            "neural_network_silu": _score_motion_predictions(y_te, n_mu, n_sig),
        }
        scores["empirical_binned_polar"]["complexity_order"] = 1
        scores["regularized_spline_polar"]["complexity_order"] = 2
        scores["neural_network_silu"]["complexity_order"] = 3

        # Predictor-specific event NLL using each candidate's own maneuver & motion models
        if te_mans:
            for c_name in CANDIDATE_NAMES:
                c_info = predictors[c_name]
                enriched_te_mans = _predict_maneuver_entry_speeds(te_mans, c_info["final_pred_fn"])
                scores[c_name]["event_censored_nll"] = round(
                    c_info["maneuver_model"].score_censored_nll(enriched_te_mans), 4
                )

        # Record OOF speed predictions and per-date speed CRPS
        for idx, r in enumerate(te_rows):
            d_str = str(r.get("date_str") or (fold.test_dates[0] if fold.test_dates else "unknown"))
            y_val_sog = float(y_te[idx])
            for c_name, mu_val, sig_val in (
                ("empirical_binned_polar", float(b_mu[idx]), float(b_sig[idx])),
                ("regularized_spline_polar", float(s_mu[idx]), float(s_sig[idx])),
                ("neural_network_silu", float(n_mu[idx]), float(n_sig[idx])),
            ):
                p_sog = math.exp(mu_val + 0.5 * (sig_val ** 2))
                p_std = p_sog * math.sqrt(max(1e-6, math.exp(sig_val ** 2) - 1.0))
                per_date_speed_crps[d_str][c_name].append(normal_crps(y_val_sog, p_sog, p_std))
            oof_speed_records.append({
                "fold_id": fold.fold_id,
                "family_id": str(r.get("family_id") or r.get("attempt_id") or ""),
                "date_str": d_str,
                "team_id": str(r.get("team_id", "")),
                "t_start_ms": int(r.get("t_start_ms", 0)),
                "observed_sog_mps": round(y_val_sog, 3),
                "empirical_pred_sog_mps": round(math.exp(b_mu[idx] + 0.5 * b_sig[idx] ** 2), 3),
                "spline_pred_sog_mps": round(math.exp(s_mu[idx] + 0.5 * s_sig[idx] ** 2), 3),
                "neural_pred_sog_mps": round(math.exp(n_mu[idx] + 0.5 * n_sig[idx] ** 2), 3),
            })

        # Build calibrated bundles for each predictor independently
        fold_bundles: dict[str, InstalledModelBundle] = {}
        for c_name in CANDIDATE_NAMES:
            c_info = predictors[c_name]
            cal_art: PredictorCalibrationArtifacts = c_info["calibration"]
            cal_res: PairedResidualSampler = c_info["residual_sampler"]
            fold_bundles[c_name] = InstalledModelBundle(
                model_id=f"eval_{fold.fold_id}_{c_info['mode_key']}",
                motion_weights=nn_weights,
                scaler_mean=mean_tr,
                scaler_scale=scale_tr,
                template_library=fold_tpl_lib,
                maneuver_model=c_info["maneuver_model"],
                start_model=start_model,
                residual_sampler=cal_res,
                variance_ledger=VarianceLedger(
                    empirical_paired_block_count=c_info["paired_block_count"],
                    empirical_cross_boat_correlation=round(cal_res.empirical_correlation, 4),
                ),
                selected_motion_model=c_info["mode_key"],
                empirical_model=binned_model,
                spline_model=spline_model,
                motion_residual_scale=cal_art.motion_residual_scale,
                margin_interval_scale=cal_art.margin_interval_scale,
                calibration_info=cal_art.to_dict(),
            )

        # Evaluate end-to-end race simulation on test families under strict EvidencePolicy
        fold_race_scores: dict[str, list[dict[str, float]]] = defaultdict(list)
        for fid in sorted(test_fids):
            out_row = (outcomes_by_family or {}).get(fid)
            rc_info = (race_courses_by_family or {}).get(fid, {})
            d_str = str((out_row or {}).get("date") or family_dates.get(fid, "unknown"))
            target_record, sim_delta_t_s = _build_race_target_record(fid, d_str, out_row, rc_info)
            all_primary_target_records.append(target_record)

            is_qualified, _qual_reason, _field_evs = policy.qualify_race_target(target_record)
            ctx_ok, ctx_reason, parsed_ctx = _validate_race_pre_context(rc_info, policy)
            if not ctx_ok:
                pre_context_rejections[ctx_reason] += 1
                continue

            team_a = target_record["team_a"]
            team_b = target_record["team_b"]
            winner = target_record["winner"]
            if not team_a or not team_b or winner not in (team_a, team_b):
                continue

            y_win_a = 1 if winner == team_a else 0

            for c_name in CANDIDATE_NAMES:
                bundle = fold_bundles[c_name]
                req = {
                    "schema_version": "kinematic-race-sim-2",
                    "model_id": bundle.model_id,
                    "team_a": team_a,
                    "team_b": team_b,
                    "course_id": parsed_ctx["course_id"],
                    "environment": {"tws_mps": parsed_ctx["tws_mps"], "twd_deg": parsed_ctx["twd_deg"]},
                    "purpose": "preview",
                    "scenario_policy_id": "training_observed_routes_v1",
                    "seed": seed,
                    "trial_count": 1000,
                }
                sim_res, trial_res = predict_scenario(bundle, req, return_trials=True)
                if sim_res.status != "available" or sim_res.timing is None or sim_res.probabilities is None:
                    continue

                p_win_a = float(sim_res.probabilities.win_a)
                pred_delta = float(sim_res.timing.mean_delta_t_s)
                pred_std = float(sim_res.time_accounting.get("margin_std_s", 15.0))
                quants = sim_res.time_accounting.get("quantiles_delta_t_s", {})
                brier_v = brier_score(y_win_a, p_win_a)
                ll_v = log_loss(y_win_a, p_win_a)

                if is_qualified and sim_delta_t_s is not None:
                    m_crps = trial_res.score_empirical_margin_crps(sim_delta_t_s)
                    m_mae = abs(sim_delta_t_s - pred_delta)
                    cov_50 = 1.0 if float(quants.get("p25", -1e9)) <= sim_delta_t_s <= float(quants.get("p75", 1e9)) else 0.0
                    cov_80 = 1.0 if float(quants.get("p10", -1e9)) <= sim_delta_t_s <= float(quants.get("p90", 1e9)) else 0.0
                    cov_95 = 1.0 if float(quants.get("p025", -1e9)) <= sim_delta_t_s <= float(quants.get("p975", 1e9)) else 0.0
                    r_entry = {
                        "winner_brier": brier_v,
                        "winner_log_loss": ll_v,
                        "race_margin_crps_s": m_crps,
                        "race_margin_mae_s": m_mae,
                        "coverage_50": cov_50,
                        "coverage_80": cov_80,
                        "coverage_95": cov_95,
                    }
                    per_date_race_crps[d_str][c_name].append(m_crps)
                    candidate_race_crps[c_name][fid] = m_crps
                    race_dates[fid] = d_str
                    fold_race_scores[c_name].append(r_entry)
                    oof_race_records.append({
                        "fold_id": fold.fold_id,
                        "family_id": fid,
                        "date_str": d_str,
                        "candidate": c_name,
                        "team_a": team_a,
                        "team_b": team_b,
                        "observed_winner": winner,
                        "observed_delta_t_s": sim_delta_t_s,
                        "pred_win_a": p_win_a,
                        "pred_mean_delta_t_s": pred_delta,
                        "pred_std_delta_t_s": pred_std,
                        "winner_brier": round(brier_v, 4),
                        "race_margin_crps_s": round(m_crps, 3),
                        "verified": True,
                    })
                elif sim_delta_t_s is not None:
                    # Unverified candidate targets are strictly segregated from primary scoring/selection
                    m_crps_cand = trial_res.score_empirical_margin_crps(sim_delta_t_s)
                    exploratory_race_records.append({
                        "fold_id": fold.fold_id,
                        "family_id": fid,
                        "date_str": d_str,
                        "candidate": c_name,
                        "team_a": team_a,
                        "team_b": team_b,
                        "candidate_winner": winner,
                        "candidate_delta_t_s": sim_delta_t_s,
                        "pred_win_a": p_win_a,
                        "pred_mean_delta_t_s": pred_delta,
                        "pred_std_delta_t_s": pred_std,
                        "winner_brier_unverified": round(brier_v, 4),
                        "race_margin_crps_s_unverified": round(m_crps_cand, 3),
                        "verified": False,
                        "eligible_for_model_selection": False,
                    })

        for c_name in CANDIDATE_NAMES:
            r_list = fold_race_scores.get(c_name, [])
            if r_list:
                scores[c_name]["winner_brier"] = round(float(np.mean([x["winner_brier"] for x in r_list])), 4)
                scores[c_name]["winner_log_loss"] = round(float(np.mean([x["winner_log_loss"] for x in r_list])), 4)
                m_crps_vals = [x["race_margin_crps_s"] for x in r_list if "race_margin_crps_s" in x]
                if m_crps_vals:
                    scores[c_name]["race_margin_crps_s"] = round(float(np.mean(m_crps_vals)), 3)
                    scores[c_name]["race_margin_mae_s"] = round(float(np.mean([x["race_margin_mae_s"] for x in r_list if "race_margin_mae_s" in x])), 3)
                    scores[c_name]["coverage_50"] = round(float(np.mean([x["coverage_50"] for x in r_list if "coverage_50" in x])), 3)
                    scores[c_name]["coverage_80"] = round(float(np.mean([x["coverage_80"] for x in r_list if "coverage_80" in x])), 3)
                    scores[c_name]["coverage_95"] = round(float(np.mean([x["coverage_95"] for x in r_list if "coverage_95" in x])), 3)

        fold_results.append({
            "fold_id": fold.fold_id,
            "inner_split": inner_split.to_dict(),
            "split_counts": suite["split_counts"],
            "test_dates": fold.test_dates,
            "train_samples": suite["split_counts"]["outer_windows"],
            "test_samples": len(te_rows),
            "evaluated_qualified_races": len(fold_race_scores.get("empirical_binned_polar", [])),
            "calibrations": {
                c_name: predictors[c_name]["calibration"].to_dict()
                for c_name in CANDIDATE_NAMES
            },
            "candidate_scores": scores,
        })

    # Aggregate across all folds
    aggregated: dict[str, dict[str, float]] = {c: {} for c in CANDIDATE_NAMES}
    for c in CANDIDATE_NAMES:
        c_folds = [f["candidate_scores"][c] for f in fold_results if c in f["candidate_scores"]]
        if not c_folds:
            continue
        agg_c: dict[str, float] = {
            "sog_mae_mps": round(float(np.mean([x["sog_mae_mps"] for x in c_folds])), 3),
            "sog_rmse_mps": round(float(np.mean([x["sog_rmse_mps"] for x in c_folds])), 3),
            "log_speed_nll": round(float(np.mean([x["log_speed_nll"] for x in c_folds])), 4),
            "log_speed_crps": round(float(np.mean([x["log_speed_crps"] for x in c_folds])), 4),
            "sog_crps_mps": round(float(np.mean([x["sog_crps_mps"] for x in c_folds])), 3),
            "complexity_order": 1 if "binned" in c else (2 if "spline" in c else 3),
        }
        ev_vals = [x["event_censored_nll"] for x in c_folds if "event_censored_nll" in x]
        if ev_vals:
            agg_c["event_censored_nll"] = round(float(np.mean(ev_vals)), 4)

        race_crps_vals = [x["race_margin_crps_s"] for x in c_folds if "race_margin_crps_s" in x]
        if race_crps_vals:
            agg_c["race_margin_crps_s"] = round(float(np.mean(race_crps_vals)), 3)
            agg_c["race_margin_mae_s"] = round(float(np.mean([x["race_margin_mae_s"] for x in c_folds if "race_margin_mae_s" in x])), 3)
            agg_c["winner_brier"] = round(float(np.mean([x["winner_brier"] for x in c_folds if "winner_brier" in x])), 4)
            agg_c["winner_log_loss"] = round(float(np.mean([x["winner_log_loss"] for x in c_folds if "winner_log_loss" in x])), 4)
            agg_c["coverage_50"] = round(float(np.mean([x["coverage_50"] for x in c_folds if "coverage_50" in x])), 3)
            agg_c["coverage_80"] = round(float(np.mean([x["coverage_80"] for x in c_folds if "coverage_80" in x])), 3)
            agg_c["coverage_95"] = round(float(np.mean([x["coverage_95"] for x in c_folds if "coverage_95" in x])), 3)
            agg_c["crps"] = agg_c["race_margin_crps_s"]
            agg_c["primary_selection_crps_kind"] = "race_margin_crps_s"
        else:
            agg_c["primary_selection_crps_kind"] = "insufficient_qualified_race_targets"

        aggregated[c] = agg_c

    # Strict EvidencePolicy target qualification (rejects unverified candidate results)
    qualification_result = qualify_evaluation_targets(all_primary_target_records, policy=policy)
    qualified_race_ids = {
        str(t.get("race_id") or t.get("family_id"))
        for t in qualification_result.qualified_targets
    }

    # Summarize strictly isolated unverified candidate diagnostics without leaking into selection
    exploratory_summary: dict[str, Any] = {
        "verified": False,
        "eligible_for_model_selection": False,
        "warning": "Computed against unverified candidate_results_json targets; strictly excluded from primary selection.",
        "total_candidate_evaluations": len(exploratory_race_records),
        "candidates": {},
    }
    for c_name in CANDIDATE_NAMES:
        c_exp = [r for r in exploratory_race_records if r["candidate"] == c_name]
        if c_exp:
            exploratory_summary["candidates"][c_name] = {
                "race_count": len(c_exp),
                "mean_race_margin_crps_s_unverified": round(float(np.mean([r["race_margin_crps_s_unverified"] for r in c_exp])), 3),
                "mean_winner_brier_unverified": round(float(np.mean([r["winner_brier_unverified"] for r in c_exp])), 4),
            }

    # Primary selection rule under Work Packet P3: mean of date-level race-margin CRPS
    # comparing candidates on common qualified race IDs with candidate-specific 1-SE rule
    selection_decision = select_default_model_from_races(
        candidate_race_crps=candidate_race_crps,
        race_dates=race_dates,
        qualified_race_ids=qualified_race_ids,
        candidate_speed_scores=aggregated,
        min_eligible_dates=5,
    )
    selected_candidate = selection_decision.selected_model_id
    if selection_decision.is_fallback:
        rationale = (
            f"Retained empirical reference ({selected_candidate}) due to fallback: "
            f"{selection_decision.fallback_reason} "
            f"(qualified_targets={qualification_result.qualified_count}/{qualification_result.total_evaluated}, "
            f"eligible_dates={selection_decision.eligible_dates_count})."
        )
    else:
        rationale = (
            f"Selected '{selection_decision.selected_model_id}' (family {selection_decision.selected_model_family}) "
            f"within its own 1-SE limit ({selection_decision.paired_difference_se.get(selection_decision.selected_model_id, 0.0):.4f}) "
            f"across {selection_decision.eligible_dates_count} common eligible dates"
        )

    # Save OOF predictions parquet
    if oof_speed_records:
        oof_path = out_dir / "oof_predictions.parquet"
        pq.write_table(pa.Table.from_pylist(oof_speed_records), oof_path, compression="snappy")

    if oof_race_records:
        oof_race_path = out_dir / "oof_race_predictions.json"
        oof_race_path.write_text(json.dumps(oof_race_records, indent=2), encoding="utf-8")
    elif (out_dir / "oof_race_predictions.json").exists():
        (out_dir / "oof_race_predictions.json").unlink()

    if exploratory_race_records:
        exp_path = out_dir / "exploratory_candidate_race_diagnostics.json"
        exp_path.write_text(json.dumps(exploratory_race_records, indent=2), encoding="utf-8")

    report = {
        "schema_version": "ac75-evaluation-1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "experimental",
        "evidence_policy": policy.to_dict(),
        "target_qualification": qualification_result.to_dict(),
        "pre_race_context_rejections": dict(pre_context_rejections),
        "skipped_folds": skipped_folds,
        "total_folds_evaluated": len(fold_results),
        "total_oof_windows": len(oof_speed_records),
        "total_oof_races": len(oof_race_records) // 3 if oof_race_records else 0,
        "aggregated_scores": aggregated,
        "selection_decision": selection_decision.to_dict(),
        "per_date_paired_crps_diffs": selection_decision.paired_differences_to_best,
        "selected_candidate": selected_candidate,
        "selection_rationale": rationale,
        "exploratory_candidate_diagnostics": exploratory_summary,
        "fold_results": fold_results,
    }

    report_path = out_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    rep = run_ac75_full_evaluation()
    print(
        f"Evaluation complete: {rep['total_folds_evaluated']} folds, "
        f"selected={rep['selected_candidate']}"
    )
