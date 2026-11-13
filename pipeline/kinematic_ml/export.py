"""Export kinematic ML simulation candidate bundles to .forecast/kinematic_ml/candidates/."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.kinematic_ml.simulator import simulate_kinematic_race
from pipeline.kinematic_ml.course_lvc import COURSE_PRESETS, BARCELONA_2024_LVC


def export_kinematic_bundle(root: Path = ROOT, n_sims: int = 2000, seed: int = 2027) -> dict:
    """Pre-computes and stages an experimental kinematic simulation bundle."""
    # Load empirical primitives if available
    prims_file = root / ".forecast" / "ac75" / "primitives.json"
    primitives = json.loads(prims_file.read_text(encoding="utf-8")) if prims_file.exists() else {}

    # Load nested evaluation status
    eval_file = root / ".forecast" / "kinematic_ml" / "qa" / "nested_evaluation.json"
    eval_doc = json.loads(eval_file.read_text(encoding="utf-8")) if eval_file.exists() else {}
    model_status = eval_doc.get("status", "experimental")

    # Load empirical transfer team effects
    transfer_file = root / ".forecast" / "transfer" / "ac37_transfer.json"
    transfer_doc = json.loads(transfer_file.read_text(encoding="utf-8")) if transfer_file.exists() else {}
    team_effects = transfer_doc.get("team_effects_ac75", {})

    wind_speeds = [8.5, 11.5, 14.5, 17.5]
    top_teams = ["ETNZ", "GB1", "LUNA_ROSSA", "ALINGHI", "LA_ROCHE_POSAY", "ARC_USA", "AUSTRALIA"]
    key_matchups = [
        ("ETNZ", "GB1"),
        ("ETNZ", "LUNA_ROSSA"),
        ("GB1", "LUNA_ROSSA"),
        ("LUNA_ROSSA", "ALINGHI"),
        ("ETNZ", "LA_ROCHE_POSAY"),
        ("GB1", "ARC_USA"),
        ("LUNA_ROSSA", "AUSTRALIA")
    ]

    scenarios = []
    # 1. Mode: Pure Empirical Barcelona 2024 AC75
    for ta, tb in key_matchups:
        for tws in wind_speeds:
            sim = simulate_kinematic_race(ta, tb, tws_kt=tws, n_sims=n_sims, seed=seed, team_effects=team_effects)
            sim["mode"] = "barcelona_2024_empirical"
            sim["course"] = asdict(BARCELONA_2024_LVC)
            scenarios.append(sim)

    # 2. Mode: Empirical with AC38 Rule Adjustments (Battery power adjustment + cyclors)
    # Under AC38 rules, cyclors provide increased hydraulic reservoir pressure (+0.25 kt upwind)
    adjusted_effects = {k: v + 0.15 for k, v in team_effects.items()}
    for ta, tb in key_matchups:
        for tws in wind_speeds:
            sim = simulate_kinematic_race(ta, tb, tws_kt=tws, n_sims=n_sims, seed=seed + 1, team_effects=adjusted_effects)
            sim["mode"] = "barcelona_2024_empirical_with_ac38_rules"
            sim["course"] = asdict(BARCELONA_2024_LVC)
            sim["rule_adjustments"] = {
                "cyclor_power_boost_kt": 0.25,
                "maneuver_loss_multiplier": 0.95,
                "foil_span_limit_factor": 1.05
            }
            scenarios.append(sim)

    bundle_meta = {
        "schema_version": "kinematic-bundle-1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_status": model_status,
        "status_notice": (
            "Status: Experimental. Out-of-sample Brier and LogLoss currently exceed strict validation gates. "
            "Displayed strictly as an exploratory tactical simulation tool; not an official calibrated forecast."
        ),
        "total_scenarios": len(scenarios),
        "available_teams": top_teams,
        "available_modes": [
            {
                "id": "barcelona_2024_empirical",
                "label": "Empirical Barcelona 2024 AC75",
                "description": "Direct telemetry-derived speed and maneuver profiles from Barcelona 2024 AC75 racing."
            },
            {
                "id": "barcelona_2024_empirical_with_ac38_rules",
                "label": "Empirical + AC38 Rule Adjustments",
                "description": "Barcelona 2024 base with explicit, parameterized adjustments for AC38 Class Rule v3.05 (cyclor power, foil span)."
            }
        ],
        "default_sliders": {
            "battery_power_offset_kt": {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.1, "unit": "kt"},
            "maneuver_loss_multiplier": {"default": 1.0, "min": 0.8, "max": 1.2, "step": 0.05, "unit": "x"},
            "foil_span_factor": {"default": 1.0, "min": 0.95, "max": 1.10, "step": 0.01, "unit": "x"}
        },
        "courses": [asdict(c) for c in COURSE_PRESETS.values()],
        "scenarios": scenarios
    }

    # Hash canonical content
    raw_bytes = json.dumps(bundle_meta, sort_keys=True, separators=(",", ":")).encode("utf-8")
    bundle_hash = hashlib.sha256(raw_bytes).hexdigest()

    candidates_dir = root / ".forecast" / "kinematic_ml" / "candidates" / bundle_hash
    candidates_dir.mkdir(parents=True, exist_ok=True)
    
    catalog_file = candidates_dir / "catalog.json"
    catalog_file.write_text(json.dumps(bundle_meta, indent=2) + "\n", encoding="utf-8")

    pointer_file = root / ".forecast" / "kinematic_ml" / "latest_candidate.json"
    pointer = {
        "bundle_hash": bundle_hash,
        "candidate_path": str(catalog_file.relative_to(root)).replace("\\", "/"),
        "created_at": bundle_meta["created_at"],
        "model_status": model_status
    }
    pointer_file.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")

    print(f"Kinematic ML bundle staged successfully at: {catalog_file}")
    print(f"  Bundle Hash: {bundle_hash}")
    print(f"  Status: {model_status}")
    print(f"  Total Scenarios: {len(scenarios)}")
    return pointer


if __name__ == "__main__":
    export_kinematic_bundle()
