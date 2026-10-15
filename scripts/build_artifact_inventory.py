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
