"""Deterministic event/background review sampling and event-level scoring."""

from __future__ import annotations

import hashlib
import random

from pipeline.research.timing_track import Track, active_window, covered, sample_times


def _spaced_sample(rng: random.Random, population: list[int], occupied: list[int]) -> list[int]:
    order = rng.sample(population, len(population))
    chosen = []
    for timestamp in order:
        if all(abs(timestamp - prior) > 16000 for prior in occupied + chosen):
            chosen.append(timestamp)
        if len(chosen) == 3:
            break
    return chosen


def review_windows(track: Track, turns: list[dict], race_id: str) -> list[dict]:
    window = active_window(track.boat)
    if window is None:
        return []
    digest = hashlib.sha256(f"{race_id}:{track.boat['id']}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    candidates = _spaced_sample(rng, [int(event["timestamp_ms"]) for event in turns], [])
    coverage = track.boat.get("source_coverage") or {}
    background = [
        t
        for t in sample_times(window[0] + 8000, window[1] - 8000)
        if all(abs(t - event["timestamp_ms"]) > 16000 for event in turns)
        and covered(coverage, t - 8000, t + 8000)
    ]
    sampled = _spaced_sample(rng, background, candidates)
    rows = []
    for kind, timestamps, population in (
        ("detected_event", candidates, len(turns)),
        ("background", sampled, len(background)),
    ):
        for timestamp in sorted(timestamps):
            rows.append(
                {
                    "id": f"{race_id}:{track.boat['id']}:{kind}:{timestamp}",
                    "boat_id": track.boat["id"],
                    "race_id": race_id,
                    "timestamp_ms": timestamp,
                    "start_ms": timestamp - 8000,
                    "end_ms": timestamp + 8000,
                    "stratum": kind,
                    "sampled_fraction_of_stratum": len(timestamps) / population
                    if population
                    else None,
                    "sampling_scheme": "deterministic shuffled selection with non-overlapping windows; not uniform inclusion probabilities",
                    "review_status": "unreviewed",
                    "reviewed_events": None,
                    "instructions": "Review telemetry and aligned video where available; record TACK/GYBE timestamps and ambiguity. Do not infer touchdown from speed alone.",
                }
            )
    return rows


def _match_events(
    predicted: list[dict], observed: list[dict], tolerance_ms: int
) -> tuple[int, int, int]:
    unmatched = set(range(len(observed)))
    matched = 0
    for candidate in sorted(predicted, key=lambda row: row["timestamp_ms"]):
        matches = [
            index
            for index in unmatched
            if observed[index]["type"] == candidate["type"]
            and abs(observed[index]["timestamp_ms"] - candidate["timestamp_ms"]) <= tolerance_ms
        ]
        if matches:
            best = min(
                matches,
                key=lambda index: abs(observed[index]["timestamp_ms"] - candidate["timestamp_ms"]),
            )
            unmatched.remove(best)
            matched += 1
    return matched, len(predicted) - matched, len(unmatched)


def evaluate_reviewed_windows(
    turns: list[dict], windows: list[dict], tolerance_ms: int = 5000
) -> dict:
    """Score only independently reviewed windows, without treating blanks as labels."""
    reviewed = [
        row
        for row in windows
        if row.get("review_status") == "reviewed" and isinstance(row.get("reviewed_events"), list)
    ]
    if not reviewed:
        return {
            "status": "insufficient_reviewed_labels",
            "reviewed_windows": 0,
            "precision": None,
            "recall": None,
            "tolerance_ms": tolerance_ms,
        }
    reviewed.sort(key=lambda row: row["start_ms"])
    if any(a["end_ms"] >= b["start_ms"] for a, b in zip(reviewed, reviewed[1:])):
        raise ValueError("reviewed windows must not overlap")
    true_positive = false_positive = false_negative = 0
    for window in reviewed:
        if any(
            event.get("type") not in ("TACK", "GYBE")
            or not window["start_ms"] <= event.get("timestamp_ms", -1) <= window["end_ms"]
            for event in window["reviewed_events"]
        ):
            raise ValueError(
                "reviewed events require a TACK/GYBE type and timestamp inside the window"
            )
        predicted = [
            turn for turn in turns if window["start_ms"] <= turn["timestamp_ms"] <= window["end_ms"]
        ]
        tp, fp, fn = _match_events(predicted, window["reviewed_events"], tolerance_ms)
        true_positive += tp
        false_positive += fp
        false_negative += fn
    return {
        "status": "reviewed_window_estimate",
        "reviewed_windows": len(reviewed),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "tolerance_ms": tolerance_ms,
        "precision": true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else None,
        "recall": true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else None,
        "scope": "sampled reviewed windows only; not an archive-wide weighted accuracy estimate",
    }
