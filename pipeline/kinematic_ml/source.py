"""Streaming JSONL normalization and robust packet parsing for AC75 telemetry.

Enforces:
- Exhaustive streaming without arbitrary line caps.
- Preservation of every channel in a packet (no first-field elif chain).
- Pre-session packet retention via metadata staging.
- Explicit UTF-8/JSON error tracking with offsets and bounded examples.
- Native SI preservation (m/s, degrees, Unix ms).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Iterator, Mapping

from .contracts import (
    knots_to_mps,
    resolve_team_identity,
    UnsupportedIdentityError,
)


@dataclass
class NormalizationErrorReport:
    malformed_lines: int = 0
    decoding_errors: int = 0
    bounded_examples: list[dict[str, Any]] = field(default_factory=list)

    def record_error(self, line_ordinal: int, offset: int, error_msg: str, snippet: str):
        self.malformed_lines += 1
        if len(self.bounded_examples) < 3:
            self.bounded_examples.append({
                "line": line_ordinal,
                "offset": offset,
                "error": error_msg,
                "snippet": snippet[:120],
            })


@dataclass(frozen=True)
class RawPacket:
    line_ordinal: int
    offset: int
    correlation_id: str
    sequence_id: int | None
    packet_type: str  # 'session', 'telemetry', 'competitor', 'target', 'other'
    data: dict[str, Any]


def iter_source_packets(
    file_path: Path | str,
    *,
    max_lines: int | None = None,
    error_report: NormalizationErrorReport | None = None,
) -> Iterator[RawPacket]:
    """Stream raw packets from JSONL file with explicit line/offset tracking."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    report = error_report if error_report is not None else NormalizationErrorReport()
    offset = 0

    with open(path, "rb") as fp:
        for line_num, line_bytes in enumerate(fp):
            if max_lines is not None and line_num >= max_lines:
                break
            
            line_bytes_len = len(line_bytes)
            try:
                line_str = line_bytes.decode("utf-8").strip()
            except UnicodeDecodeError as ude:
                report.record_error(line_num, offset, f"UnicodeDecodeError: {ude}", line_bytes[:100].decode("latin-1", errors="replace"))
                offset += line_bytes_len
                continue

            if not line_str:
                offset += line_bytes_len
                continue

            try:
                obj = json.loads(line_str)
                if not isinstance(obj, dict):
                    report.record_error(line_num, offset, "Root JSON is not an object", line_str)
                    offset += line_bytes_len
                    continue

                corr_id = str(obj.get("correlation_id", "") or "")
                seq_id = obj.get("sequence_id")
                if seq_id is not None:
                    try:
                        seq_id = int(seq_id)
                    except (ValueError, TypeError):
                        seq_id = None

                # Determine primary packet type
                packet_type = "other"
                data = obj
                for candidate in ("telemetry", "session", "competitor", "target"):
                    if candidate in obj and isinstance(obj[candidate], dict):
                        packet_type = candidate
                        data = obj[candidate]
                        break

                yield RawPacket(
                    line_ordinal=line_num,
                    offset=offset,
                    correlation_id=corr_id,
                    sequence_id=seq_id,
                    packet_type=packet_type,
                    data=data,
                )

            except json.JSONDecodeError as jde:
                report.record_error(line_num, offset, f"JSONDecodeError: {jde}", line_str)

            offset += line_bytes_len


DEFAULT_CAUSAL_LATENCY_MS = 6000
DEFAULT_AVAILABILITY_BASIS = "assumed_constant_latency_6000ms"


