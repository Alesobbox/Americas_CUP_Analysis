"""Refresh team analytics without re-ingesting high-rate boat telemetry.

Only raw official-wind records and session metadata are parsed. The scan hashes
the complete source, but retains only the sparse wind fields in memory.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import MPS_TO_KNOTS, OFFICIAL_WIND_ASSET_ID
from pipeline.historical_analysis import attach_performance_analysis, build_historical_index
from pipeline.run_pipeline import infer_race_metadata
from pipeline.tactical_insights import TACTICAL_DEFINITIONS, attach_tactical_insights
from scripts.build_artifact_inventory import build_inventory


def read_source_wind(path, root=ROOT):
    """Stream exactly the same independent official fields as normal ingestion."""
    path, root = Path(path), Path(root)
    asset = OFFICIAL_WIND_ASSET_ID.encode("ascii")
    hasher = hashlib.sha256()
    samples = []
    window_end = None
    with path.open("rb", buffering=1024 * 1024) as stream:
        for line in stream:
            hasher.update(line)
            if b'"session"' in line and b'"telemetry"' not in line:
                session = json.loads(line).get("session")
                if session and session.get("window_end") is not None:
                    window_end = int(session["window_end"])
            if asset not in line or b'"telemetry"' not in line:
                continue
            telemetry = json.loads(line).get("telemetry") or {}
            if telemetry.get("asset_id") != OFFICIAL_WIND_ASSET_ID:
                continue
            timestamp = int(telemetry["timestamp"])
            if "true_wind_speed" in telemetry:
                samples.append({"timestamp_ms": timestamp,
                    "tws_kt": float(telemetry["true_wind_speed"]["value"]) * MPS_TO_KNOTS})
            elif "true_wind_direction" in telemetry:
                samples.append({"timestamp_ms": timestamp,
                    "twd_deg": float(telemetry["true_wind_direction"]["value"])})
    provenance = {"source_file": path.resolve().relative_to(root.resolve()).as_posix(),
                  "source_sha256": hasher.hexdigest(), "source_size_bytes": path.stat().st_size,
                  "official_wind_asset_id": OFFICIAL_WIND_ASSET_ID}
    return samples, window_end, provenance


def _races(catalog):
    entries = catalog.get("races", []) + [race for regatta in catalog.get("regattas", [])
                                         for race in regatta.get("races", [])]
    return list({race["id"]: race for race in entries}.values())


def _write_json(path, value):
    content = json.dumps(value, separators=(",", ":"), allow_nan=False)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def verify(root=ROOT):
    """Fast artifact/provenance verification; no multi-gigabyte raw rescan."""
    root = Path(root)
    data = root / "public" / "data"
    races = _races(json.loads((data / "manifests.json").read_text(encoding="utf-8")))
    inventory = json.loads((data / "artifacts.json").read_text(encoding="utf-8"))
    inventory_by_path = {item["id"]: item for item in inventory["artifacts"]}
    snapshots, boat_count, conditional_count = 0, 0, 0
    source_paths = set()

    def check(condition, message):
        if not condition:
            raise ValueError(message)

    def finite_tree(value, label):
        if isinstance(value, float):
            check(math.isfinite(value), f"Nonfinite analytics value: {label}")
        elif isinstance(value, dict):
            for key, child in value.items():
                finite_tree(child, f"{label}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                finite_tree(child, f"{label}[{index}]")

    def peer_evidence(value, own_id, boat_ids, label):
        peer_ids = value["peer_ids"]
        check(len(peer_ids) == len(set(peer_ids)) == value["peer_count"], f"Invalid peer count: {label}")
        check(own_id not in peer_ids and set(peer_ids) <= boat_ids, f"Invalid peer identities: {label}")

    expected_dimensions = {"upwind_vmg", "downwind_vmg", "upwind_speed", "downwind_speed", "tack_retention", "gybe_retention"}
    for race in races:
        race_id = race["id"]
        detail = json.loads((data / "analysis" / (race["id"] + ".json")).read_text(encoding="utf-8"))
        check(detail["race"]["id"] == race_id, f"Race mismatch: {race_id}")
        expected = attach_performance_analysis(copy.deepcopy(detail))
        boat_ids = {boat["id"] for boat in detail["boats"]}
        check(len(boat_ids) == len(detail["boats"]), f"Duplicate boat identity: {race_id}")
        if "competitors_count" in race:
            check(len(boat_ids) == race["competitors_count"], f"Boat count mismatch: {race_id}")
        for boat, rebuilt in zip(detail["boats"], expected["boats"]):
            own_id = boat["id"]
            for key in ("performance", "debrief"):
                check(boat[key] == rebuilt[key], f"Stale {key}: {race_id}/{own_id}; run refresh_team_analytics.py")
                finite_tree(boat[key], f"{race_id}/{own_id}/{key}")
            performance, debrief = boat["performance"], boat["debrief"]
            check(performance["schema_version"] == debrief["schema_version"] == "1.0", f"Boat analytics schema: {race_id}/{own_id}")
            check(performance["method_version"] == "performance-1" and debrief["method_version"] == "debrief-1", f"Boat analytics method: {race_id}/{own_id}")
            check({dimension["id"] for dimension in performance["dimensions"]} == expected_dimensions
                  and len(performance["dimensions"]) == 6, f"Performance dimensions: {race_id}/{own_id}")
            check(performance["baseline_index"] == 100, f"Performance baseline: {race_id}/{own_id}")
            if performance["overall_index"] is None:
                check(bool(performance.get("reason")), f"Missing overall reason: {race_id}/{own_id}")
            for dimension in performance["dimensions"]:
                label = f"{race_id}/{own_id}/{dimension['id']}"
                for field in ("formula", "window", "denominator", "source", "unit"):
                    check(bool(dimension.get(field)), f"Missing {field}: {label}")
                if dimension["index"] is None:
                    check(dimension["quality"] == "unavailable" and bool(dimension.get("reason")), f"Missing dimension reason: {label}")
                else:
                    check(dimension["index"] >= 0 and dimension["peer_count"] > 0, f"Invalid dimension index: {label}")
                union = set()
                for evidence in dimension["leg_evidence"]:
                    peer_evidence(evidence, own_id, boat_ids, label)
                    union.update(evidence["peer_ids"])
                    check(evidence["sample_count"] > 0 and evidence["coverage_s"] >= 0, f"Invalid evidence coverage: {label}")
                check(dimension["peer_count"] == len(union), f"Invalid aggregate peer count: {label}")
                check(dimension["matched_legs"] == [entry["leg"] for entry in dimension["leg_evidence"]], f"Matched-leg evidence mismatch: {label}")
            if not debrief["items"]:
                check(bool(debrief.get("reason")), f"Missing debrief reason: {race_id}/{own_id}")
            for item in debrief["items"]:
                check(bool(item["source"]) and item["value"] > 0, f"Invalid debrief evidence: {race_id}/{own_id}")
                if "peer_ids" in item:
                    peer_evidence(item, own_id, boat_ids, f"{race_id}/{own_id}/debrief")
        boat_count += len(boat_ids)
        tactical = detail["tactical_insights"]
        finite_tree(tactical, f"{race_id}/tactical")
        check(tactical["schema_version"] == "1.0" and tactical["method_version"] == "tactical-1", f"Tactical schema: {race_id}")
        check(tactical["race_id"] == race_id, f"Tactical race mismatch: {race_id}")
        check(tactical.get("definitions") == TACTICAL_DEFINITIONS, f"Stale tactical metric definitions: {race_id}")
        check(tactical["snapshot_interval_ms"] == 10_000 and tactical["max_snapshot_age_ms"] == 12_000, f"Tactical cadence: {race_id}")
        check(tactical["window_s"] == 120 and tactical["projection_horizon_s"] == 300, f"Tactical windows: {race_id}")
        check("not arrival-time causal" in tactical["availability_basis"], f"Missing retrospective caveat: {race_id}")
        provenance = tactical["source_provenance"]
        source = (root / provenance["source_file"]).resolve()
        if not source.exists():
            cand = (root / "Data" / "AC38" / Path(provenance["source_file"]).name).resolve()
            if cand.exists():
                source = cand
        check(source.is_relative_to((root / "Data").resolve()), f"Source outside Data: {source}")
        check(source not in source_paths and infer_race_metadata(str(source))["race_id"] == race_id, f"Source mapping mismatch: {race_id}")
        source_paths.add(source)
        check(source.stat().st_size == provenance["source_size_bytes"], f"Source size changed: {source.name}")
        check(re.fullmatch(r"[a-f0-9]{64}", provenance["source_sha256"]), f"Invalid source hash: {race_id}")
        check(provenance["official_wind_asset_id"] == OFFICIAL_WIND_ASSET_ID, f"Official wind identity mismatch: {race_id}")
        check(provenance["direction_sample_count"] >= 0 and provenance["speed_sample_count"] >= 0, f"Invalid wind count: {race_id}")
        previous = None
        for snapshot in tactical["snapshots"]:
            t = snapshot["timestamp_ms"]
            check((t == detail["race"]["gun_time_ms"]) if previous is None else t - previous == 10_000, f"Snapshot ordering: {race_id}")
            check(snapshot["window_end_ms"] == t and snapshot["window_start_ms"] == t - 120_000, f"Snapshot future window: {race_id}")
            check(t <= detail["race"]["window_end_ms"], f"Snapshot past race end: {race_id}")
            check(0 <= snapshot["coverage_s"] <= 120 and snapshot["sample_count"] >= 0, f"Snapshot coverage: {race_id}")
            check(0 <= snapshot["speed_coverage_s"] <= 120 and snapshot["speed_sample_count"] >= 0, f"Speed coverage: {race_id}")
            check(bool(snapshot["projection_reason"]) and bool(snapshot["source"]), f"Missing snapshot provenance: {race_id}")
            if snapshot["quality"] == "derived":
                check(snapshot["coverage_s"] == 120 and snapshot["sample_count"] >= 60
                      and snapshot["direction_change_deg"] is not None and snapshot["direction_rate_deg_per_min"] is not None, f"Derived wind availability: {race_id}")
            else:
                check(snapshot["quality"] == "unavailable" and bool(snapshot.get("reason"))
                      and snapshot["direction_change_deg"] is None and snapshot["projection_change_deg"] is None, f"Unavailable wind reason: {race_id}")
            if snapshot["speed_quality"] == "derived":
                check(snapshot["speed_coverage_s"] == 120 and snapshot["speed_sample_count"] >= 60
                      and snapshot["speed_change_kt"] is not None and snapshot["speed_reason"] is None, f"Derived speed availability: {race_id}")
            else:
                check(snapshot["speed_quality"] == "unavailable" and bool(snapshot["speed_reason"])
                      and snapshot["speed_change_kt"] is None, f"Unavailable speed reason: {race_id}")
            if snapshot["projection_change_deg"] is not None:
                check(abs(snapshot["projection_change_deg"]) <= 30 and "unvalidated" in snapshot["projection_reason"]
                      and "Conditional" in snapshot["projection_reason"], f"Unbounded wind projection: {race_id}")
                conditional_count += 1
            for insight in snapshot["insights"]:
                check(all(insight.get(key) for key in ("id", "title", "detail", "quality", "source", "kind")), f"Missing insight contract: {race_id}")
            previous = t
            snapshots += 1
        if detail["race"]["window_end_ms"] < detail["race"]["gun_time_ms"]:
            check(not tactical["snapshots"] and bool(tactical.get("reason")), f"Pregun session tactical reason: {race_id}")
        else:
            check(bool(tactical["snapshots"]), f"Empty tactical snapshot grid: {race_id}")
        relative = f"analysis/{race_id}.json"
        check(relative in inventory_by_path and inventory_by_path[relative]["bytes"] == (data / relative).stat().st_size, f"Stale Reports size: {relative}")
    check(inventory["summary"]["race_count"] == len(races)
          and inventory["summary"]["replayed_boat_races"] == boat_count, "Reports archive totals differ from analytics")
    check(inventory_by_path["analysis/index.json"]["bytes"] == (data / "analysis" / "index.json").stat().st_size, "Stale Reports index size")
    return {"race_count": len(races), "boat_race_count": boat_count, "snapshot_count": snapshots,
            "conditional_projection_count": conditional_count, "verification": "passed",
            "source_check": "existence, size and recorded hash format; raw contents are hashed during refresh"}


def refresh(root=ROOT, race_ids=None, *, performance_only=False):
    root = Path(root)
    data = root / "public" / "data"
    catalog_path = data / "manifests.json"
    races = _races(json.loads(catalog_path.read_text(encoding="utf-8")))
    source_by_race = {}
    raw_files = list((root / "Data").glob("*.jsonl"))
    if not raw_files and (root / "Data" / "AC38").exists():
        raw_files = list((root / "Data" / "AC38").glob("*.jsonl"))
    for path in ([] if performance_only else sorted(raw_files)):
        race_id = infer_race_metadata(str(path))["race_id"]
        if race_id in source_by_race:
            raise ValueError(f"Multiple source files map to {race_id}")
        source_by_race[race_id] = path
    selected = [race for race in races if not race_ids or race["id"] in race_ids]
    if race_ids and set(race_ids) - {race["id"] for race in selected}:
        raise ValueError("Requested race is absent from the catalog")
    summary = {"race_count": 0, "boat_race_count": 0, "snapshot_count": 0, "conditional_projection_count": 0}
    for race in selected:
        path = data / "analysis" / (race["id"] + ".json")
        detail = json.loads(path.read_text(encoding="utf-8"))
        if not performance_only:
            samples, end, provenance = read_source_wind(source_by_race[race["id"]], root)
            if end is not None:
                detail["race"]["window_end_ms"] = end
        attach_performance_analysis(detail)
        if not performance_only:
            attach_tactical_insights(detail, samples, window_end_ms=end, source_provenance=provenance)
        _write_json(path, detail)
        from scripts.build_report_exports import export_report_files
        export_report_files(detail, data / "analysis")
        tactical_snapshots = detail.get("tactical_insights", {}).get("snapshots", [])
        summary["race_count"] += 1
        summary["boat_race_count"] += len(detail["boats"])
        summary["snapshot_count"] += len(tactical_snapshots)
        summary["conditional_projection_count"] += sum(s["projection_change_deg"] is not None for s in tactical_snapshots)
        print(json.dumps({"race_id": race["id"], "snapshots": len(tactical_snapshots),
                          "refresh": "performance_only" if performance_only else "all_team_analytics",
                          "source_bytes": 0 if performance_only else provenance["source_size_bytes"]}), flush=True)
    _write_json(data / "analysis" / "index.json", build_historical_index(str(catalog_path), str(data / "analysis")))
    build_inventory(root)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Check generated analytics and source sizes without rescanning telemetry")
    parser.add_argument("--race", action="append", dest="race_ids", help="Refresh only this race (repeatable)")
    parser.add_argument("--performance-only", action="store_true", help="Refresh performance metadata and reports from existing detail; preserve tactical data and do not scan raw telemetry")
    arguments = parser.parse_args()
    if arguments.verify and arguments.performance_only:
        parser.error("--performance-only refresh cannot be combined with --verify")
    print(json.dumps(verify() if arguments.verify else refresh(race_ids=arguments.race_ids, performance_only=arguments.performance_only)))


if __name__ == "__main__":
    main()
