"""Causal alignment and exhaustive steady 5-second window extractor for AC75.

Contract (T06):
- Strictly causal as-of lookups: never reads future frames or timestamps.
- Explicit wind provenance: boat-local wind is isolated per competitor; anonymous pooling is prohibited.
- Duration-weighted physical summaries across 5-second non-overlapping active-leg windows.
- SI units: m/s, degrees [-180, 180) or [0, 360), Unix ms.
- Reuses historical analysis formula owners via contracts.py SI adapters.
- Captures exclusions with explicit reason codes in a structured ledger.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.kinematic_ml.contracts import (
    MOTION_PREDICTOR_ALLOWLIST,
    SteadyWindowRecord,
    leg_course_vmg_mps,
    validate_feature_separation,
    wind_relative_vmg_mps,
)
from pipeline.kinematic_ml.maneuvers import (
    build_maneuver_review_sample,
    circular_diff_deg,
    compute_turn_dynamics,
    detect_angular_turns,
    filter_overlapping_maneuvers,
)
from pipeline.kinematic_ml.routes import (
    LegRouteTemplate,
    RouteSegment,
    RouteTemplateLibrary,
)


def validate_window_support(
    timestamps_ms: Sequence[int],
    start_ms: int,
    end_ms: int,
    *,
    max_gap_ms: int = 1200,
    margin_ms: int = 500,
    min_boundary_frames: int = 3,
) -> dict[str, Any]:
    """Validates window boundary support and checks for internal telemetry dropouts."""
    if not timestamps_ms or end_ms <= start_ms:
        return {
            "valid": False,
            "dropout_exceeded": True,
            "max_gap_ms": float("inf"),
            "pre_count": 0,
            "post_count": 0,
            "internal_count": 0,
        }

    ts = np.asarray(timestamps_ms, dtype=np.int64)
    pre_count = int(np.sum((ts >= start_ms - margin_ms) & (ts <= start_ms)))
    post_count = int(np.sum((ts >= end_ms) & (ts <= end_ms + margin_ms)))

    internal_mask = (ts >= start_ms) & (ts <= end_ms)
    internal_ts = ts[internal_mask]
    internal_count = len(internal_ts)

    if internal_count < 2:
        max_internal_gap = end_ms - start_ms
    else:
        gaps = np.diff(internal_ts)
        max_internal_gap = int(np.max(gaps)) if len(gaps) > 0 else 0
        max_internal_gap = max(
            max_internal_gap,
            int(internal_ts[0] - start_ms),
            int(end_ms - internal_ts[-1]),
        )

    dropout_exceeded = max_internal_gap > max_gap_ms
    valid = (
        pre_count >= min_boundary_frames
        and post_count >= min_boundary_frames
        and not dropout_exceeded
    )

    return {
        "valid": bool(valid),
        "dropout_exceeded": bool(dropout_exceeded),
        "max_gap_ms": float(max_internal_gap),
        "pre_count": pre_count,
        "post_count": post_count,
        "internal_count": internal_count,
    }


def validate_multi_stream_window_support(
    streams: Mapping[str, Sequence[int]],
    start_ms: int,
    end_ms: int,
    *,
    max_gap_ms: int = 1200,
    margin_ms: int = 500,
    min_boundary_frames: int = 3,
) -> dict[str, Any]:
    """Validates boundary support and dropout constraints across all required streams independently."""
    if not streams:
        return {
            "valid": False,
            "dropout_exceeded": True,
            "max_gap_ms": float("inf"),
            "stream_results": {},
        }

    stream_results = {}
    all_valid = True
    any_dropout = False
    max_gap = 0.0

    for name, ts_list in streams.items():
        res = validate_window_support(
            ts_list,
            start_ms,
            end_ms,
            max_gap_ms=max_gap_ms,
            margin_ms=margin_ms,
            min_boundary_frames=min_boundary_frames,
        )
        stream_results[name] = res
        if not res["valid"]:
            all_valid = False
        if res["dropout_exceeded"]:
            any_dropout = True
        max_gap = max(max_gap, res["max_gap_ms"])

    return {
        "valid": bool(all_valid),
        "dropout_exceeded": bool(any_dropout),
        "max_gap_ms": float(max_gap),
        "stream_results": stream_results,
    }


def validate_stream_support(
    timestamps_ms: Sequence[int],
    start_ms: int,
    end_ms: int,
    *,
    max_gap_ms: int = 1200,
    min_duration_fraction: float = 0.95,
) -> dict[str, Any]:
    """Evaluates coverage and dropout constraints for a sensor stream over [start_ms, end_ms]."""
    total_dur = end_ms - start_ms
    if not timestamps_ms or total_dur <= 0:
        return {
            "valid": False,
            "dropout_exceeded": True,
            "max_gap_ms": total_dur,
            "supported_fraction": 0.0,
        }

    ts = np.asarray(timestamps_ms, dtype=np.int64)
    mask = (ts >= start_ms - max_gap_ms) & (ts <= end_ms + max_gap_ms)
    window_ts = ts[mask]

    if len(window_ts) < 1:
        return {
            "valid": False,
            "dropout_exceeded": True,
            "max_gap_ms": total_dur,
            "supported_fraction": 0.0,
        }

    # Internal gaps between points bounded by start_ms and end_ms
    pts = [max(start_ms, min(end_ms, int(t))) for t in window_ts if start_ms <= t <= end_ms]
    if not pts:
        return {
            "valid": False,
            "dropout_exceeded": True,
            "max_gap_ms": total_dur,
            "supported_fraction": 0.0,
        }

    pts = sorted(set(pts))
    gaps = [pts[0] - start_ms]
    for i in range(len(pts) - 1):
        gaps.append(pts[i + 1] - pts[i])
    gaps.append(end_ms - pts[-1])

    max_gap = max(gaps)
    # Calculate supported duration (sum of gaps that do not exceed max_gap_ms)
    supported_ms = sum(g for g in gaps if g <= max_gap_ms)
    fraction = min(1.0, max(0.0, supported_ms / total_dur))

    dropout_exceeded = max_gap > max_gap_ms
    valid = (not dropout_exceeded) and (fraction >= min_duration_fraction)

    return {
        "valid": bool(valid),
        "dropout_exceeded": bool(dropout_exceeded),
        "max_gap_ms": int(max_gap),
        "supported_fraction": round(fraction, 4),
    }


def compute_duration_weighted_mean(
    times_ms: Sequence[int],
    values: Sequence[float],
    start_ms: int,
    end_ms: int,
) -> float | None:
    """Computes duration-weighted mean of scalar values over [start_ms, end_ms].
    
    Uses zero-order hold (piecewise-constant forward step) clipped to interval.
    """
    if not times_ms or len(times_ms) != len(values) or end_ms <= start_ms:
        return None

    # Filter to relevant records (including one prior point for initial state if available)
    pts = sorted(zip(times_ms, values), key=lambda x: x[0])
    
    # Find last point before or at start_ms
    prior_idx = -1
    for i, (t, _) in enumerate(pts):
        if t <= start_ms:
            prior_idx = i
        else:
            break

    relevant = []
    if prior_idx >= 0:
        relevant.append((start_ms, pts[prior_idx][1]))
    
    for t, v in pts:
        if start_ms < t < end_ms:
            relevant.append((t, v))
        elif t >= end_ms:
            break

    if not relevant:
        return None

    # Step integration
    total_val = 0.0
    total_dur = 0
    for i, (cur_t, cur_v) in enumerate(relevant):
        next_t = relevant[i + 1][0] if i + 1 < len(relevant) else end_ms
        dt = next_t - cur_t
        if dt > 0:
            total_val += cur_v * dt
            total_dur += dt

    if total_dur <= 0:
        return None
    return total_val / total_dur


def compute_circular_duration_weighted_mean(
    times_ms: Sequence[int],
    angles_deg: Sequence[float],
    start_ms: int,
    end_ms: int,
) -> float | None:
    """Computes circular duration-weighted mean for directional data wrapped to [0, 360)."""
    if not times_ms or len(times_ms) != len(angles_deg) or end_ms <= start_ms:
        return None

    rads = [math.radians(a) for a in angles_deg]
    sin_vals = [math.sin(r) for r in rads]
    cos_vals = [math.cos(r) for r in rads]

    mean_sin = compute_duration_weighted_mean(times_ms, sin_vals, start_ms, end_ms)
    mean_cos = compute_duration_weighted_mean(times_ms, cos_vals, start_ms, end_ms)

    if mean_sin is None or mean_cos is None:
        return None

    res_deg = math.degrees(math.atan2(mean_sin, mean_cos)) % 360.0
    return res_deg


def select_wind_at_time(
    target_asset_id: str,
    t_ms: int,
    boat_wind: Sequence[tuple[int, float, float]],  # (t_ms, tws, twd)
    course_wind: Sequence[tuple[int, float, float]], # (t_ms, tws, twd)
    *,
    max_stale_ms: int = 2500,
) -> tuple[float | None, float | None, str]:
    """Causally selects wind observations strictly for target_asset_id without anonymous pooling.
    
    Returns (tws_mps, twd_deg, source_kind).
    """
    # Prefer boat-local wind if fresh
    if boat_wind:
        idx = bisect.bisect_right(boat_wind, (t_ms, float("inf"), float("inf"))) - 1
        if idx >= 0:
            t_obs, tws, twd = boat_wind[idx]
            if (t_ms - t_obs) <= max_stale_ms:
                return tws, twd, "boat_local"

    # Fallback to course official wind
    if course_wind:
        idx = bisect.bisect_right(course_wind, (t_ms, float("inf"), float("inf"))) - 1
        if idx >= 0:
            t_obs, tws, twd = course_wind[idx]
            if (t_ms - t_obs) <= max_stale_ms:
                return tws, twd, "course_official"

    return None, None, "stale_or_missing"


@dataclass
class ExclusionLedger:
    """Tracks window exclusion counts stratified by team, day, stage, and wind band."""
    records: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_exclusion(
        self,
        reason: str,
        team_id: str,
        date_str: str,
        stage: str,
        wind_band: str = "medium",
    ) -> None:
        key = f"{team_id}|{date_str}|{stage}|{wind_band}|{reason}"
        self.counts[key] += 1
        if len(self.records) < 1000:
            self.records.append({
                "reason": reason,
                "team_id": team_id,
                "date": date_str,
                "stage": stage,
                "wind_band": wind_band,
            })

    def summary(self) -> dict[str, Any]:
        by_reason = defaultdict(int)
        for k, v in self.counts.items():
            reason = k.split("|")[-1]
            by_reason[reason] += v
        return {
            "total_exclusions": sum(self.counts.values()),
            "by_reason": dict(by_reason),
            "by_key": dict(self.counts),
        }


def _pair_wind_streams(
    tws_stream: Sequence[tuple[int, float]],
    twd_stream: Sequence[tuple[int, float]],
    *,
    max_stale_ms: int = 2500,
) -> list[tuple[int, float, float]]:
    """Pair sorted TWS and TWD streams causally (TWD observation at or before TWS timestamp)."""
    if not tws_stream or not twd_stream:
        return []
    twd_times = [r[0] for r in twd_stream]
    twd_vals = [r[1] for r in twd_stream]
    paired: list[tuple[int, float, float]] = []
    for t_ms, tws in tws_stream:
        idx = bisect.bisect_right(twd_times, t_ms) - 1
        if idx >= 0 and (t_ms - twd_times[idx]) <= max_stale_ms:
            paired.append((t_ms, float(tws), float(twd_vals[idx])))
    return paired


def _slice_sorted_stream(
    times_ms: Sequence[int],
    vals: Sequence[float],
    start_ms: int,
    end_ms: int,
    margin_ms: int = 2500,
) -> tuple[list[int], list[float]]:
    """Slice a sorted (times_ms, vals) stream around [start_ms - margin_ms, end_ms + margin_ms] in O(log N)."""
    left = bisect.bisect_left(times_ms, start_ms - margin_ms)
    right = bisect.bisect_right(times_ms, end_ms + margin_ms)
    return list(times_ms[left:right]), list(vals[left:right])


def extract_partition_artifacts(
    parquet_path: Path,
    meta_json_path: Path | None = None,
    attempt_info: Mapping[str, Any] | None = None,
    exclusion_ledger: ExclusionLedger | None = None,
    *,
    window_duration_ms: int = 5000,
    max_kinematic_gap_ms: int = 1200,
    max_wind_gap_ms: int = 2500,
) -> dict[str, Any]:
    """Extract steady windows, maneuvers, route templates, start intervals, and course summary from a partition."""
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet partition not found: {parquet_path}")

    meta = {}
    if meta_json_path and meta_json_path.exists():
        try:
            meta = json.loads(meta_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}

    competitor_map = meta.get("competitor_map") or {}
    session_name = str(meta.get("session_name") or parquet_path.stem)
    race_start_ms = int(meta["race_start_ms"]) if meta.get("race_start_ms") is not None else None
    causal_latency_ms = int(meta["causal_latency_ms"]) if meta.get("causal_latency_ms") is not None else 6000

    if attempt_info:
        attempt_id = str(attempt_info.get("attempt_id", meta.get("session_id", parquet_path.stem)))
        family_id = str(attempt_info.get("family_id", attempt_id))
        date_str = str(attempt_info.get("date", session_name[:8]))
        stage = str(attempt_info.get("stage", "round_robin"))
        domain = str(attempt_info.get("domain", "competitive"))
    else:
        attempt_id = str(meta.get("session_id") or parquet_path.stem)
        family_id = attempt_id
        date_str = session_name[:8]
        stage = "round_robin" if "RR" in session_name else ("final" if "Finals" in session_name else "practice")
        domain = "practice" if stage == "practice" else "competitive"

    is_practice = 1 if (domain == "practice" or stage in ("practice", "official_practice")) else 0

    table = pq.read_table(
        parquet_path,
        columns=["timestamp_ms", "channel", "asset_id", "heading_deg", "sog_mps", "cog_deg", "twd_deg", "tws_mps"],
        filters=[("channel", "in", ["heading", "speed_over_ground", "course_over_ground", "true_wind_speed", "true_wind_direction"])],
    )
    timestamps = table["timestamp_ms"].to_pylist()
    channels = table["channel"].to_pylist()
    assets = table["asset_id"].to_pylist()
    headings = table["heading_deg"].to_pylist()
    sogs = table["sog_mps"].to_pylist()
    cogs = table["cog_deg"].to_pylist()
    twds = table["twd_deg"].to_pylist()
    twss = table["tws_mps"].to_pylist()

    heading_by_asset: dict[str, list[tuple[int, float]]] = defaultdict(list)
    sog_by_asset: dict[str, list[tuple[int, float]]] = defaultdict(list)
    cog_by_asset: dict[str, list[tuple[int, float]]] = defaultdict(list)
    tws_by_asset: dict[str, list[tuple[int, float]]] = defaultdict(list)
    twd_by_asset: dict[str, list[tuple[int, float]]] = defaultdict(list)
    course_tws_raw: list[tuple[int, float]] = []
    course_twd_raw: list[tuple[int, float]] = []

    for t_ms, ch, aid, hdg, sog, cog, twd, tws in zip(
        timestamps, channels, assets, headings, sogs, cogs, twds, twss
    ):
        if ch == "heading" and hdg is not None:
            heading_by_asset[aid].append((t_ms, float(hdg)))
        elif ch == "speed_over_ground" and sog is not None:
            sog_by_asset[aid].append((t_ms, float(sog)))
        elif ch == "course_over_ground" and cog is not None:
            cog_by_asset[aid].append((t_ms, float(cog)))
        elif ch == "true_wind_speed" and tws is not None:
            if aid in competitor_map:
                tws_by_asset[aid].append((t_ms, float(tws)))
                if twd is not None:
                    twd_by_asset[aid].append((t_ms, float(twd)))
            else:
                course_tws_raw.append((t_ms, float(tws)))
                if twd is not None:
                    course_twd_raw.append((t_ms, float(twd)))
        elif ch == "true_wind_direction" and twd is not None:
            if aid in competitor_map:
                twd_by_asset[aid].append((t_ms, float(twd)))
            else:
                course_twd_raw.append((t_ms, float(twd)))

    wind_by_asset: dict[str, list[tuple[int, float, float]]] = {}
    for aid in competitor_map:
        s_tws = sorted(tws_by_asset.get(aid, []), key=lambda x: x[0])
        s_twd = sorted(twd_by_asset.get(aid, []), key=lambda x: x[0])
        wind_by_asset[aid] = _pair_wind_streams(s_tws, s_twd, max_stale_ms=max_wind_gap_ms)

    course_wind = _pair_wind_streams(
        sorted(course_tws_raw, key=lambda x: x[0]),
        sorted(course_twd_raw, key=lambda x: x[0]),
        max_stale_ms=max_wind_gap_ms,
    )

    # Detect non-overlapping turns and compute turn dynamics per competitor
    turns_by_asset: dict[str, list[dict[str, Any]]] = {}
    maneuver_rows: list[dict[str, Any]] = []

    for aid, team_id in competitor_map.items():
        h_recs = sorted(heading_by_asset.get(aid, []), key=lambda x: x[0])
        sog_recs = sorted(sog_by_asset.get(aid, []), key=lambda x: x[0])
        twd_recs = sorted(twd_by_asset.get(aid, []), key=lambda x: x[0])
        if not twd_recs and course_twd_raw:
            twd_recs = sorted(course_twd_raw, key=lambda x: x[0])

        raw_turns = detect_angular_turns(h_recs, twd_recs)
        filtered_turns = filter_overlapping_maneuvers(raw_turns)
        turns_with_dyn = []
        for idx_t, t in enumerate(filtered_turns):
            if race_start_ms is not None and t["start_ms"] < race_start_ms:
                continue
            dyn = compute_turn_dynamics(t, sog_recs, max_recovery_ms=30_000)
            tws_at_turn, twd_at_turn, _ = select_wind_at_time(
                aid, int(t["start_ms"]), wind_by_asset.get(aid, []), course_wind, max_stale_ms=max_wind_gap_ms
            )
            dyn["team_id"] = team_id
            dyn["attempt_id"] = attempt_id
            dyn["family_id"] = family_id
            dyn["date_str"] = date_str
            dyn["stage"] = stage
            dyn["practice_domain"] = is_practice
            dyn["maneuver_id"] = f"{attempt_id}_{team_id[-4:]}_{idx_t:03d}"
            dyn["as_of_tws_mps"] = round(float(tws_at_turn), 3) if tws_at_turn is not None else None
            dyn["leg_type"] = 1 if dyn.get("turn_type") == "tack" else 0
            turns_with_dyn.append(dyn)
            maneuver_rows.append(dyn)
        turns_by_asset[aid] = turns_with_dyn

    windows: list[SteadyWindowRecord] = []
    window_dicts: list[dict[str, Any]] = []
    start_intervals: list[dict[str, Any]] = []

    for aid, team_id in competitor_map.items():
        h_recs = sorted(heading_by_asset.get(aid, []), key=lambda x: x[0])
        s_recs = sorted(sog_by_asset.get(aid, []), key=lambda x: x[0])
        c_recs = sorted(cog_by_asset.get(aid, []), key=lambda x: x[0])

        if not h_recs or not s_recs or not c_recs:
            continue

        h_times = [r[0] for r in h_recs]
        h_vals = [r[1] for r in h_recs]
        s_times = [r[0] for r in s_recs]
        s_vals = [r[1] for r in s_recs]
        c_times = [r[0] for r in c_recs]
        c_vals = [r[1] for r in c_recs]

        # Measure gun-to-steady foiling interval after race_start_ms
        if race_start_ms is not None and is_practice == 0:
            idx_start = bisect.bisect_left(s_times, race_start_ms)
            steady_reached_ms = None
            for k in range(idx_start, min(len(s_times), idx_start + 600)):
                if s_times[k] > race_start_ms + 60_000:
                    break
                if s_vals[k] >= 12.0:
                    steady_reached_ms = s_times[k]
                    break
            if steady_reached_ms is not None:
                gun_to_steady_s = max(2.0, (steady_reached_ms - race_start_ms) / 1000.0)
                cutoff_ms = race_start_ms - causal_latency_ms
                tws_start, _, tws_src = select_wind_at_time(
                    aid, cutoff_ms, wind_by_asset.get(aid, []), course_wind, max_stale_ms=5000
                )
                start_intervals.append({
                    "attempt_id": attempt_id,
                    "family_id": family_id,
                    "date_str": date_str,
                    "team_id": team_id,
                    "gun_to_steady_s": round(gun_to_steady_s, 3),
                    "tws_mps": round(float(tws_start), 3) if tws_start is not None else None,
                    "wind_source": tws_src,
                    "causal_cutoff_ms": cutoff_ms,
                })

        t_min = max(h_times[0], s_times[0], c_times[0])
        t_max = min(h_times[-1], s_times[-1], c_times[-1])

        # Pre-compute turn exclusion intervals sorted by start
        turn_exclusions = [
            (
                int(trn["start_ms"]) - 5000,
                int(trn["end_ms"]) + 5000 + int((trn.get("recovery_s") or 0.0) * 1000),
            )
            for trn in turns_by_asset.get(aid, [])
        ]

        cur_t = t_min
        while cur_t + window_duration_ms <= t_max:
            w_start = cur_t
            w_end = cur_t + window_duration_ms
            cur_t += window_duration_ms

            if race_start_ms is not None and w_start < race_start_ms:
                if exclusion_ledger:
                    exclusion_ledger.record_exclusion("prestart", team_id, date_str, stage)
                continue

            in_turn = False
            for t_ts, t_te in turn_exclusions:
                if not (w_end < t_ts or w_start > t_te):
                    in_turn = True
                    break
            if in_turn:
                if exclusion_ledger:
                    exclusion_ledger.record_exclusion("maneuver_or_recovery", team_id, date_str, stage)
                continue

            # Slice local windows in O(log N)
            h_win_t, h_win_v = _slice_sorted_stream(h_times, h_vals, w_start, w_end, margin_ms=max_kinematic_gap_ms)
            s_win_t, s_win_v = _slice_sorted_stream(s_times, s_vals, w_start, w_end, margin_ms=max_kinematic_gap_ms)
            c_win_t, c_win_v = _slice_sorted_stream(c_times, c_vals, w_start, w_end, margin_ms=max_kinematic_gap_ms)

            h_supp = validate_stream_support(h_win_t, w_start, w_end, max_gap_ms=max_kinematic_gap_ms)
            s_supp = validate_stream_support(s_win_t, w_start, w_end, max_gap_ms=max_kinematic_gap_ms)
            c_supp = validate_stream_support(c_win_t, w_start, w_end, max_gap_ms=max_kinematic_gap_ms)

            if not (h_supp["valid"] and s_supp["valid"] and c_supp["valid"]):
                if exclusion_ledger:
                    exclusion_ledger.record_exclusion("kinematic_dropout", team_id, date_str, stage)
                continue

            tws_mps, twd_deg, _ = select_wind_at_time(
                aid, w_start, wind_by_asset.get(aid, []), course_wind, max_stale_ms=max_wind_gap_ms
            )
            if tws_mps is None or twd_deg is None:
                if exclusion_ledger:
                    exclusion_ledger.record_exclusion("stale_wind", team_id, date_str, stage)
                continue

            mean_sog = compute_duration_weighted_mean(s_win_t, s_win_v, w_start, w_end)
            mean_heading = compute_circular_duration_weighted_mean(h_win_t, h_win_v, w_start, w_end)
            mean_cog = compute_circular_duration_weighted_mean(c_win_t, c_win_v, w_start, w_end)

            if mean_sog is None or mean_heading is None or mean_cog is None:
                continue

            twa_deg = circular_diff_deg(mean_heading, twd_deg)
            twa_rad = math.radians(twa_deg)
            twa_sin = math.sin(twa_rad)
            twa_cos = math.cos(twa_rad)
            tack_side = 1 if twa_deg >= 0 else -1
            heading_cog_offset_deg = circular_diff_deg(mean_cog, mean_heading)
            leg_type = 1 if abs(twa_deg) < 90.0 else 0
            course_wind_angle = abs(twa_deg)

            rec = SteadyWindowRecord(
                schema_version="ac75-features-1",
                attempt_id=attempt_id,
                team_id=team_id,
                t_start_ms=w_start,
                t_end_ms=w_end,
                duration_s=round((w_end - w_start) / 1000.0, 3),
                tws_mps=round(float(tws_mps), 3),
                twa_sin=round(float(twa_sin), 5),
                twa_cos=round(float(twa_cos), 5),
                tack_side=int(tack_side),
                leg_type=int(leg_type),
                course_wind_angle_deg=round(float(course_wind_angle), 2),
                heading_cog_offset_deg=round(float(heading_cog_offset_deg), 2),
                practice_domain=int(is_practice),
                sog_mps=round(float(mean_sog), 3),
                supported_fraction=round(min(h_supp["supported_fraction"], s_supp["supported_fraction"]), 4),
                max_gap_ms=int(max(h_supp["max_gap_ms"], s_supp["max_gap_ms"])),
                status="valid",
                reason_codes=[],
            )

            pred_feats = {
                "team_id": rec.team_id,
                "tws_mps": rec.tws_mps,
                "twa_sin": rec.twa_sin,
                "twa_cos": rec.twa_cos,
                "tack_side": rec.tack_side,
                "leg_type": rec.leg_type,
                "heading_cog_offset_deg": rec.heading_cog_offset_deg,
                "course_wind_angle_deg": rec.course_wind_angle_deg,
                "practice_domain": rec.practice_domain,
            }
            validate_feature_separation(pred_feats, task_type="motion")
            windows.append(rec)

            w_dict = asdict(rec)
            w_dict["family_id"] = family_id
            w_dict["date_str"] = date_str
            w_dict["stage"] = stage
            w_dict["twd_deg"] = round(float(twd_deg), 2)
            w_dict["twa_deg"] = round(float(twa_deg), 2)
            w_dict["cog_deg"] = round(float(mean_cog), 2)
            w_dict["heading_deg"] = round(float(mean_heading), 2)
            window_dicts.append(w_dict)

    # Extract observed leg route templates from competitor leg_timings and steady windows + turns
    route_templates: list[LegRouteTemplate] = []
    rc_meta = meta.get("race_course") if isinstance(meta.get("race_course"), dict) else {}
    raw_course_axis = rc_meta.get("course_axis_deg")
    raw_course_len = rc_meta.get("course_length_m")
    raw_leg_count = rc_meta.get("leg_count")
    course_axis_deg = float(raw_course_axis) if raw_course_axis is not None else None
    total_course_len = float(raw_course_len) if raw_course_len is not None else None
    leg_count = int(raw_leg_count) if (raw_leg_count is not None and int(raw_leg_count) > 0) else None
    leg_length_est = max(800.0, min(2500.0, total_course_len / 2.0)) if total_course_len is not None else None
    comp_summaries = meta.get("competitor_summaries") if isinstance(meta.get("competitor_summaries"), dict) else {}

    for aid, team_id in (competitor_map.items() if (course_axis_deg is not None and leg_length_est is not None) else ()):
        csum = comp_summaries.get(team_id, {})
        leg_timings = csum.get("leg_timings", [])
        team_wins = [w for w in window_dicts if w["team_id"] == team_id]
        team_turns = turns_by_asset.get(aid, [])

        if isinstance(leg_timings, list) and len(leg_timings) >= 2:
            for k in range(len(leg_timings) - 1):
                t0_leg = leg_timings[k].get("gate_time_ms")
                t1_leg = leg_timings[k + 1].get("gate_time_ms")
                if t0_leg is None or t1_leg is None or t1_leg <= t0_leg + 15_000:
                    continue
                leg_num = int(leg_timings[k + 1].get("leg_number") or (k + 1))
                leg_type = 1 if (leg_num % 2 == 1) else 0
                leg_bearing = course_axis_deg if leg_type == 1 else (course_axis_deg + 180.0) % 360.0

                leg_wins = [w for w in team_wins if t0_leg <= w["t_start_ms"] and w["t_end_ms"] <= t1_leg]
                leg_trns = [t for t in team_turns if t0_leg <= t["start_ms"] and t["end_ms"] <= t1_leg]
                if not leg_wins:
                    continue

                mean_tws = float(np.mean([w["tws_mps"] for w in leg_wins]))
                # Build disjoint straight and maneuver segments in normalized leg-aligned frame (bearing = 0 deg)
                segments: list[RouteSegment] = []
                cur_x, cur_y = 0.0, 0.0
                # Sort events along the leg
                leg_trns_sorted = sorted(leg_trns, key=lambda x: x["start_ms"])
                n_straight_chunks = len(leg_trns_sorted) + 1
                chunk_bounds = [t0_leg] + [int(t["start_ms"]) for t in leg_trns_sorted] + [t1_leg]

                for c_idx in range(n_straight_chunks):
                    c_start = chunk_bounds[c_idx]
                    if c_idx > 0:
                        prev_trn = leg_trns_sorted[c_idx - 1]
                        rec_ms = int((prev_trn.get("recovery_s") or 0.0) * 1000)
                        c_start = max(c_start, int(prev_trn["end_ms"]) + rec_ms)
                    c_end = chunk_bounds[c_idx + 1]

                    chunk_wins = [w for w in leg_wins if w["t_start_ms"] >= c_start - 2500 and w["t_end_ms"] <= c_end + 2500]
                    if chunk_wins and c_end > c_start:
                        dur_chunk_s = (c_end - c_start) / 1000.0
                        mean_sog_c = float(np.mean([w["sog_mps"] for w in chunk_wins]))
                        dist_c = max(20.0, mean_sog_c * dur_chunk_s)
                        # Relative COG angle with respect to leg_bearing
                        rel_cogs = [circular_diff_deg(w["cog_deg"], leg_bearing) for w in chunk_wins]
                        rel_hdgs = [circular_diff_deg(w["heading_deg"], leg_bearing) for w in chunk_wins]
                        mean_rel_cog = float(np.mean(rel_cogs))
                        mean_rel_hdg = float(np.mean(rel_hdgs))
                        rad_rel = math.radians(mean_rel_cog)
                        nx = cur_x + dist_c * math.sin(rad_rel)
                        ny = cur_y + dist_c * math.cos(rad_rel)
                        segments.append(
                            RouteSegment(
                                segment_type="straight",
                                start_pos=(round(cur_x, 2), round(cur_y, 2)),
                                end_pos=(round(nx, 2), round(ny, 2)),
                                distance_m=round(dist_c, 2),
                                target_cog_deg=round(mean_rel_cog % 360.0, 1),
                                target_heading_deg=round(mean_rel_hdg % 360.0, 1),
                            )
                        )
                        cur_x, cur_y = nx, ny

                    if c_idx < len(leg_trns_sorted):
                        trn = leg_trns_sorted[c_idx]
                        t_dur = float(trn.get("duration_s") or 5.0)
                        r_dur = float(trn.get("recovery_s") or 4.0)
                        segments.append(
                            RouteSegment(
                                segment_type="maneuver",
                                start_pos=(round(cur_x, 2), round(cur_y, 2)),
                                end_pos=(round(cur_x, 2), round(cur_y + 15.0, 2)),
                                distance_m=15.0,
                                target_cog_deg=0.0,
                                target_heading_deg=0.0,
                                turn_type=str(trn.get("turn_type", "tack")),
                                turn_rotation_deg=float(trn.get("rotation_deg", 75.0)),
                                maneuver_duration_s=round(t_dur, 3),
                                recovery_s=round(r_dur, 3),
                                is_censored=bool(trn.get("censoring", False)),
                            )
                        )
                        cur_y += 15.0

                if segments and cur_y > 200.0:
                    route_templates.append(
                        LegRouteTemplate(
                            template_id=f"{attempt_id}_{team_id[-4:]}_leg{leg_num}",
                            attempt_id=attempt_id,
                            team_id=team_id,
                            date_str=date_str,
                            stage=stage,
                            leg_number=leg_num,
                            leg_type=leg_type,
                            mean_tws_mps=round(mean_tws, 3),
                            leg_length_m=round(max(800.0, cur_y), 1),
                            segments=segments,
                            is_complete=True,
                        )
                    )

    # Compute strictly causal pre-start context and isolate hindsight whole-race weather separately.
    all_win_tws = [w["tws_mps"] for w in window_dicts if w.get("tws_mps") is not None]
    all_win_twd = [w["twd_deg"] for w in window_dicts if w.get("twd_deg") is not None]
    mean_race_tws: float | None = float(np.mean(all_win_tws)) if all_win_tws else None
    mean_race_twd: float | None = None
    if all_win_twd:
        rads = np.radians(all_win_twd)
        mean_race_twd = float(math.degrees(math.atan2(float(np.mean(np.sin(rads))), float(np.mean(np.cos(rads))))) % 360.0)

    cutoff_ms = (race_start_ms - causal_latency_ms) if race_start_ms is not None else None
    pre_cw: list[tuple[int, float, float]] = []
    prestart_tws: float | None = None
    prestart_twd: float | None = None
    prestart_available_at_ms: int | None = None
    prestart_context_status = "unavailable"
    prestart_unavailable_reason: str | None = None
    if race_start_ms is None:
        prestart_unavailable_reason = "missing_race_start_ms"
    elif not course_wind:
        prestart_unavailable_reason = "missing_course_wind_stream"
    else:
        pre_cw = [cw for cw in course_wind if race_start_ms - 180_000 <= cw[0] <= cutoff_ms]
        if pre_cw:
            prestart_tws = float(np.mean([cw[1] for cw in pre_cw]))
            rads_p = np.radians([cw[2] for cw in pre_cw])
            prestart_twd = float(math.degrees(math.atan2(float(np.mean(np.sin(rads_p))), float(np.mean(np.cos(rads_p))))) % 360.0)
            prestart_available_at_ms = int(max(cw[0] for cw in pre_cw) + causal_latency_ms)
            prestart_context_status = "available"
        else:
            prestart_unavailable_reason = "no_causal_prestart_course_wind"

    course_context_available = (
        course_axis_deg is not None
        and total_course_len is not None
        and leg_length_est is not None
        and leg_count is not None
    )
    race_course_summary = {
        "attempt_id": attempt_id,
        "family_id": family_id,
        "date_str": date_str,
        "stage": stage,
        "practice_domain": is_practice,
        "race_gun_ms": race_start_ms,
        "causal_latency_ms": causal_latency_ms,
        "course_context_status": "available" if course_context_available else "unavailable",
        "course_unavailable_reason": None if course_context_available else "missing_race_course_metadata",
        "course_axis_deg": round(course_axis_deg, 2) if course_axis_deg is not None else None,
        "course_length_m": round(total_course_len, 1) if total_course_len is not None else None,
        "leg_length_m": round(leg_length_est, 1) if leg_length_est is not None else None,
        "leg_count": leg_count,
        "prestart_context_status": prestart_context_status,
        "prestart_unavailable_reason": prestart_unavailable_reason,
        "prestart_available_at_ms": prestart_available_at_ms,
        "prestart_sample_count": len(pre_cw),
        "prestart_tws_mps": round(prestart_tws, 3) if prestart_tws is not None else None,
        "prestart_twd_deg": round(prestart_twd, 2) if prestart_twd is not None else None,
        "prestart_is_whole_race_average": False,
        "prestart_is_invented_default": False,
        "hindsight_whole_race_weather": {
            "mean_tws_mps": round(mean_race_tws, 3) if mean_race_tws is not None else None,
            "mean_twd_deg": round(mean_race_twd, 2) if mean_race_twd is not None else None,
            "is_whole_race_average": True,
        },
    }

    return {
        "windows": windows,
        "window_dicts": window_dicts,
        "maneuvers": maneuver_rows,
        "route_templates": route_templates,
        "start_intervals": start_intervals,
        "race_course_summary": race_course_summary,
    }


def extract_steady_windows_from_parquet(
    parquet_path: Path,
    meta_json_path: Path | None = None,
    exclusion_ledger: ExclusionLedger | None = None,
    *,
    window_duration_ms: int = 5000,
    required_support_fraction: float = 0.95,
    max_kinematic_gap_ms: int = 1200,
    max_wind_gap_ms: int = 2500,
) -> list[SteadyWindowRecord]:
    """Exhaustively extracts non-overlapping 5-second steady windows from a native partition."""
    res = extract_partition_artifacts(
        parquet_path,
        meta_json_path,
        exclusion_ledger=exclusion_ledger,
        window_duration_ms=window_duration_ms,
        max_kinematic_gap_ms=max_kinematic_gap_ms,
        max_wind_gap_ms=max_wind_gap_ms,
    )
    return res["windows"]


def detect_kinematic_turns_no_speed_gate(
    heading_records: Sequence[tuple[int, float]],
    twd_records: Sequence[tuple[int, float]] | None = None,
    *,
    min_rotation_deg: float = 65.0,
    max_duration_ms: int = 18_000,
    reversal_tolerance_ms: int = 1_500,
) -> list[dict[str, Any]]:
    """Legacy-compatible turn detector wrapper calling detect_angular_turns."""
    raw_turns = detect_angular_turns(
        heading_records,
        twd_records,
        min_rotation_deg=min_rotation_deg,
        max_duration_ms=max_duration_ms,
        reversal_tolerance_ms=reversal_tolerance_ms,
    )
    for t in raw_turns:
        t["detection_contract"] = "angular_rotation_only_no_speed_gate"
    return raw_turns


def build_sealed_datasets(
    dataset_id: str = "ac75_native_v1",
    *,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute T06-T09 batch feature, maneuver, route template, and split extraction over all 100 partitions."""
    root = Path(__file__).resolve().parents[2]
    forecast_dir = root / ".forecast" / "ac75_learning"
    native_dir = forecast_dir / "native" / dataset_id
    sealed_dir = out_dir if out_dir is not None else (forecast_dir / "sealed")
    sealed_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = native_dir / "dataset_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Native dataset manifest not found: {manifest_path}")
    native_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    attempts_path = forecast_dir / "attempt_ledger.json"
    attempts_data = json.loads(attempts_path.read_text(encoding="utf-8")) if attempts_path.exists() else {"attempts": []}
    attempt_by_file = {a["source_file"]: a for a in attempts_data.get("attempts", [])}

    frozen_path = forecast_dir / "frozen_evaluation_families.json"
    frozen_data = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else {}
    holdout_families = set(frozen_data.get("reserved_holdout_families", []))

    exclusion_ledger = ExclusionLedger()
    all_window_dicts: list[dict[str, Any]] = []
    all_maneuvers: list[dict[str, Any]] = []
    dev_maneuvers: list[dict[str, Any]] = []
    dev_continuous_windows: list[dict[str, Any]] = []
    route_library = RouteTemplateLibrary()
    dev_start_intervals: list[dict[str, Any]] = []
    race_courses_by_family: dict[str, dict[str, Any]] = {}

    partitions = native_manifest.get("partitions", [])
    t0 = time.perf_counter()
    print(f"Extracting steady windows, maneuvers, and route templates across {len(partitions)} partitions...")

    for idx, part in enumerate(partitions):
        pq_path = native_dir / part["parquet_file"]
        meta_path = pq_path.with_suffix(".json")
        att_info = attempt_by_file.get(part["source_file"])

        res = extract_partition_artifacts(
            pq_path,
            meta_path,
            attempt_info=att_info,
            exclusion_ledger=exclusion_ledger,
        )
        w_dicts = res["window_dicts"]
        m_rows = res["maneuvers"]
        r_tpls = res["route_templates"]
        s_ints = res["start_intervals"]
        rc_sum = res["race_course_summary"]

        all_window_dicts.extend(w_dicts)
        all_maneuvers.extend(m_rows)

        fam_id = rc_sum["family_id"]
        if att_info and att_info.get("scored_outcome_eligible", True):
            race_courses_by_family[fam_id] = rc_sum
        elif fam_id not in race_courses_by_family:
            race_courses_by_family[fam_id] = rc_sum

        # Training/development isolation: exclude frozen final holdout families from route library & review samples
        if fam_id not in holdout_families:
            dev_maneuvers.extend(m_rows)
            for tpl in r_tpls:
                route_library.add_template(tpl)
            dev_start_intervals.extend(s_ints)
            if w_dicts:
                dev_continuous_windows.append({
                    "window_id": f"{rc_sum['attempt_id']}_60s",
                    "attempt_id": rc_sum["attempt_id"],
                    "family_id": fam_id,
                    "team_id": w_dicts[0]["team_id"],
                    "t_start_ms": w_dicts[0]["t_start_ms"],
                    "duration_s": 60.0,
                })

        if (idx + 1) % 10 == 0 or (idx + 1) == len(partitions):
            print(
                f"  Extracted {idx + 1}/{len(partitions)} partitions "
                f"({len(all_window_dicts)} steady windows, {len(all_maneuvers)} maneuvers, "
                f"{route_library.total_templates} dev route templates)..."
            )

    # Write steady_windows.parquet
    windows_pq_path = sealed_dir / "steady_windows.parquet"
    if all_window_dicts:
        win_table = pa.Table.from_pylist(all_window_dicts)
        pq.write_table(win_table, windows_pq_path, compression="snappy")

    # Write maneuvers.parquet
    maneuvers_pq_path = sealed_dir / "maneuvers.parquet"
    if all_maneuvers:
        man_table = pa.Table.from_pylist(all_maneuvers)
        pq.write_table(man_table, maneuvers_pq_path, compression="snappy")

    # Write route_templates.json
    routes_json_path = sealed_dir / "route_templates.json"
    routes_json_path.write_text(json.dumps(route_library.to_dict(), indent=2), encoding="utf-8")

    # Write start_intervals.json
    starts_json_path = sealed_dir / "start_intervals.json"
    starts_json_path.write_text(json.dumps({"intervals": dev_start_intervals}, indent=2), encoding="utf-8")

    # Write race_courses_by_family.json
    courses_json_path = sealed_dir / "race_courses_by_family.json"
    courses_json_path.write_text(json.dumps(race_courses_by_family, indent=2), encoding="utf-8")

    # Write exclusions_ledger.json
    exclusions_json_path = sealed_dir / "exclusions_ledger.json"
    exclusions_json_path.write_text(json.dumps(exclusion_ledger.summary(), indent=2), encoding="utf-8")

    # Write maneuver_review_sample.json (strictly from development families)
    review_sample = build_maneuver_review_sample(dev_maneuvers, dev_continuous_windows)
    review_json_path = sealed_dir / "maneuver_review_sample.json"
    review_json_path.write_text(json.dumps(review_sample, indent=2), encoding="utf-8")

    def _hash_path(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""

    elapsed = time.perf_counter() - t0
    sealed_manifest = {
        "schema_version": "ac75-sealed-dataset-1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "native_dataset_id": dataset_id,
        "total_steady_windows": len(all_window_dicts),
        "total_maneuvers": len(all_maneuvers),
        "dev_maneuvers_count": len(dev_maneuvers),
        "dev_route_templates_count": route_library.total_templates,
        "dev_start_intervals_count": len(dev_start_intervals),
        "total_exclusions": exclusion_ledger.summary()["total_exclusions"],
        "holdout_families_excluded_from_templates": sorted(holdout_families),
        "artifacts": {
            "steady_windows_parquet": windows_pq_path.relative_to(root).as_posix(),
            "steady_windows_sha256": _hash_path(windows_pq_path),
            "maneuvers_parquet": maneuvers_pq_path.relative_to(root).as_posix(),
            "maneuvers_sha256": _hash_path(maneuvers_pq_path),
            "route_templates_json": routes_json_path.relative_to(root).as_posix(),
            "route_templates_sha256": _hash_path(routes_json_path),
            "start_intervals_json": starts_json_path.relative_to(root).as_posix(),
            "start_intervals_sha256": _hash_path(starts_json_path),
            "race_courses_json": courses_json_path.relative_to(root).as_posix(),
            "race_courses_sha256": _hash_path(courses_json_path),
            "exclusions_ledger_json": exclusions_json_path.relative_to(root).as_posix(),
            "exclusions_ledger_sha256": _hash_path(exclusions_json_path),
            "maneuver_review_sample_json": review_json_path.relative_to(root).as_posix(),
            "maneuver_review_sample_sha256": _hash_path(review_json_path),
        },
        "elapsed_s": round(elapsed, 2),
    }
    sealed_manifest_path = sealed_dir / "sealed_dataset_manifest.json"
    sealed_manifest_path.write_text(json.dumps(sealed_manifest, indent=2), encoding="utf-8")

    # Register immutable experiment (T09)
    from pipeline.kinematic_ml.splits import register_experiment
    register_experiment(
        experiment_id="ac75_2024_learned_sim_v1",
        feature_keys=sorted(MOTION_PREDICTOR_ALLOWLIST),
        target_names=["sog_mps", "duration_s", "total_event_s", "race_margin_s", "winner"],
        model_family="empirical_vs_spline_vs_2x32_silu_nn",
        hyperparameters={
            "nn_hidden_layers": [32, 32],
            "nn_activation": "SiLU",
            "nn_seeds": [2027, 2028, 2029],
            "spline_alphas": [0.1, 1.0, 10.0, 100.0],
            "window_duration_s": 5.0,
        },
        dataset_manifest_path=sealed_manifest_path,
    )

    print(
        f"Sealed dataset complete in {elapsed:.1f}s: "
        f"{len(all_window_dicts)} steady windows, {len(all_maneuvers)} maneuvers, "
        f"{route_library.total_templates} dev route templates."
    )
    return sealed_manifest


if __name__ == "__main__":
    build_sealed_datasets()
