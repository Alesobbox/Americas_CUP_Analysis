"""Authoritative Python environmental spatial/temporal sampler."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import xarray as xr

from .contracts import (
    CALM_WAVE_HS_THRESHOLD_M,
    SLACK_CURRENT_SPEED_MPS,
    kelvin_to_celsius,
    uv_to_speed_dir_towards,
    wrap_deg,
)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute spherical Earth surface distance in metres."""
    r_m = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp * 0.5) ** 2 + math.cos(p1) * math.cos(p2) * (math.sin(dl * 0.5) ** 2)
    return 2.0 * r_m * math.asin(min(1.0, math.sqrt(max(0.0, a))))


def _time_coords_to_ms(times: np.ndarray) -> np.ndarray:
    if times.size == 0:
        return np.zeros(0, dtype=np.int64)
    if np.issubdtype(times.dtype, np.datetime64):
        secs = times.astype("datetime64[s]").astype(np.int64)
        return secs * 1000
    out: list[int] = []
    for item in times:
        if hasattr(item, "year"):
            dt = datetime(
                item.year, item.month, item.day, item.hour, item.minute, item.second, tzinfo=timezone.utc
            )
            out.append(int(round(dt.timestamp() * 1000)))
        else:
            out.append(int(item))
    return np.asarray(out, dtype=np.int64)


class CachedGridField:
    """Normalized in-memory representation of cached gridded or point subsets."""

    def __init__(
        self,
        *,
        lats: np.ndarray,
        lons: np.ndarray,
        times_ms: np.ndarray,
        arrays: dict[str, np.ndarray],
        temporal_support: str,
        native_step_s: int,
        depth_m: float | None,
        temperature_convention: str | None,
    ) -> None:
        order_t = np.argsort(times_ms)
        self.times_ms = times_ms[order_t]
        lat_asc = lats if (lats.size < 2 or lats[1] >= lats[0]) else lats[::-1]
        lon_asc = lons if (lons.size < 2 or lons[1] >= lons[0]) else lons[::-1]
        flip_lat = lats.size >= 2 and lats[1] < lats[0]
        flip_lon = lons.size >= 2 and lons[1] < lons[0]
        self.lats = np.asarray(lat_asc, dtype=float)
        self.lons = np.asarray(lon_asc, dtype=float)
        self.arrays: dict[str, np.ndarray] = {}
        for name, arr in arrays.items():
            sub = arr[order_t]
            if flip_lat:
                sub = sub[:, ::-1, :]
            if flip_lon:
                sub = sub[:, :, ::-1]
            self.arrays[name] = np.asarray(sub, dtype=float)
        self.temporal_support = temporal_support
        self.native_step_s = native_step_s
        self.depth_m = depth_m
        self.temperature_convention = temperature_convention


def _load_netcdf_chunk(path: Path, meta: Mapping[str, Any], temporal_support: str, native_step_s: int) -> CachedGridField:
    with xr.open_dataset(path, engine="netcdf4", decode_cf=True, mask_and_scale=True) as ds_raw:
        ds = ds_raw.load()
    lat_name = "latitude" if "latitude" in ds.coords else "lat"
    lon_name = "longitude" if "longitude" in ds.coords else "lon"
    lats = np.asarray(ds[lat_name].values, dtype=float)
    lons = np.asarray(ds[lon_name].values, dtype=float)
    times_ms = _time_coords_to_ms(np.asarray(ds["time"].values))
    arrays: dict[str, np.ndarray] = {}
    for vname in ds.data_vars:
        arr = np.asarray(ds[vname].values, dtype=float)
        while arr.ndim > 3:
            arr = arr[:, 0, ...]
        if arr.ndim == 2:
            arr = arr[None, :, :]
        units = str(ds[vname].attrs.get("units") or "").lower()
        if ("kelvin" in units or units == "k") and "temp" in vname.lower():
            arr = arr - 273.15
        arrays[str(vname)] = arr
    return CachedGridField(
        lats=lats,
        lons=lons,
        times_ms=times_ms,
        arrays=arrays,
        temporal_support=temporal_support,
        native_step_s=native_step_s,
        depth_m=meta.get("depth_m"),
        temperature_convention=meta.get("temperature_convention"),
    )


