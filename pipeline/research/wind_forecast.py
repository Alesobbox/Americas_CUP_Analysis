"""Chronological AC38 official-wind endpoint forecast benchmark."""

from collections import defaultdict

import numpy as np

from pipeline.research.wind_forecast_data import (
    CADENCE_MS,
    FEATURE_NAMES,
    HISTORY_MS,
    HORIZON_MS,
    MAX_AGE_MS,
    SHIFT_DEG,
    build_contexts,
    prior_training_rows,
    source_count,
)
from pipeline.research.wind_forecast_models import (
    MODEL_IDS,
    distribution_prediction,
    distribution_templates,
    fit_models,
    score_prediction,
)

SCHEMA_VERSION = "1.0"
METHOD_VERSION = "wind-forecast-1"
SCORE_NAMES = ("brier", "log_loss", "circular_crps_deg")
AVAILABILITY = (
    "Retrospective measurement-time causal; historical live arrival availability is unverified."
)


def _metric_average(rows):
    return {name: round(float(np.mean([row[name] for row in rows])), 6) for name in SCORE_NAMES}


def _reliability(rows):
    bins = []
    for lower in np.arange(0.0, 1.0, 0.2):
        upper = float(lower + 0.2)
        selected = [
            row
            for row in rows
            if lower <= row["probability"] and (row["probability"] < upper or upper >= 1.0)
        ]
        if selected:
            bins.append(
                {
                    "probability_min": round(float(lower), 1),
                    "probability_max": round(float(lower + 0.2), 1),
                    "count": len(selected),
                    "mean_probability": round(
                        float(np.mean([row["probability"] for row in selected])), 5
                    ),
                    "event_frequency": round(float(np.mean([row["event"] for row in selected])), 5),
                }
            )
    return bins


def _forecast_row(model, row):
    methods, scores = {}, {}
    for model_id in MODEL_IDS:
        prediction = distribution_prediction(model, model_id, row)
        methods[model_id] = {
            "probability_shift_ge_5deg": round(prediction["probability"], 6),
            "center_twd_deg": round(prediction["center_twd_deg"], 5),
        }
        if row["target_delta_deg"] is not None:
            score = score_prediction(prediction, row["target_delta_deg"])
            score.update(
                probability=prediction["probability"],
                event=int(abs(row["target_delta_deg"]) >= SHIFT_DEG),
            )
            scores[model_id] = score
    return {
        "timestamp_ms": row["issue_ms"],
        "valid_until_ms": row["issue_ms"] + 12_000,
        "target_timestamp_ms": row["label_end_ms"],
        "current_twd_deg": row["current_deg"],
        "quality": "experimental",
        "methods": methods,
        "target_status": "observed" if scores else "censored",
        "observed_endpoint_change_deg": row["target_delta_deg"],
    }, scores


def _day_predictions(model, rows, per_race):
    scores = defaultdict(list)
    for row in rows:
        prediction, row_scores = _forecast_row(model, row)
        per_race[row["race_id"]]["predictions"].append(prediction)
        for model_id, score in row_scores.items():
            scores[model_id].append(score)
    return dict(scores)


def _unavailable_day(rows, per_race):
    for row in rows:
        per_race[row["race_id"]]["unavailable_prediction_count"] += 1
    return {
        "status": "unavailable",
        "reason": "No completed prior-day training horizons.",
        "training_days": 0,
        "training_targets": 0,
        "scored_targets": 0,
    }


def _process_day(day, rows, all_rows, per_race):
    first_issue = min(row["issue_ms"] for row in rows)
    training = prior_training_rows(all_rows, day, first_issue)
    if len(training) < 20:
        return _unavailable_day(rows, per_race), {}
    model = fit_models(training)
    templates = distribution_templates(model)
    for race_id in {row["race_id"] for row in rows}:
        per_race[race_id].update(
            distribution_templates=templates,
            training_last_label_ms=max(row["label_end_ms"] for row in training),
            training_days=len({row["date"] for row in training}),
            tuning=model["tuning"],
            ar_residual_source=model["ar_residual_source"],
        )
    scores = _day_predictions(model, rows, per_race)
    summary = {
        "status": "evaluated",
        "training_days": len({row["date"] for row in training}),
        "training_targets": len(training),
        "scored_targets": len(scores.get(MODEL_IDS[0], [])),
        "tuning": model["tuning"],
        "models": {key: _metric_average(value) for key, value in scores.items()},
    }
    return summary, scores


def _paired_days(day_results):
    differences = []
    for day, result in day_results.items():
        models = result.get("models", {})
        if not models:
            continue
        for model_id in ("event_climatology", "local_angle_ar"):
            differences.append(
                {
                    "date": day,
                    "model": model_id,
                    **{
                        name: round(
                            models[model_id][name] - models["probabilistic_persistence"][name], 6
                        )
                        for name in SCORE_NAMES
                    },
                }
            )
    return differences


