"""Numerical Laplace approximation and 2D quadrature grid for the joint transfer model."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def helmert_contrasts(n: int = 6) -> np.ndarray:
    """Orthonormal Helmert contrast basis Q in R^{n x (n-1)} with zero-sum rows."""
    q = np.zeros((n, n - 1), dtype=float)
    for k in range(1, n):
        denom = math.sqrt(k * (k + 1))
        q[:k, k - 1] = 1.0 / denom
        q[k, k - 1] = -k / denom
    return q


def _prepare_stage_groups(d40_stages: Sequence) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Group Plackett-Luce choice sets by cardinality M for vectorized evaluation."""
    buckets: dict[int, tuple[list[np.ndarray], list[np.ndarray], list[float]]] = {}
    for stage in d40_stages:
        x_mat, v_vec, weight = stage if isinstance(stage, tuple) else (stage, np.ones(len(stage)), 1.0)
        m_len = len(x_mat)
        entry = buckets.setdefault(m_len, ([], [], []))
        entry[0].append(np.asarray(x_mat, dtype=float))
        entry[1].append(np.log(np.maximum(np.asarray(v_vec, dtype=float), 1e-12)))
        entry[2].append(float(weight))
    groups = []
    for m_len in sorted(buckets):
        xs, lvs, ws = buckets[m_len]
        groups.append((np.stack(xs, axis=0), np.stack(lvs, axis=0), np.array(ws, dtype=float)))
    return groups


def _stage_nll_grad_hess(
    z40: np.ndarray,
    d40_groups: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    kappa: float,
) -> tuple[float, np.ndarray, np.ndarray]:
    k_dim = len(z40)
    nll = 0.0
    grad = np.zeros(k_dim, dtype=float)
    hess = np.zeros((k_dim, k_dim), dtype=float)
    for x_arr, log_v, w_arr in d40_groups:
        # x_arr: (S, M, K)
        u = kappa * np.einsum("smk,k->sm", x_arr, z40) + log_v
        peak = np.max(u, axis=1, keepdims=True)
        el = np.exp(u - peak)
        sel = np.sum(el, axis=1, keepdims=True)
        p = el / sel
        nll += float(np.sum(w_arr * (peak[:, 0] + np.log(sel[:, 0]) - u[:, 0])))
        mean_x = np.einsum("sm,smk->sk", p, x_arr)
        grad += kappa * np.einsum("s,sk->k", w_arr, mean_x - x_arr[:, 0, :])
        centered = x_arr - mean_x[:, None, :]
        wp = w_arr[:, None] * p
        hess += (kappa ** 2) * np.einsum("sm,smk,sml->kl", wp, centered, centered)
    return nll, grad, hess


def _match_nll_grad_hess(
    z75: np.ndarray,
    d75_matches: np.ndarray,
    kappa: float,
) -> tuple[float, np.ndarray, np.ndarray]:
    k_dim = len(z75)
    if len(d75_matches) == 0:
        return 0.0, np.zeros(k_dim, dtype=float), np.zeros((k_dim, k_dim), dtype=float)
    u = np.clip(kappa * (d75_matches @ z75), -35.0, 35.0)
    sig = 1.0 / (1.0 + np.exp(-u))
    nll = float(np.sum(np.logaddexp(0.0, -u)))
    grad = -kappa * (d75_matches.T @ (1.0 - sig))
    w = sig * (1.0 - sig)
    hess = (kappa ** 2) * (d75_matches.T * w) @ d75_matches
    return nll, grad, hess


def _prior_precision(beta: float, eta: float, sigma_40: float, k_dim: int) -> np.ndarray:
    tau_sq_inv = math.exp(-2.0 * eta)
    s40_sq_inv = 1.0 / (sigma_40 ** 2)
    eye = np.eye(k_dim, dtype=float)
    lam = np.zeros((2 * k_dim, 2 * k_dim), dtype=float)
    lam[:k_dim, :k_dim] = (s40_sq_inv + (beta ** 2) * tau_sq_inv) * eye
    lam[:k_dim, k_dim:] = (-beta * tau_sq_inv) * eye
    lam[k_dim:, :k_dim] = (-beta * tau_sq_inv) * eye
    lam[k_dim:, k_dim:] = tau_sq_inv * eye
    return lam


