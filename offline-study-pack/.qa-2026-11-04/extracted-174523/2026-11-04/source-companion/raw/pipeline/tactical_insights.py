"""Timestamp-causal recorded-wind diagnostics, never a calibrated weather forecast.

Raw fields retain independent measurement times. Historical records may arrive
out of order: sorting establishes measurement-time causality, not live arrival
availability. Appending late records with old timestamps can revise history.
"""
from __future__ import annotations

from bisect import bisect_right
import math

SCHEMA_VERSION = "1.0"
METHOD_VERSION = "tactical-1"
SNAPSHOT_INTERVAL_MS = 10_000
MAX_SNAPSHOT_AGE_MS = 12_000
WINDOW_MS = 120_000
MAX_SOURCE_AGE_MS = 2_000
SOURCE = "recorded official wind"
TACTICAL_DEFINITIONS = {
    "direction_change_deg": {
        "label": "Official wind direction change", "unit": "°",
        "formula": "Sum of signed shortest-arc differences between consecutive previous-observation directions on a 1 s grid; positive is clockwise",
        "window": "trailing 120 s ending at snapshot timestamp",
        "denominator": "one complete 120 s direction window; 121 grid points, at least 60 source timestamps, no source gap over 2 s",
        "source": "independent raw official direction observations; previous measurement only, maximum age 2 s",
    },
    "direction_rate_deg_per_min": {
        "label": "Official wind direction trend", "unit": "°/min",
        "formula": "60 × sum((second - mean second) × (unwrapped direction - mean unwrapped direction)) / sum((second - mean second)^2)",
        "window": "trailing 120 s ending at snapshot timestamp",
        "denominator": "sum of squared centered seconds on the 121-point valid 1 s direction grid",
        "source": "independent raw official direction observations; shortest-arc unwrapping, previous measurement only, maximum age 2 s",
    },
    "speed_change_kt": {
        "label": "Official wind speed change", "unit": "kt",
        "formula": "Fresh official speed at window end minus fresh official speed at window start, using previous observations",
        "window": "trailing 120 s ending at snapshot timestamp",
        "denominator": "one complete 120 s speed window; 121 grid points, at least 60 source timestamps, no source gap over 2 s",
        "source": "independent raw official speed observations converted from m/s to knots; previous measurement only, maximum age 2 s",
    },
    "projection_change_deg": {
        "label": "Conditional five-minute direction projection", "unit": "°",
        "formula": "5 × OLS rate; requires |120 s direction change| >= 1°, |rate| >= 0.2°/min, |5 × rate| <= 30°, first/last 60 s OLS slopes with the same nonzero sign and each within max(0.25°/min, 0.5 × |rate|) of full-window rate, residual RMS <= max(1°, 0.2 × |direction change|), and every 1 s direction step <= 3°",
        "window": "next 300 s, conditional on the preceding 120 s trend holding",
        "denominator": "one unvalidated linear extrapolation; not a calibrated weather forecast or an event-arrival estimate",
        "source": "trailing official direction trend only; no future measurements or external weather inputs",
    },
}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def source_wind_observations(direction_series, speed_series):
    """Preserve raw, unpaired field times; no interpolation or held pairing."""
    observations = []
    for field, series in (("twd_deg", direction_series), ("tws_kt", speed_series)):
        for timestamp, value in series:
            observations.append({"timestamp_ms": timestamp, field: value})
    return sorted(observations, key=lambda item: item["timestamp_ms"])


def _streams(samples):
    streams = {"twd_deg": {}, "tws_kt": {}}
    for sample in samples:
        timestamp = sample.get("timestamp_ms", sample.get("t"))
        if not isinstance(timestamp, int) or isinstance(timestamp, bool):
            continue
        for field in streams:
            value = sample.get(field)
            if (_number(value) and ((0 <= value < 360) if field == "twd_deg" else value >= 0)):
                streams[field][timestamp] = float(value)
    return {field: (sorted(values), [values[t] for t in sorted(values)])
            for field, values in streams.items()}


def _window(times, values, timestamp):
    """One-second trailing grid using previous observations <= each grid time."""
    start = timestamp - WINDOW_MS
    grid = []
    for t in range(start, timestamp + 1, 1000):
        index = bisect_right(times, t) - 1
        grid.append(values[index] if index >= 0 and t - times[index] <= MAX_SOURCE_AGE_MS else None)
    first = bisect_right(times, start) - 1
    last = bisect_right(times, timestamp)
    active_times = times[max(0, first):last]
    count = len(times[bisect_right(times, start - 1):last])
    gaps = [(a, b) for a, b in zip(active_times, active_times[1:]) if b - a > MAX_SOURCE_AGE_MS]
    # Reject the actual unsupported interval, even when the coarse one-second
    # grid happens to land on two apparently fresh endpoints around a gap.
    covered = sum(a is not None and b is not None
                  and not any(left < start + (i + 1) * 1000 and right > start + i * 1000
                              for left, right in gaps)
                  for i, (a, b) in enumerate(zip(grid, grid[1:])))
    complete = (all(value is not None for value in grid) and count >= 60
                and not gaps)
    return grid, count, covered, complete


def _unwrap(values):
    unwrapped = [values[0]]
    for a, b in zip(values, values[1:]):
        unwrapped.append(unwrapped[-1] + (b - a + 180) % 360 - 180)
    return unwrapped


