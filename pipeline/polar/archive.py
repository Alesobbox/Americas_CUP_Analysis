"""Assemble versioned sample-level polar artifacts without changing historical metrics."""

import numpy as np
from .bootstrap import refitted_intervals, tack_intervals
from .constants import (
    POLAR_SCHEMA_VERSION,
    POLAR_METHOD_VERSION,
    POLAR_CAVEATS,
    POLAR_DEFINITIONS,
    POLAR_BOOTSTRAP_DRAWS,
    ARCHIVE_TWS_BRACKETS,
)
from .curves import _eval_curve_points
from .dataset import assemble_dataset
from .fitting import _fit_and_predict_subset
from .residuals import boat_residual, team_rows
from .validation import evaluate, metrics, subset_dataset


def attach_single_race_polar_fallback(detail):
    for boat in detail.get("boats", []):
        boat["polar"] = {
            "schema_version": POLAR_SCHEMA_VERSION,
            "method_version": POLAR_METHOD_VERSION,
            "quality": "unavailable",
            "reason": "Archive sample-level refresh required for held-out reference",
            "evaluation_scope": "unavailable",
            "steady_sample_count": len(boat.get("polar_samples", [])),
            "steady_coverage_s": len(boat.get("polar_samples", [])),
            "leg_cluster_count": 0,
            "traffic_excluded_s": 0,
            "sog_residual_kt": None,
            "wind_vmg_residual_kt": None,
            "loro_sog_residual_kt": None,
            "lodo_sog_residual_kt": None,
            "above_p90_share": None,
            "observed_bins": {"upwind": [], "downwind": []},
        }
    detail["polar_analysis"] = {
        "schema_version": POLAR_SCHEMA_VERSION,
        "method_version": POLAR_METHOD_VERSION,
        "race_id": detail["race"]["id"],
        "quality": "unavailable",
        "evaluation_scope": "unavailable",
        "reason": "No eligible timestamped samples or no independent held-out reference",
        "caveats": POLAR_CAVEATS,
        "definitions": POLAR_DEFINITIONS,
        "validation_summary": None,
        "brackets": {"upwind": [], "downwind": []},
    }
    return detail


def descriptive_curves(ds):
    mask = np.ones(len(ds.sog), dtype=bool)
    result = {"upwind": [], "downwind": []}
    for name, mode, angles in (
        ("upwind", 1, np.arange(30, 75, 2.5)),
        ("downwind", 0, np.arange(110, 172, 2.5)),
    ):
        for key, label, lower, upper, reference in ARCHIVE_TWS_BRACKETS:
            points = _eval_curve_points(ds, mask, mode, lower, upper, angles.tolist())
            if points:
                result[name].append(
                    {
                        "id": key,
                        "label": label,
                        "tws_min_kt": lower,
                        "tws_max_kt": upper,
                        "tws_ref_kt": reference,
                        "evaluation_scope": "descriptive_full_archive",
                        "points": points,
                    }
                )
    return result


def _update_details(details, ds, context):
    validation, loro, lodo, fitted, tack, curves = context
    for rid, detail in details.items():
        rmask = ds.race_id == rid
        if not np.any(rmask):
            attach_single_race_polar_fallback(detail)
            continue
        for boat in detail["boats"]:
            mask = rmask & (ds.boat_id == boat["id"])
            boat["polar"] = boat_residual(ds, mask, (loro, lodo, fitted))
            filters = boat.get("polar_filter") or {}
            boat["polar"]["traffic_excluded_s"] = filters.get("traffic_excluded_s", 0)
        race_metrics = metrics(
            subset_dataset(ds, rmask), {key: value[rmask] for key, value in lodo.items()}, rid, 1
        )
        detail["polar_analysis"] = {
            "schema_version": POLAR_SCHEMA_VERSION,
            "method_version": POLAR_METHOD_VERSION,
            "race_id": rid,
            "quality": "derived",
            "reason": None,
            "evaluation_scope": "held_out_residuals; descriptive_full_archive_curves",
            "curve_scope": "descriptive_full_archive",
            "caveats": POLAR_CAVEATS,
            "definitions": POLAR_DEFINITIONS,
            "validation_summary": {
                "race_cell_count": sum(
                    len(boat.get("polar_cells", [])) for boat in detail["boats"]
                ),
                "race_sample_count": int(rmask.sum()),
                "target": "individual accepted 1 Hz observations",
                "race_steady_coverage_s": int(rmask.sum()),
                "lodo_sog_rmse_kt": race_metrics.get("sog_rmse_kt"),
                "tack_fixed_effect": tack,
            },
            "brackets": curves,
        }


def refresh_archive_polar_models(details_by_race_id, *, bootstrap_draws=POLAR_BOOTSTRAP_DRAWS):
    ds = assemble_dataset(details_by_race_id)
    if ds is None or len(set(ds.date)) < 2:
        for detail in details_by_race_id.values():
            attach_single_race_polar_fallback(detail)
        return None
    full = np.ones(len(ds.sog), dtype=bool)
    fitted = _fit_and_predict_subset(ds, full, full)
    validation, loro, lodo = evaluate(ds)
    day_ci, tack_draws = refitted_intervals(ds, lodo["sog"], ds.date, bootstrap_draws)
    race_ci, _ = refitted_intervals(ds, lodo["sog"], ds.race_id, bootstrap_draws)
    for intervals, unit in ((day_ci, "day"), (race_ci, "race")):
        for result in intervals.values():
            if result is not None:
                result.update(
                    scope="refitted LODO estimator on originally supported cohort; few-block sensitivity",
                    resampling_unit=unit,
                )
    tack = tack_intervals(ds, tack_draws)
    curves = descriptive_curves(ds)
    _update_details(details_by_race_id, ds, (validation, loro, lodo, fitted, tack, curves))
    return {
        "schema_version": POLAR_SCHEMA_VERSION,
        "method_version": POLAR_METHOD_VERSION,
        "evaluation_scope": "AC38 conditional sample-level performance; not live forecast skill",
        "curve_scope": "descriptive_full_archive",
        "target": "individual accepted 1 Hz observations",
        "steady_state_filter": {
            "sample_cadence_hz": 1,
            "min_sog_kt": 5,
            "max_sog_kt": 50,
            "min_tws_kt": 2,
            "max_tws_kt": 35,
            "upwind_abs_twa_deg": [28, 75],
            "downwind_abs_twa_deg": [105, 172],
            "manoeuvre_exclusion_s": 6.5,
            "gate_exclusion_s": 8,
            "max_turn_rate_deg_s": 6,
            "min_competitor_separation_m": 60,
        },
        "caveats": POLAR_CAVEATS,
        "definitions": POLAR_DEFINITIONS,
        "counts": {
            "eligible_races": len(set(ds.race_id)),
            "excluded_races": len(details_by_race_id) - len(set(ds.race_id)),
            "distinct_days": len(set(ds.date)),
            "boat_leg_clusters": len(ds.cluster_key),
            "steady_coverage_s": len(ds.sog),
            "steady_cells": len(set(zip(ds.cluster_id, ds.cell_to_grid, ds.tack))),
        },
        "tack_fixed_effect": tack,
        "validation": validation,
        "curves": curves,
        "team_residuals": team_rows(ds, loro, lodo, fitted, (day_ci, race_ci)),
        "uncertainty": {
            "primary": "day-block refitted estimator",
            "sensitivity": "race-block refitted estimator",
            "per_boat": "conditional on fixed LODO reference; within-race leg blocks",
            "few_days": True,
            "bootstrap_draws": bootstrap_draws,
        },
    }
