"""Reference-dependent progress deficits with explicit horizon censoring."""

from __future__ import annotations

import math
from collections.abc import Callable
from statistics import median

import numpy as np

from pipeline.research.timing_track import KT_TO_MPS, Track, angle_delta, covered, sample_times

ReferencePredictor = Callable[[dict], dict | None]
HORIZONS_S = (10, 20, 30)


def _steady_reference(track: Track, event: dict) -> tuple[list[dict], list[float]]:
    states, velocities = [], []
    for timestamp in sample_times(event["start_ms"] - 10000, event["start_ms"] - 2000):
        state, prior = track.state(timestamp), track.state(timestamp - 1000)
        leg = track.leg(timestamp)
        if state is None or prior is None or leg is None or leg["leg"] != event["leg"]:
            continue
        bounds = (28, 75) if event["leg"] % 2 else (105, 172)
        if not bounds[0] <= abs(state["twa"]) <= bounds[1] or not 5 <= state["sog"] <= 50:
            continue
        if abs(angle_delta(prior["heading"], state["heading"])) > 6:
            continue
        velocity = track.vmg(state, event["leg"])
        if velocity > 0:
            states.append(state)
            velocities.append(velocity)
    return states, velocities


def _polar_reference(track: Track, event: dict, state: dict, context: dict) -> dict:
    predictor = context.get("predictor")
    if predictor is None:
        return {"quality": "unavailable", "reason": "no held-out polar predictor supplied"}
    features = {
        "timestamp_ms": state["timestamp_ms"],
        "boat_id": track.boat["id"],
        "race_id": context["race_id"],
        "date": context["date"],
        "leg": event["leg"],
        "mode": "upwind" if event["leg"] % 2 else "downwind",
        "tack": "STARBOARD" if state["twa"] >= 0 else "PORT",
        "tws_kt": state["tws"],
        "abs_twa_deg": abs(state["twa"]),
        "heading_deg": state["heading"],
        "cog_deg": state["cog"],
        "twd_deg": state["twd"],
    }
    prediction = predictor(features)
    if prediction is None:
        return {
            "quality": "unavailable",
            "reason": "pre-turn conditions lack held-out polar support",
        }
    speed = prediction.get("sog_kt")
    scope = prediction.get("evaluation_scope")
    if scope not in ("leave_one_day_out", "chronological") or not isinstance(speed, (int, float)):
        return {
            "quality": "unavailable",
            "reason": "polar reference requires an explicit held-out-day scope",
        }
    if not math.isfinite(speed) or speed <= 0:
        return {"quality": "unavailable", "reason": "invalid predicted pre-turn speed"}
    direction = track.axis_deg + (180 if event["leg"] % 2 == 0 else 0)
    velocity = speed * KT_TO_MPS * math.cos(math.radians(angle_delta(direction, state["cog"])))
    if velocity <= 0:
        return {"quality": "unavailable", "reason": "non-positive polar reference progress"}
    return {
        "quality": "conditional",
        "vmg_mps": velocity,
        "evaluation_scope": scope,
        "input_timestamp_ms": state["timestamp_ms"],
        "support": prediction.get("support"),
        "trajectory": "straight pre-turn COG continuation; no mid-turn polar queries",
    }


def _limit(track: Track, event: dict, turns: list[dict]) -> tuple[int, str]:
    leg = track.leg(event["timestamp_ms"])
    if leg is None:
        return event["start_ms"], "missing_leg"
    end = int(leg["end_ms"]) - 8000
    reason = "gate_approach"
    later = [t["start_ms"] for t in turns if t["start_ms"] > event["start_ms"]]
    if later and min(later) < end:
        end, reason = min(later), "next_turn"
    if track.times and track.times[-1] < end:
        end, reason = track.times[-1], "telemetry_end"
    return max(event["start_ms"], end), reason


def _integrate(track: Track, start: int, end: int, leg: int) -> dict:
    cuts = sorted({start, end, *sample_times(start, end)})
    distance, covered_s = 0.0, 0.0
    coverage = track.boat.get("source_coverage") or {}
    for a, b in zip(cuts, cuts[1:]):
        first, last = track.state(a), track.state(b)
        if first is None or last is None or not covered(coverage, a, b):
            continue
        duration = (b - a) / 1000
        distance += 0.5 * (track.vmg(first, leg) + track.vmg(last, leg)) * duration
        covered_s += duration
    return {"distance_m": distance, "coverage_s": covered_s}


