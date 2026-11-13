"""Kinematic and statistical models for AC75 simulation (T15/P3).

Implements:
1. Physical match race phase and team profile modeling:
   - TeamKinematicProfile
   - PhaseDurationModel
   - NonFinishModel (DNS, DNF_exogenous, OCS_DSQ)
   - EmpiricalPhaseDistributionModel
   - build_default_phase_models
2. Standardized candidate model adapters:
   - BaseCandidateModel
   - EmpiricalPolarCandidate (order 1)
   - SplinePolarCandidate (order 2)
   - NeuralPolarCandidate (order 3)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Mapping, Sequence

import numpy as np

from pipeline.kinematic_ml.course_lvc import CoursePreset
from .candidates import (
    BaseCandidateModel,
    EmpiricalPolarCandidate,
    NeuralPolarCandidate,
    SplinePolarCandidate,
)


@dataclass
class TeamKinematicProfile:
    """Team-specific physical parameters shrunken toward fleet priors."""
    team_id: str
    delta_v_up_kt: float = 0.0
    delta_v_dn_kt: float = 0.0
    mean_tack_loss_s: float = 3.2
    mean_gybe_loss_s: float = 2.4
    start_line_offset_s: float = 0.0
    reliability_factor: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PhaseDurationModel:
    """Predicts duration quantiles and draws per race phase (backward compatible)."""
    phase_name: str
    base_duration_s: float
    wind_sensitivity: float = -0.5  # Seconds faster per knot of wind
    team_spread_s: float = 1.2      # Between-team variation in seconds
    nu: float = 4.0                 # Degrees of freedom for Student-t innovation

    def sample_duration(
        self,
        tws_kt: float,
        team_offset: float,
        rng: np.random.Generator,
        size: int = 1,
    ) -> np.ndarray:
        """Samples phase duration with Student-t heavy-tailed error."""
        mu = self.base_duration_s + self.wind_sensitivity * (tws_kt - 12.0) - team_offset * self.team_spread_s
        mu = max(10.0, mu)
        t_draws = rng.standard_t(df=self.nu, size=size)
        scale = 2.5
        durations = mu + t_draws * scale
        return np.maximum(durations, 5.0)


@dataclass
class NonFinishModel:
    """Categorical separation of non-finish states: DNS, DNF_exogenous, OCS_DSQ."""
    p_dns_base: float = 0.008
    p_dnf_base: float = 0.022
    p_dsq_base: float = 0.005

    def sample_status(
        self,
        tws_kt: float,
        reliability_factor: float,
        rng: np.random.Generator,
        size: int = 1,
    ) -> np.ndarray:
        """Samples race completion status: 'FINISHED', 'DNS', 'DNF_exogenous', or 'OCS_DSQ'."""
        wind_factor = 1.0 + max(0.0, (tws_kt - 15.0) * 0.1)
        rel = max(0.2, reliability_factor)
        p_dns = self.p_dns_base / rel
        p_dnf = (self.p_dnf_base * wind_factor) / rel
        p_dsq = self.p_dsq_base

        p_finished = max(0.0, 1.0 - (p_dns + p_dnf + p_dsq))
        probs = [p_finished, p_dns, p_dnf, p_dsq]
        probs = np.array(probs) / np.sum(probs)

        choices = ["FINISHED", "DNS", "DNF_exogenous", "OCS_DSQ"]
        return rng.choice(choices, size=size, p=probs)


def build_default_phase_models() -> dict[str, PhaseDurationModel]:
    return {
        "pre_start": PhaseDurationModel("pre_start", base_duration_s=120.0, wind_sensitivity=-0.1, team_spread_s=0.8),
        "upwind_leg_1": PhaseDurationModel("upwind_leg_1", base_duration_s=240.0, wind_sensitivity=-3.5, team_spread_s=3.0),
        "downwind_leg_1": PhaseDurationModel("downwind_leg_1", base_duration_s=180.0, wind_sensitivity=-2.8, team_spread_s=2.5),
        "upwind_leg_2": PhaseDurationModel("upwind_leg_2", base_duration_s=235.0, wind_sensitivity=-3.4, team_spread_s=3.0),
        "downwind_leg_2": PhaseDurationModel("downwind_leg_2", base_duration_s=175.0, wind_sensitivity=-2.7, team_spread_s=2.5),
        "finish_leg": PhaseDurationModel("finish_leg", base_duration_s=60.0, wind_sensitivity=-0.8, team_spread_s=0.8),
    }


@dataclass
class EmpiricalPhaseDistributionModel:
    """Physical telemetry-parameterized match race model.

    Computes leg travel times directly from course distance and physical VMG speeds,
    parameterizes team speed differentials shrunken by tau_team,
    samples maneuver execution losses separately from steady VMG time,
    and supports explicit rule adjustment parameters.
    """
    v_up_0: float = 17.0            # Baseline upwind VMG at 12 kt (kt)
    v_dn_0: float = 27.5            # Baseline downwind VMG at 12 kt (kt)
    alpha_wind_up: float = 0.35     # Upwind VMG sensitivity to wind (kt / kt TWS)
    alpha_wind_dn: float = 0.55     # Downwind VMG sensitivity to wind (kt / kt TWS)
    tack_loss_base_s: float = 3.2   # Mean tack loss (s)
    gybe_loss_base_s: float = 2.4   # Mean gybe loss (s)
    team_profiles: dict[str, TeamKinematicProfile] = field(default_factory=dict)
    nu: float = 4.0                 # Degrees of freedom for Student-t error innovations
    non_finish_model: NonFinishModel = field(default_factory=NonFinishModel)

    def get_profile(self, team_id: str) -> TeamKinematicProfile:
        return self.team_profiles.get(team_id, TeamKinematicProfile(team_id=team_id))

    @classmethod
    def load_from_primitives(
        cls,
        primitives: Mapping[str, Any] | None = None,
        team_effects: Mapping[str, float] | None = None,
    ) -> EmpiricalPhaseDistributionModel:
        """Constructs an EmpiricalPhaseDistributionModel from AC75 primitives and optional team effects."""
        v_up = 17.0
        v_dn = 27.5
        tack_loss = 3.2
        gybe_loss = 2.4

        if primitives:
            up_vmg = primitives.get("upwind_vmg_kt", {})
            dn_vmg = primitives.get("downwind_vmg_kt", {})
            if "10-13kt" in up_vmg and "p50" in up_vmg["10-13kt"]:
                v_up = float(up_vmg["10-13kt"]["p50"])
            if "10-13kt" in dn_vmg and "p50" in dn_vmg["10-13kt"]:
                v_dn = float(dn_vmg["10-13kt"]["p50"])
            
            manoeuvres = primitives.get("manoeuvres", {})
            if "tack_loss_s" in manoeuvres and "p50" in manoeuvres["tack_loss_s"]:
                tack_loss = float(manoeuvres["tack_loss_s"]["p50"])
            if "gybe_loss_s" in manoeuvres and "p50" in manoeuvres["gybe_loss_s"]:
                gybe_loss = float(manoeuvres["gybe_loss_s"]["p50"])

        profiles = {}
        if team_effects:
            for team, effect in team_effects.items():
                eff = float(effect)
                profiles[team] = TeamKinematicProfile(
                    team_id=team,
                    delta_v_up_kt=eff * 0.35,
                    delta_v_dn_kt=eff * 0.45,
                    mean_tack_loss_s=max(1.5, tack_loss - eff * 0.15),
                    mean_gybe_loss_s=max(1.2, gybe_loss - eff * 0.12),
                    start_line_offset_s=eff * 0.4,
                    reliability_factor=max(0.4, 1.0 + eff * 0.15),
                )

        return cls(
            v_up_0=v_up,
            v_dn_0=v_dn,
            tack_loss_base_s=tack_loss,
            gybe_loss_base_s=gybe_loss,
            team_profiles=profiles,
        )

    @classmethod
    def fit_from_telemetry(
        cls,
        features: Sequence[Mapping[str, Any]],
        races: Sequence[Mapping[str, Any]],
        tau_team: float = 0.30,
    ) -> EmpiricalPhaseDistributionModel:
        """Fits team speed differentials from telemetry features shrunken by tau_team."""
        canonical_map = {
            "SUI": "ALINGHI", "USA": "AMERICAN_MAGIC", "NZL": "ETNZ",
            "GBR": "INEOS", "GB1": "GB1", "ITA": "LUNA_ROSSA", "FRA": "ORIENT_EXPRESS"
        }

        team_sogs: dict[str, list[float]] = {}
        team_tacks: dict[str, list[float]] = {}
        team_gybes: dict[str, list[float]] = {}

        for feat in features:
            team = feat.get("team_label", feat.get("asset_id", ""))
            team = canonical_map.get(team, team)
            sog = feat.get("mean_sog_kt")
            if sog is not None and math.isfinite(sog):
                team_sogs.setdefault(team, []).append(float(sog))
            for turn in feat.get("turns", []):
                loss = turn.get("loss_s")
                if loss is not None and math.isfinite(loss):
                    tt = turn.get("turn_type")
                    if tt == "tack":
                        team_tacks.setdefault(team, []).append(float(loss))
                    elif tt == "gybe":
                        team_gybes.setdefault(team, []).append(float(loss))

        all_sogs = [s for s_list in team_sogs.values() for s in s_list]
        fleet_mean_sog = float(np.mean(all_sogs)) if all_sogs else 25.0
        
        all_tacks = [t for t_list in team_tacks.values() for t in t_list]
        fleet_mean_tack = float(np.mean(all_tacks)) if all_tacks else 3.2

        all_gybes = [g for g_list in team_gybes.values() for g in g_list]
        fleet_mean_gybe = float(np.mean(all_gybes)) if all_gybes else 2.4

        profiles = {}
        tau_sq_inv = 1.0 / (tau_team ** 2) if tau_team > 0 else 100.0

        all_teams = set(list(team_sogs.keys()) + list(canonical_map.values()))
        for team in all_teams:
            s_list = team_sogs.get(team, [])
            n_t = len(s_list)
            if n_t > 0:
                raw_diff = float(np.mean(s_list)) - fleet_mean_sog
                shrinkage = n_t / (n_t + tau_sq_inv)
                shrunk_diff = raw_diff * shrinkage
            else:
                shrunk_diff = 0.0

            t_list = team_tacks.get(team, [])
            m_tack = float(np.mean(t_list)) if t_list else fleet_mean_tack

            g_list = team_gybes.get(team, [])
            m_gybe = float(np.mean(g_list)) if g_list else fleet_mean_gybe

            profiles[team] = TeamKinematicProfile(
                team_id=team,
                delta_v_up_kt=shrunk_diff * 0.7,
                delta_v_dn_kt=shrunk_diff * 1.1,
                mean_tack_loss_s=m_tack,
                mean_gybe_loss_s=m_gybe,
                start_line_offset_s=shrunk_diff * 0.3,
                reliability_factor=1.0,
            )

        return cls(
            v_up_0=17.0,
            v_dn_0=27.5,
            tack_loss_base_s=fleet_mean_tack,
            gybe_loss_base_s=fleet_mean_gybe,
            team_profiles=profiles,
        )

    def sample_race_components(
        self,
        team_id: str,
        tws_kt: float,
        course: CoursePreset | Mapping[str, Any],
        rule_adjustments: Mapping[str, float] | None,
        rng: np.random.Generator,
        size: int = 1,
    ) -> dict[str, np.ndarray]:
        """Samples the 7 distinct physical time components for a given team."""
        profile = self.get_profile(team_id)

        if isinstance(course, CoursePreset):
            course_length_m = course.course_length_m
            axis_length_nmi = course.axis_length_nmi
            leg_count = course.leg_count
            gate_width_m = getattr(course, "gate_width_m", 50.0)
        else:
            course_length_m = float(course.get("course_length_m", 2590.0))
            axis_length_nmi = float(course.get("axis_length_nmi", course_length_m / 1852.0))
            leg_count = int(course.get("leg_count", 6))
            gate_width_m = float(course.get("gate_width_m", 50.0))

        rules = rule_adjustments or {}
        battery_power_offset = float(rules.get("battery_power_offset_kt", rules.get("cyclor_power_boost_kt", 0.0)))
        maneuver_loss_mult = float(rules.get("maneuver_loss_multiplier", 1.0))
        foil_span_factor = float(rules.get("foil_span_factor", rules.get("foil_span_limit_factor", 1.0)))

        leg_dist_m = axis_length_nmi * 1852.0

        v_up = max(
            4.0,
            (self.v_up_0 + self.alpha_wind_up * (tws_kt - 12.0) + profile.delta_v_up_kt + battery_power_offset)
            * (1.0 + 0.15 * (foil_span_factor - 1.0))
        )
        v_dn = max(
            5.0,
            (self.v_dn_0 + self.alpha_wind_dn * (tws_kt - 12.0) + profile.delta_v_dn_kt + battery_power_offset)
            * (1.0 + 0.12 * (foil_span_factor - 1.0))
        )

        v_up_mps = v_up * 0.514444
        v_dn_mps = v_dn * 0.514444

        t_vmg_up_leg = leg_dist_m / v_up_mps
        t_vmg_dn_leg = leg_dist_m / v_dn_mps

        n_upwind = (leg_count + 1) // 2
        n_downwind = leg_count // 2

        n_tacks_per_leg = max(2, int(round(3.0 * (axis_length_nmi / 1.5) * (40.0 / max(25.0, gate_width_m)))))
        n_gybes_per_leg = max(2, int(round(2.5 * (axis_length_nmi / 1.5))))

        total_tacks = n_upwind * n_tacks_per_leg
        total_gybes = n_downwind * n_gybes_per_leg

        mu_pre_start = max(30.0, 120.0 - profile.start_line_offset_s)
        mu_upwind_vmg = n_upwind * t_vmg_up_leg
        mu_downwind_vmg = n_downwind * t_vmg_dn_leg
        mu_tacks = total_tacks * profile.mean_tack_loss_s * maneuver_loss_mult
        mu_gybes = total_gybes * profile.mean_gybe_loss_s * maneuver_loss_mult
        mu_boundary = 2.0
        mu_finish = 30.0

        t_draws = rng.standard_t(df=self.nu, size=(7, size))
        
        c_pre_start = np.maximum(10.0, mu_pre_start + t_draws[0] * 1.5)
        c_upwind = np.maximum(20.0, mu_upwind_vmg + t_draws[1] * 3.0)
        c_downwind = np.maximum(20.0, mu_downwind_vmg + t_draws[2] * 2.5)
        c_tacks = np.maximum(2.0, mu_tacks + t_draws[3] * 1.2)
        c_gybes = np.maximum(2.0, mu_gybes + t_draws[4] * 1.0)
        c_boundary = np.maximum(0.0, mu_boundary + t_draws[5] * 0.5)
        c_finish = np.maximum(5.0, mu_finish + t_draws[6] * 0.5)

        total_time = c_pre_start + c_upwind + c_downwind + c_tacks + c_gybes + c_boundary + c_finish

        return {
            "pre_start": c_pre_start,
            "upwind_vmg": c_upwind,
            "downwind_vmg": c_downwind,
            "tacks": c_tacks,
            "gybes": c_gybes,
            "boundary": c_boundary,
            "finish": c_finish,
            "total_time": total_time,
        }


__all__ = [
    "BaseCandidateModel",
    "EmpiricalCandidateModel",
    "EmpiricalPhaseDistributionModel",
    "EmpiricalPolarCandidate",
    "NeuralCandidateModel",
    "NeuralPolarCandidate",
    "NonFinishModel",
    "PhaseDurationModel",
    "SplineCandidateModel",
    "SplinePolarCandidate",
    "TeamKinematicProfile",
    "build_default_phase_models",
]

# Aliases for convenience
EmpiricalCandidateModel = EmpiricalPolarCandidate
SplineCandidateModel = SplinePolarCandidate
NeuralCandidateModel = NeuralPolarCandidate
