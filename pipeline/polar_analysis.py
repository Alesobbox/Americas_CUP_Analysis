"""Observed ground-speed polar surface and conditional residuals (polar-1, schema 1.0).

Epistemic scope and terminology:
- Models an **observed ground-speed polar** from steady-state 1 Hz telemetry;
  SOG includes surface current and cannot separate water speed from current.
- Conditional residuals also reflect tactics, traffic, sea state, and
  wind-measurement error; they cannot isolate crew or flight-control skill.
- The 90th percentile (``p90``) is an **observed upper conditional percentile**,
  not a proven optimal target or theoretical VPP ceiling.
- Tack (PORT vs. STARBOARD) has two categories and is modeled as a **fixed effect**
  within each leg mode, never a generic random effect.
- Generalization is evaluated under both Leave-One-Race-Out (LORO) and
  Day-Grouped (Leave-One-Day-Out, LODO) cross-validation.
- Intervals are frequentist **bootstrap confidence intervals** formed by
  deterministic leg-cluster resampling (500 draws).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np

POLAR_SCHEMA_VERSION = "1.0"
POLAR_METHOD_VERSION = "polar-1"
POLAR_BOOTSTRAP_DRAWS = 500
POLAR_BOOTSTRAP_SEED = 20261119

STEADY_MIN_SOG_KT = 5.0
STEADY_MAX_SOG_KT = 50.0
STEADY_MIN_TWS_KT = 2.0
STEADY_MAX_TWS_KT = 35.0
UPWIND_ABS_TWA_RANGE = (28.0, 75.0)
DOWNWIND_ABS_TWA_RANGE = (105.0, 172.0)
MANOEUVRE_EXCLUSION_DEFAULT_MS = 6500
GATE_EXCLUSION_MS = 8000
MAX_STEADY_TURN_RATE_DEG_S = 6.0
MIN_COMPETITOR_SEPARATION_M = 60.0

TWS_BIN_STEP_KT = 1.0
TWA_BIN_STEP_DEG = 2.5
KERNEL_BW_TWS_KT = 1.5
KERNEL_BW_TWA_DEG = 4.0
HIST_MIN_KT = 4.0
HIST_STEP_KT = 0.25
HIST_N_BINS = 184  # covers [4.0, 50.0) kt in 0.25 kt increments
MIN_CURVE_SUPPORT_S = 12.0
MIN_CURVE_CLUSTERS = 2

POLAR_CAVEATS = [
    "Observed ground-speed polar: SOG includes surface current and cannot separate water speed from tidal or residual flow.",
    "Conditional residuals also include tactics, traffic, sea state, and wind-measurement error; they cannot isolate crew or flight-control skill.",
    "The conditional 90th percentile (p90) is an observed upper conditional percentile, not a proven optimal target.",
    "Tack (PORT vs STARBOARD) is modeled as a fixed effect; intervals are leg-cluster bootstrap confidence intervals.",
]

POLAR_DEFINITIONS = {
    "polar_sog_mean_kt": {
        "label": "Observed conditional mean ground speed",
        "unit": "kt",
        "formula": "Kernel-smoothed conditional mean steady-state SOG(TWS, |TWA|, mode) + fixed-effect tack contrast (SOG includes surface current)",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "valid steady-state seconds (excludes ±6.5 s manoeuvres, ±8 s gates, >6°/s turns, <60 m traffic)",
        "source": "interpolated 1 Hz SOG, heading, COG, TWD, and TWS within validated source coverage",
    },
    "polar_sog_p50_kt": {
        "label": "Observed conditional median ground speed (50th percentile)",
        "unit": "kt",
        "formula": "Kernel-weighted conditional 50th percentile of steady-state SOG(TWS, |TWA|, mode) + fixed-effect tack contrast",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "valid steady-state seconds with >=12 s kernel support across >=2 boat-leg clusters",
        "source": "observed steady-state SOG; descriptive quantile, not a physical VPP prediction",
    },
    "polar_sog_p90_kt": {
        "label": "Observed upper conditional percentile (90th percentile)",
        "unit": "kt",
        "formula": "Kernel-weighted conditional 90th percentile of steady-state SOG(TWS, |TWA|, mode) + fixed-effect tack contrast",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "valid steady-state seconds with >=12 s kernel support across >=2 boat-leg clusters",
        "source": "observed steady-state SOG; observed upper conditional percentile, not a proven optimal target",
    },
    "sog_residual_kt": {
        "label": "Conditional ground-speed residual",
        "unit": "kt",
        "formula": "Observed steady-state SOG minus conditional expected ground speed under Day-Grouped (LODO) or Leave-One-Race-Out (LORO) cross-validation",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "boat steady-state coverage seconds; 95% intervals are leg-cluster bootstrap confidence intervals",
        "source": "steady-state SOG, TWS, |TWA|, and tack; reflects current, tactics, traffic, sea state, and wind error alongside boat speed",
    },
    "wind_vmg_residual_kt": {
        "label": "Conditional wind-VMG residual",
        "unit": "kt",
        "formula": "Observed steady-state wind-relative VMG minus conditional expected wind-VMG(TWS, |TWA|, tack)",
        "window": "steady-state 1 Hz samples on completed active legs",
        "denominator": "boat steady-state coverage seconds; 95% intervals are leg-cluster bootstrap confidence intervals",
        "source": "steady-state SOG, COG, TWD, TWS, heading; reflects current, wind-angle choices, and measurement noise",
    },
    "tack_fixed_effect_kt": {
        "label": "Fixed-effect tack contrast (Starboard − Port)",
        "unit": "kt",
        "formula": "Weighted OLS contrast coefficient on two-category fixed effect I_stbd (+0.5 STARBOARD, -0.5 PORT) controlling for bivariate quadratic (TWS, |TWA|)",
        "window": "all steady-state 1 Hz samples within mode",
        "denominator": "valid steady-state seconds; 95% CI from 500 leg-cluster bootstrap draws",
        "source": "signed TWA derived from boat heading and TWD; reflects persistent current/wave/sensor asymmetry across tacks",
    },
}

ARCHIVE_TWS_BRACKETS = (
    ("6_9", "6–9 kt TWS", 6.0, 9.0, 7.5),
    ("9_12", "9–12 kt TWS", 9.0, 12.0, 10.5),
    ("12_15", "12–15 kt TWS", 12.0, 15.0, 13.5),
    ("15_20", "15–20 kt TWS", 15.0, 20.0, 17.0),
)


def _circular_delta_deg(a: float, b: float) -> float:
    return ((b - a + 180.0) % 360.0) - 180.0


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _boat_eligible(boat: dict[str, Any]) -> bool:
    start = boat.get("start") or {}
    return (
        boat.get("classification") not in ("OCS", "RET", "DNS", "DID_NOT_START", "RETIRED")
        and not start.get("ocs")
        and start.get("crossing_time_ms") is not None
        and not boat.get("source_conflicts")
    )


def _coverage_valid(coverage: dict[str, Any] | None, t_ms: int) -> bool:
    if not coverage:
        return True
    for fld in ("gnss", "heading", "sog", "cog", "twd", "tws"):
        info = coverage.get(fld)
        if not info:
            continue
        first_ms, last_ms = info.get("first_ms"), info.get("last_ms")
        if first_ms is None or last_ms is None or t_ms < first_ms or t_ms > last_ms:
            return False
        if any(a < t_ms < b_gap for a, b_gap in info.get("gaps", [])):
            return False
    return True


def _resolve_replay_inputs(
    detail: dict[str, Any],
    ingest_result: Any | None = None,
    replay_doc: dict[str, Any] | None = None,
    replay_path: Path | None = None,
) -> tuple[list[int], dict[str, dict[str, list[float]]], dict[str, str]] | None:
    """Return (timestamps_ms, boat_arrays_by_id, id_by_team_code) or None."""
    if ingest_result is not None and getattr(ingest_result, "boats", None):
        ts = list(ingest_result.grid_timestamps_ms)
        arrays: dict[str, dict[str, list[float]]] = {}
        by_code: dict[str, str] = {}
        for code, b in ingest_result.boats.items():
            tws_series = getattr(b, "tws_kt", None)
            if tws_series is None:
                return None
            bid = b.asset_id
            by_code[code] = bid
            arrays[bid] = {
                "x": b.x,
                "y": b.y,
                "heading": b.heading,
                "cog": b.cog,
                "sog": b.sog_kt,
                "twd": b.twd_deg,
                "tws": tws_series,
            }
        return ts, arrays, by_code

    doc = replay_doc
    if doc is None and replay_path is not None and replay_path.is_file():
        doc = json_loads_file(replay_path)
    if doc is None:
        return None
    tel = doc.get("telemetry") or {}
    ts = tel.get("timestamps") or []
    boats = tel.get("boats") or {}
    if not ts or not boats:
        return None
    by_code = {b["team_code"]: b["id"] for b in detail.get("boats", []) if b.get("id") and b.get("team_code")}
    return ts, boats, by_code


def json_loads_file(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def extract_race_polar_cells(
    detail: dict[str, Any],
    *,
    ingest_result: Any | None = None,
    replay_doc: dict[str, Any] | None = None,
    replay_path: Path | None = None,
) -> dict[str, Any]:
    """Extract deterministic 1 Hz steady-state polar cells onto ``detail['boats']``.

    Populates each boat's ``polar_cells`` (binned by leg, mode, tack, 1 kt TWS,
    2.5° |TWA|) and ``polar_filter`` accounting totals. Returns summary counts.
    """
    sample_interval_ms = detail.get("race", {}).get("sample_interval_ms", 100)
    manoeuvre_excl_ms = max(MANOEUVRE_EXCLUSION_DEFAULT_MS, int(round(65 * sample_interval_ms)))
    resolved = _resolve_replay_inputs(
        detail, ingest_result=ingest_result, replay_doc=replay_doc, replay_path=replay_path
    )
    if resolved is None:
        empty_filter = {
            "steady_sample_count": 0,
            "steady_coverage_s": 0.0,
            "traffic_excluded_s": 0.0,
            "manoeuvre_excluded_s": 0.0,
            "gate_excluded_s": 0.0,
            "turn_rate_excluded_s": 0.0,
            "coverage_excluded_s": 0.0,
        }
        clear_existing = ingest_result is not None or replay_doc is not None
        for boat in detail.get("boats", []):
            if clear_existing:
                boat["polar_cells"] = []
                boat["polar_filter"] = dict(empty_filter)
            else:
                boat.setdefault("polar_cells", [])
                boat.setdefault("polar_filter", dict(empty_filter))
        return {"extracted": False, "reason": "no replay telemetry available"}

    ts, boats_tel, _ = resolved
    if not ts:
        return {"extracted": False, "reason": "empty telemetry timestamps"}

    one_hz_indices: list[int] = []
    last_sec: int | None = None
    for idx, t_ms in enumerate(ts):
        sec = int(t_ms) // 1000
        if sec != last_sec:
            last_sec = sec
            one_hz_indices.append(idx)

    active_ids = [b["id"] for b in detail.get("boats", []) if b.get("id") in boats_tel]
    total_cells = 0
    total_samples = 0

    for boat in detail.get("boats", []):
        bid = boat.get("id")
        tel = boats_tel.get(bid)
        if not tel or not _boat_eligible(boat):
            boat["polar_cells"] = []
            boat["polar_filter"] = {
                "steady_sample_count": 0,
                "steady_coverage_s": 0.0,
                "traffic_excluded_s": 0.0,
                "manoeuvre_excluded_s": 0.0,
                "gate_excluded_s": 0.0,
                "turn_rate_excluded_s": 0.0,
                "coverage_excluded_s": 0.0,
            }
            continue

        xs = tel.get("x") or []
        ys = tel.get("y") or []
        hdgs = tel.get("heading") or []
        cogs = tel.get("cog") or []
        sogs = tel.get("sog") or []
        twds = tel.get("twd") or []
        twss = tel.get("tws") or []
        n_arr = min(len(ts), len(xs), len(ys), len(hdgs), len(cogs), len(sogs), len(twds), len(twss))
        if n_arr == 0:
            boat["polar_cells"] = []
            continue

        man_times = [
            int(m["timestamp"])
            for m in boat.get("manoeuvres", [])
            if isinstance(m.get("timestamp"), int)
        ]
        start_crossing = (boat.get("start") or {}).get("crossing_time_ms")
        gate_times = [int(start_crossing)] if isinstance(start_crossing, int) else []
        gate_times.extend(
            int(g["crossing_time_ms"])
            for g in boat.get("gates", [])
            if isinstance(g.get("crossing_time_ms"), int)
        )
        cov = boat.get("source_coverage") or {}

        counts = defaultdict(int)
        cells_out: list[dict[str, Any]] = []

        for leg in boat.get("legs", []):
            if not leg.get("complete"):
                continue
            leg_num = leg.get("leg")
            l_start, l_end = leg.get("start_ms"), leg.get("end_ms")
            if not isinstance(leg_num, int) or l_start is None or l_end is None or l_end <= l_start:
                continue
            is_up = leg_num % 2 == 1
            mode = "upwind" if is_up else "downwind"
            twa_lo, twa_hi = UPWIND_ABS_TWA_RANGE if is_up else DOWNWIND_ABS_TWA_RANGE
            buckets: dict[tuple[str, float, float], list[tuple[float, float, float, float]]] = {}

            for pos_i, idx in enumerate(one_hz_indices):
                if idx >= n_arr:
                    break
                t_ms = int(ts[idx])
                if t_ms < l_start or t_ms > l_end:
                    continue
                if (
                    t_ms < l_start + GATE_EXCLUSION_MS
                    or t_ms > l_end - GATE_EXCLUSION_MS
                    or any(abs(t_ms - gt) <= GATE_EXCLUSION_MS for gt in gate_times)
                ):
                    counts["gate_excluded"] += 1
                    continue
                if any(abs(t_ms - mt) <= manoeuvre_excl_ms for mt in man_times):
                    counts["manoeuvre_excluded"] += 1
                    continue
                if pos_i > 0:
                    p_idx = one_hz_indices[pos_i - 1]
                    if p_idx < n_arr:
                        dt_s = (t_ms - int(ts[p_idx])) / 1000.0
                        if 0.0 < dt_s <= 2.0:
                            d_hdg = abs(_circular_delta_deg(float(hdgs[p_idx]), float(hdgs[idx])))
                            if d_hdg / dt_s > MAX_STEADY_TURN_RATE_DEG_S:
                                counts["turn_rate_excluded"] += 1
                                continue
                if not _coverage_valid(cov, t_ms):
                    counts["coverage_excluded"] += 1
                    continue

                bx, by = float(xs[idx]), float(ys[idx])
                close_traffic = False
                for oid in active_ids:
                    if oid == bid:
                        continue
                    otel = boats_tel.get(oid)
                    if not otel:
                        continue
                    ox, oy = otel.get("x") or [], otel.get("y") or []
                    if idx < len(ox) and idx < len(oy):
                        if math.hypot(bx - float(ox[idx]), by - float(oy[idx])) < MIN_COMPETITOR_SEPARATION_M:
                            close_traffic = True
                            break
                if close_traffic:
                    counts["traffic_excluded"] += 1
                    continue

                sog = float(sogs[idx])
                tws = float(twss[idx])
                hdg = float(hdgs[idx])
                cog = float(cogs[idx])
                twd = float(twds[idx])
                if not (
                    _finite(sog)
                    and _finite(tws)
                    and _finite(hdg)
                    and _finite(cog)
                    and _finite(twd)
                    and STEADY_MIN_TWS_KT <= tws <= STEADY_MAX_TWS_KT
                    and STEADY_MIN_SOG_KT <= sog <= STEADY_MAX_SOG_KT
                ):
                    counts["out_of_range"] += 1
                    continue

                twa = _circular_delta_deg(hdg, twd)
                abs_twa = abs(twa)
                if not (twa_lo <= abs_twa <= twa_hi):
                    counts["out_of_range"] += 1
                    continue

                wind_diff = _circular_delta_deg(cog, twd)
                wind_vmg = sog * math.cos(math.radians(wind_diff))
                if not is_up:
                    wind_vmg = -wind_vmg

                tack = "STARBOARD" if twa >= 0.0 else "PORT"
                tws_bin = round(tws / TWS_BIN_STEP_KT) * TWS_BIN_STEP_KT
                twa_bin = round(abs_twa / TWA_BIN_STEP_DEG) * TWA_BIN_STEP_DEG
                buckets.setdefault((tack, tws_bin, twa_bin), []).append((tws, abs_twa, sog, wind_vmg))
                counts["steady"] += 1

            for (tack, tws_bin, twa_bin), vals in sorted(buckets.items()):
                arr = np.asarray(vals, dtype=float)
                n_val = int(len(vals))
                cells_out.append(
                    {
                        "leg": int(leg_num),
                        "mode": mode,
                        "tack": tack,
                        "tws_bin_kt": float(tws_bin),
                        "twa_bin_deg": float(twa_bin),
                        "sample_count": n_val,
                        "coverage_s": float(n_val),
                        "tws_mean_kt": round(float(arr[:, 0].mean()), 3),
                        "abs_twa_mean_deg": round(float(arr[:, 1].mean()), 3),
                        "sog_mean_kt": round(float(arr[:, 2].mean()), 4),
                        "sog_p50_kt": round(float(np.quantile(arr[:, 2], 0.5)), 4),
                        "sog_p90_kt": round(float(np.quantile(arr[:, 2], 0.9)), 4),
                        "wind_vmg_mean_kt": round(float(arr[:, 3].mean()), 4),
                    }
                )
                total_cells += 1
                total_samples += n_val

        boat["polar_cells"] = cells_out
        boat["polar_filter"] = {
            "steady_sample_count": int(counts["steady"]),
            "steady_coverage_s": float(counts["steady"]),
            "traffic_excluded_s": float(counts["traffic_excluded"]),
            "manoeuvre_excluded_s": float(counts["manoeuvre_excluded"]),
            "gate_excluded_s": float(counts["gate_excluded"]),
            "turn_rate_excluded_s": float(counts["turn_rate_excluded"]),
            "coverage_excluded_s": float(counts["coverage_excluded"]),
        }

    return {"extracted": True, "cells": total_cells, "samples": total_samples}


@dataclass
class _PolarDataset:
    race_id: np.ndarray
    date: np.ndarray
    race_type: np.ndarray
    team_code: np.ndarray
    boat_id: np.ndarray
    cluster_id: np.ndarray
    cluster_key: list[tuple[str, str, int]]
    mode: np.ndarray  # 1 = upwind, 0 = downwind
    tack: np.ndarray  # +0.5 = STARBOARD, -0.5 = PORT
    weights: np.ndarray
    tws: np.ndarray
    twa: np.ndarray
    tws_bin: np.ndarray
    twa_bin: np.ndarray
    sog: np.ndarray
    sog_p90: np.ndarray
    vmg: np.ndarray
    grid_keys: np.ndarray  # (G, 3): (mode, tws_bin, twa_bin)
    cell_to_grid: np.ndarray  # (N,)
    K_grid: np.ndarray  # (G, G)


def _assemble_dataset(details: dict[str, dict[str, Any]]) -> _PolarDataset | None:
    rows: list[tuple[Any, ...]] = []
    cluster_map: dict[tuple[str, str, int], int] = {}
    cluster_keys: list[tuple[str, str, int]] = []

    for race_id in sorted(details):
        detail = details[race_id]
        race = detail.get("race") or {}
        rdate = str(race.get("date") or "")
        rtype = str(race.get("race_type") or "RACE_TYPE_FLEET")
        for boat in detail.get("boats", []):
            if not _boat_eligible(boat):
                continue
            bid = str(boat.get("id") or "")
            tcode = str(boat.get("team_code") or bid)
            for cell in boat.get("polar_cells") or []:
                n_w = float(cell.get("sample_count") or cell.get("coverage_s") or 0.0)
                if n_w <= 0:
                    continue
                leg = int(cell.get("leg") or 0)
                ckey = (race_id, bid, leg)
                if ckey not in cluster_map:
                    cluster_map[ckey] = len(cluster_keys)
                    cluster_keys.append(ckey)
                cid = cluster_map[ckey]
                is_up = 1 if cell.get("mode") == "upwind" else 0
                i_stbd = 0.5 if cell.get("tack") == "STARBOARD" else -0.5
                tws_b = float(cell["tws_bin_kt"])
                twa_b = float(cell["twa_bin_deg"])
                rows.append(
                    (
                        race_id,
                        rdate,
                        rtype,
                        tcode,
                        bid,
                        cid,
                        is_up,
                        i_stbd,
                        n_w,
                        float(cell.get("tws_mean_kt", tws_b)),
                        float(cell.get("abs_twa_mean_deg", twa_b)),
                        tws_b,
                        twa_b,
                        float(cell["sog_mean_kt"]),
                        float(cell.get("sog_p90_kt", cell["sog_mean_kt"])),
                        float(cell["wind_vmg_mean_kt"]),
                    )
                )

    if not rows:
        return None

    mode = np.array([r[6] for r in rows], dtype=np.int64)
    tws_bin = np.array([r[11] for r in rows], dtype=float)
    twa_bin = np.array([r[12] for r in rows], dtype=float)
    grid_keys, cell_to_grid = np.unique(
        np.column_stack([mode.astype(float), tws_bin, twa_bin]), axis=0, return_inverse=True
    )
    g_mode = grid_keys[:, 0]
    d_tws = (grid_keys[:, 1][:, None] - grid_keys[:, 1][None, :]) / KERNEL_BW_TWS_KT
    d_twa = (grid_keys[:, 2][:, None] - grid_keys[:, 2][None, :]) / KERNEL_BW_TWA_DEG
    same_mode = (g_mode[:, None] == g_mode[None, :]).astype(float)
    K_grid = np.exp(-0.5 * (d_tws * d_tws + d_twa * d_twa)) * same_mode

    return _PolarDataset(
        race_id=np.array([r[0] for r in rows], dtype=object),
        date=np.array([r[1] for r in rows], dtype=object),
        race_type=np.array([r[2] for r in rows], dtype=object),
        team_code=np.array([r[3] for r in rows], dtype=object),
        boat_id=np.array([r[4] for r in rows], dtype=object),
        cluster_id=np.array([r[5] for r in rows], dtype=np.int64),
        cluster_key=cluster_keys,
        mode=mode,
        tack=np.array([r[7] for r in rows], dtype=float),
        weights=np.array([r[8] for r in rows], dtype=float),
        tws=np.array([r[9] for r in rows], dtype=float),
        twa=np.array([r[10] for r in rows], dtype=float),
        tws_bin=tws_bin,
        twa_bin=twa_bin,
        sog=np.array([r[13] for r in rows], dtype=float),
        sog_p90=np.array([r[14] for r in rows], dtype=float),
        vmg=np.array([r[15] for r in rows], dtype=float),
        grid_keys=grid_keys,
        cell_to_grid=cell_to_grid,
        K_grid=K_grid,
    )


def _estimate_tack_fixed_effect(
    ds: _PolarDataset, mask: np.ndarray
) -> dict[int, tuple[float, float]]:
    """Estimate fixed tack effect (STARBOARD - PORT) for SOG & wind-VMG per mode."""
    out: dict[int, tuple[float, float]] = {}
    for m in (1, 0):
        idx = mask & (ds.mode == m)
        if not np.any(idx):
            out[m] = (0.0, 0.0)
            continue
        tacks = ds.tack[idx]
        if np.all(tacks == tacks[0]):
            out[m] = (0.0, 0.0)
            continue
        tws_vals = ds.tws[idx]
        twa_vals = ds.twa[idx]
        tws_c = (tws_vals - tws_vals.mean()) / max(1.0, float(tws_vals.std()))
        twa_c = (twa_vals - twa_vals.mean()) / max(1.0, float(twa_vals.std()))
        X = np.column_stack(
            [
                np.ones(tws_c.size),
                tws_c,
                twa_c,
                tws_c * tws_c,
                twa_c * twa_c,
                tws_c * twa_c,
                tacks,
            ]
        )
        w_sqrt = np.sqrt(ds.weights[idx])[:, None]
        beta_sog, _, _, _ = np.linalg.lstsq(X * w_sqrt, ds.sog[idx] * w_sqrt[:, 0], rcond=None)
        beta_vmg, _, _, _ = np.linalg.lstsq(X * w_sqrt, ds.vmg[idx] * w_sqrt[:, 0], rcond=None)
        out[m] = (float(beta_sog[-1]), float(beta_vmg[-1]))
    return out


def _weighted_quantile_from_hist(hist: np.ndarray, q: float) -> np.ndarray:
    """Linearly interpolated quantile across fixed 0.25 kt bins [4.0, 50.0)."""
    totals = hist.sum(axis=1, keepdims=True)
    safe_totals = np.where(totals > 1e-12, totals, 1.0)
    cdf = np.cumsum(hist, axis=1) / safe_totals
    pos = np.argmax(cdf >= q, axis=1)
    rows = np.arange(hist.shape[0])
    c_hi = cdf[rows, pos]
    c_lo = np.where(pos > 0, cdf[rows, np.maximum(0, pos - 1)], 0.0)
    frac = np.where((c_hi - c_lo) > 1e-12, (q - c_lo) / np.maximum(1e-12, c_hi - c_lo), 0.5)
    vals = HIST_MIN_KT + (pos + frac) * HIST_STEP_KT
    return np.where(totals[:, 0] > 1e-12, vals, np.nan)


def _fit_and_predict_subset(
    ds: _PolarDataset,
    train_mask: np.ndarray,
    eval_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Fit kernel mean + fixed-effect tack + nonparametric conditional quantiles."""
    G = len(ds.grid_keys)
    tack_eff = _estimate_tack_fixed_effect(ds, train_mask)
    beta_sog_cell = np.array([tack_eff[int(m)][0] for m in ds.mode], dtype=float)
    beta_vmg_cell = np.array([tack_eff[int(m)][1] for m in ds.mode], dtype=float)

    sog_adj = ds.sog - beta_sog_cell * ds.tack
    vmg_adj = ds.vmg - beta_vmg_cell * ds.tack

    # Mode fallback means if a boundary cell has near-zero kernel support
    mode_mean_sog: dict[int, float] = {}
    mode_mean_vmg: dict[int, float] = {}
    for m in (1, 0):
        tr_m = train_mask & (ds.mode == m)
        if np.any(tr_m):
            mode_mean_sog[m] = float(np.average(sog_adj[tr_m], weights=ds.weights[tr_m]))
            mode_mean_vmg[m] = float(np.average(vmg_adj[tr_m], weights=ds.weights[tr_m]))
        else:
            mode_mean_sog[m] = float(np.average(sog_adj[train_mask], weights=ds.weights[train_mask]))
            mode_mean_vmg[m] = float(np.average(vmg_adj[train_mask], weights=ds.weights[train_mask]))

    g_tr_idx = ds.cell_to_grid[train_mask]
    w_tr = ds.weights[train_mask]
    w_grid = np.bincount(g_tr_idx, weights=w_tr, minlength=G)
    wsog_grid = np.bincount(g_tr_idx, weights=w_tr * sog_adj[train_mask], minlength=G)
    wvmg_grid = np.bincount(g_tr_idx, weights=w_tr * vmg_adj[train_mask], minlength=G)

    denom = ds.K_grid @ w_grid
    valid_g = denom > 1e-6
    safe_d = np.where(valid_g, denom, 1.0)
    fallback_sog_g = np.array([mode_mean_sog[int(m)] for m in ds.grid_keys[:, 0]], dtype=float)
    fallback_vmg_g = np.array([mode_mean_vmg[int(m)] for m in ds.grid_keys[:, 0]], dtype=float)

    grid_mean_sog = np.where(valid_g, (ds.K_grid @ wsog_grid) / safe_d, fallback_sog_g)
    grid_mean_vmg = np.where(valid_g, (ds.K_grid @ wvmg_grid) / safe_d, fallback_vmg_g)

    # Conditional quantile histograms at each grid point in adjusted SOG & VMG space
    y_bin_sog = np.clip(
        np.floor((sog_adj[train_mask] - HIST_MIN_KT) / HIST_STEP_KT).astype(int),
        0,
        HIST_N_BINS - 1,
    )
    h_sog = np.zeros((G, HIST_N_BINS), dtype=float)
    np.add.at(h_sog, (g_tr_idx, y_bin_sog), w_tr)
    smoothed_h = ds.K_grid @ h_sog
    grid_p50_sog = _weighted_quantile_from_hist(smoothed_h, 0.50)
    grid_p90_sog = _weighted_quantile_from_hist(smoothed_h, 0.90)
    grid_p50_sog = np.where(np.isfinite(grid_p50_sog), grid_p50_sog, grid_mean_sog)
    grid_p90_sog = np.where(np.isfinite(grid_p90_sog), grid_p90_sog, grid_mean_sog)

    result: dict[str, Any] = {
        "tack_effect": tack_eff,
        "grid_support": denom,
        "grid_mean_sog": grid_mean_sog,
        "grid_mean_vmg": grid_mean_vmg,
        "grid_p50_sog": grid_p50_sog,
        "grid_p90_sog": grid_p90_sog,
    }
    if eval_mask is not None:
        ev_g = ds.cell_to_grid[eval_mask]
        tack_offset_sog = beta_sog_cell[eval_mask] * ds.tack[eval_mask]
        tack_offset_vmg = beta_vmg_cell[eval_mask] * ds.tack[eval_mask]
        result["eval_sog"] = grid_mean_sog[ev_g] + tack_offset_sog
        result["eval_vmg"] = grid_mean_vmg[ev_g] + tack_offset_vmg
        result["eval_p50"] = grid_p50_sog[ev_g] + tack_offset_sog
        result["eval_p90"] = grid_p90_sog[ev_g] + tack_offset_sog
    return result


