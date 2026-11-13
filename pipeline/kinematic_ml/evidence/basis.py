"""Evidence basis tiers, review states, and field-level evidence provenance (Work Packet P2).

Enforces:
- Separation of evidence basis (official results, on-water confirmed timing, reviewed reconstructed timing,
  candidate/unverified values, unavailable) from review/verification state.
- Retains source reference/hash, race/attempt identity, timing basis, review state, conflicts,
  and coverage for every used field.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


class EvidenceBasis(str, Enum):
    """Hierarchy of evidence basis tiers."""
    OFFICIAL_RESULTS = "official_results"
    SOURCE_CONFIRMED_ON_WATER = "source_confirmed_on_water"
    REVIEWED_RECONSTRUCTED = "reviewed_reconstructed"
    CANDIDATE_UNVERIFIED = "candidate_unverified"
    UNAVAILABLE = "unavailable"


class ReviewState(str, Enum):
    """Review and verification states distinct from the evidence basis."""
    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    UNVERIFIED = "unverified"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class QualifiedFieldEvidence:
    """Field-level evidence record with full audit provenance."""
    field_name: str
    value: Any
    evidence_basis: str = EvidenceBasis.CANDIDATE_UNVERIFIED.value
    review_state: str = ReviewState.UNVERIFIED.value
    verified: bool = False
    source_ref: str = ""
    source_hash: str = ""
    race_id: str = ""
    attempt_id: str = ""
    timing_basis: str = "reported_results"  # e.g. 'gun_to_line', 'elapsed_sog_integration', 'reported_results'
    conflicts: list[str] = field(default_factory=list)
    coverage: float = 1.0  # Fraction in [0.0, 1.0]

    def is_qualified_for_primary(self, allow_candidate: bool = False) -> bool:
        """Return True if this field qualifies for primary evaluation without unverified candidate reliance."""
        if not self.verified:
            if not allow_candidate or self.evidence_basis == EvidenceBasis.CANDIDATE_UNVERIFIED.value:
                return False
        if self.evidence_basis == EvidenceBasis.UNAVAILABLE.value:
            return False
        if self.review_state in (ReviewState.CONFLICTED.value, ReviewState.REJECTED.value):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
