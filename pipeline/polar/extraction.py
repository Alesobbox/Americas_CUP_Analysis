"""Retain accepted timestamped seconds and legacy descriptive cell summaries."""

from collections import defaultdict
import math
import numpy as np
from .inputs import _boat_eligible, _coverage_valid, _circular_delta_deg, resolve_inputs
from .constants import (
    GATE_EXCLUSION_MS,
    MANOEUVRE_EXCLUSION_DEFAULT_MS,
    MAX_STEADY_TURN_RATE_DEG_S,
    MIN_COMPETITOR_SEPARATION_M,
    STEADY_MIN_SOG_KT,
    STEADY_MAX_SOG_KT,
    STEADY_MIN_TWS_KT,
    STEADY_MAX_TWS_KT,
    UPWIND_ABS_TWA_RANGE,
    DOWNWIND_ABS_TWA_RANGE,
)


def _close_traffic(state, index, timestamp):
    tel = state["tel"]
    for boat in state["detail"]["boats"]:
        if boat["id"] == state["boat"]["id"]:
            continue
        other = state["arrays"].get(boat["id"])
        if other is None or not _coverage_valid(
            boat.get("source_coverage"), timestamp, fields=("gnss",)
        ):
            continue
        start = (boat.get("start") or {}).get("crossing_time_ms")
        ends = [leg["end_ms"] for leg in boat.get("legs", []) if leg.get("end_ms") is not None]
        if start is None or timestamp < start or not ends or timestamp > max(ends):
            continue
        if index >= len(other.get("x", [])) or index >= len(other.get("y", [])):
            continue
        distance = math.hypot(
            tel["x"][index] - other["x"][index], tel["y"][index] - other["y"][index]
        )
        if distance < MIN_COMPETITOR_SEPARATION_M:
            return True
    return False


def _sample(state, index, leg):
    timestamp = state["times"][index]
    if not _coverage_valid(state["boat"].get("source_coverage"), timestamp):
        return "coverage_excluded", None
    if any(abs(timestamp - t) <= GATE_EXCLUSION_MS for t in state["gates"]):
        return "gate_excluded", None
    if (
        timestamp < leg["start_ms"] + GATE_EXCLUSION_MS
        or timestamp > leg["end_ms"] - GATE_EXCLUSION_MS
    ):
        return "gate_excluded", None
    if any(abs(timestamp - t) <= state["turn_window"] for t in state["turns"]):
        return "manoeuvre_excluded", None
    tel = state["tel"]
    previous = state["previous"].get(index)
    if previous is not None:
        dt = (timestamp - state["times"][previous]) / 1000
        rate = abs(_circular_delta_deg(tel["heading"][previous], tel["heading"][index])) / dt
        if rate > MAX_STEADY_TURN_RATE_DEG_S:
            return "turn_rate_excluded", None
    if _close_traffic(state, index, timestamp):
        return "traffic_excluded", None
    values = {
        key: float(tel[key][index]) for key in ("sog", "tws", "heading", "cog", "twd", "x", "y")
    }
    if not all(math.isfinite(value) for value in values.values()):
        return "out_of_range", None
    sog, tws = values["sog"], values["tws"]
    upwind = leg["leg"] % 2 == 1
    twa = _circular_delta_deg(values["heading"], values["twd"])
    lower, upper = UPWIND_ABS_TWA_RANGE if upwind else DOWNWIND_ABS_TWA_RANGE
    if not (
        STEADY_MIN_SOG_KT <= sog <= STEADY_MAX_SOG_KT
        and STEADY_MIN_TWS_KT <= tws <= STEADY_MAX_TWS_KT
        and lower <= abs(twa) <= upper
    ):
        return "out_of_range", None
    vmg = sog * math.cos(math.radians(_circular_delta_deg(values["cog"], values["twd"])))
    return "steady", {
        "timestamp_ms": int(timestamp),
        "leg": leg["leg"],
        "mode": "upwind" if upwind else "downwind",
        "tack": "STARBOARD" if twa >= 0 else "PORT",
        "tws_kt": tws,
        "abs_twa_deg": abs(twa),
        "sog_kt": sog,
        "wind_vmg_kt": vmg if upwind else -vmg,
        "heading_deg": values["heading"],
        "cog_deg": values["cog"],
        "twd_deg": values["twd"],
        "x_m": values["x"],
        "y_m": values["y"],
    }


