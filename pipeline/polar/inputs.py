"""Source coverage and replay input contracts for performance samples."""

import json


def _circular_delta_deg(a, b):
    return ((b - a + 180) % 360) - 180


def _boat_eligible(boat):
    start = boat.get("start") or {}
    return (
        boat.get("classification") not in ("OCS", "RET", "DNS", "DID_NOT_START", "RETIRED")
        and not start.get("ocs")
        and start.get("crossing_time_ms") is not None
        and not boat.get("source_conflicts")
    )


def _coverage_valid(coverage, timestamp, fields=("gnss", "heading", "sog", "cog", "twd", "tws")):
    if not coverage:
        return False
    for field in fields:
        info = coverage.get(field)
        if not info:
            return False
        first, last = info.get("first_ms"), info.get("last_ms")
        if first is None or last is None or not first <= timestamp <= last:
            return False
        if any(a < timestamp < b for a, b in info.get("gaps", [])):
            return False
    return True


def resolve_inputs(ingest, replay, path):
    if ingest is not None and getattr(ingest, "boats", None):
        arrays = {}
        for boat in ingest.boats.values():
            if getattr(boat, "tws_kt", None) is None:
                return None
            arrays[boat.asset_id] = {
                "x": boat.x,
                "y": boat.y,
                "heading": boat.heading,
                "cog": boat.cog,
                "sog": boat.sog_kt,
                "twd": boat.twd_deg,
                "tws": boat.tws_kt,
            }
        return list(ingest.grid_timestamps_ms), arrays
    if replay is None and path is not None and path.is_file():
        replay = json.loads(path.read_text(encoding="utf8"))
    telemetry = (replay or {}).get("telemetry") or {}
    times, boats = telemetry.get("timestamps"), telemetry.get("boats")
    return (times, boats) if times and boats else None
