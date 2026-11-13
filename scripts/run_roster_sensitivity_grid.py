"""Evaluate full 2x3 roster sensitivity grid (pooled_entry vs event_entry x 3 policies)."""
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.prediction.build import metadata_archive
from pipeline.prediction.cup import TEAM_IDS, map_ac40_to_cup_with_covariance, simulate_cup
from pipeline.prediction.labels import race_labels, select_training_order_rows
from pipeline.prediction.models import StrengthModel


def main():
    root = Path(__file__).resolve().parent.parent
    metadata = metadata_archive(root)
    labels = [race_labels(m) for m in metadata]
    rows = select_training_order_rows(labels, target="on_water")

    modes = ["pooled_entry", "event_entry"]
    policies = ["equal", "principal_only", "assumed_10_02"]

    results = {}
    print("Evaluating 2x3 Roster Sensitivity Grid...")

    for mode in modes:
        results[mode] = {}
        model = StrengthModel.fit(rows, strength_sd=1.2, practice_weight=0.5, discrimination_scale=1.8,
                                  entry_id_mode=mode, cross_event_correlation=0.85)
        cov_matrix = np.array(model.covariance)
        entry_keys = model.boat_order

        for pol in policies:
            mean_team, sd_team, cov_team = map_ac40_to_cup_with_covariance(
                model.effects, cov_matrix, entry_keys, policy=pol, entry_id_mode=mode
            )
            sim = simulate_cup(mean_team, trials=5000, seed=2027, feasible_slot_rule_bounds=True)

            team_summary = {}
            for t in TEAM_IDS:
                team_summary[t] = {
                    "mean": round(float(mean_team.get(t, 0.0)), 4),
                    "sd": round(float(sd_team.get(t, 0.0)), 4),
                    "lower": round(float(sim["rule_bounds"][t]["lower"]), 4),
                    "upper": round(float(sim["rule_bounds"][t]["upper"]), 4),
                    "prob": round(float(sim["probabilities"][t]), 4) if sim["probabilities"].get(t) is not None else None
                }

            results[mode][pol] = {
                "unresolved_trials": sim["unresolved_trials"],
                "resolved_trials": sim["resolved_trials"],
                "teams": team_summary
            }
            print(f"  [OK] mode={mode}, policy={pol}: ETNZ mean={team_summary['ETNZ']['mean']:.4f} (sd={team_summary['ETNZ']['sd']:.4f}), bounds=[{team_summary['ETNZ']['lower']:.4f}, {team_summary['ETNZ']['upper']:.4f}]")

    qa_dir = root / ".forecast" / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    out_file = qa_dir / "roster_sensitivity_2x3.json"
    out_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote full 2x3 roster sensitivity grid to {out_file}")


if __name__ == "__main__":
    main()
