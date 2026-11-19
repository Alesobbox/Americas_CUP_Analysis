"""Block bootstrap with estimator refits from sufficient statistics."""

from dataclasses import dataclass
import numpy as np
from .constants import POLAR_BOOTSTRAP_DRAWS, POLAR_BOOTSTRAP_SEED


def interval(point, draws):
    values = np.asarray(draws, dtype=float)
    values = values[np.isfinite(values)]
    if not values.size or not np.isfinite(point):
        return None
    return {
        "value": round(float(point), 3),
        "ci_low_kt": round(float(np.quantile(values, 0.025)), 3),
        "ci_high_kt": round(float(np.quantile(values, 0.975)), 3),
        "bootstrap_se_kt": round(float(values.std(ddof=1)), 3) if len(values) > 1 else 0.0,
        "valid_draws": int(values.size),
    }


def design(ds, mask):
    wind = (ds.tws[mask] - 12) / 5
    angle = (ds.twa[mask] - np.where(ds.mode[mask] == 1, 45, 135)) / 20
    return np.column_stack(
        [np.ones(wind.size), wind, angle, wind**2, angle**2, wind * angle, ds.tack[mask]]
    )


@dataclass
class BlockSummary:
    names: np.ndarray
    dates: np.ndarray
    mass: np.ndarray
    sums: np.ndarray
    tack_sum: np.ndarray
    gram: np.ndarray
    rhs: np.ndarray
    cluster_support: np.ndarray


def summarize(ds, grouping):
    names = np.unique(grouping)
    shape = (len(names), len(ds.grid_keys))
    mass, sums, tack_sum = np.zeros(shape), np.zeros(shape), np.zeros(shape)
    gram, rhs = np.zeros((len(names), 2, 7, 7)), np.zeros((len(names), 2, 7))
    dates = []
    for i, group in enumerate(names):
        selected = grouping == group
        dates.append(ds.date[selected][0])
        grid = ds.cell_to_grid[selected]
        mass[i] = np.bincount(grid, minlength=shape[1])
        sums[i] = np.bincount(grid, weights=ds.sog[selected], minlength=shape[1])
        tack_sum[i] = np.bincount(grid, weights=ds.tack[selected], minlength=shape[1])
        for mode in (0, 1):
            mask = selected & (ds.mode == mode)
            matrix = design(ds, mask)
            gram[i, mode] = matrix.T @ matrix
            rhs[i, mode] = matrix.T @ ds.sog[mask]
    occupancy = np.zeros((len(ds.grid_keys), len(ds.cluster_key)), dtype=np.int32)
    occupancy[ds.cell_to_grid, ds.cluster_id] = 1
    near_cluster = (ds.K_grid >= 0.25).astype(np.int32) @ occupancy > 0
    cluster_support = np.zeros(shape)
    for i, group in enumerate(names):
        clusters = np.unique(ds.cluster_id[grouping == group])
        cluster_support[i] = near_cluster[:, clusters].sum(axis=1)
    return BlockSummary(names, np.array(dates), mass, sums, tack_sum, gram, rhs, cluster_support)


def refit(ds, summary, multiplicities):
    mass = multiplicities @ summary.mass
    sums = multiplicities @ summary.sums
    tacks = multiplicities @ summary.tack_sum
    effects = np.zeros(2)
    for mode in (0, 1):
        gram = np.einsum("u,uij->ij", multiplicities, summary.gram[:, mode])
        rhs = multiplicities @ summary.rhs[:, mode]
        identifiable = gram[0, 0] > 0 and gram[-1, -1] - gram[0, -1] ** 2 / gram[0, 0] > 1e-8
        if identifiable:
            effects[mode] = np.linalg.lstsq(gram, rhs, rcond=None)[0][-1]
    adjusted = sums - effects[ds.grid_keys[:, 0].astype(int)] * tacks
    support = ds.K_grid @ mass
    clusters = (multiplicities > 0) @ summary.cluster_support
    means = np.divide(
        ds.K_grid @ adjusted,
        support,
        out=np.full(len(mass), np.nan),
        where=(support >= 12) & (clusters >= 2),
    )
    return means, effects


