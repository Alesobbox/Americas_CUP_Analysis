"""Authenticated training-view loader and centralized family-based isolation (Work Packet P1).

Enforces:
- Schema and cryptographic SHA-256 verification of frozen_evaluation_families.json.
- Resolves every row, template, and event to its canonical family using attempt_ledger.json.
- Reconciles ac37_fpr1_match_12 and ac37_lvc_rr_match_27 as canonical development families.
- Rejects unknown families (ValueError) — never infers development membership from dates alone.
- Strictly excludes reserved families across ALL fitting components:
  motion fitting, inner validation, maneuvers, starts, routes, completion models,
  calibration, and residual estimation.
- Stopped attempt and resail share identical family and can never fall into different roles.
- Chronological restrictions inside every outer fold.
- Baseline check against unchanged sealed dataset (steady_windows.parquet):
  16,128 total steady windows, 2,578 reserved-family windows excluded,
  13,550 development windows, and 539 Sept 28 stopped-attempt windows excluded
  through their resail-family link (ac37_lvc_final_r3).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pyarrow.parquet as pq

from pipeline.kinematic_ml.contracts import SplitRef, TrainingView
from pipeline.kinematic_ml.splits.registry import (
    FROZEN_REGISTRY_EXPECTED_SHA256,
    FROZEN_SPLITS_PATH,
    ATTEMPT_LEDGER_PATH,
    RECONCILED_FAMILY_ALIASES,
    load_frozen_family_registry,
    load_canonical_attempt_ledger,
)

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
SEALED_STEADY_WINDOWS_PATH = FORECAST_DIR / "sealed" / "steady_windows.parquet"


class AuthenticatedTrainingViewLoader:
    """Authenticated loader that reads frozen_evaluation_families.json and constructs verified TrainingView."""

    def __init__(
        self,
        registry_path: Path | str | None = None,
        ledger_path: Path | str | None = None,
        *,
        expected_registry_hash: str | None = FROZEN_REGISTRY_EXPECTED_SHA256,
        verify_hash: bool = True,
    ) -> None:
        self.registry_path = Path(registry_path) if registry_path is not None else FROZEN_SPLITS_PATH
        self.ledger_path = Path(ledger_path) if ledger_path is not None else ATTEMPT_LEDGER_PATH
        self.expected_registry_hash = expected_registry_hash
        self.verify_hash = verify_hash

        # 1. Authenticate and load frozen family registry
        self.registry = load_frozen_family_registry(
            self.registry_path,
            expected_hash=self.expected_registry_hash,
            verify_hash=self.verify_hash,
        )
        self.reserved_families = set(self.registry["reserved_holdout_families"])
        self.development_families = set(self.registry["development_families"])
        self.registry_hash = self.registry["registry_hash"]
        self.holdout_dates = set(self.registry["holdout_dates"])

        # 2. Load attempt ledger mappings if available
        self.family_mapping: dict[str, str] = {}
        if self.ledger_path.exists():
            self.family_mapping = load_canonical_attempt_ledger(self.ledger_path)

        # Merge reconciliation aliases
        for alias, canonical in RECONCILED_FAMILY_ALIASES.items():
            self.family_mapping[alias] = canonical

    def resolve_canonical_family(self, identifier: str) -> str:
        """Resolve attempt_id, filename, or family identifier to canonical family ID.
        
        Raises:
            ValueError: If identifier cannot be mapped to a known family in the registry/ledger.
                        Unknown families are strictly rejected, never inferred as development.
        """
        if not identifier or not str(identifier).strip():
            raise ValueError("Empty identifier cannot be resolved to a family")

        ident = str(identifier).strip()

        # Check attempt/filename mapping
        if ident in self.family_mapping:
            canonical = self.family_mapping[ident]
            return RECONCILED_FAMILY_ALIASES.get(canonical, canonical)

        # Check reconciled aliases
        if ident in RECONCILED_FAMILY_ALIASES:
            return RECONCILED_FAMILY_ALIASES[ident]

        # Check direct canonical families
        if ident in self.development_families or ident in self.reserved_families:
            return ident

        # Unknown family mapping: strictly reject
        raise ValueError(
            f"Unknown family mapping for '{ident}'. Unknown families are rejected, "
            f"never inferred as development from dates or filename."
        )

    def is_reserved_family(self, identifier: str) -> bool:
        """Check if an identifier resolves to a reserved holdout family."""
        canonical = self.resolve_canonical_family(identifier)
        return canonical in self.reserved_families

    def is_development_family(self, identifier: str) -> bool:
        """Check if an identifier resolves to an allowed development family."""
        canonical = self.resolve_canonical_family(identifier)
        return (canonical in self.development_families) and (canonical not in self.reserved_families)

    def create_training_view(
        self,
        *,
        view_id: str = "ac75_authenticated_dev_view_v1",
        split_ref: SplitRef | None = None,
        allowed_dates: Sequence[str] | None = None,
        dataset_path: Path | str | None = None,
    ) -> TrainingView:
        """Build an authenticated TrainingView contract instance."""
        total_rows = 0
        dev_rows = 0
        reserved_rows = 0
        dataset_hash = ""

        # If dataset path provided, compute row counts and hash
        if dataset_path is not None:
            p = Path(dataset_path)
            if p.exists():
                data_bytes = p.read_bytes()
                dataset_hash = hashlib.sha256(data_bytes).hexdigest()
                table = pq.read_table(p)
                total_rows = len(table)
                attempts = table["attempt_id"].to_pylist() if "attempt_id" in table.column_names else []
                families = table["family_id"].to_pylist() if "family_id" in table.column_names else []
                dates = table["date_str"].to_pylist() if "date_str" in table.column_names else []

                allowed_dates_set = set(allowed_dates) if allowed_dates is not None else None

                for i in range(total_rows):
                    att = attempts[i] if i < len(attempts) else ""
                    fam = families[i] if i < len(families) else ""
                    dt = dates[i] if i < len(dates) else ""
                    ident = att or fam
                    canonical_fam = self.resolve_canonical_family(ident)

                    if canonical_fam in self.reserved_families:
                        reserved_rows += 1
                    else:
                        if allowed_dates_set is None or dt in allowed_dates_set:
                            dev_rows += 1

        dates_tuple = tuple(sorted(allowed_dates)) if allowed_dates is not None else ()

        return TrainingView(
            schema_version="ac75-training-view-1",
            view_id=view_id,
            registry_hash=self.registry_hash,
            split_ref=split_ref,
            total_rows=total_rows,
            development_rows=dev_rows,
            reserved_excluded_rows=reserved_rows,
            development_families=tuple(sorted(self.development_families)),
            reserved_families=tuple(sorted(self.reserved_families)),
            allowed_dates=dates_tuple,
            dataset_hash=dataset_hash,
            family_mapping=dict(self.family_mapping),
        )


def load_authenticated_training_view(
    registry_path: Path | str | None = None,
    ledger_path: Path | str | None = None,
    *,
    expected_hash: str | None = FROZEN_REGISTRY_EXPECTED_SHA256,
    verify_hash: bool = True,
    split_ref: SplitRef | None = None,
    allowed_dates: Sequence[str] | None = None,
    dataset_path: Path | str | None = None,
    view_id: str = "ac75_authenticated_dev_view_v1",
) -> TrainingView:
    """Convenience loader returning an authenticated TrainingView contract instance."""
    loader = AuthenticatedTrainingViewLoader(
        registry_path=registry_path,
        ledger_path=ledger_path,
        expected_registry_hash=expected_hash,
        verify_hash=verify_hash,
    )
    return loader.create_training_view(
        view_id=view_id,
        split_ref=split_ref,
        allowed_dates=allowed_dates,
        dataset_path=dataset_path,
    )


# =============================================================================
# Centralized Component-Level Isolation Filters
# =============================================================================

def filter_steady_windows(
    tv: TrainingView,
    windows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Filter steady windows strictly excluding reserved families and unknown mappings.
    
    Used by: Motion fitting, inner validation, speed polar fitting.
    """
    dev_windows: list[dict[str, Any]] = []
    reserved_set = set(tv.reserved_families)

    for w in windows:
        ident = w.get("attempt_id") or w.get("family_id") or ""
        fam_id = tv.resolve_family(ident)

        # Exclude reserved families
        if fam_id in reserved_set:
            continue

        # Date restriction if active
        date_str = str(w.get("date_str") or w.get("date") or "")
        if date_str and not tv.is_allowed_date(date_str):
            continue

        dev_windows.append(dict(w))

    # Verify zero reserved leakage
    checked_fams = [tv.resolve_family(w.get("attempt_id") or w.get("family_id") or "") for w in dev_windows]
    tv.validate_no_reserved_leakage(checked_fams)
    return dev_windows


