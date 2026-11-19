"""Publish a compact, exhaustive download catalog for generated dashboard data."""

from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_inventory(root: Path = ROOT) -> dict:
    data = root / "public" / "data"
    manifest = json.loads((data / "manifests.json").read_text(encoding="utf-8"))
    races = [race for regatta in manifest["regattas"] for race in regatta["races"]]
    race_paths = {
        "manifests.json": (None, "Race catalog", "Reports"),
        "analysis/index.json": (None, "Historical analysis index", "Analysis"),
    }
    if (data / "presentation/race_previews.json").is_file():
        race_paths["presentation/race_previews.json"] = (
            None,
            "Race course preview index",
            "Replay",
        )
    for report in (data / "research").glob("*.json"):
        race_paths[report.relative_to(data).as_posix()] = (
            None,
            "AC38 research: " + report.stem.replace("_", " "),
            "Analysis",
        )
    for race in races:
        race_paths[race.get("replay_file", race.get("file"))] = (race["id"], "Replay", "Replay")
        race_paths["analysis/" + race["id"] + ".json"] = (race["id"], "Analysis", "Analysis")
        for suffix, label in (
            ("summary", "Race summary CSV"),
            ("performance", "Boat and leg performance CSV"),
        ):
            relative = f"analysis/{race['id']}_{suffix}.csv"
            if (data / relative).is_file():
                race_paths[relative] = (race["id"], label, "Reports")
    race_ids = {race["id"] for race in races}
    for environment in (data / "environment").rglob("*.json"):
        relative = environment.relative_to(data).as_posix()
        if environment.parent == data / "environment" / "boats" and environment.stem in race_ids:
            race_paths[relative] = (environment.stem, "Historical boat environment", "Replay")
        elif environment.parent == data / "environment" / "bundles":
            race_paths[relative] = (None, "Environment provenance bundle", "Replay")
        else:
            is_race = environment.stem in race_ids and environment.parent == data / "environment"
            race_paths[relative] = (
                environment.stem if is_race else None,
                "Historical environment" if is_race else "Environment source response",
                "Replay",
            )
    entries = []
    kinds = {
        "Replay": "replay",
        "Analysis": "analysis",
        "Historical environment": "environment",
        "Historical boat environment": "environment_boats",
        "Environment provenance bundle": "provenance",
        "Race summary CSV": "summary_csv",
        "Boat and leg performance CSV": "performance_csv",
        "Race catalog": "catalog",
        "Historical analysis index": "catalog",
        "Race course preview index": "catalog",
        "Environment source response": "source",
    }
    primary = {"replay", "analysis", "environment", "summary_csv", "performance_csv"}
    for relative, (race_id, label, view) in sorted(race_paths.items()):
        path = data / relative
        if not path.is_file():
            raise FileNotFoundError(f"Dashboard artifact is missing: {relative}")
        kind = "analysis" if label.startswith("AC38 research:") else kinds[label]
        status = (
            "retained"
            if kind == "archive"
            else "supporting"
            if kind
            in {"source", "model", "provenance", "verification", "alias", "environment_boats"}
            else "current"
        )
        entries.append(
            {
                "id": relative,
                "url": "/data/" + relative,
                "race_id": race_id,
                "label": label,
                "view": view,
                "bytes": path.stat().st_size,
                "format": path.suffix.removeprefix("."),
                "kind": kind,
                "status": status,
                "scope": "race" if race_id else "archive",
                "primary_download": race_id is not None
                and kind in primary
                and label != "Historical boat environment",
            }
        )
    replayed = sum(race["competitors_count"] for race in races)
    result = {
        "schema_version": "1.1",
        "summary": {"race_count": len(races), "replayed_boat_races": replayed},
        "artifacts": entries,
    }
    (data / "artifacts.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    result = build_inventory()
    print(json.dumps({"summary": result["summary"], "artifact_count": len(result["artifacts"])}))
