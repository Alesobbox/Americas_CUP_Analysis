"""Frozen scientific and engineering contracts for AC37 AC75 learned simulation.

Enforces:
- Canonical AC37 identities and strict cycle-scoped alias resolution.
- Explicit SI units (m, m/s, deg, ms, s) and exact formula adapters.
- Information-time separation: predictor allowlists vs. targets (zero leakage).
- Scenario-v2 discriminated results with nullable probability objects.
- Content-addressed model identifiers (prohibiting filesystem paths).
- Legacy-v1 read compatibility without silent upgrading.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from pipeline.historical_analysis import leg_course_vmg_kt, wind_relative_vmg_kt

KNOTS_TO_MPS = 1852.0 / 3600.0  # 0.5144444444444445 m/s per knot
MPS_TO_KNOTS = 3600.0 / 1852.0  # 1.9438444924406048 knots per m/s


def knots_to_mps(speed_kt: float) -> float:
    """Convert international nautical knots to metres per second."""
    if not math.isfinite(speed_kt):
        raise ValueError(f"Speed in knots must be finite, got {speed_kt}")
    return speed_kt * KNOTS_TO_MPS


def mps_to_knots(speed_mps: float) -> float:
    """Convert metres per second to international nautical knots."""
    if not math.isfinite(speed_mps):
        raise ValueError(f"Speed in m/s must be finite, got {speed_mps}")
    return speed_mps * MPS_TO_KNOTS


def leg_course_vmg_mps(sog_mps: float, cog_deg: float, axis_deg: float, leg: int) -> float:
    """SI adapter for leg-directed course VMG. Reuses pipeline.historical_analysis owner."""
    if not math.isfinite(sog_mps) or sog_mps < 0:
        raise ValueError(f"SOG must be non-negative and finite, got {sog_mps}")
    sog_kt = mps_to_knots(sog_mps)
    vmg_kt = leg_course_vmg_kt(sog_kt, cog_deg, axis_deg, leg)
    return knots_to_mps(vmg_kt)


def wind_relative_vmg_mps(sog_mps: float, cog_deg: float, twd_deg: float, upwind: bool) -> float:
    """SI adapter for wind-relative VMG. Reuses pipeline.historical_analysis owner."""
    if not math.isfinite(sog_mps) or sog_mps < 0:
        raise ValueError(f"SOG must be non-negative and finite, got {sog_mps}")
    sog_kt = mps_to_knots(sog_mps)
    vmg_kt = wind_relative_vmg_kt(sog_kt, cog_deg, twd_deg, upwind)
    return knots_to_mps(vmg_kt)


class BoatClass(str, Enum):
    AC75 = "AC75"
    AC40 = "AC40"


class RaceStage(str, Enum):
    OFFICIAL_PRACTICE = "official_practice"
    PRELIMINARY = "preliminary"
    ROUND_ROBIN = "round_robin"
    SEMIFINAL = "semifinal"
    FINAL = "final"
    MATCH = "match"


class LegType(str, Enum):
    UPWIND = "upwind"
    DOWNWIND = "downwind"


class TurnType(str, Enum):
    TACK = "tack"
    GYBE = "gybe"
    PENALTY_TURN = "penalty_turn"
    MARK_ROUNDING = "mark_rounding"


class ScenarioPurpose(str, Enum):
    PREVIEW = "preview"
    STANDARD = "standard"
    EVALUATION = "evaluation"


class ScenarioStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class ProbabilityScope(str, Enum):
    COMPLETION_ASSUMED_ON_WATER = "completion_assumed_on_water"
    UNCONDITIONAL_REVIEWED = "unconditional_reviewed"


class ManeuverCensoring(str, Enum):
    UNCENSORED = "uncensored"
    RIGHT_CENSORED_TIME_LIMIT = "right_censored_time_limit"
    RIGHT_CENSORED_GAP = "right_censored_gap"
    RIGHT_CENSORED_NEXT_EVENT = "right_censored_next_event"
    RIGHT_CENSORED_TERMINAL = "right_censored_terminal"


class NonFinishReason(str, Enum):
    DNS = "DNS"
    DNF_EXOGENOUS = "DNF_exogenous"
    OCS_DSQ = "OCS_DSQ"
    UNRESOLVED_SIMULATION = "unresolved_simulation"


CANONICAL_AC37_TEAMS = frozenset({
    "ac37:ETNZ",
    "ac37:INEOS",
    "ac37:LUNA_ROSSA",
    "ac37:AMERICAN_MAGIC",
    "ac37:ALINGHI",
    "ac37:ORIENT_EXPRESS",
})

# Display aliases valid only in AC37 historical scope
_AC37_DISPLAY_ALIASES = {
    "ETNZ": "ac37:ETNZ",
    "NZL": "ac37:ETNZ",
    "EMIRATES TEAM NEW ZEALAND": "ac37:ETNZ",
    "INEOS": "ac37:INEOS",
    "GBR": "ac37:INEOS",
    "GB1": "ac37:INEOS",  # Display alias inside AC37 only
    "INEOS BRITANNIA": "ac37:INEOS",
    "LUNA_ROSSA": "ac37:LUNA_ROSSA",
    "ITA": "ac37:LUNA_ROSSA",
    "LUNA ROSSA PRADA PIRELLI": "ac37:LUNA_ROSSA",
    "AMERICAN_MAGIC": "ac37:AMERICAN_MAGIC",
    "USA": "ac37:AMERICAN_MAGIC",
    "NYYC AMERICAN MAGIC": "ac37:AMERICAN_MAGIC",
    "ALINGHI": "ac37:ALINGHI",
    "SUI": "ac37:ALINGHI",
    "ALINGHI RED BULL RACING": "ac37:ALINGHI",
    "ORIENT_EXPRESS": "ac37:ORIENT_EXPRESS",
    "FRA": "ac37:ORIENT_EXPRESS",
    "ORIENT EXPRESS RACING TEAM": "ac37:ORIENT_EXPRESS",
}

# Known AC38 identities that must NOT be silently matched to AC37 observations
_AC38_NON_AC37_TEAMS = frozenset({
    "ac38:GB1",
    "ac38:ARC_USA",
    "ac38:LA_ROCHE_POSAY",
    "ac38:AUSTRALIA",
    "ARC_USA",
    "LA_ROCHE_POSAY",
    "AUSTRALIA",
})


class UnsupportedIdentityError(ValueError):
    """Raised when an identity is not supported in the requested historical scope."""
    pass


def resolve_team_identity(raw_id: str, *, cycle: str = "AC37") -> str:
    """Resolve raw or display team identity strictly within the specified cycle.
    
    In AC37 cycle:
    - Canonical IDs ('ac37:ETNZ', etc.) pass through.
    - Historic display aliases ('GB1', 'INEOS', 'NZL', etc.) resolve to canonical 'ac37:*'.
    - Unknown teams or AC38-specific entrants raise UnsupportedIdentityError.
    
    If cycle is not AC37 (e.g. 'AC38'):
    - Historical aliases like GB1 do NOT resolve to ac37:INEOS.
    """
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise UnsupportedIdentityError("Team identifier must be a non-empty string")
    
    clean_id = raw_id.strip()

    if cycle == "AC37":
        if clean_id in CANONICAL_AC37_TEAMS:
            return clean_id
        
        # Check explicit AC38 forbidden names
        if clean_id in _AC38_NON_AC37_TEAMS:
            raise UnsupportedIdentityError(
                f"Identity '{clean_id}' is an AC38 entrant and cannot be matched to AC37 observations"
            )
        
        # Resolve via AC37 alias mapping
        upper_id = clean_id.upper()
        if upper_id in _AC37_DISPLAY_ALIASES:
            return _AC37_DISPLAY_ALIASES[upper_id]
        
        raise UnsupportedIdentityError(
            f"Unknown or unsupported team '{clean_id}' for cycle AC37. "
            f"Supported canonical teams: {sorted(CANONICAL_AC37_TEAMS)}"
        )
    else:
        # Non-AC37 cycle: GB1 must NOT resolve to ac37:INEOS
        if clean_id.upper() == "GB1" or clean_id in _AC37_DISPLAY_ALIASES:
            raise UnsupportedIdentityError(
                f"Historical alias '{clean_id}' cannot be resolved outside AC37 cycle (requested: {cycle})"
            )
        raise UnsupportedIdentityError(f"Unsupported cycle '{cycle}' for team resolution")


MOTION_PREDICTOR_ALLOWLIST = frozenset({
    "tws_mps",
    "twa_sin",
    "twa_cos",
    "tack_side",  # -1 = port, 1 = starboard
    "leg_type",   # 0 = downwind, 1 = upwind
    "course_wind_angle_deg",
    "heading_cog_offset_deg",
    "team_id",
    "practice_domain",  # boolean: 0 = competitive, 1 = practice
})

MOTION_TARGET_ALLOWLIST = frozenset({
    "sog_mps",
    "mu_log_mps",
    "sigma_log",
    "ground_vmg_mps",
    "wind_vmg_mps",
})

EVENT_PREDICTOR_ALLOWLIST = frozenset({
    "turn_type",
    "entry_speed_predicted_mps",  # Out-of-fold predicted speed at turn onset
    "rotation_deg",
    "tws_mps",
    "team_id",
    "leg_type",
})

EVENT_TARGET_ALLOWLIST = frozenset({
    "duration_s",
    "recovery_s",
    "total_event_s",
    "censoring",
    "exit_speed_mps",
})

SCENARIO_INPUT_ALLOWLIST = frozenset({
    "schema_version",
    "model_id",
    "team_a",
    "team_b",
    "course_id",
    "environment",
    "purpose",
    "scenario_policy_id",
    "seed",         # Optional, CLI/numerical path only
    "trial_count",  # Optional, CLI/numerical path only
})

FORBIDDEN_MOTION_PREDICTORS = frozenset({
    "sog_mps",
    "cog_deg",
    "future_tws_mps",
    "future_heading_deg",
    "maneuver_count",
    "finish_order",
    "race_margin_s",
    "rating_post_race",
})


def validate_feature_separation(features: Mapping[str, Any], task_type: str = "motion") -> None:
    """Validate that features strictly conform to declared allowlists with no extra or leaky variables."""
    feature_keys = set(features.keys())
    
    if task_type == "motion":
        disallowed = feature_keys - MOTION_PREDICTOR_ALLOWLIST
        if disallowed:
            raise ValueError(
                f"Disallowed or leaky keys in motion features (must conform to MOTION_PREDICTOR_ALLOWLIST): {sorted(disallowed)}"
            )
    elif task_type == "event":
        disallowed = feature_keys - EVENT_PREDICTOR_ALLOWLIST
        if disallowed:
            raise ValueError(
                f"Disallowed or leaky keys in event features (must conform to EVENT_PREDICTOR_ALLOWLIST): {sorted(disallowed)}"
            )
    elif task_type == "scenario":
        unknown_keys = feature_keys - SCENARIO_INPUT_ALLOWLIST
        if unknown_keys:
            raise ValueError(f"Unknown or forbidden keys in scenario request: {sorted(unknown_keys)}")
    else:
        raise ValueError(f"Unknown task_type '{task_type}' (expected 'motion', 'event', or 'scenario')")


@dataclass(frozen=True)
class SourceManifestRecord:
    """Schema: ac75-source-1"""
    schema_version: str = "ac75-source-1"
    relative_path: str = ""
    bytes: int = 0
    sha256: str = ""
    format: str = "jsonl"  # 'jsonl' or 'ac37'
    class_evidence: str = "AC75"
    stage: str = ""
    t_min_ms: int | None = None
    t_max_ms: int | None = None
    record_count: int = 0
    status: str = "included"  # 'included', 'duplicate', 'excluded', 'unsupported_wire_schema'
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SteadyWindowRecord:
    """Schema: ac75-features-1"""
    schema_version: str = "ac75-features-1"
    attempt_id: str = ""
    team_id: str = ""
    t_start_ms: int = 0
    t_end_ms: int = 0
    duration_s: float = 5.0
    tws_mps: float = 0.0
    twa_sin: float = 0.0
    twa_cos: float = 0.0
    tack_side: int = 1
    leg_type: int = 1
    course_wind_angle_deg: float = 0.0
    heading_cog_offset_deg: float = 0.0
    practice_domain: int = 0
    sog_mps: float = 0.0
    supported_fraction: float = 1.0
    max_gap_ms: int = 0
    status: str = "valid"
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ManeuverRecord:
    """Schema: ac75-maneuvers-1"""
    schema_version: str = "ac75-maneuvers-1"
    maneuver_id: str = ""
    attempt_id: str = ""
    team_id: str = ""
    turn_type: str = "tack"
    t_start_ms: int = 0
    t_end_ms: int = 0
    duration_s: float = 0.0
    recovery_s: float | None = None
    total_event_s: float = 0.0
    rotation_deg: float = 0.0
    entry_sog_mps: float = 0.0
    min_sog_mps: float = 0.0
    censoring: str = "uncensored"
    review_status: str = "provisional"


@dataclass(frozen=True)
class ScenarioProbabilityDetail:
    """Structured nullable probability object."""
    win_a: float
    win_b: float
    no_winner: float | None = None
    mc_error: float | None = None

    def __post_init__(self):
        for v in (self.win_a, self.win_b):
            if not math.isfinite(v) or v < 0.0 or v > 1.0:
                raise ValueError(f"Win probability must be in [0, 1], got {v}")
        if self.no_winner is not None:
            if not math.isfinite(self.no_winner) or self.no_winner < 0.0 or self.no_winner > 1.0:
                raise ValueError(f"no_winner probability must be in [0, 1], got {self.no_winner}")
        if self.mc_error is not None:
            if not math.isfinite(self.mc_error) or self.mc_error < 0.0 or self.mc_error > 0.5:
                raise ValueError(f"mc_error must be in [0, 0.5], got {self.mc_error}")


@dataclass(frozen=True)
class ScenarioTimingDetail:
    """Structured timing object with central 80% interval."""
    mean_time_a_s: float
    mean_time_b_s: float
    mean_delta_t_s: float
    central_80_margin_interval_s: tuple[float, float]

    def __post_init__(self):
        for v in (self.mean_time_a_s, self.mean_time_b_s, self.mean_delta_t_s):
            if not math.isfinite(v):
                raise ValueError(f"Timing values must be finite, got {v}")
        p10, p90 = self.central_80_margin_interval_s
        if not math.isfinite(p10) or not math.isfinite(p90) or p10 > p90:
            raise ValueError(f"Invalid central 80% interval: [{p10}, {p90}]")


@dataclass(frozen=True)
class ScenarioV2Result:
    """Immutable scenario outcome: schema kinematic-race-sim-2."""
    schema_version: str = "kinematic-race-sim-2"
    scenario_id: str = ""
    model_id: str = ""
    status: str = "available"  # 'available', 'unavailable', 'unsupported'
    probability_scope: str = "completion_assumed_on_water"
    applied_inputs: dict[str, Any] = field(default_factory=dict)
    probabilities: ScenarioProbabilityDetail | None = None
    timing: ScenarioTimingDetail | None = None
    time_accounting: dict[str, Any] = field(default_factory=dict)
    trial_counts: dict[str, int] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)
    evidence_refs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.probabilities is not None:
            data["probabilities"] = asdict(self.probabilities)
        if self.timing is not None:
            data["timing"] = asdict(self.timing)
        return data


def validate_scenario_request(raw_request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate incoming scenario request conforming to G8.5 wire format (< 2 KiB)."""
    # 1. Payload size check
    raw_str = json.dumps(raw_request)
    if len(raw_str.encode("utf-8")) > 2048:
        raise ValueError("Scenario request exceeds 2 KiB maximum payload limit")

    # 2. Key validation (reject unknown keys)
    allowed_keys = {
        "schema_version",
        "model_id",
        "team_a",
        "team_b",
        "course_id",
        "environment",
        "purpose",
        "scenario_policy_id",
    }
    extra_keys = set(raw_request.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(f"Unknown request keys rejected: {sorted(extra_keys)}")

    # 3. Schema version
    if raw_request.get("schema_version") != "ac75-scenario-request-1":
        raise ValueError(f"Expected schema_version 'ac75-scenario-request-1', got {raw_request.get('schema_version')}")

    # 4. Model ID cannot be a filesystem path
    model_id = str(raw_request.get("model_id", "")).strip()
    if not model_id or "/" in model_id or "\\" in model_id or model_id.endswith(".npz") or model_id.endswith(".json"):
        raise ValueError(f"Invalid model_id '{model_id}': must be a content ID/hash, not a filesystem path")

    # 5. Course ID
    course_id = str(raw_request.get("course_id", "")).strip()
    if not course_id:
        raise ValueError("Missing or empty course_id")

    # 6. Team resolution in AC37 historical scope
    team_a = resolve_team_identity(str(raw_request.get("team_a", "")), cycle="AC37")
    team_b = resolve_team_identity(str(raw_request.get("team_b", "")), cycle="AC37")

    # 7. Purpose
    purpose = str(raw_request.get("purpose", "")).strip()
    if purpose not in (ScenarioPurpose.PREVIEW, ScenarioPurpose.STANDARD, ScenarioPurpose.EVALUATION):
        raise ValueError(f"Invalid purpose '{purpose}': must be preview, standard, or evaluation")

    # 8. Environment
    env = raw_request.get("environment")
    if not isinstance(env, dict):
        raise ValueError("Missing or non-dict environment object")
    if env.get("kind") != "fixed_wind":
        raise ValueError(f"Unsupported environment kind '{env.get('kind')}': only 'fixed_wind' is supported")
    
    tws_kt = float(env.get("tws_kt", 0.0))
    wind_from_deg = float(env.get("wind_from_deg", 0.0))
    if not math.isfinite(tws_kt) or tws_kt <= 0.0 or tws_kt > 40.0:
        raise ValueError(f"tws_kt must be in (0, 40] knots, got {tws_kt}")
    if not math.isfinite(wind_from_deg):
        raise ValueError(f"wind_from_deg must be finite, got {wind_from_deg}")

    normalized_wind_deg = wind_from_deg % 360.0

    return {
        "schema_version": "ac75-scenario-request-1",
        "model_id": model_id,
        "team_a": team_a,
        "team_b": team_b,
        "course_id": course_id,
        "environment": {
            "kind": "fixed_wind",
            "tws_kt": tws_kt,
            "tws_mps": knots_to_mps(tws_kt),
            "wind_from_deg": normalized_wind_deg,
        },
        "purpose": purpose,
        "scenario_policy_id": str(raw_request.get("scenario_policy_id", "ac37-observed-behavior-v1")).strip(),
    }


def is_legacy_scenario(obj: Mapping[str, Any]) -> bool:
    """Return True if the object is an old v1 scenario."""
    return obj.get("schema_version") == "kinematic-race-sim-1"


def validate_scenario_v2(obj: Mapping[str, Any]) -> None:
    """Validate scenario object strictly conforming to kinematic-race-sim-2."""
    if obj.get("schema_version") != "kinematic-race-sim-2":
        raise ValueError(f"Expected schema kinematic-race-sim-2, got {obj.get('schema_version')}")

    status = obj.get("status")
    if status not in (ScenarioStatus.AVAILABLE, ScenarioStatus.UNAVAILABLE, ScenarioStatus.UNSUPPORTED):
        raise ValueError(f"Unknown scenario status: {status}")

    scope = obj.get("probability_scope")
    if scope not in (ProbabilityScope.COMPLETION_ASSUMED_ON_WATER, ProbabilityScope.UNCONDITIONAL_REVIEWED):
        raise ValueError(f"Unknown probability_scope: {scope}")

    if status == ScenarioStatus.AVAILABLE:
        probs = obj.get("probabilities")
        if not isinstance(probs, dict):
            raise ValueError("Available scenario requires probabilities object")
        win_a = probs.get("win_a")
        win_b = probs.get("win_b")
        no_winner = probs.get("no_winner")
        mc_error = probs.get("mc_error")
        if win_a is None or win_b is None or not (0.0 <= win_a <= 1.0) or not (0.0 <= win_b <= 1.0):
            raise ValueError(f"Available scenario requires valid win_a and win_b, got {win_a}, {win_b}")
        if mc_error is not None and (not math.isfinite(mc_error) or mc_error < 0.0 or mc_error > 0.5):
            raise ValueError(f"probabilities.mc_error must be in [0, 0.5], got {mc_error}")

        if scope == ProbabilityScope.COMPLETION_ASSUMED_ON_WATER:
            if no_winner is not None:
                raise ValueError(
                    f"Under completion_assumed_on_water, probabilities.no_winner must be None, got {no_winner}"
                )
            if abs((win_a + win_b) - 1.0) > 1e-3:
                raise ValueError(
                    f"Under completion_assumed_on_water, win_a + win_b must equal 1.0, got {win_a + win_b}"
                )
        elif scope == ProbabilityScope.UNCONDITIONAL_REVIEWED:
            if no_winner is None or not (0.0 <= no_winner <= 1.0):
                raise ValueError(
                    f"Under unconditional_reviewed, no_winner must be in [0, 1], got {no_winner}"
                )
            if abs((win_a + win_b + no_winner) - 1.0) > 1e-3:
                raise ValueError(
                    f"Under unconditional_reviewed, win_a + win_b + no_winner must equal 1.0, got {win_a + win_b + no_winner}"
                )

        timing = obj.get("timing")
        if not isinstance(timing, dict):
            raise ValueError("Available scenario requires timing object")
        if "central_80_margin_interval_s" not in timing:
            raise ValueError("Available scenario timing requires central_80_margin_interval_s")
    else:
        # Unavailable or unsupported must have reasons
        reasons = obj.get("reason_codes", [])
        if not reasons:
            raise ValueError(f"Status '{status}' requires non-empty reason_codes")


# =============================================================================
# Wave 0 / P0 Shared Interfaces: Isolation, Evidence, Selection, Serving
# =============================================================================


@dataclass(frozen=True)
class SplitRef:
    """Immutable split identifier with chronological boundaries and family registry binding."""
    schema_version: str = "ac75-split-ref-1"
    split_id: str = ""
    registry_hash: str = ""
    train_start_date: str = ""
    train_end_date: str = ""
    test_date: str = ""
    val_date: str | None = None
    train_family_count: int = 0
    val_family_count: int = 0
    test_family_count: int = 0
    reserved_family_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrainingView:
    """Authenticated view over rows/events with strict family resolution and reserved-family exclusion."""
    schema_version: str = "ac75-training-view-1"
    view_id: str = ""
    registry_hash: str = ""
    split_ref: SplitRef | None = None
    total_rows: int = 0
    development_rows: int = 0
    reserved_excluded_rows: int = 0
    development_families: tuple[str, ...] = field(default_factory=tuple)
    reserved_families: tuple[str, ...] = field(default_factory=tuple)
    allowed_dates: tuple[str, ...] = field(default_factory=tuple)
    dataset_hash: str = ""
    family_mapping: dict[str, str] = field(default_factory=dict)

    def resolve_family(self, identifier: str) -> str:
        """Resolve race attempt or raw identifier to canonical family.
        Unknown family mappings raise ValueError rather than being treated as development.
        """
        if not identifier:
            raise ValueError("Empty identifier cannot be resolved to a family")
        if identifier in self.family_mapping:
            return self.family_mapping[identifier]
        if identifier in self.development_families or identifier in self.reserved_families:
            return identifier
        raise ValueError(
            f"Unknown family mapping for '{identifier}'. Unknown families are rejected, never inferred as development."
        )

    def is_allowed_family(self, family_id: str) -> bool:
        """Check if a family is permitted in training (must be in development and not reserved)."""
        return (family_id in self.development_families) and (family_id not in self.reserved_families)

    def is_allowed_date(self, date_str: str) -> bool:
        """Check if a date falls within chronological restrictions."""
        if not self.allowed_dates:
            return True
        return date_str in self.allowed_dates

    def validate_no_reserved_leakage(self, families: Sequence[str]) -> None:
        """Enforce that zero reserved families are present."""
        reserved_set = set(self.reserved_families)
        leaked = [f for f in families if f in reserved_set]
        if leaked:
            raise ValueError(f"Reserved family leakage detected: {sorted(set(leaked))}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.split_ref is not None:
            data["split_ref"] = self.split_ref.to_dict()
        return data


class EvidenceBasis(str, Enum):
    OFFICIAL_RESULTS = "official_results"
    SOURCE_CONFIRMED_ON_WATER = "source_confirmed_on_water"
    REVIEWED_RECONSTRUCTED = "reviewed_reconstructed"
    CANDIDATE_UNVERIFIED = "candidate_unverified"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EvidencePolicy:
    """Policy governing evidence basis levels, pre-race input limits, and race target qualification."""
    schema_version: str = "ac75-evidence-policy-1"
    timing_basis: str = EvidenceBasis.SOURCE_CONFIRMED_ON_WATER.value
    issue_time_basis: str = "race_gun"
    max_causal_latency_ms: int = 6000
    require_both_timed_finishes: bool = True
    require_physical_winner_match: bool = True
    allow_candidate_in_primary: bool = False
    missing_records_prove_completion: bool = False
    allow_whole_race_average_weather: bool = False
    allow_invented_default_weather: bool = False

    def qualify_race_target(self, target_record: Mapping[str, Any]) -> tuple[bool, str]:
        """Validate whether a race target qualifies for primary evaluation."""
        basis = target_record.get("evidence_basis", EvidenceBasis.CANDIDATE_UNVERIFIED.value)
        if basis == EvidenceBasis.CANDIDATE_UNVERIFIED.value and not self.allow_candidate_in_primary:
            return False, "unverified_candidate_basis_rejected"
        if basis == EvidenceBasis.UNAVAILABLE.value:
            return False, "evidence_unavailable"

        status = target_record.get("status", "valid")
        if status in ("unsupported", "unavailable", "abandoned"):
            return False, f"target_status_{status}"

        if self.require_both_timed_finishes:
            finish_a = target_record.get("finish_time_a_s")
            finish_b = target_record.get("finish_time_b_s")
            if finish_a is None or finish_b is None:
                return False, "missing_timed_finish_for_both_boats"
            if not math.isfinite(finish_a) or not math.isfinite(finish_b):
                return False, "non_finite_finish_times"

        if self.require_physical_winner_match:
            winner = target_record.get("winner")
            margin_s = target_record.get("race_margin_s")
            team_a = target_record.get("team_a")
            team_b = target_record.get("team_b")
            if margin_s is not None and winner is not None:
                if margin_s < 0 and winner != team_a:
                    return False, "winner_physical_margin_mismatch"
                elif margin_s > 0 and winner != team_b:
                    return False, "winner_physical_margin_mismatch"

        return True, "qualified"

    def validate_pre_race_inputs(self, weather_record: Mapping[str, Any]) -> tuple[bool, str]:
        """Verify weather and course context was available by gun time under latency limits."""
        if not self.allow_whole_race_average_weather and weather_record.get("is_whole_race_average", False):
            return False, "whole_race_average_weather_forbidden"
        if not self.allow_invented_default_weather and weather_record.get("is_invented_default", False):
            return False, "invented_default_weather_forbidden"

        available_at_ms = weather_record.get("available_at_ms")
        race_gun_ms = weather_record.get("race_gun_ms")
        if available_at_ms is not None and race_gun_ms is not None:
            if available_at_ms > race_gun_ms + self.max_causal_latency_ms:
                return False, "weather_available_after_race_gun_limit"

        return True, "valid"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelectionDecision:
    """Model selection decision based on candidate-specific paired date-level CRPS differences."""
    schema_version: str = "ac75-selection-decision-1"
    rule_name: str = "mean_date_crps_1se_rule"
    selected_model_id: str = ""
    selected_model_family: str = "empirical"
    candidate_mean_crps: dict[str, float] = field(default_factory=dict)
    candidate_se: dict[str, float] = field(default_factory=dict)
    candidate_crps_by_date: dict[str, dict[str, float]] = field(default_factory=dict)
    paired_differences_to_best: dict[str, list[float]] = field(default_factory=dict)
    paired_difference_mean: dict[str, float] = field(default_factory=dict)
    paired_difference_se: dict[str, float] = field(default_factory=dict)
    eligible_dates_count: int = 0
    qualified_targets_count: int = 0
    min_eligible_dates: int = 5
    is_fallback: bool = False
    fallback_reason: str = ""
    hierarchy_order: tuple[str, ...] = ("empirical", "spline", "neural")

    @classmethod
    def compute_selection(
        cls,
        candidate_crps_by_date: Mapping[str, Mapping[str, float]],
        *,
        qualified_targets_count: int = 0,
        min_eligible_dates: int = 5,
        model_ids: Mapping[str, str] | None = None,
    ) -> SelectionDecision:
        """Apply candidate-specific 1-SE rule on date-averaged CRPS or explicit fallback."""
        model_ids = model_ids or {}
        hierarchy = ("empirical", "spline", "neural")

        candidate_keys = list(candidate_crps_by_date.keys())
        if not candidate_keys:
            return cls(
                selected_model_id=model_ids.get("empirical", "empirical_binned_polar"),
                selected_model_family="empirical",
                is_fallback=True,
                fallback_reason="no_candidates_provided",
            )

        date_sets = [set(candidate_crps_by_date[c].keys()) for c in candidate_keys]
        common_dates = sorted(set.intersection(*date_sets) if date_sets else set())
        n_dates = len(common_dates)

        if qualified_targets_count == 0:
            return cls(
                selected_model_id=model_ids.get("empirical", "empirical_binned_polar"),
                selected_model_family="empirical",
                eligible_dates_count=n_dates,
                qualified_targets_count=0,
                is_fallback=True,
                fallback_reason="insufficient_qualified_race_targets",
            )

        if n_dates < min_eligible_dates:
            return cls(
                selected_model_id=model_ids.get("empirical", "empirical_binned_polar"),
                selected_model_family="empirical",
                eligible_dates_count=n_dates,
                qualified_targets_count=qualified_targets_count,
                is_fallback=True,
                fallback_reason=f"insufficient_eligible_dates ({n_dates} < {min_eligible_dates})",
            )

        means: dict[str, float] = {}
        ses: dict[str, float] = {}
        by_date_dict: dict[str, dict[str, float]] = {}

        for c in candidate_keys:
            vals = [candidate_crps_by_date[c][d] for d in common_dates]
            by_date_dict[c] = {d: candidate_crps_by_date[c][d] for d in common_dates}
            m = float(sum(vals) / n_dates)
            means[c] = m
            if n_dates > 1:
                var = sum((v - m) ** 2 for v in vals) / (n_dates - 1)
                se = math.sqrt(var) / math.sqrt(n_dates)
            else:
                se = 0.0
            ses[c] = se

        best_cand = min(candidate_keys, key=lambda c: means[c])

        paired_diffs: dict[str, list[float]] = {}
        paired_mean: dict[str, float] = {}
        paired_se: dict[str, float] = {}
        for c in candidate_keys:
            diffs = [candidate_crps_by_date[c][d] - candidate_crps_by_date[best_cand][d] for d in common_dates]
            paired_diffs[c] = diffs
            p_m = float(sum(diffs) / n_dates)
            paired_mean[c] = p_m
            if n_dates > 1:
                p_var = sum((v - p_m) ** 2 for v in diffs) / (n_dates - 1)
                p_se = math.sqrt(p_var) / math.sqrt(n_dates)
            else:
                p_se = 0.0
            paired_se[c] = p_se

        selected_cand = best_cand
        for fam in hierarchy:
            if fam in candidate_keys:
                if means[fam] <= means[best_cand] + ses[fam]:
                    selected_cand = fam
                    break

        return cls(
            selected_model_id=model_ids.get(selected_cand, selected_cand),
            selected_model_family=selected_cand,
            candidate_mean_crps=means,
            candidate_se=ses,
            candidate_crps_by_date=by_date_dict,
            paired_differences_to_best=paired_diffs,
            paired_difference_mean=paired_mean,
            paired_difference_se=paired_se,
            eligible_dates_count=n_dates,
            qualified_targets_count=qualified_targets_count,
            is_fallback=False,
            fallback_reason="",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_canonical_scenario_hash(request_dict: Mapping[str, Any]) -> str:
    """Compute authoritative deterministic SHA-256 hash of normalized scenario parameters."""
    canonical = {
        "schema_version": "ac75-scenario-request-1",
        "model_id": str(request_dict.get("model_id", "")),
        "team_a": str(request_dict.get("team_a", "")),
        "team_b": str(request_dict.get("team_b", "")),
        "course_id": str(request_dict.get("course_id", "")),
        "environment": {
            "kind": "fixed_wind",
            "tws_kt": round(float(request_dict.get("environment", {}).get("tws_kt", 0.0)), 6),
            "tws_mps": round(float(request_dict.get("environment", {}).get("tws_mps", 0.0)), 6),
            "wind_from_deg": round(float(request_dict.get("environment", {}).get("wind_from_deg", 0.0)) % 360.0, 4),
        },
        "purpose": str(request_dict.get("purpose", "preview")),
        "scenario_policy_id": str(request_dict.get("scenario_policy_id", "ac37-observed-behavior-v1")),
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NormalizedScenarioRequest:
    """Authoritative canonical scenario request with SI values and deterministic hash."""
    schema_version: str = "ac75-scenario-request-1"
    model_id: str = ""
    team_a: str = ""
    team_b: str = ""
    course_id: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    purpose: str = "preview"
    scenario_policy_id: str = "ac37-observed-behavior-v1"
    seed: int | None = None
    trial_count: int | None = None
    authoritative_hash: str = ""

    @classmethod
    def from_raw_request(cls, raw_request: Mapping[str, Any]) -> NormalizedScenarioRequest:
        """Validate and normalize raw scenario request, computing authoritative hash."""
        normalized_dict = validate_scenario_request(raw_request)
        auth_hash = compute_canonical_scenario_hash(normalized_dict)
        return cls(
            schema_version=normalized_dict["schema_version"],
            model_id=normalized_dict["model_id"],
            team_a=normalized_dict["team_a"],
            team_b=normalized_dict["team_b"],
            course_id=normalized_dict["course_id"],
            environment=normalized_dict["environment"],
            purpose=normalized_dict["purpose"],
            scenario_policy_id=normalized_dict["scenario_policy_id"],
            seed=raw_request.get("seed"),
            trial_count=raw_request.get("trial_count"),
            authoritative_hash=auth_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationReceipt:
    """Cryptographically authenticated record of simulation-trial evaluations and metrics."""
    schema_version: str = "ac75-evaluation-receipt-1"
    receipt_id: str = ""
    timestamp: str = ""
    model_id: str = ""
    split_ref_id: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    breakdown_by_date: dict[str, dict[str, float]] = field(default_factory=dict)
    support_counts: dict[str, int] = field(default_factory=dict)
    environment_metadata: dict[str, Any] = field(default_factory=dict)
    code_hashes: dict[str, str] = field(default_factory=dict)
    status: str = "complete"
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
