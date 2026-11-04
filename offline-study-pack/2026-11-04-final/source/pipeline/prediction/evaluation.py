"""Preregistered chronological evaluation. Frames are never independent races."""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
import math
import numpy as np

DEVELOPMENT_DAYS = ("2026-05-23", "2026-05-24", "2026-09-25")
AUDIT_DAYS = ("2026-09-26", "2026-09-27")
GUARD_BUDGETS = {"brier": .01, "normalized_rps": .02, "normalized_mse": .02}


def scores(probabilities, winner_index, expected_positions=None, positions=None, rank_cdf=None):
    p = np.asarray(probabilities, float)
    if p.ndim != 1 or not len(p) or np.any(~np.isfinite(p)) or np.any(p < 0) or abs(p.sum()-1) > 1e-5:
        raise ValueError("Complete joint outcome probabilities required")
    if not isinstance(winner_index, (int, np.integer)) or not 0 <= winner_index < len(p):
        raise ValueError("Winner index must identify a represented joint outcome")
    y = np.eye(len(p))[winner_index]
    result = {"log_loss": -math.log(p[winner_index]) if p[winner_index] > 0 else math.inf,
              "brier": float(np.sum((p-y)**2))}
    if expected_positions is not None:
        predicted = np.asarray(expected_positions, dtype=float)
        observed = np.asarray(positions, dtype=float)
        n = predicted.size if predicted.ndim == 1 else 0
        if (predicted.ndim != 1 or n == 0 or observed.shape != predicted.shape
                or len(p) not in (n, n+1) or np.any(~np.isfinite(predicted))
                or np.any(~np.isfinite(observed)) or np.any((predicted < 1) | (predicted > n))
                or np.any((observed < 1) | (observed > n)) or np.any(observed != np.floor(observed))):
            raise ValueError("Rank targets require finite field-sized positions in [1,N]")
        result["normalized_mse"] = float(np.mean(((predicted-observed)/(n-1))**2)) if n > 1 else 0.
        if rank_cdf is not None:
            cdf = np.asarray(rank_cdf, dtype=float)
            if (cdf.shape != (n, n-1) or np.any(~np.isfinite(cdf))
                    or np.any((cdf < 0) | (cdf > 1)) or np.any(np.diff(cdf, axis=1) < -1e-12)):
                raise ValueError("Rank CDF must be monotone [0,1] at thresholds 1..N-1")
            thresholds = np.arange(1,n)
            truth = observed[:,None] <= thresholds[None,:]
            result["normalized_rps"] = float(np.mean(np.sum((cdf-truth)**2,axis=1)/(n-1))) if n > 1 else 0.
    elif rank_cdf is not None or positions is not None:
        raise ValueError("Rank evaluation requires predicted and observed positions")
    return result


def aggregate(rows):
    """First average checkpoints within a race, then race-equal or day-equal."""
    races = defaultdict(list)
    for row in rows:
        races[(row["date"], row["race_id"])].append(row)
    keys = sorted(set().union(*(r.keys() for r in rows)) - {"date", "race_id", "checkpoint"}) if rows else []
    per_race = [{"date": date, "race_id": rid,
                 **{k: float(np.mean([r[k] for r in values if k in r])) for k in keys if any(k in r for r in values)}}
                for (date,rid), values in races.items()]
    per_day = defaultdict(list)
    for row in per_race:
        per_day[row["date"]].append(row)
    race_equal = {k: float(np.mean([r[k] for r in per_race if k in r])) for k in keys if any(k in r for r in per_race)}
    day_equal = {k: float(np.mean([np.mean([r[k] for r in values if k in r])
                                  for values in per_day.values() if any(k in r for r in values)])) for k in race_equal}
    # Compute sensitivity directly from race summaries; recursive deletion
    # would grow factorially when additional independent days accumulate.
    sensitivity = {day: {k: float(np.mean([r[k] for r in per_race if r["date"] != day and k in r]))
                         for k in keys if any(r["date"] != day and k in r for r in per_race)}
                   for day in per_day} if len(per_day) > 1 else {}
    def signature(metric=None):
        identities = sorted([str(row["date"]), str(row["race_id"]), str(row.get("checkpoint", "pre_race"))]
                            for row in rows if metric is None or metric in row)
        return hashlib.sha256(json.dumps(identities, separators=(",", ":")).encode()).hexdigest()
    return {"race_equal": race_equal, "day_equal": day_equal, "race_count": len(races),
            "independent_days": len(per_day), "leave_one_day": sensitivity,
            "race_keys": [list(key) for key in sorted(races)],
            "coverage_signature": signature(),
            "metric_coverage_signatures": {k: signature(k) for k in keys},
            "per_race": per_race,
            "per_day": [{"date": day, **{k: float(np.mean([r[k] for r in values if k in r]))
                         for k in keys if any(k in r for r in values)}} for day, values in sorted(per_day.items())]}


def _paired_coverage(candidate, reference):
    if not candidate.get("independent_days") or not reference.get("independent_days"):
        return "No eligible chronological evidence"
    if (not candidate.get("coverage_signature") or not reference.get("coverage_signature")
            or candidate["coverage_signature"] != reference["coverage_signature"]
            or candidate.get("race_keys") != reference.get("race_keys")):
        return "Candidate/reference must use identical paired races and checkpoints"
    return None


def guardrails(candidate, reference, *, applicable=("brier", "normalized_rps", "normalized_mse")):
    """Paired practical loss budgets without requiring a primary gain.

    Used separately for pre-race ranks when a shared strength/dynamics model
    changes. Missing applicable metrics are a failed gate, never a skipped test.
    """
    reason = _paired_coverage(candidate, reference)
    if reason:
        return {"passed": False, "reason": reason, "checks": {}}
    if any(key not in GUARD_BUDGETS for key in applicable):
        raise ValueError("Unknown practical guardrail metric")
    checks = {}
    for averaging in ("race_equal", "day_equal"):
        c, r = candidate.get(averaging, {}), reference.get(averaging, {})
        for key in applicable:
            matched = (candidate.get("metric_coverage_signatures", {}).get(key)
                       == reference.get("metric_coverage_signatures", {}).get(key)
                       == candidate.get("coverage_signature"))
            checks[averaging+":"+key] = bool(key in c and key in r and matched
                and math.isfinite(c[key]) and math.isfinite(r[key])
                and c[key]-r[key] <= GUARD_BUDGETS[key] + 1e-12)
    return {"passed": all(checks.values()), "checks": checks,
            "status": "provisional_low_evidence", "guard_budgets": GUARD_BUDGETS}


def promotion(candidate, reference, *, applicable=("brier", "normalized_rps", "normalized_mse")):
    """Operational budgets, never a small-sample significance claim."""
    budgets = guardrails(candidate, reference, applicable=applicable)
    if "reason" in budgets:
        return {"promoted": False, "reason": budgets["reason"], "checks": budgets["checks"]}
    checks = dict(budgets["checks"])
    for averaging in ("race_equal", "day_equal"):
        c, r = candidate.get(averaging, {}), reference.get(averaging, {})
        matched = (candidate.get("metric_coverage_signatures", {}).get("log_loss")
                   == reference.get("metric_coverage_signatures", {}).get("log_loss")
                   == candidate.get("coverage_signature"))
        checks[averaging] = bool(matched and math.isfinite(c.get("log_loss", math.inf))
                                  and math.isfinite(r.get("log_loss", math.inf))
                                  and c.get("log_loss", math.inf) < r.get("log_loss", math.inf))
    return {"promoted": all(checks.values()), "checks": checks,
            "status": "provisional_low_evidence", "guard_budgets": GUARD_BUDGETS}