def _cells(samples):
    buckets = defaultdict(list)
    for sample in samples:
        key = (
            sample["leg"],
            sample["mode"],
            sample["tack"],
            round(sample["tws_kt"]),
            round(sample["abs_twa_deg"] / 2.5) * 2.5,
        )
        buckets[key].append(sample)
    cells = []
    for (leg, mode, tack, wind, angle), values in sorted(buckets.items()):
        speeds = np.array([row["sog_kt"] for row in values])
        cells.append(
            {
                "leg": leg,
                "mode": mode,
                "tack": tack,
                "tws_bin_kt": wind,
                "twa_bin_deg": angle,
                "sample_count": len(values),
                "coverage_s": len(values),
                "tws_mean_kt": float(np.mean([v["tws_kt"] for v in values])),
                "abs_twa_mean_deg": float(np.mean([v["abs_twa_deg"] for v in values])),
                "sog_mean_kt": float(speeds.mean()),
                "sog_p50_kt": float(np.quantile(speeds, 0.5)),
                "sog_p90_kt": float(np.quantile(speeds, 0.9)),
                "sog_sum_squares_kt2": float((speeds**2).sum()),
                "wind_vmg_mean_kt": float(np.mean([v["wind_vmg_kt"] for v in values])),
            }
        )
    return cells


def _extract_boat(state):
    boat, tel = state["boat"], state["tel"]
    counts, samples = defaultdict(int), []
    needed = ("x", "y", "heading", "cog", "sog", "twd", "tws")
    if not _boat_eligible(boat) or not tel or any(key not in tel for key in needed):
        return samples, counts
    maximum = min(len(state["times"]), *(len(tel[key]) for key in needed))
    for leg in boat.get("legs", []):
        if not leg.get("complete") or leg.get("start_ms") is None or leg.get("end_ms") is None:
            continue
        for index in state["indices"]:
            if index >= maximum:
                break
            timestamp = state["times"][index]
            if not leg["start_ms"] <= timestamp < leg["end_ms"]:
                continue
            reason, sample = _sample(state, index, leg)
            counts[reason] += 1
            if sample is not None:
                samples.append(sample)
    return samples, counts


def extract_race_polar_cells(detail, *, ingest_result=None, replay_doc=None, replay_path=None):
    resolved = resolve_inputs(ingest_result, replay_doc, replay_path)
    if resolved is None:
        for boat in detail.get("boats", []):
            boat["polar_samples"], boat["polar_cells"], boat["polar_filter"] = [], [], {}
        return {"extracted": False, "reason": "no replay telemetry available"}
    times, arrays = resolved
    indices = [i for i, t in enumerate(times) if i == 0 or t // 1000 != times[i - 1] // 1000]
    previous = {b: a for a, b in zip(indices, indices[1:]) if 0 < times[b] - times[a] <= 2000}
    race = detail.get("race") or {}
    turn_window = max(MANOEUVRE_EXCLUSION_DEFAULT_MS, int(65 * race.get("sample_interval_ms", 100)))
    total = 0
    for boat in detail.get("boats", []):
        gates = [
            g["crossing_time_ms"]
            for g in boat.get("gates", [])
            if g.get("crossing_time_ms") is not None
        ]
        start = (boat.get("start") or {}).get("crossing_time_ms")
        if start is not None:
            gates.append(start)
        state = {
            "detail": detail,
            "boat": boat,
            "times": times,
            "arrays": arrays,
            "tel": arrays.get(boat["id"]),
            "indices": indices,
            "previous": previous,
            "gates": gates,
            "turns": [m["timestamp"] for m in boat.get("manoeuvres", [])],
            "turn_window": turn_window,
        }
        samples, counts = _extract_boat(state)
        boat["polar_samples"], boat["polar_cells"] = samples, _cells(samples)
        boat["polar_filter"] = {
            key + "_s": float(value) for key, value in counts.items() if key != "steady"
        }
        boat["polar_filter"].update(
            steady_sample_count=len(samples), steady_coverage_s=float(len(samples))
        )
        total += len(samples)
    return {"extracted": True, "samples": total, "target": "individual accepted 1 Hz observations"}
