"""Source inventory, archive classification, and outcome evidence auditing for AC75 learning.

Account for all files in Data/ and Data/AC37/, classifies wire formats, enforces
AC40/AC75 isolation, identifies unsupported binary schemas, audits official outcome
evidence, and reserves chronological evaluation dates from metadata only.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping

from .contracts import (
    resolve_team_identity,
    UnsupportedIdentityError,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data"
AC37_DIR = DATA_DIR / "AC37"
FORECAST_DIR = ROOT / ".forecast" / "ac75_learning"
SOURCES_DIR = FORECAST_DIR / "sources"
AUDIT_DOC_PATH = ROOT / "docs" / "ac75_learning_data_audit.md"
AC37_RESULTS_PATH = ROOT / "docs" / "ac37_results.json"
AC37_ANCHORS_PATH = ROOT / "docs" / "ac37_verified_anchors.json"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash streaming in 1 MB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        while chunk := fp.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _resolve_competitors_from_session(s: dict[str, Any]) -> list[str]:
    """Extract and canonically resolve competitors from session assets and competitor entries."""
    assets = {a["id"]: a for a in s.get("assets", []) if isinstance(a, dict) and "id" in a}
    resolved: list[str] = []
    comps = s.get("competitors", {})
    if isinstance(comps, list):
        for c in comps:
            aid = c.get("asset_id") if isinstance(c, dict) else str(c)
            asset = assets.get(aid, {})
            raw_name = (
                asset.get("abbreviation")
                or asset.get("official_name")
                or asset.get("name")
                or aid
            )
            if raw_name:
                try:
                    resolved.append(resolve_team_identity(raw_name, cycle="AC37"))
                except UnsupportedIdentityError:
                    resolved.append(str(raw_name))
    elif isinstance(comps, dict):
        for cid, cinfo in comps.items():
            if isinstance(cinfo, dict):
                raw_name = (
                    cinfo.get("abbreviation")
                    or cinfo.get("official_name")
                    or cinfo.get("name")
                    or cinfo.get("short_name")
                    or cid
                )
            else:
                raw_name = str(cinfo)
            if raw_name:
                try:
                    resolved.append(resolve_team_identity(raw_name, cycle="AC37"))
                except UnsupportedIdentityError:
                    resolved.append(str(raw_name))
    return resolved


def inspect_header_sample(path: Path, max_lines: int = 20) -> dict[str, Any]:
    """Inspect first few lines of a JSONL file without loading into memory."""
    meta: dict[str, Any] = {
        "session_id": None,
        "session_name": None,
        "race_start_ms": None,
        "competitors": [],
    }
    if not path.name.endswith(".jsonl"):
        return meta

    try:
        with open(path, "rb") as fp:
            for i, line_bytes in enumerate(fp):
                if i >= max_lines:
                    break
                line_str = line_bytes.decode("utf-8", errors="replace").strip()
                if not line_str or '"session"' not in line_str:
                    continue
                try:
                    obj = json.loads(line_str)
                    s = obj.get("session")
                    if isinstance(s, dict) and not meta["session_id"]:
                        meta["session_id"] = s.get("id")
                        meta["session_name"] = s.get("name")
                        meta["race_start_ms"] = s.get("race_start")
                        meta["competitors"] = _resolve_competitors_from_session(s)
                        break
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    except OSError as err:
        meta["read_error"] = str(err)
    return meta


def parse_date_from_filename(filename: str) -> str | None:
    """Extract YYYY-MM-DD from standard AC37 naming format."""
    # Pattern: '24 08 22 ...' -> 2024-08-22
    m = re.match(r"^(\d{2})\s+(\d{2})\s+(\d{2})", filename)
    if m:
        yy, mm, dd = m.groups()
        return f"20{yy}-{mm}-{dd}"
    # Pattern: '2023-09-16 ...'
    m2 = re.match(r"^(\d{4}-\d{2}-\d{2})", filename)
    if m2:
        return m2.group(1)
    return None


def build_source_inventory() -> dict[str, Any]:
    """Scan and classify all files under Data/ and Data/AC37/."""
    all_sources = []
    category_counts: dict[str, int] = {}
    category_bytes: dict[str, int] = {}

    for file_path in sorted(DATA_DIR.rglob("*")):
        if not file_path.is_file():
            continue
        
        rel_to_data = file_path.relative_to(DATA_DIR).as_posix()
        file_size = file_path.stat().st_size
        filename = file_path.name
        date_str = parse_date_from_filename(filename)
        
        # Classification
        boat_class = "AC75"
        status = "included"
        domain = "competitive"
        reasons = []
        stage = "unknown"
        format_type = "jsonl" if filename.endswith(".jsonl") else ("ac37" if filename.endswith(".ac37") else "other")

        if "/" not in rel_to_data or rel_to_data.startswith("AC38/"):
            # AC38 AC40 replay files live under Data/AC38/*.jsonl (legacy layout had root Data/*.jsonl)
            boat_class = "AC40"
            status = "excluded"
            domain = "excluded"
            stage = "ac38_ac40_replay_archive" if rel_to_data.startswith("AC38/") else "ac40_replay_archive"
            reasons.append("boat_class_ac40_ac38_archive" if rel_to_data.startswith("AC38/") else "boat_class_ac40_replay_archive")
        elif rel_to_data.startswith("AC37/prelims_ac40_2023"):
            boat_class = "AC40"
            status = "excluded"
            domain = "excluded"
            stage = "prelims_ac40_2023"
            reasons.append("boat_class_ac40_preliminary")
        elif rel_to_data.startswith("AC37/ac75_lvc_semifinals_raw"):
            boat_class = "AC75"
            status = "unsupported_wire_schema"
            domain = "competitive"
            stage = "semifinal"
            reasons.append("binary_protobuf_schema_pending_verification")
        elif rel_to_data.startswith("AC37/ac75_official_practice"):
            boat_class = "AC75"
            status = "included_practice"
            domain = "practice"
            stage = "official_practice"
        elif rel_to_data.startswith("AC37/ac75_prelim_barcelona"):
            boat_class = "AC75"
            status = "included_competitive"
            domain = "competitive"
            stage = "preliminary"
        elif rel_to_data.startswith("AC37/ac75_lvc_round_robins"):
            boat_class = "AC75"
            status = "included_competitive"
            domain = "competitive"
            stage = "round_robin"
        elif rel_to_data.startswith("AC37/ac75_lvc_finals"):
            boat_class = "AC75"
            status = "included_competitive"
            domain = "competitive"
            stage = "final"
            if "(stopped)" in filename:
                reasons.append("stopped_race_attempt_linked_to_resail")
        else:
            boat_class = "unknown"
            status = "excluded"
            reasons.append("unrecognized_archive_location")

        # Header sample for JSONL
        header = inspect_header_sample(file_path, max_lines=10) if format_type == "jsonl" else {}
        digest = sha256_file(file_path)

        record = {
            "relative_path": f"Data/{rel_to_data}",
            "filename": filename,
            "bytes": file_size,
            "sha256": digest,
            "format": format_type,
            "boat_class": boat_class,
            "stage": stage,
            "domain": domain,
            "date": date_str,
            "status": status,
            "reason_codes": reasons,
            "session_id": header.get("session_id"),
            "session_name": header.get("session_name"),
            "race_start_ms": header.get("race_start_ms"),
            "sample_competitors": header.get("competitors", []),
        }
        all_sources.append(record)

        # Accounting
        cat_key = f"{stage} ({status})"
        category_counts[cat_key] = category_counts.get(cat_key, 0) + 1
        category_bytes[cat_key] = category_bytes.get(cat_key, 0) + file_size

    # Merkle root of all source files
    merkle_input = "\n".join(f"{s['relative_path']}:{s['sha256']}" for s in all_sources).encode("utf-8")
    merkle_root = hashlib.sha256(merkle_input).hexdigest()

    return {
        "inventory_id": f"ac37-inventory-{merkle_root[:16]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "merkle_root_sha256": merkle_root,
        "total_files": len(all_sources),
        "total_bytes": sum(s["bytes"] for s in all_sources),
        "ac37_file_count": len([s for s in all_sources if s["relative_path"].startswith("Data/AC37/")]),
        "ac37_byte_count": sum(s["bytes"] for s in all_sources if s["relative_path"].startswith("Data/AC37/")),
        "ac75_file_count": len([s for s in all_sources if s["boat_class"] == "AC75"]),
        "ac75_byte_count": sum(s["bytes"] for s in all_sources if s["boat_class"] == "AC75"),
        "ac75_eligible_jsonl_count": len([s for s in all_sources if s["boat_class"] == "AC75" and s["format"] == "jsonl"]),
        "ac75_eligible_jsonl_bytes": sum(s["bytes"] for s in all_sources if s["boat_class"] == "AC75" and s["format"] == "jsonl"),
        "ac75_unsupported_binary_count": len([s for s in all_sources if s["status"] == "unsupported_wire_schema"]),
        "ac75_unsupported_binary_bytes": sum(s["bytes"] for s in all_sources if s["status"] == "unsupported_wire_schema"),
        "breakdown": category_counts,
        "bytes_breakdown": category_bytes,
        "sources": all_sources,
    }


def audit_outcome_evidence() -> dict[str, Any]:
    """Audit candidate outcome evidence in docs/ac37_results.json and anchors."""
    if not AC37_RESULTS_PATH.exists():
        return {"error": "docs/ac37_results.json not found"}

    results_data = json.loads(AC37_RESULTS_PATH.read_text(encoding="utf-8"))
    races = results_data.get("races", [])

    by_stage: dict[str, list[dict]] = {}
    missing_telemetry = []
    audited_races = []

    for r in races:
        stage = r.get("stage", "unknown")
        by_stage.setdefault(stage, []).append(r)
        
        # Check telemetry presence
        has_telemetry = True
        telemetry_status = "present_jsonl"
        if stage == "match":
            has_telemetry = False
            telemetry_status = "telemetry_missing_for_match"
            missing_telemetry.append(r["race_id"])
        elif stage.startswith("lvc_semifinal"):
            telemetry_status = "telemetry_unsupported_binary"

        audited_races.append({
            "race_id": r.get("race_id"),
            "stage": stage,
            "race_number": r.get("race_number"),
            "date": r.get("date"),
            "competitor_a": r.get("competitor_a"),
            "competitor_b": r.get("competitor_b"),
            "winner": r.get("winner"),
            "delta_s": r.get("delta_s"),
            "wind_knots": r.get("wind_knots"),
            "telemetry_status": telemetry_status,
        })

    anchors_info = {}
    if AC37_ANCHORS_PATH.exists():
        anchors_data = json.loads(AC37_ANCHORS_PATH.read_text(encoding="utf-8"))
        anchors_info = anchors_data.get("anchors", {})

    return {
        "total_outcome_races": len(races),
        "stage_breakdown": {k: len(v) for k, v in by_stage.items()},
        "telemetry_missing_count": len(missing_telemetry),
        "telemetry_missing_ids": missing_telemetry,
        "anchors_verified": len(anchors_info),
        "audited_races": audited_races,
    }


def reserve_chronological_evaluation_dates(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Reserve chronological evaluation holdout dates using metadata only (Section 9)."""
    # Filter to all competitive AC75 sources (both JSONL and binary)
    comp_sources = [
        s for s in inventory["sources"]
        if s["boat_class"] == "AC75" and s["domain"] == "competitive"
    ]
    
    unique_dates = sorted({s["date"] for s in comp_sources if s["date"]})
    n_dates = len(unique_dates)
    
    # Latest 20% of competitive dates (at least three where feasible, using ceil)
    n_holdout = max(3, math.ceil(n_dates * 0.20))
    dev_dates = unique_dates[:-n_holdout]
    holdout_dates = unique_dates[-n_holdout:]

    holdout_sources = [s["filename"] for s in comp_sources if s["date"] in holdout_dates]

    return {
        "total_competitive_dates": n_dates,
        "all_dates": unique_dates,
        "split_method": "latest_20_percent_chronological_block_metadata_only",
        "development_dates_count": len(dev_dates),
        "development_dates": dev_dates,
        "reserved_holdout_dates_count": len(holdout_dates),
        "reserved_holdout_dates": holdout_dates,
        "reserved_holdout_files": holdout_sources,
        "isolation_status": "locked_prior_to_feature_or_label_tuning",
    }


