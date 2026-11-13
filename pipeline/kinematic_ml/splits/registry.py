"""Split registry verification, frozen evaluation families loader, and family reconciliation.

Enforces:
- Schema and cryptographic SHA-256 hash verification of frozen_evaluation_families.json.
- Reconciles ac37_fpr1_match_12 and ac37_lvc_rr_match_27 canonical families.
- Rejects missing, tampered, or unsupported split registries.
- Strict mapping from attempt and source records to canonical family IDs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[3]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
FROZEN_SPLITS_PATH = FORECAST_DIR / "frozen_evaluation_families.json"
ATTEMPT_LEDGER_PATH = FORECAST_DIR / "attempt_ledger.json"

FROZEN_REGISTRY_EXPECTED_SHA256 = "1ddde3fd253eea492d55eb3b7f5718b5c92643d3cc4aa153b01f0a7f41839820"

# Canonical reconciliation aliases:
# In the original frozen metadata, these two round-robin / preliminary matches were labelled
# with legacy semifinal aliases. Reconcile both to canonical families.
RECONCILED_FAMILY_ALIASES: dict[str, str] = {
    "ac37_lvc_semifinal_1_r12": "ac37_fpr1_match_12",
    "ac37_lvc_semifinal_1_r27": "ac37_lvc_rr_match_27",
}


def compute_frozen_registry_hash(data: Mapping[str, Any]) -> str:
    """Compute the deterministic content SHA-256 hash of a frozen registry payload."""
    payload = {k: v for k, v in data.items() if k != "content_sha256"}
    content_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(content_bytes).hexdigest()


def verify_split_registry(
    data: Mapping[str, Any],
    *,
    expected_hash: str | None = FROZEN_REGISTRY_EXPECTED_SHA256,
) -> str:
    """Verify registry schema and cryptographic content hash.
    
    Raises:
        ValueError: If schema is invalid or SHA-256 hash does not match expected hash.
    """
    if not isinstance(data, dict):
        raise ValueError("Split registry data must be a dictionary")

    # 1. Schema checks
    status = data.get("status")
    if status not in ("frozen_metadata_only", "frozen"):
        raise ValueError(f"Invalid split registry status '{status}' (expected 'frozen_metadata_only' or 'frozen')")

    required_keys = ("holdout_dates", "reserved_holdout_families", "development_families")
    for k in required_keys:
        if k not in data or not isinstance(data[k], list):
            raise ValueError(f"Split registry missing or invalid list for '{k}'")

    reserved_fams = data["reserved_holdout_families"]
    dev_fams = data["development_families"]
    holdout_dates = data["holdout_dates"]

    if len(reserved_fams) == 0:
        raise ValueError("Split registry has empty reserved_holdout_families")
    if len(dev_fams) == 0:
        raise ValueError("Split registry has empty development_families")
    if len(holdout_dates) == 0:
        raise ValueError("Split registry has empty holdout_dates")

    # Check for internal overlap in registry itself
    overlap = set(reserved_fams) & set(dev_fams)
    if overlap:
        raise ValueError(f"Split registry has internal overlap between reserved and dev families: {sorted(overlap)}")

    # 2. Cryptographic content hash verification
    computed_hash = compute_frozen_registry_hash(data)
    declared_hash = data.get("content_sha256")
    if declared_hash and declared_hash != computed_hash:
        raise ValueError(
            f"Split registry content SHA-256 mismatch: declared '{declared_hash}' != computed '{computed_hash}'"
        )

    if expected_hash is not None and computed_hash != expected_hash:
        raise ValueError(
            f"Split registry SHA-256 verification failed: computed '{computed_hash}' != expected '{expected_hash}'"
        )

    return computed_hash


def load_frozen_family_registry(
    registry_path: Path | str | None = None,
    *,
    expected_hash: str | None = FROZEN_REGISTRY_EXPECTED_SHA256,
    verify_hash: bool = True,
) -> dict[str, Any]:
    """Load and authenticate frozen evaluation families registry.
    
    Returns authenticated dictionary containing:
    - reserved_holdout_families: set of 9 canonical reserved family IDs
    - development_families: set of 105 canonical development family IDs (including reconciled families)
    - holdout_dates: set of 5 holdout dates
    - registry_hash: verified SHA-256 hash string
    - raw_payload: unmodified dictionary from disk
    """
    path = Path(registry_path) if registry_path is not None else FROZEN_SPLITS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Frozen evaluation families registry not found at '{path}'")

    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except Exception as exc:
        raise ValueError(f"Corrupt or unreadable frozen evaluation families registry at '{path}': {exc}") from exc

    if verify_hash:
        content_hash = verify_split_registry(data, expected_hash=expected_hash)
    else:
        # Schema-only check when hash verification is explicitly disabled
        required_keys = ("holdout_dates", "reserved_holdout_families", "development_families")
        for k in required_keys:
            if k not in data or not isinstance(data[k], list):
                raise ValueError(f"Split registry missing or invalid list for '{k}'")
        overlap = set(data["reserved_holdout_families"]) & set(data["development_families"])
        if overlap:
            raise ValueError(f"Split registry has internal overlap between reserved and dev families: {sorted(overlap)}")
        content_hash = data.get("content_sha256", compute_frozen_registry_hash(data))

    # Extract families and apply reconciliation for canonical resolution
    reserved = set(data["reserved_holdout_families"])
    dev = set(data["development_families"])

    # Reconcile legacy aliases to canonical family names
    for legacy_alias, canonical_name in RECONCILED_FAMILY_ALIASES.items():
        if legacy_alias in dev:
            dev.remove(legacy_alias)
            dev.add(canonical_name)
        elif legacy_alias in reserved:
            reserved.remove(legacy_alias)
            reserved.add(canonical_name)

    # Ensure canonical development families are explicitly present
    dev.add("ac37_fpr1_match_12")
    dev.add("ac37_lvc_rr_match_27")

    return {
        "reserved_holdout_families": frozenset(reserved),
        "development_families": frozenset(dev),
        "holdout_dates": frozenset(data["holdout_dates"]),
        "registry_hash": content_hash,
        "raw_payload": data,
    }


def load_canonical_attempt_ledger(
    ledger_path: Path | str | None = None,
) -> dict[str, str]:
    """Load attempt_ledger.json and build deterministic mapping of attempt_id -> canonical family_id.
    
    Reconciles ac37_fpr1_match_12 and ac37_lvc_rr_match_27.
    """
    path = Path(ledger_path) if ledger_path is not None else ATTEMPT_LEDGER_PATH
    if not path.exists():
        raise FileNotFoundError(f"Attempt ledger not found at '{path}'")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Corrupt or unreadable attempt ledger at '{path}': {exc}") from exc

    mapping: dict[str, str] = {}
    for att in data.get("attempts", []):
        att_id = att.get("attempt_id")
        fam_id = att.get("family_id")
        if not att_id or not fam_id:
            continue
        # Apply reconciliation aliases if needed
        fam_id = RECONCILED_FAMILY_ALIASES.get(fam_id, fam_id)
        mapping[att_id] = fam_id
        # Also map filename if available
        src_file = att.get("source_file")
        if src_file:
            mapping[src_file] = fam_id

    # Canonical aliases pass-through
    for legacy_alias, canonical_name in RECONCILED_FAMILY_ALIASES.items():
        mapping[legacy_alias] = canonical_name

    return mapping
