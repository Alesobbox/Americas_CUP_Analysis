"""Gridded netCDF/OPeNDAP/Copernicus provider subset fetchers and probes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import xarray as xr

from .registry import ProviderSpec, REQUEST_TIMEOUT_SECONDS, SPLIT_THRESHOLD_BYTES


class SubsetTooLargeError(ValueError):
    """Raised when an uncompressed subset exceeds the 32 MiB ceiling."""


def _canonical_hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _serialize_dataset_netcdf(ds: xr.Dataset) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "subset.nc"
        enc = {"time": {"units": "seconds since 1970-01-01 00:00:00", "dtype": "float64"}} if "time" in ds.coords else None
        ds.to_netcdf(out_path, engine="netcdf4", encoding=enc)
        return out_path.read_bytes()


def _coord_spacing_metrics(lat_vals: np.ndarray, lon_vals: np.ndarray) -> dict[str, Any]:
    lat_arr = np.asarray(lat_vals, dtype=float)
    lon_arr = np.asarray(lon_vals, dtype=float)
    dlat = float(np.median(np.abs(np.diff(lat_arr)))) if lat_arr.size >= 2 else None
    dlon = float(np.median(np.abs(np.diff(lon_arr)))) if lon_arr.size >= 2 else None
    lat_mid = float(np.mean(lat_arr)) if lat_arr.size >= 1 else 0.0
    dy_m = float(dlat * 111_132.0) if dlat is not None else None
    dx_m = float(dlon * 111_320.0 * math.cos(math.radians(lat_mid))) if dlon is not None else None
    return {
        "dlat_deg": round(dlat, 6) if dlat is not None else None,
        "dlon_deg": round(dlon, 6) if dlon is not None else None,
        "approx_dy_m": round(dy_m, 1) if dy_m is not None else None,
        "approx_dx_m": round(dx_m, 1) if dx_m is not None else None,
        "shape": [int(lat_arr.size), int(lon_arr.size)],
    }


def _open_netcdf_bytes(raw_bytes: bytes) -> xr.Dataset:
    try:
        return xr.open_dataset(io.BytesIO(raw_bytes), engine="scipy", mask_and_scale=True)
    except Exception:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_file = Path(tmpdir) / "raw.nc"
            tmp_file.write_bytes(raw_bytes)
            with xr.open_dataset(tmp_file, engine="netcdf4", mask_and_scale=True) as ds:
                return ds.load()


def _default_http_get(url: str, timeout: float) -> tuple[int, bytes, dict[str, str]]:
    safe_url = url.replace("[", "%5B").replace("]", "%5D")
    req = Request(safe_url, headers={"User-Agent": "2d-regatta-replay-env/2"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
            return int(resp.status), resp.read(), headers
    except HTTPError as exc:
        headers = {str(k).lower(): str(v) for k, v in exc.headers.items()} if exc.headers else {}
        return int(exc.code), exc.read(), headers


def _parse_env_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k and k not in os.environ:
            os.environ[k] = v


def load_dotenv_if_present() -> None:
    """Load key-value pairs from .env or ~/.env into os.environ if not already set."""
    _parse_env_file(Path.cwd() / ".env")
    _parse_env_file(Path(__file__).resolve().parents[2] / ".env")
    _parse_env_file(Path.home() / ".env")


def has_copernicus_credentials() -> bool:
    """Return True if Copernicus Marine credentials are configured locally."""
    load_dotenv_if_present()
    user = os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME")
    pwd = os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD")
    if user and pwd:
        return True
    cred_file = Path.home() / ".copernicusmarine" / ".copernicusmarine-credentials"
    return cred_file.is_file()


def probe_copernicus(spec: ProviderSpec, *, copernicus_client: Any = None) -> dict[str, Any]:
    """Run metadata-only describe probe for one Copernicus Marine dataset."""
    client = copernicus_client
    if client is None:
        import copernicusmarine as client  # type: ignore[no-redef]
    cat = client.describe(dataset_id=spec.dataset_id, disable_progress_bar=True)
    vars_found: list[str] = []
    coord_summary: list[dict[str, Any]] = []
    version_found = False
    for prod in getattr(cat, "products", []):
        for ds in getattr(prod, "datasets", []):
            if ds.dataset_id != spec.dataset_id:
                continue
            for ver in getattr(ds, "versions", []):
                if ver.label != spec.dataset_version:
                    continue
                version_found = True
                for part in getattr(ver, "parts", []):
                    for svc in getattr(part, "services", []):
                        if "arco" not in str(svc.service_name) or not getattr(svc, "variables", None):
                            continue
                        vars_found = [v.short_name for v in svc.variables]
                        first = svc.variables[0]
                        coord_summary = [
                            {
                                "id": c.coordinate_id,
                                "min": c.minimum_value,
                                "max": c.maximum_value,
                                "step": c.step,
                            }
                            for c in getattr(first, "coordinates", [])
                        ]
                        break
                    if coord_summary:
                        break
    return {
        "ok": version_found and all(v in vars_found for v in spec.variables),
        "provider_id": spec.provider_id,
        "dataset_id": spec.dataset_id,
        "dataset_version": spec.dataset_version,
        "auth_configured": has_copernicus_credentials(),
        "variables_present": [v for v in spec.variables if v in vars_found],
        "coordinates": coord_summary,
        "metadata_sha256": _canonical_hash({"vars": vars_found, "coords": coord_summary}),
    }


def _select_shallowest_depth(ds: xr.Dataset) -> tuple[xr.Dataset, float | None]:
    for name in ("depth", "lev", "z"):
        if name in ds.coords or name in ds.dims:
            vals = np.asarray(ds[name].values, dtype=float)
            valid = vals[np.isfinite(vals)]
            depth_val = float(np.min(np.abs(valid))) if valid.size else None
            idx = int(np.argmin(np.abs(vals))) if vals.size else 0
            return ds.isel({name: idx}, drop=True), depth_val
    return ds, None


def _normalize_dataset_coords(ds: xr.Dataset, spec: ProviderSpec) -> xr.Dataset:
    rename_map: dict[str, str] = {}
    if "latitude" not in ds.coords and "lat" in ds.coords:
        rename_map["lat"] = "latitude"
    if "longitude" not in ds.coords and "lon" in ds.coords:
        rename_map["lon"] = "longitude"
    out = ds.rename(rename_map) if rename_map else ds
    for vname in list(out.data_vars):
        vals = np.asarray(out[vname].values, dtype=float)
        if vname in spec.variables and not np.isfinite(vals).any():
            raise ValueError(f"{spec.provider_id} returned all-NaN/masked values for {vname}")
        units = str(out[vname].attrs.get("units") or "").lower()
        if ("kelvin" in units or units == "k") and "temperature" in spec.group:
            attrs = dict(out[vname].attrs)
            attrs["units"] = "degC"
            out[vname] = out[vname] - 273.15
            out[vname].attrs = attrs
    return out


def fetch_copernicus_subset(
    spec: ProviderSpec,
    req: dict[str, Any],
    *,
    copernicus_client: Any = None,
) -> dict[str, Any]:
    """Acquire bounded spatial/time/depth subset from Copernicus Marine."""
    client = copernicus_client
    if client is None:
        if not has_copernicus_credentials():
            raise RuntimeError(
                "Copernicus Marine credentials not configured; run `copernicusmarine login` first."
            )
        import copernicusmarine as client  # type: ignore[no-redef]
    bbox = req["bbox"]
    start_iso = datetime.fromtimestamp(req["start_ms"] / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    end_iso = datetime.fromtimestamp(req["end_ms"] / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    kwargs: dict[str, Any] = {
        "dataset_id": spec.dataset_id,
        "dataset_version": spec.dataset_version,
        "variables": list(req["variables"]),
        "minimum_longitude": float(bbox["lon_min"]),
        "maximum_longitude": float(bbox["lon_max"]),
        "minimum_latitude": float(bbox["lat_min"]),
        "maximum_latitude": float(bbox["lat_max"]),
        "start_datetime": start_iso,
        "end_datetime": end_iso,
        "coordinates_selection_method": "outside",
    }
    if spec.depth_m is not None:
        kwargs["minimum_depth"] = 0.0
        kwargs["maximum_depth"] = max(2.5, float(spec.depth_m) + 1.0)
    ds_raw = client.open_dataset(**kwargs)
    if ds_raw is None:
        raise RuntimeError(f"Copernicus Marine returned empty dataset handle for {spec.dataset_id}")
    ds_loaded = ds_raw.load()
    ds_sel, depth_m = _select_shallowest_depth(ds_loaded)
    ds_norm = _normalize_dataset_coords(ds_sel, spec)
    nbytes = int(ds_norm.nbytes)
    if nbytes > SPLIT_THRESHOLD_BYTES:
        raise SubsetTooLargeError(f"Copernicus subset {nbytes} bytes > {SPLIT_THRESHOLD_BYTES}")
    raw_bytes = _serialize_dataset_netcdf(ds_norm)
    meta_doc = {
        "dataset_id": spec.dataset_id,
        "dataset_version": spec.dataset_version,
        "attrs": dict(ds_norm.attrs),
        "var_attrs": {v: dict(ds_norm[v].attrs) for v in ds_norm.data_vars},
        "depth_m": depth_m if depth_m is not None else spec.depth_m,
        "spatial_support": _coord_spacing_metrics(ds_norm["latitude"].values, ds_norm["longitude"].values),
        "times": [str(t) for t in ds_norm["time"].values],
    }
    return {
        "format": "nc",
        "raw_bytes": raw_bytes,
        "raw_subset_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "metadata_sha256": _canonical_hash(meta_doc),
        "uncompressed_bytes": nbytes,
        "depth_m": meta_doc["depth_m"],
        "returned_coordinates": {
            "lat": [float(v) for v in ds_norm["latitude"].values],
            "lon": [float(v) for v in ds_norm["longitude"].values],
            "time_count": int(ds_norm["time"].size),
        },
        "spatial_support": meta_doc["spatial_support"],
        "initialization_time_utc": "unknown",
        "availability_time_utc": "unknown",
    }


def _parthenope_url(spec: ProviderSpec, dt: datetime) -> str:
    return spec.endpoint.format(
        YYYY=dt.strftime("%Y"),
        MM=dt.strftime("%m"),
        DD=dt.strftime("%d"),
        HH=dt.strftime("%H"),
    )


def _fetch_parthenope_coords(
    base_url: str,
    http_get: Callable[[str, float], tuple[int, bytes, dict[str, str]]],
    timeout: float,
) -> tuple[np.ndarray, np.ndarray, str | None]:
    code_dds, dds_bytes, _ = http_get(base_url + ".dds", timeout)
    if code_dds != 200:
        raise RuntimeError(f"Parthenope DDS HTTP {code_dds} for {base_url}")
    dds_txt = dds_bytes.decode("utf-8", errors="replace")
    depth_expr = "depth[0:1:2]," if "depth[depth" in dds_txt else ""
    coord_url = f"{base_url}.nc?{depth_expr}latitude,longitude"
    code_c, coord_bytes, _ = http_get(coord_url, timeout)
    if code_c != 200:
        raise RuntimeError(f"Parthenope coord HTTP {code_c} for {coord_url}")
    ds_c = _open_netcdf_bytes(coord_bytes)
    lats = np.asarray(ds_c["latitude"].values, dtype=float)
    lons = np.asarray(ds_c["longitude"].values, dtype=float)
    return lats, lons, (depth_expr or None)


def fetch_parthenope_subset(
    spec: ProviderSpec,
    req: dict[str, Any],
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Fetch bounded Parthenope d03 hourly NetCDF subsets over OPeNDAP."""
    getter = http_get or _default_http_get
    start_h = int(req["start_ms"] // 3_600_000) * 3_600_000
    end_h = int(math.ceil(req["end_ms"] / 3_600_000)) * 3_600_000
    bbox = req["bbox"]
    coord_cache: tuple[np.ndarray, np.ndarray, str | None] | None = None
    datasets: list[xr.Dataset] = []
    var_attr_meta: dict[str, Any] = {}
    hour_ms = start_h
    while hour_ms <= end_h:
        dt = datetime.fromtimestamp(hour_ms / 1000.0, tz=timezone.utc)
        url = _parthenope_url(spec, dt)
        if coord_cache is None:
            coord_cache = _fetch_parthenope_coords(url, getter, timeout)
        lats, lons, depth_expr = coord_cache
        if (
            bbox["lat_max"] < float(lats.min())
            or bbox["lat_min"] > float(lats.max())
            or bbox["lon_max"] < float(lons.min())
            or bbox["lon_min"] > float(lons.max())
        ):
            raise ValueError(f"Parthenope bbox {bbox} outside grid extent")
        i0 = max(0, int(np.searchsorted(lats, bbox["lat_min"], side="right")) - 1)
        i1 = min(lats.size - 1, int(np.searchsorted(lats, bbox["lat_max"], side="left")) + 1)
        j0 = max(0, int(np.searchsorted(lons, bbox["lon_min"], side="right")) - 1)
        j1 = min(lons.size - 1, int(np.searchsorted(lons, bbox["lon_max"], side="left")) + 1)
        vars_q = ",".join(f"{v}[0:1:0][{i0}:1:{i1}][{j0}:1:{j1}]" for v in req["variables"])
        depth_q = "depth[0:1:0]," if depth_expr else ""
        sub_url = f"{url}.nc?time[0:1:0],{depth_q}latitude[{i0}:1:{i1}],longitude[{j0}:1:{j1}],{vars_q}"
        code, nc_bytes, _ = getter(sub_url, timeout)
        if code != 200:
            raise RuntimeError(f"Parthenope subset HTTP {code} for {sub_url}")
        ds_h = _open_netcdf_bytes(nc_bytes).load()
        datasets.append(ds_h)
        if not var_attr_meta:
            var_attr_meta = {v: dict(ds_h[v].attrs) for v in ds_h.data_vars}
        hour_ms += 3_600_000

    combined = xr.concat(datasets, dim="time") if len(datasets) > 1 else datasets[0]
    ds_sel, depth_m = _select_shallowest_depth(combined)
    ds_norm = _normalize_dataset_coords(ds_sel, spec)
    if int(ds_norm.nbytes) > SPLIT_THRESHOLD_BYTES:
        raise SubsetTooLargeError(f"Parthenope subset {ds_norm.nbytes} > {SPLIT_THRESHOLD_BYTES}")
    raw_bytes = _serialize_dataset_netcdf(ds_norm)
    meta_doc = {
        "dataset_id": spec.dataset_id,
        "var_attrs": var_attr_meta,
        "depth_m": depth_m if depth_m is not None else spec.depth_m,
        "spatial_support": _coord_spacing_metrics(ds_norm["latitude"].values, ds_norm["longitude"].values),
        "times": [str(t) for t in ds_norm["time"].values],
    }
    return {
        "format": "nc",
        "raw_bytes": raw_bytes,
        "raw_subset_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "metadata_sha256": _canonical_hash(meta_doc),
        "uncompressed_bytes": int(ds_norm.nbytes),
        "depth_m": meta_doc["depth_m"],
        "returned_coordinates": {
            "lat": [float(v) for v in ds_norm["latitude"].values],
            "lon": [float(v) for v in ds_norm["longitude"].values],
            "time_count": int(ds_norm["time"].size),
        },
        "spatial_support": meta_doc["spatial_support"],
        "initialization_time_utc": "unknown",
        "availability_time_utc": "unknown",
    }


def fetch_hycom_subset(
    spec: ProviderSpec,
    req: dict[str, Any],
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, bytes, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Acquire surface depth=0 m HYCOM GOFS 3.1 subset via THREDDS NCSS."""
    getter = http_get or _default_http_get
    bbox = req["bbox"]
    pad_start = int(req["start_ms"]) - 3 * 3_600_000
    pad_end = int(req["end_ms"]) + 3 * 3_600_000
    params = {
        "var": ",".join(req["variables"]),
        "north": bbox["lat_max"],
        "south": bbox["lat_min"],
        "west": bbox["lon_min"],
        "east": bbox["lon_max"],
        "time_start": datetime.fromtimestamp(pad_start / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_end": datetime.fromtimestamp(pad_end / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vertCoord": 0.0,
        "accept": "netcdf",
    }
    url = f"{spec.endpoint}?{urlencode(params)}"
    code, nc_bytes, _ = getter(url, timeout)
    if code != 200:
        raise RuntimeError(f"HYCOM NCSS HTTP {code} for {url}")
    ds_raw = _open_netcdf_bytes(nc_bytes).load()
    ds_sel, depth_m = _select_shallowest_depth(ds_raw)
    ds_norm = _normalize_dataset_coords(ds_sel, spec)
    if int(ds_norm.nbytes) > SPLIT_THRESHOLD_BYTES:
        raise SubsetTooLargeError(f"HYCOM subset {ds_norm.nbytes} > {SPLIT_THRESHOLD_BYTES}")
    meta_doc = {
        "dataset_id": spec.dataset_id,
        "attrs": dict(ds_norm.attrs),
        "var_attrs": {v: dict(ds_norm[v].attrs) for v in ds_norm.data_vars},
        "depth_m": 0.0 if depth_m is None else depth_m,
        "spatial_support": _coord_spacing_metrics(ds_norm["latitude"].values, ds_norm["longitude"].values),
        "times": [str(t) for t in ds_norm["time"].values],
    }
    return {
        "format": "nc",
        "raw_bytes": nc_bytes,
        "raw_subset_sha256": hashlib.sha256(nc_bytes).hexdigest(),
        "metadata_sha256": _canonical_hash(meta_doc),
        "uncompressed_bytes": int(ds_norm.nbytes),
        "depth_m": meta_doc["depth_m"],
        "returned_coordinates": {
            "lat": [float(v) for v in ds_norm["latitude"].values],
            "lon": [float(v) for v in ds_norm["longitude"].values],
            "time_count": int(ds_norm["time"].size),
        },
        "spatial_support": meta_doc["spatial_support"],
        "initialization_time_utc": "unknown",
        "availability_time_utc": "unknown",
    }
