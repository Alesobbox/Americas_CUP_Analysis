"""Attach saved research only while its data and producer code still match."""

import hashlib
import json
from pathlib import Path


def dependency_hash(details):
    digest = hashlib.sha256()
    boat_fields = (
        "id",
        "team_code",
        "classification",
        "start",
        "legs",
        "gates",
        "source_coverage",
        "manoeuvres",
        "source_conflicts",
        "polar_samples",
    )
    for rid, detail in sorted(details.items()):
        tactical = detail.get("tactical_insights") or {}
        payload = {
            "id": rid,
            "race": detail["race"],
            "sample_provenance": detail.get("polar_sample_provenance"),
            "wind_provenance": tactical.get("source_provenance"),
            "boats": [{key: boat.get(key) for key in boat_fields} for boat in detail["boats"]],
        }
        digest.update(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        )
    for folder in (Path(__file__).parent, Path(__file__).parents[1] / "polar"):
        for path in sorted(folder.glob("*.py")):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def attach_cached_research(index, details, analysis_dir):
    folder = Path(analysis_dir).parent / "research"
    receipt = folder / "receipt.json"
    if not receipt.is_file():
        return
    manifest = json.loads(receipt.read_text(encoding="utf8"))
    if manifest.get("dependency_sha256") != dependency_hash(details):
        return
    for filename, expected in manifest["artifacts"].items():
        path = folder / filename
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            return
    index["research_provenance"] = manifest
    for key, filename in (
        ("polar_research", "polar_experiments.json"),
        ("wind_forecast_model", "wind_forecast.json"),
        ("timing_research", "timing_summary.json"),
    ):
        report = json.loads((folder / filename).read_text(encoding="utf8"))
        index[key] = {name: value for name, value in report.items() if name != "per_race"}


def receipt_for(details, data):
    artifacts = {}
    for filename in ("polar_experiments.json", "wind_forecast.json", "timing_summary.json"):
        artifacts[filename] = hashlib.sha256(
            (data / "research" / filename).read_bytes()
        ).hexdigest()
    return {
        "schema_version": "ac38-research-receipt-1",
        "dependency_sha256": dependency_hash(details),
        "artifacts": artifacts,
        "availability_basis": "retrospective measurements and historical model context",
    }
