"""Replay Export Engine: Generates Web-Ready Replay JSON Artifacts.

Conforms strictly to ReplayManifest interface contract in PROJECT.md:
- Generates public/data/replays/naples_pr1.json
- Generates public/data/manifests.json
"""

from __future__ import annotations

import json
import math
import os
from bisect import bisect_left, bisect_right
from typing import Dict, List, Any, Optional, Tuple

from pipeline.config import (
    LAT0,
    LON0,
    K_LAT,
    K_LON,
    UUID_TO_MARK,
)
from pipeline.contact_coalescer import coalesce_from_replay_dict
from pipeline.ingest import IngestionResult
from pipeline.reconstruction import ReconstructionResult
from pipeline.manoeuvres import Manoeuvre


def build_replay_manifest(
    ingest_result: IngestionResult,
    reconstruction_result: ReconstructionResult,
    manoeuvres_by_boat: Dict[str, List[Manoeuvre]],
    progress_by_boat: Dict[str, List[float]],
    leg_by_boat: Dict[str, List[int]],
    race_id: Optional[str] = None,
    race_name: Optional[str] = None,
    race_date: Optional[str] = None,
    venue: Optional[str] = None,
    virtual_contact_incidents: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assembles the complete ReplayManifest structure conforming to interface contract."""
    sess = ingest_result.session
    timestamps = ingest_result.grid_timestamps_ms
    n_frames = len(timestamps)

    # 1. Safety borders definition
    platform_border = getattr(sess, "platform_border", None) or [
        {"x": 0.0, "y": -0.215},
        {"x": 1.5075, "y": 0.0},
        {"x": 5.415, "y": 6.278},
        {"x": 5.415, "y": 6.89},
        {"x": 0.0, "y": 12.963},
        {"x": -5.415, "y": 6.89},
        {"x": -5.415, "y": 6.278},
        {"x": -1.5075, "y": 0.0},
        {"x": 0.0, "y": -0.215},
    ]

    keep_clear_border = getattr(sess, "keep_clear_border", None) or [
        {"x": 0.0, "y": -0.215},
        {"x": 3.5075, "y": 0.0},
        {"x": 7.415, "y": 6.278},
        {"x": 7.415, "y": 6.89},
        {"x": 2.0, "y": 12.963},
        {"x": -2.0, "y": 12.963},
        {"x": -7.415, "y": 6.89},
        {"x": -7.415, "y": 6.278},
        {"x": -3.5075, "y": 0.0},
        {"x": 0.0, "y": -0.215},
    ]

    safety_borders_dict = {
        "platform_border": platform_border,
        "keep_clear_border": keep_clear_border,
    }

    # 2. Course definition
    # Extract sequences and start marks first to identify active marks
    exported_sequences = []
    start_marks = {"port": "RM8", "starboard": "RM6"}
    if hasattr(sess, "course_sequences") and sess.course_sequences:
        total_legs = len(sess.course_sequences) - 1
        for leg_idx, seq in enumerate(sess.course_sequences):
            gate = seq.get("gate", {})
            p_id = gate.get("port_asset_id")
            s_id = gate.get("starboard_asset_id")
            p_code = UUID_TO_MARK.get(p_id)
            s_code = UUID_TO_MARK.get(s_id)
            if not p_code:
                for c, m in ingest_result.marks.items():
                    if getattr(m, "asset_id", None) == p_id:
                        p_code = c
                        break
                if not p_code:
                    p_code = "RM4" if leg_idx % 2 == 1 else "RM8"
            if not s_code:
                for c, m in ingest_result.marks.items():
                    if getattr(m, "asset_id", None) == s_id:
                        s_code = c
                        break
                if not s_code:
                    s_code = "RM2" if leg_idx % 2 == 1 else "RM6"
            g_type = "START" if leg_idx == 0 else ("FINISH" if leg_idx == total_legs else ("TOP" if leg_idx % 2 == 1 else "BOTTOM"))
            exported_sequences.append({
                "leg": leg_idx,
                "port_mark": p_code,
                "starboard_mark": s_code,
                "gate_type": g_type,
            })
        if exported_sequences:
            start_marks = {
                "port": exported_sequences[0]["port_mark"],
                "starboard": exported_sequences[0]["starboard_mark"],
            }

    # Filter course marks to active race course marks
    active_mark_codes = set()
    for seq in exported_sequences:
        if seq.get("port_mark"):
            active_mark_codes.add(seq["port_mark"])
        if seq.get("starboard_mark"):
            active_mark_codes.add(seq["starboard_mark"])
    if start_marks:
        if start_marks.get("port"):
            active_mark_codes.add(start_marks["port"])
        if start_marks.get("starboard"):
            active_mark_codes.add(start_marks["starboard"])

    if not active_mark_codes:
        active_mark_codes = {"RM8", "RM6", "RM4", "RM2"}

    marks_dict = {}
    active_asset_ids = set()
    for code, m in ingest_result.marks.items():
        if code in active_mark_codes:
            marks_dict[code] = {
                "code": code,
                "name": m.name,
                "target": [round(m.target_x, 2), round(m.target_y, 2)],
                "asset_id": m.asset_id,
                "role": m.role,
            }
            active_asset_ids.add(m.asset_id)

    course_data = {
        "axis_deg": round(sess.course_axis_deg, 4),
        "length_m": round(sess.course_length_m, 2),
        "origin": {"lat": getattr(sess, "origin_lat", LAT0), "lon": getattr(sess, "origin_lon", LON0)},
        "projection": {"k_lat": getattr(sess, "k_lat", K_LAT), "k_lon": getattr(sess, "k_lon", K_LON)},
        "boundaries": {
            "race": [[round(x, 2), round(y, 2)] for x, y in sess.race_boundary],
            "safety": [[round(x, 2), round(y, 2)] for x, y in sess.safety_boundary],
        },
        "safety_borders": safety_borders_dict,
        "boundary_timeline": [
            {
                "t": item["t"],
                "race": [[round(x, 2), round(y, 2)] for x, y in item["race"]],
                "safety": [[round(x, 2), round(y, 2)] for x, y in item["safety"]],
            }
            for item in sess.boundary_timeline
        ],
        "marks": marks_dict,
        "sequences": exported_sequences,
        "start_marks": start_marks,
    }

    # 2. Wind definition
    official_wind = ingest_result.official_wind
    # Compass directions must be averaged on the circle, especially at north.
    if official_wind.raw_timeline:
        angles = [math.radians(w["twd_deg"]) for w in official_wind.raw_timeline]
        mean_twd = math.degrees(math.atan2(sum(math.sin(a) for a in angles),
                                           sum(math.cos(a) for a in angles))) % 360.0
    else:
        mean_twd = 54.3
    mean_tws = (
        sum(official_wind.speed_kt) / len(official_wind.speed_kt)
        if official_wind.speed_kt
        else 10.7
    )

    wind_timeline = []
    # Sample wind every 1 second (every 10 frames) to keep replay JSON compact
    for i in range(0, n_frames, 10):
        t = timestamps[i]
        twd_val = official_wind.direction_deg[i] if official_wind.direction_deg else mean_twd
        tws_val = official_wind.speed_kt[i] if official_wind.speed_kt else mean_tws
        wind_timeline.append({
            "t": t,
            "twd": round(twd_val % 360.0, 1) % 360.0,
            "tws": round(tws_val, 1),
        })

    wind_data = {
        "reference_twd_deg": round(mean_twd, 1),
        "reference_tws_kt": round(mean_tws, 1),
        "timeline": wind_timeline,
    }

    # 3. Chronology definition
    chronology_data = {
        "gun_time": reconstruction_result.chronology.gun_time,
        "window_start": reconstruction_result.chronology.window_start,
        "window_end": reconstruction_result.chronology.window_end,
    }

    # 4. Competitors catalog & summary
    competitors_list = []
    for code, b_data in ingest_result.boats.items():
        comp_rec = reconstruction_result.competitors[code]
        manoeuvres = manoeuvres_by_boat.get(code, [])

        tacks = [m for m in manoeuvres if m.type == "TACK"]
        gybes = [m for m in manoeuvres if m.type == "GYBE"]

        # Race-only summary; exclude pre-start and post-finish telemetry.
        start_ms = max(reconstruction_result.chronology.gun_time, comp_rec.start.crossing_time or reconstruction_result.chronology.gun_time)
        end_ms = comp_rec.finish_time_ms or timestamps[-1]
        start_idx = min(n_frames - 1, bisect_left(timestamps, start_ms))
        end_idx = max(start_idx, bisect_right(timestamps, end_ms) - 1)
        dist_sailed = 0.0
        for i in range(start_idx + 1, end_idx + 1):
            dx = b_data.x[i] - b_data.x[i - 1]
            dy = b_data.y[i] - b_data.y[i - 1]
            dist_sailed += math.hypot(dx, dy)

        count = end_idx - start_idx + 1
        avg_speed = sum(b_data.sog_kt[start_idx:end_idx + 1]) / count if count > 0 else 0.0
        avg_vmg = sum(b_data.vmg_kt[start_idx:end_idx + 1]) / count if count > 0 else 0.0

        # Start block
        start_block = {
            "crossing_time": comp_rec.start.crossing_time or 0,
            "delta_to_gun_s": round(comp_rec.start.delta_to_gun_s, 3) if comp_rec.start.delta_to_gun_s is not None else 0.0,
            "ocs": comp_rec.start.ocs,
            "chosen_side": comp_rec.start.chosen_side,
        }

        # Gates block
        gates_list = []
        for g in comp_rec.gates:
            gates_list.append({
                "leg": g.leg,
                "crossing_time": g.crossing_time,
                "mark_chosen": g.mark_chosen,
                "side": g.side,
            })

        # Manoeuvres block
        manoeuvres_list = []
        for m in manoeuvres:
            manoeuvres_list.append({
                "type": m.type,
                "timestamp": m.timestamp,
                "entry_speed_kt": m.entry_speed_kt,
                "min_speed_kt": m.min_speed_kt,
                "speed_loss_kt": m.speed_loss_kt,
                "recovery_time_s": m.recovery_time_s,
            })

        # Summary block
        summary_block = {
            "finish_rank": comp_rec.official_rank or 9,
            "elapsed_s": round(comp_rec.elapsed_s, 3) if comp_rec.elapsed_s is not None else 0.0,
            "distance_sailed_m": round(dist_sailed, 1),
            "tack_count": len(tacks),
            "gybe_count": len(gybes),
            "avg_speed_kt": round(avg_speed, 1),
            "avg_vmg_kt": round(avg_vmg, 1),
        }

        competitors_list.append({
            "id": comp_rec.asset_id,
            "team_code": code,
            "team_name": comp_rec.team_name,
            "color": comp_rec.color,
            "classification": comp_rec.classification,
            "start": start_block,
            "gates": gates_list,
            "manoeuvres": manoeuvres_list,
            "summary": summary_block,
        })

    # Sort competitors by finish rank
    competitors_list.sort(key=lambda c: c["summary"]["finish_rank"])

    # 5. Telemetry streams
    boats_telemetry = {}
    for code, b_data in ingest_result.boats.items():
        prog = progress_by_boat.get(code, [0.0] * n_frames)
        legs = leg_by_boat.get(code, [0] * n_frames)

        boats_telemetry[b_data.asset_id] = {
            "x": [round(v, 2) for v in b_data.x],
            "y": [round(v, 2) for v in b_data.y],
            "heading": [round(v % 360.0, 1) % 360.0 for v in b_data.heading],
            "cog": [round(v % 360.0, 1) % 360.0 for v in b_data.cog],
            "sog": [round(v, 1) for v in b_data.sog_kt],
            "vmg": [round(v, 1) for v in b_data.vmg_kt],
            "twa": [round(v, 1) for v in b_data.twa_deg],
            "twd": [round(v % 360.0, 1) % 360.0 for v in b_data.twd_deg],
            "tws": [round(v, 1) for v in b_data.tws_kt],
            "progress_m": [round(v, 1) for v in prog],
            "leg": legs,
        }

    marks_telemetry = {}
    for code, m in ingest_result.marks.items():
        if m.asset_id in active_asset_ids or code in active_mark_codes:
            marks_telemetry[m.asset_id] = {
                "x": [round(v, 2) for v in m.x],
                "y": [round(v, 2) for v in m.y],
            }

    telemetry_data = {
        "timestamps": timestamps,
        "boats": boats_telemetry,
        "marks": marks_telemetry,
    }

    manifest_id = race_id or "naples_pr1"
    manifest_name = race_name or "Naples Practice Race 1"
    manifest_date = race_date or "2026-09-22"
    manifest_venue = venue or "Gulf of Naples, Italy"

    event_edition = getattr(sess, "event_edition", "38th America's Cup Preliminary Regatta Naples 2026")
    boat_class = getattr(sess, "boat_class", "AC40")
    class_evidence = getattr(sess, "class_evidence", {
        "description": "Explicit ASSET_TYPE_AC40 and 12.963m length telemetry envelope",
        "confidence": "CONFIRMED",
        "source": "session.assets and session.platform_border",
    })

    manifest = {
        "id": manifest_id,
        "name": manifest_name,
        "venue": manifest_venue,
        "date": manifest_date,
        "event_edition": event_edition,
        "boat_class": boat_class,
        "class_evidence": class_evidence,
        "safety_borders": safety_borders_dict,
        "virtual_contact_incidents": virtual_contact_incidents,
        "course": course_data,
        "wind": wind_data,
        "chronology": chronology_data,
        "competitors": competitors_list,
        "telemetry": telemetry_data,
        "provenance": {
            "source_records": ingest_result.stats["total_lines"],
            "sample_interval_ms": ingest_result.stats["sample_interval_ms"],
            "measured_streams": ["gnss_position", "heading", "course_over_ground", "speed_over_ground", "boat_true_wind", "official_true_wind", "session_boundaries", "official_competitor_events"],
            "derived_fields": {
                "x_y": "WGS84 GNSS projected to local metres, then interpolated to the replay grid",
                "heading_cog_twd": "Measured angles circularly interpolated to the replay grid",
                "sog_tws": "Measured m/s converted to knots, then interpolated to the replay grid",
                "twa_vmg": "Derived from synchronized heading, wind and boat velocity",
                "progress_m_leg": "Geometric reconstruction from bow positions and gate events",
                "gates_start_manoeuvres": "Reconstructed from official events and trajectories",
                "summary": "Reconstructed classification and elapsed times from source gate timings; race-window distance and average telemetry",
            },
            "stream_coverage": {
                code: cov["gnss"]
                for code, cov in (getattr(ingest_result, "stream_coverage", None) or {}).items()
                if isinstance(cov, dict) and "gnss" in cov
            },
        },
    }

    if virtual_contact_incidents is None:
        # Virtual contacts must match the rounded telemetry actually shipped to
        # the browser; otherwise recomputation can differ at centimetre scale.
        manifest["virtual_contact_incidents"] = coalesce_from_replay_dict(manifest)
    return manifest


def export_replay_artifacts(
    manifest_dict: Dict[str, Any],
    replays_dir: str = "public/data/replays",
    manifests_file: str = "public/data/manifests.json",
) -> Tuple[str, str]:
    """Writes replay JSON and upserts race into manifests.json."""
    os.makedirs(replays_dir, exist_ok=True)
    race_id = manifest_dict.get("id", "naples_pr1")
    replay_path = os.path.join(replays_dir, f"{race_id}.json")

    with open(replay_path, "w", encoding="utf-8") as f:
        json.dump(manifest_dict, f, separators=(",", ":"))

    # Also build / upsert manifests.json
    os.makedirs(os.path.dirname(manifests_file), exist_ok=True)
    event_edition = manifest_dict.get("event_edition", "38th America's Cup Preliminary Regatta Naples 2026")
    boat_class = manifest_dict.get("boat_class", "AC40")

    manifest_index = {
        "event_edition": event_edition,
        "boat_class": boat_class,
        "regatta": "38th America's Cup Preliminary Regatta Naples 2026",
        "venue": manifest_dict.get("venue", "Gulf of Naples, Italy"),
        "races": [],
        "regattas": [
            {
                "id": "naples_2026",
                "name": "America's Cup Preliminary Regatta Naples 2026",
                "event_edition": event_edition,
                "boat_class": boat_class,
                "venue": manifest_dict.get("venue", "Gulf of Naples, Italy"),
                "races": [],
            }
        ],
    }

    if os.path.exists(manifests_file):
        try:
            with open(manifests_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, dict) and "races" in existing:
                    manifest_index = existing
                    manifest_index.setdefault("event_edition", event_edition)
                    manifest_index.setdefault("boat_class", boat_class)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            manifest_index["load_warning"] = str(exc)

    comps = manifest_dict.get("competitors", [])
    winner = next((comp for comp in comps if comp.get("classification") == "RANK_1"
                   and comp.get("summary", {}).get("finish_rank") == 1), None)
    winner_code = winner["team_code"] if winner else None
    duration_s = winner["summary"]["elapsed_s"] if winner else None
    wind_kt = manifest_dict.get("wind", {}).get("reference_tws_kt", 10.7)

    # Upsert into flat races list
    new_root_entry = {
        "id": race_id,
        "name": manifest_dict.get("name", race_id),
        "event_edition": event_edition,
        "boat_class": boat_class,
        "date": manifest_dict.get("date", "2026-09-22"),
        "file": f"replays/{race_id}.json",
        "winner": winner_code,
        "duration_s": duration_s,
        "result_provenance": "reconstructed" if winner else "unavailable",
    }
    races_list = [r for r in manifest_index.get("races", []) if r.get("id") != race_id]
    races_list.append(new_root_entry)
    races_list.sort(key=lambda x: (x.get("date", ""), x.get("id", "")))
    manifest_index["races"] = races_list

    # Upsert into the matching regatta; new events must not be placed under Naples.
    new_regatta_entry = {
        "id": race_id,
        "name": manifest_dict.get("name", race_id),
        "event_edition": event_edition,
        "boat_class": boat_class,
        "date": manifest_dict.get("date", "2026-09-22"),
        "replay_file": f"replays/{race_id}.json",
        "competitors_count": len(comps),
        "winner": winner_code,
        "wind_speed_kt": wind_kt,
        "result_provenance": "reconstructed" if winner else "unavailable",
    }
    target_regatta_id = "cagliari_2026" if "cag" in race_id.lower() or "cagliari" in event_edition.lower() or "cagliari" in manifest_dict.get("venue", "").lower() else "naples_2026"
    target_regatta_name = "38th America's Cup Preliminary Regatta Cagliari 2026" if target_regatta_id == "cagliari_2026" else "38th America's Cup Preliminary Regatta Naples 2026"
    target_venue = "Cagliari, Sardinia, Italy" if target_regatta_id == "cagliari_2026" else "Gulf of Naples, Italy"

    if not manifest_index.get("regattas"):
        manifest_index["regattas"] = []

    matching = next((group for group in manifest_index["regattas"] if group.get("id") == target_regatta_id), None)
    if matching is None:
        matching = {
            "id": target_regatta_id,
            "name": target_regatta_name,
            "event_edition": event_edition,
            "boat_class": boat_class,
            "venue": manifest_dict.get("venue", target_venue),
            "races": [],
        }
        manifest_index["regattas"].append(matching)
    else:
        matching["name"] = target_regatta_name
        matching["event_edition"] = event_edition
        matching["boat_class"] = boat_class

    # Remove an existing ID from another group if metadata changed on re-ingestion.
    for group in manifest_index["regattas"]:
        group["races"] = [r for r in group.get("races", []) if r.get("id") != race_id]
    reg_races = matching["races"]
    reg_races.append(new_regatta_entry)
    reg_races.sort(key=lambda x: (x.get("date", ""), x.get("id", "")))
    matching["races"] = reg_races

    if {group.get("id") for group in manifest_index["regattas"]} >= {"cagliari_2026", "naples_2026"}:
        manifest_index["event_edition"] = "38th America's Cup Preliminary Regattas 2026"
        manifest_index["regatta"] = "38th America's Cup Preliminary Regattas 2026"
        manifest_index["venue"] = "Cagliari and Naples, Italy"

    with open(manifests_file, "w", encoding="utf-8") as f:
        json.dump(manifest_index, f, indent=2)

    # Sync to dist/data if dist exists
    dist_replays = "dist/data/replays"
    dist_manifest = "dist/data/manifests.json"
    if os.path.exists("dist/data"):
        try:
            os.makedirs(dist_replays, exist_ok=True)
            dist_rep_path = os.path.join(dist_replays, f"{race_id}.json")
            with open(dist_rep_path, "w", encoding="utf-8") as f:
                json.dump(manifest_dict, f, separators=(",", ":"))
            with open(dist_manifest, "w", encoding="utf-8") as f:
                json.dump(manifest_index, f, indent=2)
        except OSError as exc:
            raise RuntimeError(f"Failed to sync dist replay artifacts to {dist_replays}: {exc}") from exc

    return replay_path, manifests_file
