"""Explicit scenario support and issue/availability/valid-time forecast contract.

No reanalysis is accepted as a forecast that a crew could have known. The MVP
uses raw observed wind at the cutoff and modeled future variation; archive
forecast records may be supplied locally through this contract.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ForecastWind:
    issued_at_ms: int
    available_at_ms: int
    valid_at_ms: int
    tws_kt: float
    twd_deg: float
    source: str
    product: str = "archived_forecast"

    def __post_init__(self):
        if (any(not isinstance(value, int) or isinstance(value, bool)
                for value in (self.issued_at_ms, self.available_at_ms, self.valid_at_ms))
                or self.product != "archived_forecast" or not self.source
                or self.available_at_ms < self.issued_at_ms or self.valid_at_ms < self.issued_at_ms
                or not math.isfinite(self.tws_kt) or self.tws_kt < 0
                or not math.isfinite(self.twd_deg) or not 0<=self.twd_deg<360):
            raise ValueError("Invalid available forecast; reanalysis is not a historical forecast")


def available_run(records, cutoff_ms):
    eligible=[r for r in records if r.available_at_ms <= cutoff_ms and r.issued_at_ms <= cutoff_ms]
    if not eligible:
        return []
    issue=max(r.issued_at_ms for r in eligible)
    return sorted([r for r in eligible if r.issued_at_ms==issue],key=lambda r:r.valid_at_ms)


def condition_support(transitions, *, tws_kt, direction_offset_deg):
    if not math.isfinite(tws_kt) or tws_kt<0 or not math.isfinite(direction_offset_deg):
        return False,"Conditions must be finite, with nonnegative wind speed"
    if abs(direction_offset_deg)>15:
        return False,"Direction exceeds the declared ±15 degree fixed-course support"
    matching=[r for r in transitions if not r.get("practice")
              and r.get("competitive", True) is not False and r.get("valid", True) is not False
              and isinstance(r.get("wind_knots"), (int, float)) and math.isfinite(r["wind_knots"])
              and r["wind_knots"] >= 0 and abs(r["wind_knots"]-tws_kt)<=2]
    if len({r["date"] for r in matching})<2 or len({r["race_id"] for r in matching})<3:
        return False,"Fewer than two earlier competitive dates and three races within ±2 knots"
    # Direction responses are not measured by a wind-speed-only reference.
    if direction_offset_deg != 0:
        return False,"A course-relative direction response has not passed validation"
    return True,None