def _parse_session_dict(s: dict[str, Any], meta: dict[str, Any], *, line_ordinal: int = 0) -> None:
    """Helper to parse session metadata, competitors, mark locations, and session revisions."""
    if not meta.get("session_id") and s.get("id"):
        meta["session_id"] = s.get("id")
        meta["session_name"] = s.get("name")
    if s.get("race_start") is not None:
        try:
            meta["race_start_ms"] = int(s["race_start"])
        except (ValueError, TypeError):
            meta["race_start_ms"] = s.get("race_start")
    if s.get("official_wind_asset_id"):
        meta["official_wind_asset_id"] = s.get("official_wind_asset_id")

    rc = s.get("race_course")
    if isinstance(rc, dict):
        seqs = rc.get("sequences", [])
        meta["race_course"] = {
            "course_axis_deg": float(rc["course_axis"]) if rc.get("course_axis") is not None else None,
            "course_length_m": float(rc["course_length"]) if rc.get("course_length") is not None else None,
            "gate_sequence_count": len(seqs) if isinstance(seqs, list) else 0,
            "leg_count": max(0, len(seqs) - 1) if isinstance(seqs, list) else 0,
        }

    assets = {a["id"]: a for a in s.get("assets", []) if isinstance(a, dict) and "id" in a}
    comps = s.get("competitors", {})
    if isinstance(comps, list):
        for c in comps:
            aid = c.get("asset_id") if isinstance(c, dict) else str(c)
            asset = assets.get(aid, {})
            raw_name = (
                asset.get("abbreviation")
                or asset.get("official_name")
                or asset.get("name")
                or aid
            )
            if raw_name:
                try:
                    canonical = resolve_team_identity(raw_name, cycle="AC37")
                except UnsupportedIdentityError:
                    canonical = str(raw_name)
                if canonical not in meta["competitors"]:
                    meta["competitors"].append(canonical)
                if aid:
                    meta["competitor_map"][aid] = canonical
    elif isinstance(comps, dict):
        for cid, cinfo in comps.items():
            if isinstance(cinfo, dict):
                raw_name = (
                    cinfo.get("abbreviation")
                    or cinfo.get("official_name")
                    or cinfo.get("name")
                    or cinfo.get("short_name")
                    or cid
                )
            else:
                raw_name = str(cinfo)
            if raw_name:
                try:
                    canonical = resolve_team_identity(raw_name, cycle="AC37")
                except UnsupportedIdentityError:
                    canonical = str(raw_name)
                if canonical not in meta["competitors"]:
                    meta["competitors"].append(canonical)
                meta["competitor_map"][cid] = canonical

    for tgt in s.get("asset_targets", []):
        if isinstance(tgt, dict):
            aid = tgt.get("asset_id")
            loc = tgt.get("location")
            if aid and isinstance(loc, dict) and "x" in loc and "y" in loc:
                meta["marks"][aid] = {"lat": float(loc["y"]), "lon": float(loc["x"])}

    # Record session revision provenance
    rev_ts = None
    if s.get("timestamp") is not None:
        try:
            rev_ts = int(s["timestamp"])
        except (ValueError, TypeError):
            rev_ts = None

    rc = meta.get("race_course")
    rc_dict = rc if isinstance(rc, dict) else {}
    marks_obj = meta.get("marks")
    marks_dict = marks_obj if isinstance(marks_obj, dict) else {}
    rev_entry = {
        "line_ordinal": line_ordinal,
        "timestamp_ms": rev_ts,
        "race_state": s.get("race_state"),
        "race_start_ms": meta.get("race_start_ms"),
        "course_axis_deg": rc_dict.get("course_axis_deg"),
        "course_length_m": rc_dict.get("course_length_m"),
        "mark_count": len(marks_dict),
    }
    revs = meta.setdefault("session_revisions", [])
    if not revs or revs[-1].get("race_state") != rev_entry["race_state"] or revs[-1].get("course_length_m") != rev_entry["course_length_m"]:
        revs.append(rev_entry)


def _parse_competitor_dict(c: dict[str, Any], meta: dict[str, Any], *, line_ordinal: int = 0) -> None:
    """Capture competitor event revisions, leg timings, start state, and penalties."""
    aid = c.get("asset_id")
    if not aid:
        return
    cmap = meta.get("competitor_map")
    cmap_dict = cmap if isinstance(cmap, dict) else {}
    team_id = cmap_dict.get(aid, str(aid))
    comp_summaries = meta.setdefault("competitor_summaries", {})
    prev = comp_summaries.get(team_id, {"revision_count": 0, "leg_timings": []})

    raw_ts = c.get("timestamp")
    ts_ms = None
    if raw_ts is not None:
        try:
            ts_ms = int(raw_ts)
        except (ValueError, TypeError):
            ts_ms = None

    leg_timings_raw = c.get("leg_timings", [])
    parsed_timings = []
    if isinstance(leg_timings_raw, list):
        for lt in leg_timings_raw:
            if isinstance(lt, dict):
                gt = lt.get("gate_time")
                mt = lt.get("mark_time")
                parsed_timings.append({
                    "leg_number": int(lt.get("leg_number", 0)),
                    "gate_time_ms": int(gt) if gt is not None else None,
                    "mark_time_ms": int(mt) if mt is not None else None,
                })

    start_state = c.get("start_state") if isinstance(c.get("start_state"), dict) else {}
    course_pos = c.get("course_position") if isinstance(c.get("course_position"), dict) else {}
    penalties = c.get("penalties") if isinstance(c.get("penalties"), list) else []
    protests = c.get("protests") if isinstance(c.get("protests"), list) else []

    comp_summaries[team_id] = {
        "asset_id": str(aid),
        "team_id": team_id,
        "revision_count": int(prev.get("revision_count", 0)) + 1,
        "last_line_ordinal": line_ordinal,
        "last_timestamp_ms": ts_ms,
        "max_leg_number": course_pos.get("leg_number"),
        "started": bool(start_state.get("started", False)),
        "entry_state": start_state.get("entry_state"),
        "ocs_calculated": bool(start_state.get("ocs_calculated", False)),
        "penalty_count": len(penalties),
        "protest_count": len(protests),
        "leg_timings": parsed_timings if len(parsed_timings) >= len(prev.get("leg_timings", [])) else prev.get("leg_timings", []),
    }


