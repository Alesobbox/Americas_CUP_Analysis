"""AC38 AC40 entry fitting, syndicate mapping, joint world sampling, and nested intervals."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .ac38_evidence import build_eligibility_ledger, is_valid_independent_evidence, parse_utc_iso
from .ac38_telemetry import TELEM_DIMS, fit_pl_with_telemetry
from .cup import TEAM_IDS, TEAM_NAMES, CupRules, CupScenario, simulate_cup
from .transfer_sample import sample_joint_transfer_parameters


@dataclass(frozen=True)
class MappingSpec:
    policy: str
    a_matrix: np.ndarray
    entry_keys: tuple[str, ...]
    provenance: list[dict[str, Any]]
    observed_mask: np.ndarray


def _load_ac38_race_rows(root: Path, ledger: dict[str, Any], *, evidence_scope: str) -> dict[str, Any]:
    flag_key = "eligible_ac38_anchored_only" if evidence_scope == "anchored_only" else "eligible_ac38_with_reconstructed"
    eligible_ids = {row["observation_id"] for row in ledger["ac38_observations"] if row.get(flag_key)}
    excluded = [
        {"observation_id": row["observation_id"], "reason": row.get("exclusion_reason")}
        for row in ledger["ac38_observations"]
        if not row.get(flag_key)
    ]
    off_doc = json.loads((root / "docs" / "official_results_ac38_prelims.json").read_text(encoding="utf-8"))
    orders: list[list[str]] = []
    race_ids: list[str] = []
    anchored_ids: list[str] = []
    reconstructed_ids: list[str] = []

    obs_by_id = {row["observation_id"]: row for row in ledger["ac38_observations"]}
    for r in off_doc.get("races", []):
        rid = r["race_id"]
        if rid not in eligible_ids:
            continue
        order = r.get("official_order") or r.get("on_water_finish_order") or []
        if len(order) < 2:
            continue
        orders.append(list(order))
        race_ids.append(rid)
        obs_rec = obs_by_id.get(rid)
        if obs_rec and obs_rec.get("reconstructed_fallback_used"):
            reconstructed_ids.append(rid)
        else:
            anchored_ids.append(rid)
    return {
        "orders": orders,
        "race_ids": race_ids,
        "anchored_race_ids": anchored_ids,
        "reconstructed_race_ids": reconstructed_ids,
        "excluded_observations": excluded,
    }


def fit_ac38_ac40_strengths(
    root: Path,
    *,
    issuance_cutoff_utc: str,
    evidence_scope: str = "with_reconstructed",
    sigma_40: float = 1.2,
    kappa: float = 1.0,
) -> dict[str, Any]:
    """Fit AC38 AC40 entry strengths on kappa=1.0 scale strictly <= issuance_cutoff_utc."""
    root = Path(root)
    if parse_utc_iso(issuance_cutoff_utc) is None:
        raise ValueError("Explicit valid UTC issuance_cutoff_utc is required")
    if evidence_scope not in ("with_reconstructed", "anchored_only"):
        raise ValueError(f"Unsupported evidence_scope: {evidence_scope}")

    ledger = build_eligibility_ledger(root, issuance_cutoff_utc=issuance_cutoff_utc, write=False)
    loaded = _load_ac38_race_rows(root, ledger, evidence_scope=evidence_scope)
    orders = loaded["orders"]
    entrants = sorted({entry for order in orders for entry in order})

    if not orders or not entrants:
        return {
            "issuance_cutoff_utc": issuance_cutoff_utc,
            "evidence_scope": evidence_scope,
            "sigma_40": sigma_40,
            "kappa": kappa,
            "entrants": [],
            "theta": {},
            "covariance": [],
            "race_ids": [],
            "anchored_race_ids": [],
            "reconstructed_race_ids": [],
            "excluded_observations": loaded["excluded_observations"],
        }

    zero_z = [{e: np.zeros(len(TELEM_DIMS)) for e in order} for order in orders]
    zero_m = [{e: np.zeros(len(TELEM_DIMS), dtype=bool) for e in order} for order in orders]
    fit = fit_pl_with_telemetry(
        orders, zero_z, zero_m, entrants=entrants, sigma_40=sigma_40, kappa=kappa
    )
    n_ent = len(entrants)
    cov_ent = np.asarray(fit["covariance"], dtype=float)[:n_ent, :n_ent]
    cov_ent = 0.5 * (cov_ent + cov_ent.T)
    return {
        "issuance_cutoff_utc": issuance_cutoff_utc,
        "evidence_scope": evidence_scope,
        "sigma_40": sigma_40,
        "kappa": kappa,
        "entrants": entrants,
        "theta": fit["theta"],
        "covariance": cov_ent.tolist(),
        "race_ids": loaded["race_ids"],
        "anchored_race_ids": loaded["anchored_race_ids"],
        "reconstructed_race_ids": loaded["reconstructed_race_ids"],
        "excluded_observations": loaded["excluded_observations"],
    }


def map_ac38_entries_to_ac75_syndicates(
    root: Path,
    ac40_fit: dict[str, Any],
    *,
    mapping_policy: str = "confirmed_crew_then_principal_ac40_else_prior",
) -> MappingSpec:
    """Map AC38 AC40 entry strengths onto the 7 registered AC75 teams without race-count weighting."""
    if mapping_policy not in ("confirmed_crew_then_principal_ac40_else_prior", "equal"):
        raise ValueError(f"Unsupported mapping_policy: {mapping_policy}")
    roster = json.loads((Path(root) / "docs" / "ac38_roster.json").read_text(encoding="utf-8"))
    by_team = {s["team_id"]: s for s in roster.get("syndicates", [])}

    entrants = list(ac40_fit.get("entrants", []))
    ent_idx = {e: i for i, e in enumerate(entrants)}
    theta_ent = ac40_fit.get("theta", {})
    cov_ent = np.asarray(ac40_fit.get("covariance", []), dtype=float)
    a_mat = np.zeros((len(TEAM_IDS), len(entrants)), dtype=float)
    observed_mask = np.zeros(len(TEAM_IDS), dtype=bool)
    provenance: list[dict[str, Any]] = []

    for t_i, team in enumerate(TEAM_IDS):
        spec = by_team.get(team, {})
        cand_entries = [e["entry_id"] for e in spec.get("entries", [])]
        confirmed_crew = spec.get("confirmed_ac75_crew_entry")
        principal_entry = spec.get("principal_ac40_entry")

        selected: list[str] = []
        basis = "population_prior"
        if mapping_policy == "equal":
            selected = [e for e in cand_entries if e in ent_idx]
            if selected:
                basis = "equal_crew_sensitivity"
        else:
            if confirmed_crew and confirmed_crew in ent_idx:
                selected = [confirmed_crew]
                basis = "confirmed_crew"
            elif principal_entry and principal_entry in ent_idx:
                selected = [principal_entry]
                basis = "documented_principal_ac40_entry"

        if selected:
            w = 1.0 / len(selected)
            for e in selected:
                a_mat[t_i, ent_idx[e]] = w
            observed_mask[t_i] = True
            mu_mapped = float(sum(w * float(theta_ent[e]) for e in selected))
            row_cov = float(a_mat[t_i] @ cov_ent @ a_mat[t_i]) if len(entrants) else 0.0
            sd_mapped = math.sqrt(max(0.0, row_cov))
        else:
            mu_mapped, sd_mapped = None, None

        provenance.append({
            "team_id": team,
            "campaign_team_id": spec.get("campaign_team_id", f"ac38:{team}"),
            "team_name": TEAM_NAMES[team],
            "observed": bool(selected),
            "basis": basis,
            "source_entries": [{"entry_id": e, "effect": round(float(theta_ent[e]), 6)} for e in selected],
            "mapped_ac40_mean": round(mu_mapped, 6) if mu_mapped is not None else None,
            "mapped_ac40_sd": round(sd_mapped, 6) if sd_mapped is not None else None,
        })

    return MappingSpec(
        policy=mapping_policy,
        a_matrix=a_mat,
        entry_keys=tuple(entrants),
        provenance=provenance,
        observed_mask=observed_mask,
    )


def _apply_ac75_sir_updates(
    root: Path,
    theta_75: np.ndarray,
    updates: Sequence[dict[str, Any]],
    *,
    issuance_cutoff_utc: str | None,
    rng: np.random.Generator,
    kappa: float = 1.0,
) -> tuple[np.ndarray, list[str], float]:
    """Update target-cycle AC75 draws via importance resampling without mutating historical fit."""
    seen_ids: set[str] = set()
    applied_ids: list[str] = []
    cutoff_dt = parse_utc_iso(issuance_cutoff_utc) if issuance_cutoff_utc else None
    team_idx = {t: i for i, t in enumerate(TEAM_IDS)}
    log_lik = np.zeros(len(theta_75), dtype=float)

    for rec in updates:
        rid = str(rec.get("race_id") or "")
        if not rid or rid in seen_ids:
            raise ValueError(f"Duplicate or missing AC75 update race_id: '{rid}'")
        seen_ids.add(rid)
        ok, reason = is_valid_independent_evidence(
            root, rec.get("evidence"), required_scopes=("match_winner", "full_fleet_order")
        )
        if not ok:
            raise ValueError(f"Unverified AC75 update '{rid}': {reason}")
        avail_dt = parse_utc_iso((rec.get("evidence") or {}).get("available_at_utc"))
        if cutoff_dt is not None and avail_dt is not None and avail_dt > cutoff_dt:
            raise ValueError(f"AC75 update '{rid}' available after issuance cutoff")

        order = rec.get("official_order")
        if order:
            idxs = [team_idx[t] for t in order]
            for s in range(len(idxs) - 1):
                sub = theta_75[:, idxs[s:]] * kappa
                m_sub = np.max(sub, axis=1, keepdims=True)
                lse = m_sub[:, 0] + np.log(np.sum(np.exp(sub - m_sub), axis=1))
                log_lik += sub[:, 0] - lse
        else:
            win = rec["winner"]
            ca, cb = rec["competitor_a"], rec["competitor_b"]
            lose = cb if win == ca else ca
            diff = (theta_75[:, team_idx[win]] - theta_75[:, team_idx[lose]]) * kappa
            log_lik -= np.logaddexp(0.0, -np.clip(diff, -30.0, 30.0))
        applied_ids.append(rid)

    if not applied_ids:
        return theta_75, [], float(len(theta_75))

    lw = log_lik - float(np.max(log_lik))
    w = np.exp(lw)
    w_sum = float(np.sum(w))
    if w_sum <= 0 or not math.isfinite(w_sum):
        raise ValueError("AC75 update importance weights collapsed")
    w /= w_sum
    ess = float(1.0 / np.sum(w ** 2))
    # Systematic resampling preserves joint posterior correlation while staying deterministic
    n = len(theta_75)
    positions = (rng.random() + np.arange(n)) / n
    cdf = np.cumsum(w)
    cdf[-1] = 1.0
    idx = np.searchsorted(cdf, positions)
    return theta_75[idx], applied_ids, ess


def draw_ac38_ac75_worlds(
    root: Path,
    posterior_doc: dict[str, Any],
    ac40_fit: dict[str, Any],
    mapping: MappingSpec,
    *,
    n_worlds: int,
    seed: int = 2027,
    residual_scale: float = 1.0,
    zero_transfer: bool = False,
    ac75_updates: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Jointly draw (beta, tau, theta_40, eps) once per forecast world."""
    if residual_scale < 0 or not math.isfinite(residual_scale):
        raise ValueError("residual_scale must be finite and non-negative")
    rng = np.random.default_rng(seed)
    trans = sample_joint_transfer_parameters(posterior_doc, n_worlds, rng=rng, include_latents=False)
    beta = np.zeros(n_worlds, dtype=float) if zero_transfer else trans["beta"]
    tau = trans["tau"]

    sigma_40 = float(ac40_fit.get("sigma_40", 1.2))
    entrants = list(mapping.entry_keys)
    theta_40_team = rng.normal(0.0, sigma_40, size=(n_worlds, len(TEAM_IDS)))

    if entrants:
        mu_ent = np.array([float(ac40_fit["theta"][e]) for e in entrants], dtype=float)
        cov_ent = np.asarray(ac40_fit["covariance"], dtype=float)
        cov_ent = 0.5 * (cov_ent + cov_ent.T) + 1e-9 * np.eye(len(entrants))
        ent_draws = rng.multivariate_normal(mu_ent, cov_ent, size=n_worlds)
        mapped_draws = ent_draws @ mapping.a_matrix.T
        obs_idx = np.where(mapping.observed_mask)[0]
        theta_40_team[:, obs_idx] = mapped_draws[:, obs_idx]

    eps = rng.normal(0.0, 1.0, size=(n_worlds, len(TEAM_IDS))) * (residual_scale * tau)[:, None]
    theta_75 = beta[:, None] * theta_40_team + eps

    applied_ids: list[str] = []
    ess = float(n_worlds)
    if ac75_updates:
        theta_75, applied_ids, ess = _apply_ac75_sir_updates(
            Path(root), theta_75, ac75_updates,
            issuance_cutoff_utc=ac40_fit.get("issuance_cutoff_utc"),
            rng=rng, kappa=float(ac40_fit.get("kappa", 1.0)),
        )

    return {
        "worlds": theta_75,
        "beta_draws": beta,
        "tau_draws": tau,
        "applied_ac75_updates": applied_ids,
        "effective_sample_size": ess,
    }


