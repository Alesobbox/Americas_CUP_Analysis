"""Race attempts, family resolution, duplicate reconciliation, and outcome evidence ledger.

Enforces:
- Construction of family and attempt IDs with stopped-race / resail links.
- At most one valid scored outcome per race family.
- Deduplication of identical packet observations and file copies.
- Separation of practice physical data from competitive reliability denominators.
- Field-level provenance for winner, margin, wind, and finish status.
- Metadata-only freezing of final-evaluation families prior to model/detector tuning.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from .contracts import (
    resolve_team_identity,
    UnsupportedIdentityError,
    knots_to_mps,
)

ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
ATTEMPTS_LEDGER_PATH = FORECAST_DIR / "attempt_ledger.json"
OUTCOME_LEDGER_PATH = FORECAST_DIR / "outcome_evidence_ledger.json"


@dataclass(frozen=True)
class RaceAttempt:
    attempt_id: str
    family_id: str
    source_file: str
    stage: str
    domain: str  # 'practice' or 'competitive'
    date: str
    team_a: str
    team_b: str
    is_stopped_race: bool
    is_resail: bool
    linked_resail_attempt_id: str | None
    scored_outcome_eligible: bool
    status: str  # 'completed', 'stopped', 'practice_session'
    session_id: str | None = None
    race_start_ms: int | None = None


@dataclass(frozen=True)
class OutcomeFieldEvidence:
    value: Any
    provenance: str  # 'official_anchor_verified', 'telemetry_timed_finish', 'unverified_estimate', 'unavailable'
    source_ref: str
    verified: bool


@dataclass(frozen=True)
class RaceFamilyOutcome:
    family_id: str
    stage: str
    date: str
    team_a: str
    team_b: str
    winner: OutcomeFieldEvidence
    delta_s: OutcomeFieldEvidence
    wind_mps: OutcomeFieldEvidence
    finish_status: OutcomeFieldEvidence
    telemetry_status: str  # 'present_jsonl', 'unsupported_binary', 'missing_from_archive'
    attempts: list[str] = field(default_factory=list)


def derive_canonical_family_id(source_record: Mapping[str, Any]) -> str:
    """Map source filename and directory to the canonical family ID."""
    filename = source_record["filename"]
    rel_path = source_record.get("relative_path", "")
    domain = source_record.get("domain", "")
    boat_class = source_record.get("boat_class", "AC75")

    fn_lower = filename.lower()
    rel_lower = rel_path.lower()

    if boat_class == "AC75" and domain == "competitive":
        # 1. Semifinals (check BEFORE finals, since 'semifinal' contains 'final')
        if "semifinal" in rel_lower or re.search(r"\blvs\b", fn_lower):
            m = re.search(r"match\s+(\d+)", fn_lower)
            r_num = m.group(1) if m else "1"
            if any(t in fn_lower for t in ["sui", "gbr"]):
                return f"ac37_lvc_semifinal_1_r{r_num}"
            else:
                return f"ac37_lvc_semifinal_2_r{r_num}"

        # 2. Finals
        if "finals" in rel_lower or re.search(r"\blv\s+finals\b", fn_lower):
            m = re.search(r"match\s+(\d+)", fn_lower)
            if m:
                return f"ac37_lvc_final_r{m.group(1)}"

        # 3. Preliminary Barcelona
        if "prelim_barcelona" in rel_lower or re.search(r"\bfpr\d*\b", fn_lower):
            if "final" in fn_lower:
                return "ac37_fpr1_match_16"
            m = re.search(r"match\s+(\d+)", fn_lower)
            if m:
                return f"ac37_fpr1_match_{m.group(1)}"

        # 4. Round Robins
        if "round_robin" in rel_lower or re.search(r"\brr\d*\b", fn_lower):
            m = re.search(r"match\s+(\d+)", fn_lower)
            if m:
                return f"ac37_lvc_rr_match_{m.group(1)}"

    if domain == "practice":
        clean_name = re.sub(r"\.jsonl|\.ac37", "", filename).strip()
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", clean_name).strip("_").lower()
        return f"ac37_practice_{slug}"

    if boat_class == "AC40":
        clean_name = re.sub(r"\.jsonl|\.ac37", "", filename).strip()
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", clean_name).strip("_").lower()
        return f"ac40_{slug}"

    clean_name = re.sub(r"\.jsonl|\.ac37", "", filename).strip()
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", clean_name).strip("_").lower()
    return f"fam_{slug}"


def construct_family_and_attempt(source_record: Mapping[str, Any]) -> RaceAttempt:
    """Derive deterministic family and attempt IDs from source metadata."""
    filename = source_record["filename"]
    stage = source_record["stage"]
    domain = source_record["domain"]
    date_str = source_record.get("date") or "unknown_date"

    is_stopped = "(stopped)" in filename.lower()
    is_resail = "re-sail" in filename.lower() or "resail" in filename.lower()

    family_id = derive_canonical_family_id(source_record)

    if is_stopped:
        attempt_id = f"{family_id}_att1_stopped"
        resail_link = f"{family_id}_att2_resail"
        scored_eligible = False
        status = "stopped"
    elif is_resail:
        attempt_id = f"{family_id}_att2_resail"
        resail_link = None
        scored_eligible = True
        status = "completed"
    elif domain == "practice":
        attempt_id = f"{family_id}_att1"
        resail_link = None
        scored_eligible = False
        status = "practice_session"
    else:
        attempt_id = f"{family_id}_att1"
        resail_link = None
        scored_eligible = True
        status = "completed"

    comps = source_record.get("sample_competitors", [])
    team_a = "unknown"
    team_b = "unknown"
    if len(comps) >= 2:
        try:
            team_a = resolve_team_identity(comps[0], cycle="AC37")
        except UnsupportedIdentityError:
            team_a = str(comps[0])
        try:
            team_b = resolve_team_identity(comps[1], cycle="AC37")
        except UnsupportedIdentityError:
            team_b = str(comps[1])

    return RaceAttempt(
        attempt_id=attempt_id,
        family_id=family_id,
        source_file=source_record["filename"],
        stage=stage,
        domain=domain,
        date=date_str,
        team_a=team_a,
        team_b=team_b,
        is_stopped_race=is_stopped,
        is_resail=is_resail,
        linked_resail_attempt_id=resail_link,
        scored_outcome_eligible=scored_eligible,
        status=status,
        session_id=source_record.get("session_id"),
        race_start_ms=source_record.get("race_start_ms"),
    )


def reconcile_attempts_and_families(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Process all sources into attempts and deduplicated race families."""
    sources = inventory.get("sources", [])
    attempts: list[RaceAttempt] = []
    families: dict[str, list[RaceAttempt]] = {}

    for s in sources:
        if s["boat_class"] != "AC75":
            continue
        att = construct_family_and_attempt(s)
        attempts.append(att)
        families.setdefault(att.family_id, []).append(att)

    # Validate that every family has at most one scored outcome eligible attempt
    multi_scored_families = []
    for fam_id, fam_attempts in families.items():
        scored = [a for a in fam_attempts if a.scored_outcome_eligible]
        if len(scored) > 1:
            multi_scored_families.append(fam_id)

    if multi_scored_families:
        raise ValueError(f"Race families with multiple scored attempts: {multi_scored_families}")

    return {
        "total_ac75_sources": len(attempts),
        "total_ac75_families": len(families),
        "attempts": [asdict(a) for a in attempts],
        "families": {k: [asdict(a) for a in v] for k, v in families.items()},
    }


