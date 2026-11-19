"""Fixed-cohort feature ablations with train-only normalization."""

import numpy as np

from .polar_evaluation import day_equal_scores, day_folds, paired_day_difference, score_predictions
from .polar_surface import ridge_predict
from .polar_table import ResearchTable, describe_cohort


def compare_features(
    table: ResearchTable, features: dict[str, np.ndarray], chronological: bool = False
) -> dict:
    complete = np.logical_and.reduce(
        [np.all(np.isfinite(value), axis=1) for value in features.values()]
    )
    cohort = table.select(complete)
    design = {name: values[complete] for name, values in features.items()}
    folds = []
    targets = []
    predictions: dict[str, list[np.ndarray]] = {name: [] for name in features}
    for day, train, test in day_folds(cohort, chronological):
        models = {}
        targets.append(cohort.sog[test])
        for name, values in design.items():
            prediction = ridge_predict(values[train], cohort.sog[train], values[test])
            predictions[name].append(prediction)
            models[name] = score_predictions(cohort.sog[test], prediction)
        folds.append(
            {"day": day, "training_dates": np.unique(cohort.day[train]).tolist(), "models": models}
        )
    actual = np.concatenate(targets) if targets else np.array([])
    baseline = next(iter(features))
    return {
        "status": "evaluated" if folds else "insufficient_common_days",
        "split": "expanding_chronological_days" if chronological else "leave_one_day_out",
        "source_sample_count": table.size,
        "cohort": describe_cohort(cohort),
        "missing_or_unmatched_count": int(table.size - cohort.size),
        "folds": folds,
        "day_equal": day_equal_scores(folds),
        "sample_weighted": {
            name: score_predictions(actual, np.concatenate(values) if values else np.array([]))
            for name, values in predictions.items()
        },
        "paired_day_differences": {
            name: paired_day_difference(folds, baseline, name)
            for name in features
            if name != baseline
        },
        "model": "predeclared quadratic mode-interacted ridge; penalty 1; training-only scaling",
        "comparison_cohort": "identical complete test and training rows for every candidate",
    }
