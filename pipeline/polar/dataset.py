"""One row per accepted second; smoothing grids contain predictors only."""

from dataclasses import dataclass
import numpy as np
from .constants import KERNEL_BW_TWA_DEG, KERNEL_BW_TWS_KT
from .inputs import _boat_eligible


@dataclass
class PolarDataset:
    race_id: np.ndarray
    date: np.ndarray
    team_code: np.ndarray
    boat_id: np.ndarray
    cluster_id: np.ndarray
    cluster_key: list
    mode: np.ndarray
    tack: np.ndarray
    weights: np.ndarray
    tws: np.ndarray
    twa: np.ndarray
    tws_bin: np.ndarray
    twa_bin: np.ndarray
    sog: np.ndarray
    vmg: np.ndarray
    grid_keys: np.ndarray
    cell_to_grid: np.ndarray
    K_grid: np.ndarray
    leg: np.ndarray
    timestamp: np.ndarray


def _rows(details):
    rows, clusters, keys = [], {}, []
    for rid, detail in sorted(details.items()):
        for boat in detail.get("boats", []):
            if not _boat_eligible(boat):
                continue
            for sample in boat.get("polar_samples", []):
                key = (rid, boat["id"], sample["leg"])
                if key not in clusters:
                    clusters[key] = len(keys)
                    keys.append(key)
                rows.append(
                    (
                        rid,
                        detail["race"]["date"],
                        boat["team_code"],
                        boat["id"],
                        clusters[key],
                        sample,
                    )
                )
    return rows, keys


def assemble_dataset(details):
    rows, keys = _rows(details)
    if not rows:
        return None
    samples = [r[5] for r in rows]
    mode = np.array([int(s["mode"] == "upwind") for s in samples])
    tws = np.array([s["tws_kt"] for s in samples], dtype=float)
    twa = np.array([s["abs_twa_deg"] for s in samples], dtype=float)
    tws_bin = np.round(tws)
    twa_bin = np.round(twa / 2.5) * 2.5
    grid, inverse = np.unique(
        np.column_stack([mode, tws_bin, twa_bin]), axis=0, return_inverse=True
    )
    distance = ((grid[:, None, 1] - grid[None, :, 1]) / KERNEL_BW_TWS_KT) ** 2
    distance += ((grid[:, None, 2] - grid[None, :, 2]) / KERNEL_BW_TWA_DEG) ** 2
    kernel = np.exp(-distance / 2) * (grid[:, None, 0] == grid[None, :, 0])
    return PolarDataset(
        race_id=np.array([r[0] for r in rows]),
        date=np.array([r[1] for r in rows]),
        team_code=np.array([r[2] for r in rows]),
        boat_id=np.array([r[3] for r in rows]),
        cluster_id=np.array([r[4] for r in rows]),
        cluster_key=keys,
        mode=mode,
        tack=np.array([0.5 if s["tack"] == "STARBOARD" else -0.5 for s in samples]),
        weights=np.ones(len(rows)),
        tws=tws,
        twa=twa,
        tws_bin=tws_bin,
        twa_bin=twa_bin,
        sog=np.array([s["sog_kt"] for s in samples]),
        vmg=np.array([s["wind_vmg_kt"] for s in samples]),
        grid_keys=grid,
        cell_to_grid=inverse,
        K_grid=kernel,
        leg=np.array([s["leg"] for s in samples]),
        timestamp=np.array([s["timestamp_ms"] for s in samples]),
    )