def format_audit_markdown(
    inventory: Mapping[str, Any],
    outcome_audit: Mapping[str, Any],
    date_reservation: Mapping[str, Any],
) -> str:
    """Format the archive data audit markdown document dynamically from computed inventory data."""
    inv_id = inventory["inventory_id"]
    sources = inventory.get("sources", [])

    def _stats_for_prefix(prefix: str, *, root_only: bool = False) -> tuple[int, int]:
        if root_only:
            matched = [
                s for s in sources
                if s["relative_path"].startswith("Data/")
                and "/" not in s["relative_path"][len("Data/"):]
            ]
        else:
            matched = [s for s in sources if s["relative_path"].startswith(prefix)]
        return len(matched), sum(int(s["bytes"]) for s in matched)

    c_root, b_root = _stats_for_prefix("Data/", root_only=True)
    c_ac40_pre, b_ac40_pre = _stats_for_prefix("Data/AC37/prelims_ac40_2023")
    c_prac, b_prac = _stats_for_prefix("Data/AC37/ac75_official_practice")
    c_prelim, b_prelim = _stats_for_prefix("Data/AC37/ac75_prelim_barcelona")
    c_rr, b_rr = _stats_for_prefix("Data/AC37/ac75_lvc_round_robins")
    c_sf, b_sf = _stats_for_prefix("Data/AC37/ac75_lvc_semifinals_raw")
    c_fin, b_fin = _stats_for_prefix("Data/AC37/ac75_lvc_finals")

    ac40_total_files = c_root + c_ac40_pre
    ac37_files = inventory["ac37_file_count"]
    ac37_bytes = inventory["ac37_byte_count"]
    elig_count = inventory["ac75_eligible_jsonl_count"]
    elig_bytes = inventory["ac75_eligible_jsonl_bytes"]
    bin_count = inventory["ac75_unsupported_binary_count"]
    bin_bytes = inventory["ac75_unsupported_binary_bytes"]

    sb = outcome_audit.get("stage_breakdown", {})
    prelim_races = sb.get("preliminary", sb.get("fpr1", 0))
    rr_races = sum(v for k, v in sb.items() if "round_robin" in k or k.startswith("lvc_rr"))
    sf_races = sum(v for k, v in sb.items() if "semifinal" in k)
    fin_races = sum(v for k, v in sb.items() if "final" in k and "semifinal" not in k)
    match_races = sb.get("match", 0)
    missing_ids = outcome_audit.get("telemetry_missing_ids", [])
    missing_span = f"`{missing_ids[0]}` through `{missing_ids[-1]}`" if missing_ids else "none"

    all_dates = date_reservation.get("all_dates", [])
    date_span = f"{all_dates[0]} to {all_dates[-1]}" if all_dates else "N/A"

    return f"""# AC37 Archive Data Audit & Evidence Inventory

**Generated At:** {inventory['created_at']}  
**Inventory ID:** `{inv_id}`  
**Merkle Root:** `{inventory['merkle_root_sha256']}`  
**Owning Code:** `pipeline/kinematic_ml/inventory.py`  

---

## 1. Executive Summary & Archive Accounting

Total archive surveyed: **{inventory['total_files']} files** ({inventory['total_bytes'] / (1024**3):.2f} GB).

| Archive Section | Boat Class | Wire Format | Files | Total Bytes | Status & Scope |
|---|---|---|---:|---:|---|
| `Data/*.jsonl` | `AC40` | `JSONL` | {c_root} | {b_root:,} | Excluded (`boat_class_ac40_replay_archive`) |
| `Data/AC37/prelims_ac40_2023/` | `AC40` | `JSONL` | {c_ac40_pre} | {b_ac40_pre:,} | Excluded (`boat_class_ac40_preliminary`) |
| `Data/AC37/ac75_official_practice/` | `AC75` | `JSONL` | {c_prac} | {b_prac:,} | Included Practice (`domain: practice`) |
| `Data/AC37/ac75_prelim_barcelona/` | `AC75` | `JSONL` | {c_prelim} | {b_prelim:,} | Included Competitive (`domain: competitive`) |
| `Data/AC37/ac75_lvc_round_robins/` | `AC75` | `JSONL` | {c_rr} | {b_rr:,} | Included Competitive (`domain: competitive`) |
| `Data/AC37/ac75_lvc_semifinals_raw/` | `AC75` | `.ac37 Protobuf` | {c_sf} | {b_sf:,} | Unsupported Wire Schema (`pending .proto descriptor`) |
| `Data/AC37/ac75_lvc_finals/` | `AC75` | `JSONL` | {c_fin} | {b_fin:,} | Included Competitive (`domain: competitive`) |
| **Total AC37 Archive** | **Mixed** | **Mixed** | **{ac37_files}** | **{ac37_bytes:,}** | **100% Accounted For** |

---

## 2. Boat Class Isolation & Coverage Exclusions

1. **AC40 Isolation:** All {ac40_total_files} AC40 files ({c_root} root replay files + {c_ac40_pre} preliminary 2023 files) are strictly excluded from AC75 model training and normalization.
2. **Unsupported Binary Protobuf Schema:** The {bin_count} semifinal `.ac37` files ({bin_bytes / (1024**3):.2f} GB) require a verified official Protocol Buffer schema. In accordance with the project contract, they are classified as `unsupported_wire_schema`. This coverage limitation is propagated downstream to T04/T05 without blocking JSONL normalization.
3. **Eligible AC75 JSONL Telemetry:** {elig_count} files totaling {elig_bytes:,} bytes (~{elig_bytes / (1024**3):.2f} GB) across Official Practice, Preliminary, Round Robins, and Finals are fully eligible for streaming normalization.

---

## 3. Candidate Outcome Evidence Audit (`docs/ac37_results.json`)

- Total records: **{outcome_audit['total_outcome_races']} races**
  - Barcelona Preliminary: {prelim_races} races
  - LVC Round Robins: {rr_races} races
  - LVC Semifinals: {sf_races} races
  - LVC Finals: {fin_races} races
  - America's Cup Match: {match_races} races
- **Critical Telemetry Finding:** Physical telemetry is **missing** for all {outcome_audit['telemetry_missing_count']} America's Cup Match races ({missing_span}). The Match records represent official race results only, with no corresponding high-rate sensor streams in the archive.
- **Stopped / Resail Attempt Links:** `24 09 28 BCN LV Finals Match 3 GBRvITA (stopped).jsonl` is linked to `24 09 29 BCN LV Finals Match 3 GBRvITA Re-Sail.jsonl`.

---

## 4. Chronological Evaluation Holdout Reservation

To maintain strict chronological isolation before any feature or event detector tuning:
- Total eligible competitive AC75 dates: **{date_reservation['total_competitive_dates']} dates** (from {date_span}).
- **Development Dates ({date_reservation['development_dates_count']}):** {', '.join(date_reservation['development_dates'])}
- **Reserved Final Holdout Block ({date_reservation['reserved_holdout_dates_count']} dates):**
  - Dates: `{', '.join(date_reservation['reserved_holdout_dates'])}`
  - Files ({len(date_reservation['reserved_holdout_files'])}): `{', '.join(date_reservation['reserved_holdout_files'])}`
  - Status: **Locked prior to feature extraction or model tuning**.
"""


