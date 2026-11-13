"""Export immutable AC75 learned simulation candidate bundles and exact caches (T16).

Contract (G4, T16):
- Trains on the real sealed AC37 telemetry development dataset (zero synthetic training shortcuts).
- Trains across frozen seeds (2027, 2028, 2029) with race-equal sample weights.
- Exports neural (.pt, .npz, .json), baseline, maneuver, start, route template, and paired residual artifacts.
- Content-addresses candidate_id from artifact SHA-256 digests.
- All scenarios generated exclusively through predict_scenario.
- Stages unified catalog envelope into .forecast/ac75_learning/candidates/<candidate_id>/.
- Updates atomic latest_candidate.json pointer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

# Prevent Windows MKL / OpenMP runtime collision
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import numpy as np
import pyarrow.parquet as pq

from pipeline.kinematic_ml.baselines import (
    BinnedPolarBaseline,
    RegularizedSplinePolarBaseline,
)
from pipeline.kinematic_ml.calibration import ChronologicalInnerSplit, PredictorCalibrationArtifacts
from pipeline.kinematic_ml.config import compute_config_hash, load_config
from pipeline.kinematic_ml.evaluate_ac75 import (
    _build_race_target_record,
    _validate_race_pre_context,
    fit_and_calibrate_predictor_suite,
    run_ac75_full_evaluation,
)
from pipeline.kinematic_ml.evidence.policy import EvidencePolicy
from pipeline.kinematic_ml.training_view import (
    filter_maneuvers,
    filter_route_templates,
    filter_start_intervals,
    filter_steady_windows,
    load_authenticated_training_view,
)
from pipeline.kinematic_ml.events import (
    ManeuverDurationModel,
    StartBehaviorModel,
)
from pipeline.kinematic_ml.inference import (
    CANONICAL_TEAMS,
    COURSE_PRESETS,
    predict_scenario,
)
from pipeline.kinematic_ml.neural import export_neural_bundle
from pipeline.kinematic_ml.routes import RouteTemplateLibrary
from pipeline.kinematic_ml.uncertainty import (
    PairedResidualSampler,
    VarianceLedger,
)

from pipeline.kinematic_ml.loader import (
    load_authenticated_bundle,
    load_staged_ac75_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
SEALED_DIR = FORECAST_DIR / "sealed"
EVAL_DIR = FORECAST_DIR / "evaluation"
CANDIDATES_DIR = FORECAST_DIR / "candidates"
LATEST_POINTER_PATH = FORECAST_DIR / "latest_candidate.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_numerical_code_hashes(root: Path) -> dict[str, str]:
    """Compute deterministic SHA-256 digests of core owning numerical modules."""
    files = [
        "contracts.py",
        "baselines.py",
        "neural.py",
        "events.py",
        "routes.py",
        "uncertainty.py",
        "inference.py",
        "course_lvc.py",
    ]
    hashes = {}
    pkg_dir = root / "pipeline" / "kinematic_ml"
    for f in sorted(files):
        p = pkg_dir / f
        if p.exists():
            hashes[f] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def compute_installed_model_identity(
    selected_predictor: str,
    artifact_hashes: Mapping[str, str],
    config_hash: str,
    contracts_version: str,
    dataset_manifest_hash: str,
    split_registry_hash: str,
    code_hashes: Mapping[str, str],
) -> str:
    """Compute content-addressed installed model identity.
    
    Includes selected predictor, fitted components, config and numerical-contract versions,
    lineage, and code hashes, while strictly excluding timestamps, absolute paths,
    unrelated UI changes, and the model ID itself.
    """
    hasher = hashlib.sha256()
    identity_dict = {
        "selected_predictor": str(selected_predictor),
        "contracts_version": str(contracts_version),
        "config_hash": str(config_hash),
        "dataset_manifest_hash": str(dataset_manifest_hash),
        "split_registry_hash": str(split_registry_hash),
        "artifact_hashes": {
            k: artifact_hashes[k]
            for k in sorted(artifact_hashes.keys())
            if not k.endswith("catalog") and not k.endswith("catalog_sha256")
        },
        "code_hashes": {k: code_hashes[k] for k in sorted(code_hashes.keys())},
    }
    serialized = json.dumps(identity_dict, sort_keys=True, separators=(",", ":"))
    hasher.update(serialized.encode("utf-8"))
    return f"ac75_{hasher.hexdigest()[:12]}"



def export_ac75_learned_bundle(
    root: Path = ROOT,
    *,
    seed: int = 2027,
) -> dict[str, Any]:
    """Trains on real sealed AC75 telemetry, exports immutable candidate bundle, and updates pointer."""
    forecast_dir = root / ".forecast" / "ac75_learning"
    sealed_dir = forecast_dir / "sealed"
    eval_dir = forecast_dir / "evaluation"
    candidates_dir = forecast_dir / "candidates"
    latest_pointer_path = forecast_dir / "latest_pointer.json" if False else (forecast_dir / "latest_candidate.json")

    sw_path = sealed_dir / "steady_windows.parquet"
    man_path = sealed_dir / "maneuvers.parquet"
    rt_path = sealed_dir / "route_templates.json"
    si_path = sealed_dir / "start_intervals.json"
    sm_path = sealed_dir / "sealed_dataset_manifest.json"

    if not sw_path.exists() or not rt_path.exists():
        raise FileNotFoundError(
            f"Sealed dataset artifacts missing in {sealed_dir}. Run `python -m pipeline.kinematic_ml.features` first."
        )

    steady_windows = pq.read_table(sw_path).to_pylist()
    maneuvers = pq.read_table(man_path).to_pylist() if man_path.exists() else []
    template_lib = RouteTemplateLibrary.from_dict(
        json.loads(rt_path.read_text(encoding="utf-8"))
    )
    si_raw = (
        json.loads(si_path.read_text(encoding="utf-8")) if si_path.exists() else {}
    )
    start_intervals = (
        si_raw.get("intervals", []) if isinstance(si_raw, dict) else si_raw
    )
    sealed_manifest = (
        json.loads(sm_path.read_text(encoding="utf-8")) if sm_path.exists() else {}
    )
    # Centralized family-based isolation (P1): strictly exclude reserved families
    tv = load_authenticated_training_view(dataset_path=sw_path)
    dev_windows = filter_steady_windows(tv, steady_windows)
    dev_maneuvers = filter_maneuvers(tv, maneuvers)
    dev_starts = filter_start_intervals(tv, start_intervals)
    dev_routes = filter_route_templates(tv, template_lib._templates)
    template_lib = RouteTemplateLibrary(dev_routes)

    if len(dev_windows) != 13550:
        raise ValueError(
            f"Gate B violation: Expected exactly 13,550 development steady windows, got {len(dev_windows)}"
        )

    # Recompute or verify chronological evaluation report with explicit EvidencePolicy
    eval_report_path = eval_dir / "evaluation_report.json"
    eval_report: dict[str, Any] | None = None
    if eval_report_path.exists():
        try:
            cand_rep = json.loads(eval_report_path.read_text(encoding="utf-8"))
            if "evidence_policy" in cand_rep and "target_qualification" in cand_rep:
                eval_report = cand_rep
        except Exception:
            eval_report = None

    if eval_report is None:
        eval_report = run_ac75_full_evaluation(
            steady_windows=dev_windows,
            maneuvers=dev_maneuvers,
            route_templates=template_lib._templates,
            start_intervals=dev_starts,
            out_dir=eval_dir,
            seed=seed,
        )

    selection_decision = eval_report.get("selection_decision", {}) if isinstance(eval_report, dict) else {}
    target_qual = eval_report.get("target_qualification", {}) if isinstance(eval_report, dict) else {}
    selected_cand_name = str(eval_report.get("selected_candidate", "empirical_binned_polar"))

    # Chronological inner split on development dates for held-out calibration
    dev_dates = sorted({str(r.get("date_str", "")) for r in dev_windows if r.get("date_str")})
    inner_split = ChronologicalInnerSplit.from_outer_dates(dev_dates)

    # Qualify calibration-date races strictly under EvidencePolicy
    policy = EvidencePolicy()
    rc_path = sealed_dir / "race_courses_by_family.json"
    race_courses_by_family = json.loads(rc_path.read_text(encoding="utf-8")) if rc_path.exists() else {}
    ol_path = forecast_dir / "outcome_evidence_ledger.json"
    outcomes_by_family: dict[str, dict[str, Any]] = {}
    if ol_path.exists():
        ol_doc = json.loads(ol_path.read_text(encoding="utf-8"))
        for row in ol_doc.get("outcomes", []):
            fid = str(row.get("family_id", ""))
            if fid:
                outcomes_by_family[fid] = row

    cal_date_set = set(inner_split.calibrate_dates)
    qualified_cal_races: list[dict[str, Any]] = []
    cal_fids = sorted({str(r.get("family_id") or r.get("attempt_id") or "") for r in dev_windows if str(r.get("date_str") or "") in cal_date_set})
    for fid_c in cal_fids:
        if not fid_c:
            continue
        out_c = outcomes_by_family.get(fid_c)
        rc_c = race_courses_by_family.get(fid_c, {})
        d_c = str((out_c or {}).get("date") or rc_c.get("date_str") or "")
        if d_c not in cal_date_set:
            continue
        t_rec_c, sim_d_c = _build_race_target_record(fid_c, d_c, out_c, rc_c)
        ok_q_c, _rq, _fe = policy.qualify_race_target(t_rec_c)
        ok_ctx_c, _rc, parsed_ctx_c = _validate_race_pre_context(rc_c, policy)
        if ok_q_c and ok_ctx_c and sim_d_c is not None and t_rec_c["team_a"] and t_rec_c["team_b"]:
            t_rec_c["scenario_request"] = {
                "schema_version": "kinematic-race-sim-2",
                "model_id": "export_cal_probe",
                "team_a": t_rec_c["team_a"],
                "team_b": t_rec_c["team_b"],
                "course_id": parsed_ctx_c["course_id"],
                "environment": {
                    "tws_mps": parsed_ctx_c["tws_mps"],
                    "twd_deg": parsed_ctx_c["twd_deg"],
                },
                "purpose": "preview",
                "scenario_policy_id": "training_observed_routes_v1",
                "seed": seed,
                "trial_count": 500,
            }
            qualified_cal_races.append(t_rec_c)

    # Fit & chronologically calibrate all three candidates cleanly (no in-sample spline contamination)
    suite = fit_and_calibrate_predictor_suite(
        dev_windows,
        inner_split,
        maneuvers=dev_maneuvers,
        start_intervals=dev_starts,
        route_templates=template_lib._templates,
        qualified_cal_races=qualified_cal_races,
        seed=seed,
        neural_max_epochs=100,
        neural_patience=15,
        multiseed=True,
        oof_residual_max_dates=12,
        model_prefix="export_ac75",
    )

    empirical_model: BinnedPolarBaseline = suite["empirical_model"]
    spline_model: RegularizedSplinePolarBaseline = suite["spline_model"]
    weights = suite["nn_weights"]
    scaler_mean = suite["scaler_mean"]
    scaler_scale = suite["scaler_scale"]
    fit_metrics = suite["neural_fit_metrics"]
    start_model: StartBehaviorModel = suite["start_model"]

    predictors = suite["predictors"]
    if selected_cand_name not in predictors:
        selected_cand_name = "empirical_binned_polar"
    sel_info = predictors[selected_cand_name]
    selected_mode = sel_info["mode_key"]
    cal_art: PredictorCalibrationArtifacts = sel_info["calibration"]
    residual_sampler: PairedResidualSampler = sel_info["residual_sampler"]
    paired_blocks_count = int(sel_info["paired_block_count"])
    maneuver_model: ManeuverDurationModel = sel_info["maneuver_model"]

    variance_ledger = VarianceLedger(
        empirical_paired_block_count=paired_blocks_count,
        empirical_cross_boat_correlation=round(residual_sampler.empirical_correlation, 4),
    )

    # Stage artifacts in temporary directory first to compute content-addressed candidate_id
    staging_dir = candidates_dir / "_staging_tmp"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    npz_prefix = staging_dir / "model_weights"
    export_meta = export_neural_bundle(weights, scaler_mean, scaler_scale, npz_prefix)

    emp_path = staging_dir / "empirical_polar.json"
    emp_path.write_text(json.dumps(empirical_model.to_dict(), indent=2), encoding="utf-8")

    spl_path = staging_dir / "spline_polar.json"
    spl_path.write_text(json.dumps(spline_model.to_dict(), indent=2), encoding="utf-8")

    man_json_path = staging_dir / "maneuver_model.json"
    man_json_path.write_text(json.dumps(maneuver_model.to_dict(), indent=2), encoding="utf-8")

    start_json_path = staging_dir / "start_model.json"
    start_json_path.write_text(json.dumps(start_model.to_dict(), indent=2), encoding="utf-8")

    rt_out_path = staging_dir / "route_templates.json"
    rt_out_path.write_text(json.dumps(template_lib.to_dict(), indent=2), encoding="utf-8")

    res_npz_path = staging_dir / "residual_blocks.npz"
    residual_sampler.save_npz(res_npz_path)

    cfg = load_config()
    cfg_hash = compute_config_hash(cfg)

    code_hashes = compute_numerical_code_hashes(root)
    split_reg_hash = tv.registry_hash
    sealed_manifest_hash = _sha256_file(sm_path) if sm_path.exists() else ""
    eval_report_hash = _sha256_file(eval_report_path) if eval_report_path.exists() else ""

    fitted_hashes = {
        "weights_npz": export_meta["npz_sha256"],
        "weights_pt": export_meta["pt_sha256"],
        "model_json": export_meta["json_sha256"],
        "empirical_polar_json": _sha256_file(emp_path),
        "spline_polar_json": _sha256_file(spl_path),
        "maneuver_model_json": _sha256_file(man_json_path),
        "start_model_json": _sha256_file(start_json_path),
        "route_templates_json": _sha256_file(rt_out_path),
        "residual_blocks_npz": _sha256_file(res_npz_path),
        "calibration_sha256": hashlib.sha256(
            json.dumps(cal_art.to_dict(), sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }

    candidate_id = compute_installed_model_identity(
        selected_predictor=selected_cand_name,
        artifact_hashes=fitted_hashes,
        config_hash=cfg_hash,
        contracts_version="ac75-model-1",
        dataset_manifest_hash=sealed_manifest_hash,
        split_registry_hash=split_reg_hash or eval_report_hash,
        code_hashes=code_hashes,
    )

    target_dir = candidates_dir / candidate_id
    if target_dir.exists():
        shutil.rmtree(target_dir)
    staging_dir.rename(target_dir)

    # Remove old synthetic ac75_learned_v1 directory if present
    legacy_synth_dir = candidates_dir / "ac75_learned_v1"
    if legacy_synth_dir.exists() and legacy_synth_dir != target_dir:
        shutil.rmtree(legacy_synth_dir)

    # Re-point paths inside target_dir
    npz_path = target_dir / "model_weights.npz"
    pt_path = target_dir / "model_weights.pt"
    json_path = target_dir / "model_weights.json"
    emp_path = target_dir / "empirical_polar.json"
    spl_path = target_dir / "spline_polar.json"
    man_json_path = target_dir / "maneuver_model.json"
    start_json_path = target_dir / "start_model.json"
    rt_out_path = target_dir / "route_templates.json"
    res_npz_path = target_dir / "residual_blocks.npz"
    catalog_path = target_dir / "scenarios_catalog.json"

    initial_catalog = {
        "schema_version": "ac75-catalog-2",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_id": candidate_id,
        "model_status": "experimental",
        "selected_motion_candidate": selected_cand_name,
        "status_notice": "Generating authentic catalog scenarios...",
        "total_scenarios": 0,
        "available_teams": list(CANONICAL_TEAMS),
        "available_modes": [
            {"id": "ac75_learned_v2", "label": "AC75 Learned Simulator (v2)", "description": ""},
        ],
        "default_sliders": {},
        "courses": list(COURSE_PRESETS.values()),
        "scenarios": [],
    }
    catalog_path.write_text(json.dumps(initial_catalog, indent=2), encoding="utf-8")
    initial_cat_hash = _sha256_file(catalog_path)

    manifest_file = target_dir / "candidate_manifest.json"
    manifest_doc = {
        "schema_version": "ac75-model-1",
        "candidate_id": candidate_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "experimental",
        "selected_motion_candidate": selected_cand_name,
        "selected_motion_mode": selected_mode,
        "calibration": cal_art.to_dict(),
        "calibrations_all_predictors": {
            k: v["calibration"].to_dict() for k, v in predictors.items()
        },
        "inner_split": inner_split.to_dict(),
        "selection_decision": selection_decision,
        "target_qualification_summary": {
            "status": target_qual.get("status"),
            "qualified_count": target_qual.get("qualified_count", 0),
            "total_evaluated": target_qual.get("total_evaluated", 0),
            "rejection_reasons": target_qual.get("rejection_reasons", {}),
        },
        "config_sha256": cfg_hash,
        "sealed_dataset_manifest_sha256": sealed_manifest_hash,
        "evaluation_report_sha256": eval_report_hash,
        "code_hashes": code_hashes,
        "status_notice": "",
        "fit_metrics": fit_metrics,
        "maneuver_model_summary": {
            "fitted_turn_count": maneuver_model.fitted_turn_count,
            "censored_turn_count": maneuver_model.censored_turn_count,
            "intercept_tack": round(maneuver_model.intercept_tack, 4),
            "intercept_gybe": round(maneuver_model.intercept_gybe, 4),
            "sigma": round(maneuver_model.sigma, 4),
        },
        "route_template_count": template_lib.total_templates,
        "paired_residual_block_count": paired_blocks_count,
        "artifacts": {
            "weights_pt": str(pt_path.relative_to(root)).replace("\\", "/"),
            "weights_pt_sha256": export_meta["pt_sha256"],
            "weights_npz": str(npz_path.relative_to(root)).replace("\\", "/"),
            "weights_npz_sha256": export_meta["npz_sha256"],
            "model_json": str(json_path.relative_to(root)).replace("\\", "/"),
            "model_json_sha256": export_meta["json_sha256"],
            "empirical_polar_json": str(emp_path.relative_to(root)).replace("\\", "/"),
            "empirical_polar_sha256": _sha256_file(emp_path),
            "spline_polar_json": str(spl_path.relative_to(root)).replace("\\", "/"),
            "spline_polar_sha256": _sha256_file(spl_path),
            "maneuver_model_json": str(man_json_path.relative_to(root)).replace("\\", "/"),
            "maneuver_model_sha256": _sha256_file(man_json_path),
            "start_model_json": str(start_json_path.relative_to(root)).replace("\\", "/"),
            "start_model_sha256": _sha256_file(start_json_path),
            "route_templates_json": str(rt_out_path.relative_to(root)).replace("\\", "/"),
            "route_templates_sha256": _sha256_file(rt_out_path),
            "residual_blocks_npz": str(res_npz_path.relative_to(root)).replace("\\", "/"),
            "residual_blocks_sha256": _sha256_file(res_npz_path),
            "scenarios_catalog": str(catalog_path.relative_to(root)).replace("\\", "/"),
            "scenarios_catalog_sha256": initial_cat_hash,
        },
        "total_scenarios_cached": 0,
        "available_teams": list(CANONICAL_TEAMS),
    }
    manifest_file.write_text(json.dumps(manifest_doc, indent=2), encoding="utf-8")

    reloaded_bundle = load_authenticated_bundle(manifest_file, root=root)

    key_pairs = [
        ("ac37:ETNZ", "ac37:INEOS"),
        ("ac37:ETNZ", "ac37:LUNA_ROSSA"),
        ("ac37:INEOS", "ac37:LUNA_ROSSA"),
        ("ac37:INEOS", "ac37:AMERICAN_MAGIC"),
        ("ac37:LUNA_ROSSA", "ac37:AMERICAN_MAGIC"),
        ("ac37:AMERICAN_MAGIC", "ac37:ALINGHI"),
        ("ac37:INEOS", "ac37:ALINGHI"),
        ("ac37:INEOS", "ac37:ORIENT_EXPRESS"),
        ("ac37:ETNZ", "ac37:AMERICAN_MAGIC"),
        ("ac37:ETNZ", "ac37:ALINGHI"),
    ]
    wind_speeds = [6.0, 9.0, 12.0]  # m/s (~ 11.7, 17.5, 23.3 kt)

    scenarios: list[dict[str, Any]] = []
    for ta, tb in key_pairs:
        for ws in wind_speeds:
            req = {
                "schema_version": "kinematic-race-sim-2",
                "model_id": candidate_id,
                "team_a": ta,
                "team_b": tb,
                "course_id": "barcelona_lvc_4leg",
                "environment": {"tws_mps": ws, "twd_deg": 180.0},
                "purpose": "preview",
                "scenario_policy_id": "training_observed_routes_v1",
                "seed": seed,
                "trial_count": 2000,
            }
            res = predict_scenario(reloaded_bundle, req)
            scenarios.append(res.to_dict())

    fallback_note = (
        f" Fallback reason: {selection_decision.get('fallback_reason')} "
        f"(qualified targets: {target_qual.get('qualified_count', 0)}/{target_qual.get('total_evaluated', 0)})."
        if selection_decision.get("is_fallback")
        else ""
    )
    status_notice = (
        f"Status: Experimental learned simulator ({candidate_id}, default motion predictor: {selected_cand_name}).{fallback_note} "
        f"Trained on {len(dev_windows):,} causal 5-second AC75 steady windows and {len(dev_maneuvers):,} "
        f"speed-independent maneuvers across {len(dev_dates)} development racing days; "
        f"chronologically calibrated on held-out date {cal_art.calibration_date} "
        f"(motion_residual_scale={cal_art.motion_residual_scale}, margin_interval_scale={cal_art.margin_interval_scale}). "
        "Evaluated under expanding chronological folds; not an official AC38 prediction."
    )

    catalog_envelope = {
        "schema_version": "ac75-catalog-2",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_id": candidate_id,
        "model_status": "experimental",
        "selected_motion_candidate": selected_cand_name,
        "selection_decision": selection_decision,
        "calibration": cal_art.to_dict(),
        "status_notice": status_notice,
        "total_scenarios": len(scenarios),
        "available_teams": list(CANONICAL_TEAMS),
        "available_modes": [
            {
                "id": "ac75_learned_v2",
                "label": "AC75 Learned Simulator (v2)",
                "description": "Causal AC37 telemetry learned motion, maneuver, and route simulator",
            },
            {
                "id": "barcelona_2024_empirical",
                "label": "Empirical Barcelona 2024 AC75 (v1)",
                "description": "Legacy phase-distribution model",
            },
            {
                "id": "barcelona_2024_empirical_with_ac38_rules",
                "label": "Empirical + AC38 Rule Adjustments (v1)",
                "description": "Legacy phase-distribution model with rule sliders",
            },
        ],
        "default_sliders": {
            "tws_mps": {"default": 9.0, "min": 4.0, "max": 12.0, "step": 0.5, "unit": "m/s"},
            "twd_deg": {"default": 180.0, "min": 0.0, "max": 355.0, "step": 5.0, "unit": "deg"},
        },
        "courses": list(COURSE_PRESETS.values()),
        "scenarios": scenarios,
    }

    catalog_path.write_text(json.dumps(catalog_envelope, indent=2), encoding="utf-8")
    catalog_hash = _sha256_file(catalog_path)

    manifest_doc["status_notice"] = status_notice
    manifest_doc["total_scenarios_cached"] = len(scenarios)
    manifest_doc["artifacts"]["scenarios_catalog_sha256"] = catalog_hash
    manifest_file.write_text(json.dumps(manifest_doc, indent=2), encoding="utf-8")
    manifest_hash = _sha256_file(manifest_file)

    load_authenticated_bundle(manifest_file, root=root)

    latest_doc = {
        "candidate_id": candidate_id,
        "staged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_path": str(manifest_file.relative_to(root)).replace("\\", "/"),
        "manifest_sha256": manifest_hash,
        "status": "experimental",
        "selected_motion_candidate": selected_cand_name,
        "route_template_count": len(template_lib._templates),
        "paired_residual_block_count": paired_blocks_count,
        "steady_windows_count": len(dev_windows),
    }
    tmp_pointer = latest_pointer_path.with_suffix(".tmp")
    tmp_pointer.write_text(json.dumps(latest_doc, indent=2), encoding="utf-8")
    tmp_pointer.replace(latest_pointer_path)

    return latest_doc


run_full_export_and_staging = export_ac75_learned_bundle


if __name__ == "__main__":
    doc = export_ac75_learned_bundle()
    print(f"Exported and staged candidate: {doc['candidate_id']}")
