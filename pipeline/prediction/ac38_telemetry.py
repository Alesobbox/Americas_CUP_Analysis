"""Lagged AC40 telemetry feature adapter reusing historical_analysis.py metrics."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from pipeline.analytics import AnalyticsEngine
from pipeline.historical_analysis import attach_performance_analysis, build_race_analysis
from pipeline.ingest import IngestionPipeline
from pipeline.manoeuvres import ManoeuvreDetector
from pipeline.reconstruction import RaceReconstructionEngine

from .ac38_evidence import parse_utc_iso

TELEM_DIMS = ("upwind_vmg", "downwind_vmg", "tack_retention", "gybe_retention")
TELEM_PRIOR_SD = 0.25

VNR_CODE_MAP = {
    "NZL": "ETNZ",
    "GBR": "INEOS",
    "ITA": "LUNA_ROSSA",
    "USA": "AMERICAN_MAGIC",
    "SUI": "ALINGHI",
    "FRA": "ORIENT_EXPRESS",
}

VNR_JSONL_FILES = {
    "ac37_ac40_vnr_r1": "2023-09-16 VNR 1.jsonl",
    "ac37_ac40_vnr_r2": "2023-09-16 VNR 2.jsonl",
    "ac37_ac40_vnr_r3": "2023-09-17 VNR 3.jsonl",
    "ac37_ac40_vnr_r4": "2023-09-17 VNR 4.jsonl",
    "ac37_ac40_vnr_r5": "2023-09-17 VNR 5.jsonl",
}


def extract_dims_from_analysis(detail: dict, code_map: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Extract 4 dimensionless peer-relative metrics and availability masks without zero-imputation."""
    boats_out: dict[str, dict[str, Any]] = {}
    for boat in detail.get("boats", []):
        raw_code = str(boat.get("team_code") or "")
        code = code_map.get(raw_code, raw_code) if code_map else raw_code
        dims = {d["id"]: d for d in (boat.get("performance") or {}).get("dimensions", []) if isinstance(d, dict)}
        values: dict[str, float | None] = {}
        available: dict[str, bool] = {}
        for dim in TELEM_DIMS:
            item = dims.get(dim, {})
            val = item.get("index")
            ok = isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val))
            values[dim] = round(float(val), 6) if ok else None
            available[dim] = bool(ok)
        boats_out[code] = {"values": values, "available": available}
    return boats_out


def _patch_out_of_venue_marks(ing: Any) -> None:
    targets = {t["asset_id"]: t["location"] for t in ing.session.asset_targets if t.get("location")}
    xs = [b.x[0] for b in ing.boats.values() if b.x]
    ys = [b.y[0] for b in ing.boats.values() if b.y]
    if not xs or not ys:
        return
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    from pipeline.projection import wgs84_to_metric
    for m in ing.marks.values():
        loc = targets.get(m.asset_id)
        if loc and m.x and (abs(m.x[0] - cx) > 20_000 or abs(m.y[0] - cy) > 20_000):
            tx, ty = wgs84_to_metric(
                loc["y"], loc["x"],
                lat0=ing.session.origin_lat, lon0=ing.session.origin_lon,
                k_lat=ing.session.k_lat, k_lon=ing.session.k_lon,
            )
            m.x = [tx] * len(m.x)
            m.y = [ty] * len(m.y)