def _validation(day_results, scores):
    output = {}
    for model_id, model_scores in scores.items():
        day_means = [
            result["models"][model_id] for result in day_results.values() if result.get("models")
        ]
        output[model_id] = {
            "sample_weighted": _metric_average(model_scores),
            "day_equal": _metric_average(day_means),
            "scored_targets": len(model_scores),
            "scored_days": len(day_means),
            "reliability": _reliability(model_scores),
        }
    return output


def _difference_summary(differences):
    output = []
    for model_id in ("event_climatology", "local_angle_ar"):
        values = [row for row in differences if row["model"] == model_id]
        if not values:
            continue
        row = {"model": model_id, "day_count": len(values), "scores": {}}
        draws = np.random.default_rng(20261119).integers(0, len(values), (1000, len(values)))
        for name in SCORE_NAMES:
            observed = np.asarray([value[name] for value in values])
            bootstrap = observed[draws].mean(axis=1)
            row["scores"][name] = {
                "mean_difference": round(float(observed.mean()), 6),
                "day_resampling_p025": round(float(np.quantile(bootstrap, 0.025)), 6),
                "day_resampling_p975": round(float(np.quantile(bootstrap, 0.975)), 6),
                "minimum_day_difference": round(float(observed.min()), 6),
                "maximum_day_difference": round(float(observed.max()), 6),
            }
        output.append(row)
    return {
        "scope": "Paired held-out day-score sensitivity, conditional on fitted historical forecasts; few-day percentile bands are not calibrated confidence guarantees.",
        "bootstrap_draws": 1000,
        "models": output,
    }


def _race_outputs(records):
    return {
        record["id"]: {
            "schema_version": SCHEMA_VERSION,
            "method_version": METHOD_VERSION,
            "race_id": record["id"],
            "availability_basis": AVAILABILITY,
            "source_provenance": record.get("source_provenance", {}),
            "predictions": [],
            "unavailable_prediction_count": 0,
            "reference_model": "probabilistic_persistence",
            "max_snapshot_age_ms": 12_000,
        }
        for record in records
    }


def run_wind_forecast(records_by_race):
    """Evaluate all models on identical endpoints, training on strictly earlier days."""
    records = (
        list(records_by_race.values())
        if isinstance(records_by_race, dict)
        else list(records_by_race)
    )
    records.sort(key=lambda record: (record["date"], record["id"]))
    per_race = _race_outputs(records)
    all_rows, extraction, source_samples = [], {}, 0
    for record in records:
        rows, counts = build_contexts(record)
        all_rows.extend(rows)
        extraction[record["id"]] = counts
        source_samples += source_count(record)[0]
        per_race[record["id"]]["extraction"] = counts
    days, scores = {}, defaultdict(list)
    for day in sorted({row["date"] for row in all_rows}):
        rows = [row for row in all_rows if row["date"] == day]
        result, day_scores = _process_day(day, rows, all_rows, per_race)
        days[day] = result
        for model_id, values in day_scores.items():
            scores[model_id].extend(values)
    validation = _validation(days, scores)
    paired = _paired_days(days)
    return {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "status": "experimental" if validation else "insufficient_prior_days",
        "availability_basis": AVAILABILITY,
        "target": {
            "definition": "abs(wrap(TWD(t+180s)-TWD(t))) >= 5 degrees at the endpoint",
            "horizon_s": HORIZON_MS // 1000,
            "threshold_deg": SHIFT_DEG,
            "history_s": HISTORY_MS // 1000,
            "cadence_s": CADENCE_MS // 1000,
            "max_source_age_ms": MAX_AGE_MS,
            "features": list(FEATURE_NAMES),
        },
        "validation_protocol": "Expanding whole-day origins; all training label horizons end before the first current-day issue; inner tuning uses earlier training days only.",
        "counts": {
            "races": len(records),
            "source_direction_samples": source_samples,
            "context_days": len(days),
            "fresh_contexts": len(all_rows),
            "censored_targets": sum(value["censored_target"] for value in extraction.values()),
            "scored_targets": len(scores.get(MODEL_IDS[0], [])),
        },
        "validation": validation,
        "by_day": days,
        "paired_day_differences": paired,
        "day_uncertainty": _difference_summary(paired),
        "reference_model": "probabilistic_persistence",
        "per_race": per_race,
        "limitations": [
            "Overlapping horizons are dependent; sample counts are not independent trials.",
            "Few race days: reliability bins and paired day differences are descriptive, not proof of calibration.",
            "All models predict reported official wind at its asset, not wind across the racecourse.",
            "A small training-only uniform component prevents unsupported exact event probabilities of zero or one.",
            "No automatic adoption of the autoregressive challenger or exact coverage guarantee.",
        ],
    }