def solve_joint_laplace_with_diagnostics(
    beta: float,
    eta: float,
    d40_stages: Sequence,
    d75_matches: np.ndarray,
    *,
    sigma_40: float = 1.2,
    kappa: float = 1.0,
    z_init: np.ndarray | None = None,
    grad_tol: float = 1e-6,
    max_iter: int = 60,
) -> tuple[float, np.ndarray, np.ndarray, dict]:
    """Solve inner Newton mode at (beta, eta) and validate convergence rigorously."""
    k_dim = 5
    d40_groups = (
        d40_stages
        if (len(d40_stages) > 0 and isinstance(d40_stages[0], tuple) and len(d40_stages[0]) == 3 and getattr(d40_stages[0][0], "ndim", 0) == 3)
        else _prepare_stage_groups(d40_stages)
    )
    lam = _prior_precision(beta, eta, sigma_40, k_dim)
    z = np.zeros(2 * k_dim, dtype=float) if z_init is None else np.copy(z_init)

    converged = False
    line_search_ok = True
    grad_norm = float("inf")
    psi_val = float("inf")
    h_full = np.copy(lam)

    for it in range(max_iter):
        z40, z75 = z[:k_dim], z[k_dim:]
        nll40, g40, h40 = _stage_nll_grad_hess(z40, d40_groups, kappa)
        nll75, g75, h75 = _match_nll_grad_hess(z75, d75_matches, kappa)
        psi_val = 0.5 * float(z @ (lam @ z)) + nll40 + nll75
        g_full = lam @ z
        g_full[:k_dim] += g40
        g_full[k_dim:] += g75
        grad_norm = float(np.linalg.norm(g_full))

        h_full = np.copy(lam)
        h_full[:k_dim, :k_dim] += h40
        h_full[k_dim:, k_dim:] += h75
        h_full = 0.5 * (h_full + h_full.T)

        if grad_norm < grad_tol:
            converged = True
            break
        try:
            step = np.linalg.solve(h_full, g_full)
        except np.linalg.LinAlgError:
            line_search_ok = False
            break

        slope = float(g_full @ step)
        alpha = 1.0
        accepted = False
        for _ in range(25):
            z_trial = z - alpha * step
            nll40_t, _, _ = _stage_nll_grad_hess(z_trial[:k_dim], d40_groups, kappa)
            nll75_t, _, _ = _match_nll_grad_hess(z_trial[k_dim:], d75_matches, kappa)
            psi_t = 0.5 * float(z_trial @ (lam @ z_trial)) + nll40_t + nll75_t
            if math.isfinite(psi_t) and (
                psi_t <= psi_val - 1e-4 * alpha * max(slope, 0.0)
                or (grad_norm < 1e-4 and psi_t <= psi_val + 1e-11)
            ):
                z = z_trial
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            line_search_ok = False
            break
    else:
        # Final gradient check after max_iter update
        nll40, g40, h40 = _stage_nll_grad_hess(z[:k_dim], d40_groups, kappa)
        nll75, g75, h75 = _match_nll_grad_hess(z[k_dim:], d75_matches, kappa)
        psi_val = 0.5 * float(z @ (lam @ z)) + nll40 + nll75
        g_full = lam @ z
        g_full[:k_dim] += g40
        g_full[k_dim:] += g75
        grad_norm = float(np.linalg.norm(g_full))
        h_full = np.copy(lam)
        h_full[:k_dim, :k_dim] += h40
        h_full[k_dim:, k_dim:] += h75
        h_full = 0.5 * (h_full + h_full.T)
        converged = grad_norm < grad_tol

    try:
        np.linalg.cholesky(h_full)
        pd_ok = True
    except np.linalg.LinAlgError:
        pd_ok = False

    sign, logdet_h = np.linalg.slogdet(h_full)
    # Priors: beta ~ N(0, 1), tau ~ HalfNormal(1) => p(eta) = sqrt(2/pi) exp(-0.5 exp(2*eta) + eta)
    log_p_beta = -0.5 * math.log(2.0 * math.pi) - 0.5 * (beta ** 2)
    log_p_eta = 0.5 * math.log(2.0 / math.pi) - 0.5 * math.exp(2.0 * eta) + eta
    log_prior_det = -0.5 * k_dim * math.log(sigma_40 ** 2) - float(k_dim) * eta
    finite_obj = math.isfinite(psi_val) and math.isfinite(logdet_h) and sign > 0 and pd_ok
    log_p_tilde = (
        log_p_beta + log_p_eta + log_prior_det - psi_val - 0.5 * logdet_h
        if finite_obj
        else -float("inf")
    )
    diag = {
        "converged": bool(converged and line_search_ok and pd_ok and math.isfinite(log_p_tilde)),
        "grad_norm": grad_norm,
        "line_search_ok": line_search_ok,
        "hessian_pd": pd_ok,
        "finite_objective": finite_obj,
    }
    return log_p_tilde, z, h_full, diag


def solve_joint_laplace_mode(
    beta: float,
    eta: float,
    d40_stages: Sequence,
    d75_matches: np.ndarray,
    sigma_40: float = 1.2,
    kappa: float = 1.0,
    z_init: np.ndarray | None = None,
) -> tuple[float, np.ndarray, np.ndarray]:
    log_p, z, h_full, _ = solve_joint_laplace_with_diagnostics(
        beta, eta, d40_stages, d75_matches, sigma_40=sigma_40, kappa=kappa, z_init=z_init
    )
    return log_p, z, h_full