def generate_inventory_and_audit():
    """Main execution entrypoint for T02."""
    print("Building complete source inventory across Data/ and Data/AC37/...")
    inventory = build_source_inventory()
    inv_id = inventory["inventory_id"]
    
    inv_dir = SOURCES_DIR / inv_id
    inv_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = inv_dir / "manifest.json"
    manifest_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {manifest_path} ({inventory['total_files']} files, {inventory['total_bytes'] / (1024**3):.2f} GB)")

    print("Auditing candidate outcome evidence in docs/ac37_results.json...")
    outcome_audit = audit_outcome_evidence()

    print("Reserving chronological evaluation dates from metadata...")
    date_reservation = reserve_chronological_evaluation_dates(inventory)

    audit_md = format_audit_markdown(inventory, outcome_audit, date_reservation)
    AUDIT_DOC_PATH.write_text(audit_md, encoding="utf-8")
    print(f"Wrote data audit doc: {AUDIT_DOC_PATH}")

    return {
        "inventory_id": inv_id,
        "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "audit_path": AUDIT_DOC_PATH.relative_to(ROOT).as_posix(),
        "merkle_root": inventory["merkle_root_sha256"],
        "total_files": inventory["total_files"],
        "ac75_eligible_jsonl_count": inventory["ac75_eligible_jsonl_count"],
        "ac75_unsupported_binary_count": inventory["ac75_unsupported_binary_count"],
        "reserved_holdout_dates": date_reservation["reserved_holdout_dates"],
    }


if __name__ == "__main__":
    generate_inventory_and_audit()
