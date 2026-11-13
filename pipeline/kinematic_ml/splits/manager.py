"""Chronological split manager, expanding outer folds, and final-holdout isolation guard.

Contract:
- Whole-family grouping: linked resails and both boats stay together in the same group.
- Outer development folds use expanding chronological days.
- Inner validation uses earlier whole-day blocks wholly within each outer training set.
- Zero reserved-family leakage across any fold (train, val, or test).
- Complete chronological restrictions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from pipeline.kinematic_ml.contracts import SplitRef
from .registry import (
    FROZEN_SPLITS_PATH,
    FROZEN_REGISTRY_EXPECTED_SHA256,
    load_frozen_family_registry,
    RECONCILED_FAMILY_ALIASES,
)


@dataclass(frozen=True)
class OuterFold:
    """Expanding chronological fold for development and validation."""
    fold_id: str
    train_dates: list[str]
    train_families: list[str]
    val_dates: list[str]
    val_families: list[str]
    test_dates: list[str]
    test_families: list[str]

    def to_split_ref(self, registry_hash: str) -> SplitRef:
        """Convert fold to frozen SplitRef contract."""
        return SplitRef(
            split_id=self.fold_id,
            registry_hash=registry_hash,
            train_start_date=self.train_dates[0] if self.train_dates else "",
            train_end_date=self.train_dates[-1] if self.train_dates else "",
            test_date=self.test_dates[0] if self.test_dates else "",
            val_date=self.val_dates[-1] if self.val_dates else None,
            train_family_count=len(self.train_families),
            val_family_count=len(self.val_families),
            test_family_count=len(self.test_families),
            reserved_family_hash=registry_hash,
        )


class ChronologicalSplitManager:
    """Manages expanding chronological folds and prevents leakage into frozen final holdouts."""

    def __init__(
        self,
        frozen_splits_path: Path | str | None = None,
        *,
        expected_hash: str | None = None,
        verify_hash: bool | None = None,
    ) -> None:
        path = Path(frozen_splits_path) if frozen_splits_path is not None else FROZEN_SPLITS_PATH
        is_default = (path == FROZEN_SPLITS_PATH)
        should_verify = verify_hash if verify_hash is not None else is_default
        exp_h = expected_hash if expected_hash is not None else (
            FROZEN_REGISTRY_EXPECTED_SHA256 if is_default else None
        )
        registry = load_frozen_family_registry(path, expected_hash=exp_h, verify_hash=should_verify)

        self.holdout_dates: set[str] = set(registry["holdout_dates"])
        self.reserved_holdout_families: set[str] = set(registry["reserved_holdout_families"])
        self.development_families: set[str] = set(registry["development_families"])
        self.merkle_sha256: str = registry["registry_hash"]
        self.registry_path = path

    def is_holdout_family(self, family_id: str) -> bool:
        """Returns True if family belongs to the locked final holdout."""
        resolved = RECONCILED_FAMILY_ALIASES.get(family_id, family_id)
        return resolved in self.reserved_holdout_families

    def is_development_family(self, family_id: str) -> bool:
        """Returns True if family belongs to permitted development families."""
        resolved = RECONCILED_FAMILY_ALIASES.get(family_id, family_id)
        return (resolved in self.development_families) and (resolved not in self.reserved_holdout_families)

    def validate_no_reserved_leakage(self, families: Sequence[str]) -> None:
        """Enforce that zero reserved families are present. Raises ValueError on any leakage."""
        leaked = [f for f in families if self.is_holdout_family(f)]
        if leaked:
            raise ValueError(f"Reserved family leakage detected: {sorted(set(leaked))}")

    def build_expanding_folds(
        self,
        family_dates: Mapping[str, str],  # family_id -> YYYY-MM-DD
        *,
        min_train_days: int = 5,
        val_days_count: int = 2,
    ) -> list[OuterFold]:
        """Constructs expanding chronological outer folds from development families only."""
        # Filter to permitted development families only, strictly excluding holdout dates & holdout families
        dev_items: list[tuple[str, str]] = []
        for fid, dt in family_dates.items():
            canonical_fid = RECONCILED_FAMILY_ALIASES.get(fid, fid)
            if self.is_development_family(canonical_fid) and dt not in self.holdout_dates:
                dev_items.append((canonical_fid, dt))

        # Group families by date
        date_to_fids: dict[str, list[str]] = {}
        for fid, dt in dev_items:
            date_to_fids.setdefault(dt, []).append(fid)

        sorted_dates = sorted(date_to_fids.keys())
        if len(sorted_dates) < min_train_days + val_days_count + 1:
            min_train_days = max(2, len(sorted_dates) // 3)
            val_days_count = 1

        folds: list[OuterFold] = []
        for i in range(min_train_days, len(sorted_dates) - 1):
            train_span = sorted_dates[:i]
            test_dt = sorted_dates[i]

            # Inner validation: last val_days_count days of train_span
            inner_val_dates = train_span[-val_days_count:] if len(train_span) >= val_days_count else [train_span[-1]]
            pure_train_dates = [d for d in train_span if d not in inner_val_dates]

            train_fids = [fid for d in pure_train_dates for fid in date_to_fids[d]]
            val_fids = [fid for d in inner_val_dates for fid in date_to_fids[d]]
            test_fids = date_to_fids[test_dt]

            fold = OuterFold(
                fold_id=f"fold_{len(folds):02d}_{test_dt}",
                train_dates=pure_train_dates,
                train_families=sorted(train_fids),
                val_dates=inner_val_dates,
                val_families=sorted(val_fids),
                test_dates=[test_dt],
                test_families=sorted(test_fids),
            )
            self.validate_fold_isolation(fold)
            folds.append(fold)

        return folds

    def validate_fold_isolation(self, fold: OuterFold) -> None:
        """Verify that a fold satisfies chronological restrictions and zero reserved leakage."""
        train_set = set(fold.train_dates)
        val_set = set(fold.val_dates)
        test_set = set(fold.test_dates)

        # Disjoint dates check
        if train_set & test_set:
            raise ValueError(f"Train and test dates overlap in fold {fold.fold_id}: {train_set & test_set}")
        if val_set & test_set:
            raise ValueError(f"Val and test dates overlap in fold {fold.fold_id}: {val_set & test_set}")
        if train_set & val_set:
            raise ValueError(f"Pure train and val dates overlap in fold {fold.fold_id}: {train_set & val_set}")

        # Chronological ordering check: train < val <= test
        if fold.train_dates and fold.test_dates:
            if max(fold.train_dates) >= min(fold.test_dates):
                raise ValueError(f"Train dates are not strictly prior to test dates in fold {fold.fold_id}")
        if fold.val_dates and fold.test_dates:
            if max(fold.val_dates) >= min(fold.test_dates):
                raise ValueError(f"Val dates are not strictly prior to test dates in fold {fold.fold_id}")

        # No reserved family leakage
        all_fold_fams = fold.train_families + fold.val_families + fold.test_families
        self.validate_no_reserved_leakage(all_fold_fams)
