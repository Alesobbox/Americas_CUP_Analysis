"""Source on-water timings and independently reviewed completion stay separate."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Sequence


def current_along_leg_mps(environment: dict | None, timestamp_ms: int | float | None,
                          course_axis: float | None, leg_index: int) -> float:
    """Project hourly 2m ocean current onto the leg axis.
    
    Current flows TOWARDS direction d. course_axis is the bearing from Gate 0 to Gate 1.
    Odd leg (index 0, 2, ...): along course_axis (+sign).
    Even leg (index 1, 3, ...): opposite course_axis (-sign).
    """
    if not environment or timestamp_ms is None or course_axis is None or not math.isfinite(course_axis):
        return 0.0
    hourly = environment.get("hourly", {})
    times = hourly.get("time_ms", [])
    velocities = hourly.get("current_velocity_mps", [])
    directions = hourly.get("current_direction_deg", [])
    if not times or not velocities or not directions or len(times) != len(velocities):
        return 0.0
    hour_ms = (int(timestamp_ms) // 3_600_000) * 3_600_000
    idx = next((i for i, t in enumerate(times) if t == hour_ms), None)
    if idx is None:
        earlier = [i for i, t in enumerate(times) if t <= timestamp_ms]
        if not earlier:
            return 0.0
        idx = earlier[-1]
    v, d = velocities[idx], directions[idx]
    if v is None or d is None or not math.isfinite(v) or not math.isfinite(d):
        return 0.0
    sign = 1.0 if leg_index % 2 == 0 else -1.0
    return sign * float(v) * math.cos(math.radians(float(d) - float(course_axis)))


def race_labels(metadata: dict) -> dict:
    final = metadata["sessions"][-1]
    sequences = final["race_course"]["sequences"]
    final_leg = len(sequences)-1
    timings, status, starts, availability = {}, {}, {}, {}
    cleared_ocs, active_dsq, events_by_boat = {}, {}, {}
    for event in metadata["competitor_events"]:
        aid = event["asset_id"]
        if aid not in metadata["boat_ids"]:
            continue
        events_by_boat.setdefault(aid, []).append(event)
        status[aid] = event.get("classification", "UNSPECIFIED")
        starts[aid] = event.get("start_state", {}).get("started")
        penalties = event.get("penalties", [])
        if any(p.get("reason") == "PENALTY_REASON_OCS" and p.get("state") == "PENALTY_STATE_CLEARED"
               and p.get("cleared_at") for p in penalties):
            cleared_ocs[aid] = True
        active_dsq[aid] = any(p.get("type") == "PENALTY_TYPE_DISQUALIFIED"
                              and p.get("state") == "PENALTY_STATE_ACTIVE" for p in penalties)
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
    imputed = {}
    for aid, boat in timings.items():
        missing = set(range(final_leg+1)) - set(boat)
        if len(missing) == 1:
            k = next(iter(missing))
            if 1 <= k < final_leg and (k-1 in boat) and (k+1 in boat) and boat[k-1] < boat[k+1]:
                gate_marks = {sequences[k]["gate"].get("port_asset_id"),
                              sequences[k]["gate"].get("starboard_asset_id")}
                evs = events_by_boat.get(aid, [])
                zone_ev = next((ev for ev in evs
                                if (ev.get("mark_zone_state") or {}).get("inside") is True
                                and (ev.get("mark_zone_state") or {}).get("mark_id") in gate_marks
                                and boat[k-1] < int(ev["timestamp"]) < boat[k+1]), None)
                leg_ev = next((ev for ev in evs
                               if (ev.get("course_position") or {}).get("leg_number") == k+1
                               and boat[k-1] < int(ev["timestamp"]) <= boat[k+1]), None)
                if zone_ev is not None and leg_ev is not None:
                    boat[k] = int(zone_ev["timestamp"])
                    availability[(aid, k)] = zone_ev["available_at_ms"]
                    imputed.setdefault(aid, []).append(k)
    def valid_finish(aid):
        gates = timings.get(aid, {})
        started_valid = starts.get(aid) is True or (0 in gates and cleared_ocs.get(aid, False))
        return (set(gates) == set(range(final_leg+1)) and started_valid and not active_dsq.get(aid, False)
                and all(gates[i] < gates[i+1] for i in range(final_leg)))
    finishers = sorted((aid for aid in metadata["boat_ids"] if valid_finish(aid)),
                       key=lambda a: timings[a][final_leg])
    ties = any(timings[a][final_leg] == timings[b][final_leg] for a,b in zip(finishers, finishers[1:]))
    on_water_order = [metadata["identities"][a]["entry_id"] for a in finishers]
    result_available = max(availability.values(), default=metadata["window_end_ms"]+6000)
    return {"race_id": metadata["race_id"], "date": metadata["date"],
            "practice": metadata["practice"], "source_classification": status,
            "source_started": starts, "timings": timings,
            "imputed_gates": imputed, "cleared_ocs": cleared_ocs, "active_dsq": active_dsq,
            "order": on_water_order,
            "on_water_result": {
                "order": list(on_water_order),
                "finisher_ids": list(finishers),
                "order_tied": ties,
                "order_valid": not ties and len(finishers) >= 2,
                "available_at_ms": result_available
            },
            "official_result": None,
            "finisher_ids": finishers, "order_tied": ties, "order_valid": not ties and len(finishers) >= 2,
            "provenance": "source_gate_timings_with_nested_start_flag_and_cleared_ocs; not independently verified",
            "official_order_verified": False,
            "result_available_at_ms": result_available}


def attach_official_results(labels_input: dict[str, dict] | Sequence[dict],
                            official_path: Path | None = None,
                            current_time_ms: int | None = None) -> tuple[list[dict], dict[str, Any]]:
    """Attach verified official results without mutating on-water order in-place."""
    path = official_path or Path("docs/official_results_ac38_prelims.json")
    if isinstance(labels_input, dict):
        labels_by_race = labels_input
        labels_list = list(labels_input.values())
    else:
        labels_by_race = {r["race_id"]: r for r in labels_input}
        labels_list = list(labels_input)

    if not path.exists():
        return labels_list, {"total_races": 0, "verified_races": 0}

    doc = json.loads(path.read_text(encoding="utf-8"))
    verified_count = 0
    for r in doc.get("races", []):
        rid = r.get("race_id")
        if rid in labels_by_race:
            avail = r.get("available_at_ms", 0)
            if current_time_ms is not None and current_time_ms < avail:
                continue
            source_url = str(r.get("source_url") or r.get("source") or "")
            is_external_source = source_url.startswith("https://") and not source_url.startswith("Data/")
            is_verified_final = (
                r.get("status") == "final"
                and r.get("verified") is True
                and is_external_source
                and isinstance(r.get("official_order"), list)
                and len(r["official_order"]) >= 2
            )
            target_order = list(r["official_order"]) if is_verified_final else list(labels_by_race[rid].get("order", []))
            if is_verified_final:
                verified_count += 1
            labels_by_race[rid]["official_result"] = {
                "order": target_order,
                "dns_entries": list(r.get("dns_entries", [])),
                "dnf_entries": list(r.get("dnf_entries", [])),
                "ocs_or_dsq_entries": list(r.get("ocs_or_dsq_entries", [])),
                "protest_penalties": list(r.get("protest_penalties", [])),
                "jury_decisions_applied_at_ms": r.get("jury_decisions_applied_at_ms"),
                "available_at_ms": avail,
                "verified": is_verified_final,
                "status": r.get("status", "unverified"),
                "source_url": source_url,
            }
            labels_by_race[rid]["official_order_verified"] = is_verified_final
            labels_by_race[rid]["official_order"] = target_order if is_verified_final else None
            labels_by_race[rid]["dns_entries"] = list(r.get("dns_entries", []))
            labels_by_race[rid]["dnf_entries"] = list(r.get("dnf_entries", []))
            labels_by_race[rid]["ocs_or_dsq_entries"] = list(r.get("ocs_or_dsq_entries", []))
            labels_by_race[rid]["official_status"] = r.get("status", "unverified")

    return labels_list, {"total_races": len(doc.get("races", [])), "verified_races": verified_count}


def source_completion_records(metadata: dict, label: dict) -> list[dict]:
    """Scheduled-entry completion facts reconstructed from the same source feed.

    These records describe the on-water target (did the boat record a valid
    finish?). They are deliberately ``audited=False`` with
    ``ascertainment='source'``: they are not an independent review and cannot
    distinguish an exogenous breakdown from a retirement, a disqualification
    or a recording gap. ``failure_type`` keeps that distinction visible.
    """
    if metadata["practice"]:
        return []
    final_leg = len(metadata["sessions"][-1]["race_course"]["sequences"])-1
    finishers = set(label["finisher_ids"])
    records = []
    for aid in metadata["boat_ids"]:
        gates = label["timings"].get(aid, {})
        cls = str(label["source_classification"].get(aid) or "UNSPECIFIED").upper()
        started = (label["source_started"].get(aid) is True
                   or (0 in gates and label["cleared_ocs"].get(aid, False)))
        if cls.endswith("DID_NOT_START"):
            started = False
        completed = aid in finishers
        record = {"asset_id": aid, "entry_id": metadata["identities"][aid]["entry_id"],
                  "race_id": metadata["race_id"], "date": metadata["date"],
                  "started": bool(started or completed), "completed": completed,
                  "audited": False, "ascertainment": "source", "competitive": True, "practice": False,
                  "available_at_ms": int(label["result_available_at_ms"])}
        if record["started"] and not completed:
            if label["active_dsq"].get(aid, False):
                record["failure_type"] = "disqualified"
            elif cls.endswith("RETIRED"):
                record["failure_type"] = "retired"
            else:
                # No terminal classification: retirement or a recording gap.
                record["failure_type"] = "unresolved"
            record["last_gate"] = max(gates, default=-1)
            record["final_gate"] = final_leg
        records.append(record)
    return records


def leg_rows(metadata, rows, label):
    """Valid intervals survive a later retirement. Gun-to-gate includes the start loss."""
    final = metadata["sessions"][-1]
    max_leg = len(final["race_course"]["sequences"])-1
    # Winds are observed at entry, never a future race average.
    winds = [r for r in rows if r["asset_id"] == final.get("official_wind_asset_id")
             and r["field"] == "true_wind_speed" and r["value"] is not None]
    result = []
    for aid, gates in label["timings"].items():
        imputed = set(label.get("imputed_gates", {}).get(aid, ()))
        for leg in range(1, max_leg+1):
            if leg in imputed or (leg-1) in imputed:
                continue  # zone-entry time is not a rounding time
            entry = metadata["gun_ms"] if leg == 1 else gates.get(leg-1)
            exit = gates.get(leg)
            if not entry or not exit or exit <= entry:
                continue
            entry_session=next((s for s in reversed(metadata["sessions"]) if int(s["timestamp"]) <= entry),None)
            if not entry_session or leg >= len(entry_session["race_course"]["sequences"]):
                continue
            distance=float(entry_session["race_course"]["course_length"])
            axis=entry_session["race_course"].get("course_axis")
            c_parallel = current_along_leg_mps(metadata.get("environment"), entry, axis, leg - 1)
            wind = next((w["value"]*1.943844 for w in reversed(winds)
                         if w.get("bucket_closed_at_ms",w["timestamp_ms"]) <= entry), None)
            result.append({"boat_id": metadata["identities"][aid]["entry_id"],
                           "leg_kind": "odd" if leg%2 else "even", "leg_index":leg-1,"distance_m": distance,
                           "duration_s": (exit-entry)/1000, "wind_knots": wind,
                           "c_parallel_mps": c_parallel,
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


def select_training_order_rows(labels: Sequence[dict], *,
                               target: str = "on_water",
                               prefer_official: bool | None = None,
                               cutoff_ms: int | None = None) -> list[dict]:
    """Select training order rows using explicit on_water or official target with cutoff check."""
    result = []
    if prefer_official is True:
        target = "official"
    for r in labels:
        row = dict(r)
        if target == "official":
            off = r.get("official_result")
            is_verified = bool(r.get("official_order_verified") or (off and off.get("verified") is not False))
            if off and off.get("order") and is_verified and (cutoff_ms is None or off.get("available_at_ms", 0) <= cutoff_ms):
                row["order"] = list(off["order"])
                row["training_target"] = "official"
                row["training_order_source"] = "official_verified"
                row["target_available_at_ms"] = off.get("available_at_ms")
            else:
                on_w = r.get("on_water_result", {})
                row["order"] = list(on_w.get("order", r.get("order", [])))
                row["training_target"] = "on_water_fallback"
                row["training_order_source"] = "on_water_fallback"
                row["target_available_at_ms"] = on_w.get("available_at_ms", r.get("result_available_at_ms"))
        else:
            on_w = r.get("on_water_result", {})
            row["order"] = list(on_w.get("order", r.get("order", [])))
            row["training_target"] = "on_water"
            row["training_order_source"] = "on_water"
            row["target_available_at_ms"] = on_w.get("available_at_ms", r.get("result_available_at_ms"))
        result.append(row)
    return result
