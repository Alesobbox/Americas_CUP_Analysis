"""Frozen-split chronological and LOTO backtests with 1-SE telemetry selection."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .ac38_evidence import is_valid_independent_evidence
from .ac38_telemetry import (
    TELEM_DIMS,
    apply_fold_standardization,
    compute_lagged_features_before,
    fit_fold_standardization,
    fit_pl_with_telemetry,
    load_or_build_telemetry_cache,
    predict_pl_win_probs,
)
from .transfer_evidence import BOAT_TO_AC37_TEAM, SHARED_AC37_TEAMS
from .transfer_num import evaluate_grid, helmert_contrasts


def _logistic_arr(x: np.ndarray) -> np.ndarray:
    c = np.clip(x, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-c))


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 30.0), -30.0)))


def _calibration_stats(probs: Sequence[float], outcomes: Sequence[float]) -> dict[str, Any]:
    if len(probs) < 4:
        return {"slope": None, "intercept": None, "mean_pred": float(np.mean(probs)) if probs else None, "mean_obs": float(np.mean(outcomes)) if outcomes else None, "bins": []}
    p_arr = np.clip(np.asarray(probs, dtype=float), 1e-6, 1.0 - 1e-6)
    y_arr = np.asarray(outcomes, dtype=float)
    logits = np.log(p_arr / (1.0 - p_arr))
    a, b = 0.0, 1.0
    for _ in range(30):
        pred = _logistic_arr(a + b * logits)
        w = pred * (1.0 - pred) + 1e-9
        g0 = float(np.sum(pred - y_arr))
        g1 = float(np.sum((pred - y_arr) * logits))
        h00 = float(np.sum(w)) + 1e-4
        h01 = float(np.sum(w * logits))
        h11 = float(np.sum(w * (logits ** 2))) + 1e-4
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        da = (h11 * g0 - h01 * g1) / det
        db = (-h01 * g0 + h00 * g1) / det
        a -= da
        b -= db
        if abs(da) + abs(db) < 1e-7:
            break

    bins = []
    for lo, hi in ((0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)):
        mask = (p_arr >= lo) & (p_arr < hi)
        if np.any(mask):
            bins.append({
                "range": [lo, min(hi, 1.0)],
                "count": int(np.sum(mask)),
                "mean_pred": round(float(np.mean(p_arr[mask])), 4),
                "mean_obs": round(float(np.mean(y_arr[mask])), 4),
            })
    return {
        "slope": round(b, 4),
        "intercept": round(a, 4),
        "mean_pred": round(float(np.mean(p_arr)), 4),
        "mean_obs": round(float(np.mean(y_arr)), 4),
        "bins": bins,
    }


def _grouped_summary(rows: Sequence[dict[str, Any]], group_key: str) -> dict[str, Any]:
    if not rows:
        return {"n_obs": 0, "n_groups": 0, "mean_log_loss": None, "se_log_loss": None, "mean_brier": None}
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row[group_key]), []).append(row)
    g_losses = [float(np.mean([r["log_loss"] for r in items])) for items in groups.values()]
    g_briers = [float(np.mean([r["brier"] for r in items])) for items in groups.values()]
    n_g = len(g_losses)
    se_ll = float(np.std(g_losses, ddof=1) / math.sqrt(n_g)) if n_g > 1 else 0.0
    se_br = float(np.std(g_briers, ddof=1) / math.sqrt(n_g)) if n_g > 1 else 0.0
    cov50 = [float(np.mean([r["cov50"] for r in items if r.get("cov50") is not None])) for items in groups.values() if any(r.get("cov50") is not None for r in items)]
    cov90 = [float(np.mean([r["cov90"] for r in items if r.get("cov90") is not None])) for items in groups.values() if any(r.get("cov90") is not None for r in items)]
    cal_p: list[float] = []
    cal_y: list[float] = []
    for row in rows:
        pairs = row.get("cal_pairs")
        if pairs:
            for p_val, y_val in pairs:
                cal_p.append(float(p_val))
                cal_y.append(float(y_val))
        else:
            cal_p.append(float(row["p_event"]))
            cal_y.append(float(row["y_event"]))
    return {
        "n_obs": len(rows),
        "n_groups": n_g,
        "mean_log_loss": round(float(np.mean([r["log_loss"] for r in rows])), 5),
        "grouped_mean_log_loss": round(float(np.mean(g_losses)), 5),
        "grouped_se_log_loss": round(se_ll, 5),
        "mean_brier": round(float(np.mean([r["brier"] for r in rows])), 5),
        "grouped_se_brier": round(se_br, 5),
        "coverage_50": round(float(np.mean(cov50)), 4) if cov50 else None,
        "coverage_90": round(float(np.mean(cov90)), 4) if cov90 else None,
        "calibration": _calibration_stats(cal_p, cal_y),
    }


def _paired_grouped_diff(
    rows_a: Sequence[dict[str, Any]], rows_b: Sequence[dict[str, Any]], group_key: str
) -> dict[str, Any]:
    """Compute grouped mean difference (rows_b - rows_a); negative favors rows_b."""
    by_g_a: dict[str, list[float]] = {}
    by_g_b: dict[str, list[float]] = {}
    for ra, rb in zip(rows_a, rows_b):
        g = str(ra[group_key])
        by_g_a.setdefault(g, []).append(float(ra["log_loss"]))
        by_g_b.setdefault(g, []).append(float(rb["log_loss"]))
    diffs = [float(np.mean(by_g_b[g]) - np.mean(by_g_a[g])) for g in by_g_a]
    n_g = len(diffs)
    mean_d = float(np.mean(diffs)) if n_g else 0.0
    se_d = float(np.std(diffs, ddof=1) / math.sqrt(n_g)) if n_g > 1 else 0.0
    return {
        "n_groups": n_g,
        "mean_diff_log_loss": round(mean_d, 6),
        "grouped_se_diff": round(se_d, 6),
        "improves_by_more_than_1se": bool(n_g >= 2 and mean_d < -se_d),
    }


def _load_ac40_chronological_races(root: Path) -> list[dict[str, Any]]:
    races: list[dict[str, Any]] = []
    ac37 = json.loads((root / "docs" / "ac37_ac40_2023_results.json").read_text(encoding="utf-8"))
    for r in ac37.get("races", []):
        if r.get("status") != "completed":
            continue
        order = r.get("official_order") or []
        if len(order) < 2:
            continue
        avail = (r.get("evidence") or {}).get("available_at_utc") or f"{r['date']}T18:00:00Z"
        races.append({
            "race_id": r["race_id"],
            "cycle": "ac37",
            "date": r["date"],
            "available_at_utc": avail,
            "order": list(order),
        })
    ac38 = json.loads((root / "docs" / "official_results_ac38_prelims.json").read_text(encoding="utf-8"))
    for r in ac38.get("races", []):
        order = r.get("official_order") or r.get("on_water_finish_order") or []
        if len(order) < 2:
            continue
        ev = r.get("evidence") or {}
        avail = (
            (ev.get("independent_anchor") or {}).get("available_at_utc")
            or (ev.get("telemetry_reconstruction") or {}).get("available_at_utc")
            or f"{r['date']}T18:00:00Z"
        )
        races.append({
            "race_id": r["race_id"],
            "cycle": "ac38",
            "date": r["date"],
            "available_at_utc": avail,
            "order": list(order),
        })
    races.sort(key=lambda item: (item["cycle"], item["available_at_utc"], item["race_id"]))
    return races


def _pl_rank_coverage(
    rng: np.random.Generator,
    fit_doc: dict[str, Any] | None,
    order: Sequence[str],
    z_map: dict[str, np.ndarray] | None = None,
    m_map: dict[str, np.ndarray] | None = None,
    n_draws: int = 400,
) -> tuple[float, float]:
    """Fraction of finishers whose actual finish rank falls in 50% and 90% posterior-predictive rank intervals."""
    k_field = len(order)
    gumbels = rng.gumbel(size=(n_draws, k_field))
    if fit_doc is None:
        utils = gumbels
    else:
        entrants = fit_doc["entrants"]
        n_ent = len(entrants)
        ent_idx = [entrants.index(e) for e in order]
        cov_full = np.asarray(fit_doc["covariance"], dtype=float)
        if z_map is not None and m_map is not None:
            gamma_mu = np.array([fit_doc["gamma"].get(d, 0.0) for d in TELEM_DIMS], dtype=float)
            mu_full = np.concatenate([np.array([fit_doc["theta"][e] for e in entrants], dtype=float), gamma_mu])
            draws_full = rng.multivariate_normal(mu_full, cov_full, size=n_draws)
            x_mat = np.array([z_map[e] * m_map[e] for e in order], dtype=float)
            lin = draws_full[:, ent_idx] + draws_full[:, n_ent:] @ x_mat.T
        else:
            mu_sub = np.array([fit_doc["theta"][e] for e in order], dtype=float)
            lin = rng.multivariate_normal(mu_sub, cov_full[np.ix_(ent_idx, ent_idx)], size=n_draws)
        utils = lin + gumbels

    in50, in90 = 0, 0
    for j in range(k_field):
        ranks_j = 1 + np.sum(utils > utils[:, [j]], axis=1)
        q05, q25, q75, q95 = np.quantile(ranks_j, [0.05, 0.25, 0.75, 0.95])
        actual_rank = float(j + 1)
        in50 += int(q25 <= actual_rank <= q75)
        in90 += int(q05 <= actual_rank <= q95)
    return in50 / k_field, in90 / k_field


def backtest_ac40_chronological(root: Path, telemetry_cache: dict[str, Any]) -> dict[str, Any]:
    """Expanding chronological AC40 backtest comparing results-only vs results+telemetry."""
    all_races = _load_ac40_chronological_races(root)
    telem_races = telemetry_cache.get("races", [])
    rows_uniform, rows_results, rows_telem = [], [], []
    rng = np.random.default_rng(2027)

    for cycle in ("ac37", "ac38"):
        c_races = [r for r in all_races if r["cycle"] == cycle]
        entrants = sorted({e for r in c_races for e in r["order"]})
        for idx in range(1, len(c_races)):
            target = c_races[idx]
            train = [r for r in c_races[:idx] if r["available_at_utc"] < target["available_at_utc"]]
            if not train:
                continue
            train_orders = [r["order"] for r in train]
            train_lagged = [
                compute_lagged_features_before(
                    telem_races, cycle=cycle, cutoff_utc=r["available_at_utc"], entrants=r["order"]
                )
                for r in train
            ]
            std_stats = fit_fold_standardization(train_lagged, train_orders)
            z_rows, m_rows = [], []
            zero_z = [{e: np.zeros(len(TELEM_DIMS)) for e in r["order"]} for r in train]
            zero_m = [{e: np.zeros(len(TELEM_DIMS), dtype=bool) for e in r["order"]} for r in train]
            for lagged_r, r in zip(train_lagged, train):
                zr, mr = apply_fold_standardization(lagged_r, std_stats, r["order"])
                z_rows.append(zr)
                m_rows.append(mr)

            fit_res = fit_pl_with_telemetry(train_orders, zero_z, zero_m, entrants=entrants)
            fit_tel = fit_pl_with_telemetry(train_orders, z_rows, m_rows, entrants=entrants)

            targ_lagged = compute_lagged_features_before(
                telem_races, cycle=cycle, cutoff_utc=target["available_at_utc"], entrants=target["order"]
            )
            targ_z, targ_m = apply_fold_standardization(targ_lagged, std_stats, target["order"])

            p_res = predict_pl_win_probs(fit_res, target["order"])
            p_tel = predict_pl_win_probs(fit_tel, target["order"], targ_z, targ_m)
            winner = target["order"][0]
            k_field = len(target["order"])
            p_uni = {e: 1.0 / k_field for e in target["order"]}

            cov_uni = _pl_rank_coverage(rng, None, target["order"])
            cov_res = _pl_rank_coverage(rng, fit_res, target["order"])
            cov_tel = _pl_rank_coverage(rng, fit_tel, target["order"], targ_z, targ_m)

            for bucket, probs, (c50, c90) in (
                (rows_uniform, p_uni, cov_uni),
                (rows_results, p_res, cov_res),
                (rows_telem, p_tel, cov_tel),
            ):
                pw = float(probs[winner])
                brier = float((1.0 - pw) ** 2 + sum(float(probs[e]) ** 2 for e in target["order"] if e != winner))
                bucket.append({
                    "race_id": target["race_id"],
                    "cycle": cycle,
                    "group": f"{cycle}:{target['date']}",
                    "log_loss": -math.log(max(pw, 1e-12)),
                    "brier": brier,
                    "p_event": pw,
                    "y_event": 1.0,
                    "cal_pairs": [(float(probs[e]), 1.0 if e == winner else 0.0) for e in target["order"]],
                    "cov50": c50,
                    "cov90": c90,
                })

    return {
        "uniform": _grouped_summary(rows_uniform, "group"),
        "results_only": _grouped_summary(rows_results, "group"),
        "results_plus_telemetry": _grouped_summary(rows_telem, "group"),
        "telem_vs_results_diff": _paired_grouped_diff(rows_results, rows_telem, "group"),
    }


def _load_ac37_data(root: Path) -> tuple[list[list[str]], list[dict[str, Any]]]:
    ac40_doc = json.loads((root / "docs" / "ac37_ac40_2023_results.json").read_text(encoding="utf-8"))
    ac40_orders = [
        [BOAT_TO_AC37_TEAM[t] for t in r["official_order"] if t in BOAT_TO_AC37_TEAM]
        for r in ac40_doc.get("races", [])
        if r.get("status") == "completed" and len(r.get("official_order", [])) >= 2
    ]
    ac75_doc = json.loads((root / "docs" / "ac37_results.json").read_text(encoding="utf-8"))
    ac75_matches = []
    for r in ac75_doc.get("races", []):
        if r.get("status", "completed") != "completed":
            continue
        ok, _ = is_valid_independent_evidence(root, r.get("evidence"), required_scopes=("match_winner",))
        if not ok:
            continue
        ca, cb, win = r["competitor_a"], r["competitor_b"], r["winner"]
        if ca in SHARED_AC37_TEAMS and cb in SHARED_AC37_TEAMS and win in (ca, cb):
            loser = cb if win == ca else ca
            ac75_matches.append({"race_id": r["race_id"], "date": r["date"], "winner": win, "loser": loser})
    ac75_matches.sort(key=lambda m: (m["date"], m["race_id"]))
    return ac40_orders, ac75_matches


def _order_to_stages(order: Sequence[str], q_mat: np.ndarray, c_map: dict[str, int]) -> list[np.ndarray]:
    idxs = [c_map[t] for t in order if t in c_map]
    stages = []
    for k in range(len(idxs) - 1):
        rem = idxs[k:]
        stages.append(np.array([q_mat[rem[0]] - q_mat[j] for j in rem], dtype=float))
    return stages


def _fit_bt_carryover(train_matches: Sequence[dict[str, Any]], prior_sd: float = 1.0) -> dict[str, float]:
    c_map = {t: i for i, t in enumerate(SHARED_AC37_TEAMS)}
    q_mat = helmert_contrasts(6)
    vecs = [q_mat[c_map[m["winner"]]] - q_mat[c_map[m["loser"]]] for m in train_matches]
    z = np.zeros(5, dtype=float)
    prec = (1.0 / (prior_sd ** 2)) * np.eye(5)
    if vecs:
        for _ in range(30):
            grad = prec @ z
            hess = np.copy(prec)
            for d in vecs:
                sig = _logistic(float(np.dot(d, z)))
                grad += -(1.0 - sig) * d
                hess += sig * (1.0 - sig) * np.outer(d, d)
            step = np.linalg.solve(hess, grad)
            z -= step
            if float(np.linalg.norm(step)) < 1e-8:
                break
    theta = q_mat @ z
    return dict(zip(SHARED_AC37_TEAMS, theta.tolist()))


def _day_predictive_coverage(
    rng: np.random.Generator,
    test_m: Sequence[dict[str, Any]],
    ctx: dict[str, Any],
    n_sim: int = 800,
) -> tuple[float, float]:
    q_mat, c_map = ctx["q_mat"], ctx["c_map"]
    w_act, z_flat, chol = ctx["w_act"], ctx["z_flat"], ctx["chol"]
    d_canon = []
    actual_wins = 0.0
    for m in test_m:
        a, b = (m["winner"], m["loser"]) if m["winner"] < m["loser"] else (m["loser"], m["winner"])
        d_canon.append(q_mat[c_map[a]] - q_mat[c_map[b]])
        actual_wins += 1.0 if m["winner"] == a else 0.0
    d_mat = np.asarray(d_canon, dtype=float)
    cell_idx = rng.choice(len(w_act), size=n_sim, p=w_act)
    eps = rng.standard_normal((n_sim, z_flat.shape[1]))
    z_draws = z_flat[cell_idx] + np.einsum("nij,nj->ni", chol[cell_idx], eps)
    p_mat = _logistic_arr(z_draws @ d_mat.T)
    sim_wins = np.sum(rng.random(p_mat.shape) < p_mat, axis=1)
    q05, q25, q75, q95 = np.quantile(sim_wins, [0.05, 0.25, 0.75, 0.95])
    return float(q25 <= actual_wins <= q75), float(q05 <= actual_wins <= q95)


def backtest_ac75_chronological(root: Path) -> dict[str, Any]:
    """Expanding chronological AC75 match backtest grouped by racing day."""
    ac40_orders, ac75_matches = _load_ac37_data(root)
    q_mat = helmert_contrasts(6)
    c_map = {t: i for i, t in enumerate(SHARED_AC37_TEAMS)}
    d40_stages = [st for order in ac40_orders for st in _order_to_stages(order, q_mat, c_map)]

    pl40 = fit_pl_with_telemetry(
        ac40_orders,
        [{t: np.zeros(4) for t in order} for order in ac40_orders],
        [{t: np.zeros(4, dtype=bool) for t in order} for order in ac40_orders],
        entrants=SHARED_AC37_TEAMS,
    )["theta"]

    betas = np.linspace(-2.5, 3.5, 37)
    etas = np.linspace(-2.5, 1.5, 33)
    dates = sorted({m["date"] for m in ac75_matches})
    rows = {k: [] for k in ("no_transfer", "naive_ac40_strength", "ac75_carryover", "transfer_results_only")}
    rng = np.random.default_rng(2027)

    for d in dates:
        train_m = [m for m in ac75_matches if m["date"] < d]
        test_m = [m for m in ac75_matches if m["date"] == d]
        carry = _fit_bt_carryover(train_m)
        d75_vecs = np.array([q_mat[c_map[m["winner"]]] - q_mat[c_map[m["loser"]]] for m in train_m], dtype=float) if train_m else np.zeros((0, 5))
        _, w, _, grid_info = evaluate_grid(betas, etas, d40_stages, d75_vecs, sigma_40=1.2, kappa=1.0, return_conditionals=True)
        z_grid = grid_info["z_grid"]
        h_grid = grid_info["h_grid"]

        flat_w = w.ravel()
        active = np.where(flat_w > 1e-5)[0]
        w_act = flat_w[active] / float(np.sum(flat_w[active]))
        z_flat = z_grid.reshape(-1, 10)[active, 5:]
        c_flat = np.array([np.linalg.inv(h_grid.reshape(-1, 10, 10)[idx])[5:, 5:] for idx in active])
        chol = np.linalg.cholesky(c_flat + 1e-10 * np.eye(5)[None, :, :])
        day_cov50, day_cov90 = _day_predictive_coverage(
            rng, test_m, {"q_mat": q_mat, "c_map": c_map, "w_act": w_act, "z_flat": z_flat, "chol": chol}
        )

        for m in test_m:
            diff_q = q_mat[c_map[m["winner"]]] - q_mat[c_map[m["loser"]]]
            p_naive = _logistic(pl40[m["winner"]] - pl40[m["loser"]])
            p_carry = _logistic(carry[m["winner"]] - carry[m["loser"]])
            p_notrans = 0.5

            mu_d = z_flat @ diff_q
            var_d = np.einsum("i,kij,j->k", diff_q, c_flat, diff_q)
            denom = np.sqrt(1.0 + (math.pi / 8.0) * np.maximum(var_d, 0.0))
            p_cells = _logistic_arr(mu_d / denom)
            p_trans = float(np.dot(w_act, p_cells))
            p_obs_like = min(max(p_trans, 1e-12), 1.0 - 1e-12)
            side_a = m["winner"] < m["loser"]
            y_cal = 1.0 if side_a else 0.0

            for name, pv in (("no_transfer", p_notrans), ("naive_ac40_strength", p_naive), ("ac75_carryover", p_carry), ("transfer_results_only", p_obs_like)):
                p_cal = pv if side_a else (1.0 - pv)
                rows[name].append({
                    "race_id": m["race_id"],
                    "group": d,
                    "log_loss": -math.log(max(pv, 1e-12)),
                    "brier": (1.0 - pv) ** 2,
                    "p_event": p_cal,
                    "y_event": y_cal,
                    "cov50": day_cov50 if name == "transfer_results_only" else None,
                    "cov90": day_cov90 if name == "transfer_results_only" else None,
                })

    return {k: _grouped_summary(v, "group") for k, v in rows.items()}


def _loto_team_coverage(
    rng: np.random.Generator,
    held_idx: int,
    opp_indices: Sequence[int],
    actual_held_wins: int,
    ctx: dict[str, Any],
    telem_shift: float = 0.0,
) -> tuple[float, float]:
    n_sim = 1000
    q_mat = ctx["q_mat"]
    w_act, b_act, tau_act = ctx["w_act"], ctx["b_act"], ctx["tau_act"]
    z_flat, chol = ctx["z_flat"], ctx["chol"]
    opp_arr = np.asarray(opp_indices, dtype=int)
    cell_idx = rng.choice(len(w_act), size=n_sim, p=w_act)
    std_norm = rng.standard_normal((n_sim, z_flat.shape[1]))
    u_draws = z_flat[cell_idx] + np.einsum("nij,nj->ni", chol[cell_idx], std_norm)
    eps = rng.normal(0.0, tau_act[cell_idx])
    th_held = b_act[cell_idx] * ((u_draws[:, :5] @ q_mat[held_idx]) + telem_shift) + eps
    th_opp = u_draws[:, 5:] @ q_mat[opp_arr].T
    p_mat = _logistic_arr(th_held[:, None] - th_opp)
    sim_wins = np.sum(rng.random(p_mat.shape) < p_mat, axis=1)
    q05, q25, q75, q95 = np.quantile(sim_wins, [0.05, 0.25, 0.75, 0.95])
    return float(q25 <= actual_held_wins <= q75), float(q05 <= actual_held_wins <= q95)


def backtest_ac75_loto(root: Path, telemetry_cache: dict[str, Any]) -> dict[str, Any]:
    """Leave-One-Team's-AC75-Outcomes-Out cross-validation across all 6 AC37 teams."""
    ac40_orders, ac75_matches = _load_ac37_data(root)
    q_mat = helmert_contrasts(6)
    c_map = {t: i for i, t in enumerate(SHARED_AC37_TEAMS)}
    d40_stages = [st for order in ac40_orders for st in _order_to_stages(order, q_mat, c_map)]

    ac37_chron = [r for r in _load_ac40_chronological_races(root) if r["cycle"] == "ac37"]
    telem_races = telemetry_cache.get("races", [])
    tr_orders = [[BOAT_TO_AC37_TEAM[t] for t in r["order"] if t in BOAT_TO_AC37_TEAM] for r in ac37_chron]
    tr_lagged = [compute_lagged_features_before(telem_races, cycle="ac37", cutoff_utc=r["available_at_utc"], entrants=ord_) for r, ord_ in zip(ac37_chron, tr_orders)]
    std_37 = fit_fold_standardization(tr_lagged, tr_orders)
    z_37, m_37 = [], []
    for lag_r, ord_ in zip(tr_lagged, tr_orders):
        zr, mr = apply_fold_standardization(lag_r, std_37, ord_)
        z_37.append(zr)
        m_37.append(mr)
    fit_pl_res = fit_pl_with_telemetry(tr_orders, [{t: np.zeros(4) for t in o} for o in tr_orders], [{t: np.zeros(4, dtype=bool) for t in o} for o in tr_orders], entrants=SHARED_AC37_TEAMS)
    fit_pl_tel = fit_pl_with_telemetry(tr_orders, z_37, m_37, entrants=SHARED_AC37_TEAMS)

    theta_40_res = np.array([fit_pl_res["theta"][t] for t in SHARED_AC37_TEAMS], dtype=float)
    gamma_tel = np.array([fit_pl_tel["gamma"][d] for d in TELEM_DIMS], dtype=float)
    final_lagged = compute_lagged_features_before(telem_races, cycle="ac37", cutoff_utc="2024-08-01T00:00:00Z", entrants=SHARED_AC37_TEAMS)
    z_fin, m_fin = apply_fold_standardization(final_lagged, std_37, SHARED_AC37_TEAMS)
    total_tel = np.array([fit_pl_tel["theta"][t] + float(np.dot(gamma_tel, z_fin[t] * m_fin[t])) for t in SHARED_AC37_TEAMS], dtype=float)
    total_tel -= float(np.mean(total_tel))
    telem_delta_40 = total_tel - theta_40_res

    betas = np.linspace(-2.5, 3.5, 37)
    etas = np.linspace(-2.5, 1.5, 33)
    rows = {k: [] for k in ("no_transfer", "naive_ac40_strength", "results_only_transfer", "results_plus_telemetry_transfer")}
    rng = np.random.default_rng(2027)

    for held_team in SHARED_AC37_TEAMS:
        held_idx = c_map[held_team]
        train_m = [m for m in ac75_matches if held_team not in (m["winner"], m["loser"])]
        test_m = [m for m in ac75_matches if held_team in (m["winner"], m["loser"])]
        if not test_m:
            continue
        carry = _fit_bt_carryover(train_m)
        d75_vecs = np.array([q_mat[c_map[m["winner"]]] - q_mat[c_map[m["loser"]]] for m in train_m], dtype=float)
        _, w, _, grid_info = evaluate_grid(betas, etas, d40_stages, d75_vecs, sigma_40=1.2, kappa=1.0, return_conditionals=True)
        flat_w = w.ravel()
        active = np.where(flat_w > 1e-5)[0]
        w_act = flat_w[active] / float(np.sum(flat_w[active]))
        b_grid, e_grid = np.meshgrid(betas, etas, indexing="ij")
        b_act = b_grid.ravel()[active]
        tau_act = np.exp(e_grid.ravel()[active])
        z_flat = grid_info["z_grid"].reshape(-1, 10)[active]
        c_flat = np.array([np.linalg.inv(grid_info["h_grid"].reshape(-1, 10, 10)[idx]) for idx in active])

        th40_mean = z_flat[:, :5] @ q_mat.T
        th75_mean = z_flat[:, 5:] @ q_mat.T
        opp_indices = [c_map[m["loser"]] if m["winner"] == held_team else c_map[m["winner"]] for m in test_m]
        actual_held_wins = sum(1 for m in test_m if m["winner"] == held_team)
        chol_full = np.linalg.cholesky(c_flat + 1e-10 * np.eye(10)[None, :, :])
        loto_ctx = {"q_mat": q_mat, "w_act": w_act, "b_act": b_act, "tau_act": tau_act, "z_flat": z_flat, "chol": chol_full}
        res_cov50, res_cov90 = _loto_team_coverage(rng, held_idx, opp_indices, actual_held_wins, loto_ctx, 0.0)
        tel_cov50, tel_cov90 = _loto_team_coverage(rng, held_idx, opp_indices, actual_held_wins, loto_ctx, float(telem_delta_40[held_idx]))

        for m in test_m:
            wi, li = c_map[m["winner"]], c_map[m["loser"]]
            opp_idx = li if wi == held_idx else wi
            sgn = 1.0 if wi == held_idx else -1.0

            p_notrans = _logistic(sgn * (0.0 - carry[SHARED_AC37_TEAMS[opp_idx]]) / math.sqrt(1.0 + math.pi / 8.0))
            p_naive = _logistic(theta_40_res[wi] - theta_40_res[li])

            mean_held = b_act * th40_mean[:, held_idx]
            mean_opp = th75_mean[:, opp_idx]
            v_vec = np.zeros((len(active), 10), dtype=float)
            v_vec[:, :5] = b_act[:, None] * q_mat[held_idx][None, :]
            v_vec[:, 5:] = -q_mat[opp_idx][None, :]
            quad_var = np.einsum("ki,kij,kj->k", v_vec, c_flat, v_vec)
            tot_var = (tau_act ** 2) + np.maximum(quad_var, 0.0)
            denom = np.sqrt(1.0 + (math.pi / 8.0) * tot_var)

            p_res_cells = _logistic_arr(sgn * (mean_held - mean_opp) / denom)
            p_res = float(np.dot(w_act, p_res_cells))

            mean_held_tel = b_act * (th40_mean[:, held_idx] + telem_delta_40[held_idx])
            p_tel_cells = _logistic_arr(sgn * (mean_held_tel - mean_opp) / denom)
            p_tel = float(np.dot(w_act, p_tel_cells))

            y_cal = 1.0 if wi == held_idx else 0.0
            for name, pv in (
                ("no_transfer", p_notrans),
                ("naive_ac40_strength", p_naive),
                ("results_only_transfer", p_res),
                ("results_plus_telemetry_transfer", p_tel),
            ):
                p_cal = pv if wi == held_idx else (1.0 - pv)
                cov50 = res_cov50 if name == "results_only_transfer" else (tel_cov50 if name == "results_plus_telemetry_transfer" else None)
                cov90 = res_cov90 if name == "results_only_transfer" else (tel_cov90 if name == "results_plus_telemetry_transfer" else None)
                rows[name].append({
                    "race_id": m["race_id"],
                    "group": held_team,
                    "log_loss": -math.log(max(pv, 1e-12)),
                    "brier": (1.0 - pv) ** 2,
                    "p_event": p_cal,
                    "y_event": y_cal,
                    "cov50": cov50,
                    "cov90": cov90,
                })

    return {
        **{k: _grouped_summary(v, "group") for k, v in rows.items()},
        "telem_vs_results_diff": _paired_grouped_diff(rows["results_only_transfer"], rows["results_plus_telemetry_transfer"], "group"),
    }