def _validation_metrics(
    ds: _PolarDataset,
    pred_sog: np.ndarray,
    pred_vmg: np.ndarray,
    pred_p50: np.ndarray,
    pred_p90: np.ndarray,
    label: str,
    folds: int,
) -> dict[str, Any]:
    w = ds.weights
    err_sog = ds.sog - pred_sog
    err_vmg = ds.vmg - pred_vmg
    ybar_sog = float(np.average(ds.sog, weights=w))
    ybar_vmg = float(np.average(ds.vmg, weights=w))
    mse_sog = float(np.average(err_sog * err_sog, weights=w))
    mse_vmg = float(np.average(err_vmg * err_vmg, weights=w))
    var_sog = max(1e-9, float(np.average((ds.sog - ybar_sog) ** 2, weights=w)))
    var_vmg = max(1e-9, float(np.average((ds.vmg - ybar_vmg) ** 2, weights=w)))

    def pinball(y_true: np.ndarray, q_hat: np.ndarray, q: float) -> float:
        diff = y_true - q_hat
        loss = np.where(diff >= 0.0, q * diff, (q - 1.0) * diff)
        return float(np.average(loss, weights=w))

    return {
        "label": label,
        "folds": int(folds),
        "sog_rmse_kt": round(math.sqrt(mse_sog), 3),
        "sog_mae_kt": round(float(np.average(np.abs(err_sog), weights=w)), 3),
        "sog_r2": round(1.0 - mse_sog / var_sog, 4),
        "vmg_rmse_kt": round(math.sqrt(mse_vmg), 3),
        "vmg_mae_kt": round(float(np.average(np.abs(err_vmg), weights=w)), 3),
        "vmg_r2": round(1.0 - mse_vmg / var_vmg, 4),
        "p50_pinball_loss_kt": round(pinball(ds.sog, pred_p50, 0.50), 3),
        "p90_pinball_loss_kt": round(pinball(ds.sog, pred_p90, 0.90), 3),
        "p50_empirical_coverage": round(float(np.average((ds.sog <= pred_p50).astype(float), weights=w)), 4),
        "p90_empirical_coverage": round(float(np.average((ds.sog <= pred_p90).astype(float), weights=w)), 4),
    }


