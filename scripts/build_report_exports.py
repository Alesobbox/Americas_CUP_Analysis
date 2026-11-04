"""Serialize canonical historical metrics for analyst downloads; no new formulas."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_FIELDS = ("race_id", "race_date", "boat_id", "team_code", "classification",
                  "reconstructed_rank", "reconstructed_elapsed_s", "metric", "value", "unit",
                  "quality", "coverage_s", "sample_count", "window", "denominator", "source",
                  "method_version", "reason", "source_conflicts")
PERFORMANCE_FIELDS = ("race_id", "boat_id", "team_code", "scope", "leg", "metric", "value",
                      "unit", "index", "peer_mean", "peer_count", "peer_ids", "quality",
                      "coverage_s", "sample_count", "start_ms", "end_ms", "window", "denominator",
                      "source", "method_version", "reason")


def _write_csv(path, fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = stream.getvalue()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="")
    temporary.replace(path)


def export_report_files(detail, analysis_dir):
    """Copy exported values, quality and definitions verbatim into tidy CSV rows."""
    race = detail["race"]
    summary, performance = [], []
    for boat in detail["boats"]:
        common = {"race_id": race["id"], "race_date": race.get("date", ""), "boat_id": boat["id"],
                  "team_code": boat["team_code"], "classification": boat["classification"],
                  "reconstructed_rank": boat.get("official_rank"),
                  "reconstructed_elapsed_s": boat.get("official_elapsed_s"),
                  "source_conflicts": "; ".join(boat.get("source_conflicts") or [])}
        for key, metric in sorted(boat.get("metrics", {}).items()):
            definition = detail.get("definitions", {}).get(key, {})
            summary.append({**common, "metric": key, **metric,
                            "window": definition.get("window", ""),
                            "denominator": definition.get("denominator", ""),
                            "source": definition.get("source", ""),
                            "method_version": detail["method_version"]})
        profile = boat.get("performance") or {}
        for dimension in profile.get("dimensions", []):
            base = {**common, "metric": dimension["id"], "unit": dimension["unit"],
                    "window": dimension["window"], "denominator": dimension["denominator"],
                    "source": dimension["source"], "method_version": profile["method_version"]}
            performance.append({**base, **{k: dimension.get(k) for k in PERFORMANCE_FIELDS if k in dimension},
                                "scope": "all_comparable_legs", "peer_ids": ";".join(sorted({peer
                                    for leg in dimension.get("leg_evidence", []) for peer in leg["peer_ids"]}))})
            for leg in dimension.get("leg_evidence", []):
                performance.append({**base, **leg, "scope": "leg",
                                    "quality": leg.get("quality", dimension["quality"]),
                                    "peer_ids": ";".join(leg["peer_ids"])})
    folder = Path(analysis_dir)
    paths = (folder / f"{race['id']}_summary.csv", folder / f"{race['id']}_performance.csv")
    _write_csv(paths[0], SUMMARY_FIELDS, summary)
    _write_csv(paths[1], PERFORMANCE_FIELDS, performance)
    return paths


def build_reports(root=ROOT):
    folder = Path(root) / "public" / "data" / "analysis"
    details = sorted(path for path in folder.glob("*.json") if path.name != "index.json")
    for path in details:
        export_report_files(json.loads(path.read_text(encoding="utf-8")), folder)
    return {"race_count": len(details), "csv_files": len(details) * 2}


if __name__ == "__main__":
    print(json.dumps(build_reports()))
