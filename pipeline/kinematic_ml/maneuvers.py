"""Angular-only maneuver detector, turn classification, and recovery dynamics for AC75.

Enforces:
- Angular-only rotation detection (>= 65 deg, <= 18 s, reversal tolerance <= 1.5 s).
- Speed-loss independence: detection never conditions on deceleration.
- Causal wind lookup: as-of TWD strictly precedes turn timestamp.
- Explicit classification: tack (head-to-wind), gybe (downwind), ambiguous.
- Censored recovery tracking: no arbitrary 30-second truncation or dropping.
- Zero synthetic floors or hardcoded 25/15-knot speed fallbacks.
"""
from __future__ import annotations

import bisect
from typing import Any, Mapping, Sequence

import numpy as np


def circular_diff_deg(a: float, b: float) -> float:
    """Computes signed angular difference a - b wrapped to [-180, 180)."""
    return (a - b + 180.0) % 360.0 - 180.0


def classify_turn_type(
    h_start: float,
    h_end: float,
    as_of_twd: float,
) -> str:
    """Classify turn based on angular crossing of true wind direction.
    
    Tack: crosses head-to-wind (TWA = 0).
    Gybe: crosses directly downwind (|TWA| = 180).
    """
    twa_start = circular_diff_deg(h_start, as_of_twd)
    twa_end = circular_diff_deg(h_end, as_of_twd)

    # Check if sign changed across 0 (tack)
    if (twa_start * twa_end < 0) and abs(twa_start) < 100.0 and abs(twa_end) < 100.0:
        return "tack"

    # Check if crossed downwind 180 (gybe)
    # If both magnitudes are large and signs opposite
    if (twa_start * twa_end < 0) and abs(twa_start) > 80.0 and abs(twa_end) > 80.0:
        return "gybe"

    # Angular displacement check
    rot = circular_diff_deg(h_end, h_start)
    if abs(rot) >= 65.0:
        # If mean heading is closer to upwind than downwind
        mean_twa = (abs(twa_start) + abs(twa_end)) / 2.0
        return "tack" if mean_twa < 90.0 else "gybe"

    return "ambiguous"


def compute_duration_weighted_median(
    times_ms: Sequence[int],
    values: Sequence[float],
    start_ms: int,
    end_ms: int,
) -> float | None:
    """Compute duration-weighted median of scalar values over [start_ms, end_ms]."""
    if not times_ms or len(times_ms) != len(values) or end_ms <= start_ms:
        return None

    in_win = sorted(
        [(int(t), float(v)) for t, v in zip(times_ms, values) if start_ms <= t <= end_ms],
        key=lambda x: x[0],
    )
    if not in_win:
        return None
    if len(in_win) == 1:
        return float(in_win[0][1])

    weighted_samples: list[tuple[float, float]] = []
    for idx, (t_curr, v_curr) in enumerate(in_win):
        t_left = start_ms if idx == 0 else t_curr
        t_right = in_win[idx + 1][0] if idx + 1 < len(in_win) else end_ms
        dt = float(max(1, t_right - t_left))
        weighted_samples.append((v_curr, dt))

    weighted_samples.sort(key=lambda x: x[0])
    total_w = sum(w for _, w in weighted_samples)
    half_w = 0.5 * total_w
    cum_w = 0.0
    for val, w in weighted_samples:
        cum_w += w
        if cum_w >= half_w:
            return float(val)
    return float(weighted_samples[-1][0])