def _bootstrap_ci_matrix(
    cluster_weights: np.ndarray,
    cluster_weighted_vals: np.ndarray,
    mult: np.ndarray,
    fallback_point: float | None = None,
) -> dict[str, float] | None:
    """Compute frequentist 95% bootstrap confidence interval across cluster weights (C, K)."""
    tot_w = float(cluster_weights.sum())
    if tot_w <= 0:
        return None
    point = float(cluster_weighted_vals.sum() / tot_w) if fallback_point is None else float(fallback_point)
    boot_w = mult @ cluster_weights
    boot_y = mult @ cluster_weighted_vals
    valid = boot_w > 1e-9
    if not np.any(valid):
        return {
            "value": round(point, 3),
            "ci_low_kt": round(point, 3),
            "ci_high_kt": round(point, 3),
            "bootstrap_se_kt": 0.0,
        }
    est = boot_y[valid] / boot_w[valid]
    return {
        "value": round(point, 3),
        "ci_low_kt": round(float(np.quantile(est, 0.025)), 3),
        "ci_high_kt": round(float(np.quantile(est, 0.975)), 3),
        "bootstrap_se_kt": round(float(np.std(est, ddof=1)) if est.size > 1 else 0.0, 3),
    }


def _compute_archive_tack_bootstrap(
    ds: _PolarDataset, mult: np.ndarray
) -> dict[str, Any]:
    """Compute fixed tack effect contrasts with cluster bootstrap 95% confidence intervals."""
    out: dict[str, Any] = {
        "specification": (
            "Two-category fixed effect (I_stbd = +0.5 STARBOARD, -0.5 PORT) controlling for "
            "bivariate quadratic (TWS, |TWA|) surface per leg mode"
        ),
        "bootstrap_draws": int(mult.shape[0]),
    }
    C = len(ds.cluster_key)

    # Point estimates on full sample
    all_mask = np.ones(len(ds.weights), dtype=bool)
    full_eff = _estimate_tack_fixed_effect(ds, all_mask)
    w_up = float(ds.weights[ds.mode == 1].sum())
    w_dn = float(ds.weights[ds.mode == 0].sum())

    # Bootstrap cluster residual contrast preserving covariance across upwind/downwind legs
    full_fit = _fit_and_predict_subset(ds, all_mask, all_mask)
    sog_starboard_part = ds.sog - (
        full_fit["eval_sog"] - np.where(ds.mode == 1, full_eff[1][0], full_eff[0][0]) * ds.tack
    )
    centered_by_mode: dict[str, np.ndarray | None] = {"upwind": None, "downwind": None}
    for key, mode_val in (("upwind", 1), ("downwind", 0)):
        sel = ds.mode == mode_val
        cov_s = float(ds.weights[sel].sum())
        if not np.any(sel) or cov_s <= 0:
            out[key] = None
            continue
        point_c = full_eff[mode_val][0]
        c_stbd_w = np.bincount(ds.cluster_id[sel & (ds.tack > 0)], weights=ds.weights[sel & (ds.tack > 0)], minlength=C)
        c_stbd_y = np.bincount(ds.cluster_id[sel & (ds.tack > 0)], weights=ds.weights[sel & (ds.tack > 0)] * sog_starboard_part[sel & (ds.tack > 0)], minlength=C)
        c_port_w = np.bincount(ds.cluster_id[sel & (ds.tack < 0)], weights=ds.weights[sel & (ds.tack < 0)], minlength=C)
        c_port_y = np.bincount(ds.cluster_id[sel & (ds.tack < 0)], weights=ds.weights[sel & (ds.tack < 0)] * sog_starboard_part[sel & (ds.tack < 0)], minlength=C)

        boot_stbd_w = mult @ c_stbd_w
        boot_port_w = mult @ c_port_w
        valid = (boot_stbd_w > 1e-9) & (boot_port_w > 1e-9)
        if np.any(valid):
            contrasts = np.where(
                valid,
                (mult @ c_stbd_y) / np.where(valid, boot_stbd_w, 1.0)
                - (mult @ c_port_y) / np.where(valid, boot_port_w, 1.0),
                point_c,
            )
            mean_valid = float(contrasts[valid].mean())
            centered = np.where(valid, contrasts - mean_valid + point_c, point_c)
            valid_centered = centered[valid]
            ci_lo = float(np.quantile(valid_centered, 0.025))
            ci_hi = float(np.quantile(valid_centered, 0.975))
            se = float(np.std(valid_centered, ddof=1)) if valid_centered.size > 1 else 0.0
            centered_by_mode[key] = centered
        else:
            ci_lo = ci_hi = point_c
            se = 0.0
            centered_by_mode[key] = np.full(mult.shape[0], point_c)
        out[key] = {
            "contrast_kt": round(point_c, 3),
            "ci_low_kt": round(ci_lo, 3),
            "ci_high_kt": round(ci_hi, 3),
            "bootstrap_se_kt": round(se, 3),
            "coverage_s": round(cov_s, 1),
        }

    # Weighted average contrast across modes using coupled bootstrap draws
    tot_w = w_up + w_dn
    if tot_w > 0:
        p_all = (full_eff[1][0] * w_up + full_eff[0][0] * w_dn) / tot_w
        up_draws, dn_draws = centered_by_mode.get("upwind"), centered_by_mode.get("downwind")
        if up_draws is not None and dn_draws is not None:
            draws_all = (w_up * up_draws + w_dn * dn_draws) / tot_w
            se_all = float(np.std(draws_all, ddof=1)) if draws_all.size > 1 else 0.0
            out["overall"] = {
                "contrast_kt": round(p_all, 3),
                "ci_low_kt": round(float(np.quantile(draws_all, 0.025)), 3),
                "ci_high_kt": round(float(np.quantile(draws_all, 0.975)), 3),
                "bootstrap_se_kt": round(se_all, 3),
                "coverage_s": round(tot_w, 1),
            }
        else:
            ref = out.get("upwind") or out.get("downwind")
            out["overall"] = dict(ref) if ref else None
    else:
        out["overall"] = None
    return out