def _process_ac37_vnr_race(jsonl_path: Path, race_doc: dict) -> dict[str, dict[str, Any]]:
    ing = IngestionPipeline(str(jsonl_path)).process()
    _patch_out_of_venue_marks(ing)
    rec_eng = RaceReconstructionEngine(
        gun_time_ms=ing.session.race_start_ms,
        window_start_ms=ing.session.window_start_ms,
        window_end_ms=ing.session.window_end_ms,
        course_axis_deg=ing.session.course_axis_deg,
        course_sequences=ing.session.course_sequences,
        nominal_leg_length_m=ing.session.course_length_m,
    )
    rec = rec_eng.process(ing.boats, ing.marks, ing.grid_timestamps_ms, ing.competitor_events)
    total_legs = max(1, len(ing.session.course_sequences) - 1) if ing.session.course_sequences else 4
    for code, comp in rec.competitors.items():
        if comp.start.ocs or comp.gates:
            continue
        boat = ing.boats[code]
        gc_all = rec_eng.reconstruct_geometric_crossings_for_boat(
            boat.x, boat.y, boat.heading, ing.grid_timestamps_ms, ing.marks
        )
        gc_legs = [g for g in gc_all if g.leg >= 1]
        if gc_legs:
            comp.gates = gc_legs
            fin = next((g for g in gc_legs if g.leg == total_legs), None)
            if fin is not None:
                comp.finish_time_ms = fin.crossing_time
                comp.elapsed_s = (fin.crossing_time - ing.session.race_start_ms) / 1000.0
                comp.classification = "FINISHED"
    det = ManoeuvreDetector(sample_interval_ms=100)
    ana = AnalyticsEngine(
        gun_time_ms=rec.chronology.gun_time,
        course_axis_deg=ing.session.course_axis_deg,
        nominal_leg_length_m=ing.session.course_length_m,
        course_sequences=ing.session.course_sequences,
    )
    mans, legs = {}, {}
    for code, boat in ing.boats.items():
        comp = rec.competitors[code]
        mans[code] = det.detect_manoeuvres_for_boat(
            ing.grid_timestamps_ms, boat.heading, boat.sog_kt, boat.twa_deg, rec.chronology.gun_time, comp.finish_time_ms
        )
        _, legs[code] = ana.compute_continuous_race_progress_for_boat(
            code, boat.x, boat.y, boat.heading, ing.grid_timestamps_ms, comp, ing.marks
        )
    detail = build_race_analysis(
        ing, rec, mans, legs,
        race_id=race_doc["race_id"],
        race_name=race_doc.get("event", race_doc["race_id"]),
        race_date=race_doc.get("date", ""),
        venue="Vilanova i la Geltru",
    )
    attach_performance_analysis(detail)
    return extract_dims_from_analysis(detail, VNR_CODE_MAP)