def evaluate_grid(
    betas: np.ndarray,
    etas: np.ndarray,
    d40_stages: Sequence,
    d75_matches: np.ndarray,
    sigma_40: float = 1.2,
    kappa: float = 1.0,
    *,
    return_conditionals: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Evaluate 2D log marginal density on beta x eta grid with convergence tracking."""
    d40_groups = _prepare_stage_groups(d40_stages)
    nb, ne = len(betas), len(etas)
    log_p = np.zeros((nb, ne), dtype=float)
    z_grid = np.zeros((nb, ne, 10), dtype=float) if return_conditionals else None
    h_grid = np.zeros((nb, ne, 10, 10), dtype=float) if return_conditionals else None

    last_z = None
    best_log_p = -float("inf")
    best_z = np.zeros(10, dtype=float)
    best_coord = (0.0, 0.0)
    max_grad = 0.0
    failed_points = 0

    for i, b in enumerate(betas):
        e_indices = range(ne) if i % 2 == 0 else reversed(range(ne))
        for j in e_indices:
            lik, z_sol, h_mat, diag = solve_joint_laplace_with_diagnostics(
                float(b), float(etas[j]), d40_groups, d75_matches,
                sigma_40=sigma_40, kappa=kappa, z_init=last_z,
            )
            if not diag["converged"] and last_z is not None:
                lik, z_sol, h_mat, diag = solve_joint_laplace_with_diagnostics(
                    float(b), float(etas[j]), d40_groups, d75_matches,
                    sigma_40=sigma_40, kappa=kappa, z_init=None,
                )
            last_z = z_sol
            log_p[i, j] = lik
            if return_conditionals:
                z_grid[i, j] = z_sol
                h_grid[i, j] = h_mat
            max_grad = max(max_grad, diag["grad_norm"])
            if not diag["converged"]:
                failed_points += 1
            if lik > best_log_p:
                best_log_p = lik
                best_z = z_sol
                best_coord = (float(b), float(etas[j]))

    if not math.isfinite(best_log_p):
        raise ValueError("All Laplace grid evaluations produced non-finite objective")

    weights = np.exp(log_p - best_log_p)
    weights /= float(np.sum(weights))
    boundary_mass = float(
        np.sum(weights[0, :]) + np.sum(weights[-1, :]) + np.sum(weights[1:-1, 0]) + np.sum(weights[1:-1, -1])
    )
    tau_mode = math.exp(best_coord[1])
    rho_denom = math.sqrt((best_coord[0] * sigma_40) ** 2 + tau_mode ** 2)
    mode_info = {
        "beta": best_coord[0],
        "eta": best_coord[1],
        "tau": tau_mode,
        "rho": float((best_coord[0] * sigma_40) / rho_denom) if rho_denom > 1e-12 else 0.0,
        "log_marginal_likelihood": best_log_p,
        "boundary_mass": boundary_mass,
        "max_grad_norm": max_grad,
        "failed_grid_points": failed_points,
        "all_points_converged": failed_points == 0,
    }
    if return_conditionals:
        mode_info["z_grid"] = z_grid
        mode_info["h_grid"] = h_grid
    return log_p, weights, best_z, mode_info


def extract_percentiles(
    betas: np.ndarray,
    etas: np.ndarray,
    weights: np.ndarray,
    sigma_40: float = 1.2,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    p_beta = np.sum(weights, axis=1)
    p_beta = p_beta / np.sum(p_beta)
    cdf_beta = np.cumsum(p_beta) - 0.5 * p_beta
    b_pct = {
        k: round(float(np.interp(q, cdf_beta, betas)), 4)
        for k, q in (("p05", 0.05), ("p50", 0.50), ("p95", 0.95))
    }

    p_eta = np.sum(weights, axis=0)
    p_eta = p_eta / np.sum(p_eta)
    cdf_eta = np.cumsum(p_eta) - 0.5 * p_eta
    tau_pct = {
        k: round(float(math.exp(np.interp(q, cdf_eta, etas))), 4)
        for k, q in (("p05", 0.05), ("p50", 0.50), ("p95", 0.95))
    }

    rho_grid = np.zeros_like(weights)
    for i, b in enumerate(betas):
        for j, e in enumerate(etas):
            t = math.exp(float(e))
            denom = math.sqrt((float(b) * sigma_40) ** 2 + t ** 2)
            rho_grid[i, j] = (float(b) * sigma_40) / denom if denom > 1e-12 else 0.0

    flat_rho = rho_grid.flatten()
    order = np.argsort(flat_rho)
    s_rho = flat_rho[order]
    s_w = weights.flatten()[order]
    s_w = s_w / np.sum(s_w)
    cdf_rho = np.cumsum(s_w) - 0.5 * s_w
    rho_pct = {
        k: round(float(np.interp(q, cdf_rho, s_rho)), 4)
        for k, q in (("p05", 0.05), ("p50", 0.50), ("p95", 0.95))
    }
    return b_pct, tau_pct, rho_pct
