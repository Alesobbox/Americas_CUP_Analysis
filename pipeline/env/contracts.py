"""Metric definitions, vector conventions, provenance contracts, and environment-1/2 readers."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

ENVIRONMENT_SCHEMA_V1 = "environment-1"
ENVIRONMENT_SCHEMA_V2 = "environment-2"

SLACK_CURRENT_SPEED_MPS = 0.01
CALM_WAVE_HS_THRESHOLD_M = 0.05

CANONICAL_CHANNELS = ("currents", "waves", "air_temperature", "water_temperature")
VALID_PRODUCT_CLASSES = frozenset({
    "retrospective_reanalysis",
    "archived_forecast",
    "climatological_scenario",
})
VALID_QUALITY_STATUSES = frozenset({
    "available",
    "partial",
    "fallback",
    "unavailable",
    "excluded",
})

CANONICAL_QUANTITY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "current_u_mps": {"unit": "m/s", "definition": "Geographic eastward surface water velocity."},
    "current_v_mps": {"unit": "m/s", "definition": "Geographic northward surface water velocity."},
    "current_speed_mps": {"unit": "m/s", "definition": "Derived magnitude sqrt(u^2 + v^2)."},
    "current_dir_towards_deg": {
        "unit": "deg",
        "definition": "Current flow towards bearing clockwise from true north; null under slack threshold.",
    },
    "wave_height_m": {"unit": "m", "definition": "Significant wave height Hs (spectral moment m0)."},
    "wave_period_s": {
        "unit": "s",
        "definition": "Energy wave period Tm-1,0; null below calm Hs threshold.",
    },
    "wave_dir_from_deg": {
        "unit": "deg",
        "definition": "Mean wave direction coming FROM clockwise from true north; null below calm Hs threshold.",
    },
    "air_temperature_c": {"unit": "degC", "definition": "Air temperature at 2 m above surface."},
    "water_temperature_c": {
        "unit": "degC",
        "definition": "Near-surface modeled water temperature with channel-specific depth_m and convention.",
    },
}


def wrap_deg(angle_deg: float) -> float:
    """Wrap angle in degrees to [0, 360)."""
    return float(angle_deg % 360.0)


def kelvin_to_celsius(temp_k: float) -> float:
    """Convert Kelvin temperature to Celsius."""
    return float(temp_k - 273.15)


def uv_to_speed_dir_towards(
    u_mps: float | None,
    v_mps: float | None,
    *,
    slack_threshold_mps: float = SLACK_CURRENT_SPEED_MPS,
) -> tuple[float | None, float | None]:
    """Derive current speed (m/s) and towards-bearing (deg clockwise from north) in Python."""
    if u_mps is None or v_mps is None or not (math.isfinite(u_mps) and math.isfinite(v_mps)):
        return None, None
    speed = math.hypot(u_mps, v_mps)
    if speed < slack_threshold_mps:
        return speed, None
    bearing = wrap_deg(math.degrees(math.atan2(u_mps, v_mps)))
    return speed, bearing


def speed_dir_towards_to_uv(speed_mps: float, dir_towards_deg: float) -> tuple[float, float]:
    """Convert speed (m/s) and towards-bearing (deg clockwise from north) to east/north (u, v)."""
    rad = math.radians(dir_towards_deg)
    return float(speed_mps * math.sin(rad)), float(speed_mps * math.cos(rad))


def bearing_from_to_towards_deg(dir_from_deg: float | None) -> float | None:
    """Convert meteorological/wave FROM bearing into TOWARDS vector bearing."""
    if dir_from_deg is None or not math.isfinite(dir_from_deg):
        return None
    return wrap_deg(dir_from_deg + 180.0)


def angular_diff_deg(a_deg: float, b_deg: float) -> float:
    """Signed shortest angular difference (a - b) in (-180, 180]."""
    return ((a_deg - b_deg + 180.0) % 360.0) - 180.0


def build_channel_provenance(
    *,
    channel: str,
    provider: str,
    provider_id: str,
    dataset: str,
    dataset_version: str,
    variables: list[str],
    native_spatial_support: Mapping[str, Any],
    native_temporal_support: str,
    averaging_bounds: Mapping[str, Any],
    depth_m: float | None,
    temperature_convention: str | None,
    units: Mapping[str, str],
    mask_handling: str,
    interpolation: str,
    quality_status: str,
    request_spec: Mapping[str, Any],
    returned_coordinates: Mapping[str, Any],
    retrieval_time_utc: str,
    raw_subset_sha256: str,
    metadata_sha256: str,
    valid_time_bounds: Mapping[str, Any],
    initialization_time_utc: str = "unknown",
    availability_time_utc: str = "unknown",
    product_classification: str = "retrospective_reanalysis",
    missing_count: int = 0,
    total_count: int = 0,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    distance_to_wet_cell_m: Mapping[str, float | None] | float | None = None,
) -> dict[str, Any]:
    """Construct one validated channel provenance record."""
    if channel not in CANONICAL_CHANNELS:
        raise ValueError(f"Unsupported channel '{channel}'")
    if quality_status not in VALID_QUALITY_STATUSES:
        raise ValueError(f"Invalid quality_status '{quality_status}'")
    if product_classification not in VALID_PRODUCT_CLASSES:
        raise ValueError(f"Invalid product_classification '{product_classification}'")
    return {
        "channel": channel,
        "provider": provider,
        "provider_id": provider_id,
        "dataset": dataset,
        "dataset_version": dataset_version,
        "variables": list(variables),
        "native_spatial_support": dict(native_spatial_support),
        "native_temporal_support": native_temporal_support,
        "averaging_bounds": dict(averaging_bounds),
        "depth_m": depth_m,
        "temperature_convention": temperature_convention,
        "units": dict(units),
        "mask_handling": mask_handling,
        "interpolation": interpolation,
        "quality_status": quality_status,
        "request_spec": dict(request_spec),
        "returned_coordinates": dict(returned_coordinates),
        "retrieval_time_utc": retrieval_time_utc,
        "raw_subset_sha256": raw_subset_sha256,
        "metadata_sha256": metadata_sha256,
        "valid_time_bounds": dict(valid_time_bounds),
        "initialization_time_utc": initialization_time_utc or "unknown",
        "availability_time_utc": availability_time_utc or "unknown",
        "product_classification": product_classification,
        "missingness": {"missing_count": int(missing_count), "total_count": int(total_count)},
        "fallback_used": bool(fallback_used),
        "fallback_reason": fallback_reason,
        "distance_to_wet_cell_m": distance_to_wet_cell_m,
    }


def _validate_channel_record(name: str, ch: Mapping[str, Any]) -> None:
    required = (
        "provider", "provider_id", "dataset", "dataset_version", "variables",
        "native_spatial_support", "native_temporal_support", "averaging_bounds",
        "depth_m", "temperature_convention", "units", "mask_handling",
        "interpolation", "quality_status", "request_spec", "returned_coordinates",
        "retrieval_time_utc", "raw_subset_sha256", "metadata_sha256",
        "valid_time_bounds", "initialization_time_utc", "availability_time_utc",
        "product_classification", "missingness", "fallback_used", "fallback_reason",
        "distance_to_wet_cell_m",
    )
    missing = [key for key in required if key not in ch]
    if missing:
        raise ValueError(f"Channel '{name}' missing required provenance keys: {missing}")
    if ch["quality_status"] not in VALID_QUALITY_STATUSES:
        raise ValueError(f"Channel '{name}' invalid quality_status: {ch['quality_status']}")
    if ch["product_classification"] not in VALID_PRODUCT_CLASSES:
        raise ValueError(f"Channel '{name}' invalid product_classification: {ch['product_classification']}")


def _validate_series_values(series: Mapping[str, Any], length: int, label: str) -> None:
    numeric_fields = (
        "current_u_mps", "current_v_mps", "current_speed_mps", "current_dir_towards_deg",
        "wave_height_m", "wave_period_s", "wave_dir_from_deg",
        "air_temperature_c", "water_temperature_c",
    )
    for field in numeric_fields:
        vals = series.get(field)
        if not isinstance(vals, list) or len(vals) != length:
            raise ValueError(f"Series '{label}.{field}' must match time_ms length {length}")
        for val in vals:
            if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val)):
                raise ValueError(f"Series '{label}.{field}' contains non-finite value: {val!r}")
    for idx in range(length):
        hs = series["wave_height_m"][idx]
        if hs is not None and hs < CALM_WAVE_HS_THRESHOLD_M:
            if series["wave_period_s"][idx] is not None or series["wave_dir_from_deg"][idx] is not None:
                raise ValueError(f"Series '{label}' must null wave period/dir when Hs < {CALM_WAVE_HS_THRESHOLD_M}")
        spd = series["current_speed_mps"][idx]
        if spd is not None and spd < SLACK_CURRENT_SPEED_MPS:
            if series["current_dir_towards_deg"][idx] is not None:
                raise ValueError(f"Series '{label}' must null current bearing when speed < {SLACK_CURRENT_SPEED_MPS}")


def validate_environment_v2(doc: Mapping[str, Any]) -> bool:
    """Validate an environment-2 payload strictly."""
    if not isinstance(doc, Mapping):
        raise ValueError("Environment artifact must be a JSON object")
    if doc.get("schema_version") != ENVIRONMENT_SCHEMA_V2:
        raise ValueError(f"Unsupported schema_version: {doc.get('schema_version')!r}")
    for key in ("race_id", "context", "registry_version", "location", "window", "channels", "course_centre"):
        if key not in doc:
            raise ValueError(f"Environment-2 artifact missing '{key}'")
    channels = doc["channels"]
    if not isinstance(channels, Mapping) or set(channels.keys()) != set(CANONICAL_CHANNELS):
        raise ValueError("Environment-2 channels must define all four canonical channels")
    for ch_name, ch_doc in channels.items():
        if not isinstance(ch_doc, Mapping):
            raise ValueError(f"Channel '{ch_name}' must be an object")
        _validate_channel_record(ch_name, ch_doc)
    centre = doc["course_centre"]
    if not isinstance(centre, Mapping) or not isinstance(centre.get("time_ms"), list):
        raise ValueError("Environment-2 course_centre must contain time_ms array")
    _validate_series_values(centre, len(centre["time_ms"]), "course_centre")
    return True


def _upgrade_v1_to_common(doc: Mapping[str, Any]) -> dict[str, Any]:
    hourly = doc.get("hourly")
    hourly_map = hourly if isinstance(hourly, Mapping) else {}
    times = list(hourly_map.get("time_ms") or [])
    empty = [None] * len(times)
    air = list(hourly_map.get("air_temperature_c") or empty)
    wave_h = list(hourly_map.get("wave_height_m") or empty)
    water = list(hourly_map.get("water_temperature_c") or empty)
    return {
        "schema_version": ENVIRONMENT_SCHEMA_V1,
        "native_schema_version": ENVIRONMENT_SCHEMA_V1,
        "race_id": doc.get("race_id"),
        "context": doc.get("context", "historical_replay_only"),
        "location": doc.get("location"),
        "window": doc.get("window"),
        "channels": {},
        "course_centre": {
            "time_ms": times,
            "current_u_mps": list(empty),
            "current_v_mps": list(empty),
            "current_speed_mps": list(empty),
            "current_dir_towards_deg": list(empty),
            "wave_height_m": wave_h,
            "wave_period_s": list(empty),
            "wave_dir_from_deg": list(empty),
            "air_temperature_c": air,
            "water_temperature_c": water,
        },
        "legacy_v1_sources": doc.get("sources"),
        "errors": doc.get("errors"),
    }


def read_environment_artifact(source: Path | str | Mapping[str, Any]) -> dict[str, Any]:
    """Read either environment-2 or legacy environment-1 into a normalized dict."""
    if isinstance(source, (Path, str)):
        doc = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        doc = dict(source)
    schema = doc.get("schema_version")
    if schema == ENVIRONMENT_SCHEMA_V2:
        validate_environment_v2(doc)
        normalized = dict(doc)
        normalized["native_schema_version"] = ENVIRONMENT_SCHEMA_V2
        return normalized
    if schema == ENVIRONMENT_SCHEMA_V1:
        return _upgrade_v1_to_common(doc)
    raise ValueError(f"Unsupported environment schema version: {schema!r}")
