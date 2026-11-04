#!/usr/bin/env python3
"""
Executable Example 03 — Plackett-Luce Expected Rank, Tied-N Identity & AC38 Cup Bounds
======================================================================================
Data Provenance:
  - PART A uses SYNTHETIC 3-BOAT & 2-BOAT EXAMPLES to prove:
      1. The Tied-N Expected Rank Sum Identity vs Standard Permutation Rank Sum K(K+1)/2.
      2. Persistent vs Independent Ability Draws in a First-to-7 Cup Match (75.00% vs 93.76%).
  - PART B uses ACTUAL REPOSITORY EVIDENCE from `evidence/cup_2027.json` and
    `evidence/scheduled_entry_ledger.json` to verify the 227-entry ledger and the
    34.46% RRSAC 102.1 unresolved interval width across all 7 AC38 teams.

Requires: Python 3.10+ standard library only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "evidence"


def analytic_pl_expected_ranks_with_tied_n(
    gammas: list[float], p_complete: list[float]
) -> tuple[list[float], float]:
    """
    Exact enumeration over all 2^K completion subsets S, using the analytic Plackett-Luce
    conditional expected rank formula E[R_i | S] = 1 + sum_{j in S, j != i} gamma_j / (gamma_i + gamma_j)
    for finishers i in S, and rank K for non-finishers i not in S (pipeline/prediction/simulation.py).
    """
    k = len(gammas)
    expected_ranks = [0.0] * k
    excess_sum_from_formula = 0.0

    for mask in range(1 << k):
        prob_s = 1.0
        finishers = []
        for i in range(k):
            if (mask >> i) & 1:
                prob_s *= p_complete[i]
                finishers.append(i)
            else:
                prob_s *= 1.0 - p_complete[i]

        m = len(finishers)
        if m <= k - 2:
            excess_sum_from_formula += prob_s * ((k - m) * (k - m - 1) / 2.0)

        for i in range(k):
            if (mask >> i) & 1:
                cond_rank = 1.0 + sum(
                    gammas[j] / (gammas[i] + gammas[j]) for j in finishers if j != i
                )
            else:
                cond_rank = float(k)  # Tied-N nonfinish convention
            expected_ranks[i] += prob_s * cond_rank

    return expected_ranks, excess_sum_from_formula


def first_to_7_win_prob_given_p(p: float) -> float:
    """Negative binomial probability that Team A reaches 7 wins before Team B reaches 7 wins."""
    total = 0.0
    for b_wins in range(7):
        total += math.comb(6 + b_wins, b_wins) * (p ** 7) * ((1.0 - p) ** b_wins)
    return total


def main() -> None:
    print("=" * 78)
    print("EXECUTABLE EXAMPLE 03: PLACKETT-LUCE, TIED-N SUM & AC38 CUP RULE BOUNDS")
    print("=" * 78)

    # PART A.1: Synthetic 3-boat Tied-N Rank Sum Identity
    gammas = [3.0, 2.0, 1.0]
    p_comp = [0.90, 0.85, 0.75]
    k = len(gammas)
    exp_ranks, excess = analytic_pl_expected_ranks_with_tied_n(gammas, p_comp)
    base_sum = k * (k + 1) / 2.0

    print("\n[PART A.1 — SYNTHETIC 3-BOAT TIED-N EXPECTED RANK SUM IDENTITY]")
    for i, r in enumerate(exp_ranks, 1):
        print(f"  Boat {i} (gamma={gammas[i-1]:.1f}, p_comp={p_comp[i-1]:.2f}) -> E[R_{i}] = {r:.6f}")
    print(f"  Standard permutation sum K(K+1)/2 : {base_sum:.6f}")
    print(f"  Theoretical tied-N excess         : +{excess:.6f}")
    print(f"  Sum of expected ranks             : {sum(exp_ranks):.6f}")
    assert abs(sum(exp_ranks) - (base_sum + excess)) < 1e-12

    # PART A.2: Persistent vs Independent Ability Draws in a First-to-7 Series
    # (docs/forecasting_implementation.md:L122-L123)
    # Under a 50/50 mixture of latent single-race win probability p in {0.50, 0.90}:
    # - Persistent tournament draw: 0.5 * P(series | p=0.50) + 0.5 * P(series | p=0.90) = 75.00%
    # - Independent per-race draws: marginal p_bar = 0.5*(0.50 + 0.90) = 0.70 -> P(series | p=0.70) = 93.76%
    series_persistent = 0.5 * first_to_7_win_prob_given_p(0.50) + 0.5 * first_to_7_win_prob_given_p(0.90)
    series_independent = first_to_7_win_prob_given_p(0.70)
    print("\n[PART A.2 — PERSISTENT VS INDEPENDENT SERIES WIN PROBABILITY (FIRST-TO-7)]")
    print(f"  50/50 mix of latent p in {{0.50, 0.90}} — Persistent ability draw : {series_persistent*100:.2f}%")
    print(f"  50/50 mix of latent p in {{0.50, 0.90}} — Independent draws (p=0.7): {series_independent*100:.2f}%")
    assert round(series_persistent * 100, 2) == 75.00
    assert round(series_independent * 100, 2) == 93.76

    # PART B: Actual Repository Evidence (scheduled_entry_ledger.json & cup_2027.json)
    entries = json.loads((EVIDENCE_DIR / "scheduled_entry_ledger.json").read_text(encoding="utf-8"))
    cup = json.loads((EVIDENCE_DIR / "cup_2027.json").read_text(encoding="utf-8"))

    completed_count = sum(1 for e in entries if e["completed"])
    no_telemetry = [e for e in entries if not e["has_telemetry"]]

    print("\n[PART B — ACTUAL REPOSITORY EVIDENCE: 227-ENTRY LEDGER & CUP_2027.JSON]")
    print(f"  Total scheduled boat-races in ledger : {len(entries)} (Completed: {completed_count}, Rate: {completed_count/len(entries)*100:.2f}%)")
    print(f"  Scheduled entries with 0 telemetry   : {len(no_telemetry)} -> {[ (e['race_id'], e['entry_id']) for e in no_telemetry ]}")
    assert len(entries) == 227 and completed_count == 169 and len(no_telemetry) == 3

    base_id = cup["scenario_analysis"]["baseline_scenario_id"]
    base_rec = next(r for r in cup["scenario_analysis"]["records"] if r["scenario_id"] == base_id)
    n_trials = base_rec["trials"]
    unresolved = base_rec["unresolved_trials"]
    resolved = base_rec["resolved_trials"]
    u_frac = unresolved / n_trials

    print(f"\n  AC38 Baseline Scenario ({base_id}):")
    print(f"    Trials = {n_trials}, Resolved = {resolved} ({resolved/n_trials*100:.2f}%), Unresolved = {unresolved} ({u_frac*100:.2f}%)")
    print(f"    Headline point probabilities: {cup['probabilities']}")
    assert all(v is None for v in cup["probabilities"].values())

    lower_sum = 0.0
    upper_sum = 0.0
    for team_id, bounds in cup["rule_bounds_by_team"].items():
        width = bounds["upper"] - bounds["lower"]
        lower_sum += bounds["lower"]
        upper_sum += bounds["upper"]
        print(
            f"    {team_id:14s} | Baseline Bounds: [{bounds['lower']*100:6.2f}%, {bounds['upper']*100:6.2f}%] "
            f"(Width = {width*100:.2f} pp) | 9-Scenario Envelope: "
            f"[{cup['scenario_envelope_by_team'][team_id]['lower']*100:5.2f}%, "
            f"{cup['scenario_envelope_by_team'][team_id]['upper']*100:5.2f}%]"
        )
        assert abs(width - u_frac) < 1e-12

    print(f"    Sum of lower bounds = {lower_sum:.4f} (equals 1 - u = {1.0 - u_frac:.4f})")
    print(f"    Sum of upper bounds = {upper_sum:.4f} (equals 1 + 6u = {1.0 + 6.0 * u_frac:.4f})")
    assert abs(lower_sum - (1.0 - u_frac)) < 1e-12
    assert abs(upper_sum - (1.0 + 6.0 * u_frac)) < 1e-12
    print("\nAll assertions passed successfully.")


if __name__ == "__main__":
    main()
