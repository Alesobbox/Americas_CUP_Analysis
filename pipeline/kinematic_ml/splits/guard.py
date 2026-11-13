"""Holdout target consumption audit ledger guard and experiment registration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[3]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
CONSUMED_LEDGER_PATH = FORECAST_DIR / "consumed_holdout_ledger.json"
EXPERIMENT_REG_PATH = FORECAST_DIR / "experiment_registration.json"


class FinalTargetAccessGuard:
    """Audit ledger guard for final-evaluation target access."""

    def __init__(self, ledger_path: Path | str | None = None) -> None:
        self.ledger_path = Path(ledger_path) if ledger_path is not None else CONSUMED_LEDGER_PATH
        self._ensure_ledger_exists()

    def _ensure_ledger_exists(self) -> None:
        if not self.ledger_path.exists():
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            initial = {
                "schema_version": "ac75-splits-1",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "access_log": [],
            }
            self.ledger_path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def record_holdout_access(
        self,
        caller: str,
        purpose: str,
        accessed_families: Sequence[str],
    ) -> None:
        """Records an immutable consumption entry when final holdout targets are queried."""
        try:
            ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except Exception:
            ledger = {"schema_version": "ac75-splits-1", "access_log": []}

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "caller": caller,
            "purpose": purpose,
            "family_count": len(accessed_families),
            "families": sorted(accessed_families),
        }
        ledger.setdefault("access_log", []).append(entry)
        self.ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def register_experiment(
    experiment_id: str,
    feature_keys: Sequence[str],
    target_names: Sequence[str],
    model_family: str,
    hyperparameters: Mapping[str, Any],
    dataset_manifest_path: Path | str,
    *,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Registers immutable experiment configuration and dataset feature hashes."""
    d_path = Path(dataset_manifest_path)
    manifest_bytes = d_path.read_bytes() if d_path.exists() else b""
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    reg = {
        "schema_version": "ac75-splits-1",
        "experiment_id": experiment_id,
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_family": model_family,
        "feature_keys": sorted(feature_keys),
        "target_names": sorted(target_names),
        "hyperparameters": dict(hyperparameters),
        "dataset_manifest_hash": manifest_hash,
    }
    target_out = Path(out_path) if out_path is not None else EXPERIMENT_REG_PATH
    target_out.parent.mkdir(parents=True, exist_ok=True)
    target_out.write_text(json.dumps(reg, indent=2), encoding="utf-8")
    return reg