def _horizon(
    track: Track, event: dict, reference: dict, limit: tuple[int, str], seconds: int
) -> dict:
    start = event["start_ms"]
    end = min(start + seconds * 1000, limit[0])
    observed = _integrate(track, start, end, event["leg"])
    duration = (end - start) / 1000
    complete = abs(observed["coverage_s"] - seconds) < 1e-6
    deficit = reference["vmg_mps"] * observed["coverage_s"] - observed["distance_m"]
    polar = reference["polar"]
    polar_deficit = (
        polar["vmg_mps"] * observed["coverage_s"] - observed["distance_m"]
        if polar["quality"] == "conditional"
        else None
    )
    return {
        "horizon_s": seconds,
        "observed_duration_s": duration,
        "coverage_s": observed["coverage_s"],
        "right_censored": not complete,
        "censor_reason": (None if complete else limit[1] if duration < seconds else "source_gap"),
        "progress_deficit_m": round(deficit, 3) if complete else None,
        "observed_prefix_deficit_m": round(deficit, 3),
        "observed_progress_m": round(observed["distance_m"], 3),
        "reference_sensitivity_m": (
            [round(v * seconds - observed["distance_m"], 3) for v in reference["vmg_quartiles_mps"]]
            if complete
            else None
        ),
        "polar_reference_deficit_m": round(polar_deficit, 3)
        if complete and polar_deficit is not None
        else None,
    }


def _recovery(track: Track, event: dict, entry_speed: float, limit: int) -> dict:
    end = min(event["start_ms"] + 30000, limit)
    states = [(t, track.state(t)) for t in sample_times(event["start_ms"], end)]
    valid = [(t, s["sog"]) for t, s in states if s is not None]
    if not valid:
        return {"recovery_s": None, "right_censored": True, "minimum_sog_kt": None}
    minimum = min(valid, key=lambda value: value[1])
    recovery = next(
        (t for t, speed in valid if t > minimum[0] and speed >= 0.95 * entry_speed), None
    )
    coverage = track.boat.get("source_coverage") or {}
    uninterrupted = covered(coverage, event["start_ms"], recovery if recovery is not None else end)
    return {
        "recovery_s": (
            round((recovery - minimum[0]) / 1000, 3)
            if recovery is not None and uninterrupted
            else None
        ),
        "right_censored": recovery is None or not uninterrupted,
        "minimum_sog_kt": round(minimum[1], 3),
        "speed_loss_kt": round(entry_speed - minimum[1], 3),
        "speed_regime": "severe_speed_collapse"
        if minimum[1] < 0.5 * entry_speed
        else "other_speed_response",
        "physical_event_label": None,
        "review_required": True,
    }


def characterize_turns(track: Track, turns: list[dict], context: dict) -> list[dict]:
    output = []
    for event in turns:
        states, velocities = _steady_reference(track, event)
        if len(states) < 6:
            output.append(
                {
                    **event,
                    "cost_quality": "unavailable",
                    "cost_reason": "fewer than six supported pre-turn seconds",
                    "horizons": [],
                }
            )
            continue
        polar = _polar_reference(track, event, states[-1], context)
        reference = {
            "vmg_mps": median(velocities),
            "vmg_quartiles_mps": np.quantile(velocities, [0.25, 0.75]).tolist(),
            "polar": polar,
            "sample_count": len(states),
            "window_s": [-10, -2],
            "interpretation": "observed pre-turn straight continuation; quartiles are baseline sensitivity, not confidence bounds",
        }
        limit = _limit(track, event, turns)
        output.append(
            {
                **event,
                "cost_quality": "conditional",
                "reference": reference,
                "horizons": [
                    _horizon(track, event, reference, limit, seconds) for seconds in HORIZONS_S
                ],
                "recovery": _recovery(track, event, median(s["sog"] for s in states), limit[0]),
            }
        )
    return output
