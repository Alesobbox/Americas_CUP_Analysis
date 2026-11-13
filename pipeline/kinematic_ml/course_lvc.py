"""Course presets and geometric boundaries for Barcelona and Naples regattas."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CoursePreset:
    preset_id: str
    name: str
    venue: str
    course_axis_deg: float
    course_length_m: float
    boundary_width_m: float
    leg_count: int
    default_wind_speed_kt: float
    default_wind_dir_deg: float
    gate_width_m: float = 50.0

    @property
    def axis_length_nmi(self) -> float:
        return self.course_length_m / 1852.0


BARCELONA_2024_LVC = CoursePreset(
    preset_id="barcelona_2024_lvc",
    name="Barcelona 2024 Louis Vuitton Cup Match Course",
    venue="Barcelona",
    course_axis_deg=105.0,
    course_length_m=2590.0,
    boundary_width_m=800.0,
    leg_count=6,
    default_wind_speed_kt=11.5,
    default_wind_dir_deg=105.0
)

NAPLES_2026_PRELIM = CoursePreset(
    preset_id="naples_2026_prelim",
    name="Naples 2026 Preliminary Regatta Match Course",
    venue="Naples",
    course_axis_deg=75.0,
    course_length_m=2450.0,
    boundary_width_m=750.0,
    leg_count=6,
    default_wind_speed_kt=12.0,
    default_wind_dir_deg=65.0
)

COURSE_PRESETS = {
    BARCELONA_2024_LVC.preset_id: BARCELONA_2024_LVC,
    NAPLES_2026_PRELIM.preset_id: NAPLES_2026_PRELIM,
}