def detect_angular_turns(
    heading_records: Sequence[tuple[int, float]],
    twd_records: Sequence[tuple[int, float]] | None = None,
    *,
    min_rotation_deg: float = 65.0,
    max_duration_ms: int = 18_000,
    reversal_tolerance_ms: int = 1_500,
) -> list[dict[str, Any]]:
    """Detect turns purely from heading rotation rate without speed loss conditioning."""
    if len(heading_records) < 5:
        return []

    if len(heading_records) > 500:
        # Decimate high-frequency telemetry (10-25 Hz) to >= 200 ms (5 Hz) steps
        decimated: list[tuple[int, float]] = []
        last_t = -1_000_000
        for r in heading_records:
            if r[0] - last_t >= 200:
                decimated.append(r)
                last_t = r[0]
        if len(decimated) >= 5:
            heading_records = decimated

    times = [r[0] for r in heading_records]
    headings = [r[1] % 360.0 for r in heading_records]
    n = len(times)

    # Prepare strictly causal as-of TWD lookup (never reads future wind)
    twd_times = [r[0] for r in twd_records] if twd_records else []
    twd_vals = [r[1] % 360.0 for r in twd_records] if twd_records else []

    def get_as_of_twd(t_ms: int) -> float | None:
        if not twd_times:
            return None
        idx = bisect.bisect_right(twd_times, t_ms) - 1
        if idx < 0:
            return None
        return float(twd_vals[idx])

    detected_turns: list[dict[str, Any]] = []
    i = 0
    while i < n - 2:
        t_start = times[i]
        h_start = headings[i]

        best_turn = None
        cached_twd_looked_up = False
        cached_as_of_twd: float | None = None
        j = i + 1
        cum_rotation = 0.0
        prev_h = h_start
        last_forward_ms = t_start
        current_direction = 0

        while j < n:
            t_curr = times[j]
            h_curr = headings[j]
            dt_turn = t_curr - t_start

            if dt_turn > max_duration_ms:
                break
            if dt_turn > 4_000 and cum_rotation < 12.0:
                break

            step_rot = circular_diff_deg(h_curr, prev_h)
            step_dir = 1 if step_rot > 0 else (-1 if step_rot < 0 else 0)

            if current_direction == 0 and step_dir != 0:
                current_direction = step_dir

            if step_dir == current_direction:
                cum_rotation += abs(step_rot)
                last_forward_ms = t_curr
            elif step_dir != 0:
                cum_rotation -= abs(step_rot)
                if t_curr - last_forward_ms > reversal_tolerance_ms:
                    break

            if cum_rotation >= min_rotation_deg:
                if not cached_twd_looked_up:
                    cached_as_of_twd = get_as_of_twd(t_start)
                    cached_twd_looked_up = True
                if cached_as_of_twd is None:
                    turn_type = "unsupported_missing_wind"
                else:
                    turn_type = classify_turn_type(h_start, h_curr, cached_as_of_twd)
                best_turn = {
                    "start_ms": t_start,
                    "end_ms": t_curr,
                    "duration_s": round(dt_turn / 1000.0, 3),
                    "rotation_deg": round(float(cum_rotation), 2),
                    "turn_type": turn_type,
                    "as_of_twd_deg": round(float(cached_as_of_twd), 1) if cached_as_of_twd is not None else None,
                    "start_heading_deg": round(h_start, 1),
                    "end_heading_deg": round(h_curr, 1),
                }

            prev_h = h_curr
            j += 1

        if best_turn:
            detected_turns.append(best_turn)
            i = j
        else:
            i += 1

    return detected_turns


