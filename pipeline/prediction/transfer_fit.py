"""Joint transfer model fitting and convergence validation."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Sequence

import numpy as np

from .transfer_evidence import SHARED_AC37_TEAMS, load_transfer_observations
from .transfer_num import evaluate_grid, extract_percentiles, helmert_contrasts


@dataclass(frozen=True)
class TransferResult:
    schema_version: str
    beta_mode: float
    tau_mode: float
    rho_mode: float
    log_marginal_likelihood: float
    beta_percentiles: dict[str, float]
    tau_percentiles: dict[str, float]
    rho_percentiles: dict[str, float]
    two_stage_diagnostic: dict[str, float]
    boundary_mass: float
    grid_converged: bool
    sigma_40: float
    kappa: float
    roster_policy: str
    team_effects_ac75: dict[str, float]
    team_effects_ac40: dict[str, float]
    grid_summary: dict
    ac40_source: str = "ac37_2023"
    diagnostics: dict = field(default_factory=dict)
    posterior_grid: dict = field(default_factory=dict)


def estimate_transfer_two_stage(
    d40_stages: Sequence[np.ndarray],
    d75_matches: Sequence[np.ndarray],
    sigma_40: float = 1.2,
    kappa: float = 1.0,
) -> dict[str, float]:
    """Compute two-stage plug-in diagnostic for comparison against joint Laplace posterior."""
    prec = 1.0 / (sigma_40 ** 2)
    z40 = np.zeros(5)
    for _ in range(50):
        grad = prec * z40
        hess = prec * np.eye(5)
        for stage in d40_stages:
            x_mat, v_vec, w = stage if isinstance(stage, tuple) else (stage, np.ones(len(stage)), 1.0)
            u = kappa * (x_mat @ z40) + np.log(np.maximum(v_vec, 1e-12))
            p = np.exp(u - float(np.max(u)))
            p /= float(np.sum(p))
            mean_x = p @ x_mat
            grad += w * kappa * (mean_x - x_mat[0])
            centered = x_mat - mean_x
            hess += w * (kappa ** 2) * ((centered.T * p) @ centered)
        step = np.linalg.solve(hess, grad)
        z40 -= step
        if float(np.linalg.norm(step)) < 1e-8:
            break

    z75 = np.zeros(5)
    for _ in range(50):
        grad = prec * z75
        hess = prec * np.eye(5)
        for d in d75_matches:
            u = kappa * float(np.dot(d, z75))
            sig = 1.0 / (1.0 + math.exp(-max(min(u, 30.0), -30.0)))
            grad += -kappa * (1.0 - sig) * d
            hess += (kappa ** 2) * sig * (1.0 - sig) * np.outer(d, d)
        step = np.linalg.solve(hess, grad)
        z75 -= step
        if float(np.linalg.norm(step)) < 1e-8:
            break

    norm_40_sq = float(np.dot(z40, z40))
    if norm_40_sq > 1e-9:
        b_2stage = float(np.dot(z40, z75) / norm_40_sq)
        res = z75 - b_2stage * z40
        tau_2stage = float(np.sqrt(np.sum(res ** 2) / max(len(z75) - 1, 1)))
        norm_75 = float(np.linalg.norm(z75))
        rho_2stage = float(np.dot(z40, z75) / (math.sqrt(norm_40_sq) * norm_75)) if norm_75 > 1e-9 else 0.0
    else:
        b_2stage, tau_2stage, rho_2stage = 0.0, 1.0, 0.0
    return {"beta": b_2stage, "tau": tau_2stage, "rho": rho_2stage}


def fit_transfer_from_arrays(
    d40_stages: Sequence,
    d75_matches: np.ndarray,
    *,
    sigma_40: float = 1.2,
    kappa: float = 1.0,
    policy: str = "equal",
    ac40_source: str = "ac37_2023",
    check_refinement: bool = True,
    n_beta: int = 81,
    n_eta: int = 61,
    include_conditionals: bool = False,
    evidence_meta: dict | None = None,
) -> TransferResult:
    """Fit joint transfer model directly from design matrices (used for folds & live fit)."""
    q_mat = helmert_contrasts(6)
    two_stage = estimate_transfer_two_stage(
        d40_stages, [d75_matches[i] for i in range(len(d75_matches))], sigma_40=sigma_40, kappa=kappa
    )

    beta_min, beta_max = -2.5, 3.5
    eta_min, eta_max = math.log(0.015), math.log(3.5)
    betas = np.linspace(beta_min, beta_max, n_beta)
    etas = np.linspace(eta_min, eta_max, n_eta)
    log_p, weights, best_z, mode_info = evaluate_grid(
        betas, etas, d40_stages, d75_matches, sigma_40=sigma_40, kappa=kappa, return_conditionals=include_conditionals
    )

    for _ in range(4):
        if mode_info["boundary_mass"] < 1e-3:
            break
        w_bl, w_bh = float(np.sum(weights[0, :])), float(np.sum(weights[-1, :]))
        w_el, w_eh = float(np.sum(weights[:, 0])), float(np.sum(weights[:, -1]))
        expanded = False
        if w_bl >= 1.5e-4:
            beta_min -= 1.0
            n_beta += 20
            expanded = True
        if w_bh >= 1.5e-4:
            beta_max += 1.0
            n_beta += 20
            expanded = True
        if w_el >= 1.5e-4:
            eta_min -= 0.5
            n_eta += 15
            expanded = True
        if w_eh >= 1.5e-4:
            eta_max += 0.5
            n_eta += 15
            expanded = True
        if not expanded:
            worst = max([("bl", w_bl), ("bh", w_bh), ("el", w_el), ("eh", w_eh)], key=lambda x: x[1])[0]
            if worst == "bl":
                beta_min -= 1.0
                n_beta += 20
            elif worst == "bh":
                beta_max += 1.0
                n_beta += 20
            elif worst == "el":
                eta_min -= 0.5
                n_eta += 15
            else:
                eta_max += 0.5
                n_eta += 15
        betas = np.linspace(beta_min, beta_max, n_beta)
        etas = np.linspace(eta_min, eta_max, n_eta)
        log_p, weights, best_z, mode_info = evaluate_grid(
            betas, etas, d40_stages, d75_matches, sigma_40=sigma_40, kappa=kappa, return_conditionals=include_conditionals
        )

    b_pct, tau_pct, rho_pct = extract_percentiles(betas, etas, weights, sigma_40=sigma_40)

    refinement_delta = 0.0
    refinement_ok = True
    if check_refinement:
        betas_fine = np.linspace(beta_min, beta_max, 2 * len(betas) - 1)
        etas_fine = np.linspace(eta_min, eta_max, 2 * len(etas) - 1)
        _, w_fine, _, m_fine = evaluate_grid(betas_fine, etas_fine, d40_stages, d75_matches, sigma_40=sigma_40, kappa=kappa)
        bf, tf, rf = extract_percentiles(betas_fine, etas_fine, w_fine, sigma_40=sigma_40)
        refinement_delta = max(
            max(abs(b_pct[k] - bf[k]) for k in ("p05", "p50", "p95")),
            max(abs(tau_pct[k] - tf[k]) for k in ("p05", "p50", "p95")),
            max(abs(rho_pct[k] - rf[k]) for k in ("p05", "p50", "p95")),
        )
        refinement_ok = bool(refinement_delta < 0.01 and m_fine["all_points_converged"])

    grid_converged = bool(
        mode_info["all_points_converged"]
        and mode_info["boundary_mass"] < 1e-3
        and refinement_ok
    )

    th40_mode = q_mat @ best_z[:5]
    th75_mode = q_mat @ best_z[5:]
    team_effects_40 = {t: round(float(th40_mode[i]), 4) for i, t in enumerate(SHARED_AC37_TEAMS)}
    team_effects_75 = {t: round(float(th75_mode[i]), 4) for i, t in enumerate(SHARED_AC37_TEAMS)}

    diff_2stage = {
        "beta": round(two_stage["beta"], 4),
        "tau": round(two_stage["tau"], 4),
        "rho": round(two_stage["rho"], 4),
        "diff_beta_from_joint_p50": round(two_stage["beta"] - b_pct["p50"], 4),
        "diff_tau_from_joint_p50": round(two_stage["tau"] - tau_pct["p50"], 4),
        "diff_rho_from_joint_p50": round(two_stage["rho"] - rho_pct["p50"], 4),
    }

    diagnostics = {
        "all_points_converged": mode_info["all_points_converged"],
        "failed_grid_points": mode_info["failed_grid_points"],
        "max_grad_norm": mode_info["max_grad_norm"],
        "boundary_mass": mode_info["boundary_mass"],
        "refinement_max_quantile_delta": round(refinement_delta, 6),
        "refinement_ok": refinement_ok,
        "priors": {"ac40_sd": sigma_40, "beta": "Normal(0, 1)", "tau": "HalfNormal(1)", "kappa": kappa},
    }
    if evidence_meta:
        diagnostics["evidence"] = evidence_meta

    posterior_grid = {}
    if include_conditionals:
        posterior_grid = {
            "betas": betas,
            "etas": etas,
            "log_p": log_p,
            "weights": weights,
            "z_grid": mode_info["z_grid"],
            "h_grid": mode_info["h_grid"],
        }

    return TransferResult(
        schema_version="ac37-transfer-2",
        beta_mode=round(mode_info["beta"], 4),
        tau_mode=round(mode_info["tau"], 4),
        rho_mode=round(mode_info["rho"], 4),
        log_marginal_likelihood=round(mode_info["log_marginal_likelihood"], 4),
        beta_percentiles=b_pct,
        tau_percentiles=tau_pct,
        rho_percentiles=rho_pct,
        two_stage_diagnostic=diff_2stage,
        boundary_mass=round(mode_info["boundary_mass"], 6),
        grid_converged=grid_converged,
        sigma_40=sigma_40,
        kappa=kappa,
        roster_policy=policy,
        team_effects_ac75=team_effects_75,
        team_effects_ac40=team_effects_40,
        grid_summary={
            "beta_range": [round(float(betas[0]), 3), round(float(betas[-1]), 3)],
            "eta_range": [round(float(etas[0]), 3), round(float(etas[-1]), 3)],
            "evaluated_grid_points": len(betas) * len(etas),
            "boundary_mass": round(mode_info["boundary_mass"], 6),
            "grid_converged": grid_converged,
            "max_grad_norm": mode_info["max_grad_norm"],
            "refinement_max_quantile_delta": round(refinement_delta, 6),
        },
        ac40_source=ac40_source,
        diagnostics=diagnostics,
        posterior_grid=posterior_grid,
    )


def fit_transfer_model(
    root: Path,
    *,
    policy: str = "equal",
    sigma_40: float = 1.2,
    kappa: float = 1.0,
    check_refinement: bool = True,
    n_beta: int = 81,
    n_eta: int = 61,
    ac40_source: str = "ac37_2023",
    include_conditionals: bool = False,
) -> TransferResult:
    """Fit empirical transfer model from independently anchored AC37 observations."""
    obs = load_transfer_observations(root, ac40_source=ac40_source, policy=policy, require_independent=True)
    meta = {
        "n_ac40_races": len(obs["ac40_race_ids"]),
        "n_ac75_matches": len(obs["ac75_race_ids"]),
        "ac40_race_ids": obs["ac40_race_ids"],
        "ac75_race_ids": obs["ac75_race_ids"],
        "excluded_ac40": obs["excluded_ac40"],
        "excluded_ac75": obs["excluded_ac75"],
        "source_hashes": obs["source_hashes"],
    }
    return fit_transfer_from_arrays(
        obs["d40_stages"],
        obs["d75_matches"],
        sigma_40=sigma_40,
        kappa=kappa,
        policy=policy,
        ac40_source=ac40_source,
        check_refinement=check_refinement,
        n_beta=n_beta,
        n_eta=n_eta,
        include_conditionals=include_conditionals,
        evidence_meta=meta,
    )
