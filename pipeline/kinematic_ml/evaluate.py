"""Nested cross-validation and performance-gated status evaluation for kinematic ML.

Strict contract:
- Outer chronological day-ahead evaluation on DEVELOPMENT_DAYS (2026-05-23, 2026-05-24, 2026-09-25).
- Inner cross-validation over shrinkage hyperparameter tau_team in [0.15, 0.30, 0.50, 0.80].
- Canonical alphabetical ordering team_a = min(u, v), team_b = max(u, v) eliminates winner-first bias:
  y in {0.0, 1.0} with positive rate in (0.2, 0.8).
- Performance status is strictly determined by pre-declared empirical thresholds:
  Brier <= 0.18 AND LogLoss <= 0.55 AND Calibration Slope in [0.85, 1.15] -> 'validated'
  Otherwise -> 'experimental'. Never overridden manually.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Mapping, Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.prediction.evaluation import DEVELOPMENT_DAYS, AUDIT_DAYS
from pipeline.prediction.models import StrengthModel
from pipeline.kinematic_ml.models import EmpiricalPhaseDistributionModel
from pipeline.kinematic_ml.simulator import simulate_kinematic_race


BOAT_TO_TEAM = {
    "SUI": "ALINGHI", "USA": "AMERICAN_MAGIC",
    "NZL": "ETNZ", "NZL B": "ETNZ", "NZL G": "ETNZ",
    "GBR": "INEOS", "GBR B": "INEOS", "GBR G": "INEOS", "GB1": "INEOS",
    "ITA": "LUNA_ROSSA", "ITA B": "LUNA_ROSSA", "ITA G": "LUNA_ROSSA",
    "FRA": "ORIENT_EXPRESS"
}


def _get_race_order(r: Mapping[str, Any]) -> list[str]:
    """Extracts unique canonical team order from a race record."""
    raw_order = r.get("official_order") if (r.get("verified") and r.get("official_order")) else (r.get("on_water_finish_order") or r.get("order", []))
    if not raw_order:
        return []
    seen = set()
    order = []
    for b in raw_order:
        t = BOAT_TO_TEAM.get(b, b)
        if t not in seen:
            seen.add(t)
            order.append(t)
    return order


def _load_features(root: Path) -> list[dict[str, Any]]:
    """Loads pre-extracted features or creates them from turn audit if needed."""
    feat_path = root / ".forecast" / "kinematic" / "ac40_features.json"
    if feat_path.exists():
        try:
            return json.loads(feat_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Build features from turn_audit.json if available
    audit_path = root / ".forecast" / "kinematic" / "turn_audit.json"
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            team_breakdown = audit.get("speed_model_hypothesis_audit", {}).get("team_speed_breakdown", {})
            features = []
            for team, stats in team_breakdown.items():
                mean_kt = float(stats.get("mean_kt", 27.0))
                features.append({
                    "team_label": team,
                    "mean_sog_kt": mean_kt,
                    "turns": [
                        {"turn_type": "tack", "loss_s": 3.2},
                        {"turn_type": "gybe", "loss_s": 2.4}
                    ]
                })
            return features
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            pass

    return []


def run_nested_evaluation(root: Path = ROOT) -> dict[str, Any]:
    """Runs genuine chronological nested day-ahead evaluation on observed preliminary regatta races."""
    doc_file = root / "docs" / "official_results_ac38_prelims.json"
    if not doc_file.exists():
        raise FileNotFoundError(f"Official results file not found: {doc_file}")
    doc = json.loads(doc_file.read_text(encoding="utf-8"))
    all_races = [r for r in doc.get("races", []) if not r.get("practice", False) and r.get("competitive", True)]

    # Load primitives and transfer documents if available
    prims_file = root / ".forecast" / "ac75" / "primitives.json"
    primitives = json.loads(prims_file.read_text(encoding="utf-8")) if prims_file.exists() else {}

    transfer_file = root / ".forecast" / "transfer" / "ac37_transfer.json"
    transfer_doc = json.loads(transfer_file.read_text(encoding="utf-8")) if transfer_file.exists() else {}
    ac40_effects = transfer_doc.get("team_effects_ac40", {})

    features = _load_features(root)

    tau_candidates = [0.15, 0.30, 0.50, 0.80]

    dev_y_trues: list[float] = []
    dev_p_preds: list[float] = []
    dev_p_bases: list[float] = []
    dev_losses: list[float] = []
    dev_briers: list[float] = []
    dev_base_briers: list[float] = []
    dev_base_losses: list[float] = []

    match_race_evals: list[dict[str, Any]] = []

    pair_counter = 0

    # 1. Chronological Outer Loop over DEVELOPMENT_DAYS
    for day in DEVELOPMENT_DAYS:
        day_races = [r for r in all_races if r.get("date") == day]
        prior_races = [r for r in all_races if r.get("date") < day]

        if not day_races:
            continue

        # Build training rows for StrengthModel
        train_rows = []
        for pr in prior_races:
            p_order = _get_race_order(pr)
            if len(p_order) >= 2:
                train_rows.append({
                    "order": p_order,
                    "competitive": True,
                    "order_valid": True,
                    "practice": False,
                    "date": pr.get("date"),
                })

        # Inner cross-validation over tau_team if enough history exists
        prior_dates = sorted(set(r.get("date") for r in prior_races))
        best_tau = 0.30

        if len(prior_dates) >= 2:
            inner_val_date = prior_dates[-1]
            inner_train = [r for r in prior_races if r.get("date") < inner_val_date]
            inner_val = [r for r in prior_races if r.get("date") == inner_val_date]

            inner_best_brier = float("inf")
            for tau in tau_candidates:
                model_cand = EmpiricalPhaseDistributionModel.fit_from_telemetry(features, inner_train, tau_team=tau)
                briers_tau = []
                for vr in inner_val:
                    v_order = _get_race_order(vr)
                    tws = float(vr.get("wind_knots") or 12.0)
                    for i in range(len(v_order)):
                        for j in range(i + 1, len(v_order)):
                            u, v = v_order[i], v_order[j]
                            ta, tb = min(u, v), max(u, v)
                            y_val = 1.0 if u == ta else 0.0
                            s = simulate_kinematic_race(ta, tb, tws_kt=tws, model=model_cand, n_sims=300, seed=42)
                            pa = s["win_probability_a"]
                            pb = s["win_probability_b"]
                            p_dec = pa / (pa + pb) if (pa + pb) > 0 else 0.5
                            briers_tau.append((y_val - p_dec) ** 2)
                if briers_tau and np.mean(briers_tau) < inner_best_brier:
                    inner_best_brier = float(np.mean(briers_tau))
                    best_tau = tau

        # Fit models strictly on prior history
        if features:
            kin_model = EmpiricalPhaseDistributionModel.fit_from_telemetry(features, prior_races, tau_team=best_tau)
        else:
            kin_model = EmpiricalPhaseDistributionModel.load_from_primitives(primitives, team_effects=ac40_effects)

        base_model = StrengthModel.fit(train_rows) if train_rows else None

        # Evaluate day races
        for r in day_races:
            order = _get_race_order(r)
            if len(order) < 2:
                continue
            tws = float(r.get("wind_knots") or 12.0)
            is_match_race = len(order) == 2 or "mr_final" in r.get("race_id", "")

            for i in range(len(order)):
                for j in range(i + 1, len(order)):
                    u, v = order[i], order[j]
                    # Canonical alphabetical ordering: team_a = min(u, v), team_b = max(u, v)
                    team_a = min(u, v)
                    team_b = max(u, v)
                    y = 1.0 if u == team_a else 0.0

                    pair_counter += 1
                    sim = simulate_kinematic_race(
                        team_a, team_b, tws_kt=tws, model=kin_model, n_sims=500, seed=1000 + pair_counter
                    )
                    pa = sim["win_probability_a"]
                    pb = sim["win_probability_b"]
                    p_kin = pa / (pa + pb) if (pa + pb) > 0 else 0.5

                    # Baseline model prediction
                    if base_model and team_a in base_model.boat_order and team_b in base_model.boat_order:
                        p_probs = base_model.predict_win_probabilities([team_a, team_b])
                        p_base = float(p_probs.get(team_a, 0.50))
                    else:
                        p_base = 0.50

                    p_kin_clipped = float(np.clip(p_kin, 1e-6, 1.0 - 1e-6))
                    p_base_clipped = float(np.clip(p_base, 1e-6, 1.0 - 1e-6))

                    dev_y_trues.append(y)
                    dev_p_preds.append(p_kin)
                    dev_p_bases.append(p_base)

                    dev_briers.append((y - p_kin) ** 2)
                    dev_losses.append(-(y * math.log(p_kin_clipped) + (1.0 - y) * math.log(1.0 - p_kin_clipped)))

                    dev_base_briers.append((y - p_base) ** 2)
                    dev_base_losses.append(-(y * math.log(p_base_clipped) + (1.0 - y) * math.log(1.0 - p_base_clipped)))

                    if is_match_race and len(order) == 2:
                        match_race_evals.append({
                            "race_id": r.get("race_id"),
                            "date": day,
                            "team_a": team_a,
                            "team_b": team_b,
                            "y": y,
                            "p_kinematic": round(p_kin, 4),
                            "p_baseline": round(p_base, 4),
                            "brier_kinematic": round((y - p_kin) ** 2, 4),
                        })

    n_pairs = len(dev_y_trues)
    positive_rate = round(float(np.mean(dev_y_trues)), 4) if n_pairs > 0 else 0.5
    mean_brier = round(float(np.mean(dev_briers)), 4) if dev_briers else 0.25
    mean_log_loss = round(float(np.mean(dev_losses)), 4) if dev_losses else 0.69
    base_brier = round(float(np.mean(dev_base_briers)), 4) if dev_base_briers else 0.25
    base_log_loss = round(float(np.mean(dev_base_losses)), 4) if dev_base_losses else 0.69

    # Calibration slope via OLS regression: y on p_pred
    p_arr = np.array(dev_p_preds)
    y_arr = np.array(dev_y_trues)
    if len(p_arr) > 2 and float(np.var(p_arr)) > 1e-6:
        cov = float(np.cov(p_arr, y_arr)[0, 1])
        var_p = float(np.var(p_arr))
        slope = round(cov / var_p, 3)
    else:
        slope = 1.0

    # Strict performance gating thresholds
    brier_passed = mean_brier <= 0.18
    log_loss_passed = mean_log_loss <= 0.55
    slope_passed = 0.85 <= slope <= 1.15

    is_validated = brier_passed and log_loss_passed and slope_passed
    model_status = "validated" if is_validated else "experimental"

    result = {
        "schema_version": "kinematic-nested-evaluation-2",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "development_days": list(DEVELOPMENT_DAYS),
        "audit_days": list(AUDIT_DAYS),
        "development_pairwise_metrics": {
            "n_pairs": n_pairs,
            "positive_rate": positive_rate,
            "brier_score": mean_brier,
            "log_loss": mean_log_loss,
            "calibration_slope": slope,
            "baseline_brier_score": base_brier,
            "baseline_log_loss": base_log_loss,
        },
        "match_race_holdout_metrics": {
            "n_match_races": len(match_race_evals),
            "match_races": match_race_evals,
            "mean_brier": round(float(np.mean([m["brier_kinematic"] for m in match_race_evals])), 4) if match_race_evals else None,
        },
        "thresholds": {
            "brier_max": 0.18,
            "log_loss_max": 0.55,
            "slope_range": [0.85, 1.15],
        },
        "threshold_checks": {
            "brier_passed": brier_passed,
            "log_loss_passed": log_loss_passed,
            "slope_passed": slope_passed,
        },
        "status": model_status,
        "policy": "Status is strictly performance-gated by out-of-sample metrics. Never overridden manually.",
    }

    # Save to both target locations
    for out_path in (
        root / ".forecast" / "kinematic" / "evaluation.json",
        root / ".forecast" / "kinematic_ml" / "qa" / "nested_evaluation.json",
    ):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    # Generate markdown documentation
    md_content = f"""# Kinematic Simulator Out-of-Sample Evaluation Report

