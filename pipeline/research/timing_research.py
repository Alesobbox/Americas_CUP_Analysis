"""Retrospective AC38 checkpoint accounting and turn-cost research contract."""

from __future__ import annotations

from pipeline.research.maneuver_cost import ReferencePredictor, characterize_turns
from pipeline.research.maneuver_events import detect_turn_candidates
from pipeline.research.maneuver_review import evaluate_reviewed_windows, review_windows
from pipeline.research.timing_ledger import attach_peer_ledgers, checkpoint_ledger, phase_accounting
from pipeline.research.timing_track import track_for


def build_timing_research(
    detail: dict, replay: dict, reference_predictor: ReferencePredictor | None = None
) -> dict:
    """Return exact timing identities and reference-dependent progress deficits."""
    race = detail.get("race") or {}
    rows = []
    context = {
        "race_id": race.get("id"),
        "date": race.get("date"),
        "predictor": reference_predictor,
    }
    for boat in detail.get("boats", []):
        track = track_for(replay, boat)
        turns = detect_turn_candidates(track)
        review = review_windows(track, turns, str(race.get("id")))
        rows.append(
            {
                "boat_id": boat["id"],
                "team_code": boat.get("team_code"),
                "ledger": checkpoint_ledger(boat, race.get("gun_time_ms")),
                "phases": phase_accounting(track, turns),
                "turns": characterize_turns(track, turns, context),
                "review_queue": review,
                "detector_evaluation": evaluate_reviewed_windows(turns, review),
            }
        )
    attach_peer_ledgers(rows)
    return {
        "schema_version": "timing-research-1",
        "method_version": "checkpoint-phases-1",
        "race_id": race.get("id"),
        "scope": "retrospective_observed_ground_relative",
        "definitions": {
            "ledger": "gun-to-start delay plus consecutive observed leg durations equals gun-to-endpoint elapsed seconds",
            "phases": "unavailable, gate approach, turn and other sailing are disjoint; their seconds equal observed active duration",
            "progress_deficit_m": "integral of stated-reference course-axis VMG minus observed course-axis VMG, in metres",
            "polar_reference": "held-out-day predicted SOG at supported pre-turn conditions and pre-turn COG; no polar query during a turn",
        },
        "caveats": [
            "Timing accounting does not identify causal seconds attributable to crew, tactics or weather.",
            "Progress deficits depend on a hypothetical reference trajectory and are not seconds lost.",
            "Geometry candidates include low-loss turns but require manual review; severe speed collapse is not verified touchdown.",
            "Recovery and horizon deficits remain censored at source gaps, the next turn, gate approach or telemetry end.",
        ],
        "boats": rows,
    }
