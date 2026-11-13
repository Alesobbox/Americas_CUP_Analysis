"""Evaluate condition_effects on DEVELOPMENT_DAYS without leaking audit split."""
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.prediction.build import prepare
from pipeline.prediction.evaluation import AUDIT_DAYS, DEVELOPMENT_DAYS, aggregate, scores
from pipeline.prediction.labels import attach_official_results, before_day, select_training_order_rows
from pipeline.prediction.models import StrengthModel


def compute_order_log_loss(model: StrengthModel, order: list[str], wind_knots: float | None = None) -> float:
    """Compute Plackett-Luce full order negative log-likelihood."""
    if len(order) < 2:
        return 0.0
    total_nll = 0.0
    for k in range(len(order) - 1):
        rem = order[k:]
        probs = model.predict_win_probabilities(rem, wind_knots=wind_knots)
        p_winner = probs.get(rem[0], 1.0 / len(rem))
        total_nll += -math.log(max(p_winner, 1e-9))
    return float(total_nll)


def evaluate_split(labels: list[dict], split_days: tuple[str, ...], condition_effects: bool) -> list[dict]:
    eval_rows = []
    for day in split_days:
        train_raw = before_day(labels, day)
        train_rows = select_training_order_rows(train_raw, prefer_official=True)
        if len(train_rows) < 2:
            continue
        try:
            model = StrengthModel.fit(train_rows, condition_effects=condition_effects)
        except Exception:
            continue

        day_races = [
            r for r in labels
            if r.get("date") == day and r.get("competitive", True) and len(r.get("order", [])) >= 2
        ]
        for r in day_races:
            order = r["official_order"] if r.get("official_order_verified") and r.get("official_order") else r["order"]
            if len(order) < 2:
                continue
            wind = float(r["wind_knots"]) if (condition_effects and r.get("wind_knots") is not None) else None
            probs_map = model.predict_win_probabilities(order, wind_knots=wind)
            prob_arr = np.array([probs_map.get(b, 0.0) for b in order], dtype=float)
            s_arr = prob_arr.sum()
            if s_arr > 0:
                prob_arr /= s_arr
            else:
                prob_arr = np.ones(len(order)) / len(order)

            sc = scores(prob_arr, 0)
            full_nll = compute_order_log_loss(model, order, wind_knots=wind)
            sc["full_order_log_loss"] = full_nll
            sc["race_id"] = r["race_id"]
            sc["date"] = r["date"]
            eval_rows.append(sc)

    return eval_rows


def run_wind_experiment(root: Path = ROOT) -> dict[str, Any]:
    _, labels_list, _, _ = prepare(root)
    labels, _ = attach_official_results(labels_list, root / "docs" / "official_results_ac38_prelims.json")

    results: dict[str, Any] = {
        "schema_version": "wind-experiment-2",
        "description": "Chronological evaluation of condition_effects on development days with zero audit leak.",
        "splits": {},
    }

    for split_name, split_days in [("development", DEVELOPMENT_DAYS), ("audit", AUDIT_DAYS)]:
        base_rows = evaluate_split(labels, split_days, condition_effects=False)
        wind_rows = evaluate_split(labels, split_days, condition_effects=True)

        base_agg = aggregate(base_rows) if base_rows else {}
        wind_agg = aggregate(wind_rows) if wind_rows else {}

        base_brier = base_agg.get("race_equal", {}).get("brier", None)
        wind_brier = wind_agg.get("race_equal", {}).get("brier", None)
        base_log_loss = base_agg.get("race_equal", {}).get("log_loss", None)
        wind_log_loss = wind_agg.get("race_equal", {}).get("log_loss", None)
        base_full_loss = base_agg.get("race_equal", {}).get("full_order_log_loss", None)
        wind_full_loss = wind_agg.get("race_equal", {}).get("full_order_log_loss", None)

        brier_diff = round(wind_brier - base_brier, 6) if (wind_brier is not None and base_brier is not None) else None
        loss_diff = round(wind_log_loss - base_log_loss, 6) if (wind_log_loss is not None and base_log_loss is not None) else None

        results["splits"][split_name] = {
            "days": list(split_days),
            "sample_count": len(base_rows),
            "baseline": {
                "brier_mean": base_brier,
                "log_loss_mean": base_log_loss,
                "full_order_log_loss_mean": base_full_loss,
            },
            "wind_conditioned": {
                "brier_mean": wind_brier,
                "log_loss_mean": wind_log_loss,
                "full_order_log_loss_mean": wind_full_loss,
            },
            "delta_wind_minus_base": {
                "brier": brier_diff,
                "log_loss": loss_diff,
            },
        }

    dev = results["splits"]["development"]
    dev_base = dev["baseline"]
    dev_wind = dev["wind_conditioned"]
    wind_improves_both = (
        dev_wind["brier_mean"] is not None
        and dev_base["brier_mean"] is not None
        and dev_wind["full_order_log_loss_mean"] is not None
        and dev_base["full_order_log_loss_mean"] is not None
        and dev_wind["brier_mean"] < dev_base["brier_mean"]
        and dev_wind["full_order_log_loss_mean"] < dev_base["full_order_log_loss_mean"]
    )
    results["wind_improves_both_development_metrics"] = wind_improves_both
    results["recommendation"] = "retain_wind_effects" if wind_improves_both else "keep_baseline_unconditioned"

    out_dir = root / ".forecast" / "wind_experiment"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "evaluation.json"
    out_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote wind experiment evaluation to {out_file}")
    return results


if __name__ == "__main__":
    res = run_wind_experiment()
    print("Development baseline Brier:", res["splits"]["development"]["baseline"]["brier_mean"])
    print("Development wind Brier:    ", res["splits"]["development"]["wind_conditioned"]["brier_mean"])
    print("Recommendation:            ", res["recommendation"])