def _eval_curve_points(
    ds: _PolarDataset,
    mask: np.ndarray,
    mode_val: int,
    tws_lo: float,
    tws_hi: float,
    twa_grid: list[float],
) -> list[dict[str, Any]]:
    """Compute observed conditional polar curve (mean, p50, p90) vs |TWA| for a TWS band."""
    sel = mask & (ds.mode == mode_val) & (ds.tws >= tws_lo) & (ds.tws <= tws_hi)
    if not np.any(sel):
        return []
    tack_eff = _estimate_tack_fixed_effect(ds, mask)
    beta_sog = tack_eff[mode_val][0]
    beta_vmg = tack_eff[mode_val][1]

    sog_adj = ds.sog[sel] - beta_sog * ds.tack[sel]
    vmg_adj = ds.vmg[sel] - beta_vmg * ds.tack[sel]
    tws_sel = ds.tws[sel]
    twa_sel = ds.twa[sel]
    w_sel = ds.weights[sel]
    cids = ds.cluster_id[sel]
    tws_ref = float(np.average(tws_sel, weights=w_sel))

    points: list[dict[str, Any]] = []
    for target_twa in twa_grid:
        k = np.exp(
            -0.5
            * (
                ((tws_ref - tws_sel) / KERNEL_BW_TWS_KT) ** 2
                + ((target_twa - twa_sel) / KERNEL_BW_TWA_DEG) ** 2
            )
        ) * w_sel
        eff_s = float(k.sum())
        support_clusters = int(len(set(int(c) for c in cids[k >= 0.25 * w_sel])))
        if eff_s < MIN_CURVE_SUPPORT_S or support_clusters < MIN_CURVE_CLUSTERS:
            continue
        mean_sog = float(np.sum(k * sog_adj) / eff_s)
        mean_vmg = float(np.sum(k * vmg_adj) / eff_s)
        order = np.argsort(sog_adj)
        cdf = np.cumsum(k[order]) / eff_s
        p50_sog = float(sog_adj[order][int(np.argmax(cdf >= 0.50))])
        p90_sog = float(sog_adj[order][int(np.argmax(cdf >= 0.90))])

        order_v = np.argsort(vmg_adj)
        cdf_v = np.cumsum(k[order_v]) / eff_s
        p50_vmg = float(vmg_adj[order_v][int(np.argmax(cdf_v >= 0.50))])
        p90_vmg = float(vmg_adj[order_v][int(np.argmax(cdf_v >= 0.90))])
        points.append(
            {
                "twa_deg": float(target_twa),
                "mean_sog_kt": round(mean_sog, 2),
                "p50_sog_kt": round(p50_sog, 2),
                "p90_sog_kt": round(max(p50_sog, p90_sog), 2),
                "mean_wind_vmg_kt": round(mean_vmg, 2),
                "p50_wind_vmg_kt": round(p50_vmg, 2),
                "p90_wind_vmg_kt": round(max(p50_vmg, p90_vmg), 2),
                "effective_coverage_s": round(eff_s, 1),
                "support_clusters": support_clusters,
            }
        )
    return points


