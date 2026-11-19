"""Coverage-aware replay access for retrospective timing research."""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
import math

KT_TO_MPS = 1852.0 / 3600.0
TRACK_FIELDS = ("sog", "cog", "heading", "twd", "tws", "x", "y")
SOURCE_FIELDS = ("sog", "cog", "heading", "twd", "tws", "gnss")


def angle_delta(a: float, b: float) -> float:
    return (b - a + 180.0) % 360.0 - 180.0


def covered(coverage: dict, start: float, end: float) -> bool:
    for field in SOURCE_FIELDS:
        info = coverage.get(field)
        if not info or info.get("first_ms") is None or info.get("last_ms") is None:
            return False
        if start < info["first_ms"] or end > info["last_ms"]:
            return False
        if any(a < end and b > start for a, b in info.get("gaps", [])):
            return False
    return True


@dataclass
class Track:
    times: list[int]
    telemetry: dict
    boat: dict
    axis_deg: float

    def state(self, timestamp: float) -> dict | None:
        if not self.times or not covered(
            self.boat.get("source_coverage") or {}, timestamp, timestamp
        ):
            return None
        if timestamp < self.times[0] or timestamp > self.times[-1]:
            return None
        right = min(bisect_right(self.times, timestamp), len(self.times) - 1)
        left = max(0, right - 1)
        span = self.times[right] - self.times[left]
        fraction = (timestamp - self.times[left]) / span if span else 0.0
        state = {"timestamp_ms": timestamp}
        for field in TRACK_FIELDS:
            values = self.telemetry.get(field) or []
            if right >= len(values):
                return None
            a, b = values[left], values[right]
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                return None
            if not math.isfinite(a) or not math.isfinite(b):
                return None
            change = angle_delta(a, b) if field in ("heading", "cog", "twd") else b - a
            state[field] = a + fraction * change
        state["twa"] = angle_delta(state["heading"], state["twd"])
        return state

    def leg(self, timestamp: float) -> dict | None:
        return next(
            (
                leg
                for leg in self.boat.get("legs", [])
                if leg.get("start_ms") is not None
                and leg.get("end_ms") is not None
                and leg["start_ms"] <= timestamp < leg["end_ms"]
            ),
            None,
        )

    def vmg(self, state: dict, leg: int) -> float:
        bearing = self.axis_deg + (180.0 if leg % 2 == 0 else 0.0)
        return state["sog"] * KT_TO_MPS * math.cos(math.radians(angle_delta(bearing, state["cog"])))


def track_for(replay: dict, boat: dict) -> Track:
    telemetry = replay.get("telemetry") or {}
    course = replay.get("course") or {}
    axis = course.get("axis_deg")
    if not isinstance(axis, (int, float)) or not math.isfinite(axis):
        raise ValueError("timing research requires a finite course axis")
    times = telemetry.get("timestamps") or []
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("timing research requires increasing replay timestamps")
    boats = telemetry.get("boats") or {}
    return Track(times, boats.get(boat["id"], {}), boat, float(axis))


def active_window(boat: dict) -> tuple[int, int] | None:
    start = (boat.get("start") or {}).get("crossing_time_ms")
    ends = [leg["end_ms"] for leg in boat.get("legs", []) if leg.get("end_ms") is not None]
    if start is None or not ends or max(ends) <= start:
        return None
    return int(start), int(max(ends))


def sample_times(start: int, end: int) -> list[int]:
    return list(range(((start + 999) // 1000) * 1000, end + 1, 1000))