def run_ac38_backtest(root: Path, *, write: bool = True, verbose: bool = False) -> dict[str, Any]:
    """Run all frozen-split backtests and apply the 1-SE telemetry selection rule."""
    root = Path(root)
    telemetry_cache = load_or_build_telemetry_cache(root, verbose=verbose)
    ac40_eval = backtest_ac40_chronological(root, telemetry_cache)
    ac75_eval = backtest_ac75_chronological(root)
    loto_eval = backtest_ac75_loto(root, telemetry_cache)

    ac40_1se = ac40_eval["telem_vs_results_diff"]["improves_by_more_than_1se"]
    loto_1se = loto_eval["telem_vs_results_diff"]["improves_by_more_than_1se"]
    selected_candidate = "results_plus_telemetry" if (ac40_1se and loto_1se) else "results_only"

    report = {
        "schema_version": "ac38-backtest-report-1",
        "selection_rule": "1-SE grouped improvement on both AC40 chronological and AC75 LOTO log loss",
        "selected_candidate": selected_candidate,
        "telemetry_retained": selected_candidate == "results_plus_telemetry",
        "ac40_chronological": ac40_eval,
        "ac75_chronological": ac75_eval,
        "ac75_loto": loto_eval,
    }
    if write:
        out = root / ".forecast" / "ac38" / "backtest_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
