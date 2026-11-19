"""Orchestrate AC38 model, wind-source and environmental comparisons."""

import hashlib
from pathlib import Path

from .environment_ablation import run_environment_ablation
from .polar_evaluation import evaluate_surfaces
from .polar_table import describe_cohort, table_from_details
from .wind_agreement import run_wind_agreement


def run_polar_experiments(details_by_id: dict, data_dir: Path) -> dict:
    table = table_from_details(details_by_id)
    report = {
        "schema_version": "ac38-polar-experiments-1",
        "method_version": "ac38-research-1",
        "input_sha256": _input_hash(table, details_by_id, Path(data_dir)),
        "cohort": describe_cohort(table),
        "scope": "AC38 AC40 accepted steady 1 Hz samples; retrospective conditional performance",
        "calibration_limits": {
            "day_count": len(set(table.day)),
            "conformal_status": "insufficient_independent_days_for_strong_split_conformal_guarantees",
            "explanation": "Day grouping does not establish exchangeability or conditional coverage.",
        },
        "regime_model_status": {
            "status": "not_physically_identified",
            "reason": "No verified foil-state labels; selected steady population excludes SOG<5kt and incomplete legs.",
            "decision": "Compare kernel and local-linear models; do not label latent components as foiling states.",
        },
    }
    if table.size == 0:
        report.update(
            status="unavailable",
            reason="No timestamped polar_samples; regenerate sample extraction first.",
        )
        return report
    report["status"] = "evaluated"
    report["model_comparison"] = {
        "leave_one_day_out": evaluate_surfaces(table),
        "chronological": evaluate_surfaces(table, True),
    }
    report["wind_comparison"] = run_wind_agreement(table, Path(data_dir))
    report["environment_ablation"] = run_environment_ablation(table, Path(data_dir))
    return report


def experiment_input_hash(details_by_id: dict, data_dir: Path) -> str:
    return _input_hash(table_from_details(details_by_id), details_by_id, Path(data_dir))


def _input_hash(table, details, data_dir):
    digest = hashlib.sha256()
    for name, values in vars(table).items():
        digest.update(name.encode())
        digest.update(values.dtype.str.encode())
        digest.update(values.tobytes())
    for race_id in sorted(details):
        replay = data_dir / "replays" / f"{race_id}.json"
        digest.update(replay.read_bytes() if replay.is_file() else b"missing_replay")
        environment = data_dir / "environment" / "boats" / f"{race_id}.json"
        digest.update(environment.read_bytes() if environment.is_file() else b"missing_environment")
    modules = (
        "polar_table",
        "polar_surface",
        "polar_evaluation",
        "feature_evaluation",
        "wind_agreement",
        "environment_ablation",
        "polar_experiments",
    )
    for module in modules:
        digest.update(Path(__file__).with_name(module + ".py").read_bytes())
    return digest.hexdigest()
