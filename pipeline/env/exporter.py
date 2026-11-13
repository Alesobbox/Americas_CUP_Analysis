"""Offline packet-4 exporter: course-centre & 1 Hz boat outputs and provenance bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .cache import verify_cache_offline
from .contracts import CANONICAL_CHANNELS, ENVIRONMENT_SCHEMA_V2, validate_environment_v2
from .registry import REGISTRY_VERSION
from .sampler import CachedGridField
from .session_sampling import build_session_channels, load_samplers_for_session, load_session_tracks_1hz, sample_track_points


def _atomic_write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        json.dumps(payload, separators=(",", ":"))
        if compact
        else json.dumps(payload, indent=2) + "\n"
    )
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _course_centre_ticks(ws_ms: int, we_ms: int) -> np.ndarray:
    h_start = (int(ws_ms) // 3_600_000) * 3_600_000
    h_end = ((int(we_ms) + 3_599_999) // 3_600_000) * 3_600_000
    if h_end <= h_start:
        h_end = h_start + 3_600_000
    return np.arange(h_start, h_end + 1, 3_600_000, dtype=np.int64)


def _build_bundle(src: Mapping[str, Any], channels: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    payload = {
        "schema_version": "environment-bundle-1",
        "registry_version": REGISTRY_VERSION,
        "venue_id": src["venue_id"],
        "utc_date": src["utc_date"],
        "channels": {
            ch: {
                "provider_id": ch_doc["provider_id"],
                "dataset": ch_doc["dataset"],
                "dataset_version": ch_doc["dataset_version"],
                "chunk_sha256s": ch_doc.get("chunk_sha256s", []),
                "metadata_sha256": ch_doc["metadata_sha256"],
                "retrieval_time_utc": ch_doc["retrieval_time_utc"],
            }
            for ch, ch_doc in channels.items()
        },
    }
    sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {**payload, "bundle_sha256": sha}


def _export_one_session(
    root: Path,
    cache_root: Path,
    src: Mapping[str, Any],
    task_lookup: Mapping[tuple[str, str, str], dict[str, Any]],
    field_memo: dict[str, CachedGridField | None],
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any], dict[str, dict[str, int]]]:
    samplers, var_map, channel_tasks = load_samplers_for_session(cache_root, src, task_lookup, field_memo)
    bbox = src["bbox"]
    ticks = _course_centre_ticks(int(src["window_start_ms"]), int(src["window_end_ms"]))
    c_lats = np.full(ticks.size, float(bbox["center_lat"]), dtype=float)
    c_lons = np.full(ticks.size, float(bbox["center_lon"]), dtype=float)
    centre_series, centre_stats = sample_track_points(samplers, var_map, ticks, c_lats, c_lons)

    tracks_1hz = load_session_tracks_1hz(root, src)
    boat_series_map: dict[str, Any] = {}
    boat_agg = {ch: {"missing": 0, "total": 0} for ch in CANONICAL_CHANNELS}
    for aid, (t_arr, la_arr, lo_arr) in sorted(tracks_1hz.items()):
        b_series, b_stats = sample_track_points(samplers, var_map, t_arr, la_arr, lo_arr)
        boat_series_map[aid] = b_series
        for ch in CANONICAL_CHANNELS:
            boat_agg[ch]["missing"] += int(b_stats[ch]["missing"])
            boat_agg[ch]["total"] += int(b_stats[ch]["total"])

    channels = build_session_channels(channel_tasks, samplers, centre_stats, boat_agg)
    bundle_doc = _build_bundle(src, channels)
    bsha = bundle_doc["bundle_sha256"]
    rid = str(src["race_id"])
    is_public = bool(src.get("in_public_replay_catalog"))
    boats_payload = (
        {
            "schema_version": "environment-boats-1",
            "parent_schema": ENVIRONMENT_SCHEMA_V2,
            "race_id": rid,
            "bundle_sha256": bsha,
            "sample_hz": 1,
            "boats": boat_series_map,
        }
        if boat_series_map
        else None
    )
    doc: dict[str, Any] = {
        "schema_version": ENVIRONMENT_SCHEMA_V2,
        "registry_version": REGISTRY_VERSION,
        "race_id": rid,
        "session_id": src.get("session_id"),
        "attempt_id": src.get("attempt_id"),
        "family_id": src.get("family_id"),
        "cycle": src.get("cycle"),
        "boat_class": src.get("boat_class"),
        "domain": src.get("domain"),
        "venue_id": src.get("venue_id"),
        "context": "historical_replay_only" if is_public else f"session_{src.get('domain', 'unknown')}",
        "bundle_sha256": bsha,
        "bundle_relpath": f"bundles/{bsha}.json" if is_public else f"../bundles/{bsha}.json",
        "boats_relpath": f"boats/{rid}.json" if (is_public and boats_payload) else None,
        "location": {
            "latitude": round(float(bbox["center_lat"]), 6),
            "longitude": round(float(bbox["center_lon"]), 6),
            "bbox": bbox,
        },
        "window": {
            "start_ms": int(src["window_start_ms"]),
            "end_ms": int(src["window_end_ms"]),
            "start_utc": src.get("window_start_utc"),
            "end_utc": src.get("window_end_utc"),
            "gun_ms": src.get("gun_ms"),
        },
        "channels": channels,
        "course_centre": centre_series,
    }
    validate_environment_v2(doc)
    counts = {
        ch: {
            "cc_missing": int(centre_stats[ch]["missing"]),
            "cc_total": int(centre_stats[ch]["total"]),
            "boat_missing": int(boat_agg[ch]["missing"]),
            "boat_total": int(boat_agg[ch]["total"]),
        }
        for ch in CANONICAL_CHANNELS
    }
    return doc, boats_payload, bundle_doc, counts


def _write_session_outputs(
    root_path: Path,
    src: Mapping[str, Any],
    doc: Mapping[str, Any],
    boats_payload: Mapping[str, Any] | None,
    bundle_doc: Mapping[str, Any],
) -> None:
    env_dir = root_path / ".forecast" / "environment"
    pub_dir = root_path / "public" / "data" / "environment"
    rid = str(doc["race_id"])
    bsha = str(bundle_doc["bundle_sha256"])
    _atomic_write_json(env_dir / "sessions" / f"{rid}.json", doc, compact=True)
    if boats_payload is not None:
        _atomic_write_json(env_dir / "sessions" / "boats" / f"{rid}.json", boats_payload, compact=True)
    _atomic_write_json(env_dir / "bundles" / f"{bsha}.json", bundle_doc)
    if src.get("in_public_replay_catalog"):
        _atomic_write_json(pub_dir / f"{rid}.json", doc)
        _atomic_write_json(pub_dir / "bundles" / f"{bsha}.json", bundle_doc)
        if boats_payload is not None:
            _atomic_write_json(pub_dir / "boats" / f"{rid}.json", boats_payload, compact=True)


def export_all_environments(
    root: Path | str | None = None,
    *,
    verify_cache: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    """Export environment-2 payloads, 1 Hz boat files, and bundles from offline cache."""
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    env_dir = root_path / ".forecast" / "environment"
    cache_root = env_dir / "cache"
    cache_check = verify_cache_offline(root_path) if verify_cache else {"status": "skipped"}

    inv = json.loads((env_dir / "inventory.json").read_text(encoding="utf-8"))
    manifest = json.loads((cache_root / "manifest.json").read_text(encoding="utf-8"))
    task_lookup = {
        (str(t["venue_id"]), str(t["utc_date"]), str(t["group"])): t for t in manifest.get("tasks", [])
    }

    field_memo: dict[str, CachedGridField | None] = {}
    bundles_written: dict[str, dict[str, Any]] = {}
    public_races: list[str] = []
    session_races: list[str] = []
    agg_miss = {
        ch: {"cc_missing": 0, "cc_total": 0, "boat_missing": 0, "boat_total": 0, "fallback_sessions": 0, "unavailable_sessions": 0}
        for ch in CANONICAL_CHANNELS
    }

    for src in inv.get("sources", []):
        if src.get("acquisition_status") != "ready":
            continue
        doc, boats_payload, bundle_doc, per_ch_counts = _export_one_session(
            root_path, cache_root, src, task_lookup, field_memo
        )
        rid = doc["race_id"]
        bsha = bundle_doc["bundle_sha256"]
        bundles_written[bsha] = bundle_doc
        session_races.append(rid)
        if src.get("in_public_replay_catalog"):
            public_races.append(rid)

        for ch in CANONICAL_CHANNELS:
            agg_miss[ch]["cc_missing"] += per_ch_counts[ch]["cc_missing"]
            agg_miss[ch]["cc_total"] += per_ch_counts[ch]["cc_total"]
            agg_miss[ch]["boat_missing"] += per_ch_counts[ch]["boat_missing"]
            agg_miss[ch]["boat_total"] += per_ch_counts[ch]["boat_total"]
            qstat = doc["channels"][ch]["quality_status"]
            if qstat == "fallback":
                agg_miss[ch]["fallback_sessions"] += 1
            elif qstat == "unavailable":
                agg_miss[ch]["unavailable_sessions"] += 1

        if write:
            _write_session_outputs(root_path, src, doc, boats_payload, bundle_doc)

    inv_counts = inv.get("counts") or {}
    summary = {
        "schema_version": "environment-export-summary-1",
        "registry_version": REGISTRY_VERSION,
        "cache_verification": cache_check,
        "ready_sessions_exported": len(session_races),
        "public_replay_exports": len(public_races),
        "unique_bundles": len(bundles_written),
        "excluded_binary_ac37_files": inv_counts.get("ac37_ac75_binary_files", 0),
        "excluded_result_only_without_raw_file": inv_counts.get("result_only_without_raw_file_records", 0),
        "missingness_by_channel": agg_miss,
    }
    if write:
        _atomic_write_json(env_dir / "export_summary.json", summary)
    return summary