def build_ac40_telemetry_cache(root: Path, *, write: bool = True, verbose: bool = False) -> dict[str, Any]:
    """Build or refresh cached race-level AC40 telemetry features and missingness masks."""
    root = Path(root)
    ac37_doc = json.loads((root / "docs" / "ac37_ac40_2023_results.json").read_text(encoding="utf-8"))
    ac38_doc = json.loads((root / "docs" / "official_results_ac38_prelims.json").read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []

    for r in ac37_doc.get("races", []):
        if r.get("status") != "completed":
            continue
        rid = r["race_id"]
        evidence_meta = r.get("evidence")
        raw_avail = evidence_meta.get("available_at_utc") if isinstance(evidence_meta, dict) else None
        avail_utc = raw_avail or f"{r['date']}T18:00:00Z"
        fname = VNR_JSONL_FILES.get(rid)
        raw_path = (root / "Data" / "AC37" / "prelims_ac40_2023" / fname) if fname else None
        if raw_path and raw_path.is_file():
            if verbose:
                sys.stderr.write(f"[telemetry] Extracting AC37 {rid} from {raw_path.name}\n")
            boats = _process_ac37_vnr_race(raw_path, r)
            src_ok = True
        else:
            boats = {
                t: {"values": dict.fromkeys(TELEM_DIMS, None), "available": dict.fromkeys(TELEM_DIMS, False)}
                for t in r.get("official_order", [])
            }
            src_ok = False
        records.append({
            "race_id": rid,
            "cycle": "ac37",
            "date": r.get("date"),
            "available_at_utc": avail_utc,
            "source_available": src_ok,
            "boats": boats,
        })

    for r in ac38_doc.get("races", []):
        rid = r["race_id"]
        ev = r.get("evidence") or {}
        avail_utc = (
            (ev.get("independent_anchor") or {}).get("available_at_utc")
            or (ev.get("telemetry_reconstruction") or {}).get("available_at_utc")
            or f"{r['date']}T18:00:00Z"
        )
        ana_path = root / "public" / "data" / "analysis" / f"{rid}.json"
        if ana_path.is_file():
            detail = json.loads(ana_path.read_text(encoding="utf-8"))
            if not any("performance" in b for b in detail.get("boats", [])):
                attach_performance_analysis(detail)
            boats = extract_dims_from_analysis(detail)
            src_ok = True
        else:
            boats = {
                t: {"values": dict.fromkeys(TELEM_DIMS, None), "available": dict.fromkeys(TELEM_DIMS, False)}
                for t in (r.get("official_order") or r.get("on_water_finish_order") or [])
            }
            src_ok = False
        records.append({
            "race_id": rid,
            "cycle": "ac38",
            "date": r.get("date"),
            "available_at_utc": avail_utc,
            "source_available": src_ok,
            "boats": boats,
        })

    records.sort(key=lambda item: (item.get("available_at_utc") or "", item["race_id"]))
    cache = {
        "schema_version": "ac38-ac40-telemetry-features-1",
        "dimensions": list(TELEM_DIMS),
        "aggregation_policy": "equal_weight_matched_legs_per_race_then_equal_weight_prior_races",
        "missing_policy": "preserve_null_and_false_mask_no_zero_imputation",
        "races": records,
    }
    if write:
        out = root / ".forecast" / "ac38" / "ac40_telemetry_features.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    return cache


def load_or_build_telemetry_cache(root: Path, *, verbose: bool = False) -> dict[str, Any]:
    cache_path = Path(root) / ".forecast" / "ac38" / "ac40_telemetry_features.json"
    if cache_path.is_file():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    return build_ac40_telemetry_cache(root, write=True, verbose=verbose)


def compute_lagged_features_before(
    races: Sequence[dict[str, Any]],
    *,
    cycle: str,
    cutoff_utc: str,
    entrants: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Aggregate equal-race lagged telemetry strictly before cutoff_utc; preserves None when missing."""
    cutoff_dt = parse_utc_iso(cutoff_utc)
    prior_races = [
        r for r in races
        if r.get("cycle") == cycle
        and (dt := parse_utc_iso(r.get("available_at_utc"))) is not None
        and cutoff_dt is not None
        and dt < cutoff_dt
    ]
    out: dict[str, dict[str, Any]] = {}
    for entry in entrants:
        sums = dict.fromkeys(TELEM_DIMS, 0.0)
        counts = dict.fromkeys(TELEM_DIMS, 0)
        for r in prior_races:
            b = (r.get("boats") or {}).get(entry)
            if not b:
                continue
            for dim in TELEM_DIMS:
                if (b.get("available") or {}).get(dim) and (b.get("values") or {}).get(dim) is not None:
                    sums[dim] += float(b["values"][dim])
                    counts[dim] += 1
        vals = {dim: (sums[dim] / counts[dim] if counts[dim] > 0 else None) for dim in TELEM_DIMS}
        masks = {dim: (counts[dim] > 0) for dim in TELEM_DIMS}
        out[entry] = {"values": vals, "available": masks, "prior_race_counts": counts}
    return out


def fit_fold_standardization(
    lagged_by_race: Sequence[dict[str, dict[str, Any]]],
    entrants_by_race: Sequence[Sequence[str]],
) -> dict[str, dict[str, float]]:
    """Compute fold-internal mean and SD over observed (available=True) entries ONLY."""
    stats: dict[str, dict[str, float]] = {}
    for dim in TELEM_DIMS:
        obs: list[float] = []
        for lagged, entrants in zip(lagged_by_race, entrants_by_race):
            for entry in entrants:
                rec = lagged.get(entry)
                if not rec:
                    continue
                if (rec.get("available") or {}).get(dim) and (rec.get("values") or {}).get(dim) is not None:
                    obs.append(float(rec["values"][dim]))
        if len(obs) >= 2:
            arr = np.asarray(obs, dtype=float)
            sd = float(np.std(arr, ddof=1))
            stats[dim] = {"mean": float(np.mean(arr)), "sd": sd if sd >= 1e-8 else 0.0, "n_obs": len(obs)}
        else:
            stats[dim] = {"mean": 0.0, "sd": 0.0, "n_obs": len(obs)}
    return stats


def apply_fold_standardization(
    lagged_for_race: dict[str, dict[str, Any]],
    std_stats: dict[str, dict[str, float]],
    entrants: Sequence[str],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Return standardized feature vectors and boolean masks; unavailable stays masked False."""
    z_map: dict[str, np.ndarray] = {}
    m_map: dict[str, np.ndarray] = {}
    for entry in entrants:
        z = np.zeros(len(TELEM_DIMS), dtype=float)
        m = np.zeros(len(TELEM_DIMS), dtype=bool)
        rec = lagged_for_race.get(entry) or {}
        for idx, dim in enumerate(TELEM_DIMS):
            st = std_stats.get(dim, {"mean": 0.0, "sd": 0.0})
            ok = bool((rec.get("available") or {}).get(dim)) and (rec.get("values") or {}).get(dim) is not None and st["sd"] > 0.0
            if ok:
                z[idx] = (float(rec["values"][dim]) - st["mean"]) / st["sd"]
                m[idx] = True
        z_map[entry] = z
        m_map[entry] = m
    return z_map, m_map


def fit_pl_with_telemetry(
    order_rows: Sequence[Sequence[str]],
    z_rows: Sequence[dict[str, np.ndarray]],
    m_rows: Sequence[dict[str, np.ndarray]],
    *,
    entrants: Sequence[str],
    sigma_40: float = 1.2,
    kappa: float = 1.0,
    telem_sd: float = TELEM_PRIOR_SD,
    weights: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Fit penalized Plackett-Luce with team effects N(0, sigma_40^2) and gamma ~ N(0, 0.25^2)."""
    ent_list = list(entrants)
    idx_map = {e: i for i, e in enumerate(ent_list)}
    n_ent = len(ent_list)
    n_dim = len(TELEM_DIMS)
    p_dim = n_ent + n_dim

    prior_prec = np.zeros(p_dim, dtype=float)
    prior_prec[:n_ent] = 1.0 / (sigma_40 ** 2)
    prior_prec[n_ent:] = 1.0 / (telem_sd ** 2)
    lam = np.diag(prior_prec)

    # Identifiability soft sum-to-zero on entrant strengths (exact centering applied post-solve too)
    stages: list[tuple[np.ndarray, float]] = []
    for row_idx, order in enumerate(order_rows):
        w = 1.0 if weights is None else float(weights[row_idx])
        z_r = z_rows[row_idx]
        m_r = m_rows[row_idx]
        valid = [e for e in order if e in idx_map]
        for s in range(len(valid) - 1):
            rem = valid[s:]
            x_mat = np.zeros((len(rem), p_dim), dtype=float)
            for k, entry in enumerate(rem):
                x_mat[k, idx_map[entry]] = 1.0
                x_mat[k, n_ent:] = z_r[entry] * m_r[entry]
            stages.append((x_mat, w))

    param = np.zeros(p_dim, dtype=float)
    hess = np.copy(lam)
    for _ in range(50):
        grad = lam @ param
        hess = np.copy(lam)
        for x_mat, w in stages:
            u = kappa * (x_mat @ param)
            p = np.exp(u - float(np.max(u)))
            p /= float(np.sum(p))
            mean_x = p @ x_mat
            grad += w * kappa * (mean_x - x_mat[0])
            centered = x_mat - mean_x
            hess += w * (kappa ** 2) * ((centered.T * p) @ centered)
        step = np.linalg.solve(hess, grad)
        param -= step
        if float(np.linalg.norm(step)) < 1e-8:
            break

    cov = np.linalg.inv(hess)
    cov = 0.5 * (cov + cov.T)
    theta_raw = param[:n_ent]
    theta_centered = theta_raw - float(np.mean(theta_raw))
    gamma = param[n_ent:]
    return {
        "entrants": ent_list,
        "theta": dict(zip(ent_list, theta_centered.tolist())),
        "gamma": dict(zip(TELEM_DIMS, gamma.tolist())),
        "covariance": cov.tolist(),
        "hessian": hess.tolist(),
        "sigma_40": sigma_40,
        "kappa": kappa,
        "telem_sd": telem_sd,
    }


def predict_pl_win_probs(
    fit_doc: dict[str, Any],
    entrants: Sequence[str],
    z_map: dict[str, np.ndarray] | None = None,
    m_map: dict[str, np.ndarray] | None = None,
    *,
    kappa: float = 1.0,
) -> dict[str, float]:
    """Predict first-place win probabilities for an entrant field using fitted PL + optional telemetry."""
    gamma = np.array([fit_doc["gamma"].get(d, 0.0) for d in TELEM_DIMS], dtype=float)
    theta = fit_doc["theta"]
    utils = []
    for entry in entrants:
        base = float(theta.get(entry, 0.0))
        if z_map is not None and m_map is not None and entry in z_map:
            base += float(np.dot(gamma, z_map[entry] * m_map[entry]))
        utils.append(kappa * base)
    u = np.asarray(utils, dtype=float)
    p = np.exp(u - float(np.max(u)))
    p /= float(np.sum(p))
    return dict(zip(entrants, p.tolist()))
