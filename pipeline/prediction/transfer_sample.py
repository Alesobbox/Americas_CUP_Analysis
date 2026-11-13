"""Private versioned transfer-posterior artifact and joint posterior sampler."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .transfer_evidence import SHARED_AC37_TEAMS
from .transfer_fit import fit_transfer_model
from .transfer_num import helmert_contrasts


def _artifact_hash(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "artifact_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_transfer_posterior_artifact(
    root: Path,
    *,
    sigma_40: float = 1.2,
    kappa: float = 1.0,
    policy: str = "equal",
    ac40_source: str = "ac37_2023",
    weight_cutoff: float = 1e-7,
    out_path: Path | None = None,
) -> dict:
    """Fit transfer model, compute sigma_40 sensitivities (0.8, 1.8), and persist joint posterior."""
    root = Path(root)
    if ac40_source != "ac37_2023":
        raise ValueError("Primary transfer_posterior artifact requires ac40_source='ac37_2023'; use diagnostic outputs for cross-cycle tests.")

    res = fit_transfer_model(
        root,
        policy=policy,
        sigma_40=sigma_40,
        kappa=kappa,
        check_refinement=True,
        include_conditionals=True,
    )
    if not res.grid_converged:
        raise RuntimeError(f"Primary transfer model failed convergence gate: {res.diagnostics}")

    sens_results = {}
    for s40 in (0.8, 1.8):
        s_res = fit_transfer_model(root, policy=policy, sigma_40=s40, kappa=kappa, check_refinement=True)
        sens_results[f"sigma_40_{s40:g}"] = {
            "sigma_40": s40,
            "beta_mode": s_res.beta_mode,
            "tau_mode": s_res.tau_mode,
            "rho_mode": s_res.rho_mode,
            "beta_percentiles": s_res.beta_percentiles,
            "tau_percentiles": s_res.tau_percentiles,
            "rho_percentiles": s_res.rho_percentiles,
            "grid_converged": s_res.grid_converged,
            "boundary_mass": s_res.boundary_mass,
        }

    pg = res.posterior_grid
    betas = pg["betas"]
    etas = pg["etas"]
    weights = pg["weights"]
    z_grid = pg["z_grid"]
    h_grid = pg["h_grid"]

    active_cells = []
    for i, b in enumerate(betas):
        for j, e in enumerate(etas):
            w = float(weights[i, j])
            if w <= weight_cutoff:
                continue
            cov = np.linalg.inv(h_grid[i, j])
            cov = 0.5 * (cov + cov.T)
            active_cells.append({
                "i": int(i),
                "j": int(j),
                "beta": float(b),
                "eta": float(e),
                "tau": float(math.exp(float(e))),
                "weight": w,
                "z_hat": [round(float(x), 7) for x in z_grid[i, j]],
                "z_cov": [[round(float(val), 7) for val in row] for row in cov],
            })

    total_active_w = sum(c["weight"] for c in active_cells)
    for c in active_cells:
        c["weight"] /= total_active_w

    doc = {
        "schema_version": "ac38-transfer-posterior-1",
        "cycle_training_domain": "ac37_within_cycle",
        "ac40_source": ac40_source,
        "shared_teams": [f"ac37:{t}" for t in SHARED_AC37_TEAMS],
        "scale_kappa": kappa,
        "priors": {
            "ac40_strength_sd": sigma_40,
            "ac40_sensitivity_sds": [0.8, 1.8],
            "beta": "Normal(0, 1)",
            "tau": "HalfNormal(1)",
        },
        "summary": {
            "beta_mode": res.beta_mode,
            "tau_mode": res.tau_mode,
            "rho_mode": res.rho_mode,
            "beta_percentiles": res.beta_percentiles,
            "tau_percentiles": res.tau_percentiles,
            "rho_percentiles": res.rho_percentiles,
            "log_marginal_likelihood": res.log_marginal_likelihood,
            "two_stage_diagnostic": res.two_stage_diagnostic,
            "team_effects_ac40": res.team_effects_ac40,
            "team_effects_ac75": res.team_effects_ac75,
        },
        "diagnostics": res.diagnostics,
        "prior_sensitivity": sens_results,
        "grid_axes": {
            "betas": [round(float(b), 6) for b in betas],
            "etas": [round(float(e), 6) for e in etas],
            "weights_normalized": [[round(float(w), 10) for w in row] for row in weights],
            "active_weight_retained": round(float(total_active_w), 8),
        },
        "active_conditionals": active_cells,
    }
    doc["artifact_sha256"] = _artifact_hash(doc)

    target = out_path or (root / ".forecast" / "ac38" / "transfer_posterior.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def load_transfer_posterior(root: Path, path: Path | None = None) -> dict:
    p = path or (Path(root) / ".forecast" / "ac38" / "transfer_posterior.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema_version") != "ac38-transfer-posterior-1":
        raise ValueError(f"Unexpected transfer posterior schema: {doc.get('schema_version')}")
    if doc.get("artifact_sha256") != _artifact_hash(doc):
        raise ValueError("Transfer posterior artifact SHA-256 mismatch")
    if not doc.get("diagnostics", {}).get("all_points_converged"):
        raise ValueError("Transfer posterior failed convergence diagnostics")
    return doc


def sample_joint_transfer_parameters(
    posterior_doc: dict,
    n_draws: int,
    *,
    rng: np.random.Generator,
    include_latents: bool = False,
) -> dict[str, np.ndarray]:
    """Sample (beta, tau[, theta_ac37_40, theta_ac37_75]) jointly preserving dependence."""
    cells = posterior_doc["active_conditionals"]
    probs = np.array([float(c["weight"]) for c in cells], dtype=float)
    probs /= float(np.sum(probs))
    indices = rng.choice(len(cells), size=n_draws, replace=True, p=probs)
    betas = np.array([float(cells[idx]["beta"]) for idx in indices], dtype=float)
    taus = np.array([float(cells[idx]["tau"]) for idx in indices], dtype=float)

    out: dict[str, np.ndarray] = {"beta": betas, "tau": taus}
    if include_latents:
        q_mat = helmert_contrasts(6)
        z_draws = np.zeros((n_draws, 10), dtype=float)
        unique_idx, inv = np.unique(indices, return_inverse=True)
        for pos, cell_idx in enumerate(unique_idx):
            cell = cells[int(cell_idx)]
            mask = inv == pos
            count = int(np.sum(mask))
            mean = np.array(cell["z_hat"], dtype=float)
            cov = np.array(cell["z_cov"], dtype=float)
            z_draws[mask] = rng.multivariate_normal(mean, cov, size=count)
        out["theta_ac37_40"] = z_draws[:, :5] @ q_mat.T
        out["theta_ac37_75"] = z_draws[:, 5:] @ q_mat.T
    return out
