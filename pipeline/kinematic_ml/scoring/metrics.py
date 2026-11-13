"""Decoupled scoring metrics and reporting engine (T15/P3).

Separately evaluates and reports:
1. Motion errors: SOG MAE/RMSE, VMG MAE/RMSE, log-speed censored NLL, SOG CRPS.
2. Event censored likelihood: maneuver censored NLL.
3. Race margin CRPS: empirical CRPS directly from unrounded simulation trials.
4. Matched-target winner metrics: Brier score, log loss.
5. Predictive interval metrics: interval width (50%, 80%) and empirical coverage (50%, 80%, 95%).
6. Explicit denominators: qualified races, evaluated races, abstained races, eligible dates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.special import log_ndtr

from pipeline.kinematic_ml.contracts import EvaluationReceipt
from .crps import brier_score, empirical_crps, log_loss, normal_crps


@dataclass(frozen=True)
class MotionMetrics:
    """Component metrics for steady-state motion prediction."""
    sog_mae_mps: float = 0.0
    sog_rmse_mps: float = 0.0
    sog_crps_mps: float = 0.0
    log_speed_nll: float = 0.0
    ground_vmg_mae_mps: float | None = None
    ground_vmg_rmse_mps: float | None = None
    wind_vmg_mae_mps: float | None = None
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventMetrics:
    """Component metrics for turn/maneuver duration prediction."""
    event_censored_nll: float = 0.0
    duration_mae_s: float | None = None
    duration_rmse_s: float | None = None
    sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RaceMetrics:
    """End-to-end race outcome and margin metrics."""
    race_margin_crps_s: float = 0.0
    race_margin_mae_s: float = 0.0
    winner_brier: float = 0.0
    winner_log_loss: float = 0.0
    interval_width_50_s: float = 0.0
    interval_width_80_s: float = 0.0
    coverage_50: float = 0.0
    coverage_80: float = 0.0
    coverage_95: float = 0.0
    race_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SupportDenominators:
    """Explicit audit counts of evaluated vs abstained units."""
    total_dates: int = 0
    eligible_dates: int = 0
    total_races: int = 0
    qualified_races: int = 0
    evaluated_races: int = 0
    abstained_races: int = 0
    abstention_reasons: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComprehensiveEvaluationReport:
    """Full decoupled evaluation report with component separation and audit lineage."""
    schema_version: str = "ac75-evaluation-report-2"
    model_id: str = ""
    candidate_family: str = "empirical"
    motion_metrics: MotionMetrics = field(default_factory=MotionMetrics)
    event_metrics: EventMetrics = field(default_factory=EventMetrics)
    race_metrics: RaceMetrics = field(default_factory=RaceMetrics)
    support_denominators: SupportDenominators = field(default_factory=SupportDenominators)
    date_breakdowns: dict[str, dict[str, float]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "candidate_family": self.candidate_family,
            "motion_metrics": self.motion_metrics.to_dict(),
            "event_metrics": self.event_metrics.to_dict(),
            "race_metrics": self.race_metrics.to_dict(),
            "support_denominators": self.support_denominators.to_dict(),
            "date_breakdowns": self.date_breakdowns,
            "metadata": self.metadata,
        }

    def to_evaluation_receipt(self, receipt_id: str = "", split_ref_id: str = "") -> EvaluationReceipt:
        """Export to frozen EvaluationReceipt interface contract."""
        all_metrics = {
            "sog_mae_mps": self.motion_metrics.sog_mae_mps,
            "sog_rmse_mps": self.motion_metrics.sog_rmse_mps,
            "sog_crps_mps": self.motion_metrics.sog_crps_mps,
            "log_speed_nll": self.motion_metrics.log_speed_nll,
            "event_censored_nll": self.event_metrics.event_censored_nll,
            "race_margin_crps_s": self.race_metrics.race_margin_crps_s,
            "race_margin_mae_s": self.race_metrics.race_margin_mae_s,
            "winner_brier": self.race_metrics.winner_brier,
            "winner_log_loss": self.race_metrics.winner_log_loss,
            "interval_width_80_s": self.race_metrics.interval_width_80_s,
            "coverage_50": self.race_metrics.coverage_50,
            "coverage_80": self.race_metrics.coverage_80,
            "coverage_95": self.race_metrics.coverage_95,
        }
        support_counts = {
            "total_dates": self.support_denominators.total_dates,
            "eligible_dates": self.support_denominators.eligible_dates,
            "total_races": self.support_denominators.total_races,
            "qualified_races": self.support_denominators.qualified_races,
            "evaluated_races": self.support_denominators.evaluated_races,
            "abstained_races": self.support_denominators.abstained_races,
        }
        return EvaluationReceipt(
            receipt_id=receipt_id,
            model_id=self.model_id,
            split_ref_id=split_ref_id,
            metrics=all_metrics,
            breakdown_by_date=self.date_breakdowns,
            support_counts=support_counts,
            status="complete" if self.race_metrics.race_count > 0 else "abstained",
        )


def censored_log_speed_nll(y_sog: float, mu_log: float, sigma_log: float, censor_mps: float = 2.0) -> float:
    """Log-speed Gaussian NLL with left-censoring at censor_mps."""
    sig = max(0.05, float(sigma_log))
    if y_sog <= censor_mps:
        z_c = (math.log(censor_mps) - mu_log) / sig
        return float(-log_ndtr(z_c))
    z = (math.log(y_sog) - mu_log) / sig
    return float(math.log(sig) + 0.5 * (z * z) + 0.5 * math.log(2.0 * math.pi))


def compute_motion_metrics(
    y_sog: Sequence[float] | np.ndarray,
    mu_log: Sequence[float] | np.ndarray,
    sigma_log: Sequence[float] | np.ndarray,
    *,
    y_ground_vmg: Sequence[float] | np.ndarray | None = None,
    pred_ground_vmg: Sequence[float] | np.ndarray | None = None,
    y_wind_vmg: Sequence[float] | np.ndarray | None = None,
    pred_wind_vmg: Sequence[float] | np.ndarray | None = None,
) -> MotionMetrics:
    """Compute decoupled motion predictions metrics."""
    y_arr = np.asarray(y_sog, dtype=float)
    mu_arr = np.asarray(mu_log, dtype=float)
    sig_arr = np.clip(np.asarray(sigma_log, dtype=float), 0.05, 2.0)
    n = len(y_arr)
    if n == 0:
        return MotionMetrics()

    pred_sog = np.exp(mu_arr + 0.5 * (sig_arr ** 2))
    pred_sog_std = pred_sog * np.sqrt(np.maximum(1e-6, np.exp(sig_arr ** 2) - 1.0))

    mae = float(np.mean(np.abs(y_arr - pred_sog)))
    rmse = float(math.sqrt(np.mean((y_arr - pred_sog) ** 2)))

    nlls = [
        censored_log_speed_nll(float(y), float(m), float(s))
        for y, m, s in zip(y_arr, mu_arr, sig_arr)
    ]
    sog_crps_vals = [
        normal_crps(float(y), float(ps), float(std_s))
        for y, ps, std_s in zip(y_arr, pred_sog, pred_sog_std)
    ]

    gvmg_mae = None
    gvmg_rmse = None
    if y_ground_vmg is not None and pred_ground_vmg is not None and len(y_ground_vmg) == n:
        gv_diff = np.asarray(y_ground_vmg, dtype=float) - np.asarray(pred_ground_vmg, dtype=float)
        gvmg_mae = round(float(np.mean(np.abs(gv_diff))), 3)
        gvmg_rmse = round(float(math.sqrt(np.mean(gv_diff ** 2))), 3)

    wvmg_mae = None
    if y_wind_vmg is not None and pred_wind_vmg is not None and len(y_wind_vmg) == n:
        wv_diff = np.asarray(y_wind_vmg, dtype=float) - np.asarray(pred_wind_vmg, dtype=float)
        wvmg_mae = round(float(np.mean(np.abs(wv_diff))), 3)

    return MotionMetrics(
        sog_mae_mps=round(mae, 3),
        sog_rmse_mps=round(rmse, 3),
        sog_crps_mps=round(float(np.mean(sog_crps_vals)), 3),
        log_speed_nll=round(float(np.mean(nlls)), 4),
        ground_vmg_mae_mps=gvmg_mae,
        ground_vmg_rmse_mps=gvmg_rmse,
        wind_vmg_mae_mps=wvmg_mae,
        sample_count=n,
    )


def compute_race_metrics(
    evaluations: Sequence[Mapping[str, Any]],
) -> RaceMetrics:
    """Compute race outcome metrics across evaluated race targets.
    
    Each evaluation record in `evaluations` should contain:
    - observed_winner: str
    - pred_win_a: float
    - team_a: str
    - observed_margin_s: float | None
    - pred_trial_deltas: Sequence[float] | None (unrounded trials for empirical CRPS)
    - pred_mean_margin_s: float | None
    - quantiles_delta_t_s: dict[str, float] | None
    """
    if not evaluations:
        return RaceMetrics()

    briers: list[float] = []
    log_losses: list[float] = []
    crps_vals: list[float] = []
    mae_vals: list[float] = []
    width_50_vals: list[float] = []
    width_80_vals: list[float] = []
    cov_50_vals: list[float] = []
    cov_80_vals: list[float] = []
    cov_95_vals: list[float] = []

    for ev in evaluations:
        obs_win = ev.get("observed_winner")
        team_a = ev.get("team_a")
        p_win_a = float(ev.get("pred_win_a", 0.5))

        if obs_win is not None and team_a is not None:
            y_win = 1 if obs_win == team_a else 0
            briers.append(brier_score(y_win, p_win_a))
            log_losses.append(log_loss(y_win, p_win_a))

        obs_margin = ev.get("observed_margin_s")
        if obs_margin is not None and math.isfinite(obs_margin):
            trial_deltas = ev.get("pred_trial_deltas")
            pred_mean = ev.get("pred_mean_margin_s")

            if trial_deltas is not None and len(trial_deltas) > 0:
                # Primary: empirical CRPS from unrounded simulation trials
                crps_v = empirical_crps(trial_deltas, obs_margin)
            elif pred_mean is not None:
                # Fallback to Gaussian CRPS if only mean and std available
                pred_std = float(ev.get("pred_std_margin_s", 15.0))
                crps_v = normal_crps(obs_margin, float(pred_mean), pred_std)
            else:
                continue

            crps_vals.append(crps_v)
            if pred_mean is not None:
                mae_vals.append(abs(obs_margin - float(pred_mean)))

            quants = ev.get("quantiles_delta_t_s") or {}
            if quants:
                p10 = float(quants.get("p10", -1e9))
                p90 = float(quants.get("p90", 1e9))
                p25 = float(quants.get("p25", -1e9))
                p75 = float(quants.get("p75", 1e9))
                p025 = float(quants.get("p025", -1e9))
                p975 = float(quants.get("p975", 1e9))

                width_50_vals.append(max(0.0, p75 - p25))
                width_80_vals.append(max(0.0, p90 - p10))

                cov_50_vals.append(1.0 if p25 <= obs_margin <= p75 else 0.0)
                cov_80_vals.append(1.0 if p10 <= obs_margin <= p90 else 0.0)
                cov_95_vals.append(1.0 if p025 <= obs_margin <= p975 else 0.0)

    return RaceMetrics(
        race_margin_crps_s=round(float(np.mean(crps_vals)), 3) if crps_vals else 0.0,
        race_margin_mae_s=round(float(np.mean(mae_vals)), 3) if mae_vals else 0.0,
        winner_brier=round(float(np.mean(briers)), 4) if briers else 0.0,
        winner_log_loss=round(float(np.mean(log_losses)), 4) if log_losses else 0.0,
        interval_width_50_s=round(float(np.mean(width_50_vals)), 2) if width_50_vals else 0.0,
        interval_width_80_s=round(float(np.mean(width_80_vals)), 2) if width_80_vals else 0.0,
        coverage_50=round(float(np.mean(cov_50_vals)), 3) if cov_50_vals else 0.0,
        coverage_80=round(float(np.mean(cov_80_vals)), 3) if cov_80_vals else 0.0,
        coverage_95=round(float(np.mean(cov_95_vals)), 3) if cov_95_vals else 0.0,
        race_count=len(crps_vals) if crps_vals else len(evaluations),
    )
