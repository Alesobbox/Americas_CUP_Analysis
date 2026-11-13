"""Batch qualification for evaluation targets and pre-race context (Work Packet P2).

Enforces:
- If no qualified race targets remain, return insufficient_qualified_race_targets.
- Retains field-level evidence provenance across all qualified targets.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping, Sequence

from .basis import QualifiedFieldEvidence
from .policy import EvidencePolicy


@dataclass(frozen=True)
class QualificationResult:
    """Result of dataset-level race target qualification."""
    status: str  # 'qualified' or 'insufficient_qualified_race_targets'
    qualified_count: int = 0
    total_evaluated: int = 0
    qualified_targets: list[dict[str, Any]] = field(default_factory=list)
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    field_evidence_catalog: dict[str, dict[str, QualifiedFieldEvidence]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Convert field evidence dataclasses to dicts
        catalog_dict: dict[str, dict[str, Any]] = {}
        for r_id, f_dict in self.field_evidence_catalog.items():
            catalog_dict[r_id] = {k: asdict(v) for k, v in f_dict.items()}
        data["field_evidence_catalog"] = catalog_dict
        return data


def qualify_evaluation_targets(
    race_targets: Sequence[Mapping[str, Any]],
    policy: EvidencePolicy | None = None,
) -> QualificationResult:
    """Qualify a collection of candidate race targets against explicit evidence policy.
    
    If no qualified targets remain, returns status 'insufficient_qualified_race_targets'.
    """
    pol = policy or EvidencePolicy()
    qualified: list[dict[str, Any]] = []
    rejections: dict[str, int] = {}
    catalog: dict[str, dict[str, QualifiedFieldEvidence]] = {}

    for target in race_targets:
        is_ok, reason, field_evs = pol.qualify_race_target(target)
        if is_ok:
            qualified.append(dict(target))
            target_id = str(target.get("race_id") or target.get("family_id") or len(qualified))
            catalog[target_id] = field_evs
        else:
            rejections[reason] = rejections.get(reason, 0) + 1

    total = len(race_targets)
    count = len(qualified)

    status = "qualified" if count > 0 else "insufficient_qualified_race_targets"

    return QualificationResult(
        status=status,
        qualified_count=count,
        total_evaluated=total,
        qualified_targets=qualified,
        rejection_reasons=rejections,
        field_evidence_catalog=catalog,
    )