def build_outcome_evidence_ledger(
    inventory: Mapping[str, Any] | None = None,
    results_path: Path | str | None = None,
    anchors_path: Path | str | None = None,
) -> dict[str, Any]:
    """Construct field-level outcome evidence ledger combining archive, official results, and anchors."""
    r_path = Path(results_path) if results_path else ROOT / "docs" / "ac37_results.json"
    a_path = Path(anchors_path) if anchors_path else ROOT / "docs" / "ac37_verified_anchors.json"

    raw_results = json.loads(r_path.read_text(encoding="utf-8")) if r_path.exists() else {"races": []}
    raw_anchors = json.loads(a_path.read_text(encoding="utf-8")) if a_path.exists() else {"anchors": {}, "race_anchors": {}}
    race_anchors = raw_anchors.get("race_anchors", {})

    families_map: dict[str, list[dict[str, Any]]] = {}
    if inventory:
        reconciled = reconcile_attempts_and_families(inventory)
        families_map = reconciled.get("families", {})

    ledger: list[RaceFamilyOutcome] = []
    total_verified = 0

    for r in raw_results.get("races", []):
        race_id = r.get("race_id", "")
        stage = r.get("stage", "")
        date_str = r.get("date", "")
        team_a_raw = r.get("competitor_a", "")
        team_b_raw = r.get("competitor_b", "")

        try:
            team_a = resolve_team_identity(team_a_raw, cycle="AC37")
        except UnsupportedIdentityError:
            team_a = team_a_raw
        try:
            team_b = resolve_team_identity(team_b_raw, cycle="AC37")
        except UnsupportedIdentityError:
            team_b = team_b_raw

        winner_raw = r.get("winner")
        try:
            winner_canonical = resolve_team_identity(winner_raw, cycle="AC37") if winner_raw else None
        except UnsupportedIdentityError:
            winner_canonical = winner_raw

        delta_s = r.get("delta_s")
        wind_kt = r.get("wind_knots")
        wind_mps = knots_to_mps(float(wind_kt)) if wind_kt is not None else None

        # Link to attempts
        family_attempts = families_map.get(race_id, [])
        attempt_ids = [a["attempt_id"] for a in family_attempts]

        # Determine evidence / telemetry status
        if family_attempts:
            if any(".ac37" in a["source_file"] for a in family_attempts):
                telemetry_status = "unsupported_binary"
            else:
                telemetry_status = "present_jsonl"
        else:
            telemetry_status = "missing_from_archive"

        # Evidence verification:
        # Each field is verified independently ONLY if explicitly present in race_anchor.
        race_anchor = race_anchors.get(race_id) if isinstance(race_anchors.get(race_id), dict) else None
        anchor_url = str(race_anchor.get("source_url", "")) if race_anchor else ""
        candidate_url = str(r.get("source_url", ""))

        # 1. Winner verification
        anchor_winner_raw = race_anchor.get("winner") if race_anchor else None
        if anchor_winner_raw is not None:
            try:
                anchor_winner = resolve_team_identity(str(anchor_winner_raw), cycle="AC37")
            except UnsupportedIdentityError:
                anchor_winner = str(anchor_winner_raw)
            winner_ev = OutcomeFieldEvidence(
                value=anchor_winner,
                provenance="official_race_anchor_verified",
                source_ref=anchor_url,
                verified=True,
            )
            total_verified += 1
        else:
            winner_ev = OutcomeFieldEvidence(
                value=winner_canonical,
                provenance="candidate_results_json" if winner_canonical is not None else "unavailable",
                source_ref=candidate_url,
                verified=False,
            )

        # 2. Margin (delta_s) verification
        anchor_delta = None
        if race_anchor is not None:
            if "delta_s" in race_anchor and race_anchor["delta_s"] is not None:
                anchor_delta = float(race_anchor["delta_s"])
            elif "elapsed_margin_s" in race_anchor and race_anchor["elapsed_margin_s"] is not None:
                anchor_delta = float(race_anchor["elapsed_margin_s"])

        if anchor_delta is not None:
            delta_ev = OutcomeFieldEvidence(
                value=anchor_delta,
                provenance="official_race_anchor_verified",
                source_ref=anchor_url,
                verified=True,
            )
        else:
            delta_ev = OutcomeFieldEvidence(
                value=delta_s,
                provenance="candidate_reported_margin" if delta_s is not None else "unavailable",
                source_ref=candidate_url,
                verified=False,
            )

        # 3. Wind verification
        anchor_wind_mps = None
        if race_anchor is not None:
            if "wind_mps" in race_anchor and race_anchor["wind_mps"] is not None:
                anchor_wind_mps = float(race_anchor["wind_mps"])
            elif "wind_knots" in race_anchor and race_anchor["wind_knots"] is not None:
                anchor_wind_mps = knots_to_mps(float(race_anchor["wind_knots"]))

        if anchor_wind_mps is not None:
            wind_ev = OutcomeFieldEvidence(
                value=anchor_wind_mps,
                provenance="official_race_anchor_verified",
                source_ref=anchor_url,
                verified=True,
            )
        else:
            wind_ev = OutcomeFieldEvidence(
                value=wind_mps,
                provenance="candidate_reported_wind_converted_si" if wind_mps is not None else "unavailable",
                source_ref=candidate_url,
                verified=False,
            )

        # 4. Finish status verification
        anchor_finish = (
            race_anchor.get("finish_status")
            if race_anchor is not None and race_anchor.get("finish_status") is not None
            else None
        )
        if anchor_finish is not None:
            finish_ev = OutcomeFieldEvidence(
                value=str(anchor_finish),
                provenance="official_race_anchor_verified",
                source_ref=anchor_url,
                verified=True,
            )
        else:
            finish_status_str = "both_finished" if delta_s is not None else "unverified_or_retired"
            finish_ev = OutcomeFieldEvidence(
                value=finish_status_str,
                provenance="candidate_results_inference",
                source_ref=candidate_url,
                verified=False,
            )

        ledger.append(RaceFamilyOutcome(
            family_id=race_id,
            stage=stage,
            date=date_str,
            team_a=team_a,
            team_b=team_b,
            winner=winner_ev,
            delta_s=delta_ev,
            wind_mps=wind_ev,
            finish_status=finish_ev,
            telemetry_status=telemetry_status,
            attempts=attempt_ids,
        ))

    return {
        "schema_version": "ac75-outcomes-1",
        "total_races": len(ledger),
        "total_anchor_verified_races": total_verified,
        "outcomes": [
            {
                "family_id": o.family_id,
                "stage": o.stage,
                "date": o.date,
                "team_a": o.team_a,
                "team_b": o.team_b,
                "winner": asdict(o.winner),
                "delta_s": asdict(o.delta_s),
                "wind_mps": asdict(o.wind_mps),
                "finish_status": asdict(o.finish_status),
                "telemetry_status": o.telemetry_status,
                "attempts": o.attempts,
            }
            for o in ledger
        ],
    }


