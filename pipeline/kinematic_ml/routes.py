"""Observed-behavior route template extraction, normalization, and sampling (T08).

Contract (G3.2, G3.3):
- Disjoint straight, maneuver-plus-recovery, start, and dwell segments.
- Every segment contributes exactly once: maneuver duration replaces straight integration.
- Training-only route library: held-out dates/families are strictly excluded.
- Minimum-support rule: prefers team templates only with >= 10 eligible legs across >= 3 training days;
  otherwise uses explicit pooled templates and reports support tier.
- No future or elapsed times used in route selection.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class RouteSegment:
    """Disjoint segment of a regatta leg route."""
    segment_type: str  # 'straight', 'maneuver', 'start', 'dwell', 'gate'
    start_pos: tuple[float, float]  # (x, y) in meters
    end_pos: tuple[float, float]
    distance_m: float
    target_cog_deg: float
    target_heading_deg: float
    turn_type: str | None = None
    turn_rotation_deg: float | None = None
    maneuver_duration_s: float | None = None
    recovery_s: float | None = None
    is_censored: bool = False


@dataclass(frozen=True)
class LegRouteTemplate:
    """Normalized leg route template extracted from observed telemetry."""
    template_id: str
    attempt_id: str
    team_id: str
    date_str: str
    stage: str
    leg_number: int
    leg_type: int  # 1 = upwind, 0 = downwind
    mean_tws_mps: float
    leg_length_m: float
    segments: list[RouteSegment]
    is_complete: bool = True


class RouteTemplateLibrary:
    """Stores training-only route templates and samples compatible routes for simulation."""

    def __init__(self, templates: Sequence[LegRouteTemplate] | None = None) -> None:
        self._templates: list[LegRouteTemplate] = list(templates) if templates else []

    @property
    def total_templates(self) -> int:
        return len(self._templates)

    def add_template(self, t: LegRouteTemplate) -> None:
        self._templates.append(t)

    def team_support_level(self, team_id: str, leg_type: int) -> tuple[str, int, int]:
        """Check team support: returns (support_tier, leg_count, day_count).
        
        Requires >= 10 eligible legs across >= 3 training days for team-specific tier.
        """
        team_legs = [
            t for t in self._templates
            if t.team_id == team_id and t.leg_type == leg_type and t.is_complete
        ]
        days = {t.date_str for t in team_legs}
        leg_count = len(team_legs)
        day_count = len(days)

        if leg_count >= 10 and day_count >= 3:
            return "team_specific", leg_count, day_count
        return "pooled", leg_count, day_count

    def query_nearest_templates(
        self,
        team_id: str,
        leg_type: int,
        target_tws_mps: float,
        target_leg_length_m: float,
        *,
        k: int = 10,
        epsilon: float = 1e-4,
    ) -> tuple[list[tuple[LegRouteTemplate, float]], str]:
        """Queries k nearest compatible templates using standardized distance.
        
        Returns list of (template, normalized_weight) and the support_tier used.
        """
        tier, leg_cnt, day_cnt = self.team_support_level(team_id, leg_type)
        if tier == "team_specific":
            candidates = [
                t for t in self._templates
                if t.team_id == team_id and t.leg_type == leg_type and t.is_complete
            ]
        else:
            candidates = [
                t for t in self._templates
                if t.leg_type == leg_type and t.is_complete
            ]

        if not candidates:
            return [], "unavailable"

        # Standardized distance metrics
        # Scale: tws ~ 5 m/s stdev, leg_length ~ 500 m stdev
        tws_scale = 5.0
        len_scale = 500.0

        scored = []
        for cand in candidates:
            d_tws = (cand.mean_tws_mps - target_tws_mps) / tws_scale
            d_len = (cand.leg_length_m - target_leg_length_m) / len_scale
            dist = math.sqrt(d_tws * d_tws + d_len * d_len)
            scored.append((cand, dist))

        scored.sort(key=lambda x: x[1])
        top_k = scored[:k]

        # Inverse distance weights
        raw_weights = [1.0 / (dist + epsilon) for _, dist in top_k]
        total_w = sum(raw_weights)
        norm_weights = [w / total_w for w in raw_weights]

        res = [(top_k[i][0], norm_weights[i]) for i in range(len(top_k))]
        return res, tier

    def sample_template(
        self,
        team_id: str,
        leg_type: int,
        target_tws_mps: float,
        target_leg_length_m: float,
        rng: np.random.Generator,
    ) -> tuple[LegRouteTemplate | None, str]:
        """Samples a compatible template according to inverse-distance weights."""
        weighted_templates, tier = self.query_nearest_templates(
            team_id, leg_type, target_tws_mps, target_leg_length_m
        )
        if not weighted_templates:
            return None, "unavailable"

        templates = [t for t, _ in weighted_templates]
        probs = [p for _, p in weighted_templates]
        choice_idx = int(rng.choice(len(templates), p=probs))
        return templates[choice_idx], tier

    def to_dict(self) -> dict[str, Any]:
        """Serialize library to JSON-compatible dictionary."""
        return {
            "schema_version": "ac75-route-templates-1",
            "total_templates": len(self._templates),
            "templates": [asdict(t) for t in self._templates],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RouteTemplateLibrary:
        """Deserialize library from JSON dictionary."""
        templates: list[LegRouteTemplate] = []
        for raw_t in data.get("templates", []):
            segs = [
                RouteSegment(
                    segment_type=str(s["segment_type"]),
                    start_pos=(float(s["start_pos"][0]), float(s["start_pos"][1])),
                    end_pos=(float(s["end_pos"][0]), float(s["end_pos"][1])),
                    distance_m=float(s["distance_m"]),
                    target_cog_deg=float(s["target_cog_deg"]),
                    target_heading_deg=float(s["target_heading_deg"]),
                    turn_type=s.get("turn_type"),
                    turn_rotation_deg=float(s["turn_rotation_deg"]) if s.get("turn_rotation_deg") is not None else None,
                    maneuver_duration_s=float(s["maneuver_duration_s"]) if s.get("maneuver_duration_s") is not None else None,
                    recovery_s=float(s["recovery_s"]) if s.get("recovery_s") is not None else None,
                    is_censored=bool(s.get("is_censored", False)),
                )
                for s in raw_t.get("segments", [])
            ]
            templates.append(
                LegRouteTemplate(
                    template_id=str(raw_t["template_id"]),
                    attempt_id=str(raw_t["attempt_id"]),
                    team_id=str(raw_t["team_id"]),
                    date_str=str(raw_t["date_str"]),
                    stage=str(raw_t["stage"]),
                    leg_number=int(raw_t["leg_number"]),
                    leg_type=int(raw_t["leg_type"]),
                    mean_tws_mps=float(raw_t["mean_tws_mps"]),
                    leg_length_m=float(raw_t["leg_length_m"]),
                    segments=segs,
                    is_complete=bool(raw_t.get("is_complete", True)),
                )
            )
        return cls(templates=templates)


def transform_template_to_course(
    template: LegRouteTemplate,
    course_bearing_deg: float,
    course_length_m: float,
    *,
    leeway_deg: float = 3.0,
) -> list[RouteSegment]:
    """Transforms a normalized template (where +y is along leg bearing 0 deg and +x is starboard/East)
    to physical course dimensions and compass bearing (clockwise from North +y toward East +x).

    Preserves straight/maneuver partition and recomputes segment COG/heading.
    """
    if template.leg_length_m <= 0:
        scale = 1.0
    else:
        scale = course_length_m / template.leg_length_m

    rad_bearing = math.radians(course_bearing_deg)
    cos_b = math.cos(rad_bearing)
    sin_b = math.sin(rad_bearing)

    transformed: list[RouteSegment] = []
    for s in template.segments:
        # Scale coordinates
        x1_s = s.start_pos[0] * scale
        y1_s = s.start_pos[1] * scale
        x2_s = s.end_pos[0] * scale
        y2_s = s.end_pos[1] * scale

        # Clockwise compass rotation by course_bearing_deg:
        # (0, L) rotated by 90 deg -> (+L, 0) (East, COG 90 deg)
        x1 = x1_s * cos_b + y1_s * sin_b
        y1 = -x1_s * sin_b + y1_s * cos_b
        x2 = x2_s * cos_b + y2_s * sin_b
        y2 = -x2_s * sin_b + y2_s * cos_b

        dx = x2 - x1
        dy = y2 - y1
        dist_m = math.sqrt(dx * dx + dy * dy)

        if dist_m > 1e-3:
            cog_deg = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
        else:
            cog_deg = (s.target_cog_deg + course_bearing_deg) % 360.0

        # Derive heading by applying leeway offset
        hdg_deg = (cog_deg - leeway_deg + 360.0) % 360.0

        seg = RouteSegment(
            segment_type=s.segment_type,
            start_pos=(round(x1, 2), round(y1, 2)),
            end_pos=(round(x2, 2), round(y2, 2)),
            distance_m=round(dist_m, 2),
            target_cog_deg=round(cog_deg, 1),
            target_heading_deg=round(hdg_deg, 1),
            turn_type=s.turn_type,
            turn_rotation_deg=s.turn_rotation_deg,
            maneuver_duration_s=s.maneuver_duration_s,
            recovery_s=s.recovery_s,
            is_censored=s.is_censored,
        )
        transformed.append(seg)

    return transformed
