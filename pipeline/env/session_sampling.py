"""Session 1 Hz GNSS track loader and batched field sampler."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq

from pipeline.projection import metric_to_wgs84

from .contracts import (
    CALM_WAVE_HS_THRESHOLD_M,
    CANONICAL_CHANNELS,
    build_channel_provenance,
    uv_to_speed_dir_towards,
    wrap_deg,
)
from .registry import PROVIDER_SPECS, VENUE_POLICIES
from .sampler import CachedGridField, _temporal_indices, load_cached_chunks_field, spatial_weights_at_point


def _ms_to_utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _round_opt(val: float | None, digits: int = 5) -> float | None:
    if val is None or not math.isfinite(val):
        return None
    return round(float(val), digits)


def _dedup_1hz_rows(
    assets: list[Any],
    ts_list: list[Any],
    lat_list: list[Any],
    lon_list: list[Any],
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    grouped: dict[str, tuple[list[int], list[float], list[float]]] = {}
    seen_sec: dict[str, int] = {}
    pairs = sorted(zip(assets, ts_list, lat_list, lon_list), key=lambda r: (str(r[0]), int(r[1])))
    for asset, ts_raw, lat_raw, lon_raw in pairs:
        if asset is None or ts_raw is None or lat_raw is None or lon_raw is None:
            continue
        la, lo = float(lat_raw), float(lon_raw)
        if not (math.isfinite(la) and math.isfinite(lo)):
            continue
        ts_ms = int(ts_raw)
        sec = ts_ms // 1000
        aid = str(asset)
        if seen_sec.get(aid) == sec:
            continue
        seen_sec[aid] = sec
        bucket = grouped.setdefault(aid, ([], [], []))
        bucket[0].append(ts_ms)
        bucket[1].append(la)
        bucket[2].append(lo)
    return {
        aid: (
            np.asarray(t_vals, dtype=np.int64),
            np.asarray(la_vals, dtype=float),
            np.asarray(lo_vals, dtype=float),
        )
        for aid, (t_vals, la_vals, lo_vals) in grouped.items()
    }


def _load_tracks_from_jsonl(
    jsonl_path: Path,
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    assets: list[str] = []
    ts_list: list[int] = []
    lat_list: list[float] = []
    lon_list: list[float] = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if "gnss_position" not in line:
                continue
            obj = json.loads(line)
            tel = obj.get("telemetry")
            if not isinstance(tel, dict):
                continue
            gnss = tel.get("gnss_position")
            if not isinstance(gnss, dict):
                continue
            aid = tel.get("asset_id")
            ts_raw = tel.get("timestamp")
            lat_raw = gnss.get("latitude")
            lon_raw = gnss.get("longitude")
            if aid is None or ts_raw is None or lat_raw is None or lon_raw is None:
                continue
            assets.append(str(aid))
            ts_list.append(int(ts_raw))
            lat_list.append(float(lat_raw))
            lon_list.append(float(lon_raw))
    return _dedup_1hz_rows(assets, ts_list, lat_list, lon_list)


def _load_tracks_from_replay(
    replay_path: Path,
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    doc = json.loads(replay_path.read_text(encoding="utf-8"))
    course = doc.get("course") or {}
    origin = course.get("origin") or {}
    proj = course.get("projection") or {}
    lat0, lon0 = origin.get("lat"), origin.get("lon")
    if lat0 is None or lon0 is None:
        return {}
    k_lat_raw, k_lon_raw = proj.get("k_lat"), proj.get("k_lon")
    k_lat = float(k_lat_raw) if k_lat_raw is not None else None
    k_lon = float(k_lon_raw) if k_lon_raw is not None else None
    tel = doc.get("telemetry") or {}
    timestamps = tel.get("timestamps") or []
    boats = tel.get("boats") or {}
    if not timestamps or not isinstance(boats, dict):
        return {}
    # Deduplicate timestamps to 1 Hz indices up front before projection.
    one_hz_indices: list[int] = []
    last_sec: int | None = None
    for idx, ts_raw in enumerate(timestamps):
        sec = int(ts_raw) // 1000
        if sec != last_sec:
            last_sec = sec
            one_hz_indices.append(idx)
    out: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for aid, bdata in sorted(boats.items()):
        if not isinstance(bdata, dict):
            continue
        xs = bdata.get("x") or []
        ys = bdata.get("y") or []
        t_vals: list[int] = []
        la_vals: list[float] = []
        lo_vals: list[float] = []
        for idx in one_hz_indices:
            if idx >= len(xs) or idx >= len(ys):
                continue
            xv, yv = xs[idx], ys[idx]
            if xv is None or yv is None or not (math.isfinite(float(xv)) and math.isfinite(float(yv))):
                continue
            la, lo = metric_to_wgs84(
                float(xv),
                float(yv),
                float(lat0),
                float(lon0),
                k_lat=k_lat,
                k_lon=k_lon,
            )
            t_vals.append(int(timestamps[idx]))
            la_vals.append(la)
            lo_vals.append(lo)
        if t_vals:
            out[str(aid)] = (
                np.asarray(t_vals, dtype=np.int64),
                np.asarray(la_vals, dtype=float),
                np.asarray(lo_vals, dtype=float),
            )
    return out


def load_session_tracks_1hz(
    root: Path,
    source_entry: Mapping[str, Any],
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Extract sorted 1 Hz `(timestamp_ms, lat_deg, lon_deg)` arrays per asset ID."""
    rel = source_entry.get("position_source")
    pq_path = (root / str(rel)) if rel else None
    if pq_path is not None and pq_path.suffix == ".parquet" and pq_path.is_file():
        schema_names = set(pq.read_schema(pq_path).names)
        if "field" in schema_names and "latitude" in schema_names:
            tbl = pq.read_table(pq_path, columns=["asset_id", "field", "timestamp_ms", "latitude", "longitude"])
            sub = tbl.filter(pc.equal(tbl["field"], "gnss_position"))
            return _dedup_1hz_rows(
                sub["asset_id"].to_pylist(),
                sub["timestamp_ms"].to_pylist(),
                sub["latitude"].to_pylist(),
                sub["longitude"].to_pylist(),
            )
        if "lat_deg" in schema_names and "lon_deg" in schema_names:
            tbl = pq.read_table(pq_path, columns=["asset_id", "timestamp_ms", "lat_deg", "lon_deg"])
            return _dedup_1hz_rows(
                tbl["asset_id"].to_pylist(),
                tbl["timestamp_ms"].to_pylist(),
                tbl["lat_deg"].to_pylist(),
                tbl["lon_deg"].to_pylist(),
            )
    jsonl_rel = rel if (rel and str(rel).endswith(".jsonl")) else source_entry.get("relative_path")
    if jsonl_rel:
        jsonl_path = root / str(jsonl_rel)
        if jsonl_path.suffix == ".jsonl" and jsonl_path.is_file():
            return _load_tracks_from_jsonl(jsonl_path)
    race_id = source_entry.get("race_id")
    if race_id:
        replay_path = root / "public" / "data" / "replays" / f"{race_id}.json"
        if replay_path.is_file():
            return _load_tracks_from_replay(replay_path)
    return {}


class FieldSamplerCache:
    """Per-field mask and temporal lookup cache preserving exact `sample_point` semantics."""

    def __init__(self, field: CachedGridField | None, var_names: tuple[str, ...]) -> None:
        self.field = field
        self.var_names = var_names
        self.masks: dict[int, np.ndarray] = {}
        self.temp_cache: dict[int, tuple[tuple[int, int, float] | None, dict[str, Any]]] = {}

    def _valid_mask(self, t_idx: int) -> np.ndarray | None:
        if t_idx in self.masks:
            return self.masks[t_idx]
        fld = self.field
        assert fld is not None
        mask = np.ones((fld.lats.size, fld.lons.size), dtype=bool)
        for vn in self.var_names:
            if vn not in fld.arrays:
                return None
            mask &= np.isfinite(fld.arrays[vn][t_idx])
        self.masks[t_idx] = mask
        return mask

    def _time_lookup(self, t_ms: int) -> tuple[tuple[int, int, float] | None, dict[str, Any]]:
        if t_ms in self.temp_cache:
            return self.temp_cache[t_ms]
        assert self.field is not None
        res = _temporal_indices(self.field, int(t_ms))
        self.temp_cache[t_ms] = res
        return res

    def eval_scalar(self, qlat: float, qlon: float, t_ms: int) -> tuple[dict[str, float] | None, str, float | None]:
        """Evaluate scalar or vector components at `(lat, lon, t_ms)`."""
        if self.field is None:
            return None, "unavailable_no_field", None
        t_pair, t_info = self._time_lookup(t_ms)
        if t_pair is None:
            return None, str(t_info.get("status", "unavailable")), None
        i0, i1, frac = t_pair
        m0 = self._valid_mask(i0)
        m1 = self._valid_mask(i1)
        if m0 is None or m1 is None:
            return None, "unavailable_missing_variable", None
        w0, meth0, d0 = spatial_weights_at_point(self.field.lats, self.field.lons, m0, qlat, qlon)
        if not w0:
            return None, meth0, d0
        if i0 == i1:
            vals = {vn: float(sum(float(self.field.arrays[vn][i0, ii, jj]) * wt for ii, jj, wt in w0)) for vn in self.var_names}
            return vals, meth0, d0
        w1, meth1, _ = spatial_weights_at_point(self.field.lats, self.field.lons, m1, qlat, qlon)
        if not w1:
            return None, meth1, d0
        vals = {}
        for vn in self.var_names:
            v0 = sum(float(self.field.arrays[vn][i0, ii, jj]) * wt for ii, jj, wt in w0)
            v1 = sum(float(self.field.arrays[vn][i1, ii, jj]) * wt for ii, jj, wt in w1)
            vals[vn] = float((1.0 - frac) * v0 + frac * v1)
        return vals, f"{meth0}+{meth1}", d0

    def _eval_wave_slice(self, idx: int, qlat: float, qlon: float) -> tuple[tuple[float, float, float] | None, str, float | None]:
        assert self.field is not None
        h_var, p_var, d_var = self.var_names
        mask = self._valid_mask(idx)
        if mask is None:
            return None, "unavailable_missing_variable", None
        wt_list, meth, d_m = spatial_weights_at_point(self.field.lats, self.field.lons, mask, qlat, qlon)
        if not wt_list:
            return None, meth, d_m
        hs = sum(float(self.field.arrays[h_var][idx, ii, jj]) * w for ii, jj, w in wt_list)
        per = sum(float(self.field.arrays[p_var][idx, ii, jj]) * w for ii, jj, w in wt_list)
        sx = sum(math.sin(math.radians(float(self.field.arrays[d_var][idx, ii, jj]))) * w for ii, jj, w in wt_list)
        cx = sum(math.cos(math.radians(float(self.field.arrays[d_var][idx, ii, jj]))) * w for ii, jj, w in wt_list)
        if math.hypot(sx, cx) > 1e-8:
            ang = wrap_deg(math.degrees(math.atan2(sx, cx)))
        else:
            bi, bj, _ = max(wt_list, key=lambda item: item[2])
            ang = wrap_deg(float(self.field.arrays[d_var][idx, bi, bj]))
        return (hs, per, ang), meth, d_m

    def eval_wave(self, qlat: float, qlon: float, t_ms: int) -> tuple[dict[str, float] | None, str, float | None]:
        """Evaluate wave `(Hs, Tm-1,0, circular dir)` at `(lat, lon, t_ms)`."""
        if self.field is None:
            return None, "unavailable_no_field", None
        t_pair, t_info = self._time_lookup(t_ms)
        if t_pair is None:
            return None, str(t_info.get("status", "unavailable")), None
        h_var, p_var, d_var = self.var_names
        i0, i1, frac = t_pair
        s0, m0, d0 = self._eval_wave_slice(i0, qlat, qlon)
        if s0 is None:
            return None, m0, d0
        if i0 == i1:
            return {h_var: s0[0], p_var: s0[1], d_var: s0[2]}, m0, d0
        s1, m1, _ = self._eval_wave_slice(i1, qlat, qlon)
        if s1 is None:
            return None, m1, d0
        hs_f = (1.0 - frac) * s0[0] + frac * s1[0]
        per_f = (1.0 - frac) * s0[1] + frac * s1[1]
        sx = (1.0 - frac) * math.sin(math.radians(s0[2])) + frac * math.sin(math.radians(s1[2]))
        cx = (1.0 - frac) * math.cos(math.radians(s0[2])) + frac * math.cos(math.radians(s1[2]))
        ang_f = wrap_deg(math.degrees(math.atan2(sx, cx))) if math.hypot(sx, cx) > 1e-8 else s0[2]
        return {h_var: hs_f, p_var: per_f, d_var: ang_f}, f"{m0}+{m1}", d0