def _load_open_meteo_chunk(path: Path, meta: Mapping[str, Any], temporal_support: str, native_step_s: int) -> CachedGridField:
    doc = json.loads(path.read_text(encoding="utf-8"))
    hourly = doc["hourly"]
    times_ms = np.asarray([int(t) * 1000 for t in hourly["time"]], dtype=np.int64)
    lats = np.asarray([float(doc["latitude"])], dtype=float)
    lons = np.asarray([float(doc["longitude"])], dtype=float)
    arrays: dict[str, np.ndarray] = {}
    for k, vals in hourly.items():
        if k == "time":
            continue
        arr = np.asarray([np.nan if v is None else float(v) for v in vals], dtype=float)[:, None, None]
        if str(doc["hourly_units"].get(k) or "").lower() == "k":
            arr = arr - 273.15
        arrays[k] = arr
    return CachedGridField(
        lats=lats,
        lons=lons,
        times_ms=times_ms,
        arrays=arrays,
        temporal_support=temporal_support,
        native_step_s=native_step_s,
        depth_m=meta.get("depth_m"),
        temperature_convention=meta.get("temperature_convention"),
    )


def load_cached_chunks_field(
    cache_root: Path,
    chunks: list[Mapping[str, Any]],
    *,
    temporal_support: str,
    native_step_s: int,
) -> CachedGridField | None:
    """Load and merge cached chunks for one channel into one sorted field."""
    if not chunks:
        return None
    fields: list[CachedGridField] = []
    for ch in chunks:
        obj_p = cache_root / str(ch["object_relpath"])
        if ch.get("format") == "json":
            fields.append(_load_open_meteo_chunk(obj_p, ch, temporal_support, native_step_s))
        else:
            fields.append(_load_netcdf_chunk(obj_p, ch, temporal_support, native_step_s))
    if len(fields) == 1:
        return fields[0]
    first = fields[0]
    times_cat = np.concatenate([f.times_ms for f in fields])
    uniq_t, uniq_idx = np.unique(times_cat, return_index=True)
    merged: dict[str, np.ndarray] = {}
    for vname in first.arrays:
        if all(vname in f.arrays for f in fields):
            merged[vname] = np.concatenate([f.arrays[vname] for f in fields], axis=0)[uniq_idx]
    for f in fields[1:]:
        for vname, arr in f.arrays.items():
            if vname not in merged and arr.shape[0] == first.times_ms.size:
                merged[vname] = arr
    return CachedGridField(
        lats=first.lats,
        lons=first.lons,
        times_ms=uniq_t,
        arrays=merged,
        temporal_support=temporal_support,
        native_step_s=native_step_s,
        depth_m=first.depth_m,
        temperature_convention=first.temperature_convention,
    )


def _cell_bounds(axis: np.ndarray, q: float) -> tuple[int, int] | None:
    if axis.size == 0:
        return None
    if axis.size == 1:
        return 0, 0
    if q < axis[0] - 1e-6 or q > axis[-1] + 1e-6:
        return None
    qc = min(max(q, float(axis[0])), float(axis[-1]))
    hi = int(np.searchsorted(axis, qc, side="left"))
    if hi == 0:
        return 0, 1
    if hi >= axis.size:
        return axis.size - 2, axis.size - 1
    return hi - 1, hi


def _has_land_barrier(
    valid_mask: np.ndarray,
    ci: int,
    cj: int,
    ti: int,
    tj: int,
) -> bool:
    if abs(ti - ci) <= 1 and abs(tj - cj) <= 1:
        if ti != ci and tj != cj:
            return not (valid_mask[ci, tj] or valid_mask[ti, cj])
        return False
    return True


