"""Tack and Gybe Manoeuvre Detector with Hysteresis and Performance Analytics.

Implements:
1. True Wind Angle (TWA) zero/pi sign transition detection:
   - Tack: Bow turns through the eye of the wind (TWA crosses through 0 deg).
   - Gybe: Stern turns through the eye of the wind (TWA crosses through +/-180 deg).
2. Rate of turn (ROT) and angular deflection hysteresis:
   - Heading deflection magnitude >= 50-60 deg.
   - Peak ROT >= 5.0 deg/s.
   - Speed dip >= 3.0 kt (1.5 m/s).
   - Tack stability duration >= 2.0-2.5 seconds (prevents chatter/false triggers).
   - ZERO false positives during steady-state straight runs with small heading corrections (<15 deg).
3. Performance metric derivation:
   - Entry speed (SOG at turn onset).
   - Minimum speed during manoeuvre.
   - Speed loss (entry - min).
   - Manoeuvre duration.
   - Recovery time (time from min speed until 90% of entry speed recovered).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Manoeuvre:
    type: str  # 'TACK' | 'GYBE'
    timestamp: int  # Epoch ms at peak turn / wind transition
    entry_speed_kt: float
    min_speed_kt: float
    speed_loss_kt: float
    recovery_time_s: float
    duration_s: float
    turn_delta_deg: float


def circular_shortest_diff_deg(from_deg: float, to_deg: float) -> float:
    """Computes shortest signed angular difference from from_deg to to_deg in [-180, 180)."""
    return ((to_deg - from_deg + 180.0) % 360.0) - 180.0


def normalize_angle_180(deg: float) -> float:
    """Normalizes angle to [-180.0, +180.0) degrees."""
    return ((deg + 180.0) % 360.0) - 180.0


class ManoeuvreDetector:
    """Detects and characterizes tacks and gybes from AC40 telemetry streams."""

    def __init__(
        self,
        min_heading_change_deg: float = 50.0,
        min_rot_deg_s: float = 5.0,
        min_speed_loss_kt: float = 2.5,
        min_tack_stability_s: float = 2.0,
        min_manoeuvre_separation_s: float = 8.0,
        sample_interval_ms: int = 100,
    ):
        self.min_heading_change_deg = min_heading_change_deg
        self.min_rot_deg_s = min_rot_deg_s
        self.min_speed_loss_kt = min_speed_loss_kt
        self.min_tack_stability_s = min_tack_stability_s
        self.min_manoeuvre_separation_s = min_manoeuvre_separation_s
        self.sample_interval_ms = sample_interval_ms
        self.sample_rate_hz = 1000.0 / sample_interval_ms

    def detect_manoeuvres_for_boat(
        self,
        timestamps: List[int],
        heading_deg: List[float],
        sog_kt: List[float],
        twa_deg: List[float],
        race_start_ms: Optional[int] = None,
        race_finish_ms: Optional[int] = None,
    ) -> List[Manoeuvre]:
        """Scans time series telemetry to extract validated tacks and gybes."""
        n = len(timestamps)
        if n < 30:
            return []

        dt_s = self.sample_interval_ms / 1000.0
        stability_samples = max(5, int(round(self.min_tack_stability_s * self.sample_rate_hz)))
        min_separation_samples = int(round(self.min_manoeuvre_separation_s * self.sample_rate_hz))

        # Compute smoothed rate of turn (ROT) in deg/s using 3-sample central difference
        rot_deg_s = [0.0] * n
        for i in range(1, n - 1):
            dh = circular_shortest_diff_deg(heading_deg[i - 1], heading_deg[i + 1])
            rot_deg_s[i] = abs(dh) / (2.0 * dt_s)

        manoeuvres: List[Manoeuvre] = []
        last_manoeuvre_idx = -min_separation_samples

        # Candidate scan: identify TWA sign transitions with stability
        i = stability_samples
        while i < n - stability_samples:
            t = timestamps[i]

            # Only detect during racing window if provided
            if race_start_ms is not None and t < race_start_ms:
                i += 1
                continue
            if race_finish_ms is not None and t > race_finish_ms:
                break

            # Enforce minimum separation from prior detected manoeuvre
            if i - last_manoeuvre_idx < min_separation_samples:
                i += 1
                continue

            twa_curr = normalize_angle_180(twa_deg[i])
            twa_prev = normalize_angle_180(twa_deg[i - stability_samples])
            twa_next = normalize_angle_180(twa_deg[i + stability_samples])

            # Check if there is a stable sign transition
            is_tack_candidate = False
            is_gybe_candidate = False

            # TACK: TWA crosses through 0 deg (|TWA| < 90 deg before and after, opposite signs)
            if (
                abs(twa_prev) < 95.0
                and abs(twa_next) < 95.0
                and (twa_prev * twa_next < -10.0)  # Distinct sign change
                and abs(twa_curr) < 40.0           # Near the eye of the wind
            ):
                is_tack_candidate = True

            # GYBE: TWA crosses through +/-180 deg (|TWA| > 85 deg before and after, opposite signs)
            elif (
                abs(twa_prev) > 85.0
                and abs(twa_next) > 85.0
                and (twa_prev * twa_next < -10.0)  # Opposite signs across 180/-180
                and abs(twa_curr) > 130.0          # Stern through wind
            ):
                is_gybe_candidate = True

            if not (is_tack_candidate or is_gybe_candidate):
                i += 1
                continue

            # Candidate found at index i. Now evaluate surrounding window [-6s, +6s] (60 samples)
            win_half = min(60, min(i, n - 1 - i))
            w_start = i - win_half
            w_end = i + win_half

            # Peak ROT in window
            peak_rot = max(rot_deg_s[w_start : w_end + 1])
            if peak_rot < self.min_rot_deg_s:
                i += 1
                continue

            # Find turn onset (start of turn where ROT rises > 2.0 deg/s)
            turn_start_idx = i
            while turn_start_idx > w_start and rot_deg_s[turn_start_idx] > 2.0:
                turn_start_idx -= 1

            # Find turn completion (where ROT drops back < 2.0 deg/s)
            turn_end_idx = i
            while turn_end_idx < w_end and rot_deg_s[turn_end_idx] > 2.0:
                turn_end_idx += 1

            if turn_end_idx <= turn_start_idx:
                i += 1
                continue

            # Total angular deflection across the turn
            hdg_start = heading_deg[turn_start_idx]
            hdg_end = heading_deg[turn_end_idx]
            turn_delta = abs(circular_shortest_diff_deg(hdg_start, hdg_end))

            if turn_delta < self.min_heading_change_deg:
                i += 1
                continue

            # Speed performance profile
            # Entry speed: speed before turn begins
            entry_idx = max(0, turn_start_idx - 5)
            entry_speed = max(sog_kt[entry_idx : turn_start_idx + 1]) if turn_start_idx >= entry_idx else sog_kt[turn_start_idx]

            # Minimum speed in turn window
            min_speed = min(sog_kt[turn_start_idx : turn_end_idx + 1])
            min_speed_idx = turn_start_idx + sog_kt[turn_start_idx : turn_end_idx + 1].index(min_speed)

            speed_loss = entry_speed - min_speed
            if speed_loss < self.min_speed_loss_kt:
                i += 1
                continue

            # Recovery time: time from min_speed until speed recovers to 90% of entry speed
            recovery_target = 0.90 * entry_speed
            rec_idx = min_speed_idx + 1
            max_rec_window = min(n - 1, min_speed_idx + int(15.0 * self.sample_rate_hz))
            recovered = False
            while rec_idx <= max_rec_window:
                if sog_kt[rec_idx] >= recovery_target:
                    recovered = True
                    break
                rec_idx += 1

            if recovered:
                recovery_time_s = (timestamps[rec_idx] - timestamps[min_speed_idx]) / 1000.0
            else:
                recovery_time_s = (timestamps[max_rec_window] - timestamps[min_speed_idx]) / 1000.0

            duration_s = (timestamps[turn_end_idx] - timestamps[turn_start_idx]) / 1000.0

            m_type = "TACK" if is_tack_candidate else "GYBE"
            manoeuvre = Manoeuvre(
                type=m_type,
                timestamp=timestamps[i],
                entry_speed_kt=round(entry_speed, 2),
                min_speed_kt=round(min_speed, 2),
                speed_loss_kt=round(speed_loss, 2),
                recovery_time_s=round(recovery_time_s, 2),
                duration_s=round(duration_s, 2),
                turn_delta_deg=round(turn_delta, 1),
            )
            manoeuvres.append(manoeuvre)
            last_manoeuvre_idx = turn_end_idx
            i = turn_end_idx + 5

        return manoeuvres
