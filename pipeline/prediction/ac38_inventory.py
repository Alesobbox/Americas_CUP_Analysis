"""Compact unified inventory reconciling AC37 AC40, AC37 AC75, and AC38 AC40 data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _summarize_ac37_ac40(root: Path) -> dict[str, Any]:
    raw_dir = root / "Data" / "AC37" / "prelims_ac40_2023"
    docs_doc = json.loads((root / "docs" / "ac37_ac40_2023_results.json").read_text(encoding="utf-8"))
    raw_files = sorted(raw_dir.glob("*.jsonl")) if raw_dir.exists() else []
    vnr_comp = [f for f in raw_files if "VNR" in f.name and "6 USA NZL" not in f.name]
    vnr_abandoned = [f for f in raw_files if "6 USA NZL" in f.name]
    jed_practice = [f for f in raw_files if "P" in f.name and "VNR" not in f.name]

    races = docs_doc.get("races", [])
    completed = [r for r in races if r.get("status") == "completed"]
    abandoned = [r for r in races if r.get("status") == "abandoned"]
    boat_races = sum(len(r.get("official_order", [])) + len(r.get("non_finishes", {})) for r in completed)
    racing_days = sorted({r["date"] for r in completed})

    return {
        "cycle": "ac37",
        "boat_class": "AC40",
        "source_doc": "docs/ac37_ac40_2023_results.json",
        "source_doc_sha256": _sha256_file(root / "docs" / "ac37_ac40_2023_results.json"),
        "telemetry_windows_total": len(raw_files),
        "telemetry_breakdown": {
            "vilanova_competitive_fleet": len(vnr_comp),
            "vilanova_abandoned_match_final": len(vnr_abandoned),
            "jeddah_official_practice_and_starts": len(jed_practice),
            "jeddah_official_competitive": 0,
        },
        "documented_races_total": len(races),
        "completed_races": len(completed),
        "abandoned_races": len(abandoned),
        "boat_races": boat_races,
        "racing_days": len(racing_days),
        "racing_dates": racing_days,
        "gap_notes": [
            "Jeddah R1-R8 and Jeddah Match Final lack raw JSONL files in Data/AC37/prelims_ac40_2023/; anchored to captured official/Wikipedia tables.",
            "Vilanova Match Final (2023-09-17 VNR 6 USA NZL.jsonl) was abandoned on leg 1 and is excluded from completed race counts.",
        ],
    }


def _summarize_ac37_ac75(root: Path) -> dict[str, Any]:
    ledger_path = root / ".forecast" / "ac75_learning" / "attempt_ledger.json"
    ac37_path = root / "docs" / "ac37_results.json"
    ac37_doc = json.loads(ac37_path.read_text(encoding="utf-8"))
    races = ac37_doc.get("races", [])
    stopped_doc = ac37_doc.get("stopped_attempts", [])

    attempts = []
    if ledger_path.exists():
        attempts = json.loads(ledger_path.read_text(encoding="utf-8")).get("attempts", [])
    comp_attempts = [a for a in attempts if a.get("domain") == "competitive"]
    practice_attempts = [a for a in attempts if a.get("domain") != "competitive"]
    comp_jsonl = [a for a in comp_attempts if not str(a.get("source_file", "")).endswith(".ac37")]
    practice_jsonl = [a for a in practice_attempts if not str(a.get("source_file", "")).endswith(".ac37")]
    binary_attempts = [a for a in attempts if str(a.get("source_file", "")).endswith(".ac37")]
    stopped_att = [a for a in comp_attempts if a.get("is_stopped_race")]
    resail_att = [a for a in comp_attempts if a.get("is_resail")]

    raw_ac37_sf = list((root / "Data" / "AC37" / "ac75_lvc_semifinals_raw").glob("*.ac37")) if (root / "Data" / "AC37" / "ac75_lvc_semifinals_raw").exists() else []
    ledger_ac37_files = {str(a.get("source_file", "")) for a in binary_attempts}
    disk_only_ac37 = [p for p in raw_ac37_sf if p.name not in ledger_ac37_files]
    binary_count = len(binary_attempts) + len(disk_only_ac37)
    racing_days = sorted({r["date"] for r in races if r.get("date")})
    return {
        "cycle": "ac37",
        "boat_class": "AC75",
        "source_doc": "docs/ac37_results.json",
        "source_doc_sha256": _sha256_file(ac37_path),
        "attempt_ledger_path": ".forecast/ac75_learning/attempt_ledger.json" if ledger_path.exists() else None,
        "attempt_ledger_sha256": _sha256_file(ledger_path) if ledger_path.exists() else None,
        "telemetry_windows_total": len(comp_jsonl) + len(practice_jsonl) + binary_count,
        "telemetry_breakdown": {
            "competitive_attempts_jsonl": len(comp_jsonl),
            "official_practice_jsonl": len(practice_jsonl),
            "semifinal_binary_ac37": binary_count,
            "stopped_race_attempts": len(stopped_att),
            "resail_attempts": len(resail_att),
            "cup_match_raw_telemetry": 0,
        },
        "completed_races": len(races),
        "stopped_races": max(len(stopped_doc), len(stopped_att)),
        "resails": len(resail_att),
        "boat_races": len(races) * 2,
        "racing_days": len(racing_days),
        "racing_dates": racing_days,
        "gap_notes": [
            "37th America's Cup Match (9 races) has no raw JSONL files in Data/AC37/; anchored via captured Wikipedia tables and docs/ac37_verified_anchors.json.",
            "15 LVC Semi-Final binary .ac37 telemetry files are unparsed; match outcomes are independently anchored via captured Wikipedia LVC tables and Luna Rossa SF report.",
        ],
    }


def _summarize_ac38_ac40(root: Path) -> dict[str, Any]:
    ds_idx_path = root / ".forecast" / "dataset" / "index.json"
    sched_path = root / ".forecast" / "scheduled_entry_ledger.json"
    off_path = root / "docs" / "official_results_ac38_prelims.json"
    an_idx_path = root / "public" / "data" / "analysis" / "index.json"

    ds_races = json.loads(ds_idx_path.read_text(encoding="utf-8")).get("races", []) if ds_idx_path.exists() else []
    sched_rows = json.loads(sched_path.read_text(encoding="utf-8")) if sched_path.exists() else []
    off_races = json.loads(off_path.read_text(encoding="utf-8")).get("races", []) if off_path.exists() else []
    an_races = json.loads(an_idx_path.read_text(encoding="utf-8")).get("races", []) if an_idx_path.exists() else []

    comp_ds = [r for r in ds_races if not r.get("practice", False)]
    prac_ds = [r for r in ds_races if r.get("practice", False)]
    comp_sched = [r for r in sched_rows if r.get("competitive", False) and not r.get("practice", False)]
    started_sched = [r for r in comp_sched if r.get("source_started")]
    completed_sched = [r for r in comp_sched if r.get("completed")]
    racing_days = sorted({r["date"] for r in comp_ds if r.get("date")})

    return {
        "cycle": "ac38",
        "boat_class": "AC40",
        "source_doc": "docs/official_results_ac38_prelims.json",
        "source_doc_sha256": _sha256_file(off_path),
        "dataset_index_sha256": _sha256_file(ds_idx_path) if ds_idx_path.exists() else None,
        "scheduled_ledger_sha256": _sha256_file(sched_path) if sched_path.exists() else None,
        "telemetry_windows_total": len(ds_races),
        "analysis_sessions_total": len(an_races),
        "telemetry_breakdown": {
            "competitive_sessions": len(comp_ds),
            "practice_sessions": len(prac_ds),
        },
        "completed_races": len(off_races),
        "scheduled_entries": len(comp_sched),
        "started_boat_races": len(started_sched),
        "completed_boat_races": len(completed_sched),
        "racing_days": len(racing_days),
        "racing_dates": racing_days,
        "gap_notes": [
            "2 AC38 match finals (Cagliari and Naples) have independently captured winner reports; 16 fleet races rely on AC38 telemetry on-water finish reconstructions plus partial news podiums.",
            "10 practice sessions are retained only in telemetry inventory and strictly excluded from strength fitting.",
        ],
    }


def build_inventory(root: Path, *, write: bool = True) -> dict[str, Any]:
    root = Path(root)
    doc = {
        "schema_version": "ac38-inventory-1",
        "domains": {
            "ac37_ac40": _summarize_ac37_ac40(root),
            "ac37_ac75": _summarize_ac37_ac75(root),
            "ac38_ac40": _summarize_ac38_ac40(root),
        },
    }
    if write:
        out_path = root / ".forecast" / "ac38" / "inventory.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc
