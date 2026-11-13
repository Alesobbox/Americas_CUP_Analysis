"""Frozen default-model selection rule under G3.6 and Work Packet P3.

Enforces:
1. Primary metric is mean of date-level race-margin CRPS (averaging races within each date),
   comparing candidates on common qualified race IDs.
2. Candidate-specific paired candidate-minus-best differences by date with standard error:
   SE = std(ddof=1) / sqrt(number_of_dates).
3. With >= 5 eligible dates, choose the simplest candidate within its own 1-SE limit:
   hierarchy: empirical (1) -> spline (2) -> neural (3).
4. With < 5 dates or no qualified targets, retain empirical experimental reference with
   explicit fallback reason: 'insufficient_eligible_dates' or 'insufficient_qualified_race_targets'.
5. Removes fixed 0.05 and maximum-across-candidates SE fallbacks.
6. Decouples speed ranking from race-margin ranking so speed differences never corrupt selection.
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np

from pipeline.kinematic_ml.contracts import SelectionDecision

HIERARCHY_ORDER = ("empirical", "spline", "neural")

CANONICAL_MODEL_IDS = {
    "empirical": "empirical_binned_polar",
    "spline": "regularized_spline_polar",
    "neural": "neural_network_silu",
}


def resolve_candidate_family(candidate_name: str) -> str:
    """Resolve a candidate name or identifier to its canonical model family."""
    name_clean = str(candidate_name).strip().lower()
    if "empirical" in name_clean or "binned" in name_clean:
        return "empirical"
    if "spline" in name_clean:
        return "spline"
    if "neural" in name_clean or "silu" in name_clean or "mlp" in name_clean:
        return "neural"
    return name_clean


def select_default_model_from_races(
    candidate_race_crps: Mapping[str, Mapping[str, float]],
    race_dates: Mapping[str, str],
    *,
    qualified_race_ids: Sequence[str] | set[str] | None = None,
    candidate_speed_scores: Mapping[str, Mapping[str, float]] | None = None,
    min_eligible_dates: int = 5,
    model_ids: Mapping[str, str] | None = None,
) -> SelectionDecision:
    """Select default model using race-level CRPS aggregated to date-level on common qualified races.
    
    Args:
        candidate_race_crps: candidate_id -> {race_id: race_margin_crps_s}
        race_dates: race_id -> date_str
        qualified_race_ids: set of qualified race IDs (from evidence policy). If None, all races with dates are used.
        candidate_speed_scores: optional mapping of candidate_id -> speed metrics (recorded for audit, never overrides margin CRPS).
        min_eligible_dates: minimum common eligible dates required (default: 5).
        model_ids: mapping of family -> concrete model_id string.
    """
    candidate_keys = list(candidate_race_crps.keys())
    effective_model_ids = dict(CANONICAL_MODEL_IDS)
    if model_ids:
        effective_model_ids.update(model_ids)

    # 1. Zero qualified targets check
    if qualified_race_ids is not None and len(qualified_race_ids) == 0:
        return SelectionDecision(
            selected_model_id=effective_model_ids.get("empirical", "empirical_binned_polar"),
            selected_model_family="empirical",
            eligible_dates_count=0,
            qualified_targets_count=0,
            min_eligible_dates=min_eligible_dates,
            is_fallback=True,
            fallback_reason="insufficient_qualified_race_targets",
        )

    if not candidate_keys:
        return SelectionDecision(
            selected_model_id=effective_model_ids.get("empirical", "empirical_binned_polar"),
            selected_model_family="empirical",
            eligible_dates_count=0,
            qualified_targets_count=0,
            min_eligible_dates=min_eligible_dates,
            is_fallback=True,
            fallback_reason="insufficient_qualified_race_targets",
        )

    # 2. Find common qualified race IDs across all candidates
    candidate_races = [set(candidate_race_crps[c].keys()) for c in candidate_keys]
    common_races = set.intersection(*candidate_races) if candidate_races else set()
    if qualified_race_ids is not None:
        common_races = common_races.intersection(set(qualified_race_ids))

    if not common_races:
        return SelectionDecision(
            selected_model_id=effective_model_ids.get("empirical", "empirical_binned_polar"),
            selected_model_family="empirical",
            eligible_dates_count=0,
            qualified_targets_count=0,
            min_eligible_dates=min_eligible_dates,
            is_fallback=True,
            fallback_reason="insufficient_qualified_race_targets",
        )

    # 3. Aggregate race-margin CRPS to date level (averaging races within each date)
    date_to_races: dict[str, list[str]] = {}
    for r in sorted(common_races):
        d = race_dates.get(r)
        if d:
            date_to_races.setdefault(d, []).append(r)

    candidate_crps_by_date: dict[str, dict[str, float]] = {c: {} for c in candidate_keys}
    for c in candidate_keys:
        for d, r_list in date_to_races.items():
            vals = [candidate_race_crps[c][r] for r in r_list if r in candidate_race_crps[c]]
            if vals:
                candidate_crps_by_date[c][d] = float(np.mean(vals))

    return select_default_model_from_date_crps(
        candidate_crps_by_date,
        qualified_targets_count=len(common_races),
        min_eligible_dates=min_eligible_dates,
        model_ids=effective_model_ids,
    )


def select_default_model_from_date_crps(
    candidate_crps_by_date: Mapping[str, Mapping[str, float]],
    *,
    qualified_targets_count: int | None = None,
    min_eligible_dates: int = 5,
    model_ids: Mapping[str, str] | None = None,
) -> SelectionDecision:
    """Select default model using date-level race-margin CRPS.
    
    Primary metric: mean of date-level race-margin CRPS.
    Compares candidates on common qualified dates.
    Calculates candidate-specific paired candidate-minus-best differences by date with SE:
      SE = std(ddof=1) / sqrt(n_dates).
    Chooses simplest candidate within its own 1-SE limit (empirical -> spline -> neural).
    With < 5 dates or no qualified targets, retains empirical with explicit fallback.
    """
    effective_model_ids = dict(CANONICAL_MODEL_IDS)
    if model_ids:
        effective_model_ids.update(model_ids)

    candidate_keys = list(candidate_crps_by_date.keys())
    if not candidate_keys:
        return SelectionDecision(
            selected_model_id=effective_model_ids.get("empirical", "empirical_binned_polar"),
            selected_model_family="empirical",
            is_fallback=True,
            fallback_reason="insufficient_qualified_race_targets",
        )

    # Intersection of dates common to all candidates
    date_sets = [set(candidate_crps_by_date[c].keys()) for c in candidate_keys]
    common_dates = sorted(set.intersection(*date_sets) if date_sets else set())
    n_dates = len(common_dates)

    target_count = qualified_targets_count if qualified_targets_count is not None else n_dates

    # Fallback 1: zero qualified targets
    if target_count == 0:
        return SelectionDecision(
            selected_model_id=effective_model_ids.get("empirical", "empirical_binned_polar"),
            selected_model_family="empirical",
            eligible_dates_count=n_dates,
            qualified_targets_count=0,
            min_eligible_dates=min_eligible_dates,
            is_fallback=True,
            fallback_reason="insufficient_qualified_race_targets",
        )

    # Fallback 2: fewer than min_eligible_dates (5)
    if n_dates < min_eligible_dates:
        return SelectionDecision(
            selected_model_id=effective_model_ids.get("empirical", "empirical_binned_polar"),
            selected_model_family="empirical",
            eligible_dates_count=n_dates,
            qualified_targets_count=target_count,
            min_eligible_dates=min_eligible_dates,
            is_fallback=True,
            fallback_reason="insufficient_eligible_dates",
        )

    # 1. Compute candidate mean date-level CRPS and unpaired SE for reporting
    means: dict[str, float] = {}
    ses: dict[str, float] = {}
    by_date_dict: dict[str, dict[str, float]] = {}

    for c in candidate_keys:
        vals = [float(candidate_crps_by_date[c][d]) for d in common_dates]
        by_date_dict[c] = {d: float(candidate_crps_by_date[c][d]) for d in common_dates}
        m = float(np.mean(vals))
        means[c] = round(m, 4)
        se = float(np.std(vals, ddof=1) / math.sqrt(n_dates)) if n_dates > 1 else 0.0
        ses[c] = round(se, 4)

    # 2. Identify the best candidate (lowest mean date-level CRPS)
    best_cand = min(candidate_keys, key=lambda c: means[c])

    # 3. Calculate candidate-specific paired candidate-minus-best differences by date
    paired_diffs: dict[str, list[float]] = {}
    paired_means: dict[str, float] = {}
    paired_ses: dict[str, float] = {}

    for c in candidate_keys:
        diffs = [
            float(candidate_crps_by_date[c][d] - candidate_crps_by_date[best_cand][d])
            for d in common_dates
        ]
        paired_diffs[c] = [round(v, 4) for v in diffs]
        p_m = float(np.mean(diffs))
        paired_means[c] = round(p_m, 4)
        # Candidate-specific paired SE: std(ddof=1) / sqrt(n_dates)
        if n_dates > 1:
            p_se = float(np.std(diffs, ddof=1) / math.sqrt(n_dates))
        else:
            p_se = 0.0
        paired_ses[c] = round(p_se, 4)

    # 4. Map candidate keys to canonical families
    cand_by_family: dict[str, str] = {}
    for c in candidate_keys:
        fam = resolve_candidate_family(c)
        cand_by_family[fam] = c

    # 5. Apply the candidate-specific 1-SE rule along the simplicity hierarchy:
    # Hierarchy: empirical (1) -> spline (2) -> neural (3)
    # A candidate qualifies if its mean paired difference to best is <= its OWN paired SE:
    #   paired_mean[c] <= paired_se[c]  (i.e. mean[c] <= mean[best] + paired_se[c])
    selected_cand = best_cand
    for fam in HIERARCHY_ORDER:
        if fam in cand_by_family:
            c_name = cand_by_family[fam]
            # Check if this candidate is within its own 1-SE limit of the best candidate
            if paired_means[c_name] <= paired_ses[c_name] + 1e-9:
                selected_cand = c_name
                break

    selected_family = resolve_candidate_family(selected_cand)
    selected_model_id = effective_model_ids.get(selected_family, selected_cand)

    return SelectionDecision(
        schema_version="ac75-selection-decision-1",
        rule_name="mean_date_crps_1se_rule",
        selected_model_id=selected_model_id,
        selected_model_family=selected_family,
        candidate_mean_crps=means,
        candidate_se=ses,
        candidate_crps_by_date=by_date_dict,
        paired_differences_to_best=paired_diffs,
        paired_difference_mean=paired_means,
        paired_difference_se=paired_ses,
        eligible_dates_count=n_dates,
        qualified_targets_count=target_count,
        min_eligible_dates=min_eligible_dates,
        is_fallback=False,
        fallback_reason="",
        hierarchy_order=HIERARCHY_ORDER,
    )