def _slope(values):
    center = (len(values) - 1) / 2
    average = sum(values) / len(values)
    denominator = sum((i - center) ** 2 for i in range(len(values)))
    slope = sum((i - center) * (value - average) for i, value in enumerate(values)) / denominator
    residual = math.sqrt(sum((value - average - slope * (i - center)) ** 2
                             for i, value in enumerate(values)) / len(values))
    return slope * 60, residual


def _projection(values, rate):
    """Conservative conditional extrapolation, deliberately often unavailable."""
    first_rate, _ = _slope(values[:61])
    last_rate, _ = _slope(values[60:])
    _, residual = _slope(values)
    net = values[-1] - values[0]
    if (abs(net) < 1 or abs(rate) < 0.2 or abs(rate * 5) > 30
            or first_rate * last_rate <= 0
            or max(abs(first_rate - rate), abs(last_rate - rate)) > max(0.25, abs(rate) * 0.5)
            or residual > max(1.0, abs(net) * 0.2)
            or max(abs(b - a) for a, b in zip(values, values[1:])) > 3):
        return None, "Recent direction is too flat, variable or steep for a bounded linear projection."
    return round(rate * 5, 2), "Conditional on the last 120 s trend holding for 5 min; unvalidated linear extrapolation, not a calibrated forecast."


def attach_tactical_insights(detail, source_wind_samples, *, window_end_ms=None, source_provenance=None):
    """Attach compact diagnostics. No sample later than a snapshot is consulted."""
    streams = _streams(source_wind_samples)
    direction_times, direction_values = streams["twd_deg"]
    speed_times, speed_values = streams["tws_kt"]
    gun = detail["race"]["gun_time_ms"]
    end = window_end_ms if window_end_ms is not None else detail["race"].get("window_end_ms")
    if end is None:
        end = max([gun, *direction_times, *speed_times])
    snapshots = []
    for timestamp in range(gun, end + 1, SNAPSHOT_INTERVAL_MS):
        values, count, coverage, complete = _window(direction_times, direction_values, timestamp)
        speeds, speed_count, speed_coverage, speed_complete = _window(speed_times, speed_values, timestamp)
        snapshot = {"timestamp_ms": timestamp, "window_start_ms": timestamp - WINDOW_MS,
                    "window_end_ms": timestamp, "coverage_s": coverage, "sample_count": count,
                    "quality": "derived" if complete else "unavailable", "source": SOURCE,
                    "speed_coverage_s": speed_coverage, "speed_sample_count": speed_count,
                    "speed_quality": "derived" if speed_complete else "unavailable",
                    "speed_reason": None if speed_complete else "Need 120 s of fresh official speed observations, at least 60 samples and no source gap over 2 s.",
                    "direction_change_deg": None, "direction_rate_deg_per_min": None,
                    "speed_change_kt": None, "projection_change_deg": None,
                    "projection_reason": "A complete recent wind window is unavailable.", "insights": []}
        if not complete:
            snapshot["reason"] = "Need 120 s of fresh official direction observations, at least 60 samples and no source gap over 2 s."
        else:
            unwrapped = _unwrap(values)
            change = unwrapped[-1] - unwrapped[0]
            rate, _ = _slope(unwrapped)
            projection, projection_reason = _projection(unwrapped, rate)
            snapshot.update(direction_change_deg=round(change, 2), direction_rate_deg_per_min=round(rate, 3),
                            projection_change_deg=projection, projection_reason=projection_reason)
            snapshot["insights"].append({"id": "wind_direction", "title": f"Wind change {change:+.1f}° in 2 min",
                "detail": "Recorded official wind; positive is clockwise (veering), negative is counterclockwise (backing).",
                "quality": "derived", "source": SOURCE, "kind": "observed_direction"})
            if projection is not None:
                snapshot["insights"].append({"id": "wind_projection", "title": f"Conditional 5 min projection: {projection:+.1f}°",
                    "detail": projection_reason, "quality": "conditional", "source": SOURCE, "kind": "conditional_projection"})
        if speed_complete:
            speed_change = speeds[-1] - speeds[0]
            snapshot["speed_change_kt"] = round(speed_change, 2)
            snapshot["insights"].append({"id": "wind_speed", "title": f"Wind speed {speed_change:+.1f} kt in 2 min",
                "detail": "Difference between fresh official speed observations at the ends of the trailing 120 s window.",
                "quality": "derived", "source": SOURCE, "kind": "observed_speed"})
        snapshots.append(snapshot)
    provenance = dict(source_provenance or {})
    provenance.update(direction_sample_count=len(direction_times), speed_sample_count=len(speed_times),
                      first_measurement_ms=min([*direction_times, *speed_times], default=None),
                      last_measurement_ms=max([*direction_times, *speed_times], default=None))
    detail["tactical_insights"] = {"schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION,
        "race_id": detail["race"]["id"], "source": SOURCE, "snapshot_interval_ms": SNAPSHOT_INTERVAL_MS,
        "max_snapshot_age_ms": MAX_SNAPSHOT_AGE_MS, "window_s": 120, "projection_horizon_s": 300,
        "definitions": TACTICAL_DEFINITIONS,
        "availability_basis": "Measurement timestamps only; retrospective, not arrival-time causal. Late records with earlier timestamps can revise history.",
        "source_provenance": provenance, "snapshots": snapshots}
    if end < gun:
        detail["tactical_insights"]["reason"] = "Replay window ends before the source gun; no post-gun tactical interval."
    return detail
