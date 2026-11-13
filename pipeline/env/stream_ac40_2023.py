"""Lightweight single-pass streaming cache for unnormalized 2023 AC40 JSONL telemetry."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


def _finite_coord(lat: Any, lon: Any) -> tuple[float, float] | None:
    if isinstance(lat, bool) or isinstance(lon, bool):
        return None
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(la) and math.isfinite(lo)):
        return None
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0):
        return None
    return la, lo


def _extract_polygon_points(boundary: Any, out: list[tuple[float, float]]) -> None:
    if not isinstance(boundary, list):
        return
    for pt in boundary:
        if not isinstance(pt, dict):
            continue
        coord = _finite_coord(pt.get("y", pt.get("latitude")), pt.get("x", pt.get("longitude")))
        if coord is not None:
            out.append(coord)


def _update_session_state(state: dict[str, Any], sess: dict[str, Any]) -> None:
    if sess.get("id") and not state["session_id"]:
        state["session_id"] = str(sess["id"])
    if sess.get("name"):
        state["session_name"] = str(sess["name"])
    for key in ("window_start", "window_end", "race_start"):
        raw = sess.get(key)
        if raw is not None:
            try:
                state[f"{key}_ms"] = int(raw)
            except (TypeError, ValueError):
                pass
    comps = sess.get("competitors")
    if isinstance(comps, list):
        for comp in comps:
            if isinstance(comp, dict) and comp.get("asset_id"):
                aid = str(comp["asset_id"])
                code = str(comp.get("code") or comp.get("short_name") or comp.get("name") or aid)
                state["competitors"][aid] = code
    assets = sess.get("assets")
    if isinstance(assets, dict):
        for aid, meta in assets.items():
            if not isinstance(meta, dict):
                continue
            if meta.get("asset_type") == "ASSET_TYPE_COMPETITOR" or aid in state["competitors"]:
                code = str(meta.get("short_name") or meta.get("abbreviation") or meta.get("name") or aid)
                state["competitors"].setdefault(str(aid), code)
            pos = meta.get("position")
            if isinstance(pos, dict):
                coord = _finite_coord(pos.get("latitude"), pos.get("longitude"))
                if coord is not None:
                    state["mark_points"][str(aid)] = coord
    for bkey in ("race_boundary", "safety_boundary"):
        _extract_polygon_points(sess.get(bkey), state["boundary_points"])


def _append_gnss_1hz(state: dict[str, Any], tel: dict[str, Any]) -> None:
    gnss = tel.get("gnss_position")
    if not isinstance(gnss, dict):
        return
    coord = _finite_coord(gnss.get("latitude"), gnss.get("longitude"))
    aid = tel.get("asset_id")
    ts_raw = tel.get("timestamp")
    if coord is None or aid is None or ts_raw is None:
        return
    try:
        ts_ms = int(ts_raw)
    except (TypeError, ValueError):
        return
    la, lo = coord
    aid_str = str(aid)
    state["t_min_ms"] = ts_ms if state["t_min_ms"] is None else min(state["t_min_ms"], ts_ms)
    state["t_max_ms"] = ts_ms if state["t_max_ms"] is None else max(state["t_max_ms"], ts_ms)
    state["lat_min"] = la if state["lat_min"] is None else min(state["lat_min"], la)
    state["lat_max"] = la if state["lat_max"] is None else max(state["lat_max"], la)
    state["lon_min"] = lo if state["lon_min"] is None else min(state["lon_min"], lo)
    state["lon_max"] = lo if state["lon_max"] is None else max(state["lon_max"], lo)
    sec = ts_ms // 1000
    last_sec = state["last_sec_by_asset"].get(aid_str)
    if last_sec != sec:
        state["last_sec_by_asset"][aid_str] = sec
        state["rows_1hz"].append({
            "asset_id": aid_str,
            "timestamp_ms": ts_ms,
            "lat_deg": la,
            "lon_deg": lo,
        })


def _bbox_summary(state: dict[str, Any]) -> dict[str, Any] | None:
    pts: list[tuple[float, float]] = list(state["boundary_points"]) + list(state["mark_points"].values())
    if state["lat_min"] is not None:
        pts.append((state["lat_min"], state["lon_min"]))
        pts.append((state["lat_max"], state["lon_max"]))
    if not pts:
        return None
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    return {
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
        "center_lat": 0.5 * (lat_min + lat_max),
        "center_lon": 0.5 * (lon_min + lon_max),
        "mark_count": len(state["mark_points"]),
        "boundary_point_count": len(state["boundary_points"]),
    }


def extract_ac40_2023_metadata(
    source_path: Path,
    cache_dir: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Stream one 2023 AC40 JSONL file into compact metadata and 1 Hz GNSS cache."""
    slug = "".join(ch if ch.isalnum() else "_" for ch in source_path.stem).strip("_").lower()
    meta_path = cache_dir / f"{slug}.json"
    tracks_path = cache_dir / f"{slug}_1hz.parquet"
    stat = source_path.stat()
    if not force and meta_path.is_file() and tracks_path.is_file():
        cached = json.loads(meta_path.read_text(encoding="utf-8"))
        if cached.get("source_bytes") == stat.st_size and cached.get("source_mtime_ns") == stat.st_mtime_ns:
            return cached

    cache_dir.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "session_id": None,
        "session_name": None,
        "window_start_ms": None,
        "window_end_ms": None,
        "race_start_ms": None,
        "t_min_ms": None,
        "t_max_ms": None,
        "lat_min": None,
        "lat_max": None,
        "lon_min": None,
        "lon_max": None,
        "competitors": {},
        "mark_points": {},
        "boundary_points": [],
        "last_sec_by_asset": {},
        "rows_1hz": [],
    }
    hasher = hashlib.sha256()
    with source_path.open("rb", buffering=1024 * 1024) as fp:
        for line_bytes in fp:
            hasher.update(line_bytes)
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            sess = obj.get("session")
            if isinstance(sess, dict):
                _update_session_state(state, sess)
            tel = obj.get("telemetry")
            if isinstance(tel, dict):
                _append_gnss_1hz(state, tel)

    schema = pa.schema([
        ("asset_id", pa.string()),
        ("timestamp_ms", pa.int64()),
        ("lat_deg", pa.float64()),
        ("lon_deg", pa.float64()),
    ])
    table = pa.Table.from_pylist(state["rows_1hz"], schema=schema)
    tmp_pq = tracks_path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp_pq, compression="snappy")
    tmp_pq.replace(tracks_path)

    doc = {
        "source_file": source_path.name,
        "source_bytes": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "source_sha256": hasher.hexdigest(),
        "session_id": state["session_id"],
        "session_name": state["session_name"],
        "window_start_ms": state["window_start_ms"] or state["t_min_ms"],
        "window_end_ms": state["window_end_ms"] or state["t_max_ms"],
        "race_start_ms": state["race_start_ms"],
        "t_min_ms": state["t_min_ms"],
        "t_max_ms": state["t_max_ms"],
        "competitors": state["competitors"],
        "bbox": _bbox_summary(state),
        "tracks_1hz_parquet": tracks_path.name,
        "tracks_1hz_rows": len(state["rows_1hz"]),
    }
    tmp_meta = meta_path.with_suffix(".json.tmp")
    tmp_meta.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    tmp_meta.replace(meta_path)
    return doc
