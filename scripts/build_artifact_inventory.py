"""Publish a compact, exhaustive download catalog for generated dashboard data."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build_inventory(root: Path = ROOT) -> dict:
    data = root / "public" / "data"
    manifest = json.loads((data / "manifests.json").read_text(encoding="utf-8"))
    races = [race for regatta in manifest["regattas"] for race in regatta["races"]]
    race_paths = {"manifests.json": (None, "Race catalog", "Reports"),
                  "analysis/index.json": (None, "Historical analysis index", "Analysis")}
    if (data / "presentation/race_previews.json").is_file():
        race_paths["presentation/race_previews.json"] = (None, "Race course preview index", "Replay")
    for race in races:
        race_paths[race.get("replay_file", race.get("file"))] = (race["id"], "Replay", "Replay")
        race_paths["analysis/" + race["id"] + ".json"] = (race["id"], "Analysis", "Analysis")
        for suffix, label in (("summary", "Race summary CSV"), ("performance", "Boat and leg performance CSV")):
            relative = f"analysis/{race['id']}_{suffix}.csv"
            if (data / relative).is_file():
                race_paths[relative] = (race["id"], label, "Reports")
    race_ids = {race["id"] for race in races}
    for environment in (data / "environment").rglob("*.json"):
        relative = environment.relative_to(data).as_posix()
        is_race = environment.stem in race_ids and environment.parent == data / "environment"
        race_paths[relative] = (environment.stem if is_race else None,
                                "Historical environment" if is_race else "Environment source response",
                                "Replay")
    prediction_index = data / "predictions" / "index.json"
    if prediction_index.is_file():
        predictions = json.loads(prediction_index.read_text(encoding="utf-8"))
        race_paths["predictions/index.json"] = (None, "Forecast catalog", "Forecast")
        race_paths["predictions/" + predictions["cup_path"]] = (None, "America's Cup evidence and scenarios", "Forecast")
        race_paths["predictions/" + predictions["source_manifest_path"]] = (None, "Forecast source provenance", "Forecast")
        if (data / "predictions/cup_2027.json").is_file():
            race_paths["predictions/cup_2027.json"] = (None, "America's Cup compatibility reference", "Forecast")
        if (data / "predictions" / "verification.json").is_file():
            race_paths["predictions/verification.json"] = (None, "Forecast verification results", "Forecast")
        for entry in predictions["races"]:
            race_paths["predictions/" + entry["path"]] = (entry["race_id"], "Race forecast", "Forecast")
            race_paths["predictions/models/" + entry["model_ref"] + ".json"] = (None, "Forecast model and validation card", "Forecast")
            for preset in entry.get("presets", []):
                if preset.get("path"):
                    race_paths["predictions/" + preset["path"]] = (entry["race_id"], "Pre-race condition scenario", "Forecast")
                if preset.get("model_ref"):
                    model = "predictions/models/" + preset["model_ref"] + ".json"
                    if (data / model).is_file():
                        race_paths[model] = (None, "Forecast model and validation card", "Forecast")
                if preset.get("source_manifest_hash"):
                    manifest = "predictions/manifests/" + preset["source_manifest_hash"] + ".json"
                    if (data / manifest).is_file():
                        race_paths[manifest] = (None, "Forecast source provenance", "Forecast")
        # Immutable earlier objects remain valid for readers holding an older
        # index. Keep every public JSON discoverable without calling it current.
        for retained in (data / "predictions").rglob("*.json"):
            relative = retained.relative_to(data).as_posix()
            race_paths.setdefault(relative, (None, "Forecast archive artifact", "Forecast"))
    entries = []
    kinds = {"Replay": "replay", "Analysis": "analysis", "Historical environment": "environment",
             "Race summary CSV": "summary_csv", "Boat and leg performance CSV": "performance_csv",
             "Race forecast": "forecast", "Pre-race condition scenario": "scenario",
             "Race catalog": "catalog", "Historical analysis index": "catalog", "Forecast catalog": "catalog", "Race course preview index": "catalog",
             "America's Cup evidence and scenarios": "cup", "Forecast model and validation card": "model",
             "Forecast verification results": "verification", "Forecast source provenance": "provenance",
             "Environment source response": "source", "Forecast archive artifact": "archive",
             "America's Cup compatibility reference": "alias"}
    primary = {"replay", "analysis", "environment", "summary_csv", "performance_csv", "forecast"}
    for relative, (race_id, label, view) in sorted(race_paths.items()):
        path = data / relative
        if not path.is_file():
            raise FileNotFoundError(f"Dashboard artifact is missing: {relative}")
        kind = kinds[label]
        status = "retained" if kind == "archive" else "supporting" if kind in {"source", "model", "provenance", "verification", "alias"} else "current"
        entries.append({"id": relative, "url": "/data/" + relative, "race_id": race_id,
                        "label": label, "view": view, "bytes": path.stat().st_size,
                        "format": path.suffix.removeprefix("."), "kind": kind, "status": status,
                        "scope": "race" if race_id else "archive",
                        "primary_download": race_id is not None and kind in primary})
    replayed = sum(race["competitors_count"] for race in races)
    result = {"schema_version": "1.1", "summary": {"race_count": len(races),
              "replayed_boat_races": replayed},
              "artifacts": entries}
    (data / "artifacts.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    result = build_inventory()
    print(json.dumps({"summary": result["summary"], "artifact_count": len(result["artifacts"])}))
