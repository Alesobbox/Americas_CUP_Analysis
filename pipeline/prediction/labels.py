"""Source on-water timings and independently reviewed completion stay separate."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path


def race_labels(metadata: dict) -> dict:
    final = metadata["sessions"][-1]
    final_leg = len(final["race_course"]["sequences"])-1
    timings, status, starts, availability = {}, {}, {}, {}
    for event in metadata["competitor_events"]:
        aid = event["asset_id"]
        if aid not in metadata["boat_ids"]:
            continue
        status[aid] = event.get("classification", "UNSPECIFIED")
        starts[aid] = event.get("start_state", {}).get("started")
        boat = timings.setdefault(aid, {})
        for timing in event.get("leg_timings", []):
            if timing.get("gate_time"):
                leg, t = int(timing["leg_number"]), int(timing["gate_time"])
                if t > int(event["timestamp"]):
                    continue
                if leg not in boat:
                    boat[leg] = t
                    availability[(aid, leg)] = event["available_at_ms"]
                elif boat[leg] != t:
                    # Corrections supersede training labels only when available.
                    boat[leg] = t
                    availability[(aid, leg)] = event["available_at_ms"]
    def valid_finish(aid):
        gates = timings.get(aid, {})
        return (set(gates) == set(range(final_leg+1)) and starts.get(aid) is True
                and all(gates[i] < gates[i+1] for i in range(final_leg)))
    finishers = sorted((aid for aid in metadata["boat_ids"] if valid_finish(aid)),
                       key=lambda a: timings[a][final_leg])
    ties = any(timings[a][final_leg] == timings[b][final_leg] for a,b in zip(finishers, finishers[1:]))
    return {"race_id": metadata["race_id"], "date": metadata["date"],
            "practice": metadata["practice"], "source_classification": status,
            "source_started": starts, "timings": timings,
            "order": [metadata["identities"][a]["entry_id"] for a in finishers],
            "finisher_ids": finishers, "order_tied":ties,"order_valid": not ties and len(finishers) >= 2,
            "provenance": "source_gate_timings_with_nested_start_flag; not independently verified",
            "official_order_verified": False,
            "result_available_at_ms": max(availability.values(), default=metadata["window_end_ms"]+6000)}


def leg_rows(metadata, rows, label):
    """Valid intervals survive a later retirement. Gun-to-gate includes the start loss."""
    final = metadata["sessions"][-1]
    max_leg = len(final["race_course"]["sequences"])-1
    # Winds are observed at entry, never a future race average.
    winds = [r for r in rows if r["asset_id"] == final.get("official_wind_asset_id")
             and r["field"] == "true_wind_speed" and r["value"] is not None]
    result = []
    for aid, gates in label["timings"].items():
        for leg in range(1, max_leg+1):
            entry = metadata["gun_ms"] if leg == 1 else gates.get(leg-1)
            exit = gates.get(leg)
            if not entry or not exit or exit <= entry:
                continue
            entry_session=next((s for s in reversed(metadata["sessions"]) if int(s["timestamp"]) <= entry),None)
            if not entry_session or leg >= len(entry_session["race_course"]["sequences"]):
                continue
            distance=float(entry_session["race_course"]["course_length"])
            wind = next((w["value"]*1.943844 for w in reversed(winds)
                         if w.get("bucket_closed_at_ms",w["timestamp_ms"]) <= entry), None)
            result.append({"boat_id": metadata["identities"][aid]["entry_id"],
                           "leg_kind": "odd" if leg%2 else "even", "leg_index":leg-1,"distance_m": distance,
                           "duration_s": (exit-entry)/1000, "wind_knots": wind,
                           "race_id": metadata["race_id"], "date": metadata["date"],
                           "practice": metadata["practice"], "valid": True,
                           "target_censored": False, "target_source": "source_gate_interval",
                           "available_at_ms": label["result_available_at_ms"]})
    return result


def load_reviews(root: Path, datasets: list[dict], path: Path | None = None) -> list[dict]:
    """Reject partial denominators and evidence-free review overrides.

    Audited races must account for every scheduled entry, including nonstarters.
    They need an evidence reference and an actual review availability timestamp.
    """
    path = path or root/"docs"/"forecast_completion_review.json"
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema_version") != "completion-review-1":
        raise ValueError("Unsupported completion review schema")
    by_race = {m["race_id"]: m for m in datasets}
    result, seen = [], set()
    for race in doc.get("races", []):
        rid = race["race_id"]
        if rid in seen or rid not in by_race:
            raise ValueError("Duplicate or unknown reviewed race")
        seen.add(rid)
        meta = by_race[rid]
        if meta["practice"]:
            raise ValueError("Practice cannot establish competitive completion")
        entries = race.get("entries", [])
        if set(e["asset_id"] for e in entries) != set(meta["boat_ids"]) or len(entries) != len(meta["boat_ids"]):
            raise ValueError("Reviewed denominator must include every scheduled entry exactly once")
        if not race.get("evidence_ref") or not isinstance(race.get("available_at_ms"), int):
            raise ValueError("Audited results require evidence and availability time")
        for entry in entries:
            if not isinstance(entry.get("started"), bool) or not isinstance(entry.get("completed"), bool):
                raise ValueError("Unresolved completion is not an audited denominator")
            if entry["completed"] and not entry["started"]:
                raise ValueError("A nonstarter cannot be a valid finisher")
            cause = entry.get("failure_type")
            if entry["started"] and not entry["completed"] and cause not in ("exogenous", "time_rule"):
                raise ValueError("An untyped DNF cannot establish random failure risk")
            result.append(dict(entry, audited=True, competitive=True, practice=False,
                               race_id=rid, date=meta["date"], evidence_ref=race["evidence_ref"],
                               available_at_ms=race["available_at_ms"]))
    return result


def before_day(rows, date: str):
    cutoff = int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp()*1000)
    return [r for r in rows if r["date"] < date and r.get("available_at_ms", r.get("result_available_at_ms", 0)) < cutoff]