def _build_race_brackets(ds: _PolarDataset, race_mask: np.ndarray, full_mask: np.ndarray) -> dict[str, list[dict[str, Any]]]:
    twa_grids = {
        "upwind": [30.0 + 2.5 * i for i in range(18)],  # 30..72.5
        "downwind": [110.0 + 2.5 * i for i in range(25)],  # 110..170
    }
    out: dict[str, list[dict[str, Any]]] = {"upwind": [], "downwind": []}
    for mode_name, mode_val in (("upwind", 1), ("downwind", 0)):
        sel = race_mask & (ds.mode == mode_val)
        if not np.any(sel):
            continue
        r_tws = ds.tws[sel]
        r_w = ds.weights[sel]
        tws_min = float(r_tws.min())
        tws_max = float(r_tws.max())
        tws_ref = float(np.average(r_tws, weights=r_w))
        pts = _eval_curve_points(
            ds,
            full_mask,
            mode_val,
            max(STEADY_MIN_TWS_KT, tws_min - 1.0),
            min(STEADY_MAX_TWS_KT, tws_max + 1.0),
            twa_grids[mode_name],
        )
        out[mode_name].append(
            {
                "id": "race_window",
                "label": f"Race wind ({tws_min:.1f}–{tws_max:.1f} kt)",
                "tws_min_kt": round(tws_min, 1),
                "tws_max_kt": round(tws_max, 1),
                "tws_ref_kt": round(tws_ref, 1),
                "points": pts,
            }
        )
        for bid, blabel, b_lo, b_hi, _ in ARCHIVE_TWS_BRACKETS:
            if np.any(sel & (ds.tws >= b_lo) & (ds.tws <= b_hi)):
                bpts = _eval_curve_points(ds, full_mask, mode_val, b_lo, b_hi, twa_grids[mode_name])
                if bpts:
                    out[mode_name].append(
                        {
                            "id": bid,
                            "label": blabel,
                            "tws_min_kt": b_lo,
                            "tws_max_kt": b_hi,
                            "tws_ref_kt": 0.5 * (b_lo + b_hi),
                            "points": bpts,
                        }
                    )
    return out


