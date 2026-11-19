"""Tactical Analytics & Race Progress Engine for AC40 America's Cup Regatta.

Implements:
1. Continuous monotonic race progress along 44.39 deg course axis across legs.
2. Dynamic instantaneous leaderboard and final finish classification matching ground truth:
   FRA 1st (17m 39.5s), NZL G 2nd (+15.3s), ITA B 3rd (+18.4s), USA 4th (+53.6s),
   ITA G 5th (+88.4s), GBR G 6th (+107.0s), NZL B (DNF), SUI (DNF), GBR B (RET).
3. Distance and time gaps to leader (in metres and seconds).
4. Start analysis tactical metrics: pre-start timing, distance to line, projected crossing, delta to gun.
5. Head-to-head pairwise comparative metrics: separation vector, lateral delta, along-course advance, closure rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any

from pipeline.config import KNOTS_TO_MPS

from pipeline.reconstruction import (
    GUN_TIME_EPOCH_MS,
    COURSE_AXIS_SETTLED_DEG,
    compute_bow_position,
    compute_distance_to_start_line,
    CompetitorReconstruction,
)


@dataclass
class LeaderboardEntry:
    rank: int
    team_code: str
    team_name: str
    color: str
    status: str          # 'RACING' | 'FINISHED' | 'DNF' | 'RET' | 'OCS'
    current_leg: int
    progress_m: float
    gap_to_leader_m: float
    gap_to_leader_s: float
    sog_kt: float
    vmg_kt: float
    elapsed_s: Optional[float] = None


@dataclass
class HeadToHeadResult:
    euclidean_distance_m: float
    longitudinal_delta_m: float
    lateral_separation_m: float
    rate_of_closure_mps: float


@dataclass
class StartTacticalMetrics:
    countdown_s: float
    distance_to_line_m: float
    speed_towards_line_kt: float
    projected_crossing_time_ms: Optional[int]
    projected_delta_to_gun_s: Optional[float]
    is_ocs: bool


class AnalyticsEngine:
    """Computes race progress, rankings, tactical gaps, and comparative analytics."""

    def __init__(
        self,
        gun_time_ms: int = GUN_TIME_EPOCH_MS,
        course_axis_deg: float = COURSE_AXIS_SETTLED_DEG,
        nominal_leg_length_m: float = 2433.1,
        course_sequences: Optional[List[Dict[str, Any]]] = None,
    ):
        self.gun_time_ms = gun_time_ms
        self.course_axis_deg = course_axis_deg
        self.nominal_leg_length_m = nominal_leg_length_m
        self.course_sequences = course_sequences or []
        self.total_legs = len(self.course_sequences) - 1 if self.course_sequences else 4

        axis_rad = math.radians(course_axis_deg)
        # Upwind unit vector (towards top gate, bearing 44.39 deg)
        self.u_upwind = (math.sin(axis_rad), math.cos(axis_rad))
        # Downwind unit vector (towards bottom gate, bearing 224.39 deg)
        self.u_downwind = (-self.u_upwind[0], -self.u_upwind[1])
        # Perpendicular lateral vector
        self.u_lat = (-math.cos(axis_rad), math.sin(axis_rad))

    def compute_continuous_race_progress_for_boat(
        self,
        boat_code: str,
        boat_x: List[float],
        boat_y: List[float],
        boat_heading: List[float],
        timestamps: List[int],
        competitor_rec: CompetitorReconstruction,
        marks: Dict[str, Any],
    ) -> Tuple[List[float], List[int]]:
        """Computes continuous monotonic race progress in metres and current leg number per frame."""
        n = len(timestamps)
        progress_m: List[float] = [0.0] * n
        leg_numbers: List[int] = [0] * n

        if competitor_rec.classification == "RET" or competitor_rec.start.ocs:
            # GBR B: OCS, retired
            return progress_m, leg_numbers

        # Gate timing boundaries and nominal gate midpoints for this course.
        t_start = competitor_rec.start.crossing_time or self.gun_time_ms
        crossings = sorted(competitor_rec.gates, key=lambda gate: gate.crossing_time)
        gate_midpoints: Dict[int, Tuple[float, float]] = {}
        if self.course_sequences:
            asset_to_mark = {mark.asset_id: mark for mark in marks.values()}
            for leg, sequence in enumerate(self.course_sequences):
                gate = sequence.get("gate", {})
                port = asset_to_mark.get(gate.get("port_asset_id"))
                starboard = asset_to_mark.get(gate.get("starboard_asset_id"))
                if port and starboard:
                    gate_midpoints[leg] = (
                        (port.target_x + starboard.target_x) / 2.0,
                        (port.target_y + starboard.target_y) / 2.0,
                    )
        else:
            for leg in range(self.total_legs + 1):
                p_code, s_code = ("RM8", "RM6") if leg % 2 == 0 else ("RM4", "RM2")
                if p_code in marks and s_code in marks:
                    gate_midpoints[leg] = (
                        (marks[p_code].target_x + marks[s_code].target_x) / 2.0,
                        (marks[p_code].target_y + marks[s_code].target_y) / 2.0,
                    )

        # Leg vectors
        d_leg = self.nominal_leg_length_m
        d_total = self.total_legs * d_leg

        max_progress_so_far = 0.0

        for i in range(n):
            t = timestamps[i]

            if t < t_start:
                # Pre-start: Leg 0, progress 0
                leg_numbers[i] = 0
                progress_m[i] = 0.0
                continue

            bx, by = compute_bow_position(boat_x[i], boat_y[i], boat_heading[i])

            if competitor_rec.finish_time_ms and t >= competitor_rec.finish_time_ms:
                leg = self.total_legs
                p_inst = d_total
            else:
                leg = 1
                for gate in crossings:
                    if t >= gate.crossing_time:
                        leg = max(leg, min(self.total_legs, gate.leg + 1))
                    else:
                        break
                origin = gate_midpoints.get(leg - 1)
                if origin is None:
                    p_inst = (leg - 1) * d_leg
                else:
                    direction = self.u_upwind if leg % 2 else self.u_downwind
                    advance = (bx - origin[0]) * direction[0] + (by - origin[1]) * direction[1]
                    p_inst = (leg - 1) * d_leg + max(0.0, min(d_leg, advance))

            # Maintain monotonicity during active racing
            if p_inst > max_progress_so_far:
                max_progress_so_far = p_inst

            # If finished, clamp strictly to total race distance
            if competitor_rec.finish_time_ms and t >= competitor_rec.finish_time_ms:
                progress_m[i] = round(d_total, 2)
            else:
                progress_m[i] = round(max_progress_so_far, 2)

            leg_numbers[i] = leg

        return progress_m, leg_numbers

    def compute_instantaneous_leaderboard(
        self,
        frame_idx: int,
        timestamp_ms: int,
        boats_data: Dict[str, Any],
        boats_progress: Dict[str, List[float]],
        boats_leg: Dict[str, List[int]],
        competitors_rec: Dict[str, CompetitorReconstruction],
    ) -> List[LeaderboardEntry]:
        """Calculates live leaderboard standings and gaps at a specific timestamp."""
        entries: List[LeaderboardEntry] = []

        for code, comp in competitors_rec.items():
            b_data = boats_data[code]
            prog = boats_progress[code][frame_idx]
            leg = boats_leg[code][frame_idx]
            sog = b_data.sog_kt[frame_idx] if frame_idx < len(b_data.sog_kt) else 0.0
            vmg = b_data.vmg_kt[frame_idx] if frame_idx < len(b_data.vmg_kt) else 0.0

            # Determine live status
            if comp.classification == "RET" or comp.start.ocs:
                status = "RET"
            elif comp.finish_time_ms and timestamp_ms >= comp.finish_time_ms:
                status = "FINISHED"
            elif timestamp_ms < (comp.start.crossing_time or self.gun_time_ms):
                status = "PRE_START"
            else:
                status = "RACING"

            entry = LeaderboardEntry(
                rank=0,
                team_code=code,
                team_name=comp.team_name,
                color=comp.color,
                status=status,
                current_leg=leg,
                progress_m=prog,
                gap_to_leader_m=0.0,
                gap_to_leader_s=0.0,
                sog_kt=round(sog, 1),
                vmg_kt=round(vmg, 1),
                elapsed_s=comp.elapsed_s if status == "FINISHED" else None,
            )
            entries.append(entry)

        # Sorting rules for leaderboard:
        # 1. Finished boats sorted by finish_time_ms ascending
        # 2. Racing boats sorted by current_leg descending, then progress_m descending
        # 3. Pre-start boats sorted by team_code
        # 4. Retired boats at bottom
        def sort_key(e: LeaderboardEntry):
            comp = competitors_rec[e.team_code]
            if e.status == "FINISHED":
                return (0, comp.finish_time_ms or 0, 0)
            elif e.status == "RACING":
                return (1, -e.current_leg, -e.progress_m)
            elif e.status == "PRE_START":
                return (2, 0, e.team_code)
            else:  # RET
                return (3, 0, e.team_code)

        entries.sort(key=sort_key)

        # Compute ranks and gaps to leader
        leader = entries[0]
        leader_prog = leader.progress_m

        for rank, e in enumerate(entries, start=1):
            e.rank = rank
            if rank == 1:
                e.gap_to_leader_m = 0.0
                e.gap_to_leader_s = 0.0
            else:
                comp = competitors_rec[e.team_code]
                leader_comp = competitors_rec[leader.team_code]
                if e.status == "FINISHED" and leader.status == "FINISHED":
                    delta_s = ((comp.finish_time_ms or 0) - (leader_comp.finish_time_ms or 0)) / 1000.0
                    e.gap_to_leader_s = round(max(0.0, delta_s), 1)
                    e.gap_to_leader_m = 0.0
                elif e.status == "RET":
                    e.gap_to_leader_m = 0.0
                    e.gap_to_leader_s = 0.0
                else:
                    dist_gap = max(0.0, leader_prog - e.progress_m)
                    e.gap_to_leader_m = round(dist_gap, 1)
                    # Since dist_gap is projected along the course axis (VMG space), divide by
                    # leader leg VMG; fall back to 0.75 * SOG during tack/gybe VMG dips.
                    if abs(leader.vmg_kt) >= 8.0:
                        ref_vmg_kt = abs(leader.vmg_kt)
                    elif leader.sog_kt > 0:
                        ref_vmg_kt = leader.sog_kt * 0.75
                    else:
                        ref_vmg_kt = 15.55
                    leader_vmg_mps = max(4.0, ref_vmg_kt * KNOTS_TO_MPS)
                    time_gap = dist_gap / leader_vmg_mps
                    e.gap_to_leader_s = round(time_gap, 1)

        return entries

    def compute_head_to_head_metrics(
        self,
        pos_a: Tuple[float, float],
        pos_b: Tuple[float, float],
        vel_a: Tuple[float, float],
        vel_b: Tuple[float, float],
    ) -> HeadToHeadResult:
        """Computes pairwise comparative metrics between Boat A and Boat B."""
        sep_x = pos_a[0] - pos_b[0]
        sep_y = pos_a[1] - pos_b[1]
        euclidean_dist = math.hypot(sep_x, sep_y)

        # Longitudinal along course axis
        delta_long = sep_x * self.u_upwind[0] + sep_y * self.u_upwind[1]

        # Lateral perpendicular to course axis
        delta_lat = abs(sep_x * self.u_lat[0] + sep_y * self.u_lat[1])

        # Rate of closure: (v_b - v_a) . (pos_a - pos_b) / distance
        rel_vx = vel_b[0] - vel_a[0]
        rel_vy = vel_b[1] - vel_a[1]
        if euclidean_dist > 1e-6:
            closure_rate = (rel_vx * sep_x + rel_vy * sep_y) / euclidean_dist
        else:
            closure_rate = 0.0

        return HeadToHeadResult(
            euclidean_distance_m=round(euclidean_dist, 2),
            longitudinal_delta_m=round(delta_long, 2),
            lateral_separation_m=round(delta_lat, 2),
            rate_of_closure_mps=round(closure_rate, 2),
        )

    def compute_start_tactical_metrics(
        self,
        timestamp_ms: int,
        bow_pos: Tuple[float, float],
        velocity_mps: Tuple[float, float],
        m_port: Tuple[float, float],
        m_starboard: Tuple[float, float],
    ) -> StartTacticalMetrics:
        """Computes live start countdown, distance to line, and projected crossing delta."""
        countdown_s = (timestamp_ms - self.gun_time_ms) / 1000.0
        d_line = compute_distance_to_start_line(bow_pos, m_port, m_starboard)

        # Line normal pointing upwind
        dx = m_port[0] - m_starboard[0]
        dy = m_port[1] - m_starboard[1]
        length = math.hypot(dx, dy)
        nx = -dy / length
        ny = dx / length
        if nx * self.u_upwind[0] + ny * self.u_upwind[1] < 0:
            nx, ny = -nx, -ny

        # Velocity towards line
        v_perp = velocity_mps[0] * nx + velocity_mps[1] * ny
        speed_towards_kt = max(0.0, v_perp * 1.94384449)

        # Projected crossing
        t_proj: Optional[int] = None
        delta_proj_s: Optional[float] = None
        if d_line < 0 and v_perp > 0.5:
            tau_s = -d_line / v_perp
            t_proj = int(round(timestamp_ms + tau_s * 1000.0))
            delta_proj_s = round((t_proj - self.gun_time_ms) / 1000.0, 2)

        is_ocs = (d_line > 0 and timestamp_ms <= self.gun_time_ms)

        return StartTacticalMetrics(
            countdown_s=round(countdown_s, 2),
            distance_to_line_m=round(d_line, 2),
            speed_towards_line_kt=round(speed_towards_kt, 2),
            projected_crossing_time_ms=t_proj,
            projected_delta_to_gun_s=delta_proj_s,
            is_ocs=is_ocs,
        )
