"""Internal simulation trial container (T15/P3).

Preserves unrounded trial arrays for evaluation and CRPS computation,
while explicitly preventing raw trial arrays from leaking into browser
payloads or LLM context summaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping

import numpy as np

from pipeline.kinematic_ml.contracts import (
    ScenarioProbabilityDetail,
    ScenarioTimingDetail,
    ScenarioV2Result,
)
from .crps import empirical_crps


@dataclass
class SimulationTrialResult:
    """Internal evaluation container holding unrounded simulation trials.
    
    Attributes:
        scenario_id: Canonical scenario identifier.
        model_id: Installed model identifier.
        team_a: Competitor A identifier.
        team_b: Competitor B identifier.
        trial_count: Number of simulated trials.
        deltas: Raw unrounded margin trials (T_B - T_A) in seconds.
        times_a: Raw unrounded total time trials for team A in seconds.
        times_b: Raw unrounded total time trials for team B in seconds.
        wins_a: Fractional or binary win indicator per trial.
        both_finished: Boolean mask for trials where both boats finished.
        straights_a: Optional straight-line durations for boat A.
        straights_b: Optional straight-line durations for boat B.
        maneuvers_a: Optional maneuver durations for boat A.
        maneuvers_b: Optional maneuver durations for boat B.
        starts_a: Optional start delay trials for boat A.
        starts_b: Optional start delay trials for boat B.
    """
    scenario_id: str
    model_id: str
    team_a: str
    team_b: str
    trial_count: int
    deltas: np.ndarray
    times_a: np.ndarray
    times_b: np.ndarray
    wins_a: np.ndarray
    both_finished: np.ndarray
    straights_a: np.ndarray | None = None
    straights_b: np.ndarray | None = None
    maneuvers_a: np.ndarray | None = None
    maneuvers_b: np.ndarray | None = None
    starts_a: np.ndarray | None = None
    starts_b: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def score_empirical_margin_crps(self, observed_margin_s: float) -> float:
        """Compute empirical margin CRPS directly from unrounded simulation trials."""
        return empirical_crps(self.deltas, observed_margin_s)

    def compute_summary_statistics(self) -> dict[str, Any]:
        """Compute summary statistics for evaluation without returning raw arrays."""
        n_trials = len(self.deltas)
        if n_trials == 0:
            return {}

        mean_delta = float(np.mean(self.deltas))
        std_delta = float(np.std(self.deltas))
        se_delta = float(std_delta / math.sqrt(n_trials))

        p_win_a = float(np.mean(self.wins_a))
        p_win_b = 1.0 - p_win_a
        prob_mc_se = float(math.sqrt(max(0.0, p_win_a * (1.0 - p_win_a)) / n_trials))

        quantiles = [2.5, 5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 97.5]
        q_vals = [float(v) for v in np.percentile(self.deltas, quantiles)]
        q_dict = {
            "p025": round(q_vals[0], 2),
            "p05": round(q_vals[1], 2),
            "p10": round(q_vals[2], 2),
            "p25": round(q_vals[3], 2),
            "p50": round(q_vals[4], 2),
            "p75": round(q_vals[5], 2),
            "p90": round(q_vals[6], 2),
            "p95": round(q_vals[7], 2),
            "p975": round(q_vals[8], 2),
        }

        return {
            "scenario_id": self.scenario_id,
            "model_id": self.model_id,
            "team_a": self.team_a,
            "team_b": self.team_b,
            "trial_count": n_trials,
            "win_a": round(p_win_a, 4),
            "win_b": round(p_win_b, 4),
            "prob_mc_error": round(prob_mc_se, 4),
            "mean_delta_t_s": round(mean_delta, 2),
            "std_delta_t_s": round(std_delta, 3),
            "se_delta_t_s": round(se_delta, 4),
            "central_80_interval_s": (q_dict["p10"], q_dict["p90"]),
            "quantiles_delta_t_s": q_dict,
        }

    def to_scenario_v2_result(
        self,
        applied_inputs: Mapping[str, Any],
        *,
        status: str = "available",
        probability_scope: str = "completion_assumed_on_water",
        reason_codes: list[str] | None = None,
    ) -> ScenarioV2Result:
        """Convert internal trials to public ScenarioV2Result, omitting raw arrays."""
        summary = self.compute_summary_statistics()
        if not summary or status != "available":
            return ScenarioV2Result(
                scenario_id=self.scenario_id,
                model_id=self.model_id,
                status=status,
                probability_scope=probability_scope,
                applied_inputs=dict(applied_inputs),
                probabilities=None,
                timing=None,
                reason_codes=reason_codes or ["simulation_unavailable"],
                trial_counts={"scheduled": self.trial_count, "completed": 0, "unresolved": self.trial_count},
            )

        mean_time_a = float(np.mean(self.times_a))
        mean_time_b = float(np.mean(self.times_b))
        p10 = summary["quantiles_delta_t_s"]["p10"]
        p90 = summary["quantiles_delta_t_s"]["p90"]

        timing_detail = ScenarioTimingDetail(
            mean_time_a_s=round(mean_time_a, 2),
            mean_time_b_s=round(mean_time_b, 2),
            mean_delta_t_s=summary["mean_delta_t_s"],
            central_80_margin_interval_s=(p10, p90),
        )

        prob_detail = ScenarioProbabilityDetail(
            win_a=summary["win_a"],
            win_b=summary["win_b"],
            no_winner=None,
            mc_error=summary["prob_mc_error"],
        )

        time_accounting = {
            "total_mean_delta_s": summary["mean_delta_t_s"],
            "margin_mc_se_s": summary["se_delta_t_s"],
            "margin_std_s": summary["std_delta_t_s"],
            "quantiles_delta_t_s": summary["quantiles_delta_t_s"],
        }
        if self.straights_a is not None and self.straights_b is not None:
            time_accounting["straight_delta_s"] = round(float(np.mean(self.straights_b - self.straights_a)), 2)
        if self.maneuvers_a is not None and self.maneuvers_b is not None:
            time_accounting["maneuver_delta_s"] = round(float(np.mean(self.maneuvers_b - self.maneuvers_a)), 2)
        if self.starts_a is not None and self.starts_b is not None:
            time_accounting["start_delta_s"] = round(float(np.mean(self.starts_b - self.starts_a)), 2)

        return ScenarioV2Result(
            scenario_id=self.scenario_id,
            model_id=self.model_id,
            status="available",
            probability_scope=probability_scope,
            applied_inputs=dict(applied_inputs),
            timing=timing_detail,
            probabilities=prob_detail,
            time_accounting=time_accounting,
            trial_counts={
                "scheduled": self.trial_count,
                "completed": len(self.deltas),
                "unresolved": 0,
            },
        )
