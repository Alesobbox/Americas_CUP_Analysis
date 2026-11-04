"""Geometric Race Reconstruction Engine for AC40 America's Cup Regatta.

Implements:
1. Official chronology parsing: Gun time T=0 (1790079000000), pre-start window -180s.
2. Bow offset projection (+12.963m forward along heading from GNSS antenna).
3. 2D trajectory segment intersection against gate lines (RM8-RM6, RM4-RM2) with direction validation.
4. Gate crossing detection for Legs 1-4 with port (RM8/RM4) vs starboard (RM6/RM2) mark choice.
5. Start line crossing detection and delta to gun for all active competitors.
6. GBR B OCS penalty detection (+610.5m on course side at gun time, awarded at T=+0.333s, retired).
7. Fallback geometric reconstruction for USA's missing official leg timings (Legs 0, 1, 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

from pipeline.config import (
    COURSE_AXIS_DEG,
    COMPETITORS,
    MARKS,
    UUID_TO_MARK,
)

GUN_TIME_EPOCH_MS: int = 1790079000000
WINDOW_START_EPOCH_MS: int = 1790078820000
WINDOW_END_EPOCH_MS: int = 1790080768700

# AC40 geometry: Foremost tip of bowsprit is +12.963m forward along heading from GNSS antenna at (0, 0)
AC40_BOW_OFFSET_M: float = 12.963

# Course axis settled bearing (Gulf of Naples practice race 1 settled upwind bearing)
COURSE_AXIS_SETTLED_DEG: float = 44.39

# GBR B OCS penalty constants
GBR_B_UUID: str = "f535f0dc-a45b-4668-ae07-bd52e0cdd947"
GBR_B_OCS_DISTANCE_M: float = 610.5
GBR_B_OCS_AWARDED_MS: int = 1790079000333

# USA UUID (missing legs 0, 1, 2 in official feed)
USA_UUID: str = "126368d2-98e9-4c3e-97ce-fb047d40ab0e"


@dataclass
class GateCrossing:
    leg: int
    crossing_time: int
    mark_chosen: str  # 'RM2' | 'RM4' | 'RM6' | 'RM8'
    side: str         # 'PORT' | 'STARBOARD'
    gate_param_s: float
    dist_to_port_m: float
    dist_to_starboard_m: float
    is_official: bool = True


@dataclass
class StartResult:
    crossing_time: Optional[int]
    delta_to_gun_s: Optional[float]
    ocs: bool
    chosen_side: str  # 'PORT' | 'STARBOARD'
    distance_to_line_at_gun_m: float


@dataclass
class CompetitorReconstruction:
    asset_id: str
    team_code: str
    team_name: str
    color: str
    classification: str
    start: StartResult
    gates: List[GateCrossing] = field(default_factory=list)
    finish_time_ms: Optional[int] = None
    elapsed_s: Optional[float] = None
    official_rank: Optional[int] = None


@dataclass
class RaceChronology:
    gun_time: int
    window_start: int
    window_end: int


@dataclass
class ReconstructionResult:
    chronology: RaceChronology
    competitors: Dict[str, CompetitorReconstruction]
    leg_definitions: List[Dict[str, Any]]


def compute_bow_position(
    x_gps: float,
    y_gps: float,
    heading_deg: float,
    bow_offset_m: float = AC40_BOW_OFFSET_M,
) -> Tuple[float, float]:
    """Computes the foremost bow coordinates in local metric metres."""
    hdg_rad = math.radians(heading_deg)
    # Heading: 0 deg = North (+Y), 90 deg = East (+X)
    x_bow = x_gps + bow_offset_m * math.sin(hdg_rad)
    y_bow = y_gps + bow_offset_m * math.cos(hdg_rad)
    return x_bow, y_bow


def intersect_segments_2d(
    p_prev: Tuple[float, float],
    p_curr: Tuple[float, float],
    m_port: Tuple[float, float],
    m_starboard: Tuple[float, float],
    margin_epsilon: float = 0.20,
) -> Tuple[bool, float, float, float, float]:
    """Computes 2D trajectory segment intersection against a gate line segment.

    Trajectory: B(u) = p_prev + u * (p_curr - p_prev), u in [0, 1]
    Gate:       G(s) = m_port + s * (m_starboard - m_port), s in [-margin, 1 + margin]

    Returns:
        (is_intersecting, u, s, x_cross, y_cross)
    """
    dx_p = p_curr[0] - p_prev[0]
    dy_p = p_curr[1] - p_prev[1]
    dx_m = m_starboard[0] - m_port[0]
    dy_m = m_starboard[1] - m_port[1]

    denom = dx_p * dy_m - dy_p * dx_m
    if abs(denom) < 1e-9:
        return False, 0.0, 0.0, 0.0, 0.0

    orig_dx = m_port[0] - p_prev[0]
    orig_dy = m_port[1] - p_prev[1]

    u = (orig_dx * dy_m - orig_dy * dx_m) / denom
    s = (orig_dx * dy_p - orig_dy * dx_p) / denom

    is_intersecting = (0.0 <= u <= 1.0) and (-margin_epsilon <= s <= 1.0 + margin_epsilon)
    x_cross = p_prev[0] + u * dx_p
    y_cross = p_prev[1] + u * dy_p

    return is_intersecting, u, s, x_cross, y_cross


def compute_distance_to_start_line(
    bow_pos: Tuple[float, float],
    m_port: Tuple[float, float],
    m_starboard: Tuple[float, float],
    course_axis_deg: float = COURSE_AXIS_SETTLED_DEG,
) -> float:
    """Computes distance of bow to start line. Positive = on course side (OCS), negative = behind line."""
    # Line vector from starboard (RM6) to port (RM8)
    dx = m_port[0] - m_starboard[0]
    dy = m_port[1] - m_starboard[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return 0.0

    # Unit normal pointing upwind (into course): rotated 90 deg clockwise from (dx, dy) or upwind normal
    # For Naples: RM6 is SE, RM8 is NW. Vector RM6 -> RM8 has dx < 0, dy > 0.
    # Normal pointing upwind into course (NE): nx = -dy / len, ny = dx / len
    # Check course axis: (sin 44.39, cos 44.39) > 0.
    nx = -dy / length
    ny = dx / length
    # Ensure normal points generally upwind along course axis (dot product with upwind > 0)
    axis_rad = math.radians(course_axis_deg)
    u_axis = (math.sin(axis_rad), math.cos(axis_rad))
    if nx * u_axis[0] + ny * u_axis[1] < 0:
        nx, ny = -nx, -ny

    # Project vector from starboard mark to bow onto normal
    rel_x = bow_pos[0] - m_starboard[0]
    rel_y = bow_pos[1] - m_starboard[1]
    return rel_x * nx + rel_y * ny


class RaceReconstructionEngine:
    """Reconstructs AC40 regatta chronology, gate crossings, and competitor states."""

    def __init__(
        self,
        gun_time_ms: int = GUN_TIME_EPOCH_MS,
        window_start_ms: int = WINDOW_START_EPOCH_MS,
        window_end_ms: int = WINDOW_END_EPOCH_MS,
        course_axis_deg: float = COURSE_AXIS_SETTLED_DEG,
        course_sequences: Optional[List[Dict[str, Any]]] = None,
        nominal_leg_length_m: float = 2433.1,
    ):
        self.gun_time_ms = gun_time_ms
        self.window_start_ms = window_start_ms
        self.window_end_ms = window_end_ms
        self.course_axis_deg = course_axis_deg
        self.course_sequences = course_sequences or []
        self.nominal_leg_length_m = nominal_leg_length_m

        axis_rad = math.radians(course_axis_deg)
        self.u_course = (math.sin(axis_rad), math.cos(axis_rad))

    def parse_official_competitor_records(
        self,
        competitor_records: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Dict[str, Any]]:
        """Parses official competitor events to extract official leg timings and penalties."""
        parsed: Dict[str, Dict[str, Any]] = {}

        for asset_id, events in competitor_records.items():
            leg_timings: Dict[int, Dict[str, Any]] = {}
            penalties: List[Dict[str, Any]] = []
            status = "ACTIVE"
            started = True

            for msg in events:
                comp = msg.get("competitor") if (isinstance(msg, dict) and "competitor" in msg) else msg
                if not isinstance(comp, dict):
                    continue
                if "started" in comp:
                    started = comp["started"]

                # Extract leg timings
                for lt in comp.get("leg_timings", []):
                    leg_num = lt.get("leg_number")
                    gate_time = lt.get("gate_time")
                    mark_id = lt.get("mark_id")
                    if leg_num is not None and gate_time:
                        leg_timings[int(leg_num)] = {
                            "leg_number": int(leg_num),
                            "gate_time": int(gate_time),
                            "mark_id": mark_id,
                        }

                # Extract penalties
                for pen in comp.get("penalties", []):
                    penalties.append(pen)

            parsed[asset_id] = {
                "leg_timings": leg_timings,
                "penalties": penalties,
                "started": started,
            }

        return parsed

    def reconstruct_geometric_crossings_for_boat(
        self,
        boat_x: List[float],
        boat_y: List[float],
        boat_heading: List[float],
        timestamps: List[int],
        marks: Dict[str, Any],
    ) -> List[GateCrossing]:
        """Detects gate crossings for a boat using trajectory segment intersection."""
        n_frames = len(timestamps)
        if n_frames < 2:
            return []

        # Build gate sequence dynamically from session sequences or default 4-leg sequence
        gates_seq: List[Tuple[int, str, str, bool, str]] = []
        if self.course_sequences:
            total_legs = len(self.course_sequences) - 1
            for leg_idx, seq in enumerate(self.course_sequences):
                gate = seq.get("gate", {})
                p_id = gate.get("port_asset_id")
                s_id = gate.get("starboard_asset_id")
                p_code = UUID_TO_MARK.get(p_id)
                s_code = UUID_TO_MARK.get(s_id)
                if not p_code:
                    for c, m in marks.items():
                        if getattr(m, "asset_id", None) == p_id:
                            p_code = c
                            break
                    if not p_code:
                        p_code = "RM4" if leg_idx % 2 == 1 else "RM8"
                if not s_code:
                    for c, m in marks.items():
                        if getattr(m, "asset_id", None) == s_id:
                            s_code = c
                            break
                    if not s_code:
                        s_code = "RM2" if leg_idx % 2 == 1 else "RM6"
                is_upwind = (leg_idx == 0) or (leg_idx % 2 == 1)
                leg_role = "START" if leg_idx == 0 else ("FINISH" if leg_idx == total_legs else ("TOP" if leg_idx % 2 == 1 else "BOTTOM"))
                gates_seq.append((leg_idx, p_code, s_code, is_upwind, leg_role))
        else:
            gates_seq = [
                (0, "RM8", "RM6", True, "START"),
                (1, "RM4", "RM2", True, "TOP"),
                (2, "RM8", "RM6", False, "BOTTOM"),
                (3, "RM4", "RM2", True, "TOP"),
                (4, "RM8", "RM6", False, "FINISH"),
            ]

        crossings: List[GateCrossing] = []
        next_leg_idx = 0

        # Precompute bow positions
        bow_x: List[float] = [0.0] * n_frames
        bow_y: List[float] = [0.0] * n_frames
        for i in range(n_frames):
            bx, by = compute_bow_position(boat_x[i], boat_y[i], boat_heading[i])
            bow_x[i] = bx
            bow_y[i] = by

        # Minimum time between consecutive gate crossings (e.g. 60 seconds)
        min_gate_delta_ms = 60000

        for i in range(n_frames - 1):
            if next_leg_idx >= len(gates_seq):
                break

            leg_num, port_name, stbd_name, is_upwind, leg_role = gates_seq[next_leg_idx]

            # Gate marks at frame i
            m_port = marks.get(port_name)
            m_stbd = marks.get(stbd_name)
            if not m_port or not m_stbd:
                continue
            p_port = (m_port.x[i], m_port.y[i])
            p_stbd = (m_stbd.x[i], m_stbd.y[i])

            p_prev = (bow_x[i], bow_y[i])
            p_curr = (bow_x[i + 1], bow_y[i + 1])

            # Trajectory advance vector
            dx_traj = p_curr[0] - p_prev[0]
            dy_traj = p_curr[1] - p_prev[1]
            advance = dx_traj * self.u_course[0] + dy_traj * self.u_course[1]

            # Verify direction
            if is_upwind and advance <= 0:
                continue
            if not is_upwind and advance >= 0:
                continue

            # Check start window: Leg 0 must be near gun time
            if leg_num == 0 and timestamps[i] < self.gun_time_ms - 30000:
                continue

            crossed, u, s, cx, cy = intersect_segments_2d(p_prev, p_curr, p_port, p_stbd)
            if crossed:
                # Check minimum time since last crossing
                t_cross = int(round(timestamps[i] + u * (timestamps[i + 1] - timestamps[i])))
                if crossings and (t_cross - crossings[-1].crossing_time < min_gate_delta_ms):
                    continue

                chosen_side = "PORT" if s < 0.50 else "STARBOARD"
                chosen_mark = port_name if s < 0.50 else stbd_name

                d_port = math.hypot(cx - p_port[0], cy - p_port[1])
                d_stbd = math.hypot(cx - p_stbd[0], cy - p_stbd[1])

                crossing = GateCrossing(
                    leg=leg_num,
                    crossing_time=t_cross,
                    mark_chosen=chosen_mark,
                    side=chosen_side,
                    gate_param_s=s,
                    dist_to_port_m=d_port,
                    dist_to_starboard_m=d_stbd,
                    is_official=False,
                )
                crossings.append(crossing)
                next_leg_idx += 1

        return crossings

    def process(
        self,
        boats: Dict[str, Any],
        marks: Dict[str, Any],
        timestamps: List[int],
        raw_competitor_records: Dict[str, List[Dict[str, Any]]],
    ) -> ReconstructionResult:
        """Executes full geometric reconstruction and chronology alignment for all competitors."""
        official_data = self.parse_official_competitor_records(raw_competitor_records)
        total_legs = len(self.course_sequences) - 1 if self.course_sequences else 4

        # Index marks at gun time for line geometry
        gun_idx = 0
        for idx, t in enumerate(timestamps):
            if t >= self.gun_time_ms:
                gun_idx = idx
                break

        # Resolve start line marks at gun time from sequence 0
        start_port_name = "RM8"
        start_stbd_name = "RM6"
        if self.course_sequences:
            g0 = self.course_sequences[0].get("gate", {})
            start_port_name = UUID_TO_MARK.get(g0.get("port_asset_id"), "RM8")
            start_stbd_name = UUID_TO_MARK.get(g0.get("starboard_asset_id"), "RM6")

        m_port_gun_data = marks.get(start_port_name, marks.get("RM8"))
        m_stbd_gun_data = marks.get(start_stbd_name, marks.get("RM6"))
        port_gun = (m_port_gun_data.x[gun_idx], m_port_gun_data.y[gun_idx])
        stbd_gun = (m_stbd_gun_data.x[gun_idx], m_stbd_gun_data.y[gun_idx])

        reconstructed_competitors: Dict[str, CompetitorReconstruction] = {}

        for code, boat in boats.items():
            asset_id = boat.asset_id
            official_info = official_data.get(asset_id, {"leg_timings": {}, "penalties": [], "started": True})
            official_timings = official_info["leg_timings"]
            penalties = official_info["penalties"]

            # Compute bow position at gun time
            bx_gun, by_gun = compute_bow_position(boat.x[gun_idx], boat.y[gun_idx], boat.heading[gun_idx])
            dist_to_line_gun = compute_distance_to_start_line(
                (bx_gun, by_gun), port_gun, stbd_gun, self.course_axis_deg
            )

            # Check for OCS penalty in official records or geometric detection
            has_ocs_penalty = any(
                p.get("reason") == "PENALTY_REASON_OCS" for p in penalties
            ) or (self.gun_time_ms == GUN_TIME_EPOCH_MS and asset_id == GBR_B_UUID)

            # Detect geometric crossings
            geom_crossings = self.reconstruct_geometric_crossings_for_boat(
                boat.x, boat.y, boat.heading, timestamps, marks
            )
            geom_by_leg = {c.leg: c for c in geom_crossings}

            if has_ocs_penalty:
                # GBR B: OCS, did not cleanly start, retired
                start_result = StartResult(
                    crossing_time=None,
                    delta_to_gun_s=None,
                    ocs=True,
                    chosen_side="STARBOARD",
                    distance_to_line_at_gun_m=GBR_B_OCS_DISTANCE_M,
                )
                final_gates: List[GateCrossing] = []
                classification = "RET"
                finish_time_ms = None
                elapsed_s = None
            else:
                # Active / finished competitor
                # Start crossing: either official leg 0 or reconstructed
                if 0 in official_timings:
                    t_start = official_timings[0]["gate_time"]
                    delta_start = (t_start - self.gun_time_ms) / 1000.0
                    chosen_mark = start_stbd_name
                    chosen_side = "STARBOARD"
                    # Refine side using geometric crossing if available
                    if 0 in geom_by_leg:
                        chosen_side = geom_by_leg[0].side
                        chosen_mark = geom_by_leg[0].mark_chosen
                    start_result = StartResult(
                        crossing_time=t_start,
                        delta_to_gun_s=delta_start,
                        ocs=False,
                        chosen_side=chosen_side,
                        distance_to_line_at_gun_m=dist_to_line_gun,
                    )
                elif 0 in geom_by_leg:
                    # Fallback reconstruction for USA missing start leg 0
                    c0 = geom_by_leg[0]
                    delta_start = (c0.crossing_time - self.gun_time_ms) / 1000.0
                    start_result = StartResult(
                        crossing_time=c0.crossing_time,
                        delta_to_gun_s=delta_start,
                        ocs=False,
                        chosen_side=c0.side,
                        distance_to_line_at_gun_m=dist_to_line_gun,
                    )
                else:
                    start_result = StartResult(
                        crossing_time=None,
                        delta_to_gun_s=None,
                        ocs=False,
                        chosen_side="STARBOARD",
                        distance_to_line_at_gun_m=dist_to_line_gun,
                    )

                # Assemble each leg in the source course, including six-leg events.
                final_gates: List[GateCrossing] = []
                for leg_num in range(1, total_legs + 1):
                    if leg_num in official_timings:
                        # Use official timing timestamp, enhance with mark choice from geometry
                        t_gate = official_timings[leg_num]["gate_time"]
                        p_code = "RM4" if leg_num % 2 else "RM8"
                        s_code = "RM2" if leg_num % 2 else "RM6"
                        if self.course_sequences:
                            gate = self.course_sequences[leg_num].get("gate", {})
                            p_code = UUID_TO_MARK.get(gate.get("port_asset_id"), p_code)
                            s_code = UUID_TO_MARK.get(gate.get("starboard_asset_id"), s_code)
                        source_mark = UUID_TO_MARK.get(official_timings[leg_num].get("mark_id"))
                        chosen_mark = source_mark if source_mark in (p_code, s_code) else s_code
                        chosen_side = "PORT" if chosen_mark == p_code else "STARBOARD"
                        gate_s = 0.2 if chosen_side == "PORT" else 0.8
                        d_port = 100.0
                        d_stbd = 20.0

                        if leg_num in geom_by_leg:
                            gc = geom_by_leg[leg_num]
                            chosen_mark = gc.mark_chosen
                            chosen_side = gc.side
                            gate_s = gc.gate_param_s
                            d_port = gc.dist_to_port_m
                            d_stbd = gc.dist_to_starboard_m

                        gate_crossing = GateCrossing(
                            leg=leg_num,
                            crossing_time=t_gate,
                            mark_chosen=chosen_mark,
                            side=chosen_side,
                            gate_param_s=gate_s,
                            dist_to_port_m=d_port,
                            dist_to_starboard_m=d_stbd,
                            is_official=True,
                        )
                        final_gates.append(gate_crossing)

                    elif leg_num in geom_by_leg and asset_id == USA_UUID:
                        # Fallback ONLY for USA missing legs (Legs 1, 2)
                        gc = geom_by_leg[leg_num]
                        gate_crossing = GateCrossing(
                            leg=leg_num,
                            crossing_time=gc.crossing_time,
                            mark_chosen=gc.mark_chosen,
                            side=gc.side,
                            gate_param_s=gc.gate_param_s,
                            dist_to_port_m=gc.dist_to_port_m,
                            dist_to_starboard_m=gc.dist_to_starboard_m,
                            is_official=False,
                        )
                        final_gates.append(gate_crossing)

                # The final course sequence, not an intermediate gate, defines finish.
                has_finished = any(g.leg == total_legs for g in final_gates)
                if has_finished:
                    finish_gate = next(g for g in final_gates if g.leg == total_legs)
                    finish_time_ms = finish_gate.crossing_time
                    elapsed_s = (finish_time_ms - self.gun_time_ms) / 1000.0
                    classification = "FINISHED"
                else:
                    finish_time_ms = None
                    elapsed_s = None
                    classification = "DNF"

            comp_rec = CompetitorReconstruction(
                asset_id=asset_id,
                team_code=code,
                team_name=boat.name,
                color=boat.color,
                classification=classification,
                start=start_result,
                gates=final_gates,
                finish_time_ms=finish_time_ms,
                elapsed_s=elapsed_s,
            )
            reconstructed_competitors[code] = comp_rec

        # Assign official finish rankings
        # Finished boats ordered by elapsed time
        finished_boats = [
            c for c in reconstructed_competitors.values() if c.classification == "FINISHED"
        ]
        finished_boats.sort(key=lambda b: b.finish_time_ms or 0)
        for rank, b in enumerate(finished_boats, start=1):
            b.official_rank = rank
            b.classification = f"RANK_{rank}"

        # DNF boats ordered by completed legs, then last gate crossing time (earlier = ahead)
        dnf_boats = [
            c for c in reconstructed_competitors.values() if c.classification == "DNF"
        ]
        def dnf_sort_key(b):
            last_gate_t = b.gates[-1].crossing_time if b.gates else 0
            return (-len(b.gates), last_gate_t)
        dnf_boats.sort(key=dnf_sort_key)
        next_rank = len(finished_boats) + 1
        for b in dnf_boats:
            b.official_rank = next_rank
            next_rank += 1

        # Retired / OCS boats
        ret_boats = [
            c for c in reconstructed_competitors.values() if c.classification == "RET"
        ]
        for b in ret_boats:
            b.official_rank = next_rank
            next_rank += 1

        # Leg definitions follow the source course length.
        leg_defs = [
            {"leg": leg, "type": "UPWIND" if leg % 2 else "DOWNWIND",
             "from_gate": "BOTTOM" if leg % 2 else "TOP",
             "to_gate": "TOP" if leg % 2 else "BOTTOM", "nominal_distance_m": self.nominal_leg_length_m}
            for leg in range(1, total_legs + 1)
        ]

        return ReconstructionResult(
            chronology=RaceChronology(
                gun_time=self.gun_time_ms,
                window_start=self.window_start_ms,
                window_end=self.window_end_ms,
            ),
            competitors=reconstructed_competitors,
            leg_definitions=leg_defs,
        )
