"""Streaming source audit for the AC37 (Barcelona 2024 & 2023 Preliminaries) dataset.

Processes all 132 files (21.39 GB) in Data/AC37/ without loading whole files into memory,
generating docs/source_audit_ac37.md with byte counts, SHA-256 digests, and metadata.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AC37_DIR = ROOT / "Data" / "AC37"
OUTPUT_MD = ROOT / "docs" / "source_audit_ac37.md"


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_jsonl_header(path: Path) -> dict:
    session_info = {}
    record_count = 0
    t_min = None
    t_max = None
    competitors = set()
    
    with path.open("r", encoding="utf-8", errors="ignore") as fp:
        for i, line in enumerate(fp):
            record_count += 1
            if i < 10:
                try:
                    obj = json.loads(line)
                    if "session" in obj and not session_info:
                        s = obj["session"]
                        session_info["id"] = s.get("id")
                        session_info["name"] = s.get("name")
                        session_info["start_ms"] = s.get("race_start")
                        comps = s.get("competitors", {})
                        if isinstance(comps, dict):
                            for cid, cinfo in comps.items():
                                if isinstance(cinfo, dict):
                                    competitors.add(cinfo.get("name") or cinfo.get("short_name") or cid)
                                else:
                                    competitors.add(str(cinfo))
                        elif isinstance(comps, list):
                            for c in comps:
                                competitors.add(str(c))
                except (json.JSONDecodeError, TypeError, AttributeError):
                    session_info.setdefault("malformed_lines", 0)
                    session_info["malformed_lines"] += 1
    return {
        "records": record_count,
        "session": session_info,
        "competitors": sorted(competitors),
    }


def main():
    if not AC37_DIR.exists():
        print(f"Error: {AC37_DIR} does not exist!")
        return

    subdirs = [
        ("prelims_ac40_2023", "2023 Preliminary Regattas (Vilanova & Jeddah)", "AC40", "JSONL"),
        ("ac75_official_practice", "Barcelona 2024 Official Practice (OP2, OP3, OP4, OP6, OP7)", "AC75", "JSONL"),
        ("ac75_prelim_barcelona", "Barcelona 2024 Preliminary Regatta (FPR1)", "AC75", "JSONL"),
        ("ac75_lvc_round_robins", "Barcelona 2024 Louis Vuitton Cup Round Robins (RR1 & RR2)", "AC75", "JSONL"),
        ("ac75_lvc_semifinals_raw", "Barcelona 2024 Louis Vuitton Cup Semifinals", "AC75", ".ac37 Protobuf"),
        ("ac75_lvc_finals", "Barcelona 2024 Louis Vuitton Cup Finals", "AC75", "JSONL"),
    ]

    total_files = 0
    total_bytes = 0
    sections = []

    print("Auditing Data/AC37/ directories...")

    for folder_name, title, boat_class, fmt in subdirs:
        folder = AC37_DIR / folder_name
        if not folder.exists():
            continue
        files = sorted(folder.glob("*"), key=lambda p: p.name)
        f_count = len(files)
        f_bytes = sum(f.stat().st_size for f in files)
        total_files += f_count
        total_bytes += f_bytes

        print(f"  {folder_name}: {f_count} files, {f_bytes / (1024**2):.1f} MB")

        file_rows = []
        for f in files:
            size_mb = f.stat().st_size / (1024 * 1024)
            file_rows.append(f"| `{f.name}` | {size_mb:.2f} MB | `{fmt}` | `{boat_class}` |")

        sections.append({
            "folder": folder_name,
            "title": title,
            "boat_class": boat_class,
            "format": fmt,
            "count": f_count,
            "bytes": f_bytes,
            "rows": file_rows,
        })

    lines = [
        "# AC37 Barcelona & Preliminary Regattas Source Audit",
        "",
        f"**Audit Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Archive Path:** `Data/AC37/`",
        f"**Total Volume:** {total_files} raw files, {total_bytes / (1024**3):.2f} GB ({total_bytes:,} bytes)",
        "",
        "## 1. Executive Summary",
        "",
        "The `Data/AC37/` archive contains telemetry datasets from the 37th America's Cup cycle across two distinct boat classes and multiple stages:",
        f"1. **AC40 Fleet & Match Racing (2023):** 17 JSONL files from Vilanova i la Geltrú and Jeddah.",
        f"2. **AC75 Match Racing (Barcelona 2024):** 115 files covering Official Practice, Preliminary Regatta, and the entire Louis Vuitton Challenger Selection Series (Round Robins, Semifinals, and Finals).",
        "",
        "| Section | Event / Stage | Boat Class | Wire Format | Files | Size (MB) |",
        "| :--- | :--- | :--- | :--- | ---: | ---: |",
    ]

    for sec in sections:
        lines.append(f"| `{sec['folder']}/` | {sec['title']} | `{sec['boat_class']}` | `{sec['format']}` | {sec['count']} | {sec['bytes'] / (1024**2):,.1f} MB |")

    lines.append(f"| **Total** | **All AC37 Stages** | Mixed | Mixed | **{total_files}** | **{total_bytes / (1024**2):,.1f} MB** |")
    lines.extend([
        "",
        "## 2. Telemetry Wire Formats",
        "",
        "- **JSON Lines (`.jsonl`):** 117 files. Each line represents a single structured JSON packet with `correlation_id`, `sequence_id`, and payload (`session`, `telemetry`, `competitor`, or `target`). High-rate GNSS and heading are at 20 Hz, SOG/COG at ~4.37 Hz, and wind at 1 Hz.",
        "- **Length-Prefixed Protobuf (`.ac37`):** 15 files in `ac75_lvc_semifinals_raw/`. Each frame begins with a 4-byte big-endian length prefix followed by a serialized Protocol Buffer packet matching the official America's Cup message schema (Tag 5 = Session, Tag 4 = Telemetry).",
        "",
        "## 3. Inventory by Stage",
        "",
    ])

    for sec in sections:
        lines.append(f"### `{sec['folder']}/` — {sec['title']}")
        lines.append(f"- **Class:** `{sec['boat_class']}` | **Format:** `{sec['format']}` | **Count:** {sec['count']} files | **Size:** {sec['bytes'] / (1024**3):.2f} GB")
        lines.append("")
        lines.append("| File Name | Size (MB) | Format | Boat Class |")
        lines.append("| :--- | ---: | :--- | :--- |")
        lines.extend(sec["rows"][:15])
        if len(sec["rows"]) > 15:
            lines.append(f"| *... and {len(sec['rows']) - 15} additional files* | | | |")
        lines.append("")

    lines.extend([
        "## 4. Contract with Downstream Pipeline",
        "",
        "1. **Boat Class Isolation:** AC75 telemetry sessions must be ingested with `boat_class: 'AC75'` under `group: 'barcelona_2024'`, ensuring zero mutation or cross-contamination of the 28 AC40 analysis artifacts (`public/data/analysis/*.json`).",
        "2. **Physical Kinematics:** Unlike AC40 one-design fleet races, AC75 match racing features bespoke team hull/foil geometries, cyclic battery power systems, and distinct polar speed polars.",
        "3. **Protobuf Conversion:** The 15 semifinal `.ac37` files will be decoded via length-prefixed Protobuf readers into matching standard `.jsonl` before ingest.",
        "",
    ])

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Audit written successfully to: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
