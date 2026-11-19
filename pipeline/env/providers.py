"""Provider metadata probes, bbox expansion, splitting, and Open-Meteo adapter."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Callable
from urllib.parse import urlencode

from .adapters_grid import (
    _coord_spacing_metrics,
    _default_http_get,
    _open_netcdf_bytes,
    fetch_copernicus_subset,
    fetch_hycom_subset,
    fetch_parthenope_subset,
    probe_copernicus,
)
from .registry import (
    BBOX_EXPAND_CELLS,
    PROVIDER_SPECS,
    ProviderSpec,
    REQUEST_TIMEOUT_SECONDS,
    SPLIT_THRESHOLD_BYTES,
)


def expand_bbox(
    bbox: dict[str, Any],
    spacing_deg: float,
    cells: int = BBOX_EXPAND_CELLS,
) -> dict[str, float]:
    """Expand bounding box symmetrically by `cells` native grid steps."""
    step = max(float(spacing_deg), 1e-4)
    pad = step * float(cells)
    return {
        "lat_min": round(max(-89.9, float(bbox["lat_min"]) - pad), 6),
        "lat_max": round(min(89.9, float(bbox["lat_max"]) + pad), 6),
        "lon_min": round(max(-180.0, float(bbox["lon_min"]) - pad), 6),
        "lon_max": round(min(180.0, float(bbox["lon_max"]) + pad), 6),
    }


def estimate_subset_uncompressed_bytes(spec: ProviderSpec, req: dict[str, Any]) -> int:
    """Estimate uncompressed array byte footprint before downloading."""
    bbox = req["bbox"]
    spacing = max(float(spec.approx_spacing_deg), 1e-4)
    n_lat = max(2, int(math.ceil((bbox["lat_max"] - bbox["lat_min"]) / spacing)) + 3)
    n_lon = max(2, int(math.ceil((bbox["lon_max"] - bbox["lon_min"]) / spacing)) + 3)
    span_s = max(1.0, (int(req["end_ms"]) - int(req["start_ms"])) / 1000.0)
    n_time = max(1, int(math.ceil(span_s / max(1, spec.native_step_s))) + 2)
    n_vars = max(1, len(req["variables"]))
    return int(n_lat * n_lon * n_time * n_vars * 8)


def split_request_if_oversize(
    spec: ProviderSpec,
    req: dict[str, Any],
    *,
    max_bytes: int = SPLIT_THRESHOLD_BYTES,
    est_bytes: int | None = None,
) -> list[dict[str, Any]]:
    """Split a subset request by time, or variables at 1 step, when exceeding ceiling."""
    est = est_bytes if est_bytes is not None else estimate_subset_uncompressed_bytes(spec, req)
    if est <= max_bytes:
        return [req]
    start_ms = int(req["start_ms"])
    end_ms = int(req["end_ms"])
    min_span = max(3_600_000, int(spec.native_step_s) * 1000)
    if end_ms - start_ms > min_span:
        mid_ms = start_ms + (end_ms - start_ms) // 2
        left = dict(req, end_ms=mid_ms)
        right = dict(req, start_ms=mid_ms)
        return split_request_if_oversize(spec, left, max_bytes=max_bytes) + split_request_if_oversize(
            spec, right, max_bytes=max_bytes
        )
    vars_list = list(req["variables"])
    if len(vars_list) > 1:
        mid_v = len(vars_list) // 2
        return [dict(req, variables=vars_list[:mid_v]), dict(req, variables=vars_list[mid_v:])]
    return [req]


def open_meteo_request_url(spec: ProviderSpec, req: dict[str, Any]) -> str:
    """Build an explicit-model, sea-cell, UTC Open-Meteo historical forecast URL."""
    model_id = str(spec.dataset_id)
    if not model_id or model_id == "best_match":
        raise ValueError("Implicit best_match model is prohibited in environment-2")
    bbox = req["bbox"]
    lat = round(0.5 * (float(bbox["lat_min"]) + float(bbox["lat_max"])), 4)
    lon = round(0.5 * (float(bbox["lon_min"]) + float(bbox["lon_max"])), 4)
    start_date = datetime.fromtimestamp(req["start_ms"] / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    end_date = datetime.fromtimestamp(req["end_ms"] / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(req["variables"]),
        "models": model_id,
        "cell_selection": "sea",
        "timeformat": "unixtime",
        "timezone": "UTC",
    }
    return f"{spec.endpoint}?{urlencode(params)}"


def fetch_open_meteo_subset(
    spec: ProviderSpec,
    req: dict[str, Any],
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Fetch and validate explicit-model Open-Meteo hourly JSON response."""
    getter = http_get or _default_http_get
    url = open_meteo_request_url(spec, req)
    code, raw_bytes, _ = getter(url, timeout)
    if code != 200:
        raise RuntimeError(f"Open-Meteo HTTP {code} for {spec.dataset_id}")
    payload = json.loads(raw_bytes.decode("utf-8"))
    if payload.get("error"):
        raise ValueError(f"Open-Meteo provider error: {payload.get('reason') or 'unknown'}")
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError(f"Expected utc_offset_seconds=0, got {payload.get('utc_offset_seconds')!r}")
    hourly = payload.get("hourly")
    units = payload.get("hourly_units")
    if not isinstance(hourly, dict) or not isinstance(units, dict):
        raise ValueError("Malformed Open-Meteo hourly object")
    times = hourly.get("time")
    if not isinstance(times, list) or not times or any(isinstance(t, bool) or not isinstance(t, int) for t in times):
        raise ValueError("Invalid Open-Meteo hourly.time sequence")
    for prev, nxt in zip(times, times[1:]):
        if nxt - prev != 3600:
            raise ValueError(f"Non-hourly Open-Meteo step: {prev} -> {nxt}")
    for var in req["variables"]:
        unit = units.get(var)
        if unit != "°C":
            raise ValueError(f"Unexpected unit {unit!r} for {var}")
        vals = hourly.get(var)
        if not isinstance(vals, list) or len(vals) != len(times):
            raise ValueError(f"Open-Meteo variable {var} length mismatch")
        for val in vals:
            if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val)):
                raise ValueError(f"Non-finite Open-Meteo value {val!r} in {var}")
        if all(val is None for val in vals):
            raise ValueError(f"Open-Meteo returned all-null values for {var}")
    meta_doc = {
        "model_id": spec.dataset_id,
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "hourly_units": units,
        "time_count": len(times),
    }
    meta_sha = hashlib.sha256(json.dumps(meta_doc, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "format": "json",
        "raw_bytes": raw_bytes,
        "raw_subset_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "metadata_sha256": meta_sha,
        "uncompressed_bytes": len(raw_bytes),
        "depth_m": spec.depth_m,
        "returned_coordinates": {
            "lat": [float(payload["latitude"])],
            "lon": [float(payload["longitude"])],
            "time_count": len(times),
        },
        "spatial_support": {"spacing_deg": spec.approx_spacing_deg, "cell_selection": "sea"},
        "initialization_time_utc": "unknown",
        "availability_time_utc": "unknown",
    }


def probe_all_venues(
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
    copernicus_client: Any = None,
) -> dict[str, Any]:
    """Probe metadata endpoints for every configured provider before acquisition."""
    getter = http_get or _default_http_get
    results: dict[str, Any] = {}
    sample_dates = {
        "open_meteo_arome_france_hd": ("2024-09-01", 41.35, 2.17),
        "open_meteo_icon_2i": ("2026-09-22", 40.81, 14.25),
        "open_meteo_ecmwf_ifs": ("2023-11-28", 21.65, 39.08),
    }
    for pid, spec in PROVIDER_SPECS.items():
        try:
            if spec.adapter == "copernicus":
                results[pid] = probe_copernicus(spec, copernicus_client=copernicus_client)
            elif spec.adapter == "parthenope":
                url = spec.endpoint.format(YYYY="2026", MM="09", DD="26", HH="12")
                c1, dds_b, _ = getter(url + ".dds", timeout)
                dds_txt = dds_b.decode("utf-8", errors="replace")
                depth_q = "depth[0:1:1]," if "depth[depth" in dds_txt else ""
                c2, coord_b, _ = getter(f"{url}.nc?{depth_q}latitude[0:1:2],longitude[0:1:2]", timeout)
                ds = _open_netcdf_bytes(coord_b) if c2 == 200 else None
                spacing = _coord_spacing_metrics(ds["latitude"].values, ds["longitude"].values) if ds is not None else {}
                depth0 = float(ds["depth"].values[0]) if ds is not None and "depth" in ds else spec.depth_m
                results[pid] = {
                    "ok": c1 == 200 and c2 == 200,
                    "provider_id": pid,
                    "http_status": c1,
                    "depth_m": depth0,
                    "spatial_support": spacing,
                    "metadata_sha256": hashlib.sha256(dds_b).hexdigest(),
                }
            elif spec.adapter == "hycom":
                c_xml, xml_b, _ = getter(spec.endpoint + "/dataset.xml", timeout)
                results[pid] = {
                    "ok": c_xml == 200,
                    "provider_id": pid,
                    "http_status": c_xml,
                    "metadata_sha256": hashlib.sha256(xml_b).hexdigest(),
                }
            else:
                d_str, la, lo = sample_dates[pid]
                probe_req = {
                    "variables": list(spec.variables),
                    "bbox": {"lat_min": la, "lat_max": la, "lon_min": lo, "lon_max": lo},
                    "start_ms": int(datetime.fromisoformat(f"{d_str}T00:00:00+00:00").timestamp() * 1000),
                    "end_ms": int(datetime.fromisoformat(f"{d_str}T23:00:00+00:00").timestamp() * 1000),
                }
                res = fetch_open_meteo_subset(spec, probe_req, timeout=timeout, http_get=getter)
                results[pid] = {"ok": True, "provider_id": pid, "metadata_sha256": res["metadata_sha256"]}
        except Exception as exc:
            results[pid] = {"ok": False, "provider_id": pid, "error": str(exc)}
    return {
        "status": "pass" if all(r.get("ok") for r in results.values()) else "partial",
        "providers": results,
    }


_ADAPTER_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "copernicus": lambda spec, req, timeout, http_get, cop_client: fetch_copernicus_subset(
        spec, req, copernicus_client=cop_client
    ),
    "parthenope": lambda spec, req, timeout, http_get, _cop: fetch_parthenope_subset(
        spec, req, timeout=timeout, http_get=http_get
    ),
    "hycom": lambda spec, req, timeout, http_get, _cop: fetch_hycom_subset(
        spec, req, timeout=timeout, http_get=http_get
    ),
    "open_meteo": lambda spec, req, timeout, http_get, _cop: fetch_open_meteo_subset(
        spec, req, timeout=timeout, http_get=http_get
    ),
}


def fetch_provider_subset(
    spec: ProviderSpec,
    req: dict[str, Any],
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
    copernicus_client: Any = None,
) -> dict[str, Any]:
    """Dispatch one subset request to its concrete adapter."""
    handler = _ADAPTER_HANDLERS.get(spec.adapter)
    if handler is None:
        raise ValueError(f"Unsupported adapter: {spec.adapter}")
    return handler(spec, req, timeout, http_get, copernicus_client)
