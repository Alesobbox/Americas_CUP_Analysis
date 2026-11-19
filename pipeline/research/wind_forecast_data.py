"""Causal official-wind contexts and separately observed endpoint targets."""

from bisect import bisect_left, bisect_right
import math

import numpy as np

HORIZON_MS = 180_000
HISTORY_MS = 120_000
CADENCE_MS = 10_000
MAX_AGE_MS = 2_000
SHIFT_DEG = 5.0
FEATURE_NAMES = ("change_30s_deg", "change_60s_deg", "change_120s_deg", "variation_120s_deg")


def wrapped(value):
    """Signed shortest angular displacement, in degrees."""
    return (np.asarray(value) + 180.0) % 360.0 - 180.0


def direction_stream(samples):
    """Keep finite direction observations with independent source timestamps."""
    values = {}
    for sample in samples:
        timestamp = sample.get("timestamp_ms", sample.get("t"))
        direction = sample.get("twd_deg")
        if (
            isinstance(timestamp, int)
            and not isinstance(timestamp, bool)
            and isinstance(direction, (int, float))
            and not isinstance(direction, bool)
            and math.isfinite(direction)
            and 0 <= direction < 360
        ):
            values[timestamp] = float(direction)
    times = sorted(values)
    return times, [values[timestamp] for timestamp in times]


def previous_grid(stream, start, end):
    """Sample previous measurements only; reject stale values or source gaps."""
    times, directions = stream
    if not times:
        return None
    first = bisect_right(times, start) - 1
    last = bisect_right(times, end)
    active = times[max(0, first) : last]
    if any(b - a > MAX_AGE_MS for a, b in zip(active, active[1:])):
        return None
    values = []
    for timestamp in range(start, end + 1, 1000):
        index = bisect_right(times, timestamp) - 1
        if index < 0 or timestamp - times[index] > MAX_AGE_MS:
            return None
        values.append(directions[index])
    return np.asarray(values, dtype=float)


def build_contexts(record):
    """Future labels never enter the four trailing-context predictors."""
    stream = direction_stream(record.get("samples", []))
    times, _ = stream
    gun = record.get("gun_time_ms", times[0] if times else 0)
    end = record.get("window_end_ms", times[-1] if times else gun)
    rows, counts = [], {"missing_history": 0, "censored_target": 0, "fresh_contexts": 0}
    if end is None:
        end = times[-1] if times else gun
    for timestamp in range(gun, end + 1, CADENCE_MS):
        history = previous_grid(stream, timestamp - HISTORY_MS, timestamp)
        if history is None:
            counts["missing_history"] += 1
            continue
        steps = wrapped(np.diff(history))
        features = [float(wrapped(history[-1] - history[-1 - lag])) for lag in (30, 60, 120)]
        features.append(float(np.sqrt(np.mean(steps * steps))))
        endpoint = timestamp + HORIZON_MS
        future = previous_grid(stream, timestamp, endpoint) if endpoint <= end else None
        delta = None if future is None else float(wrapped(future[-1] - history[-1]))
        counts["fresh_contexts"] += 1
        counts["censored_target"] += int(delta is None)
        rows.append(
            {
                "race_id": record["id"],
                "date": record["date"],
                "issue_ms": timestamp,
                "label_end_ms": endpoint,
                "current_deg": float(history[-1]),
                "features": features,
                "target_delta_deg": delta,
            }
        )
    return rows, counts


def prior_training_rows(rows, day, first_issue_ms):
    """Purge outcomes whose horizon has not finished before this day issues."""
    return [
        row
        for row in rows
        if row["date"] < day
        and row["target_delta_deg"] is not None
        and row["label_end_ms"] < first_issue_ms
    ]


def source_count(record):
    times, _ = direction_stream(record.get("samples", []))
    gun = record.get("gun_time_ms", times[0] if times else 0)
    return len(times), bisect_left(times, gun)
