"""Nested whole-day tuning and fixed-cohort conditional-speed comparisons."""

import numpy as np

from .polar_surface import CONFIGS, SurfaceConfig, predict_prepared, prepare_surface
from .polar_table import ResearchTable, describe_cohort


def score_predictions(y: np.ndarray, predictions: np.ndarray) -> dict:
    valid = np.isfinite(y) & np.isfinite(predictions)
    if not np.any(valid):
        return {"sample_count": 0, "rmse_kt": None, "mae_kt": None, "bias_kt": None}
    error = y[valid] - predictions[valid]
    return {
        "sample_count": int(valid.sum()),
        "rmse_kt": round(float(np.sqrt(np.mean(error**2))), 4),
        "mae_kt": round(float(np.mean(np.abs(error))), 4),
        "bias_kt": round(float(np.mean(error)), 4),
    }


def day_folds(
    table: ResearchTable, chronological: bool
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    folds = []
    for day in np.unique(table.day):
        train = table.day < day if chronological else table.day != day
        if len(np.unique(table.day[train])) >= (3 if chronological else 2):
            folds.append((str(day), train, table.day == day))
    return folds


def _tune_configs(table: ResearchTable) -> tuple[dict[str, SurfaceConfig], dict]:
    losses: dict[str, list[float]] = {config.name: [] for config in CONFIGS}
    for _, train_mask, test_mask in day_folds(table, False):
        train, test = table.select(train_mask), table.select(test_mask)
        prepared = prepare_surface(train)
        predictions = [predict_prepared(prepared, test, config) for config in CONFIGS]
        common = np.logical_and.reduce([np.isfinite(pred) for pred in predictions])
        if not np.any(common):
            continue
        for config, prediction in zip(CONFIGS, predictions, strict=True):
            losses[config.name].append(float(np.mean((test.sog[common] - prediction[common]) ** 2)))
    selected = {}
    diagnostics = {}
    for method in ("kernel", "local_linear"):
        candidates = [config for config in CONFIGS if config.method == method]
        eligible = [config for config in candidates if losses[config.name]]
        choice = min(eligible, key=lambda c: np.mean(losses[c.name])) if eligible else candidates[1]
        selected[method] = choice
        diagnostics[method] = {
            "selected_config": choice.name,
            "inner_day_count": len(losses[choice.name]),
            "inner_day_equal_mse_kt2": (
                round(float(np.mean(losses[choice.name])), 5) if losses[choice.name] else None
            ),
            "selection_status": "nested_day_cv"
            if eligible
            else "fixed_default_insufficient_inner_days",
        }
    return selected, diagnostics


def evaluate_surfaces(table: ResearchTable, chronological: bool = False) -> dict:
    folds = []
    actual = []
    prediction_lists: dict[str, list[np.ndarray]] = {key: [] for key in ("kernel", "local_linear")}
    for day, train_mask, test_mask in day_folds(table, chronological):
        train, test = table.select(train_mask), table.select(test_mask)
        configs, tuning = _tune_configs(train)
        prepared = prepare_surface(train)
        predictions = {
            key: predict_prepared(prepared, test, config) for key, config in configs.items()
        }
        common = np.logical_and.reduce([np.isfinite(value) for value in predictions.values()])
        folds.append(
            {
                "day": day,
                "training_dates": np.unique(train.day).tolist(),
                "test_sample_count": test.size,
                "common_supported_count": int(common.sum()),
                "tuning": tuning,
                "models": {
                    key: score_predictions(test.sog[common], pred[common])
                    for key, pred in predictions.items()
                },
            }
        )
        actual.append(test.sog[common])
        for key, pred in predictions.items():
            prediction_lists[key].append(pred[common])
    y = np.concatenate(actual) if actual else np.array([])
    return {
        "status": "evaluated" if folds else "insufficient_days",
        "split": "expanding_chronological_days" if chronological else "leave_one_day_out",
        "target": "individual accepted 1 Hz SOG in knots",
        "cohort": describe_cohort(table),
        "folds": folds,
        "sample_weighted": {
            key: score_predictions(y, np.concatenate(values) if values else np.array([]))
            for key, values in prediction_lists.items()
        },
        "day_equal": day_equal_scores(folds),
        "paired_local_linear_minus_kernel_rmse": paired_day_difference(
            folds, "kernel", "local_linear"
        ),
        "scope": "conditional speed given contemporaneous wind/angle; not a future-motion forecast",
    }


def day_equal_scores(folds: list[dict]) -> dict:
    output = {}
    for method in folds[0]["models"] if folds else ():
        metrics = [
            fold["models"][method] for fold in folds if fold["models"][method]["sample_count"]
        ]
        output[method] = {
            "days": len(metrics),
            "mean_rmse_kt": round(float(np.mean([item["rmse_kt"] for item in metrics])), 4)
            if metrics
            else None,
            "mean_mae_kt": round(float(np.mean([item["mae_kt"] for item in metrics])), 4)
            if metrics
            else None,
        }
    return output


def paired_day_difference(folds: list[dict], baseline: str, candidate: str) -> dict:
    deltas = [
        fold["models"][candidate]["rmse_kt"] - fold["models"][baseline]["rmse_kt"]
        for fold in folds
        if fold["models"][candidate]["rmse_kt"] is not None
        and fold["models"][baseline]["rmse_kt"] is not None
    ]
    if not deltas:
        return {"mean_delta_kt": None, "day_count": 0, "interval_95": None}
    values = np.asarray(deltas)
    rng = np.random.default_rng(20261119)
    draws = values[rng.integers(0, len(values), size=(1000, len(values)))].mean(axis=1)
    interval = np.quantile(draws, [0.025, 0.975]).tolist() if len(values) >= 3 else None
    return {
        "mean_delta_kt": round(float(values.mean()), 4),
        "day_count": len(values),
        "interval_95": [round(float(value), 4) for value in interval] if interval else None,
        "interval_scope": "paired observed-day bootstrap sensitivity; few-day precision is limited",
    }
