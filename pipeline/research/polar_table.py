"""Timestamped sample table used by AC38 conditional-performance experiments."""

from dataclasses import dataclass, replace
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ResearchTable:
    race: np.ndarray
    day: np.ndarray
    boat: np.ndarray
    team: np.ndarray
    timestamp: np.ndarray
    leg: np.ndarray
    mode: np.ndarray
    tack: np.ndarray
    tws: np.ndarray
    twa: np.ndarray
    sog: np.ndarray
    heading: np.ndarray
    cog: np.ndarray
    twd: np.ndarray
    x: np.ndarray
    y: np.ndarray

    def select(self, mask: np.ndarray) -> "ResearchTable":
        return ResearchTable(**{key: value[mask] for key, value in vars(self).items()})

    def with_wind(self, speed: np.ndarray, direction: np.ndarray) -> "ResearchTable":
        angle = np.abs(circular_difference(direction, self.heading))
        tack = np.where(circular_difference(direction, self.heading) >= 0, 1, -1)
        return replace(self, tws=speed, twd=direction, twa=angle, tack=tack)

    @property
    def size(self) -> int:
        return self.sog.size


def circular_difference(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return (first - second + 180.0) % 360.0 - 180.0


def table_from_details(details: dict[str, dict[str, Any]]) -> ResearchTable:
    columns: dict[str, list] = {key: [] for key in ResearchTable.__dataclass_fields__}
    for race_id, detail in sorted(details.items()):
        race = detail["race"]
        for boat in detail.get("boats", []):
            for sample in boat.get("polar_samples", []):
                row = _sample_row(sample, race_id, race, boat)
                for key, value in row.items():
                    columns[key].append(value)
    strings = {"race", "day", "boat", "team"}
    return ResearchTable(
        **{
            key: np.asarray(values, dtype=str if key in strings else float)
            for key, values in columns.items()
        }
    )


def _sample_row(sample: dict, race_id: str, race: dict, boat: dict) -> dict:
    return {
        "race": race_id,
        "day": str(race["date"]),
        "boat": str(boat["id"]),
        "team": str(boat.get("team_code", boat["id"])),
        "timestamp": int(sample["timestamp_ms"]),
        "leg": int(sample["leg"]),
        "mode": int(sample["mode"] == "upwind"),
        "tack": 1 if sample["tack"] == "STARBOARD" else -1,
        "tws": float(sample["tws_kt"]),
        "twa": float(sample["abs_twa_deg"]),
        "sog": float(sample["sog_kt"]),
        "heading": float(sample["heading_deg"]),
        "cog": float(sample["cog_deg"]),
        "twd": float(sample["twd_deg"]),
        "x": float(sample["x_m"]),
        "y": float(sample["y_m"]),
    }


def describe_cohort(table: ResearchTable) -> dict:
    return {
        "sample_count": table.size,
        "races": len(np.unique(table.race)),
        "days": len(np.unique(table.day)),
        "boats": len(np.unique(table.boat)),
        "dates": np.unique(table.day).tolist(),
        "sample_unit": "accepted 1 Hz steady-state sample",
    }