def spatial_weights_at_point(
    lats: np.ndarray,
    lons: np.ndarray,
    valid_mask: np.ndarray,
    qlat: float,
    qlon: float,
) -> tuple[list[tuple[int, int, float]], str, float | None]:
    """Compute bilinear or <=1-cell wet neighbor weights with land-barrier guard."""
    if lats.size == 1 and lons.size == 1:
        if not valid_mask[0, 0]:
            return [], "unavailable_dry_point", None
        return [(0, 0, 1.0)], "nearest_point", haversine_m(qlat, qlon, float(lats[0]), float(lons[0]))

    ib = _cell_bounds(lats, qlat)
    jb = _cell_bounds(lons, qlon)
    if ib is None or jb is None:
        return [], "unavailable_out_of_domain", None
    i0, i1 = ib
    j0, j1 = jb
    corners = [(i0, j0), (i0, j1), (i1, j0), (i1, j1)]
    if all(bool(valid_mask[i, j]) for i, j in corners):
        dy = float(lats[i1] - lats[i0]) or 1.0
        dx = float(lons[j1] - lons[j0]) or 1.0
        wy = min(max((qlat - float(lats[i0])) / dy, 0.0), 1.0)
        wx = min(max((qlon - float(lons[j0])) / dx, 0.0), 1.0)
        w = [
            (i0, j0, (1.0 - wy) * (1.0 - wx)),
            (i0, j1, (1.0 - wy) * wx),
            (i1, j0, wy * (1.0 - wx)),
            (i1, j1, wy * wx),
        ]
        return w, "bilinear", 0.0

    ci = i0 if abs(qlat - float(lats[i0])) <= abs(float(lats[i1]) - qlat) else i1
    cj = j0 if abs(qlon - float(lons[j0])) <= abs(float(lons[j1]) - qlon) else j1
    cands: list[tuple[float, int, int, bool]] = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ti, tj = ci + di, cj + dj
            if not (0 <= ti < lats.size and 0 <= tj < lons.size):
                continue
            if not valid_mask[ti, tj]:
                continue
            dist = haversine_m(qlat, qlon, float(lats[ti]), float(lons[tj]))
            barrier = _has_land_barrier(valid_mask, ci, cj, ti, tj) if not valid_mask[ci, cj] else False
            cands.append((dist, ti, tj, barrier))
    if not cands:
        return [], "unavailable_no_wet_cell", None
    cands.sort(key=lambda item: item[0])
    best_dist, bi, bj, best_barrier = cands[0]
    if best_barrier:
        return [], "unavailable_land_barrier", None
    return [(bi, bj, 1.0)], "nearest_wet_1cell", round(best_dist, 2)


def _sample_field_at_time_index(
    field: CachedGridField,
    t_idx: int,
    qlat: float,
    qlon: float,
    var_names: tuple[str, ...],
) -> tuple[dict[str, float] | None, str, float | None]:
    mask = np.ones((field.lats.size, field.lons.size), dtype=bool)
    for vn in var_names:
        if vn not in field.arrays:
            return None, f"missing_variable:{vn}", None
        mask &= np.isfinite(field.arrays[vn][t_idx])
    weights, method, dist_m = spatial_weights_at_point(field.lats, field.lons, mask, qlat, qlon)
    if not weights:
        return None, method, dist_m
    vals: dict[str, float] = {}
    for vn in var_names:
        slice_2d = field.arrays[vn][t_idx]
        vals[vn] = float(sum(float(slice_2d[i, j]) * w for i, j, w in weights))
    return vals, method, dist_m


