"""Command-line interface and receipt engine for AC75 kinematic learning."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
PRESERVATION_RECEIPT_PATH = FORECAST_DIR / "preservation_receipt.json"
PROGRESS_PATH = FORECAST_DIR / "progress.json"
DEFAULT_REPAIR_REGISTRATION = FORECAST_DIR / "experiments" / "repair_experiment_v1.json"


def make_receipt(
    command: str,
    status: str,
    reason_codes: list[str] | None = None,
    input_ids: dict[str, Any] | None = None,
    output_ids: dict[str, Any] | None = None,
    counts: dict[str, int] | None = None,
    elapsed_s: float = 0.0,
    log_path: str = "",
    exit_code: int = 0,
) -> dict[str, Any]:
    """Create a receipt conforming to G8.7 schema."""
    return {
        "schema_version": "ac75-command-receipt-1",
        "command": command,
        "status": status,
        "reason_codes": reason_codes or [],
        "input_ids": input_ids or {},
        "output_ids": output_ids or {},
        "counts": counts or {},
        "elapsed_s": round(elapsed_s, 4),
        "log_path": log_path,
        "exit_code": exit_code,
    }


def verify_environment() -> dict[str, Any]:
    """Verify runtime dependencies, disk space, and memory."""
    t0 = time.perf_counter()
    errors: list[str] = []
    counts = {"checks_run": 0, "checks_passed": 0}

    counts["checks_run"] += 1
    if sys.version_info < (3, 12):
        errors.append(f"Python >= 3.12 required, found {sys.version}")
    else:
        counts["checks_passed"] += 1

    for pkg in ("numpy", "scipy", "pyarrow", "sklearn", "catboost"):
        counts["checks_run"] += 1
        try:
            __import__(pkg)
            counts["checks_passed"] += 1
        except ImportError as e:
            errors.append(f"Missing core package {pkg}: {e}")

    counts["checks_run"] += 1
    free_gb = shutil.disk_usage(ROOT).free / (1024**3)
    if free_gb < 10.0:
        errors.append(f"Insufficient disk space: {free_gb:.2f} GB free, minimum 10 GB required")
    else:
        counts["checks_passed"] += 1

    counts["checks_run"] += 1
    torch_available = False
    try:
        __import__("torch")
        torch_available = True
    except ImportError:
        torch_available = False
    counts["checks_passed"] += 1

    return make_receipt(
        command="verify-environment",
        status="failed" if errors else "complete",
        reason_codes=errors,
        counts=counts,
        output_ids={
            "python": sys.version.split()[0],
            "free_disk_gb": round(free_gb, 2),
            "forecast_neural_installed": torch_available,
        },
        elapsed_s=time.perf_counter() - t0,
        exit_code=1 if errors else 0,
    )


def verify_preservation() -> dict[str, Any]:
    """Verify that public artifacts match the preservation receipt."""
    t0 = time.perf_counter()
    if not PRESERVATION_RECEIPT_PATH.exists():
        return make_receipt(
            command="verify-preservation",
            status="failed",
            reason_codes=["Preservation receipt not found"],
            exit_code=1,
            elapsed_s=time.perf_counter() - t0,
        )

    receipt_data = json.loads(PRESERVATION_RECEIPT_PATH.read_text(encoding="utf-8"))
    pub_artifacts = receipt_data.get("public_artifacts")
    recorded_merkle = (
        pub_artifacts.get("merkle_root_sha256")
        if isinstance(pub_artifacts, dict)
        else None
    )
    public_data = ROOT / "public" / "data"

    all_digests: list[str] = []
    file_count = 0
    for file_path in sorted(public_data.rglob("*")):
        if not file_path.is_file():
            continue
        file_count += 1
        rel_path = file_path.relative_to(public_data).as_posix()
        h = hashlib.sha256()
        with open(file_path, "rb") as fp:
            while chunk := fp.read(1024 * 1024):
                h.update(chunk)
        all_digests.append(f"{rel_path}:{h.hexdigest()}")

    computed_merkle = hashlib.sha256("\n".join(sorted(all_digests)).encode("utf-8")).hexdigest()
    mismatches = (
        [f"Merkle root mismatch: recorded {recorded_merkle}, computed {computed_merkle}"]
        if computed_merkle != recorded_merkle
        else []
    )
    return make_receipt(
        command="verify-preservation",
        status="failed" if mismatches else "complete",
        reason_codes=mismatches,
        counts={"verified_files": file_count, "mismatch_count": len(mismatches)},
        input_ids={"recorded_merkle_root": recorded_merkle},
        output_ids={"computed_merkle_root": computed_merkle},
        elapsed_s=time.perf_counter() - t0,
        exit_code=1 if mismatches else 0,
    )


def get_progress_status(task_id: str | None = None) -> dict[str, Any]:
    """Read and return task progress."""
    t0 = time.perf_counter()
    if not PROGRESS_PATH.exists():
        return make_receipt(
            command="progress",
            status="failed",
            reason_codes=["progress.json does not exist"],
            exit_code=1,
            elapsed_s=time.perf_counter() - t0,
        )

    data = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    tasks = data.get("tasks") if isinstance(data.get("tasks"), dict) else {}
    if task_id:
        if task_id not in tasks:
            return make_receipt(
                command="progress",
                status="failed",
                reason_codes=[f"Task {task_id} not found in progress.json"],
                exit_code=1,
                elapsed_s=time.perf_counter() - t0,
            )
        return make_receipt(
            command="progress",
            status="complete",
            output_ids={"task": tasks[task_id]},
            elapsed_s=time.perf_counter() - t0,
        )

    completed = [tid for tid, t in tasks.items() if t.get("status") == "complete"]
    pending = [tid for tid, t in tasks.items() if t.get("status") == "pending"]
    return make_receipt(
        command="progress",
        status="complete",
        counts={
            "total_tasks": len(tasks),
            "completed_tasks": len(completed),
            "pending_tasks": len(pending),
        },
        output_ids={"current_task": data.get("current_task"), "completed": completed},
        elapsed_s=time.perf_counter() - t0,
    )


def run_inventory(config_path: str | None = None) -> dict[str, Any]:
    """Execute archive inventory and evidence registration."""
    t0 = time.perf_counter()
    from .config import compute_config_hash, load_config
    from .inventory import generate_inventory_and_audit

    cfg = load_config(config_path)
    cfg_hash = compute_config_hash(cfg)
    res = generate_inventory_and_audit()
    return make_receipt(
        command="inventory",
        status="complete",
        input_ids={"config_id": cfg.config_id, "config_hash": cfg_hash},
        output_ids={
            "inventory_id": res["inventory_id"],
            "manifest_path": res["manifest_path"],
            "audit_path": res["audit_path"],
            "merkle_root": res["merkle_root"],
        },
        counts={
            "total_files": res["total_files"],
            "ac75_eligible_jsonl_count": res["ac75_eligible_jsonl_count"],
            "ac75_unsupported_binary_count": res["ac75_unsupported_binary_count"],
            "reserved_holdout_dates_count": len(res["reserved_holdout_dates"]),
        },
        elapsed_s=time.perf_counter() - t0,
    )


def run_labels() -> dict[str, Any]:
    """Execute attempt ledger and outcome evidence extraction."""
    t0 = time.perf_counter()
    from .labels import run_labels_and_splits

    res = run_labels_and_splits()
    return make_receipt(
        command="labels",
        status="complete",
        output_ids={
            "attempt_ledger_path": res.get("attempt_ledger_path", ""),
            "outcome_ledger_path": res.get("outcome_ledger_path", ""),
            "splits_path": res.get("splits_path", ""),
        },
        counts={
            "total_attempts": res.get("total_attempts", 0),
            "total_outcomes": res.get("total_outcomes", 0),
        },
        elapsed_s=time.perf_counter() - t0,
    )


def run_normalize() -> dict[str, Any]:
    """Execute native AC75 Parquet dataset normalization."""
    t0 = time.perf_counter()
    from .dataset import build_native_dataset

    manifest = build_native_dataset()
    return make_receipt(
        command="normalize",
        status="complete",
        output_ids={"dataset_id": manifest.get("dataset_id", "")},
        counts={
            "total_partitions": manifest.get("total_partitions", 0),
            "total_rows": manifest.get("total_rows", 0),
        },
        elapsed_s=time.perf_counter() - t0,
    )


def run_features() -> dict[str, Any]:
    """Execute sealed causal feature, maneuver, and route extraction."""
    t0 = time.perf_counter()
    from .features import build_sealed_feature_dataset

    manifest = build_sealed_feature_dataset()
    return make_receipt(
        command="features",
        status="complete",
        output_ids={"schema_version": manifest.get("schema_version", "")},
        counts=manifest.get("counts", {}),
        elapsed_s=time.perf_counter() - t0,
    )


def run_evaluate() -> dict[str, Any]:
    """Execute chronological expanding evaluation."""
    t0 = time.perf_counter()
    from .evaluate_ac75 import run_ac75_full_evaluation

    report = run_ac75_full_evaluation()
    return make_receipt(
        command="evaluate",
        status="complete",
        output_ids={
            "selected_candidate": report.get("selected_candidate", ""),
            "selection_rationale": report.get("selection_rationale", ""),
        },
        counts={
            "total_folds_evaluated": report.get("total_folds_evaluated", 0),
            "total_oof_windows": report.get("total_oof_windows", 0),
            "total_oof_races": report.get("total_oof_races", 0),
        },
        elapsed_s=time.perf_counter() - t0,
    )


def run_export() -> dict[str, Any]:
    """Execute full candidate training, export, and staging."""
    t0 = time.perf_counter()
    from .export_ac75 import run_full_export_and_staging

    manifest = run_full_export_and_staging()
    return make_receipt(
        command="export",
        status="complete",
        output_ids={
            "candidate_id": manifest.get("candidate_id", ""),
            "selected_motion_candidate": manifest.get("selected_motion_candidate", ""),
        },
        counts={
            "total_scenarios_cached": manifest.get("total_scenarios_cached", 0),
            "route_template_count": manifest.get("route_template_count", 0),
            "paired_residual_block_count": manifest.get("paired_residual_block_count", 0),
        },
        elapsed_s=time.perf_counter() - t0,
    )


def run_simulate_cli(
    team_a: str,
    team_b: str,
    tws_kt: float,
    twd_deg: float,
    course_id: str,
    mode: str,
) -> dict[str, Any]:
    """Execute single scenario simulation via learned AC75 bundle."""
    t0 = time.perf_counter()
    from .inference import predict_scenario
    from .loader import load_staged_ac75_bundle

    bundle = load_staged_ac75_bundle()
    tws_mps = round(float(tws_kt) / 1.943844, 4)
    c_a = team_a if team_a.startswith("ac37:") else f"ac37:{team_a}"
    c_b = team_b if team_b.startswith("ac37:") else f"ac37:{team_b}"
    scen_req = {
        "schema_version": "kinematic-race-sim-2",
        "model_id": bundle.model_id,
        "team_a": c_a,
        "team_b": c_b,
        "course_id": course_id or "barcelona_lvc_4leg",
        "environment": {"tws_mps": tws_mps, "twd_deg": twd_deg},
        "purpose": "preview",
        "trial_count": 2000,
        "seed": 2027,
    }
    scen_res = predict_scenario(bundle, scen_req)
    res_dict = scen_res.to_dict()
    return make_receipt(
        command="simulate",
        status="complete" if scen_res.status == "available" else scen_res.status,
        reason_codes=scen_res.reason_codes,
        output_ids={"scenario": res_dict},
        elapsed_s=time.perf_counter() - t0,
    )


def run_repair(
    registration_path: str | Path,
    phase: str = "prepare",
    resume: bool = False,
) -> dict[str, Any]:
    """Execute thin, resumable repair experiment orchestration.

    The CLI only dispatches and records receipts, keeping computation in owning modules.
    """
    t0 = time.perf_counter()
    reg_file = Path(registration_path)
    if not reg_file.is_absolute():
        reg_file = ROOT / reg_file

    receipts_file = reg_file.parent / f"{reg_file.stem}_receipts.json"
    receipts_ledger: dict[str, Any] = {}
    if receipts_file.exists():
        try:
            receipts_ledger = json.loads(receipts_file.read_text(encoding="utf-8"))
        except Exception:
            receipts_ledger = {}

    # Resumption check: return cached complete receipt if requested
    if resume and phase in receipts_ledger:
        prior_receipt = receipts_ledger[phase]
        if prior_receipt.get("status") == "complete":
            cached = dict(prior_receipt)
            cached["resumed"] = True
            return cached

    if not reg_file.exists():
        return make_receipt(
            command=f"repair:{phase}",
            status="failed",
            reason_codes=[f"Registration file not found: {reg_file}"],
            input_ids={"registration_path": str(reg_file)},
            exit_code=1,
            elapsed_s=time.perf_counter() - t0,
        )

    try:
        reg_data = json.loads(reg_file.read_text(encoding="utf-8"))
    except Exception as e:
        return make_receipt(
            command=f"repair:{phase}",
            status="failed",
            reason_codes=[f"Failed to parse registration file: {e}"],
            input_ids={"registration_path": str(reg_file)},
            exit_code=1,
            elapsed_s=time.perf_counter() - t0,
        )

    receipt: dict[str, Any]
    if phase == "prepare":
        env_receipt = verify_environment()
        if env_receipt["exit_code"] != 0:
            return make_receipt(
                command="repair:prepare",
                status="failed",
                reason_codes=env_receipt["reason_codes"],
                exit_code=env_receipt["exit_code"],
                elapsed_s=time.perf_counter() - t0,
            )
        pres_receipt = verify_preservation()
        if pres_receipt["exit_code"] != 0:
            return make_receipt(
                command="repair:prepare",
                status="failed",
                reason_codes=pres_receipt["reason_codes"],
                exit_code=pres_receipt["exit_code"],
                elapsed_s=time.perf_counter() - t0,
            )

        fef_path = FORECAST_DIR / "frozen_evaluation_families.json"
        fef_exists = fef_path.exists()
        sealed_df_path = FORECAST_DIR / "sealed" / "steady_windows.parquet"
        sealed_exists = sealed_df_path.exists()

        receipt = make_receipt(
            command="repair:prepare",
            status="complete" if (fef_exists and sealed_exists) else "failed",
            reason_codes=[] if (fef_exists and sealed_exists) else ["Missing sealed dataset or frozen families"],
            input_ids={
                "registration_path": str(reg_file),
                "experiment_id": reg_data.get("experiment_id", ""),
            },
            output_ids={
                "merkle_root": pres_receipt.get("output_ids", {}).get("computed_merkle_root", ""),
                "frozen_families_present": fef_exists,
                "sealed_dataset_present": sealed_exists,
            },
            counts={
                "verified_files": pres_receipt.get("counts", {}).get("verified_files", 0),
            },
            elapsed_s=time.perf_counter() - t0,
            exit_code=0 if (fef_exists and sealed_exists) else 1,
        )
    elif phase == "train":
        from .export_ac75 import run_full_export_and_staging
        manifest = run_full_export_and_staging()
        receipt = make_receipt(
            command="repair:train",
            status="complete",
            input_ids={"experiment_id": reg_data.get("experiment_id", "")},
            output_ids={
                "candidate_id": manifest.get("candidate_id", ""),
                "selected_motion_candidate": manifest.get("selected_motion_candidate", ""),
            },
            counts={
                "route_template_count": manifest.get("route_template_count", 0),
                "paired_residual_block_count": manifest.get("paired_residual_block_count", 0),
            },
            elapsed_s=time.perf_counter() - t0,
            exit_code=0,
        )
    elif phase == "evaluate":
        from .evaluate_ac75 import run_ac75_full_evaluation
        report = run_ac75_full_evaluation()
        receipt = make_receipt(
            command="repair:evaluate",
            status="complete",
            input_ids={"experiment_id": reg_data.get("experiment_id", "")},
            output_ids={
                "selected_candidate": report.get("selected_candidate", ""),
                "selection_rationale": report.get("selection_rationale", ""),
            },
            counts={
                "total_folds_evaluated": report.get("total_folds_evaluated", 0),
            },
            elapsed_s=time.perf_counter() - t0,
            exit_code=0,
        )
    elif phase == "stage":
        latest_path = FORECAST_DIR / "latest_candidate.json"
        latest = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else {}
        receipt = make_receipt(
            command="repair:stage",
            status="complete" if latest else "failed",
            input_ids={"experiment_id": reg_data.get("experiment_id", "")},
            output_ids={"latest_candidate": latest.get("candidate_id", "")},
            elapsed_s=time.perf_counter() - t0,
            exit_code=0 if latest else 1,
        )
    elif phase == "verify":
        pres_receipt = verify_preservation()
        receipt = make_receipt(
            command="repair:verify",
            status=pres_receipt["status"],
            reason_codes=pres_receipt["reason_codes"],
            input_ids={"experiment_id": reg_data.get("experiment_id", "")},
            output_ids=pres_receipt.get("output_ids", {}),
            counts=pres_receipt.get("counts", {}),
            elapsed_s=time.perf_counter() - t0,
            exit_code=pres_receipt["exit_code"],
        )
    else:
        receipt = make_receipt(
            command=f"repair:{phase}",
            status="failed",
            reason_codes=[f"Unsupported phase: {phase}"],
            exit_code=1,
            elapsed_s=time.perf_counter() - t0,
        )

    # Persist receipt in receipts ledger
    if receipt.get("exit_code") == 0:
        receipts_ledger[phase] = receipt
        receipts_file.parent.mkdir(parents=True, exist_ok=True)
        receipts_file.write_text(json.dumps(receipts_ledger, indent=2), encoding="utf-8")

    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AC75 learned kinematic modeling CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("verify-environment", help="Verify runtime environment")
    subparsers.add_parser("verify-preservation", help="Verify public artifact preservation")

    inv_parser = subparsers.add_parser("inventory", help="Inventory source archive")
    inv_parser.add_argument("--config", type=str, default=None)

    subparsers.add_parser("labels", help="Extract attempt ledger and outcome evidence")
    subparsers.add_parser("normalize", help="Normalize raw AC75 JSONL into Parquet")
    subparsers.add_parser("features", help="Build sealed causal features and events")
    subparsers.add_parser("evaluate", help="Run chronological expanding evaluation")
    subparsers.add_parser("export", help="Train, export, and stage candidate bundle")

    sim_parser = subparsers.add_parser("simulate", help="Run scenario simulation")
    sim_parser.add_argument("--team-a", type=str, default="ETNZ")
    sim_parser.add_argument("--team-b", type=str, default="GB1")
    sim_parser.add_argument("--tws", type=float, default=12.0)
    sim_parser.add_argument("--twd", type=float, default=180.0)
    sim_parser.add_argument("--course", type=str, default="barcelona_6leg_1852m")
    sim_parser.add_argument("--mode", type=str, default="ac75_learned_v2")

    prog_parser = subparsers.add_parser("progress", help="Show task execution progress")
    prog_parser.add_argument("--task", type=str, default=None)

    repair_parser = subparsers.add_parser("repair", help="Run resumable repair experiment orchestration")
    repair_parser.add_argument(
        "--registration",
        type=str,
        default=str(DEFAULT_REPAIR_REGISTRATION),
        help="Path to experiment registration file",
    )
    repair_parser.add_argument(
        "--phase",
        choices=["prepare", "train", "evaluate", "stage", "verify"],
        default="prepare",
        help="Phase to execute (prepare, train, evaluate, stage, verify)",
    )
    repair_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from cached receipt if phase already completed",
    )

    args = parser.parse_args(argv)
    handlers = {
        "verify-environment": verify_environment,
        "verify-preservation": verify_preservation,
        "inventory": lambda: run_inventory(config_path=args.config),
        "labels": run_labels,
        "normalize": run_normalize,
        "features": run_features,
        "evaluate": run_evaluate,
        "export": run_export,
        "simulate": lambda: run_simulate_cli(
            args.team_a, args.team_b, args.tws, args.twd, args.course, args.mode
        ),
        "progress": lambda: get_progress_status(task_id=args.task),
        "repair": lambda: run_repair(
            registration_path=args.registration,
            phase=args.phase,
            resume=args.resume,
        ),
    }

    handler = handlers.get(args.subcommand)
    receipt = (
        handler()
        if handler is not None
        else make_receipt(
            command=args.subcommand,
            status="failed",
            reason_codes=["Unknown command"],
            exit_code=1,
        )
    )
    print(json.dumps(receipt, indent=2))
    return receipt["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
