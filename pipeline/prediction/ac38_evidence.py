"""Field-level evidence validation, cycle identities, and AC38 eligibility ledger."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

GENERIC_URLS = (
    "https://www.americascup.com/results",
    "https://37th.americascup.com/results",
)

AC37_SHARED_TEAMS = (
    "ALINGHI",
    "AMERICAN_MAGIC",
    "ETNZ",
    "INEOS",
    "LUNA_ROSSA",
    "ORIENT_EXPRESS",
)


def parse_utc_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    norm = ts.strip()
    if norm.endswith("Z"):
        norm = norm[:-1] + "+00:00"
    dt = datetime.fromisoformat(norm)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_valid_independent_evidence(root: Path, ev: dict | None, *, required_scopes: tuple[str, ...]) -> tuple[bool, str]:
    if not isinstance(ev, dict):
        return False, "missing_evidence_object"
    src = str(ev.get("supporting_source") or "").strip()
    if not src or any(src.rstrip("/") == g.rstrip("/") for g in GENERIC_URLS):
        return False, "generic_or_missing_source_url"
    if ev.get("review_status") != "independently_anchored":
        return False, f"review_status:{ev.get('review_status')}"
    if ev.get("result_scope") not in required_scopes:
        return False, f"insufficient_scope:{ev.get('result_scope')}"
    cap_rel = ev.get("captured_path")
    digest = str(ev.get("source_sha256") or "")
    if not cap_rel or len(digest) != 64:
        return False, "missing_captured_artifact_or_sha256"
    cap_path = root / cap_rel
    if not cap_path.is_file():
        return False, "captured_file_missing_on_disk"
    actual_sha = hashlib.sha256(cap_path.read_bytes()).hexdigest()
    if actual_sha != digest:
        return False, "captured_sha256_mismatch"
    if not ev.get("available_at_utc"):
        return False, "missing_available_at_utc"
    return True, "ok"


def _ac37_ledger_entries(root: Path, cutoff_dt: datetime | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    ac40_doc = json.loads((root / "docs" / "ac37_ac40_2023_results.json").read_text(encoding="utf-8"))
    for r in ac40_doc.get("races", []):
        ev = r.get("evidence")
        ok, reason = is_valid_independent_evidence(root, ev, required_scopes=("full_fleet_order", "match_final_winner"))
        avail_dt = parse_utc_iso(ev.get("available_at_utc") if isinstance(ev, dict) else None)
        if r.get("status") != "completed":
            elig, why = False, r.get("exclusion_reason") or f"status:{r.get('status')}"
        elif cutoff_dt is not None and avail_dt is not None and avail_dt > cutoff_dt:
            elig, why = False, "after_issuance_cutoff_utc"
        elif not ok:
            elig, why = False, reason
        elif len(r.get("official_order", [])) < 2:
            elig, why = False, "fewer_than_two_finishers"
        else:
            elig, why = True, "independently_anchored_completed_race"
        entries.append({
            "observation_id": r["race_id"],
            "domain": "ac37_ac40",
            "cycle": "ac37",
            "date": r.get("date"),
            "available_at_utc": ev.get("available_at_utc") if isinstance(ev, dict) else None,
            "eligible_transfer_primary": elig,
            "eligible_transfer_sensitivity_reconstructed": elig,
            "exclusion_reason": None if elig else why,
            "evidence_review_status": ev.get("review_status") if isinstance(ev, dict) else "missing",
            "cycle_teams": [f"ac37:{t}" for t in r.get("official_order", [])],
        })

    ac75_doc = json.loads((root / "docs" / "ac37_results.json").read_text(encoding="utf-8"))
    for r in ac75_doc.get("races", []):
        ev = r.get("evidence")
        ok, reason = is_valid_independent_evidence(root, ev, required_scopes=("match_winner",))
        avail_dt = parse_utc_iso(ev.get("available_at_utc") if isinstance(ev, dict) else None)
        if r.get("status") != "completed":
            elig, why = False, f"status:{r.get('status')}"
        elif cutoff_dt is not None and avail_dt is not None and avail_dt > cutoff_dt:
            elig, why = False, "after_issuance_cutoff_utc"
        elif not ok:
            elig, why = False, reason
        else:
            elig, why = True, "independently_anchored_completed_match"
        entries.append({
            "observation_id": r["race_id"],
            "domain": "ac37_ac75",
            "cycle": "ac37",
            "date": r.get("date"),
            "available_at_utc": ev.get("available_at_utc") if isinstance(ev, dict) else None,
            "eligible_transfer_primary": elig,
            "eligible_transfer_sensitivity_reconstructed": elig,
            "exclusion_reason": None if elig else why,
            "evidence_review_status": ev.get("review_status") if isinstance(ev, dict) else "missing",
            "cycle_teams": [f"ac37:{r['competitor_a']}", f"ac37:{r['competitor_b']}"],
        })
    for s in ac75_doc.get("stopped_attempts", []):
        entries.append({
            "observation_id": s["attempt_id"],
            "domain": "ac37_ac75",
            "cycle": "ac37",
            "date": s.get("date"),
            "available_at_utc": (s.get("evidence") or {}).get("available_at_utc"),
            "eligible_transfer_primary": False,
            "eligible_transfer_sensitivity_reconstructed": False,
            "exclusion_reason": s.get("exclusion_reason", "stopped_race_attempt"),
            "evidence_review_status": (s.get("evidence") or {}).get("review_status", "stopped"),
            "cycle_teams": [],
        })
    return entries


def _ac38_ledger_entries(root: Path, cutoff_dt: datetime | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    off_doc = json.loads((root / "docs" / "official_results_ac38_prelims.json").read_text(encoding="utf-8"))
    off_by_id = {r["race_id"]: r for r in off_doc.get("races", [])}
    ds_idx = json.loads((root / ".forecast" / "dataset" / "index.json").read_text(encoding="utf-8"))

    seen_ids = set()
    for ds_race in ds_idx.get("races", []):
        rid = ds_race["race_id"]
        seen_ids.add(rid)
        if ds_race.get("practice", False):
            entries.append({
                "observation_id": rid,
                "domain": "ac38_ac40",
                "cycle": "ac38",
                "date": ds_race.get("date"),
                "available_at_utc": f"{ds_race.get('date')}T18:00:00Z",
                "eligible_ac38_anchored_only": False,
                "eligible_ac38_with_reconstructed": False,
                "exclusion_reason": "practice_session_excluded",
                "evidence_review_status": "practice_excluded",
            })
            continue
        r = off_by_id.get(rid)
        entries.append(_evaluate_ac38_competitive_race(root, rid, r, cutoff_dt))

    for rid, r in off_by_id.items():
        if rid not in seen_ids:
            entries.append(_evaluate_ac38_competitive_race(root, rid, r, cutoff_dt))
    return entries


def _evaluate_ac38_competitive_race(root: Path, rid: str, r: dict | None, cutoff_dt: datetime | None) -> dict[str, Any]:
    if r is None:
        return {
            "observation_id": rid,
            "domain": "ac38_ac40",
            "cycle": "ac38",
            "date": None,
            "available_at_utc": None,
            "eligible_ac38_anchored_only": False,
            "eligible_ac38_with_reconstructed": False,
            "exclusion_reason": "missing_result_record",
            "evidence_review_status": "missing",
        }
    ev_bundle = r.get("evidence") or {}
    ind_ev = ev_bundle.get("independent_anchor")
    tel_ev = ev_bundle.get("telemetry_reconstruction")
    ind_ok, ind_reason = is_valid_independent_evidence(root, ind_ev, required_scopes=("full_fleet_order", "match_final_winner"))
    avail_iso = (ind_ev or {}).get("available_at_utc") or (tel_ev or {}).get("available_at_utc") or f"{r.get('date')}T23:59:59Z"
    avail_dt = parse_utc_iso(avail_iso)
    in_cutoff = cutoff_dt is None or (avail_dt is not None and avail_dt <= cutoff_dt)

    tel_ok = False
    if isinstance(tel_ev, dict) and tel_ev.get("captured_path"):
        tel_p = root / tel_ev["captured_path"]
        tel_ok = tel_p.is_file() and hashlib.sha256(tel_p.read_bytes()).hexdigest() == tel_ev.get("source_sha256")
    has_order = len(r.get("official_order") or r.get("on_water_finish_order") or []) >= 2

    elig_anchored = bool(in_cutoff and ind_ok and has_order)
    elig_recon = bool(in_cutoff and has_order and (ind_ok or tel_ok))
    excl = None if elig_anchored else ("after_issuance_cutoff_utc" if not in_cutoff else ind_reason)
    return {
        "observation_id": rid,
        "domain": "ac38_ac40",
        "cycle": "ac38",
        "date": r.get("date"),
        "available_at_utc": avail_iso,
        "eligible_ac38_anchored_only": elig_anchored,
        "eligible_ac38_with_reconstructed": elig_recon,
        "exclusion_reason": excl,
        "evidence_review_status": ev_bundle.get("primary_review_status", "unknown"),
        "reconstructed_fallback_used": bool(elig_recon and not elig_anchored),
    }


def build_eligibility_ledger(
    root: Path,
    *,
    issuance_cutoff_utc: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    root = Path(root)
    cutoff_dt = parse_utc_iso(issuance_cutoff_utc) if issuance_cutoff_utc else None
    ac37_entries = _ac37_ledger_entries(root, cutoff_dt)
    ac38_entries = _ac38_ledger_entries(root, cutoff_dt)

    rules_doc = json.loads((root / "docs" / "forecast_rules_sources.json").read_text(encoding="utf-8"))
    roster_doc = json.loads((root / "docs" / "ac38_roster.json").read_text(encoding="utf-8"))

    ledger = {
        "schema_version": "ac38-eligibility-ledger-1",
        "issuance_cutoff_utc": issuance_cutoff_utc,
        "cycle_identities": {
            "continuity_from_country_code": False,
            "ac37_teams": [f"ac37:{t}" for t in AC37_SHARED_TEAMS],
            "ac38_syndicates": [s["campaign_team_id"] for s in roster_doc.get("syndicates", [])],
        },
        "summary": {
            "transfer_primary_eligible": sum(1 for e in ac37_entries if e["eligible_transfer_primary"]),
            "transfer_primary_excluded": sum(1 for e in ac37_entries if not e["eligible_transfer_primary"]),
            "ac38_anchored_only_eligible": sum(1 for e in ac38_entries if e["eligible_ac38_anchored_only"]),
            "ac38_with_reconstructed_eligible": sum(1 for e in ac38_entries if e["eligible_ac38_with_reconstructed"]),
            "ac38_excluded_total": sum(1 for e in ac38_entries if not e["eligible_ac38_with_reconstructed"]),
        },
        "rules_and_roster_status": {
            "rules_precedence": rules_doc.get("rules_precedence", {}),
            "unresolved_clauses": rules_doc.get("unresolved_clauses", []),
            "default_mapping_policy": roster_doc.get("default_mapping_policy", {}),
        },
        "ac37_observations": ac37_entries,
        "ac38_observations": ac38_entries,
    }
    if write:
        out_path = root / ".forecast" / "ac38" / "eligibility_ledger.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return ledger
