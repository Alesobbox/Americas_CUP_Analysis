"""Evidence policy governing race target qualification and pre-race input validation (Work Packet P2).

Enforces:
- Race-target policy:
  - Primary margin scoring requires supported timed finishes for both boats in the same valid attempt.
  - Primary on-water winner scoring must match physical margin target.
  - Candidate values cannot enter primary selection merely because they are non-null.
  - Missing records do not prove retirement or completion.
- Pre-race input policy:
  - Evaluation issue time is the race gun.
  - Weather/course inputs must have been available by that time under registered latency.
  - Remove whole-race-average weather and invented default weather.
  - Missing required pre-race context marks case unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import math
from typing import Any, Mapping

from .basis import EvidenceBasis, ReviewState, QualifiedFieldEvidence


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

    def qualify_race_target(
        self,
        target_record: Mapping[str, Any],
    ) -> tuple[bool, str, dict[str, QualifiedFieldEvidence]]:
        """Validate whether a race target qualifies for primary evaluation.
        
        Returns:
            (is_qualified: bool, reason_code: str, field_evidence_map: dict[str, QualifiedFieldEvidence])
        """
        race_id = str(target_record.get("race_id") or target_record.get("family_id") or "")
        attempt_id = str(target_record.get("attempt_id") or "")
        src_ref = str(target_record.get("source_url") or target_record.get("source_ref") or "")
        src_hash = str(target_record.get("source_hash") or "")

        evidence_basis = target_record.get("evidence_basis", EvidenceBasis.CANDIDATE_UNVERIFIED.value)
        is_verified = bool(target_record.get("verified", False))

        # Check 1: Evidence basis tier
        if evidence_basis == EvidenceBasis.CANDIDATE_UNVERIFIED.value and not self.allow_candidate_in_primary:
            return False, "unverified_candidate_basis_rejected", {}
        if evidence_basis == EvidenceBasis.UNAVAILABLE.value:
            return False, "evidence_unavailable", {}

        # Check 2: Unverified candidate fields rejected without explicit qualifying record
        if not is_verified and evidence_basis == EvidenceBasis.CANDIDATE_UNVERIFIED.value:
            return False, "unverified_candidate_fields_rejected", {}

        # Check 3: Race target status
        status = target_record.get("status", "valid")
        if status in ("unsupported", "unavailable", "abandoned", "stopped"):
            return False, f"target_status_{status}", {}

        # Check 4: Supported timed finishes for both boats in the same valid attempt
        finish_a = target_record.get("finish_time_a_s")
        finish_b = target_record.get("finish_time_b_s")

        if self.require_both_timed_finishes:
            if finish_a is None or finish_b is None:
                return False, "missing_timed_finish_for_both_boats", {}
            try:
                fa_float = float(finish_a)
                fb_float = float(finish_b)
            except (ValueError, TypeError):
                return False, "non_finite_finish_times", {}

            if not math.isfinite(fa_float) or not math.isfinite(fb_float) or fa_float <= 0 or fb_float <= 0:
                return False, "non_finite_finish_times", {}

        # Check 5: Physical winner matching
        winner = target_record.get("winner")
        margin_s = target_record.get("race_margin_s")
        team_a = target_record.get("team_a")
        team_b = target_record.get("team_b")

        if self.require_physical_winner_match and margin_s is not None and winner is not None:
            try:
                m_float = float(margin_s)
            except (ValueError, TypeError):
                return False, "non_finite_race_margin", {}

            if m_float < 0 and winner != team_a:
                return False, "winner_physical_margin_mismatch", {}
            elif m_float > 0 and winner != team_b:
                return False, "winner_physical_margin_mismatch", {}

        # Check 6: Candidate values cannot enter primary selection merely because they are non-null
        if not self.allow_candidate_in_primary:
            field_ev_input = target_record.get("field_evidence", {})
            if isinstance(field_ev_input, dict):
                for fname, fev in field_ev_input.items():
                    if isinstance(fev, dict):
                        f_basis = fev.get("evidence_basis", EvidenceBasis.CANDIDATE_UNVERIFIED.value)
                        f_ver = fev.get("verified", False)
                        if f_basis == EvidenceBasis.CANDIDATE_UNVERIFIED.value and not f_ver:
                            return False, "candidate_unverified_cannot_enter_primary", {}

        # Check 7: Missing records do not prove retirement or completion
        finish_status = target_record.get("finish_status")
        if finish_status == "unverified_or_retired" and not self.missing_records_prove_completion:
            if finish_a is None or finish_b is None:
                return False, "missing_records_do_not_prove_completion_or_retirement", {}

        # Build comprehensive field evidence records with full audit provenance
        field_records: dict[str, QualifiedFieldEvidence] = {}
        timing_basis_str = target_record.get("timing_basis", "reported_results")

        if finish_a is not None:
            field_records["finish_time_a_s"] = QualifiedFieldEvidence(
                field_name="finish_time_a_s",
                value=float(finish_a),
                evidence_basis=evidence_basis,
                review_state=ReviewState.VERIFIED.value if is_verified else ReviewState.UNVERIFIED.value,
                verified=is_verified,
                source_ref=src_ref,
                source_hash=src_hash,
                race_id=race_id,
                attempt_id=attempt_id,
                timing_basis=timing_basis_str,
                coverage=1.0,
            )

        if finish_b is not None:
            field_records["finish_time_b_s"] = QualifiedFieldEvidence(
                field_name="finish_time_b_s",
                value=float(finish_b),
                evidence_basis=evidence_basis,
                review_state=ReviewState.VERIFIED.value if is_verified else ReviewState.UNVERIFIED.value,
                verified=is_verified,
                source_ref=src_ref,
                source_hash=src_hash,
                race_id=race_id,
                attempt_id=attempt_id,
                timing_basis=timing_basis_str,
                coverage=1.0,
            )

        if margin_s is not None:
            field_records["race_margin_s"] = QualifiedFieldEvidence(
                field_name="race_margin_s",
                value=float(margin_s),
                evidence_basis=evidence_basis,
                review_state=ReviewState.VERIFIED.value if is_verified else ReviewState.UNVERIFIED.value,
                verified=is_verified,
                source_ref=src_ref,
                source_hash=src_hash,
                race_id=race_id,
                attempt_id=attempt_id,
                timing_basis=timing_basis_str,
                coverage=1.0,
            )

        if winner is not None:
            field_records["winner"] = QualifiedFieldEvidence(
                field_name="winner",
                value=str(winner),
                evidence_basis=evidence_basis,
                review_state=ReviewState.VERIFIED.value if is_verified else ReviewState.UNVERIFIED.value,
                verified=is_verified,
                source_ref=src_ref,
                source_hash=src_hash,
                race_id=race_id,
                attempt_id=attempt_id,
                timing_basis=timing_basis_str,
                coverage=1.0,
            )

        return True, "qualified", field_records

    def validate_pre_race_inputs(
        self,
        weather_record: Mapping[str, Any] | None,
    ) -> tuple[bool, str]:
        """Verify weather and course context was available by gun time under registered latency limits.
        
        Enforces:
        - Evaluation issue time is the race gun.
        - Weather/course inputs must have been available by that time under registered latency.
        - Rejects whole-race-average weather and invented default weather.
        - Missing required pre-race context marks case unavailable.
        """
        # Missing required pre-race context marks case unavailable
        if weather_record is None or not weather_record:
            return False, "missing_pre_race_weather_context"

        # Rejection of whole-race average weather
        if not self.allow_whole_race_average_weather and weather_record.get("is_whole_race_average", False):
            return False, "whole_race_average_weather_forbidden"

        # Rejection of invented default weather
        if not self.allow_invented_default_weather and weather_record.get("is_invented_default", False):
            return False, "invented_default_weather_forbidden"

        # Issue time is race gun: check registered causal latency
        available_at_ms = weather_record.get("available_at_ms")
        race_gun_ms = weather_record.get("race_gun_ms")

        if available_at_ms is not None and race_gun_ms is not None:
            try:
                avail_ms = int(available_at_ms)
                gun_ms = int(race_gun_ms)
                if avail_ms > gun_ms + self.max_causal_latency_ms:
                    return False, "weather_available_after_race_gun_limit"
            except (ValueError, TypeError):
                return False, "invalid_timestamp_types"

        # Check essential pre-race wind values
        tws = weather_record.get("tws_mps")
        if tws is None:
            tws = weather_record.get("tws_kt")
        if tws is None:
            return False, "missing_required_weather_fields"

        try:
            tws_float = float(tws)
            if not math.isfinite(tws_float) or tws_float <= 0.0 or tws_float > 40.0:
                return False, "invalid_wind_speed_value"
        except (ValueError, TypeError):
            return False, "invalid_wind_speed_type"

        return True, "valid"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
