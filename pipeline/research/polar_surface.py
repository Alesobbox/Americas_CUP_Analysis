"""Small kernel and local-linear challengers for conditional ground speed."""

from dataclasses import dataclass

import numpy as np

from .polar_table import ResearchTable


@dataclass(frozen=True)
class SurfaceConfig:
    method: str
    wind_bandwidth: float
    angle_bandwidth: float
    ridge: float = 0.1

    @property
    def name(self) -> str:
        return f"{self.method}_bw{self.wind_bandwidth:g}_{self.angle_bandwidth:g}"


CONFIGS = tuple(
    SurfaceConfig(method, wind, angle)
    for method in ("kernel", "local_linear")
    for wind, angle in ((1.0, 3.0), (1.5, 4.0), (2.5, 7.0))
)


def surface_predict(train: ResearchTable, test: ResearchTable, config: SurfaceConfig) -> np.ndarray:
    return predict_prepared(prepare_surface(train), test, config)


def prepare_surface(train: ResearchTable) -> dict[tuple[int, int], tuple[np.ndarray, ...]]:
    groups = {}
    for mode in (0, 1):
        for tack in (-1, 1):
            fit_mask = (train.mode == mode) & (train.tack == tack)
            if np.any(fit_mask):
                groups[(mode, tack)] = _compressed(train.select(fit_mask))
    return groups


def predict_prepared(groups: dict, test: ResearchTable, config: SurfaceConfig) -> np.ndarray:
    predictions = np.full(test.size, np.nan)
    for mode in (0, 1):
        for tack in (-1, 1):
            test_mask = (test.mode == mode) & (test.tack == tack)
            if (mode, tack) in groups and np.any(test_mask):
                predictions[test_mask] = _group_prediction(
                    groups[(mode, tack)], test.select(test_mask), config
                )
    return predictions


def _compressed(table: ResearchTable) -> tuple[np.ndarray, ...]:
    keys = np.column_stack([np.round(table.tws), np.round(table.twa / 2.5) * 2.5])
    cells, inverse = np.unique(keys, axis=0, return_inverse=True)
    counts = np.bincount(inverse).astype(float)
    means = np.bincount(inverse, weights=table.sog) / counts
    cluster_keys = np.column_stack([table.race, table.boat, table.leg.astype(str)])
    _, clusters = np.unique(cluster_keys, axis=0, return_inverse=True)
    minimum = np.full(len(cells), len(clusters), dtype=int)
    maximum = np.full(len(cells), -1, dtype=int)
    np.minimum.at(minimum, inverse, clusters)
    np.maximum.at(maximum, inverse, clusters)
    return cells, counts, means, minimum, maximum


def _group_prediction(
    compressed: tuple[np.ndarray, ...], test: ResearchTable, config: SurfaceConfig
) -> np.ndarray:
    cells, counts, means, cluster_minimum, cluster_maximum = compressed
    query, inverse = np.unique(
        np.column_stack([np.round(test.tws), np.round(test.twa / 2.5) * 2.5]),
        axis=0,
        return_inverse=True,
    )
    result = np.full(len(query), np.nan)
    bandwidth = np.array([config.wind_bandwidth, config.angle_bandwidth])
    for index, point in enumerate(query):
        distance = (cells - point) / bandwidth
        weights = np.exp(-0.5 * np.sum(distance**2, axis=1)) * counts
        near = np.sum(distance**2, axis=1) <= 4.0
        if weights.sum() < 12.0 or counts[near].sum() < 12.0:
            continue
        if np.min(cluster_minimum[near]) == np.max(cluster_maximum[near]):
            continue
        if config.method == "kernel":
            result[index] = np.sum(weights * means) / weights.sum()
        else:
            design = np.column_stack([np.ones(len(cells)), distance])
            penalty = np.diag([1e-9, config.ridge, config.ridge])
            gram = design.T @ (weights[:, None] * design) + penalty
            result[index] = np.linalg.solve(gram, design.T @ (weights * means))[0]
    return result[inverse]


def ridge_features(table: ResearchTable) -> np.ndarray:
    wind = table.tws / 10.0
    angle = table.twa / 90.0
    basis = np.column_stack([wind, angle, wind**2, angle**2, wind * angle, table.tack])
    return np.column_stack([np.ones(table.size), table.mode, basis, basis * table.mode[:, None]])


def ridge_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    center = train_x.mean(axis=0)
    scale = np.maximum(train_x.std(axis=0), 1e-6)
    fit = (train_x - center) / scale
    query = (test_x - center) / scale
    fit[:, 0] = query[:, 0] = 1.0
    penalty = np.eye(fit.shape[1])
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(fit.T @ fit + penalty, fit.T @ train_y)
    return query @ beta