def _record_stat(stats: dict[str, dict[str, Any]], ch: str, meth: str | None, dist: float | None) -> None:
    if meth is None:
        stats[ch]["missing"] += 1
        return
    stats[ch]["methods"].add(meth)
    if dist is not None:
        stats[ch]["distances"].append(dist)


def sample_track_points(
    samplers: Mapping[str, FieldSamplerCache],
    var_map: Mapping[str, tuple[str, ...]],
    times_ms: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
) -> tuple[dict[str, list[Any]], dict[str, dict[str, Any]]]:
    """Evaluate all four channels across ordered `(t_ms, lat, lon)` vectors."""
    n = int(times_ms.size)
    series: dict[str, list[Any]] = {
        "time_ms": [int(t) for t in times_ms],
        "current_u_mps": [None] * n,
        "current_v_mps": [None] * n,
        "current_speed_mps": [None] * n,
        "current_dir_towards_deg": [None] * n,
        "wave_height_m": [None] * n,
        "wave_period_s": [None] * n,
        "wave_dir_from_deg": [None] * n,
        "air_temperature_c": [None] * n,
        "water_temperature_c": [None] * n,
    }
    stats: dict[str, dict[str, Any]] = {
        ch: {"missing": 0, "total": n, "methods": set(), "distances": []} for ch in CANONICAL_CHANNELS
    }
    u_var, v_var = var_map["currents"]
    h_var, p_var, d_var = var_map["waves"]
    (air_var,) = var_map["air_temperature"]
    (wat_var,) = var_map["water_temperature"]

    for i in range(n):
        t_i, la_i, lo_i = int(times_ms[i]), float(lats[i]), float(lons[i])
        c_val, c_meth, c_dist = samplers["currents"].eval_scalar(la_i, lo_i, t_i)
        if c_val is not None:
            u, v = c_val[u_var], c_val[v_var]
            spd, d_tw = uv_to_speed_dir_towards(u, v)
            series["current_u_mps"][i] = _round_opt(u, 5)
            series["current_v_mps"][i] = _round_opt(v, 5)
            series["current_speed_mps"][i] = _round_opt(spd, 5)
            series["current_dir_towards_deg"][i] = _round_opt(d_tw, 2)
        _record_stat(stats, "currents", c_meth if c_val is not None else None, c_dist)

        w_val, w_meth, w_dist = samplers["waves"].eval_wave(la_i, lo_i, t_i)
        if w_val is not None:
            hs = w_val[h_var]
            series["wave_height_m"][i] = _round_opt(hs, 4)
            if hs >= CALM_WAVE_HS_THRESHOLD_M:
                series["wave_period_s"][i] = _round_opt(w_val[p_var], 3)
                series["wave_dir_from_deg"][i] = _round_opt(w_val[d_var], 2)
        _record_stat(stats, "waves", w_meth if w_val is not None else None, w_dist)

        a_val, a_meth, a_dist = samplers["air_temperature"].eval_scalar(la_i, lo_i, t_i)
        if a_val is not None:
            series["air_temperature_c"][i] = _round_opt(a_val[air_var], 3)
        _record_stat(stats, "air_temperature", a_meth if a_val is not None else None, a_dist)

        wt_val, wt_meth, wt_dist = samplers["water_temperature"].eval_scalar(la_i, lo_i, t_i)
        if wt_val is not None:
            series["water_temperature_c"][i] = _round_opt(wt_val[wat_var], 3)
        _record_stat(stats, "water_temperature", wt_meth if wt_val is not None else None, wt_dist)
    return series, stats