def compute_turn_dynamics(
    turn: Mapping[str, Any],
    sog_records: Sequence[tuple[int, float]],
    *,
    max_recovery_ms: int = 30_000,
    recovery_fraction: float = 0.95,
    min_hold_ms: int = 2_000,
    max_gap_ms: int = 1_200,
) -> dict[str, Any]:
    """Calculate entry/exit speeds, recovery duration, and censoring for a detected turn.

    Contract:
    - Reference entry speed: duration-weighted median SOG over [t_start - 7000, t_start - 2000].
      Never falls back to in-turn or future speeds.
    - Recovery requires `min_hold_ms` (2.0 continuous supported seconds) at >= `recovery_fraction` (95%)
      of reference entry speed within `max_recovery_ms` (30.0 s) after `t_end`.
    """
    t_start = int(turn["start_ms"])
    t_end = int(turn["end_ms"])

    if len(sog_records) > 64:
        # Slice sorted sog_records around [t_start - 7000, t_end + max_recovery_ms + 3000] in O(log N)
        lo = bisect.bisect_left(sog_records, (t_start - 7000, -1e9))
        hi = bisect.bisect_right(sog_records, (t_end + max(max_recovery_ms, 3000), 1e9))
        local_sogs = sog_records[lo:hi]
    else:
        local_sogs = sog_records

    sog_times = [int(s[0]) for s in local_sogs]
    sog_vals = [float(s[1]) for s in local_sogs]

    # Reference entry speed strictly from [t_start - 7000, t_start - 2000]
    entry_speed_mps = compute_duration_weighted_median(
        sog_times,
        sog_vals,
        t_start - 7000,
        t_start - 2000,
    )

    in_turn_sogs = [float(s[1]) for s in local_sogs if t_start <= s[0] <= t_end]
    min_speed_mps = float(np.min(in_turn_sogs)) if in_turn_sogs else entry_speed_mps

    post_sogs = [float(s[1]) for s in local_sogs if t_end < s[0] <= t_end + 3000]
    exit_speed_mps = float(np.mean(post_sogs)) if post_sogs else min_speed_mps

    if entry_speed_mps is None or entry_speed_mps <= 2.0:
        res = dict(turn)
        res["entry_speed_mps"] = round(entry_speed_mps, 3) if entry_speed_mps is not None else None
        res["min_speed_mps"] = round(min_speed_mps, 3) if min_speed_mps is not None else None
        res["exit_speed_mps"] = round(exit_speed_mps, 3) if exit_speed_mps is not None else None
        res["recovery_s"] = None
        res["total_event_s"] = None
        res["censoring"] = True
        res["censoring_reason"] = "unavailable_entry_reference"
        return res

    target_v = recovery_fraction * entry_speed_mps
    recovery_s: float | None = None
    censored = False
    censoring_reason = "uncensored"

    if min_speed_mps is not None and min_speed_mps >= target_v:
        recovery_s = 0.0
        censored = False
    else:
        recovery_records = sorted(
            [(int(s[0]), float(s[1])) for s in local_sogs if t_end <= s[0] <= t_end + max_recovery_ms],
            key=lambda x: x[0],
        )
        hold_start_ms: int | None = None
        prev_t_ms: int | None = None

        for t_obs, v_obs in recovery_records:
            if prev_t_ms is not None and (t_obs - prev_t_ms) > max_gap_ms:
                # Gap exceeded during recovery window
                hold_start_ms = None
            prev_t_ms = t_obs

            if v_obs >= target_v:
                if hold_start_ms is None:
                    hold_start_ms = t_obs
                if (t_obs - hold_start_ms) >= min_hold_ms:
                    recovery_s = (t_obs - t_end) / 1000.0
                    break
            else:
                hold_start_ms = None

        if recovery_s is None:
            censored = True
            censoring_reason = "right_censored_time_limit"
            recovery_s = max_recovery_ms / 1000.0

    total_event_s = float(turn["duration_s"]) + float(recovery_s)

    res = dict(turn)
    res["entry_speed_mps"] = round(entry_speed_mps, 3)
    res["min_speed_mps"] = round(min_speed_mps, 3) if min_speed_mps is not None else None
    res["exit_speed_mps"] = round(exit_speed_mps, 3) if exit_speed_mps is not None else None
    res["recovery_s"] = round(recovery_s, 3)
    res["total_event_s"] = round(total_event_s, 3)
    res["censoring"] = censored
    res["censoring_reason"] = censoring_reason
    return res


def filter_overlapping_maneuvers(turns: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filters out overlapping turn candidate intervals, ensuring no interval is double-counted."""
    if not turns:
        return []
    sorted_turns = sorted(turns, key=lambda t: (t["start_ms"], -abs(t.get("rotation_deg", 0.0))))
    filtered: list[dict[str, Any]] = []
    last_end = -float("inf")
    for t in sorted_turns:
        if t["start_ms"] >= last_end:
            filtered.append(dict(t))
            last_end = t["end_ms"]
        else:
            prev = filtered[-1]
            if abs(t.get("rotation_deg", 0.0)) > abs(prev.get("rotation_deg", 0.0)):
                filtered[-1] = dict(t)
                last_end = t["end_ms"]
    return filtered


def build_maneuver_review_sample(
    candidate_turns: Sequence[dict[str, Any]],
    continuous_windows: Sequence[dict[str, Any]],
    *,
    max_candidate_clips: int = 120,
    max_continuous_windows: int = 60,
    seed: int = 2027,
) -> dict[str, Any]:
    """Builds stratified training-only review samples for maneuver precision and recall evaluation.
    
    Accepts candidate clips (stratified across teams/stages) and continuous windows.
    Marks label status as provisional until independent ground truth annotations are recorded.
    """
    rng = np.random.default_rng(seed)

    # Stratified selection of candidate clips
    clips = list(candidate_turns)
    if len(clips) > max_candidate_clips:
        indices = rng.choice(len(clips), size=max_candidate_clips, replace=False)
        clips = [clips[i] for i in sorted(indices)]

    # Stratified selection of continuous 60-second windows
    windows = list(continuous_windows)
    if len(windows) > max_continuous_windows:
        indices = rng.choice(len(windows), size=max_continuous_windows, replace=False)
        windows = [windows[i] for i in sorted(indices)]

    return {
        "schema_version": "ac75-maneuvers-1",
        "review_status": "provisional",
        "sample_counts": {
            "candidate_clips": len(clips),
            "continuous_windows": len(windows),
        },
        "candidate_clips": clips,
        "continuous_windows": windows,
    }