def _sample_wave_at_time_index(
    field: CachedGridField,
    t_idx: int,
    qlat: float,
    qlon: float,
    hs_var: str,
    per_var: str,
    dir_var: str,
) -> tuple[dict[str, float] | None, str, float | None]:
    for vn in (hs_var, per_var, dir_var):
        if vn not in field.arrays:
            return None, f"missing_variable:{vn}", None
    mask = (
        np.isfinite(field.arrays[hs_var][t_idx])
        & np.isfinite(field.arrays[per_var][t_idx])
        & np.isfinite(field.arrays[dir_var][t_idx])
    )
    weights, method, dist_m = spatial_weights_at_point(field.lats, field.lons, mask, qlat, qlon)
    if not weights:
        return None, method, dist_m
    hs = float(sum(float(field.arrays[hs_var][t_idx, i, j]) * w for i, j, w in weights))
    per = float(sum(float(field.arrays[per_var][t_idx, i, j]) * w for i, j, w in weights))
    sx = sum(math.sin(math.radians(float(field.arrays[dir_var][t_idx, i, j]))) * w for i, j, w in weights)
    cx = sum(math.cos(math.radians(float(field.arrays[dir_var][t_idx, i, j]))) * w for i, j, w in weights)
    if math.hypot(sx, cx) > 1e-8:
        dir_deg = wrap_deg(math.degrees(math.atan2(sx, cx)))
    else:
        bi, bj, _ = max(weights, key=lambda item: item[2])
        dir_deg = wrap_deg(float(field.arrays[dir_var][t_idx, bi, bj]))
    return {hs_var: hs, per_var: per, dir_var: dir_deg}, method, dist_m


