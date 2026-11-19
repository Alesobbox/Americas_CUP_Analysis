"""Turn candidates selected by geometry, with no minimum speed-loss requirement."""

from __future__ import annotations

from pipeline.research.timing_track import Track, active_window, angle_delta, covered, sample_times


def _candidate_type(before: dict, after: dict) -> str | None:
    if before["twa"] * after["twa"] >= 0:
        return None
    before_angle, after_angle = abs(before["twa"]), abs(after["twa"])
    if min(before_angle, after_angle) < 15:
        return None
    if max(before_angle, after_angle) < 90:
        return "TACK"
    if min(before_angle, after_angle) > 90:
        return "GYBE"
    return None


def _turn_bounds(track: Track, timestamp: int) -> tuple[int, int]:
    onset, end = timestamp, timestamp
    for direction in (-1, 1):
        for step in range(1, 7):
            current = timestamp + direction * step * 1000
            a, b = track.state(current), track.state(current - direction * 1000)
            if a is None or b is None or abs(angle_delta(a["heading"], b["heading"])) < 2:
                break
            if direction < 0:
                onset = current
            else:
                end = current
    return onset, end


def _candidate(track: Track, timestamp: int) -> dict | None:
    before, center, after = (track.state(timestamp + offset) for offset in (-3000, 0, 3000))
    if before is None or center is None or after is None:
        return None
    kind = _candidate_type(before, after)
    if kind is None or abs(angle_delta(before["heading"], after["heading"])) < 35:
        return None
    leg = track.leg(timestamp)
    if leg is None:
        return None
    onset, end = _turn_bounds(track, timestamp)
    coverage = track.boat.get("source_coverage") or {}
    if not covered(coverage, timestamp - 3000, timestamp + 3000):
        return None
    if end <= onset:
        return None
    return {
        "timestamp_ms": timestamp,
        "start_ms": onset,
        "end_ms": end,
        "leg": leg["leg"],
        "type": kind,
        "turn_angle_deg": round(abs(angle_delta(before["heading"], after["heading"])), 2),
        "quality": "candidate_geometry",
        "review_status": "unreviewed",
        "selection": "TWA side reversal and at least 35 degrees heading change over six seconds; no speed-loss threshold",
    }


def detect_turn_candidates(track: Track) -> list[dict]:
    window = active_window(track.boat)
    if window is None:
        return []
    output = []
    for timestamp in sample_times(window[0] + 3000, window[1] - 3000):
        if output and timestamp - output[-1]["timestamp_ms"] < 8000:
            continue
        candidate = _candidate(track, timestamp)
        if candidate is not None:
            output.append(candidate)
    return output