def _evaluation_cells(ds, grouping, supported):
    teams, team_code = np.unique(ds.team_code, return_inverse=True)
    unique, inverse = np.unique(
        np.column_stack([grouping, team_code, ds.cell_to_grid, ds.tack]),
        axis=0,
        return_inverse=True,
    )
    mass = np.bincount(inverse, weights=supported.astype(float))
    sums = np.bincount(inverse, weights=np.where(supported, ds.sog, 0))
    return teams, unique, mass, sums


def _draw_residuals(ds, summary, cells, multiplicities):
    _, unique, mass, sums = cells
    unit = unique[:, 0].astype(int)
    teams = unique[:, 1].astype(int)
    count = len(cells[0])
    numerator, denominator = np.zeros(count), np.zeros(count)
    for day in np.unique(summary.dates):
        training = multiplicities * (summary.dates != day)
        if not training.sum():
            continue
        means, effects = refit(ds, summary, training)
        mode = ds.grid_keys[unique[:, 2].astype(int), 0].astype(int)
        predicted = means[unique[:, 2].astype(int)] + effects[mode] * unique[:, 3]
        weights = multiplicities[unit] * (summary.dates[unit] == day)
        valid = np.isfinite(predicted) & (mass > 0)
        denominator += np.bincount(
            teams[valid], weights=weights[valid] * mass[valid], minlength=count
        )
        numerator += np.bincount(
            teams[valid],
            weights=weights[valid] * (sums[valid] - mass[valid] * predicted[valid]),
            minlength=count,
        )
    return np.divide(numerator, denominator, out=np.full(count, np.nan), where=denominator > 0)


def refitted_intervals(ds, predictions, grouping, draws=POLAR_BOOTSTRAP_DRAWS):
    summary = summarize(ds, grouping)
    units = np.searchsorted(summary.names, grouping)
    supported = np.isfinite(predictions)
    cells = _evaluation_cells(ds, units, supported)
    rng = np.random.default_rng(POLAR_BOOTSTRAP_SEED)
    estimates, tack_draws = [], []
    for _ in range(draws):
        counts = np.bincount(
            rng.integers(0, len(summary.names), len(summary.names)), minlength=len(summary.names)
        )
        estimates.append(_draw_residuals(ds, summary, cells, counts))
        _, effects = refit(ds, summary, counts)
        tack_draws.append(effects)
    estimates, tack_draws = np.asarray(estimates), np.asarray(tack_draws)
    team_intervals = {}
    for i, team in enumerate(cells[0]):
        mask = supported & (ds.team_code == team)
        point = (ds.sog[mask] - predictions[mask]).mean() if np.any(mask) else np.nan
        team_intervals[team] = interval(point, estimates[:, i])
    return team_intervals, tack_draws


def tack_intervals(ds, draws):
    summary = summarize(ds, ds.date)
    _, points = refit(ds, summary, np.ones(len(summary.names)))
    output = {
        "specification": "Quadratic wind/angle adjusted fixed effect for tack; OLS refit per block draw",
        "bootstrap_draws": len(draws),
        "resampling_unit": "day",
        "uncertainty_scope": "refitted_estimator_few_days_sensitivity",
    }
    for mode, name in ((1, "upwind"), (0, "downwind")):
        result = interval(points[mode], draws[:, mode])
        output[name] = dict(
            result, contrast_kt=result["value"], coverage_s=float((ds.mode == mode).sum())
        )
    weights = np.array([(ds.mode == mode).mean() for mode in (0, 1)])
    result = interval(points @ weights, draws @ weights)
    output["overall"] = dict(result, contrast_kt=result["value"], coverage_s=float(len(ds.sog)))
    return output