def extract_session_header(file_path: Path | str, max_scan_lines: int = 500) -> dict[str, Any]:
    """First-pass metadata scan to capture session properties and competitor UUIDs."""
    meta: dict[str, Any] = {
        "session_id": None,
        "session_name": None,
        "race_start_ms": None,
        "official_wind_asset_id": None,
        "race_course": {},
        "competitor_map": {},   # asset_id -> canonical_team
        "competitors": [],        # list of canonical_team
        "marks": {},            # asset_id -> {lat, lon}
        "session_revisions": [],
        "competitor_summaries": {},
    }

    path = Path(file_path)
    with open(path, "rb") as fp:
        for line_idx, line_bytes in enumerate(fp):
            if line_idx >= max_scan_lines:
                break
            try:
                line_str = line_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                continue

            if not line_str or ('"session"' not in line_str and '"competitor"' not in line_str):
                continue

            try:
                obj = json.loads(line_str)
                s = obj.get("session")
                if isinstance(s, dict):
                    _parse_session_dict(s, meta, line_ordinal=line_idx)
                c = obj.get("competitor")
                if isinstance(c, dict):
                    _parse_competitor_dict(c, meta, line_ordinal=line_idx)
                if meta["session_id"] and meta["competitor_map"] and line_idx >= 25:
                    break
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return meta


def normalize_telemetry_packet(
    raw: RawPacket,
    session_meta: Mapping[str, Any],
    *,
    causal_latency_ms: int = DEFAULT_CAUSAL_LATENCY_MS,
) -> Iterator[dict[str, Any]]:
    """Normalize telemetry packet, evaluating every channel independently (no elif chain)."""
    if raw.packet_type != "telemetry":
        return

    data = raw.data
    asset_id = data.get("asset_id")
    if not asset_id:
        return

    raw_ts = data.get("timestamp")
    if raw_ts is None:
        return

    try:
        ts_ms = int(raw_ts)
    except (ValueError, TypeError):
        return

    # Causal availability timestamp (modeled latency or wire receive timestamp)
    raw_avail = data.get("available_at_ms") or data.get("received_timestamp")
    if raw_avail is not None:
        try:
            avail_ms = int(raw_avail)
            avail_basis = "wire_receive_timestamp"
        except (ValueError, TypeError):
            avail_ms = ts_ms + causal_latency_ms
            avail_basis = DEFAULT_AVAILABILITY_BASIS
    else:
        avail_ms = ts_ms + causal_latency_ms
        avail_basis = DEFAULT_AVAILABILITY_BASIS

    competitor_map = session_meta.get("competitor_map", {})
    team_alias = competitor_map.get(asset_id, asset_id)
    source_name = str(data.get("source", "") or "")

    base_record = {
        "line_ordinal": raw.line_ordinal,
        "offset": raw.offset,
        "timestamp_ms": ts_ms,
        "available_at_ms": avail_ms,
        "availability_basis": avail_basis,
        "correlation_id": raw.correlation_id,
        "sequence_id": raw.sequence_id,
        "asset_id": asset_id,
        "team_alias": team_alias,
        "source": source_name,
    }

    # 1. GNSS Position
    if "gnss_position" in data and isinstance(data["gnss_position"], dict):
        pos = data["gnss_position"]
        try:
            lat = float(pos["latitude"])
            lon = float(pos["longitude"])
            alt = float(pos.get("altitude", 0.0))
            if math.isfinite(lat) and math.isfinite(lon):
                yield dict(base_record, channel="gnss_position", lat_deg=lat, lon_deg=lon, alt_m=alt)
        except (ValueError, TypeError, KeyError):
            pass

    # 2. Heading
    if "heading" in data and isinstance(data["heading"], dict):
        try:
            hdg = float(data["heading"]["value"])
            if math.isfinite(hdg):
                yield dict(base_record, channel="heading", heading_deg=hdg % 360.0)
        except (ValueError, TypeError, KeyError):
            pass

    # 3. Speed Over Ground (SI m/s on wire)
    if "speed_over_ground" in data and isinstance(data["speed_over_ground"], dict):
        try:
            sog = float(data["speed_over_ground"]["value"])
            if math.isfinite(sog) and sog >= 0.0:
                yield dict(base_record, channel="speed_over_ground", sog_mps=sog)
        except (ValueError, TypeError, KeyError):
            pass

    # 4. Course Over Ground
    if "course_over_ground" in data and isinstance(data["course_over_ground"], dict):
        try:
            cog = float(data["course_over_ground"]["value"])
            if math.isfinite(cog):
                yield dict(base_record, channel="course_over_ground", cog_deg=cog % 360.0)
        except (ValueError, TypeError, KeyError):
            pass

    # 5. True Wind Speed (SI m/s on wire)
    if "true_wind_speed" in data and isinstance(data["true_wind_speed"], dict):
        try:
            tws = float(data["true_wind_speed"]["value"])
            if math.isfinite(tws) and tws >= 0.0:
                yield dict(base_record, channel="true_wind_speed", tws_mps=tws)
        except (ValueError, TypeError, KeyError):
            pass

    # 6. True Wind Direction
    if "true_wind_direction" in data and isinstance(data["true_wind_direction"], dict):
        try:
            twd = float(data["true_wind_direction"]["value"])
            if math.isfinite(twd):
                yield dict(base_record, channel="true_wind_direction", twd_deg=twd % 360.0)
        except (ValueError, TypeError, KeyError):
            pass