def _series_win_prob(p_single: np.ndarray, target: int) -> np.ndarray:
    """Exact binomial first-to-target series win probability given fixed world p_single."""
    q = 1.0 - p_single
    p_pow = p_single ** target
    total = np.zeros_like(p_single)
    for k in range(target):
        total += math.comb(target - 1 + k, k) * p_pow * (q ** k)
    return total


def compute_pairwise_and_series(worlds: np.ndarray) -> dict[str, Any]:
    """Compute pairwise single-match, Bo9 (first to 5), and Bo13 (first to 7) from worlds."""
    n = len(worlds)
    single: dict[str, dict[str, float | None]] = {}
    bo9: dict[str, dict[str, float | None]] = {}
    bo13: dict[str, dict[str, float | None]] = {}
    single_se: dict[str, dict[str, float | None]] = {}

    for i, ti in enumerate(TEAM_IDS):
        single[ti], bo9[ti], bo13[ti], single_se[ti] = {}, {}, {}, {}
        for j, tj in enumerate(TEAM_IDS):
            if i == j:
                single[ti][tj] = None
                bo9[ti][tj] = None
                bo13[ti][tj] = None
                single_se[ti][tj] = None
                continue
            diff = np.clip(worlds[:, i] - worlds[:, j], -30.0, 30.0)
            p_raw = 1.0 / (1.0 + np.exp(-diff))
            p_w = (1.0 - 0.0001) * p_raw + 0.0001 * 0.5
            p_mean = float(np.mean(p_w))
            single[ti][tj] = round(p_mean, 6)
            single_se[ti][tj] = round(float(np.std(p_w, ddof=1) / math.sqrt(n)), 6)
            bo9[ti][tj] = round(float(np.mean(_series_win_prob(p_w, 5))), 6)
            bo13[ti][tj] = round(float(np.mean(_series_win_prob(p_w, 7))), 6)
    return {
        "single_match": single,
        "single_match_mc_se": single_se,
        "series_best_of_9_first_to_5": bo9,
        "series_best_of_13_first_to_7": bo13,
    }