def filter_maneuvers(
    tv: TrainingView,
    maneuvers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Filter maneuvers strictly excluding reserved families.
    
    Used by: Maneuver loss and turn duration fitting.
    """
    dev_maneuvers: list[dict[str, Any]] = []
    reserved_set = set(tv.reserved_families)

    for m in maneuvers:
        ident = m.get("attempt_id") or m.get("family_id") or ""
        fam_id = tv.resolve_family(ident)
        if fam_id in reserved_set:
            continue
        dev_maneuvers.append(dict(m))

    checked_fams = [tv.resolve_family(m.get("attempt_id") or m.get("family_id") or "") for m in dev_maneuvers]
    tv.validate_no_reserved_leakage(checked_fams)
    return dev_maneuvers


def filter_route_templates(
    tv: TrainingView,
    routes: Sequence[Any],
) -> list[Any]:
    """Filter route templates strictly excluding reserved families.
    
    Used by: Course waypoint and route execution models.
    """
    dev_routes: list[Any] = []
    reserved_set = set(tv.reserved_families)

    for r in routes:
        if isinstance(r, dict):
            ident = r.get("attempt_id") or r.get("family_id") or ""
        else:
            ident = getattr(r, "attempt_id", None) or getattr(r, "family_id", None) or ""
        fam_id = tv.resolve_family(ident)
        if fam_id in reserved_set:
            continue
        dev_routes.append(r)

    checked_fams = [
        tv.resolve_family(
            r.get("attempt_id") or r.get("family_id") or ""
            if isinstance(r, dict)
            else getattr(r, "attempt_id", None) or getattr(r, "family_id", None) or ""
        )
        for r in dev_routes
    ]
    tv.validate_no_reserved_leakage(checked_fams)
    return dev_routes


def filter_start_intervals(
    tv: TrainingView,
    starts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Filter start interval observations strictly excluding reserved families.
    
    Used by: Start box entry and timing models.
    """
    dev_starts: list[dict[str, Any]] = []
    reserved_set = set(tv.reserved_families)

    for s in starts:
        ident = s.get("attempt_id") or s.get("family_id") or ""
        fam_id = tv.resolve_family(ident)
        if fam_id in reserved_set:
            continue
        dev_starts.append(dict(s))

    checked_fams = [tv.resolve_family(s.get("attempt_id") or s.get("family_id") or "") for s in dev_starts]
    tv.validate_no_reserved_leakage(checked_fams)
    return dev_starts


def filter_completion_records(
    tv: TrainingView,
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Filter race completion observations strictly excluding reserved families.
    
    Used by: DNF/DNS reliability and completion models.
    """
    dev_records: list[dict[str, Any]] = []
    reserved_set = set(tv.reserved_families)

    for rec in records:
        ident = rec.get("family_id") or rec.get("race_id") or rec.get("attempt_id") or ""
        fam_id = tv.resolve_family(ident)
        if fam_id in reserved_set:
            continue
        dev_records.append(dict(rec))

    checked_fams = [tv.resolve_family(r.get("family_id") or r.get("race_id") or r.get("attempt_id") or "") for r in dev_records]
    tv.validate_no_reserved_leakage(checked_fams)
    return dev_records


def filter_calibration_samples(
    tv: TrainingView,
    samples: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Filter calibration samples strictly excluding reserved families.
    
    Used by: Uncertainty calibration and interval scaling.
    """
    dev_samples: list[dict[str, Any]] = []
    reserved_set = set(tv.reserved_families)

    for samp in samples:
        ident = samp.get("attempt_id") or samp.get("family_id") or ""
        fam_id = tv.resolve_family(ident)
        if fam_id in reserved_set:
            continue
        dev_samples.append(dict(samp))

    checked_fams = [tv.resolve_family(s.get("attempt_id") or s.get("family_id") or "") for s in dev_samples]
    tv.validate_no_reserved_leakage(checked_fams)
    return dev_samples


def filter_residual_estimation_data(
    tv: TrainingView,
    residuals: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Filter residual estimation samples strictly excluding reserved families.
    
    Used by: Motion residual covariance and noise estimation.
    """
    dev_res: list[dict[str, Any]] = []
    reserved_set = set(tv.reserved_families)

    for res in residuals:
        ident = res.get("attempt_id") or res.get("family_id") or ""
        fam_id = tv.resolve_family(ident)
        if fam_id in reserved_set:
            continue
        dev_res.append(dict(res))

    checked_fams = [tv.resolve_family(r.get("attempt_id") or r.get("family_id") or "") for r in dev_res]
    tv.validate_no_reserved_leakage(checked_fams)
    return dev_res


# =============================================================================
# Verification and Gate A Assurance Utilities
# =============================================================================

def verify_steady_windows_baseline(
    parquet_path: Path | str | None = None,
    registry_path: Path | str | None = None,
    ledger_path: Path | str | None = None,
) -> dict[str, int]:
    """Verify exact baseline counts against unchanged sealed dataset (steady_windows.parquet).
    
    Baseline criteria:
    - 16,128 total steady windows
    - 2,578 reserved-family windows excluded
    - 13,550 development windows
    - 539 Sept 28 stopped-attempt windows excluded through their resail-family link (ac37_lvc_final_r3)
    """
    pq_path = Path(parquet_path) if parquet_path is not None else SEALED_STEADY_WINDOWS_PATH
    if not pq_path.exists():
        raise FileNotFoundError(f"Sealed steady windows parquet not found at '{pq_path}'")

    loader = AuthenticatedTrainingViewLoader(
        registry_path=registry_path,
        ledger_path=ledger_path,
    )
    tv = loader.create_training_view(dataset_path=pq_path)

    table = pq.read_table(pq_path)
    rows = table.to_pylist()
    total_count = len(rows)

    dev_count = 0
    reserved_count = 0
    sept28_stopped_count = 0

    for r in rows:
        att = r.get("attempt_id", "")
        fam = r.get("family_id", "")
        ident = att or fam
        canonical_fam = tv.resolve_family(ident)

        if canonical_fam in tv.reserved_families:
            reserved_count += 1
            if att == "ac37_lvc_final_r3_att1_stopped":
                sept28_stopped_count += 1
        else:
            dev_count += 1

    # Exact baseline assertions
    if total_count != 16128:
        raise AssertionError(f"Expected 16,128 total steady windows, got {total_count}")
    if reserved_count != 2578:
        raise AssertionError(f"Expected 2,578 reserved-family windows excluded, got {reserved_count}")
    if dev_count != 13550:
        raise AssertionError(f"Expected 13,550 development windows, got {dev_count}")
    if sept28_stopped_count != 539:
        raise AssertionError(
            f"Expected 539 Sept 28 stopped-attempt windows excluded via ac37_lvc_final_r3, got {sept28_stopped_count}"
        )

    return {
        "total_windows": total_count,
        "reserved_windows_excluded": reserved_count,
        "development_windows": dev_count,
        "sept28_stopped_windows_excluded": sept28_stopped_count,
    }


def assert_stopped_attempt_and_resail_co_isolation(
    ledger_path: Path | str | None = None,
    registry_path: Path | str | None = None,
) -> None:
    """Enforce Gate A Criterion 2: Stopped attempt and resail cannot fall into different roles.
    
    Verifies that for every stopped attempt linked to a resail, both resolve to the exact same
    canonical family and are assigned the identical isolation role.
    """
    path = Path(ledger_path) if ledger_path is not None else ATTEMPT_LEDGER_PATH
    if not path.exists():
        raise FileNotFoundError(f"Attempt ledger not found at '{path}'")

    loader = AuthenticatedTrainingViewLoader(registry_path=registry_path, ledger_path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    attempts = data.get("attempts", [])

    stopped_attempts = [a for a in attempts if a.get("is_stopped_race") and a.get("linked_resail_attempt_id")]

    for sa in stopped_attempts:
        stopped_id = sa["attempt_id"]
        resail_id = sa["linked_resail_attempt_id"]

        fam_stopped = loader.resolve_canonical_family(stopped_id)
        fam_resail = loader.resolve_canonical_family(resail_id)

        if fam_stopped != fam_resail:
            raise AssertionError(
                f"Stopped attempt '{stopped_id}' has family '{fam_stopped}', but linked resail "
                f"'{resail_id}' has different family '{fam_resail}'! They must share the same family."
            )

        role_stopped = "reserved" if loader.is_reserved_family(stopped_id) else "development"
        role_resail = "reserved" if loader.is_reserved_family(resail_id) else "development"

        if role_stopped != role_resail:
            raise AssertionError(
                f"Stopped attempt '{stopped_id}' (role={role_stopped}) and resail '{resail_id}' "
                f"(role={role_resail}) fell into different roles! Gate A violation."
            )
