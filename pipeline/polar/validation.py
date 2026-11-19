"""Grouped retrospective validation and genuinely earlier-day forecasts."""

import numpy as np
from .fitting import _fit_and_predict_subset, _validation_metrics as metrics


def subset_dataset(ds, mask):
    from dataclasses import replace

    fields = (
        "race_id",
        "date",
        "team_code",
        "boat_id",
        "cluster_id",
        "mode",
        "tack",
        "weights",
        "tws",
        "twa",
        "tws_bin",
        "twa_bin",
        "sog",
        "vmg",
        "cell_to_grid",
        "leg",
        "timestamp",
    )
    return replace(ds, **{key: getattr(ds, key)[mask] for key in fields})


def empty_predictions(n):
    return {key: np.full(n, np.nan) for key in ("sog", "vmg", "p50", "p90")}


def grouped_predictions(ds, grouping, chronological=False):
    pred = empty_predictions(len(ds.sog))
    for group in sorted(set(grouping)):
        ev = grouping == group
        tr = grouping < group if chronological else ~ev
        if len(set(ds.date[tr])) < (2 if chronological else 1):
            continue
        fit = _fit_and_predict_subset(ds, tr, ev)
        for key in pred:
            pred[key][ev] = fit["eval_" + key]
    return pred


def mode_baseline(ds, valid):
    pred = empty_predictions(len(ds.sog))
    for day in sorted(set(ds.date)):
        for mode in (0, 1):
            tr = (ds.date != day) & (ds.mode == mode)
            ev = (ds.date == day) & (ds.mode == mode) & valid
            if not np.any(tr):
                continue
            pred["sog"][ev] = ds.sog[tr].mean()
            pred["vmg"][ev] = ds.vmg[tr].mean()
            pred["p50"][ev] = np.quantile(ds.sog[tr], 0.5)
            pred["p90"][ev] = np.quantile(ds.sog[tr], 0.9)
    return pred


def subgroup_metrics(ds, pred):
    groups = [("day", day, ds.date == day) for day in sorted(set(ds.date))]
    groups += [("mode", label, ds.mode == mode) for mode, label in ((1, "upwind"), (0, "downwind"))]
    groups += [
        ("tws", f"{lo}-{hi}", (ds.tws >= lo) & (ds.tws < hi))
        for lo, hi in ((2, 6), (6, 9), (9, 12), (12, 15), (15, 20), (20, 35.01))
    ]
    result = []
    for kind, group, mask in groups:
        if not np.any(mask):
            continue
        sub = subset_dataset(ds, mask)
        row = metrics(sub, {k: v[mask] for k, v in pred.items()}, str(group), 1)
        residual = sub.sog - pred["sog"][mask]
        finite = np.isfinite(residual)
        row.update(
            kind=kind,
            group=str(group),
            mean_residual_kt=(round(float(residual[finite].mean()), 4) if np.any(finite) else None),
        )
        result.append(row)
    return result


def evaluate(ds):
    loro = grouped_predictions(ds, ds.race_id)
    lodo = grouped_predictions(ds, ds.date)
    future = grouped_predictions(ds, ds.date, chronological=True)
    baseline = mode_baseline(ds, np.isfinite(lodo["sog"]))
    results = {
        "baseline_mode_only": metrics(
            ds, baseline, "LODO mode-only, same supported rows", len(set(ds.date))
        ),
        "leave_one_race_out": metrics(ds, loro, "Retrospective LORO", len(set(ds.race_id))),
        "leave_one_day_out": metrics(ds, lodo, "Retrospective LODO", len(set(ds.date))),
        "chronological": metrics(ds, future, "Earlier-day expanding evaluation", len(set(ds.date))),
    }
    results["by_group"] = subgroup_metrics(ds, lodo)
    results["calibration_status"] = (
        "diagnostic_only_insufficient_independent_days_for_coverage_guarantee"
    )
    return results, loro, lodo
