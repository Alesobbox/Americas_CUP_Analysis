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
    for race in races:
        race_paths[race.get("replay_file", race.get("file"))] = (race["id"], "Replay", "Replay")
        race_paths["analysis/" + race["id"] + ".json"] = (race["id"], "Analysis", "Analysis")
    prediction_index = data / "predictions" / "index.json"
    if prediction_index.is_file():
        predictions = json.loads(prediction_index.read_text(encoding="utf-8"))
        race_paths["predictions/index.json"] = (None, "Forecast catalog", "Forecast")
        race_paths["predictions/" + predictions["cup_path"]] = (None, "America's Cup evidence and scenarios", "Forecast")
        race_paths["predictions/" + predictions["source_manifest_path"]] = (None, "Forecast source provenance", "Forecast")
        if (data / "predictions" / "verification.json").is_file():
            race_paths["predictions/verification.json"] = (None, "Forecast verification results", "Forecast")
        for entry in predictions["races"]:
            race_paths["predictions/" + entry["path"]] = (entry["race_id"], "Race forecast", "Forecast")
            race_paths["predictions/models/" + entry["model_ref"] + ".json"] = (None, "Forecast model and validation card", "Forecast")
            for preset in entry.get("presets", []):
                if preset.get("path"):
                    race_paths["predictions/" + preset["path"]] = (entry["race_id"], "Pre-race condition scenario", "Forecast")
    entries = []
    for relative, (race_id, label, view) in sorted(race_paths.items()):
        path = data / relative
        if not path.is_file():
            raise FileNotFoundError(f"Dashboard artifact is missing: {relative}")
        entries.append({"id": relative, "url": "/data/" + relative, "race_id": race_id,
                        "label": label, "view": view, "bytes": path.stat().st_size,
                        "format": path.suffix.removeprefix(".")})
    replayed = sum(race["competitors_count"] for race in races)
    result = {"schema_version": "1.0", "summary": {"race_count": len(races),
              "replayed_boat_races": replayed},
              "artifacts": entries}
    (data / "artifacts.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    result = build_inventory()
    print(json.dumps({"summary": result["summary"], "artifact_count": len(result["artifacts"])}))