def load_samplers_for_session(
    cache_root: Path,
    source_entry: Mapping[str, Any],
    task_lookup: Mapping[tuple[str, str, str], dict[str, Any]],
    field_memo: dict[str, CachedGridField | None],
) -> tuple[dict[str, FieldSamplerCache], dict[str, tuple[str, ...]], dict[str, Any]]:
    """Build memoized channel samplers for a single session."""
    vid = str(source_entry.get("venue_id") or "")
    utc_date = str(source_entry.get("utc_date") or "")
    policy = VENUE_POLICIES[vid]
    samplers: dict[str, FieldSamplerCache] = {}
    var_map: dict[str, tuple[str, ...]] = {}
    channel_tasks: dict[str, Any] = {}
    for ch in CANONICAL_CHANNELS:
        task = task_lookup.get((vid, utc_date, ch))
        pid = task.get("selected_provider_id") if task else None
        spec = PROVIDER_SPECS[pid] if pid else PROVIDER_SPECS[policy.providers[ch][0]]
        var_map[ch] = spec.variables
        channel_tasks[ch] = {"task": task, "spec": spec}
        field: CachedGridField | None = None
        if task and task.get("chunks") and pid:
            mkey = f"{vid}__{utc_date}__{ch}__{pid}"
            if mkey not in field_memo:
                field_memo[mkey] = load_cached_chunks_field(
                    cache_root,
                    task["chunks"],
                    temporal_support=spec.temporal_support,
                    native_step_s=spec.native_step_s,
                )
            field = field_memo[mkey]
        samplers[ch] = FieldSamplerCache(field, spec.variables)
    return samplers, var_map, channel_tasks