def _temporal_indices(field: CachedGridField, t_ms: int) -> tuple[tuple[int, int, float] | None, dict[str, Any]]:
    times = field.times_ms
    if times.size == 0:
        return None, {"status": "empty_time_axis"}
    if field.temporal_support == "daily_mean":
        q_day = datetime.fromtimestamp(t_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
        for idx, ts in enumerate(times):
            day = datetime.fromtimestamp(int(ts) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            if day == q_day:
                d_start = int(datetime.fromisoformat(f"{q_day}T00:00:00+00:00").timestamp() * 1000)
                return (idx, idx, 0.0), {"start_ms": d_start, "end_ms": d_start + 86_400_000}
        return None, {"status": "unavailable_daily_gap"}

    if field.temporal_support == "hourly_mean":
        h_start = (int(t_ms) // 3_600_000) * 3_600_000
        h_end = h_start + 3_600_000
        best_idx = None
        best_diff = 10**12
        for idx, ts in enumerate(times):
            diff = abs(int(ts) - (h_start + 1_800_000))
            if h_start <= int(ts) < h_end and diff < best_diff:
                best_idx = idx
                best_diff = diff
        if best_idx is not None:
            return (best_idx, best_idx, 0.0), {"start_ms": h_start, "end_ms": h_end}
        return None, {"status": "unavailable_hourly_mean_gap"}

    pos = int(np.searchsorted(times, t_ms, side="right")) - 1
    if pos < 0:
        if abs(int(times[0]) - t_ms) == 0:
            return (0, 0, 0.0), {"start_ms": int(times[0]), "end_ms": int(times[0])}
        return None, {"status": "unavailable_before_window"}
    t0 = int(times[pos])
    if t0 == t_ms:
        return (pos, pos, 0.0), {"start_ms": t0, "end_ms": t0}
    if pos + 1 >= times.size:
        return None, {"status": "unavailable_after_window"}
    t1 = int(times[pos + 1])
    if t1 - t0 > int(field.native_step_s) * 1000:
        return None, {"status": "unavailable_temporal_gap"}
    frac = float(t_ms - t0) / float(t1 - t0)
    return (pos, pos + 1, frac), {"start_ms": t0, "end_ms": t1}


def sample_point(
    fields_by_channel: Mapping[str, CachedGridField | None],
    var_map: Mapping[str, tuple[str, ...]],
    qlat: float,
    qlon: float,
    t_ms: int,
) -> dict[str, Any]:
    """Sample all four environmental channels at one `(lat, lon, utc_ms)` point."""
    out: dict[str, Any] = {
        "current_u_mps": None,
        "current_v_mps": None,
        "current_speed_mps": None,
        "current_dir_towards_deg": None,
        "wave_height_m": None,
        "wave_period_s": None,
        "wave_dir_from_deg": None,
        "air_temperature_c": None,
        "water_temperature_c": None,
        "_meta": {},
    }

    cur_f = fields_by_channel.get("currents")
    if cur_f is not None:
        t_pair, t_info = _temporal_indices(cur_f, t_ms)
        u_var, v_var = var_map["currents"]
        if t_pair is not None:
            i0, i1, frac = t_pair
            s0, m0, d0 = _sample_field_at_time_index(cur_f, i0, qlat, qlon, (u_var, v_var))
            s1, m1, d1 = (s0, m0, d0) if i0 == i1 else _sample_field_at_time_index(cur_f, i1, qlat, qlon, (u_var, v_var))
            if s0 is not None and s1 is not None:
                u = (1.0 - frac) * s0[u_var] + frac * s1[u_var]
                v = (1.0 - frac) * s0[v_var] + frac * s1[v_var]
                spd, d_tw = uv_to_speed_dir_towards(u, v)
                out["current_u_mps"] = u
                out["current_v_mps"] = v
                out["current_speed_mps"] = spd
                out["current_dir_towards_deg"] = d_tw
                out["_meta"]["currents"] = {"method": m0 if i0 == i1 else f"{m0}+{m1}", "distance_m": d0, **t_info}
            else:
                out["_meta"]["currents"] = {"status": m0 if s0 is None else m1, **t_info}
        else:
            out["_meta"]["currents"] = t_info

    wav_f = fields_by_channel.get("waves")
    if wav_f is not None:
        t_pair, t_info = _temporal_indices(wav_f, t_ms)
        h_var, p_var, d_var = var_map["waves"]
        if t_pair is not None:
            i0, i1, frac = t_pair
            s0, m0, d0 = _sample_wave_at_time_index(wav_f, i0, qlat, qlon, h_var, p_var, d_var)
            s1, m1, d1 = (s0, m0, d0) if i0 == i1 else _sample_wave_at_time_index(wav_f, i1, qlat, qlon, h_var, p_var, d_var)
            if s0 is not None and s1 is not None:
                hs = (1.0 - frac) * s0[h_var] + frac * s1[h_var]
                per = (1.0 - frac) * s0[p_var] + frac * s1[p_var]
                sx = (1.0 - frac) * math.sin(math.radians(s0[d_var])) + frac * math.sin(math.radians(s1[d_var]))
                cx = (1.0 - frac) * math.cos(math.radians(s0[d_var])) + frac * math.cos(math.radians(s1[d_var]))
                wdir = wrap_deg(math.degrees(math.atan2(sx, cx))) if math.hypot(sx, cx) > 1e-8 else s0[d_var]
                out["wave_height_m"] = hs
                if hs >= CALM_WAVE_HS_THRESHOLD_M:
                    out["wave_period_s"] = per
                    out["wave_dir_from_deg"] = wdir
                out["_meta"]["waves"] = {"method": m0 if i0 == i1 else f"{m0}+{m1}", "distance_m": d0, **t_info}
            else:
                out["_meta"]["waves"] = {"status": m0 if s0 is None else m1, **t_info}
        else:
            out["_meta"]["waves"] = t_info

    for channel, out_key in (("air_temperature", "air_temperature_c"), ("water_temperature", "water_temperature_c")):
        fld = fields_by_channel.get(channel)
        if fld is None:
            continue
        t_pair, t_info = _temporal_indices(fld, t_ms)
        (vname,) = var_map[channel]
        if t_pair is not None:
            i0, i1, frac = t_pair
            s0, m0, d0 = _sample_field_at_time_index(fld, i0, qlat, qlon, (vname,))
            s1, m1, d1 = (s0, m0, d0) if i0 == i1 else _sample_field_at_time_index(fld, i1, qlat, qlon, (vname,))
            if s0 is not None and s1 is not None:
                out[out_key] = (1.0 - frac) * s0[vname] + frac * s1[vname]
                out["_meta"][channel] = {"method": m0 if i0 == i1 else f"{m0}+{m1}", "distance_m": d0, **t_info}
            else:
                out["_meta"][channel] = {"status": m0 if s0 is None else m1, **t_info}
        else:
            out["_meta"][channel] = t_info
    return out
