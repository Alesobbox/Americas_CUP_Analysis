"""Retrospective model-environment ablations on identical sample cohorts."""

import json
from pathlib import Path

import numpy as np

from .feature_evaluation import compare_features
from .polar_surface import ridge_features
from .polar_table import ResearchTable

KNOT_MPS = 1852.0 / 3600.0
CHANNELS = (
    "current_u_mps",
    "current_v_mps",
    "wave_height_m",
    "wave_period_s",
    "wave_dir_from_deg",
    "air_temperature_c",
    "water_temperature_c",
)


def join_environment(table: ResearchTable, data_dir: Path) -> dict[str, np.ndarray]:
    channels = {name: np.full(table.size, np.nan) for name in CHANNELS}
    for race_id in np.unique(table.race):
        path = data_dir / "environment" / "boats" / f"{race_id}.json"
        if not path.is_file():
            continue
        boats = json.loads(path.read_text(encoding="utf-8")).get("boats", {})
        for boat, values in boats.items():
            mask = (table.race == race_id) & (table.boat == boat)
            if np.any(mask):
                _assign_channels(table.timestamp[mask], values, mask, channels)
    return channels


def _assign_channels(times: np.ndarray, values: dict, mask: np.ndarray, channels: dict) -> None:
    source_times = np.asarray(values.get("time_ms", []))
    if source_times.size == 0:
        return
    indexes = np.flatnonzero(mask)
    right = np.clip(np.searchsorted(source_times, times), 0, len(source_times) - 1)
    left = np.maximum(right - 1, 0)
    nearest = np.where(
        abs(source_times[left] - times) < abs(source_times[right] - times), left, right
    )
    valid = abs(source_times[nearest] - times) <= 500
    for channel, result in channels.items():
        series = values.get(channel, [])
        if len(series) == len(source_times):
            numeric = np.asarray(
                [np.nan if value is None else value for value in series], dtype=float
            )
            result[indexes[valid]] = numeric[nearest[valid]]


def current_vectors(table: ResearchTable, channels: dict) -> dict[str, np.ndarray]:
    bearing = np.deg2rad(table.cog)
    east, north = channels["current_u_mps"] / KNOT_MPS, channels["current_v_mps"] / KNOT_MPS
    along = east * np.sin(bearing) + north * np.cos(bearing)
    cross = east * np.cos(bearing) - north * np.sin(bearing)
    water_east = table.sog * np.sin(bearing) - east
    water_north = table.sog * np.cos(bearing) - north
    water_speed = np.hypot(water_east, water_north)
    wind = np.deg2rad(table.twd)
    water_vmg = (water_east * np.sin(wind) + water_north * np.cos(wind)) * np.where(
        table.mode == 1, 1, -1
    )
    return {
        "along_kt": along,
        "cross_kt": cross,
        "model_adjusted_stw_kt": water_speed,
        "model_adjusted_wind_vmg_kt": water_vmg,
    }


def _feature_blocks(table: ResearchTable, channels: dict) -> dict[str, np.ndarray]:
    current = current_vectors(table, channels)
    height = channels["wave_height_m"]
    calm = np.isfinite(height) & (height < 0.05)
    period = np.where(calm, 0.0, channels["wave_period_s"])
    encounter = np.deg2rad(table.cog - channels["wave_dir_from_deg"])
    cosine = np.where(calm, 0.0, height * np.cos(encounter))
    sine = np.where(calm, 0.0, height * np.sin(encounter))
    return {
        "currents": np.column_stack([current["along_kt"], current["cross_kt"]]),
        "waves": np.column_stack([height, period, cosine, sine]),
        "temperatures": np.column_stack(
            [
                channels["air_temperature_c"],
                channels["air_temperature_c"] - channels["water_temperature_c"],
            ]
        ),
    }


def _sensitivity(table: ResearchTable, channels: dict) -> dict:
    corrected = current_vectors(table, channels)["model_adjusted_stw_kt"]
    valid = np.isfinite(corrected)
    difference = corrected[valid] - table.sog[valid]
    return {
        "sample_count": int(valid.sum()),
        "mean_stw_minus_sog_kt": round(float(difference.mean()), 5) if difference.size else None,
        "p05_p95_stw_minus_sog_kt": np.quantile(difference, [0.05, 0.95]).round(5).tolist()
        if difference.size
        else None,
        "formula": "norm(SOG*(sin(COG),cos(COG)) - (current_u,current_v)/KNOT_MPS)",
        "interpretation": "coarse-grid model-adjusted sensitivity, not measured water speed",
    }


def run_environment_ablation(table: ResearchTable, data_dir: Path) -> dict:
    channels = join_environment(table, data_dir)
    baseline = ridge_features(table)
    blocks = _feature_blocks(table, channels)
    comparisons = {}
    for name, features in blocks.items():
        candidates = {
            "baseline": baseline,
            f"baseline_plus_{name}": np.column_stack([baseline, features]),
        }
        comparisons[name] = {
            "leave_one_day_out": compare_features(table, candidates),
            "chronological": compare_features(table, candidates, True),
        }
    return {
        "feature_blocks": comparisons,
        "coverage": _coverage(table, channels),
        "current_adjusted_speed_sensitivity": _sensitivity(table, channels),
        "wave_period_definition": "energy period Tm-1,0, not peak period Tp",
        "calm_wave_rule": "Hs<0.05m: period and directional contributions set to zero; absent Hs remains absent",
        "thermal_definition": "air temperature and air minus near-surface modeled water temperature; not air density",
        "scope": "retrospective conditional-performance ablation; historical model availability is unverified",
        "interpretation": "No gain means these covariates did not help this benchmark; it does not rule out physical effects.",
    }


def _coverage(table: ResearchTable, channels: dict) -> list[dict]:
    rows = []
    for race_id in np.unique(table.race):
        mask = table.race == race_id
        rows.append(
            {
                "race_id": str(race_id),
                "sample_count": int(mask.sum()),
                "available_counts": {
                    name: int(np.isfinite(values[mask]).sum()) for name, values in channels.items()
                },
            }
        )
    return rows