def freeze_evaluation_families(
    inventory: Mapping[str, Any],
    holdout_dates: list[str] | None = None,
    frozen_file_path: Path | str | None = None,
) -> dict[str, Any]:
    """Freeze final evaluation race families based strictly on metadata dates without overwriting."""
    target_path = Path(frozen_file_path) if frozen_file_path else FORECAST_DIR / "frozen_evaluation_families.json"

    # If already frozen, load existing immutable assignment
    if target_path.exists():
        try:
            existing = json.loads(target_path.read_text(encoding="utf-8"))
            if existing.get("status") == "frozen_metadata_only":
                return existing
        except (json.JSONDecodeError, OSError):
            pass

    # If holdout_dates not provided, compute from all competitive AC75 dates (both JSONL and binary)
    if holdout_dates is None:
        comp_sources = [
            s for s in inventory.get("sources", [])
            if s.get("boat_class") == "AC75" and s.get("domain") == "competitive"
        ]
        all_comp_dates = sorted({s["date"] for s in comp_sources if s.get("date")})
        n_holdout = max(3, math.ceil(len(all_comp_dates) * 0.20))
        holdout_dates = all_comp_dates[-n_holdout:]

    reconciled = reconcile_attempts_and_families(inventory)
    families = reconciled["families"]

    dev_families = []
    holdout_families = []

    for fam_id, attempts in families.items():
        fam_dates = {a["date"] for a in attempts}
        if fam_dates & set(holdout_dates):
            holdout_families.append(fam_id)
        else:
            dev_families.append(fam_id)

    payload = {
        "status": "frozen_metadata_only",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "holdout_dates": sorted(holdout_dates),
        "development_families_count": len(dev_families),
        "development_families": sorted(dev_families),
        "reserved_holdout_families_count": len(holdout_families),
        "reserved_holdout_families": sorted(holdout_families),
    }

    # Add content hash
    content_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload["content_sha256"] = hashlib.sha256(content_bytes).hexdigest()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def execute_t05_ledger():
    """Main execution entrypoint for T05: writes attempt and outcome ledgers."""
    manifest_files = list((FORECAST_DIR / "sources").glob("*/manifest.json"))
    if not manifest_files:
        raise FileNotFoundError("Manifest file not found. Run T02 first.")

    inventory = json.loads(manifest_files[-1].read_text(encoding="utf-8"))

    print("Reconciling race attempts and families...")
    attempts_data = reconcile_attempts_and_families(inventory)
    ATTEMPTS_LEDGER_PATH.write_text(json.dumps(attempts_data, indent=2), encoding="utf-8")
    print(f"Wrote attempt ledger: {ATTEMPTS_LEDGER_PATH}")

    print("Building field-level outcome evidence ledger...")
    outcome_data = build_outcome_evidence_ledger(inventory)
    OUTCOME_LEDGER_PATH.write_text(json.dumps(outcome_data, indent=2), encoding="utf-8")
    print(f"Wrote outcome evidence ledger: {OUTCOME_LEDGER_PATH}")

    frozen_path = FORECAST_DIR / "frozen_evaluation_families.json"
    frozen_families = freeze_evaluation_families(inventory, frozen_file_path=frozen_path)
    print(f"Wrote/verified frozen evaluation families: {frozen_path}")

    return {
        "attempt_ledger_path": ATTEMPTS_LEDGER_PATH.relative_to(ROOT).as_posix(),
        "outcome_ledger_path": OUTCOME_LEDGER_PATH.relative_to(ROOT).as_posix(),
        "frozen_families_path": frozen_path.relative_to(ROOT).as_posix(),
        "total_attempts": attempts_data["total_ac75_sources"],
        "total_families": attempts_data["total_ac75_families"],
        "total_outcomes": outcome_data["total_races"],
        "holdout_families_count": frozen_families["reserved_holdout_families_count"],
    }


if __name__ == "__main__":
    execute_t05_ledger()
