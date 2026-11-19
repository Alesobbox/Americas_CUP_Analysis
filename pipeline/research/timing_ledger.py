"""Exact checkpoint accounting and disjoint observed phase exposure."""

from __future__ import annotations

from statistics import mean

from pipeline.research.timing_track import Track, active_window, covered, sample_times

PHASES = ("unavailable", "gate_approach", "turn", "other_sailing")


def _gate_windows(boat: dict) -> list[tuple[int, int]]:
    start = (boat.get("start") or {}).get("crossing_time_ms")
    timestamps = [start] if start is not None else []
    timestamps.extend(
        g["crossing_time_ms"]
        for g in boat.get("gates", [])
        if g.get("crossing_time_ms") is not None
    )
    return [(int(t) - 8000, int(t) + 8000) for t in timestamps]


def _phase_cuts(track: Track, turns: list[dict], window: tuple[int, int]) -> list[int]:
    start, end = window
    cuts = {start, end, *sample_times(start, end)}
    windows = _gate_windows(track.boat) + [(t["start_ms"], t["end_ms"]) for t in turns]
    for a, b in windows:
        cuts.update((max(start, min(end, a)), max(start, min(end, b))))
    for info in (track.boat.get("source_coverage") or {}).values():
        if not isinstance(info, dict):
            continue
        for a, b in info.get("gaps", []):
            cuts.update((max(start, min(end, a)), max(start, min(end, b))))
        for key in ("first_ms", "last_ms"):
            value = info.get(key)
            if value is not None and start < value < end:
                cuts.add(int(value))
    return sorted(cuts)


def phase_accounting(track: Track, turns: list[dict]) -> dict:
    window = active_window(track.boat)
    if window is None:
        return {"quality": "unavailable", "reason": "no observed active interval", "seconds": None}
    seconds = dict.fromkeys(PHASES, 0.0)
    gates = _gate_windows(track.boat)
    turn_windows = [(t["start_ms"], t["end_ms"]) for t in turns]
    cuts = _phase_cuts(track, turns, window)
    coverage = track.boat.get("source_coverage") or {}
    for a, b in zip(cuts, cuts[1:]):
        midpoint = (a + b) / 2
        if not covered(coverage, a, b) or track.state(midpoint) is None:
            phase = "unavailable"
        elif any(x <= midpoint < y for x, y in gates):
            phase = "gate_approach"
        elif any(x <= midpoint < y for x, y in turn_windows):
            phase = "turn"
        else:
            phase = "other_sailing"
        seconds[phase] += (b - a) / 1000
    total = (window[1] - window[0]) / 1000
    return {
        "quality": "derived",
        "seconds": {k: round(v, 6) for k, v in seconds.items()},
        "active_elapsed_s": total,
        "reconciliation_error_s": round(sum(seconds.values()) - total, 9),
        "priority": list(PHASES),
        "gate_window_s": 8,
        "interpretation": "Mutually exclusive observed phase durations; other sailing is not a certified steady-state regime.",
    }


def checkpoint_ledger(boat: dict, gun_ms: int | None) -> dict:
    start = (boat.get("start") or {}).get("crossing_time_ms")
    legs = sorted(boat.get("legs", []), key=lambda leg: leg["leg"])
    if gun_ms is None or start is None or not legs:
        return {
            "quality": "unavailable",
            "reason": "missing gun, start or leg intervals",
            "components": [],
        }
    components = [{"kind": "start_delay", "leg": None, "elapsed_s": (start - gun_ms) / 1000}]
    previous = start
    for leg in legs:
        a, b = leg.get("start_ms"), leg.get("end_ms")
        if a is None or b is None or b <= a or a != previous:
            break
        components.append(
            {
                "kind": "leg",
                "leg": leg["leg"],
                "elapsed_s": (b - a) / 1000,
                "complete": bool(leg.get("complete")),
            }
        )
        previous = b
        if not leg.get("complete"):
            break
    complete = len(components) == len(legs) + 1 and all(c.get("complete", True) for c in components)
    classified_finish = str(boat.get("classification", "")).startswith("RANK_")
    eligible = not (boat.get("source_conflicts") or (boat.get("start") or {}).get("ocs"))
    finished = complete and classified_finish and eligible
    total = (previous - gun_ms) / 1000
    return {
        "quality": "reconstructed" if finished else "partial",
        "complete_finish": finished,
        "reason": None
        if finished
        else "observed checkpoint prefix only; no qualified complete finish",
        "components": components,
        "accounted_elapsed_s": total,
        "endpoint_ms": previous,
        "reconciliation_error_s": round(sum(c["elapsed_s"] for c in components) - total, 9),
        "reported_elapsed_difference_s": (
            round(total - boat["official_elapsed_s"], 6)
            if finished and boat.get("official_elapsed_s") is not None
            else None
        ),
        "result_scope": "source-timed or reconstructed checkpoints, not independently verified official classification",
    }


def attach_peer_ledgers(rows: list[dict]) -> None:
    for row in rows:
        ledger = row["ledger"]
        signature = [c["leg"] for c in ledger["components"]]
        peers = [
            p
            for p in rows
            if p["boat_id"] != row["boat_id"]
            and p["ledger"].get("complete_finish")
            and [c["leg"] for c in p["ledger"]["components"]] == signature
        ]
        if not ledger.get("complete_finish") or not peers:
            ledger["peer_comparison"] = None
            continue
        components = []
        for index, component in enumerate(ledger["components"]):
            baseline = mean(p["ledger"]["components"][index]["elapsed_s"] for p in peers)
            components.append(
                {
                    "kind": component["kind"],
                    "leg": component["leg"],
                    "peer_mean_s": baseline,
                    "difference_s": component["elapsed_s"] - baseline,
                }
            )
        difference = ledger["accounted_elapsed_s"] - mean(
            p["ledger"]["accounted_elapsed_s"] for p in peers
        )
        ledger["peer_comparison"] = {
            "peer_ids": [p["boat_id"] for p in peers],
            "components": components,
            "total_difference_s": difference,
            "reconciliation_error_s": round(
                sum(c["difference_s"] for c in components) - difference, 9
            ),
            "weighting": "same eligible peer set, equal boat weights for every component",
        }
