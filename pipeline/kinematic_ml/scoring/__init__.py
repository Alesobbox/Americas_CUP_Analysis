"""Scoring module for AC75 kinematic learning (T15/P3).

Exposes:
- empirical_crps: exact non-Gaussian empirical CRPS from simulation trials.
- pairwise_empirical_crps: exact O(M^2) reference implementation.
- normal_crps: Gaussian analytical reference.
- brier_score, log_loss: binary winner metrics.
- SimulationTrialResult: internal evaluation container protecting browser/LLM context.
- MotionMetrics, EventMetrics, RaceMetrics, SupportDenominators, ComprehensiveEvaluationReport.
- compute_motion_metrics, compute_race_metrics, censored_log_speed_nll.
"""
from __future__ import annotations

from .crps import (
    brier_score,
    empirical_crps,
    log_loss,
    normal_crps,
    pairwise_empirical_crps,
)
from .metrics import (
    ComprehensiveEvaluationReport,
    EventMetrics,
    MotionMetrics,
    RaceMetrics,
    SupportDenominators,
    censored_log_speed_nll,
    compute_motion_metrics,
    compute_race_metrics,
)
from .trials import SimulationTrialResult

__all__ = [
    "brier_score",
    "censored_log_speed_nll",
    "compute_motion_metrics",
    "compute_race_metrics",
    "empirical_crps",
    "log_loss",
    "normal_crps",
    "pairwise_empirical_crps",
    "ComprehensiveEvaluationReport",
    "EventMetrics",
    "MotionMetrics",
    "RaceMetrics",
    "SimulationTrialResult",
    "SupportDenominators",
]