def _build_observed_bins(ds: _PolarDataset, boat_mask: np.ndarray, pred_sog: np.ndarray) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"upwind": [], "downwind": []}
    for mode_name, mode_val in (("upwind", 1), ("downwind", 0)):
        sel = boat_mask & (ds.mode == mode_val)
        if not np.any(sel):
            continue
        grouped: dict[tuple[str, float, float], list[int]] = defaultdict(list)
        indices = np.flatnonzero(sel)
        for i in indices:
            tack_lbl = "STARBOARD" if ds.tack[i] > 0 else "PORT"
            grouped[(tack_lbl, float(ds.tws_bin[i]), float(ds.twa_bin[i]))].append(int(i))
        rows = []
        for (tack_lbl, tws_b, twa_b), idxs in sorted(grouped.items(), key=lambda x: (x[0][2], x[0][1], x[0][0])):
            w = ds.weights[idxs]
            w_sum = float(w.sum())
            rows.append(
                {
                    "tack": tack_lbl,
                    "tws_bin_kt": tws_b,
                    "twa_bin_deg": twa_b,
                    "sog_mean_kt": round(float(np.average(ds.sog[idxs], weights=w)), 2),
                    "sog_p90_kt": round(float(np.average(ds.sog_p90[idxs], weights=w)), 2),
                    "wind_vmg_mean_kt": round(float(np.average(ds.vmg[idxs], weights=w)), 2),
                    "predicted_sog_kt": round(float(np.average(pred_sog[idxs], weights=w)), 2),
                    "sample_count": int(round(w_sum)),
                }
            )
        out[mode_name] = rows
    return out


def _make_boat_residual_block(
    boat: dict[str, Any],
    ds: _PolarDataset | None,
    boat_mask: np.ndarray | None,
    pred_sog_loro: np.ndarray | None,
    pred_sog_lodo: np.ndarray | None,
    pred_sog_in: np.ndarray | None,
    pred_vmg_lodo: np.ndarray | None,
    pred_p90_lodo: np.ndarray | None,
    eval_scope: str,
    seed_offset: int = 0,
) -> dict[str, Any]:
    filt = boat.get("polar_filter") or {}
    if not _boat_eligible(boat):
        return {
            "schema_version": POLAR_SCHEMA_VERSION,
            "method_version": POLAR_METHOD_VERSION,
            "quality": "unavailable",
            "reason": "boat retired, OCS, DNS, missing start crossing, or has source-state conflict",
            "evaluation_scope": eval_scope,
            "steady_sample_count": 0,
            "steady_coverage_s": 0.0,
            "leg_cluster_count": 0,
            "traffic_excluded_s": float(filt.get("traffic_excluded_s", 0.0)),
            "sog_residual_kt": None,
            "wind_vmg_residual_kt": None,
            "loro_sog_residual_kt": None,
            "lodo_sog_residual_kt": None,
            "above_p90_share": None,
            "observed_bins": {"upwind": [], "downwind": []},
        }
    if ds is None or boat_mask is None or not np.any(boat_mask):
        return {
            "schema_version": POLAR_SCHEMA_VERSION,
            "method_version": POLAR_METHOD_VERSION,
            "quality": "unavailable",
            "reason": "no steady-state 1 Hz samples on completed active legs",
            "evaluation_scope": eval_scope,
            "steady_sample_count": 0,
            "steady_coverage_s": 0.0,
            "leg_cluster_count": 0,
            "traffic_excluded_s": float(filt.get("traffic_excluded_s", 0.0)),
            "sog_residual_kt": None,
            "wind_vmg_residual_kt": None,
            "loro_sog_residual_kt": None,
            "lodo_sog_residual_kt": None,
            "above_p90_share": None,
            "observed_bins": {"upwind": [], "downwind": []},
        }

    w = ds.weights[boat_mask]
    res_lodo = ds.sog[boat_mask] - pred_sog_lodo[boat_mask]
    res_loro = ds.sog[boat_mask] - pred_sog_loro[boat_mask]
    res_in = ds.sog[boat_mask] - pred_sog_in[boat_mask]
    res_vmg = ds.vmg[boat_mask] - pred_vmg_lodo[boat_mask]
    above_p90 = (ds.sog[boat_mask] >= pred_p90_lodo[boat_mask]).astype(float)

    # Cell/leg bootstrap within race (cell-level resampling preserves within-race empirical uncertainty)
    n_cells = int(w.size)
    rng = np.random.default_rng(POLAR_BOOTSTRAP_SEED + seed_offset)
    if n_cells > 1:
        idx_draws = rng.integers(0, n_cells, size=(POLAR_BOOTSTRAP_DRAWS, n_cells))
        mult = np.apply_along_axis(lambda row: np.bincount(row, minlength=n_cells), 1, idx_draws).astype(float)
        sog_ci = _bootstrap_ci_matrix(w, w * res_lodo, mult)
        vmg_ci = _bootstrap_ci_matrix(w, w * res_vmg, mult)
    else:
        pt_s = round(float(res_lodo[0]), 3)
        pt_v = round(float(res_vmg[0]), 3)
        sog_ci = {"value": pt_s, "ci_low_kt": pt_s, "ci_high_kt": pt_s, "bootstrap_se_kt": 0.0}
        vmg_ci = {"value": pt_v, "ci_low_kt": pt_v, "ci_high_kt": pt_v, "bootstrap_se_kt": 0.0}

    def opt_mean(sub: np.ndarray, values: np.ndarray) -> float | None:
        if not np.any(sub):
            return None
        return round(float(np.average(values[sub], weights=w[sub])), 3)

    is_up = ds.mode[boat_mask] == 1
    is_stbd = ds.tack[boat_mask] > 0

    return {
        "schema_version": POLAR_SCHEMA_VERSION,
        "method_version": POLAR_METHOD_VERSION,
        "quality": "derived",
        "reason": None,
        "evaluation_scope": eval_scope,
        "steady_sample_count": int(round(float(w.sum()))),
        "steady_coverage_s": round(float(w.sum()), 1),
        "leg_cluster_count": int(len(set(int(c) for c in ds.cluster_id[boat_mask]))),
        "mean_observed_sog_kt": round(float(np.average(ds.sog[boat_mask], weights=w)), 2),
        "mean_predicted_sog_kt": round(float(np.average(pred_sog_lodo[boat_mask], weights=w)), 2),
        "mean_observed_wind_vmg_kt": round(float(np.average(ds.vmg[boat_mask], weights=w)), 2),
        "mean_predicted_wind_vmg_kt": round(float(np.average(pred_vmg_lodo[boat_mask], weights=w)), 2),
        "sog_residual_kt": sog_ci,
        "wind_vmg_residual_kt": vmg_ci,
        "loro_sog_residual_kt": round(float(np.average(res_loro, weights=w)), 3),
        "lodo_sog_residual_kt": round(float(np.average(res_lodo, weights=w)), 3),
        "in_sample_sog_residual_kt": round(float(np.average(res_in, weights=w)), 3),
        "upwind_sog_residual_kt": opt_mean(is_up, res_lodo),
        "downwind_sog_residual_kt": opt_mean(~is_up, res_lodo),
        "port_sog_residual_kt": opt_mean(~is_stbd, res_lodo),
        "starboard_sog_residual_kt": opt_mean(is_stbd, res_lodo),
        "above_p90_share": round(float(np.average(above_p90, weights=w)), 4),
        "bootstrap_draws": POLAR_BOOTSTRAP_DRAWS,
        "traffic_excluded_s": float(filt.get("traffic_excluded_s", 0.0)),
        "observed_bins": _build_observed_bins(ds, boat_mask, pred_sog_lodo),
    }


