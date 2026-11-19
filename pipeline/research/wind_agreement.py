"""Boat, official and target-excluded nearby-peer wind agreement."""

from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from .feature_evaluation import compare_features
from .polar_evaluation import day_equal_scores, day_folds, paired_day_difference, score_predictions
from .polar_surface import ridge_features, ridge_predict
from .polar_table import ResearchTable, circular_difference


def _official_wind(table: ResearchTable, data_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    speed = np.full(table.size, np.nan)
    direction = np.full(table.size, np.nan)
    for race_id in np.unique(table.race):
        path = data_dir / "replays" / f"{race_id}.json"
        if not path.is_file():
            continue
        replay = json.loads(path.read_text(encoding="utf-8"))
        wind = replay.get("wind")
        timeline = wind.get("timeline", []) if wind is not None else []
        _assign_official(table, race_id, timeline, speed, direction)
    return speed, direction


def _assign_official(
    table: ResearchTable, race: str, timeline: list, speed: np.ndarray, direction: np.ndarray
) -> None:
    records = [row for row in timeline if row.get("tws") is not None and row.get("twd") is not None]
    if not records:
        return
    records.sort(key=lambda row: row["t"])
    times = np.asarray([row["t"] for row in records])
    indexes = np.flatnonzero(table.race == race)
    right = np.clip(np.searchsorted(times, table.timestamp[indexes]), 0, len(times) - 1)
    left = np.maximum(right - 1, 0)
    nearest = np.where(
        abs(times[left] - table.timestamp[indexes]) < abs(times[right] - table.timestamp[indexes]),
        left,
        right,
    )
    valid = abs(times[nearest] - table.timestamp[indexes]) <= 500
    speed[indexes[valid]] = np.asarray([row["tws"] for row in records])[nearest[valid]]
    direction[indexes[valid]] = np.asarray([row["twd"] for row in records])[nearest[valid]]


def peer_wind(table: ResearchTable) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    speed, direction = np.full(table.size, np.nan), np.full(table.size, np.nan)
    support = np.zeros(table.size, dtype=int)
    groups = defaultdict(list)
    for index in range(table.size):
        groups[(table.race[index], int(table.timestamp[index] // 1000), table.leg[index])].append(
            index
        )
    for indexes in groups.values():
        _assign_peers(table, np.asarray(indexes), speed, direction, support)
    return speed, direction, support


def _assign_peers(
    table: ResearchTable,
    indexes: np.ndarray,
    speed: np.ndarray,
    direction: np.ndarray,
    support: np.ndarray,
) -> None:
    positions = np.column_stack([table.x[indexes], table.y[indexes]])
    distances = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=2)
    for local, index in enumerate(indexes):
        valid = (
            (distances[local] >= 60)
            & (distances[local] <= 300)
            & (table.boat[indexes] != table.boat[index])
            & (abs(table.timestamp[indexes] - table.timestamp[index]) <= 500)
        )
        if np.any(valid):
            peers = indexes[valid]
            radians = np.deg2rad(table.twd[peers])
            direction[index] = (
                np.degrees(np.arctan2(np.mean(np.sin(radians)), np.mean(np.cos(radians)))) % 360
            )
            speed[index] = np.mean(table.tws[peers])
            support[index] = len(peers)


def _discrepancy(table: ResearchTable, reference: tuple[np.ndarray, np.ndarray]) -> dict:
    speed, direction = reference
    output = []
    for team in np.unique(table.team):
        for tack in (-1, 1):
            mask = (
                (table.team == team)
                & (table.tack == tack)
                & np.isfinite(speed)
                & np.isfinite(direction)
            )
            if not np.any(mask):
                continue
            delta = circular_difference(table.twd[mask], direction[mask])
            output.append(
                {
                    "team_code": str(team),
                    "tack": "STARBOARD" if tack == 1 else "PORT",
                    "sample_count": int(mask.sum()),
                    "day_count": len(np.unique(table.day[mask])),
                    "median_speed_difference_kt": round(
                        float(np.median(table.tws[mask] - speed[mask])), 4
                    ),
                    "median_direction_difference_deg": round(float(np.median(delta)), 4),
                    "direction_discrepancies_above_60deg": int(np.sum(abs(delta) > 60)),
                    "day_block_sensitivity": _offset_intervals(
                        table.day[mask], table.tws[mask] - speed[mask], delta
                    ),
                }
            )
    return {
        "by_team_tack": output,
        "interpretation": "agreement offsets, not identified sensor biases",
    }


def _offset_intervals(days: np.ndarray, speed: np.ndarray, direction: np.ndarray) -> dict:
    unique = np.unique(days)
    speed_days = np.asarray([np.median(speed[days == day]) for day in unique])
    direction_days = np.asarray([_circular_mean(direction[days == day]) for day in unique])
    point = _circular_mean(direction_days)
    rng = np.random.default_rng(20261119)
    indexes = rng.integers(0, len(unique), size=(1000, len(unique)))
    speed_draws = speed_days[indexes].mean(axis=1)
    radians = np.deg2rad(direction_days[indexes])
    circular_draws = np.degrees(
        np.arctan2(np.sin(radians).mean(axis=1), np.cos(radians).mean(axis=1))
    )
    direction_draws = point + circular_difference(circular_draws, np.full(1000, point))
    return {
        "day_count": len(unique),
        "mean_daily_median_speed_difference_kt": round(float(speed_days.mean()), 4),
        "circular_mean_daily_direction_difference_deg": round(point, 4),
        "speed_interval_95_kt": np.quantile(speed_draws, [0.025, 0.975]).round(4).tolist()
        if len(unique) >= 3
        else None,
        "direction_interval_95_deg": np.quantile(direction_draws, [0.025, 0.975]).round(4).tolist()
        if len(unique) >= 3
        else None,
        "scope": "resampled observed-day summaries; few-day sensitivity, not sensor calibration certainty",
    }


def _circular_mean(values: np.ndarray) -> float:
    radians = np.deg2rad(values)
    return float(np.degrees(np.arctan2(np.sin(radians).mean(), np.cos(radians).mean())))


def _adjusted_features(
    table: ResearchTable, reference: tuple[np.ndarray, np.ndarray], train: np.ndarray
) -> np.ndarray:
    speed, direction = reference
    adjusted_speed, adjusted_direction = (
        table.tws.astype(float).copy(),
        table.twd.astype(float).copy(),
    )
    for boat in np.unique(table.boat):
        for tack in (-1, 1):
            group = (table.boat == boat) & (table.tack == tack)
            paired = group & train & np.isfinite(speed) & np.isfinite(direction)
            if paired.sum() >= 20:
                adjusted_speed[group] -= np.median(table.tws[paired] - speed[paired])
                adjusted_direction[group] -= np.median(
                    circular_difference(table.twd[paired], direction[paired])
                )
    return ridge_features(table.with_wind(adjusted_speed, adjusted_direction % 360))


def corrected_wind_evaluation(
    table: ResearchTable, reference: tuple[np.ndarray, np.ndarray]
) -> dict:
    folds = []
    raw = ridge_features(table)
    for day, train, test in day_folds(table, False):
        adjusted = _adjusted_features(table, reference, train)
        models = {}
        for name, values in (("onboard", raw), ("training_only_agreement_adjusted", adjusted)):
            prediction = ridge_predict(values[train], table.sog[train], values[test])
            models[name] = score_predictions(table.sog[test], prediction)
        folds.append(
            {"day": day, "training_dates": np.unique(table.day[train]).tolist(), "models": models}
        )
    return {
        "folds": folds,
        "day_equal": day_equal_scores(folds),
        "paired_day_difference": paired_day_difference(
            folds, "onboard", "training_only_agreement_adjusted"
        ),
        "offset_fit_scope": "training days only; boat+tack median; minimum 20 pairs",
    }


def run_wind_agreement(table: ResearchTable, data_dir: Path) -> dict:
    official = _official_wind(table, data_dir)
    peer_speed, peer_direction, support = peer_wind(table)
    features = {
        "onboard": ridge_features(table),
        "official": ridge_features(table.with_wind(*official)),
        "peer_consensus": ridge_features(table.with_wind(peer_speed, peer_direction)),
    }
    paired = np.isfinite(official[0]) & np.isfinite(official[1])
    return {
        "official_discrepancy": _discrepancy(table, official),
        "peer_discrepancy": _discrepancy(table, (peer_speed, peer_direction)),
        "peer_supported_samples": int(np.sum(support > 0)),
        "peer_radius_m": [60, 300],
        "timestamp_tolerance_ms": 500,
        "leave_one_day_out": compare_features(table, features),
        "chronological": compare_features(table, features, True),
        "training_only_agreement_adjustment": corrected_wind_evaluation(
            table.select(paired), (official[0][paired], official[1][paired])
        ),
        "scope": "contemporaneous conditional comparison; target boat excluded from peer consensus",
        "official_source": "exported interpolated official timeline; not independent local ground truth",
        "limitations": [
            "Spatial gradients and wakes cannot be distinguished from sensor offsets.",
            "Peer availability changes the comparison cohort; all models share its same rows.",
        ],
    }
