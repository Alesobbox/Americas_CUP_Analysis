"""Explicit absolute and self-excluding peer-relative residual estimands."""

from collections import defaultdict
import numpy as np
from .bootstrap import interval
from .constants import (
    POLAR_BOOTSTRAP_DRAWS,
    POLAR_BOOTSTRAP_SEED,
    POLAR_METHOD_VERSION,
    POLAR_SCHEMA_VERSION,
)
from .curves import _build_observed_bins


def mean_finite(values):
    values = values[np.isfinite(values)]
    return round(float(values.mean()), 3) if values.size else None


def conditional_interval(ds, residual, mask, grouping):
    valid = mask & np.isfinite(residual)
    groups = np.unique(grouping[valid])
    if not len(groups):
        return None
    sums = np.array([residual[valid & (grouping == group)].sum() for group in groups])
    weights = np.array([(valid & (grouping == group)).sum() for group in groups])
    rng = np.random.default_rng(POLAR_BOOTSTRAP_SEED)
    draws = rng.integers(0, len(groups), (POLAR_BOOTSTRAP_DRAWS, len(groups)))
    result = interval(residual[valid].mean(), sums[draws].sum(axis=1) / weights[draws].sum(axis=1))
    result.update(
        scope="conditional_on_fitted_out_of_day_reference",
        block_count=len(groups),
        resampling_unit="boat-leg within race" if grouping is ds.cluster_id else "day",
    )
    return result


def peer_contrasts(ds, predictions):
    groups = defaultdict(list)
    valid = np.isfinite(predictions)
    for cluster, key in enumerate(ds.cluster_key):
        mask = valid & (ds.cluster_id == cluster)
        if np.any(mask):
            groups[(key[0], key[2])].append(
                (ds.team_code[mask][0], (ds.sog[mask] - predictions[mask]).mean())
            )
    race_team = defaultdict(list)
    for (race, _), peers in groups.items():
        for team, value in peers:
            others = [other for code, other in peers if code != team]
            if others:
                race_team[(race, team)].append(value - float(np.mean(others)))
    output = defaultdict(list)
    for (race, team), values in race_team.items():
        date = ds.date[ds.race_id == race][0]
        output[team].append((date, float(np.mean(values))))
    return output


def peer_interval(observations):
    if not observations:
        return None
    days = sorted({row[0] for row in observations})
    sums = np.array([sum(value for day, value in observations if day == group) for group in days])
    weights = np.array([sum(day == group for day, _ in observations) for group in days])
    rng = np.random.default_rng(POLAR_BOOTSTRAP_SEED)
    draws = rng.integers(0, len(days), (POLAR_BOOTSTRAP_DRAWS, len(days)))
    result = interval(
        sums.sum() / weights.sum(), sums[draws].sum(axis=1) / weights[draws].sum(axis=1)
    )
    result.update(
        scope="conditional_on_cross_fitted_polar; equal peers, legs, then races",
        resampling_unit="day",
        day_count=len(days),
    )
    return result


def team_rows(ds, loro, lodo, fitted, intervals):
    day_ci, race_ci = intervals
    peers = peer_contrasts(ds, lodo["sog"])
    result = []
    for team in sorted(set(ds.team_code)):
        mask = ds.team_code == team
        residual = ds.sog - lodo["sog"]
        result.append(
            {
                "team_code": team,
                "race_count": len(set(ds.race_id[mask])),
                "leg_cluster_count": len(set(ds.cluster_id[mask])),
                "steady_coverage_s": int(mask.sum()),
                "lodo_sog_residual_kt": day_ci.get(team),
                "race_block_sensitivity_kt": race_ci.get(team),
                "loro_sog_residual_kt": conditional_interval(
                    ds, ds.sog - loro["sog"], mask, ds.date
                ),
                "in_sample_sog_residual_kt": conditional_interval(
                    ds, ds.sog - fitted["eval_sog"], mask, ds.date
                ),
                "wind_vmg_residual_kt": conditional_interval(
                    ds, ds.vmg - lodo["vmg"], mask, ds.date
                ),
                "peer_relative_residual_kt": peer_interval(peers[team]),
                "upwind_sog_residual_kt": mean_finite(residual[mask & (ds.mode == 1)]),
                "downwind_sog_residual_kt": mean_finite(residual[mask & (ds.mode == 0)]),
                "port_sog_residual_kt": mean_finite(residual[mask & (ds.tack < 0)]),
                "starboard_sog_residual_kt": mean_finite(residual[mask & (ds.tack > 0)]),
                "above_p90_share": exceedance(ds.sog[mask], lodo["p90"][mask]),
                "bootstrap_draws": POLAR_BOOTSTRAP_DRAWS,
            }
        )
    return result


def exceedance(actual, predicted):
    valid = np.isfinite(predicted)
    return round(float((actual[valid] >= predicted[valid]).mean()), 4) if np.any(valid) else None


def boat_residual(ds, mask, predictions):
    loro, lodo, fitted = predictions
    count = int(mask.sum())
    supported = bool(np.any(mask & np.isfinite(lodo["sog"])))
    base = {
        "schema_version": POLAR_SCHEMA_VERSION,
        "method_version": POLAR_METHOD_VERSION,
        "quality": "derived" if supported else "unavailable",
        "reason": None if supported else "No eligible supported held-out observations",
        "evaluation_scope": "out_of_sample_archive_cv",
        "steady_sample_count": count,
        "steady_coverage_s": count,
        "leg_cluster_count": len(set(ds.cluster_id[mask])),
        "traffic_excluded_s": 0,
        "bootstrap_draws": POLAR_BOOTSTRAP_DRAWS,
        "sog_residual_kt": conditional_interval(ds, ds.sog - lodo["sog"], mask, ds.cluster_id),
        "wind_vmg_residual_kt": conditional_interval(ds, ds.vmg - lodo["vmg"], mask, ds.cluster_id),
        "loro_sog_residual_kt": mean_finite((ds.sog - loro["sog"])[mask]),
        "lodo_sog_residual_kt": mean_finite((ds.sog - lodo["sog"])[mask]),
        "in_sample_sog_residual_kt": mean_finite((ds.sog - fitted["eval_sog"])[mask]),
        "above_p90_share": exceedance(ds.sog[mask], lodo["p90"][mask]),
        "observed_bins": _build_observed_bins(ds, mask, lodo["sog"]),
    }
    return base