def compute_nested_cup_intervals(
    root: Path,
    posterior_doc: dict[str, Any],
    ac40_fit: dict[str, Any],
    mapping: MappingSpec,
    rules: CupRules,
    *,
    seed: int = 2027,
    residual_scale: float = 1.0,
    zero_transfer: bool = False,
    ac75_updates: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Nested simulation: incrementally refine outer posterior worlds x inner trials until <=0.5pp."""
    r_inner = 200
    outer_totals = (300, 600, 1200)
    max_outer = outer_totals[-1]
    cap_trials = max_outer * r_inner
    scenario = CupScenario(rho=1.0, sigma_multiplier=1.0, match_concentration=1.0, hazard_multiplier=1.0)
    world_res = draw_ac38_ac75_worlds(
        root, posterior_doc, ac40_fit, mapping,
        n_worlds=max_outer, seed=seed + 10_000,
        residual_scale=residual_scale, zero_transfer=zero_transfer,
        ac75_updates=ac75_updates,
    )
    pool_theta = world_res["worlds"]
    mean_map = {t: float(np.mean(pool_theta[:, idx])) for idx, t in enumerate(TEAM_IDS)}
    var_map = {t: float(np.var(pool_theta[:, idx])) for idx, t in enumerate(TEAM_IDS)}

    champ_batches: list[np.ndarray] = []
    unres_batches: list[np.ndarray] = []
    prev_q: dict[str, tuple[float, float, float, float]] | None = None
    history: list[dict[str, Any]] = []
    final_q: dict[str, dict[str, dict[str, float]]] = {}
    converged = False
    max_delta = 1.0
    prev_outer = 0

    for st_idx, m_outer in enumerate(outer_totals):
        batch_outer = m_outer - prev_outer
        rep_theta = np.repeat(pool_theta[prev_outer:m_outer], r_inner, axis=0)
        sim = simulate_cup(
            {}, scenario=scenario, rules=rules, trials=batch_outer * r_inner,
            seed=seed + 20_000 + st_idx * 101,
            posterior_world_draws=rep_theta,
            forecast_prior_mean=mean_map,
            forecast_prior_var=var_map,
            return_trial_outcomes=True,
        )
        champ_batches.append(sim["_trial_outcomes"]["champion"].reshape(batch_outer, r_inner))
        unres_batches.append(sim["_trial_outcomes"]["unresolved"].reshape(batch_outer, r_inner))
        prev_outer = m_outer

        champ = np.vstack(champ_batches)
        unres = np.vstack(unres_batches)
        unres_rate = np.mean(unres, axis=1)

        cur_q: dict[str, tuple[float, float, float, float]] = {}
        stage_intervals: dict[str, dict[str, dict[str, float]]] = {}
        for t_i, team in enumerate(TEAM_IDS):
            lo_m = np.mean((~unres) & (champ == t_i), axis=1)
            hi_m = np.minimum(1.0, lo_m + unres_rate)
            lo_05, lo_95 = np.quantile(lo_m, [0.05, 0.95])
            hi_05, hi_95 = np.quantile(hi_m, [0.05, 0.95])
            cur_q[team] = (float(lo_05), float(lo_95), float(hi_05), float(hi_95))
            stage_intervals[team] = {
                "lower_p05_p95": {"p05": round(float(lo_05), 5), "p50": round(float(np.median(lo_m)), 5), "p95": round(float(lo_95), 5)},
                "upper_p05_p95": {"p05": round(float(hi_05), 5), "p50": round(float(np.median(hi_m)), 5), "p95": round(float(hi_95), 5)},
            }

        if prev_q is not None:
            max_delta = max(
                max(abs(cur_q[t][k] - prev_q[t][k]) for k in range(4))
                for t in TEAM_IDS
            )
            converged = max_delta <= 0.005
        history.append({
            "outer_worlds": m_outer,
            "inner_trials_per_world": r_inner,
            "total_trials": m_outer * r_inner,
            "max_endpoint_delta_vs_prev": round(max_delta, 6) if prev_q is not None else None,
            "within_0_5pp": bool(prev_q is not None and converged),
        })
        prev_q = cur_q
        final_q = stage_intervals
        if converged:
            break

    reason = (
        f"Posterior 90% interval endpoints stabilized within {max_delta * 100:.2f} pp (<= 0.50 pp target)."
        if converged
        else f"Reached nested simulation computation cap ({cap_trials} trials); final endpoint shift was {max_delta * 100:.2f} pp (> 0.50 pp)."
    )
    return {
        "policy": "nested_outer_posterior_inner_tournament",
        "quantiles": "5th and 95th percentiles across outer posterior parameter worlds",
        "stabilization_target_pp": 0.5,
        "computation_cap_trials": cap_trials,
        "converged_within_0_5pp": converged,
        "final_max_endpoint_delta": round(max_delta, 6),
        "reason": reason,
        "refinement_history": history,
        "intervals_by_team": final_q,
    }
