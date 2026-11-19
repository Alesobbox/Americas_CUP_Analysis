"""Small wind-increment models and empirical circular predictive distributions."""

import math

import numpy as np

from pipeline.research.wind_forecast_data import SHIFT_DEG, prior_training_rows, wrapped

MODEL_IDS = ("event_climatology", "probabilistic_persistence", "local_angle_ar")
RIDGE_GRID = (1.0, 10.0, 100.0)


def fit_ar(rows, ridge):
    features = np.asarray([row["features"] for row in rows], dtype=float)
    targets = np.asarray([row["target_delta_deg"] for row in rows], dtype=float)
    center = features.mean(axis=0)
    scale = np.maximum(features.std(axis=0), 1.0)
    design = np.column_stack([np.ones(len(rows)), (features - center) / scale])
    days, inverse, counts = np.unique(
        [row["date"] for row in rows], return_inverse=True, return_counts=True
    )
    weights = 1.0 / counts[inverse]
    weights *= len(rows) / len(days)
    penalty = np.diag([0.0, ridge, ridge, ridge, ridge])
    coefficients = np.linalg.solve(
        design.T @ (weights[:, None] * design) + penalty, design.T @ (weights * targets)
    )
    return {"center": center, "scale": scale, "coefficients": coefficients, "ridge": ridge}


def predict_ar(model, rows):
    features = np.asarray([row["features"] for row in rows], dtype=float)
    design = np.column_stack([np.ones(len(rows)), (features - model["center"]) / model["scale"]])
    return wrapped(design @ model["coefficients"])


def chronological_residuals(rows, ridge):
    """Prequential residuals, with every residual predicted using earlier days."""
    residuals, scores = [], []
    days = sorted({row["date"] for row in rows})
    for day in days[1:]:
        test = [row for row in rows if row["date"] == day]
        train = prior_training_rows(rows, day, min(row["issue_ms"] for row in test))
        if len(train) < 10 or not test:
            continue
        prediction = predict_ar(fit_ar(train, ridge), test)
        actual = np.asarray([row["target_delta_deg"] for row in test])
        errors = wrapped(actual - prediction)
        residuals.extend(errors.tolist())
        scores.append(float(np.mean(np.abs(errors))))
    return residuals, scores


def select_ar(rows):
    """Tune solely on prior-day angular errors; no current-day labels are used."""
    candidates = []
    for ridge in RIDGE_GRID:
        residuals, scores = chronological_residuals(rows, ridge)
        mean_score = float(np.mean(scores)) if scores else None
        candidates.append(
            {
                "ridge": ridge,
                "mean_day_angular_mae_deg": mean_score,
                "inner_days": len(scores),
                "residuals": residuals,
            }
        )
    eligible = [item for item in candidates if item["inner_days"] >= 2]
    selected = (
        min(eligible, key=lambda item: item["mean_day_angular_mae_deg"])
        if eligible
        else candidates[1]
    )
    model = fit_ar(rows, selected["ridge"])
    model["residuals"] = selected["residuals"]
    diagnostics = [
        {key: value for key, value in item.items() if key != "residuals"} for item in candidates
    ]
    return model, {
        "selected_ridge": selected["ridge"],
        "inner_candidates": diagnostics,
        "tuning_status": "past_day_tuned" if eligible else "insufficient_inner_days_default_ridge",
    }


def empirical_offsets(values):
    return np.asarray(values, dtype=float)


def circular_pair_mean(values):
    """Exact mean pairwise circular distance without a quadratic matrix."""
    ordered = np.sort(np.asarray(values) % 360.0)
    size = len(ordered)
    raw_sum = 2 * np.sum(ordered * (2 * np.arange(size) - size + 1))
    tails = np.concatenate([np.cumsum(ordered[::-1])[::-1], [0.0]])
    boundaries = np.searchsorted(ordered, ordered + 180.0, side="right")
    counts = size - boundaries
    correction = 2 * (tails[boundaries] - counts * ordered) - 360 * counts
    return float((raw_sum - 2 * correction.sum()) / (size * size))


def fit_models(rows):
    increments = [row["target_delta_deg"] for row in rows]
    ar, tuning = select_ar(rows)
    residuals = ar["residuals"]
    symmetric = increments + [-value for value in increments]
    residual_source = residuals if len(residuals) >= 20 else symmetric
    offsets = {
        "event_climatology": empirical_offsets(increments),
        "probabilistic_persistence": empirical_offsets(symmetric),
        "local_angle_ar": empirical_offsets(residual_source),
    }
    return {
        "ar": ar,
        "offsets": offsets,
        "pair_distances": {key: circular_pair_mean(value) for key, value in offsets.items()},
        "uniform_weight": 1.0 / (len(rows) + 1.0),
        "tuning": tuning,
        "ar_residual_source": "past_day_forecast_errors"
        if len(residuals) >= 20
        else "symmetric_persistence_until_20_past_errors",
    }


def _distribution(offsets, center, uniform_weight):
    empirical = wrapped(offsets + center)
    uniform = np.arange(-180.0, 180.0, 10.0)
    points = np.concatenate([empirical, uniform])
    weights = np.concatenate(
        [
            np.full(len(empirical), (1 - uniform_weight) / len(empirical)),
            np.full(len(uniform), uniform_weight / len(uniform)),
        ]
    )
    return points, weights


def distribution_prediction(model, model_id, row):
    """Return event probability, wrapped ensemble, and its angular anchor."""
    center = float(predict_ar(model["ar"], [row])[0]) if model_id == "local_angle_ar" else 0.0
    points, weights = _distribution(model["offsets"][model_id], center, model["uniform_weight"])
    probability = float(weights[np.abs(points) >= SHIFT_DEG].sum())
    empirical = wrapped(model["offsets"][model_id] + center)
    uniform = np.arange(-180.0, 180.0, 10.0)
    mixture = model["uniform_weight"]
    cross_mean = float(np.abs(wrapped(empirical[:, None] - uniform[None, :])).mean())
    pair_mean = (
        (1 - mixture) ** 2 * model["pair_distances"][model_id]
        + 2 * mixture * (1 - mixture) * cross_mean
        + mixture**2 * circular_pair_mean(uniform)
    )
    return {
        "probability": probability,
        "points": points,
        "weights": weights,
        "pair_distance_expectation": pair_mean,
        "center_twd_deg": float((row["current_deg"] + center) % 360.0),
    }


def score_prediction(prediction, target):
    probability = prediction["probability"]
    event = float(abs(target) >= SHIFT_DEG)
    safe_probability = min(max(probability, 1e-12), 1 - 1e-12)
    points, weights = prediction["points"], prediction["weights"]
    distance = np.abs(wrapped(points - target))
    crps = float(weights @ distance - 0.5 * prediction["pair_distance_expectation"])
    return {
        "brier": (probability - event) ** 2,
        "log_loss": -event * math.log(safe_probability)
        - (1 - event) * math.log(1 - safe_probability),
        "circular_crps_deg": crps,
    }


def distribution_templates(model):
    return {
        model_id: {
            "family": "wrapped_empirical_with_uniform_mixture",
            "residual_offsets_deg": np.round(model["offsets"][model_id], 5).tolist(),
            "uniform_weight": model["uniform_weight"],
            "uniform_offsets_deg": list(range(-180, 180, 10)),
        }
        for model_id in MODEL_IDS
    }