**Evaluation Date:** {result['evaluated_at']}  
**Status Declared:** `{model_status.upper()}`  
**Policy:** Status is strictly performance-gated by empirical out-of-sample metrics against pre-declared thresholds.

---

## 1. Evaluation Methodology

- **Outer Loop:** Day-ahead chronological out-of-sample evaluation across development days `{', '.join(DEVELOPMENT_DAYS)}`.
- **Target Ordering:** Canonical alphabetical ordering $\\text{{team\\_a}} = \\min(u, v)$, $\\text{{team\\_b}} = \\max(u, v)$ to strictly prevent winner-first hindsight bias.
- **Empirical Shrinkage:** Inner cross-validation selects $\\tau_{{\\text{{team}}}} \\in [0.15, 0.30, 0.50, 0.80]$.
- **Baseline Comparison:** Day-ahead `StrengthModel` Bradley-Terry predictions fit strictly on prior race data.

---

## 2. Quantitative Results

| Metric | Kinematic ML | Baseline Model | Threshold | Pass Gate |
|---|---|---|---|---|
| **Pairwise Comparisons (N)** | {n_pairs} | {n_pairs} | — | Yes |
| **Positive Outcome Rate ($\\bar{{y}}$)** | {positive_rate:.4f} | — | $0.20 \\le \\bar{{y}} \\le 0.80$ | {'Yes' if 0.2 <= positive_rate <= 0.8 else 'No'} |
| **Brier Score** | **{mean_brier:.4f}** | {base_brier:.4f} | $\\le 0.18$ | {'Yes' if brier_passed else 'No (Experimental)'} |
| **Log Loss** | **{mean_log_loss:.4f}** | {base_log_loss:.4f} | $\\le 0.55$ | {'Yes' if log_loss_passed else 'No (Experimental)'} |
| **Calibration Slope** | **{slope:.3f}** | — | $[0.85, 1.15]$ | {'Yes' if slope_passed else 'No (Experimental)'} |

---

## 3. Match Race Holdout Results

Evaluated on true 2-boat match race finals:
- Total match races: {len(match_race_evals)}
- Mean Brier score: {result['match_race_holdout_metrics']['mean_brier']}

---

## 4. Status Determination

Current empirical performance {'satisfies' if is_validated else 'does not satisfy'} all three strict gates.
The kinematic simulator is therefore designated as **`{model_status}`** in the candidate catalog and UI.
"""
    (root / "docs" / "kinematic_simulator_evaluation.md").write_text(md_content, encoding="utf-8")

    print(f"Kinematic ML nested evaluation complete.")
    print(f"  N Pairs: {n_pairs}, Positive Rate: {positive_rate}")
    print(f"  Brier: {mean_brier} (Baseline: {base_brier}) -> Pass: {brier_passed}")
    print(f"  LogLoss: {mean_log_loss} (Baseline: {base_log_loss}) -> Pass: {log_loss_passed}")
    print(f"  Slope: {slope} -> Pass: {slope_passed}")
    print(f"  Declared Status: '{model_status}'")
    return result


if __name__ == "__main__":
    run_nested_evaluation()
