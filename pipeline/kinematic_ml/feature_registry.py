"""Feature contracts, schema pinning, and causal encoding for AC75 kinematic models.

Pins:
- `ac75-model-1`: legacy 14 inputs (8 continuous kinematic + 6 canonical team indicators).
- `ac75-model-2`: 21 inputs (8 continuous kinematic + 7 environmental predictors + 6 canonical team indicators).

Core Invariants:
- Ground-speed target `sog_mps` is strictly preserved. Surface current velocity is NEVER added
  to an existing SOG prediction or target. Current and waves act as learned covariate predictors.
- Evaluation holdouts: 2024-09-29..10-04 final window + Sep 28 abandoned race `ac37_lvc_final_r3`
  are strictly untouched and frozen.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

AC75_MODEL_SCHEMA_V1 = "ac75-model-1"
AC75_MODEL_SCHEMA_V2 = "ac75-model-2"
SUPPORTED_MODEL_SCHEMAS = frozenset({AC75_MODEL_SCHEMA_V1, AC75_MODEL_SCHEMA_V2})

CANONICAL_TEAMS = (
    "ac37:ETNZ",
    "ac37:INEOS",
    "ac37:LUNA_ROSSA",
    "ac37:AMERICAN_MAGIC",
    "ac37:ALINGHI",
    "ac37:ORIENT_EXPRESS",
)

BASE_CONTINUOUS_FEATURES: list[str] = [
    "tws_mps",
    "twa_sin",
    "twa_cos",
    "tack_side",
    "leg_type",
    "heading_cog_offset_deg",
    "course_wind_angle_deg",
    "practice_domain",
]

ENV_CONTINUOUS_FEATURES: list[str] = [
    "current_speed_mps",
    "current_dir_towards_deg",
    "wave_height_m",
    "wave_period_s",
    "wave_dir_from_deg",
    "air_temperature_c",
    "water_temperature_c",
]

DEFAULT_ENV_NEUTRAL_VALUES: dict[str, float] = {
    "current_speed_mps": 0.0,
    "current_dir_towards_deg": 0.0,
    "wave_height_m": 0.0,
    "wave_period_s": 0.0,
    "wave_dir_from_deg": 0.0,
    "air_temperature_c": 22.0,
    "water_temperature_c": 20.0,
}


def get_feature_dimension(schema_version: str) -> int:
    """Return total feature vector dimension (continuous + one-hot team indicators)."""
    if schema_version == AC75_MODEL_SCHEMA_V1:
        return len(BASE_CONTINUOUS_FEATURES) + len(CANONICAL_TEAMS)
    if schema_version == AC75_MODEL_SCHEMA_V2:
        return len(BASE_CONTINUOUS_FEATURES) + len(ENV_CONTINUOUS_FEATURES) + len(CANONICAL_TEAMS)
    raise ValueError(f"Unsupported schema_version '{schema_version}'. Supported: {sorted(SUPPORTED_MODEL_SCHEMAS)}")


def get_continuous_features(schema_version: str) -> list[str]:
    """Return ordered list of continuous feature names."""
    if schema_version == AC75_MODEL_SCHEMA_V1:
        return list(BASE_CONTINUOUS_FEATURES)
    if schema_version == AC75_MODEL_SCHEMA_V2:
        return BASE_CONTINUOUS_FEATURES + ENV_CONTINUOUS_FEATURES
    raise ValueError(f"Unsupported schema_version '{schema_version}'")


def encode_features_matrix(
    rows: Sequence[Mapping[str, Any]],
    schema_version: str = AC75_MODEL_SCHEMA_V1,
    scaler_mean: np.ndarray | None = None,
    scaler_scale: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Encode input feature rows into a float32 array adhering strictly to schema_version.

    Returns (X, scaler_mean, scaler_scale).
    """
    if schema_version not in SUPPORTED_MODEL_SCHEMAS:
        raise ValueError(f"Unsupported schema_version: {schema_version}")

    n = len(rows)
    cont_names = get_continuous_features(schema_version)
    k_cont = len(cont_names)
    k_teams = len(CANONICAL_TEAMS)
    total_dim = k_cont + k_teams

    X = np.zeros((n, total_dim), dtype=np.float32)

    for i, r in enumerate(rows):
        for j, feat_name in enumerate(cont_names):
            val = r.get(feat_name)
            if val is None or not (isinstance(val, (int, float)) and math.isfinite(val)):
                val = DEFAULT_ENV_NEUTRAL_VALUES.get(feat_name, 0.0)
            X[i, j] = float(val)

        tid = str(r.get("team_id", ""))
        for t_idx, team in enumerate(CANONICAL_TEAMS):
            if tid == team or tid == team.removeprefix("ac37:"):
                X[i, k_cont + t_idx] = 1.0
                break

    if scaler_mean is None or scaler_scale is None:
        if n > 0:
            scaler_mean = np.mean(X[:, :k_cont], axis=0)
            scaler_scale = np.std(X[:, :k_cont], axis=0)
            scaler_scale[scaler_scale < 1e-4] = 1.0
        else:
            scaler_mean = np.zeros(k_cont, dtype=np.float32)
            scaler_scale = np.ones(k_cont, dtype=np.float32)

    X[:, :k_cont] = (X[:, :k_cont] - scaler_mean) / scaler_scale
    return X, scaler_mean, scaler_scale


def validate_ground_speed_target(target_name: str, values: np.ndarray) -> None:
    """Invariant check: SOG is strictly ground speed; current velocity must never be added to it."""
    if target_name != "sog_mps":
        raise ValueError(f"Ground-speed target must be 'sog_mps', got '{target_name}'")
    if np.any(values < 0):
        raise ValueError("Ground speed target sog_mps contains negative values")