def build_session_channels(
    channel_tasks: Mapping[str, Any],
    samplers: Mapping[str, FieldSamplerCache],
    centre_stats: Mapping[str, Any],
    boat_stats: Mapping[str, dict[str, int]],
) -> dict[str, dict[str, Any]]:
    """Construct complete channel provenance objects with combined missingness."""
    channels: dict[str, dict[str, Any]] = {}
    for ch in CANONICAL_CHANNELS:
        info = channel_tasks[ch]
        task, spec = info["task"], info["spec"]
        fld = samplers[ch].field
        chunks = list(task.get("chunks") or []) if task else []
        first_chunk = chunks[0] if chunks else {}
        dists = list(centre_stats[ch]["distances"])
        dist_summary = {"min_m": round(min(dists), 2), "max_m": round(max(dists), 2)} if dists else None
        bs = boat_stats.get(ch) or {"missing": 0, "total": 0}
        missing_total = int(centre_stats[ch]["missing"]) + int(bs["missing"])
        point_total = int(centre_stats[ch]["total"]) + int(bs["total"])
        has_data = fld is not None and missing_total < point_total
        quality = (
            "unavailable"
            if not has_data
            else ("fallback" if (task and task.get("fallback_used")) else ("partial" if missing_total > 0 else "available"))
        )
        t_bounds = (
            {
                "min_utc": _ms_to_utc(int(fld.times_ms[0])),
                "max_utc": _ms_to_utc(int(fld.times_ms[-1])),
                "count": int(fld.times_ms.size),
            }
            if fld is not None and fld.times_ms.size
            else {}
        )
        avg_rule = (
            "00:00Z_to_24:00Z_daily_mean"
            if spec.temporal_support == "daily_mean"
            else ("hour_start_to_hour_end_mean" if spec.temporal_support == "hourly_mean" else "instantaneous")
        )
        methods = sorted(centre_stats[ch]["methods"])
        channels[ch] = build_channel_provenance(
            channel=ch,
            provider=spec.provider_name,
            provider_id=spec.provider_id,
            dataset=spec.dataset_id,
            dataset_version=spec.dataset_version,
            variables=list(spec.variables),
            native_spatial_support=first_chunk.get("spatial_support") or {"spacing_deg": spec.approx_spacing_deg},
            native_temporal_support=spec.temporal_support,
            averaging_bounds={"rule": avg_rule, "native_step_s": spec.native_step_s},
            depth_m=first_chunk.get("depth_m") if first_chunk else spec.depth_m,
            temperature_convention=spec.temperature_convention,
            units=spec.units,
            mask_handling="wet_bilinear_or_1cell_nearest_with_land_barrier_guard",
            interpolation="+".join(methods) if methods else "none",
            quality_status=quality,
            request_spec=first_chunk.get("request_spec") or {},
            returned_coordinates=first_chunk.get("returned_coordinates") or {},
            retrieval_time_utc=first_chunk.get("retrieval_time_utc") or "unknown",
            raw_subset_sha256=first_chunk.get("raw_subset_sha256") or "",
            metadata_sha256=first_chunk.get("metadata_sha256") or "",
            valid_time_bounds=t_bounds,
            initialization_time_utc=first_chunk.get("initialization_time_utc") or "unknown",
            availability_time_utc=first_chunk.get("availability_time_utc") or "unknown",
            product_classification=spec.product_classification,
            missing_count=missing_total,
            total_count=point_total,
            fallback_used=bool(task and task.get("fallback_used")),
            fallback_reason=task.get("fallback_reason") if task else "Task absent from acquisition manifest",
            distance_to_wet_cell_m=dist_summary,
        )
        channels[ch]["attribution_url"] = spec.attribution_url
        channels[ch]["chunk_sha256s"] = [str(c.get("raw_subset_sha256") or "") for c in chunks]
    return channels
