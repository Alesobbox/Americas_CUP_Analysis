"""Facade for the joint AC37 AC40-to-AC75 transfer model and private posterior artifacts."""
from __future__ import annotations

import json
from pathlib import Path

from .transfer_evidence import SHARED_AC37_TEAMS
from .transfer_fit import TransferResult, estimate_transfer_two_stage, fit_transfer_model
from .transfer_num import evaluate_grid, extract_percentiles, helmert_contrasts, solve_joint_laplace_mode
from .transfer_sample import build_transfer_posterior_artifact, load_transfer_posterior, sample_joint_transfer_parameters

ROOT = Path(__file__).resolve().parents[2]

__all__ = [
    "SHARED_AC37_TEAMS",
    "TransferResult",
    "helmert_contrasts",
    "estimate_transfer_two_stage",
    "solve_joint_laplace_mode",
    "evaluate_grid",
    "extract_percentiles",
    "fit_transfer_model",
    "run_transfer_study",
    "build_transfer_posterior_artifact",
    "load_transfer_posterior",
    "sample_joint_transfer_parameters",
]


def run_transfer_study(
    root: Path | None = None,
    out_path: Path | None = None,
    ac40_source: str = "ac37_2023",
    policy: str = "equal",
    kappa: float = 1.0,
) -> dict:
    """Execute within-cycle AC37 transfer study and isolate cross-cycle diagnostics."""
    root_path = Path(root or ROOT)
    result = fit_transfer_model(root_path, policy=policy, ac40_source=ac40_source, kappa=kappa)

    study_doc = {
        "schema_version": "ac37-transfer-study-2",
        "status": "success" if result.grid_converged else "convergence_warning",
        "ac40_source": ac40_source,
        "scale_kappa": kappa,
        "priors": {"ac40_sd": result.sigma_40, "beta": "Normal(0, 1)", "tau": "HalfNormal(1)"},
        "n_shared_teams": len(SHARED_AC37_TEAMS),
        "shared_teams": list(SHARED_AC37_TEAMS),
        "beta_mode": result.beta_mode,
        "tau_mode": result.tau_mode,
        "rho_mode": result.rho_mode,
        "log_marginal_likelihood": result.log_marginal_likelihood,
        "beta_percentiles": result.beta_percentiles,
        "tau_percentiles": result.tau_percentiles,
        "rho_percentiles": result.rho_percentiles,
        "two_stage_diagnostic": result.two_stage_diagnostic,
        "boundary_mass": result.boundary_mass,
        "grid_converged": result.grid_converged,
        "diagnostics": result.diagnostics,
        "team_effects_ac75": result.team_effects_ac75,
        "team_effects_ac40": result.team_effects_ac40,
        "ac40_strengths": result.team_effects_ac40,
        "ac75_empirical_strengths": result.team_effects_ac75,
        "grid_summary": result.grid_summary,
    }

    if out_path is not None:
        target_out = out_path
    elif ac40_source == "ac37_2023":
        target_out = root_path / ".forecast" / "transfer" / "ac37_transfer.json"
    else:
        target_out = root_path / ".forecast" / "transfer" / f"diagnostic_{ac40_source}.json"

    target_out.parent.mkdir(parents=True, exist_ok=True)
    target_out.write_text(json.dumps(study_doc, indent=2) + "\n", encoding="utf-8")
    return study_doc


if __name__ == "__main__":
    res = run_transfer_study()
    print(f"Transfer study complete. beta_mode={res['beta_mode']}, tau_mode={res['tau_mode']}, rho_mode={res['rho_mode']}")