def attach_single_race_polar_fallback(detail: dict[str, Any]) -> dict[str, Any]:
    """Attach standalone single-race observed ground-speed polar output cleanly."""
    race_id = str((detail.get("race") or {}).get("id") or "race")
    ds = _assemble_dataset({race_id: detail})
    if ds is None:
        for boat in detail.get("boats", []):
            boat["polar"] = _make_boat_residual_block(
                boat, None, None, None, None, None, None, None, "single_race_unavailable"
            )
        detail["polar_analysis"] = {
            "schema_version": POLAR_SCHEMA_VERSION,
            "method_version": POLAR_METHOD_VERSION,
            "race_id": race_id,
            "quality": "unavailable",
            "reason": "no steady-state 1 Hz telemetry samples available for ground-speed polar",
            "evaluation_scope": "single_race_unavailable",
            "caveats": POLAR_CAVEATS,
            "definitions": POLAR_DEFINITIONS,
            "validation_summary": None,
            "brackets": {"upwind": [], "downwind": []},
        }
        return detail

    all_mask = np.ones(len(ds.weights), dtype=bool)
    fit = _fit_and_predict_subset(ds, all_mask, all_mask)
    pred_sog = fit["eval_sog"]
    pred_vmg = fit["eval_vmg"]
    pred_p90 = fit["eval_p90"]

    for idx_b, boat in enumerate(detail.get("boats", [])):
        bid = str(boat.get("id") or "")
        bmask = ds.boat_id == bid
        boat["polar"] = _make_boat_residual_block(
            boat,
            ds,
            bmask,
            pred_sog,
            pred_sog,
            pred_sog,
            pred_vmg,
            pred_p90,
            "in_race_only",
            seed_offset=idx_b + 1,
        )

    rng = np.random.default_rng(POLAR_BOOTSTRAP_SEED)
    C = len(ds.cluster_key)
    draws = rng.integers(0, C, size=(POLAR_BOOTSTRAP_DRAWS, C))
    mult = np.apply_along_axis(lambda row: np.bincount(row, minlength=C), 1, draws).astype(float)
    tack_summary = _compute_archive_tack_bootstrap(ds, mult)

    detail["polar_analysis"] = {
        "schema_version": POLAR_SCHEMA_VERSION,
        "method_version": POLAR_METHOD_VERSION,
        "race_id": race_id,
        "quality": "derived",
        "reason": None,
        "evaluation_scope": "in_race_only",
        "caveats": POLAR_CAVEATS,
        "definitions": POLAR_DEFINITIONS,
        "validation_summary": {
            "race_cell_count": int(len(ds.weights)),
            "race_steady_coverage_s": round(float(ds.weights.sum()), 1),
            "in_sample_sog_rmse_kt": _validation_metrics(
                ds, pred_sog, pred_vmg, fit["eval_p50"], pred_p90, "In-race fit", 1
            )["sog_rmse_kt"],
            "tack_fixed_effect": tack_summary,
        },
        "brackets": _build_race_brackets(ds, all_mask, all_mask),
    }
    return detail


def refresh_archive_polar_models(details_by_race_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Fit cross-validated observed ground-speed polar across all archive races.

    Runs Leave-One-Race-Out (LORO) and Day-Grouped (Leave-One-Day-Out, LODO) CV
    alongside 500-draw leg-cluster bootstrap confidence intervals, mutating each
    ``detail['polar_analysis']`` and ``boat['polar']`` and returning ``polar_model``
    for ``analysis/index.json``.
    """
    ds = _assemble_dataset(details_by_race_id)
    if ds is None:
        for detail in details_by_race_id.values():
            attach_single_race_polar_fallback(detail)
        return None

    N = len(ds.weights)
    all_mask = np.ones(N, dtype=bool)
    in_fit = _fit_and_predict_subset(ds, all_mask, all_mask)
    in_sog = in_fit["eval_sog"]
    in_vmg = in_fit["eval_vmg"]
    in_p50 = in_fit["eval_p50"]
    in_p90 = in_fit["eval_p90"]

    # Unconditioned mode-only baseline evaluated LODO
    base_sog = np.zeros(N, dtype=float)
    base_vmg = np.zeros(N, dtype=float)
    base_p50 = np.zeros(N, dtype=float)
    base_p90 = np.zeros(N, dtype=float)

    # Leave-One-Race-Out CV
    loro_sog = np.zeros(N, dtype=float)
    loro_vmg = np.zeros(N, dtype=float)
    loro_p50 = np.zeros(N, dtype=float)
    loro_p90 = np.zeros(N, dtype=float)
    unique_races = sorted(set(ds.race_id.tolist()))
    for rid in unique_races:
        ev = ds.race_id == rid
        tr = ~ev
        if np.any(tr):
            fold = _fit_and_predict_subset(ds, tr, ev)
            loro_sog[ev] = fold["eval_sog"]
            loro_vmg[ev] = fold["eval_vmg"]
            loro_p50[ev] = fold["eval_p50"]
            loro_p90[ev] = fold["eval_p90"]
        else:
            loro_sog[ev] = in_sog[ev]
            loro_vmg[ev] = in_vmg[ev]
            loro_p50[ev] = in_p50[ev]
            loro_p90[ev] = in_p90[ev]

    # Day-Grouped CV (Leave-One-Day-Out)
    lodo_sog = np.zeros(N, dtype=float)
    lodo_vmg = np.zeros(N, dtype=float)
    lodo_p50 = np.zeros(N, dtype=float)
    lodo_p90 = np.zeros(N, dtype=float)
    unique_days = sorted(set(ds.date.tolist()))
    for day in unique_days:
        ev = ds.date == day
        tr = ~ev
        if np.any(tr):
            fold = _fit_and_predict_subset(ds, tr, ev)
            lodo_sog[ev] = fold["eval_sog"]
            lodo_vmg[ev] = fold["eval_vmg"]
            lodo_p50[ev] = fold["eval_p50"]
            lodo_p90[ev] = fold["eval_p90"]
            for m in (1, 0):
                tr_m = tr & (ds.mode == m)
                ev_m = ev & (ds.mode == m)
                if np.any(ev_m):
                    ref = tr_m if np.any(tr_m) else tr
                    base_sog[ev_m] = float(np.average(ds.sog[ref], weights=ds.weights[ref]))
                    base_vmg[ev_m] = float(np.average(ds.vmg[ref], weights=ds.weights[ref]))
                    order = np.argsort(ds.sog[ref])
                    w_ord = ds.weights[ref][order]
                    cdf = np.cumsum(w_ord) / max(1e-9, float(w_ord.sum()))
                    base_p50[ev_m] = float(ds.sog[ref][order][int(np.argmax(cdf >= 0.50))])
                    base_p90[ev_m] = float(ds.sog[ref][order][int(np.argmax(cdf >= 0.90))])
        else:
            lodo_sog[ev] = in_sog[ev]
            lodo_vmg[ev] = in_vmg[ev]
            lodo_p50[ev] = in_p50[ev]
            lodo_p90[ev] = in_p90[ev]

    # Leg-cluster bootstrap multiplicity matrix (B x C)
    rng = np.random.default_rng(POLAR_BOOTSTRAP_SEED)
    C = len(ds.cluster_key)
    boot_draws = rng.integers(0, C, size=(POLAR_BOOTSTRAP_DRAWS, C))
    mult = np.apply_along_axis(lambda row: np.bincount(row, minlength=C), 1, boot_draws).astype(float)

    tack_fixed_effect = _compute_archive_tack_bootstrap(ds, mult)
    validation = {
        "baseline_mode_only": _validation_metrics(
            ds, base_sog, base_vmg, base_p50, base_p90, "Unconditioned leg-mode baseline", len(unique_days)
        ),
        "leave_one_race_out": _validation_metrics(
            ds, loro_sog, loro_vmg, loro_p50, loro_p90, "Leave-One-Race-Out CV (LORO)", len(unique_races)
        ),
        "leave_one_day_out": _validation_metrics(
            ds, lodo_sog, lodo_vmg, lodo_p50, lodo_p90, "Day-Grouped CV (Leave-One-Day-Out)", len(unique_days)
        ),
    }

    # Team conditional residuals across the archive with leg-cluster bootstrap CIs
    res_lodo_all = ds.sog - lodo_sog
    res_loro_all = ds.sog - loro_sog
    res_in_all = ds.sog - in_sog
    res_vmg_all = ds.vmg - lodo_vmg
    above_p90_all = (ds.sog >= lodo_p90).astype(float)

    team_rows: list[dict[str, Any]] = []
    for tcode in sorted(set(ds.team_code.tolist())):
        tm = ds.team_code == tcode
        if not np.any(tm):
            continue
        cw = np.bincount(ds.cluster_id[tm], weights=ds.weights[tm], minlength=C)
        cy_lodo = np.bincount(ds.cluster_id[tm], weights=ds.weights[tm] * res_lodo_all[tm], minlength=C)
        cy_loro = np.bincount(ds.cluster_id[tm], weights=ds.weights[tm] * res_loro_all[tm], minlength=C)
        cy_in = np.bincount(ds.cluster_id[tm], weights=ds.weights[tm] * res_in_all[tm], minlength=C)
        cy_vmg = np.bincount(ds.cluster_id[tm], weights=ds.weights[tm] * res_vmg_all[tm], minlength=C)

        w_tm = ds.weights[tm]
        up_tm = tm & (ds.mode == 1)
        dn_tm = tm & (ds.mode == 0)
        port_tm = tm & (ds.tack < 0)
        stbd_tm = tm & (ds.tack > 0)

        team_rows.append(
            {
                "team_code": tcode,
                "race_count": int(len(set(ds.race_id[tm].tolist()))),
                "leg_cluster_count": int(len(set(int(c) for c in ds.cluster_id[tm]))),
                "steady_coverage_s": round(float(w_tm.sum()), 1),
                "lodo_sog_residual_kt": _bootstrap_ci_matrix(cw, cy_lodo, mult),
                "loro_sog_residual_kt": _bootstrap_ci_matrix(cw, cy_loro, mult),
                "in_sample_sog_residual_kt": _bootstrap_ci_matrix(cw, cy_in, mult),
                "wind_vmg_residual_kt": _bootstrap_ci_matrix(cw, cy_vmg, mult),
                "upwind_sog_residual_kt": (
                    round(float(np.average(res_lodo_all[up_tm], weights=ds.weights[up_tm])), 3)
                    if np.any(up_tm)
                    else None
                ),
                "downwind_sog_residual_kt": (
                    round(float(np.average(res_lodo_all[dn_tm], weights=ds.weights[dn_tm])), 3)
                    if np.any(dn_tm)
                    else None
                ),
                "port_sog_residual_kt": (
                    round(float(np.average(res_lodo_all[port_tm], weights=ds.weights[port_tm])), 3)
                    if np.any(port_tm)
                    else None
                ),
                "starboard_sog_residual_kt": (
                    round(float(np.average(res_lodo_all[stbd_tm], weights=ds.weights[stbd_tm])), 3)
                    if np.any(stbd_tm)
                    else None
                ),
                "above_p90_share": round(float(np.average(above_p90_all[tm], weights=w_tm)), 4),
                "bootstrap_draws": POLAR_BOOTSTRAP_DRAWS,
            }
        )
    team_rows.sort(
        key=lambda row: -(row["lodo_sog_residual_kt"]["value"] if row["lodo_sog_residual_kt"] else -999.0)
    )

    twa_grids = {
        "upwind": [30.0 + 2.5 * i for i in range(18)],
        "downwind": [110.0 + 2.5 * i for i in range(25)],
    }
    archive_curves: dict[str, list[dict[str, Any]]] = {"upwind": [], "downwind": []}
    for mode_name, mode_val in (("upwind", 1), ("downwind", 0)):
        for bid, blabel, b_lo, b_hi, b_ref in ARCHIVE_TWS_BRACKETS:
            pts = _eval_curve_points(ds, all_mask, mode_val, b_lo, b_hi, twa_grids[mode_name])
            if pts:
                archive_curves[mode_name].append(
                    {
                        "id": bid,
                        "label": blabel,
                        "tws_min_kt": b_lo,
                        "tws_max_kt": b_hi,
                        "tws_ref_kt": b_ref,
                        "points": pts,
                    }
                )

    # Update every race detail in place with archive-backed LORO/LODO residuals & curves
    for r_idx, (race_id, detail) in enumerate(sorted(details_by_race_id.items())):
        rmask = ds.race_id == race_id
        if not np.any(rmask):
            attach_single_race_polar_fallback(detail)
            continue
        for b_idx, boat in enumerate(detail.get("boats", [])):
            bid = str(boat.get("id") or "")
            bmask = rmask & (ds.boat_id == bid)
            boat["polar"] = _make_boat_residual_block(
                boat,
                ds,
                bmask,
                loro_sog,
                lodo_sog,
                in_sog,
                lodo_vmg,
                lodo_p90,
                "out_of_sample_archive_cv",
                seed_offset=r_idx * 31 + b_idx + 1,
            )
        w_r = ds.weights[rmask]
        detail["polar_analysis"] = {
            "schema_version": POLAR_SCHEMA_VERSION,
            "method_version": POLAR_METHOD_VERSION,
            "race_id": race_id,
            "quality": "derived",
            "reason": None,
            "evaluation_scope": "out_of_sample_archive_cv",
            "caveats": POLAR_CAVEATS,
            "definitions": POLAR_DEFINITIONS,
            "validation_summary": {
                "race_cell_count": int(w_r.size),
                "race_steady_coverage_s": round(float(w_r.sum()), 1),
                "loro_sog_rmse_kt": round(math.sqrt(float(np.average((ds.sog[rmask] - loro_sog[rmask]) ** 2, weights=w_r))), 3),
                "lodo_sog_rmse_kt": round(math.sqrt(float(np.average((ds.sog[rmask] - lodo_sog[rmask]) ** 2, weights=w_r))), 3),
                "loro_sog_mae_kt": round(float(np.average(np.abs(ds.sog[rmask] - loro_sog[rmask]), weights=w_r)), 3),
                "lodo_sog_mae_kt": round(float(np.average(np.abs(ds.sog[rmask] - lodo_sog[rmask]), weights=w_r)), 3),
                "tack_fixed_effect": tack_fixed_effect,
            },
            "brackets": _build_race_brackets(ds, rmask, all_mask),
        }

    return {
        "schema_version": POLAR_SCHEMA_VERSION,
        "method_version": POLAR_METHOD_VERSION,
        "evaluation_scope": f"{len(details_by_race_id)}-session AC40 archive",
        "steady_state_filter": {
            "sample_cadence_hz": 1,
            "min_sog_kt": STEADY_MIN_SOG_KT,
            "max_sog_kt": STEADY_MAX_SOG_KT,
            "min_tws_kt": STEADY_MIN_TWS_KT,
            "max_tws_kt": STEADY_MAX_TWS_KT,
            "upwind_abs_twa_deg": list(UPWIND_ABS_TWA_RANGE),
            "downwind_abs_twa_deg": list(DOWNWIND_ABS_TWA_RANGE),
            "manoeuvre_exclusion_s": MANOEUVRE_EXCLUSION_DEFAULT_MS / 1000.0,
            "gate_exclusion_s": GATE_EXCLUSION_MS / 1000.0,
            "max_turn_rate_deg_s": MAX_STEADY_TURN_RATE_DEG_S,
            "min_competitor_separation_m": MIN_COMPETITOR_SEPARATION_M,
        },
        "caveats": POLAR_CAVEATS,
        "definitions": POLAR_DEFINITIONS,
        "counts": {
            "eligible_races": len(unique_races),
            "excluded_races": max(0, len(details_by_race_id) - len(unique_races)),
            "distinct_days": len(unique_days),
            "boat_leg_clusters": C,
            "steady_coverage_s": round(float(ds.weights.sum()), 1),
            "steady_cells": int(N),
        },
        "tack_fixed_effect": tack_fixed_effect,
        "validation": validation,
        "team_residuals": team_rows,
        "curves": archive_curves,
    }
